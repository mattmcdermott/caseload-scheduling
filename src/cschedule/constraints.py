"""Constraint functions for the pyomo model."""

__all__ = [
    "case_start_time",
    "case_end_time",
    "session_assignment",
    "no_case_overlap",
    "no_double_days",
    "session_utilized",
]


def case_start_time(model, case, session):
    """Ensures that the case start time is after the start time of the session."""
    return model.CASE_START_TIME[case, session] >= model.SESSION_START_TIME[session] - (
        (1 - model.SESSION_ASSIGNED[(case, session)]) * model.M
    )


def case_end_time(model, case, session):
    """Ensures that the case end time is before the end time of the session."""
    return model.CASE_START_TIME[case, session] + model.CASE_DURATION[
        case
    ] <= model.SESSION_END_TIME[session] + (
        (1 - model.SESSION_ASSIGNED[(case, session)]) * model.M
    )


def session_assignment(model, case):
    """Ensures that cases are only assigned to one session."""
    return (
        sum([model.SESSION_ASSIGNED[task] for task in model.TASKS if task[0] == case])
        <= 1
    )


def no_case_overlap(model, case1, session1, case2, session2):
    """
    Ensures that cases are not scheduled in overlapping sessions.
    """
    task1 = (case1, session1)
    task2 = (case2, session2)
    return [
        model.CASE_START_TIME[task1] + model.CASE_DURATION[case1]
        <= model.CASE_START_TIME[task2]
        + (
            (2 - model.SESSION_ASSIGNED[task1] - model.SESSION_ASSIGNED[task2])
            * model.M
        ),
        model.CASE_START_TIME[task2] + model.CASE_DURATION[case2]
        <= model.CASE_START_TIME[task1]
        + (
            (2 - model.SESSION_ASSIGNED[task1] - model.SESSION_ASSIGNED[task2])
            * model.M
        ),
    ]


def session_utilized(model, session):
    """Ensures that"""
    return model.STUDENTS_IN_SESSION[session] == sum(
        [model.SESSION_ASSIGNED[task] for task in model.TASKS if task[1] == session]
    )


def no_double_days(model, case1, session1, case2, session2):
    """
    Ensures that students are not scheduled for two sessions on the same day.
    """
    task1 = (case1, session1)
    task2 = (case2, session2)
    return [
        (model.CASE_START_TIME[task1] - model.CASE_START_TIME[task2])
        >= (
            800
            - (2 - model.SESSION_ASSIGNED[task1] - model.SESSION_ASSIGNED[task2])
            * model.M
        ),
        (model.CASE_START_TIME[task2] - model.CASE_START_TIME[task1])
        >= (
            800
            - (2 - model.SESSION_ASSIGNED[task1] - model.SESSION_ASSIGNED[task2])
            * model.M
        ),
    ]
