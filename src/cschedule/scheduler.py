"""Class and script for scheduling student therapy appointments."""
from itertools import product
from pathlib import Path

import pandas as pd
import pyomo.environ as pe
import pyomo.gdp as pyogdp

from cschedule.constraints import *
from cschedule.objective import summation
from cschedule.plotting import plot_calendar
from cschedule.utils import *

TOTAL_MINS_IN_WEEK = 5 * 1440


class Scheduler:
    """
    This class is used to schedule student therapy appointments. It takes in two tables:
    one containing the cases, and another containing available sessions.

    Please see the data folder for examples of the format of these tables.

    This code was inspired by Lewis Woolfson's repository:
        https://github.com/Lewisw3/theatre-scheduling
    """

    def __init__(self, cases_fn=None, sessions_fn=None, no_duplicate_days=True):
        """
        Args:
            cases_fn (str): filename/path to case data in XLSX or CSV format. If this is
                not provided, the default case data will be used (data/cases.xlsx).
            sessions_fn (str): filename/path to session data in XLSX or CSV format. If
                this is not provided, the default session data will be used
                (data/sessions.xlsx).
            no_duplicate_days (bool): if True, then students will not be scheduled for two
                sessions on the same day. Defaults to True.
        """
        data_dir = Path(__file__).resolve().parents[1] / "data"

        if cases_fn is None:
            cases_fn = data_dir / "cases.xlsx"
        if sessions_fn is None:
            sessions_fn = data_dir / "sessions.xlsx"

        load_function = pd.read_excel if cases_fn.endswith("xlsx") else pd.read_csv

        self.df_cases = load_function(cases_fn)
        self.df_sessions = load_function(sessions_fn)

        self.available_windows = self._get_available_windows()
        self.sessions = self._get_unique_availabilities()

        self.student_availabilities = self._get_student_availabilities()
        self.model = self._create_model(no_duplicate_days)

    def _create_model(self, no_duplicate_days):
        """Create pyomo model. This is called in the constructor.

        no_duplicate_days (bool): if True, then students will not be scheduled for two
            sessions on the same day. Defaults to True.

        """
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
        model.STUDENT_DISJUNCTIONS = pe.Set(
            initialize=self._generate_student_disjunctions(model.TASKS), dimen=4
        )

        model.M = pe.Param(initialize=1e3 * TOTAL_MINS_IN_WEEK)
        num_cases = self.df_cases.shape[0]

        model.SESSION_ASSIGNED = pe.Var(model.TASKS, domain=pe.Binary)
        model.CASE_START_TIME = pe.Var(
            model.TASKS, bounds=(0, TOTAL_MINS_IN_WEEK), within=pe.PositiveReals
        )
        model.STUDENTS_IN_SESSION = pe.Var(
            model.SESSIONS, bounds=(0, num_cases), within=pe.PositiveReals
        )

        model.OBJECTIVE = pe.Objective(rule=summation, sense=pe.maximize)

        model.CASE_START = pe.Constraint(model.TASKS, rule=case_start_time)
        model.CASE_END_TIME = pe.Constraint(model.TASKS, rule=case_end_time)
        model.SESSION_ASSIGNMENT = pe.Constraint(model.CASES, rule=only_one_session)

        model.DISJUNCTIONS_RULE = pyogdp.Disjunction(
            model.DISJUNCTIONS, rule=no_case_overlap
        )
        if no_duplicate_days:
            model.STUDENT_DISJUNCTIONS_RULE = pyogdp.Disjunction(
                model.STUDENT_DISJUNCTIONS, rule=no_same_day
            )

        model.SESSION_UTIL = pe.Constraint(model.SESSIONS, rule=session_utilized)

        pe.TransformationFactory("gdp.bigm").apply_to(model)

        return model

    def solve(self, solver_name="appsi_highs", options=None):
        solver = pe.SolverFactory(solver_name)

        if options is not None:
            for key, v in options.items():
                solver.options[key] = v

        solver_results = solver.solve(self.model, tee=True)
        self._log_solver_output()

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

        results_df = pd.read_excel("results.xlsx")
        plot_calendar(results_df)

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

    def _generate_disjunctions(self, tasks):
        """
        Generate disjunctions to prevent cases from overlapping.
        To save on computation a priori, we only generate disjunctions for sessions that
        we know overlap (e.g., 9:00AM-10:00AM and 8:45AM-9:30AM).
        """
        disjunctions = []
        for t1, t2 in product(tasks, tasks):
            if t1[0] != t2[0] and is_overlapping(
                self.sessions[t1[1]], self.sessions[t2[1]]
            ):
                disjunctions.append((t1, t2))

        return disjunctions

    def _generate_student_disjunctions(self, tasks):
        """
        Generates disjunctions for cases that are assigned to the same student. This
        is determined by looking at the first part of the case name (e.g., Steve in
        Steve_1) and checking if they are the same.
        """
        disjunctions = []
        for t1, t2 in product(tasks, tasks):
            if t1[0].split("_")[0] == t2[0].split("_")[0] and t1[0] != t2[0]:
                disjunctions.append((t1, t2))

        return disjunctions

    def _get_available_windows(self):
        """
        Gets available session times, converted to minutes since Monday (12AM) from the
        sessions table.

        Returns:
            (list): list of tuples with start and end times of available windows
        """
        windows = []
        for _, row in self.df_sessions.iterrows():
            windows.append(
                (
                    day_and_time_to_mins(row["Day"], row["Start"].isoformat()),
                    day_and_time_to_mins(row["Day"], row["End"].isoformat()),
                )
            )

        return windows

    def _get_unique_availabilities(self):
        """
        Gets unique available session times from the cases table. This reduces the
        complexity of the problem by removing duplicates.

        """
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
        """
        Returns a dict of student availabilities, where the key is the student name and
        the value is a list of tuples of available windows.
        """
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

    def _check_if_available(self, case, session):
        """
        Checks if a case is available for a given session.
        """
        for window in self.student_availabilities[case]:
            if window == self.sessions[session]:
                return True
        return False

    def _log_solver_output(self):
        """Prints out the results of the solver."""
        all_cases = self.model.CASES.value_list
        cases_assigned = []
        for case, session in self.model.SESSION_ASSIGNED:
            if self.model.SESSION_ASSIGNED[case, session]() == 1:
                cases_assigned.append(case)

        cases_missed = list(set(all_cases).difference(cases_assigned))

        print(f"Num. cases assigned: {len(cases_assigned)} of {len(all_cases)}")
        print(f"Num. cases assigned: {len(cases_missed)} of {len(all_cases)}")
        print("Cases assigned: ", cases_assigned)
        print("Cases missed: ", cases_missed)
        self.model.STUDENTS_IN_SESSION.pprint()
        print(
            "Total objective:"
            f" {sum(self.model.STUDENTS_IN_SESSION.get_values().values())}"
        )
