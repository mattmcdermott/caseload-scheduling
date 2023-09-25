"""Class and script for scheduling student therapy appointments."""
import os
from itertools import product

import matplotlib.cm as cm
import matplotlib.pyplot as plt
import pandas as pd
import pyomo.environ as pe
import pyomo.gdp as pyogdp
from tqdm import tqdm

from constraints import *
from objective import *
from plotting import *
from utils import *

ub = 5 * 1440  # total number of mins in a week


class Scheduler:
    """
    Schedule appointments for students to attend therapy sessions.
    """

    def __init__(self, student_file_path, availability_file_path):
        """
        Read case and session data into Pandas DataFrames
        Args:
            student_file_path (str): path to case data in CSV format
            availability_file_path (str): path to SESSION session data in CSV format
        """
        self.df_cases = pd.read_excel(student_file_path)
        self.df_days = pd.read_excel(availability_file_path)

        self.available_windows = self._get_available_windows()
        self.sessions = self._get_unique_availabilities()

        self.student_availabilities = self._get_student_availabilities()
        self.model = self.create_model()

    def create_model(self):
        """Create pyomo model"""
        model = pe.ConcreteModel()

        model.CASES = pe.Set(initialize=self.df_cases["Name"].tolist())
        model.SESSIONS = pe.Set(initialize=list(self.sessions.keys()))

        tasks = []
        for case, session in model.CASES * model.SESSIONS:
            if self._check_if_available(case, session):
                tasks.append((case, session))

        model.TASKS = pe.Set(initialize=tasks, dimen=2)
        model.CASE_DURATION = pe.Param(
            model.CASES, initialize=self._generate_case_durations()
        )
        model.SESSION_START_TIME = pe.Param(
            model.SESSIONS, initialize=self._generate_session_start_times()
        )
        model.SESSION_END_TIME = pe.Param(
            model.SESSIONS, initialize=self._generate_session_end_times()
        )
        model.DISJUNCTIONS = pe.Set(
            initialize=self._generate_disjunctions(model.TASKS), dimen=4
        )

        model.M = pe.Param(initialize=1e3 * ub)  # big M
        num_cases = self.df_cases.shape[0]

        model.SESSION_ASSIGNED = pe.Var(model.TASKS, domain=pe.Binary)
        model.CASE_START_TIME = pe.Var(
            model.TASKS, bounds=(0, ub), within=pe.PositiveReals
        )
        model.STUDENTS_IN_SESSION = pe.Var(
            model.SESSIONS, bounds=(0, num_cases), within=pe.PositiveReals
        )

        model.OBJECTIVE = pe.Objective(rule=summation, sense=pe.maximize)
        model.CASE_START = pe.Constraint(model.TASKS, rule=case_start_time)
        model.CASE_END_TIME = pe.Constraint(model.TASKS, rule=case_end_time)
        model.SESSION_ASSIGNMENT = pe.Constraint(model.CASES, rule=session_assignment)

        print("Starting disjunction constraints...")

        model.DISJUNCTIONS_RULE = pyogdp.Disjunction(
            model.DISJUNCTIONS, rule=no_case_overlap
        )
        print("Finished disjunction constraints.")

        model.SESSION_UTIL = pe.Constraint(model.SESSIONS, rule=session_util)

        pe.TransformationFactory("gdp.bigm").apply_to(model)

        return model

    def solve(self, solver_name, options=None, solver_path=None, local=True):
        if solver_path is not None:
            solver = pe.SolverFactory(solver_name, executable=solver_path)
        else:
            solver = pe.SolverFactory(solver_name)

        if options is not None:
            for key, v in options.items():
                solver.options[key] = v

        if local:
            solver_results = solver.solve(self.model, tee=True)
        else:
            solver_manager = pe.SolverManagerFactory("neos")
            solver_results = solver_manager.solve(self.model, opt=solver)

        results = [
            {
                "Case": case,
                "Grade": self.df_cases[self.df_cases["Name"] == case]["Grade"].iloc[0],
                "Session": session,
                "Start": self.model.CASE_START_TIME[case, session](),
                "End": self.model.CASE_START_TIME[case, session]()
                + self.model.CASE_DURATION[case],
                "Assignment": self.model.SESSION_ASSIGNED[case, session](),
            }
            for (case, session) in self.model.TASKS
        ]

        self.df_times = pd.DataFrame(results)
        self.df_times[self.df_times["Assignment"] == 1].drop(
            columns=["Assignment"]
        ).to_excel("results.xlsx")

        all_cases = self.model.CASES.value_list
        cases_assigned = []
        for case, session in self.model.SESSION_ASSIGNED:
            if self.model.SESSION_ASSIGNED[case, session]() == 1:
                cases_assigned.append(case)

        cases_missed = list(set(all_cases).difference(cases_assigned))
        print(
            "Number of cases assigned = {} out of {}:".format(
                len(cases_assigned), len(all_cases)
            )
        )
        print("Cases assigned: ", cases_assigned)
        print(
            "Number of cases missed = {} out of {}:".format(
                len(cases_missed), len(all_cases)
            )
        )
        print("Cases missed: ", cases_missed)
        self.model.STUDENTS_IN_SESSION.pprint()
        print(
            "Total Objective = {}".format(
                sum(self.model.STUDENTS_IN_SESSION.get_values().values())
            )
        )
        print(
            "Number of constraints = {}".format(
                solver_results["Problem"].__getitem__(0)["Number of constraints"]
            )
        )

    def plot_results(self):
        df = self.df_times
        cases = sorted(list(df["Case"].unique()))
        sessions = sorted(list(df["Session"].unique()))

        bar_style = {"alpha": 1.0, "lw": 25, "solid_capstyle": "butt"}
        text_style = {
            "color": "white",
            "weight": "bold",
            "ha": "center",
            "va": "center",
        }
        colors = cm.Dark2.colors

        df.sort_values(by=["Case", "Session"])
        df.set_index(["Case", "Session"], inplace=True)

        fig, ax = plt.subplots(1, 1)
        for c_ix, c in enumerate(cases, 1):
            for _, s in enumerate(sessions, 1):
                if (c, s) in df.index:
                    xs = df.loc[(c, s), "Start"]
                    xf = (
                        df.loc[(c, s), "Start"]
                        + self.df_cases[self.df_cases["Name"] == c]["Duration"].iloc[0]
                    )
                    ax.plot([xs, xf], [s] * 2, c=colors[c_ix % 7], **bar_style)
                    ax.text((xs + xf) / 2, s, c, **text_style)

        ax.set_title("Assigning Ophthalmology Cases to SESSION Sessions")
        ax.set_xlabel("Time")
        ax.set_ylabel("Sessions")
        ax.grid(True)

        fig.tight_layout()
        plt.show()

    def _generate_case_durations(self) -> dict:
        """
        Generate mapping of students sessions to durations

        Returns:
            dictionary with student name as key and duration as value (mins)
        """
        return pd.Series(
            self.df_cases["Duration"].values, index=self.df_cases["Name"]
        ).to_dict()

    def _generate_session_start_times(self):
        """
        Generate mapping from SessionID to session start time

        Returns:
            (dict): dictionary with SessionID as key and start time in minutes since midnight as value
        """
        return {session_id: window[0] for session_id, window in self.sessions.items()}

    def _generate_session_end_times(self) -> dict:
        """
        Generate mapping of all availability to duration in minutes

        Returns:
            (dict): dictionary with availability day as key and duration as value (mins)
        """
        return {session_id: window[1] for session_id, window in self.sessions.items()}

    def _get_available_windows(self):
        windows = []
        for _, row in self.df_days.iterrows():
            windows.append(
                (
                    day_and_time_to_mins(row["Day"], row["Start"].isoformat()),
                    day_and_time_to_mins(row["Day"], row["End"].isoformat()),
                )
            )

        return windows

    def _get_unique_availabilities(self):
        availabilities = set()
        for _, row in self.df_cases.iterrows():
            for col, day in row.items():
                if "Day" in col and not pd.isna(day):
                    num = int(col.split("_")[1])
                    availability = (
                        day_and_time_to_mins(day, row[f"Start_{num}"].isoformat()),
                        day_and_time_to_mins(day, row[f"End_{num}"].isoformat()),
                    )
                    if any(
                        is_within_window(availability, available_window)
                        for available_window in self.available_windows
                    ):
                        availabilities.add(availability)

        return {i: t for i, t in enumerate(availabilities)}

    def _get_student_availabilities(self):
        availabilities = {}
        for _, row in self.df_cases.iterrows():
            name = row["Name"]
            times = []
            for col, val in row.items():
                if "Day" in col and not pd.isna(val):
                    num = int(col.split("_")[1])
                    availability = (
                        day_and_time_to_mins(val, row[f"Start_{num}"].isoformat()),
                        day_and_time_to_mins(val, row[f"End_{num}"].isoformat()),
                    )
                    times.append(availability)
            availabilities[name] = times
        return availabilities

    def _generate_availabilities(self, tasks):
        availabilities = {}
        for case, session in tasks:
            availabilities[case, session] = self._check_if_available(case, session)
        return availabilities

    def _check_if_available(self, case, session):
        """ """
        for window in self.student_availabilities[case]:
            if is_within_window(window, self.sessions[session]):
                return True
        return False

    def _generate_disjunctions(self, tasks):
        """
        Returns:
            disjunctions (list): list of tuples containing disjunctions
        """
        disjunctions = []
        for t1, t2 in tqdm(product(tasks, tasks)):
            if t1[0] != t2[0] and is_overlapping(
                self.sessions[t1[1]], self.sessions[t2[1]]
            ):
                disjunctions.append((t1, t2))

        print(f"Made {len(disjunctions)} disjunctions!")

        return disjunctions

    def _generate_student_disjunctions(self, tasks):
        disjunctions = []
        for t1, t2 in tqdm(product(tasks, tasks)):
            if t1[0] != t2[0] and is_overlapping(
                self.sessions[t1[1]], self.sessions[t2[1]]
            ):
                disjunctions.append((t1, t2))

        print(f"Made {len(disjunctions)} disjunctions!")


if __name__ == "__main__":
    case_path = os.path.join(os.getcwd(), "data", "students_with_groups.xlsx")
    session_path = os.path.join(os.getcwd(), "data", "availability.xlsx")

    options = {"seconds": 1000}
    scheduler = Scheduler(
        student_file_path=case_path, availability_file_path=session_path
    )
    scheduler.solve(solver_name="cbc", options=options)
