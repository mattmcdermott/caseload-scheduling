from enum import Enum

from pandas import to_timedelta

__all__ = [
    "time_to_mins",
    "day_and_time_to_mins",
    "is_within_window",
    "is_overlapping",
    "mins_to_day_and_time",
]


class Day(Enum):
    """Enumerates the days of the week, starting with Sunday indexed 0."""

    SUN = 0
    MON = 1
    TUE = 2
    WED = 3
    THU = 4
    FRI = 5
    SAT = 6


def time_to_mins(time: str):
    """Converts a time (e.g. 9:30 AM) to minutes since midnight."""
    return to_timedelta(time).total_seconds() / 60


def day_and_time_to_mins(day: int, time: str):
    """
    Converts a day and time (e.g. Tue, 9:30 AM) to minutes since Monday 12:00 AM.
    """
    return (day - 1) * 1440 + time_to_mins(time)


def is_within_window(test_window: tuple, other_window: tuple):
    """
    Returns true if test_window is within other_window. Windows should be provided as
    tuples of minutes since Monday 12:00 AM: (start, end).
    """
    return test_window[0] >= other_window[0] and test_window[1] <= other_window[1]


def is_overlapping(test_window: tuple, other_window: tuple):
    """
    Returns true if test_window is overlapping with other_window. Windows should be
    provided as tuples of minutes since Monday 12:00 AM: (start, end).
    """
    return test_window[0] <= other_window[1] and test_window[1] >= other_window[0]


def mins_to_day_and_time(mins):
    """
    Converts minutes since Monday 12:00 AM to a day and time (Tue, 9:30).
    """
    mins = int(mins)
    days = mins // 1440

    hours = (mins - days * 1440) // 60
    minutes = mins - days * 1440 - hours * 60

    return Day(days + 1).name, f"{int(hours):02d}:{int(minutes):02d}"
