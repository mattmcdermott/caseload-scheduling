from cschedule.scheduler import Scheduler

cases_path = "../data/cases.xlsx"
sessions_path = "../data/sessions.xlsx"

# cases_path = (
#     "/Users/mcdermott/My Drive/postgrad/f23/scheduling/students_with_groups.xlsx"
# )
# sessions_path = "/Users/mcdermott/My Drive/postgrad/f23/scheduling/availability.xlsx"

if __name__ == "__main__":
    scheduler = Scheduler(cases_fn=cases_path, sessions_fn=sessions_path)
    scheduler.solve(solver_name="appsi_highs")
