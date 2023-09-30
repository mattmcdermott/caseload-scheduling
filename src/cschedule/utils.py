from pandas import to_timedelta

__all__ = [
    "time_to_mins",
    "day_and_time_to_mins",
    "is_within_window",
    "is_overlapping",
]


def time_to_mins(time):
    return to_timedelta(time).total_seconds() / 60


def day_and_time_to_mins(day, time):
    return (day - 1) * 1440 + time_to_mins(time)


def is_within_window(test_window, other_window):
    return test_window[0] >= other_window[0] and test_window[1] <= other_window[1]


def is_overlapping(test_window, other_window):
    return test_window[0] <= other_window[1] and test_window[1] >= other_window[0]
