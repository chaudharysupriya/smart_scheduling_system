"""
modules/data_loader.py
Handles all CSV loading, validation, and merging operations.
All paths use pathlib.Path for cross-platform compatibility.
"""

import streamlit as st
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
BOOKING_DATA_PATH = DATA_DIR / "booking_data.csv"
NEW_BOOKINGS_PATH = DATA_DIR / "new_bookings.csv"

REQUIRED_COLUMNS = [
    "booking_id", "date", "year", "month", "month_name", "season",
    "day_of_week", "day_name", "is_weekend", "is_public_holiday",
    "time_slot", "slot_hour", "service_duration_mins", "lead_time_days",
    "customer_id", "is_repeat_customer", "is_cancelled", "is_noshow", "attended",
]

NUMERIC_COLS = [
    "year", "month", "day_of_week", "slot_hour", "service_duration_mins",
    "lead_time_days", "is_weekend", "is_public_holiday", "is_repeat_customer",
    "is_cancelled", "is_noshow", "attended",
]


@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    """
    Reads booking_data.csv, validates columns, converts types,
    and returns a clean pandas DataFrame.
    Cached with st.cache_data for performance.
    """
    if not BOOKING_DATA_PATH.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(BOOKING_DATA_PATH)
    except Exception as e:
        st.error(f"Error reading data file: {e}")
        return pd.DataFrame()

    # Validate required columns
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        st.error(f"Data file is missing required columns: {missing}")
        return pd.DataFrame()

    # Convert date column
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Ensure numeric types
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(float)

    # Add recency weight (most recent year = 0.6, older = 0.4)
    max_year = df["year"].max()
    df["recency_weight"] = df["year"].apply(lambda y: 0.6 if y == max_year else 0.4)

    return df


def validate_upload(uploaded_file) -> tuple:
    """
    Checks an uploaded CSV has the required columns.
    Returns (bool, message).
    """
    try:
        df = pd.read_csv(uploaded_file)
        uploaded_file.seek(0)  # reset pointer
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            return False, f"Missing required columns: {', '.join(missing)}"
        return True, "File is valid."
    except Exception as e:
        return False, f"Error reading file: {e}"


def merge_new_bookings() -> tuple:
    """
    Appends confirmed records from new_bookings.csv into booking_data.csv,
    removes duplicates, and saves the updated file.
    Returns (count_added: int, message: str).
    """
    if not NEW_BOOKINGS_PATH.exists():
        return 0, "No new bookings file found."

    try:
        new_df = pd.read_csv(NEW_BOOKINGS_PATH)

        # Only merge non-cancelled records
        if "status" in new_df.columns:
            new_df = new_df[new_df["status"].isin(["confirmed", "attended"])]

        if new_df.empty:
            return 0, "No confirmed bookings to merge."

        # Keep only columns present in the main dataset
        cols_to_keep = [c for c in REQUIRED_COLUMNS if c in new_df.columns]
        new_df_filtered = new_df[cols_to_keep].copy()

        # Load existing data
        existing_df = pd.read_csv(BOOKING_DATA_PATH)
        before = len(existing_df)

        combined = pd.concat([existing_df, new_df_filtered], ignore_index=True)
        combined = combined.drop_duplicates(subset=["booking_id"], keep="last")
        combined.to_csv(BOOKING_DATA_PATH, index=False)

        count_added = len(combined) - before
        load_data.clear()  # invalidate cache
        return count_added, f"Successfully added {count_added} new records to the dataset."

    except Exception as e:
        return 0, f"Error merging bookings: {e}"


def load_new_bookings() -> pd.DataFrame:
    """Loads new_bookings.csv; returns empty DataFrame if not found."""
    if not NEW_BOOKINGS_PATH.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(NEW_BOOKINGS_PATH)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


def save_new_bookings(df: pd.DataFrame) -> None:
    """Saves a DataFrame to new_bookings.csv."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(NEW_BOOKINGS_PATH, index=False)


def append_uploaded_data(uploaded_file, mode: str = "append") -> tuple:
    """
    Handles a user-uploaded CSV.
    mode = 'append' adds to existing, 'replace' overwrites.
    Returns (success: bool, message: str).
    """
    try:
        new_df = pd.read_csv(uploaded_file)
        missing = [c for c in REQUIRED_COLUMNS if c not in new_df.columns]
        if missing:
            return False, f"Missing columns: {', '.join(missing)}"

        if mode == "replace":
            new_df.to_csv(BOOKING_DATA_PATH, index=False)
            load_data.clear()
            return True, f"Dataset replaced with {len(new_df):,} records."
        else:
            existing_df = pd.read_csv(BOOKING_DATA_PATH)
            combined = pd.concat([existing_df, new_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=["booking_id"], keep="last")
            combined.to_csv(BOOKING_DATA_PATH, index=False)
            load_data.clear()
            added = len(combined) - len(existing_df)
            return True, f"Appended {added:,} new records. Total: {len(combined):,}."
    except Exception as e:
        return False, f"Error processing file: {e}"
