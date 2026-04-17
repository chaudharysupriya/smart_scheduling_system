"""
modules/scheduler.py
Generates Fixed and Behaviour-Based weekly schedule templates.
"""

import pandas as pd
from datetime import date
from utils.helpers import get_uk_bank_holidays

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TIME_SLOTS = [
    "09:00", "10:00", "11:00", "12:00", "13:00",
    "14:00", "15:00", "16:00", "17:00", "18:00", "19:00",
]
HIGH_DEMAND_DAYS = {"Friday", "Saturday"}
GAP_BUFFER_MINS = 15
LONG_DURATION_THRESHOLD = 90  # minutes


def generate_fixed_schedule(settings: dict) -> pd.DataFrame:
    """
    Returns a weekly schedule DataFrame where every slot within working
    hours on every working day is marked 'open'.
    Rows = time_slot, Columns = day_name.
    """
    working_days = set(settings.get("working_days", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]))
    open_hour = int(settings.get("open_time", 9))
    close_hour = int(settings.get("close_time", 18))

    schedule = {}
    for day in DAY_ORDER:
        day_slots = {}
        for slot in TIME_SLOTS:
            hour = int(slot.split(":")[0])
            if day in working_days and open_hour <= hour < close_hour:
                day_slots[slot] = "open"
            else:
                day_slots[slot] = "closed"
        schedule[day] = day_slots

    return pd.DataFrame(schedule, index=TIME_SLOTS)


def generate_behaviour_schedule(
    classification_df: pd.DataFrame,
    settings: dict,
    target_month: int,
    df_historical: pd.DataFrame = None,
    target_year: int = None,
) -> pd.DataFrame:
    """
    Returns a weekly schedule DataFrame with slots opened according to
    green/amber/red rules:
      - green → always open (on working days within hours)
      - amber → open only on high-demand days (Friday, Saturday)
      - red   → closed
    Applies capacity constraints if historical data is provided.
    """
    working_days = set(settings.get("working_days", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]))
    open_hour = int(settings.get("open_time", 9))
    close_hour = int(settings.get("close_time", 18))

    schedule = {}
    for day in DAY_ORDER:
        day_slots = {}
        for slot in TIME_SLOTS:
            hour = int(slot.split(":")[0])

            if day not in working_days or hour < open_hour or hour >= close_hour:
                day_slots[slot] = "closed"
                continue

            classification = "red"
            if (
                not classification_df.empty
                and slot in classification_df.index
                and day in classification_df.columns
            ):
                classification = classification_df.loc[slot, day]

            if classification == "green":
                day_slots[slot] = "open"
            elif classification == "amber" and day in HIGH_DEMAND_DAYS:
                day_slots[slot] = "open"
            elif classification == "amber":
                day_slots[slot] = "marginal"
            else:
                day_slots[slot] = "closed"

        schedule[day] = day_slots

    df_schedule = pd.DataFrame(schedule, index=TIME_SLOTS)

    if df_historical is not None and not df_historical.empty:
        df_schedule = apply_capacity_constraints(df_schedule, df_historical)

    return df_schedule


def apply_holiday_adjustments(
    schedule_df: pd.DataFrame,
    target_month: int,
    target_year: int,
) -> tuple:
    """
    Identifies UK bank holidays in the target month.
    Returns (schedule_df, holiday_info) where holiday_info is a dict
    mapping day_name → formatted date string for display.
    The schedule itself is returned unchanged; the caller decides
    how to treat holiday days visually.
    """
    holidays = get_uk_bank_holidays(target_year)
    month_holidays = [h for h in holidays if h.month == target_month]

    holiday_info = {}
    for h in month_holidays:
        day_name = h.strftime("%A")
        holiday_info[day_name] = h.strftime("%d %b")

    return schedule_df, holiday_info


def apply_capacity_constraints(
    schedule_df: pd.DataFrame,
    df_historical: pd.DataFrame,
) -> pd.DataFrame:
    """
    If a slot's average service duration >= LONG_DURATION_THRESHOLD mins,
    the following slot is marked 'buffered' (unavailable) to ensure
    a GAP_BUFFER_MINS gap between appointments.
    """
    if df_historical.empty:
        return schedule_df

    avg_duration = df_historical.groupby("time_slot")["service_duration_mins"].mean()
    schedule_modified = schedule_df.copy()

    for i, slot in enumerate(TIME_SLOTS[:-1]):
        next_slot = TIME_SLOTS[i + 1]
        if slot not in avg_duration.index:
            continue

        duration = avg_duration[slot]
        slot_start_min = int(slot.split(":")[0]) * 60
        earliest_next_start = slot_start_min + duration + GAP_BUFFER_MINS
        next_slot_start_min = int(next_slot.split(":")[0]) * 60

        if earliest_next_start > next_slot_start_min:
            for day in schedule_modified.columns:
                if schedule_modified.loc[slot, day] == "open":
                    if schedule_modified.loc[next_slot, day] == "open":
                        schedule_modified.loc[next_slot, day] = "buffered"

    return schedule_modified


def estimate_daily_bookings(
    schedule_df: pd.DataFrame,
    freq_pivot: pd.DataFrame,
) -> dict:
    """
    Estimates expected bookings per day based on historical acceptance rates
    for open slots. Returns dict {day_name: estimated_bookings}.
    """
    estimates = {}
    for day in DAY_ORDER:
        if day not in schedule_df.columns:
            estimates[day] = 0
            continue

        total = 0.0
        for slot in schedule_df.index:
            if schedule_df.loc[slot, day] == "open":
                rate = 0.0
                if (
                    not freq_pivot.empty
                    and slot in freq_pivot.index
                    and day in freq_pivot.columns
                ):
                    # Normalise frequency to an acceptance probability (cap at 1)
                    max_freq = freq_pivot.values.max()
                    if max_freq > 0:
                        rate = min(freq_pivot.loc[slot, day] / max_freq, 1.0)
                total += rate
        estimates[day] = round(total, 1)

    return estimates
