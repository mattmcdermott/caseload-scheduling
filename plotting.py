import pandas as pd
from calendar_view.calendar import Calendar
from calendar_view.config import style
from calendar_view.core import data
from calendar_view.core.event import Event, EventStyles
from PIL import ImageFont
from pkg_resources import resource_filename

font_path: str = "Roboto-Regular.ttf"


def image_font(size: int):
    path: str = resource_filename("calendar_view.resources.fonts", font_path)
    return ImageFont.truetype(path, size)


def get_style(grade):
    """
    Get color by grade of school (range from -1 to 5)
    """
    if grade == -1:
        return EventStyles.BLUE
    elif grade == 0:
        return EventStyles.GRAY
    elif grade == 1:
        return EventStyles.GREEN
    elif grade == 2:
        return EventStyles.RED
    elif grade == 3:
        return EventStyles.BLUE
    elif grade == 4:
        return EventStyles.GRAY
    elif grade == 5:
        return EventStyles.GREEN
    else:
        return EventStyles.RED


def plot_calendar(results_df):
    style.hour_height = 800
    style.day_width = 1000
    style.title_font = image_font(300)
    style.hour_number_font = image_font(100)
    style.day_of_week_font = image_font(80)
    style.padding_horizontal = 200
    style.title_padding_bottom = 40

    config = data.CalendarConfig(
        lang="en",
        title="Pamela's Therapy Schedule",
        show_date=False,
        show_year=False,
        dates="Mo - Fr",
        hours="8:00 - 15:00",
        legend=False,
    )

    events = []
    for _, row in results_df.iterrows():
        start = row["Start"]
        end = row["End"]

        day = start // 1440
        start_time = str(pd.to_timedelta(f"{start} min")).split(" ")[2]
        start_time = ":".join(start_time.split(":")[0:2])

        end_time = str(pd.to_timedelta(f"{end} min")).split(" ")[2]
        end_time = ":".join(end_time.split(":")[0:2])

        events.append(
            Event(
                row["Case"],
                day_of_week=int(day),
                start=start_time,
                end=end_time,
                style=get_style(row["Grade"]),
            )
        )

    data.validate_config(config)
    data.validate_events(events, config)

    calendar = Calendar.build(config)
    calendar.add_events(events)
    calendar.save("calendar.png")


if __name__ == "__main__":
    results_df = pd.read_excel("results.xlsx")
    plot_calendar(results_df)
