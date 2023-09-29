"""Constraint functions for pyomo model"""


def case_start_time(model, case, session):
    """Case start time must be after start time of available session"""
    return model.CASE_START_TIME[case, session] >= model.SESSION_START_TIME[session] - (
        (1 - model.SESSION_ASSIGNED[(case, session)]) * model.M
    )


def case_end_time(model, case, session):
    """Case end time must be before end time of available session"""
    return model.CASE_START_TIME[case, session] + model.CASE_DURATION[
        case
    ] <= model.SESSION_END_TIME[session] + (
        (1 - model.SESSION_ASSIGNED[(case, session)]) * model.M
    )


def session_assignment(model, case):
    """Cases can be assigned to a maximum of one session"""
    return (
        sum([model.SESSION_ASSIGNED[task] for task in model.TASKS if task[0] == case])
        <= 1
    )


def no_case_overlap(model, case1, session1, case2, session2):
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


def no_double_days(model, case1, session1, case2, session2):
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


def session_util(model, session):
    """How much of the session is utilized"""
    return model.STUDENTS_IN_SESSION[session] == sum(
        [model.SESSION_ASSIGNED[task] for task in model.TASKS if task[1] == session]
    )