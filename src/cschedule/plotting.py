import pandas as pd
from calendar_view.calendar import Calendar
from calendar_view.config import style
from calendar_view.core import data
from calendar_view.core.event import Event, EventStyle, EventStyles
from PIL import ImageFont
from pkg_resources import resource_filename

from cschedule.utils import Day


def plot_calendar(results_df: pd.DataFrame, save_fn: str | None = None):
    """Saves a calendar image to the current directory."""
    style.hour_height = 350
    style.day_width = 800
    style.title_font = image_font(150)
    style.hour_number_font = image_font(80)
    style.day_of_week_font = image_font(80)
    style.event_title_font = image_font(64)
    style.padding_horizontal = 200
    style.padding_vertical = 100

    config = data.CalendarConfig(
        lang="en",
        title="Schedule",
        show_date=False,
        show_year=False,
        dates="Mo - Fr",
        hours="8:00 - 15:00",
        legend=False,
    )

    events = []
    for _, row in results_df.iterrows():
        day = Day[row["Day"]].value - 1
        start = row["Start"]
        end = row["End"]

        s = row["Case"]
        parts = s.split("_")
        title = parts[0] if len(parts) > 0 else s

        events.append(
            dict(
                title=title,
                day_of_week=day,
                start=start,
                end=end,
                style=get_style(row["Grade"]),
            )
        )
    events = sorted(events, key=lambda x: (x["day_of_week"], x["start"]))
    events = [Event(**event) for event in events]

    data.validate_config(config)
    data.validate_events(events, config)

    calendar = Calendar.build(config)
    calendar.add_events(events)

    if save_fn:
        calendar.save(save_fn)
    else:
        calendar.save("calendar.png")


def image_font(size: int):
    font_path: str = "Roboto-Regular.ttf"
    path: str = resource_filename("calendar_view.resources.fonts", font_path)
    return ImageFont.truetype(path, size)


def get_style(grade):
    """
    Get color by grade of school (range from -1 to 5)
    """
    EventStyles.ORANGE = EventStyle(
        event_border=(250, 165, 0, 240), event_fill=(250, 165, 0, 140)
    )
    EventStyles.PURPLE = EventStyle(
        event_border=(128, 0, 128, 240), event_fill=(128, 0, 128, 150)
    )
    EventStyles.PINK = EventStyle(
        event_border=(255, 192, 203, 240), event_fill=(255, 192, 203, 180)
    )

    if grade == 0:
        return EventStyles.PINK
    elif grade == 1:
        return EventStyles.BLUE
    elif grade == 2:
        return EventStyles.GREEN
    elif grade == 3:
        return EventStyles.PURPLE
    elif grade == 4:
        return EventStyles.ORANGE
    elif grade == 5:
        return EventStyles.RED
    elif grade == -1:
        return EventStyles.GRAY
