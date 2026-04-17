"""
modules/booking_manager.py
Customer-facing booking CRUD operations.
All data written to data/new_bookings.csv using pathlib.Path.
"""

import json
import pandas as pd
from pathlib import Path
from datetime import date, datetime
from utils.helpers import generate_booking_reference, get_season, get_month_name

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
NEW_BOOKINGS_PATH       = DATA_DIR / "new_bookings.csv"
PUBLISHED_SCHEDULE_PATH = DATA_DIR / "published_schedule.json"

ALL_TIME_SLOTS = [
    "09:00", "10:00", "11:00", "12:00", "13:00",
    "14:00", "15:00", "16:00", "17:00", "18:00", "19:00",
]

NEW_BOOKING_COLUMNS = [
    "booking_id", "booking_reference", "booking_timestamp",
    "customer_name", "customer_phone", "customer_email",
    "service_type", "special_requests",
    "date", "year", "month", "month_name", "season",
    "day_of_week", "day_name", "is_weekend", "is_public_holiday",
    "time_slot", "slot_hour", "service_duration_mins", "lead_time_days",
    "customer_id", "is_repeat_customer", "is_cancelled", "is_noshow",
    "attended", "status",
]


def _load() -> pd.DataFrame:
    if not NEW_BOOKINGS_PATH.exists():
        return pd.DataFrame(columns=NEW_BOOKING_COLUMNS)
    try:
        return pd.read_csv(NEW_BOOKINGS_PATH)
    except Exception:
        return pd.DataFrame(columns=NEW_BOOKING_COLUMNS)


def _save(df: pd.DataFrame) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(NEW_BOOKINGS_PATH, index=False)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def _load_published_schedule() -> dict:
    """Loads data/published_schedule.json. Returns empty dict if not found."""
    if not PUBLISHED_SCHEDULE_PATH.exists():
        return {}
    try:
        with open(PUBLISHED_SCHEDULE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def get_available_slots(target_date: date, schedule_df=None) -> tuple:
    """
    Loads published_schedule.json to find which slots are open for the day
    of week matching target_date, then cross-references new_bookings.csv.

    Returns three sorted lists:
      - available   : in published schedule AND not yet booked
      - taken       : in published schedule AND already has a confirmed booking
      - unavailable : all other time slots (not in the published schedule)
    """
    day_name = target_date.strftime("%A")
    published = _load_published_schedule()
    published_slots = set(published.get("schedule", {}).get(day_name, []))

    # Find confirmed bookings for this exact date
    bookings = _load()
    confirmed_booked: set = set()
    if not bookings.empty and "date" in bookings.columns:
        date_str = target_date.strftime("%Y-%m-%d")
        confirmed_booked = set(
            bookings[
                (bookings["date"].astype(str).str.startswith(date_str))
                & (bookings["status"].isin(["confirmed", "attended"]))
            ]["time_slot"].tolist()
        )

    available   = sorted(s for s in published_slots if s not in confirmed_booked)
    taken       = sorted(s for s in published_slots if s in confirmed_booked)
    unavailable = sorted(s for s in ALL_TIME_SLOTS if s not in published_slots)

    return available, taken, unavailable


def get_bookings_for_date(target_date: date) -> pd.DataFrame:
    """Returns all bookings for a specific date."""
    df = _load()
    if df.empty:
        return df
    date_str = target_date.strftime("%Y-%m-%d")
    return df[df["date"].astype(str).str.startswith(date_str)].copy()


def get_upcoming_bookings(days_ahead: int = 7) -> pd.DataFrame:
    """Returns bookings for today through today + days_ahead."""
    df = _load()
    if df.empty:
        return df
    today = date.today()
    df["_date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    mask = (df["_date"] >= today) & (df["_date"] <= today + pd.Timedelta(days=days_ahead))
    result = df[mask].drop(columns=["_date"]).sort_values("date")
    return result


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def create_booking(
    customer_name: str,
    customer_phone: str,
    customer_email: str,
    service_type: str,
    special_requests: str,
    booking_date: date,
    time_slot: str,
    service_duration: int = 60,
) -> str:
    """
    Creates a booking record in new_bookings.csv.
    Returns the booking reference string.
    """
    ref = generate_booking_reference()
    now = datetime.now()
    year = booking_date.year
    month = booking_date.month
    dow = booking_date.weekday()  # 0=Monday
    day_name = booking_date.strftime("%A")
    is_weekend = 1 if dow >= 5 else 0
    slot_hour = int(time_slot.split(":")[0])
    lead_time = max((booking_date - date.today()).days, 0)
    customer_id = f"NB{abs(hash(customer_phone)) % 9999:04d}"

    record = {
        "booking_id": ref,
        "booking_reference": ref,
        "booking_timestamp": now.isoformat(),
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "customer_email": customer_email,
        "service_type": service_type,
        "special_requests": special_requests,
        "date": booking_date.strftime("%Y-%m-%d"),
        "year": year,
        "month": month,
        "month_name": get_month_name(month),
        "season": get_season(month),
        "day_of_week": dow,
        "day_name": day_name,
        "is_weekend": is_weekend,
        "is_public_holiday": 0,
        "time_slot": time_slot,
        "slot_hour": slot_hour,
        "service_duration_mins": service_duration,
        "lead_time_days": lead_time,
        "customer_id": customer_id,
        "is_repeat_customer": 0,
        "is_cancelled": 0,
        "is_noshow": 0,
        "attended": 0,
        "status": "confirmed",
    }

    df = _load()
    df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
    _save(df)
    return ref


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def cancel_booking(booking_reference: str) -> tuple:
    """
    Cancels a booking by reference.
    Returns (success: bool, message: str, booking_details: dict).
    """
    df = _load()
    if df.empty:
        return False, "No bookings found.", {}

    mask = (df["booking_reference"] == booking_reference) | (df["booking_id"] == booking_reference)
    if not mask.any():
        return False, f"Reference '{booking_reference}' not found.", {}

    row = df[mask].iloc[0].to_dict()
    if row.get("status") == "cancelled":
        return False, "This booking is already cancelled.", row

    df.loc[mask, "status"] = "cancelled"
    df.loc[mask, "is_cancelled"] = 1
    _save(df)
    return True, "Booking successfully cancelled.", row


def update_attendance(booking_reference: str, status: str) -> tuple:
    """
    Updates attendance status.
    status must be one of: 'attended', 'cancelled', 'noshow'
    Returns (success: bool, message: str).
    """
    df = _load()
    if df.empty:
        return False, "No bookings found."

    mask = (df["booking_reference"] == booking_reference) | (df["booking_id"] == booking_reference)
    if not mask.any():
        return False, f"Booking '{booking_reference}' not found."

    status_map = {
        "attended":  {"attended": 1, "is_cancelled": 0, "is_noshow": 0, "status": "attended"},
        "cancelled": {"attended": 0, "is_cancelled": 1, "is_noshow": 0, "status": "cancelled"},
        "noshow":    {"attended": 0, "is_cancelled": 0, "is_noshow": 1, "status": "noshow"},
    }

    if status not in status_map:
        return False, f"Unknown status: {status}"

    for col, val in status_map[status].items():
        df.loc[mask, col] = val

    _save(df)
    return True, f"Booking updated to: {status}"
