"""
modules/analysis_engine.py
Core demand analysis functions using same-period historical comparison
with recency weighting.
"""

import pandas as pd
import numpy as np
from utils.helpers import get_month_name

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TIME_SLOTS = [
    "09:00", "10:00", "11:00", "12:00", "13:00",
    "14:00", "15:00", "16:00", "17:00", "18:00", "19:00",
]


def _ensure_all_days(pivot: pd.DataFrame) -> pd.DataFrame:
    """Ensures all seven days are columns in the pivot."""
    for day in DAY_ORDER:
        if day not in pivot.columns:
            pivot[day] = 0.0
    return pivot[DAY_ORDER]


def filter_by_month(df: pd.DataFrame, target_month: int) -> pd.DataFrame:
    """
    Filters records where month == target_month across all years.
    Applies recency weighting: most recent year → 0.6, older years → 0.4.
    """
    if df.empty:
        return df

    filtered = df[df["month"] == target_month].copy()
    if filtered.empty:
        return filtered

    max_year = filtered["year"].max()
    filtered["recency_weight"] = filtered["year"].apply(
        lambda y: 0.6 if y == max_year else 0.4
    )
    return filtered


def calculate_slot_demand(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a pivot table of weighted booking frequency.
    Rows = time_slot, Columns = day_name (Mon–Sun).
    Each booking is counted by its recency_weight so recent data
    contributes more to the frequency estimate.
    """
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["weighted_count"] = df.get("recency_weight", pd.Series(1.0, index=df.index))

    pivot = df.pivot_table(
        values="weighted_count",
        index="time_slot",
        columns="day_name",
        aggfunc="sum",
        fill_value=0,
    )
    pivot = _ensure_all_days(pivot)
    return pivot.sort_index()


def calculate_cancellation_rates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a pivot table of cancellation rates (0–1).
    Rows = time_slot, Columns = day_name.
    """
    if df.empty:
        return pd.DataFrame()

    pivot = df.pivot_table(
        values="is_cancelled",
        index="time_slot",
        columns="day_name",
        aggfunc="mean",
        fill_value=0,
    )
    pivot = _ensure_all_days(pivot)
    return pivot.sort_index()


def calculate_noshow_rates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a pivot table of no-show rates (0–1).
    Rows = time_slot, Columns = day_name.
    """
    if df.empty:
        return pd.DataFrame()

    pivot = df.pivot_table(
        values="is_noshow",
        index="time_slot",
        columns="day_name",
        aggfunc="mean",
        fill_value=0,
    )
    pivot = _ensure_all_days(pivot)
    return pivot.sort_index()


def calculate_customer_diversity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns unique customers / total bookings per slot.
    A slot with 10 bookings from 10 different customers scores 1.0.
    A slot with 10 bookings from 2 customers scores 0.2.
    Rows = time_slot, Columns = day_name.
    """
    if df.empty:
        return pd.DataFrame()

    def _diversity(series):
        total = len(series)
        if total == 0:
            return 0.0
        return series.nunique() / total

    pivot = df.pivot_table(
        values="customer_id",
        index="time_slot",
        columns="day_name",
        aggfunc=_diversity,
        fill_value=0,
    )
    pivot = _ensure_all_days(pivot)
    return pivot.sort_index()


def calculate_avg_lead_time(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns average lead time (days) per slot/day combination.
    """
    if df.empty:
        return pd.DataFrame()

    pivot = df.pivot_table(
        values="lead_time_days",
        index="time_slot",
        columns="day_name",
        aggfunc="mean",
        fill_value=0,
    )
    pivot = _ensure_all_days(pivot)
    return pivot.sort_index()


def get_seasonal_comparison(df: pd.DataFrame, time_slot: str, day_name: str) -> pd.DataFrame:
    """
    Returns month-by-month average demand for a specific day+slot combination,
    across all 12 months so the seasonal pattern is visible.
    """
    slot_df = df[(df["time_slot"] == time_slot) & (df["day_name"] == day_name)]

    monthly = slot_df.groupby("month").agg(
        total_bookings=("booking_id", "count"),
        avg_attendance=("attended", "mean"),
        cancel_rate=("is_cancelled", "mean"),
        noshow_rate=("is_noshow", "mean"),
    ).reset_index()

    all_months = pd.DataFrame({"month": range(1, 13)})
    monthly = all_months.merge(monthly, on="month", how="left").fillna(0)
    monthly["month_abbr"] = monthly["month"].apply(
        lambda m: get_month_name(m)[:3]
    )
    return monthly


def get_slot_deep_dive(df: pd.DataFrame, day_name: str, time_slot: str) -> dict:
    """
    Returns full statistics for a specific day+time_slot combination.
    """
    slot_df = df[(df["day_name"] == day_name) & (df["time_slot"] == time_slot)]
    if slot_df.empty:
        return {}

    total = len(slot_df)
    cancel_rate = slot_df["is_cancelled"].mean()
    noshow_rate = slot_df["is_noshow"].mean()
    avg_lead = slot_df["lead_time_days"].mean()
    repeat_pct = slot_df["is_repeat_customer"].mean()
    unique_custs = slot_df["customer_id"].nunique()

    monthly_attend = slot_df.groupby("month")["attended"].mean()
    best_m = int(monthly_attend.idxmax()) if not monthly_attend.empty else None
    worst_m = int(monthly_attend.idxmin()) if not monthly_attend.empty else None

    return {
        "total_bookings": total,
        "cancel_rate": cancel_rate,
        "noshow_rate": noshow_rate,
        "avg_lead_time": avg_lead,
        "repeat_pct": repeat_pct,
        "new_pct": 1 - repeat_pct,
        "unique_customers": unique_custs,
        "best_month": get_month_name(best_m) if best_m else "N/A",
        "worst_month": get_month_name(worst_m) if worst_m else "N/A",
    }
