"""
utils/helpers.py
Shared utility functions used across the scheduling system.
"""

import uuid
import calendar
from datetime import date, timedelta


def generate_booking_reference() -> str:
    """Returns a unique alphanumeric reference like BK-2024-XXXXXX."""
    year = date.today().year
    unique_part = str(uuid.uuid4()).upper().replace("-", "")[:6]
    return f"BK-{year}-{unique_part}"


def _calculate_easter(year: int) -> date:
    """Calculate Easter Sunday using the Anonymous Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _first_monday(year: int, month: int) -> date:
    d = date(year, month, 1)
    while d.weekday() != 0:
        d += timedelta(days=1)
    return d


def _last_monday(year: int, month: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    d = date(year, month, last_day)
    while d.weekday() != 0:
        d -= timedelta(days=1)
    return d


def _sub_if_weekend(d: date) -> date:
    """Move Saturday → Monday+2, Sunday → Monday+1."""
    if d.weekday() == 5:
        return d + timedelta(days=2)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def get_uk_bank_holidays(year: int) -> list:
    """Returns a list of UK bank holiday dates (England) for a given year."""
    holidays = []

    # New Year's Day
    holidays.append(_sub_if_weekend(date(year, 1, 1)))

    # Good Friday and Easter Monday
    easter = _calculate_easter(year)
    holidays.append(easter - timedelta(days=2))
    holidays.append(easter + timedelta(days=1))

    # Early May Bank Holiday (first Monday in May)
    holidays.append(_first_monday(year, 5))

    # Spring Bank Holiday (last Monday in May)
    holidays.append(_last_monday(year, 5))

    # Summer Bank Holiday (last Monday in August)
    holidays.append(_last_monday(year, 8))

    # Christmas Day
    holidays.append(_sub_if_weekend(date(year, 12, 25)))

    # Boxing Day — must not clash with Christmas substitute
    boxing = date(year, 12, 26)
    sub_boxing = _sub_if_weekend(boxing)
    sub_xmas = _sub_if_weekend(date(year, 12, 25))
    if sub_boxing == sub_xmas:
        sub_boxing = sub_boxing + timedelta(days=1)
    holidays.append(sub_boxing)

    return sorted(set(holidays))


def get_month_name(month: int) -> str:
    """Takes a month number and returns the full month name."""
    names = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }
    return names.get(int(month), "Unknown")


def format_percentage(value: float) -> str:
    """Takes a decimal and returns a formatted percentage string."""
    return f"{value * 100:.1f}%"


def get_season(month: int) -> str:
    """Takes a month number and returns Winter, Spring, Summer, or Autumn."""
    if month in (12, 1, 2):
        return "Winter"
    elif month in (3, 4, 5):
        return "Spring"
    elif month in (6, 7, 8):
        return "Summer"
    return "Autumn"


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division returning default when denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def get_page_config(settings: dict = None) -> dict:
    """
    Returns a consistent st.set_page_config dictionary for all pages.
    Reads business_name from settings if provided, otherwise uses default.
    """
    import json
    from pathlib import Path
    name = "Appointment Scheduling System"
    if settings:
        name = settings.get("business_name", name)
    else:
        # Try to load settings directly so pages can call without pre-loading
        settings_path = Path(__file__).parent.parent / "business_settings.json"
        if settings_path.exists():
            try:
                with open(settings_path) as f:
                    name = json.load(f).get("business_name", name)
            except Exception:
                pass
    return {
        "page_title": name,
        "page_icon": "📅",
        "layout": "wide",
        "initial_sidebar_state": "expanded",
    }
