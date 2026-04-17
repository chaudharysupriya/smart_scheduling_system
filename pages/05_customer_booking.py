"""
pages/05_customer_booking.py
Customer Booking Interface — browse available slots and book or cancel appointments.
"""

import sys
import json
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import date, timedelta

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.data_loader import load_data
from modules.booking_manager import get_available_slots, create_booking, cancel_booking
from utils.helpers import get_month_name
from utils.email_sender import send_booking_confirmation, send_cancellation_confirmation

PUBLISHED_SCHEDULE_PATH = ROOT / "data" / "published_schedule.json"

st.set_page_config(page_title="Book an Appointment", page_icon="📝", layout="wide")
st.markdown("""
<style>
  section[data-testid="stSidebar"] { background-color: #F1F8E9; }
  h1, h2, h3 { color: #1B5E20; }
  .slot-btn-open { background:#C8E6C9 !important; }
  .confirm-box { background:#E8F5E9; border-radius:10px; padding:20px; border-left:4px solid #2E7D32; }
</style>""", unsafe_allow_html=True)

SETTINGS_PATH = ROOT / "business_settings.json"
DAY_ORDER = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
TIME_SLOTS = ["09:00","10:00","11:00","12:00","13:00","14:00","15:00","16:00","17:00","18:00","19:00"]


def load_settings():
    defaults = {
        "business_name": "My Business", "business_type": "",
        "working_days": ["Monday","Tuesday","Wednesday","Thursday","Friday"],
        "open_time": 9, "close_time": 18,
        "services": ["Hair Cut","Styling","Colour Treatment"],
        "avg_service_duration": 60,
        "same_day_bookings": False,
    }
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH) as f:
                defaults.update(json.load(f))
        except Exception:
            pass
    return defaults


def render_sidebar(df, settings):
    with st.sidebar:
        st.markdown(f"### 📅 {settings.get('business_name','My Business')}")
        st.markdown(f"*{settings.get('business_type','')}*")
        st.markdown("---")
        if df is not None and not df.empty:
            st.markdown(f"- Records: **{len(df):,}**")
        st.markdown("---")
        st.markdown("**🔗 Navigation**")
        st.page_link("app.py",                       label="🏠 Home")
        st.page_link("pages/01_dashboard.py",         label="📊 Dashboard")
        st.page_link("pages/02_recommendations.py",   label="🗓️ Recommendations")
        st.page_link("pages/03_comparison.py",        label="⚖️ Model Comparison")
        st.page_link("pages/04_simulation.py",        label="🔬 Simulation")
        st.page_link("pages/05_customer_booking.py",  label="📝 Book Appointment")
        st.page_link("pages/06_manage_bookings.py",   label="📋 Manage Bookings")
        st.page_link("pages/07_settings.py",          label="⚙️ Settings")


def _get_week_dates(week_start: date) -> list:
    """Returns 7 dates starting from week_start (Monday)."""
    return [week_start + timedelta(days=i) for i in range(7)]


def _load_published_schedule() -> dict:
    """Loads data/published_schedule.json. Returns empty dict if not found."""
    if not PUBLISHED_SCHEDULE_PATH.exists():
        return {}
    try:
        with open(PUBLISHED_SCHEDULE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def main():
    settings = load_settings()
    if "df" not in st.session_state:
        st.session_state["df"] = load_data()
    df: pd.DataFrame = st.session_state["df"]
    render_sidebar(df, settings)

    st.title("📝 Book an Appointment")
    st.markdown(
        f"**{settings['business_name']}** — Browse available slots and book your appointment online."
    )
    st.markdown("---")

    # ── load published schedule — gate the entire booking UI on this ──────────
    published = _load_published_schedule()
    if not published:
        st.info(
            "📅 No schedule has been published yet. Please check back soon."
        )
        return

    pub_month      = int(published["month"])
    pub_year       = int(published["year"])
    pub_month_name = published.get("month_name", get_month_name(pub_month))
    pub_at         = published.get("published_at", "")

    st.markdown(
        f"**Active booking period: {pub_month_name} {pub_year}**"
        + (f"  ·  *Published {pub_at}*" if pub_at else "")
    )

    # ── week navigation ────────────────────────────────────────────────────────
    today = date.today()
    week_offset = st.number_input(
        f"Week Number within {pub_month_name} {pub_year} (1 = first week)",
        min_value=1, max_value=5, value=1,
    )

    # First Monday of the published month
    first_day = date(pub_year, pub_month, 1)
    if first_day.weekday() == 0:
        first_monday = first_day
    else:
        first_monday = first_day + timedelta(days=(7 - first_day.weekday()) % 7)

    week_start = first_monday + timedelta(weeks=week_offset - 1)
    week_dates = _get_week_dates(week_start)

    # Guard: warn if the selected week falls outside the published month
    week_months = {d.month for d in week_dates}
    if pub_month not in week_months:
        st.warning(
            f"Bookings are currently only available for **{pub_month_name} {pub_year}**. "
            f"Please select a date within that month."
        )
        return

    # ── session-level booked slots (prevent double-booking in same session) ───
    booked_key = "session_booked_slots"
    if booked_key not in st.session_state:
        st.session_state[booked_key] = set()

    # ── availability grid ──────────────────────────────────────────────────────
    st.markdown(f"### 📅 Week of {week_start.strftime('%d %B %Y')}")
    st.markdown("""
    <span style='background:#C8E6C9;color:#1B5E20;border-radius:4px;padding:2px 8px;'>● Available — click to book</span> &nbsp;
    <span style='background:#BBDEFB;color:#1565C0;border-radius:4px;padding:2px 8px;'>● Already Booked</span> &nbsp;
    <span style='background:#F5F5F5;color:#9E9E9E;border-radius:4px;padding:2px 8px;'>● Unavailable</span>
    """, unsafe_allow_html=True)

    # Track selected slot
    if "selected_slot_date" not in st.session_state:
        st.session_state["selected_slot_date"] = None
    if "selected_slot_time" not in st.session_state:
        st.session_state["selected_slot_time"] = None

    # Build header row
    header_cols = st.columns([1] + [1] * len(week_dates))
    header_cols[0].markdown("**Time**")
    for i, d in enumerate(week_dates):
        header_cols[i + 1].markdown(
            f"**{d.strftime('%a')}**<br><small>{d.strftime('%d %b')}</small>",
            unsafe_allow_html=True,
        )

    # Grid rows — iterate over every possible time slot
    for slot in TIME_SLOTS:
        row_cols = st.columns([1] + [1] * len(week_dates))
        row_cols[0].markdown(f"**{slot}**")

        for i, d in enumerate(week_dates):
            slot_key_str = f"{d.isoformat()}_{slot}"
            in_past = d < today
            is_session_booked = slot_key_str in st.session_state[booked_key]

            # Only show rows for dates within the published month
            if d.month != pub_month or d.year != pub_year:
                row_cols[i + 1].markdown(
                    "<div style='text-align:center;color:#BDBDBD;font-size:11px;'>—</div>",
                    unsafe_allow_html=True,
                )
                continue

            # Get three-way availability from the published schedule + new_bookings
            available, taken, unavailable = get_available_slots(d)

            if in_past:
                row_cols[i + 1].markdown(
                    "<div style='text-align:center;color:#9E9E9E;font-size:11px;'>—</div>",
                    unsafe_allow_html=True,
                )
            elif is_session_booked:
                row_cols[i + 1].markdown(
                    "<div style='background:#BBDEFB;border-radius:4px;text-align:center;"
                    "color:#1565C0;font-size:11px;padding:4px;'>✓ Booked</div>",
                    unsafe_allow_html=True,
                )
            elif slot in taken:
                row_cols[i + 1].markdown(
                    "<div style='background:#BBDEFB;border-radius:4px;text-align:center;"
                    "color:#1565C0;font-size:11px;padding:4px;'>Already Booked</div>",
                    unsafe_allow_html=True,
                )
            elif slot in available:
                if row_cols[i + 1].button(
                    "Book",
                    key=f"btn_{d.isoformat()}_{slot}",
                    help=f"Book {slot} on {d.strftime('%A %d %b')}",
                ):
                    st.session_state["selected_slot_date"] = d
                    st.session_state["selected_slot_time"] = slot
                    st.rerun()
            else:
                # slot is in unavailable (not in published schedule)
                row_cols[i + 1].markdown(
                    "<div style='background:#F5F5F5;border-radius:4px;text-align:center;"
                    "color:#9E9E9E;font-size:11px;padding:4px;'>Closed</div>",
                    unsafe_allow_html=True,
                )

    st.markdown("---")

    # ── booking form ──────────────────────────────────────────────────────────
    if st.session_state.get("selected_slot_date") and st.session_state.get("selected_slot_time"):
        sel_date = st.session_state["selected_slot_date"]
        sel_time = st.session_state["selected_slot_time"]

        st.markdown(f"### ✏️ Book: **{sel_date.strftime('%A %d %B %Y')}** at **{sel_time}**")

        with st.form("booking_form"):
            f_name    = st.text_input("Full Name *", placeholder="Jane Smith")
            f_phone   = st.text_input("Phone Number *", placeholder="+44 7700 000000")
            f_email   = st.text_input("Email Address", placeholder="jane@example.com")

            services  = settings.get("services", ["General Appointment"])
            if isinstance(services, str):
                services = [s.strip() for s in services.split("\n") if s.strip()]
            f_service = st.selectbox("Service Type *", services)

            f_notes   = st.text_area("Special Requests (optional)", height=80)

            col_sub, col_cancel = st.columns(2)
            submitted  = col_sub.form_submit_button("✅ Confirm Booking", use_container_width=True)
            cancelled  = col_cancel.form_submit_button("✗ Cancel Selection", use_container_width=True)

        if cancelled:
            st.session_state["selected_slot_date"] = None
            st.session_state["selected_slot_time"] = None
            st.rerun()

        if submitted:
            errors = []
            if not f_name.strip():
                errors.append("Full Name is required.")
            if not f_phone.strip():
                errors.append("Phone Number is required.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                with st.spinner("Saving your booking…"):
                    ref = create_booking(
                        customer_name=f_name.strip(),
                        customer_phone=f_phone.strip(),
                        customer_email=f_email.strip(),
                        service_type=f_service,
                        special_requests=f_notes.strip(),
                        booking_date=sel_date,
                        time_slot=sel_time,
                        service_duration=int(settings.get("avg_service_duration", 60)),
                    )
                    slot_key_str = f"{sel_date.isoformat()}_{sel_time}"
                    st.session_state[booked_key].add(slot_key_str)
                    st.session_state["selected_slot_date"] = None
                    st.session_state["selected_slot_time"] = None

                st.success(f"""
                ✅ **Booking Confirmed!**

                📋 **Reference:** `{ref}`
                📅 **Date:** {sel_date.strftime('%A, %d %B %Y')}
                🕐 **Time:** {sel_time}
                💼 **Service:** {f_service}
                👤 **Name:** {f_name}

                *Please keep your reference number for cancellations.*
                """)

                # Send confirmation email (non-fatal if it fails)
                if f_email.strip():
                    with st.spinner("Sending confirmation email…"):
                        email_ok = send_booking_confirmation(
                            customer_name=f_name.strip(),
                            customer_email=f_email.strip(),
                            booking_reference=ref,
                            appointment_date=sel_date.strftime("%A, %d %B %Y"),
                            appointment_time=sel_time,
                            service_type=f_service,
                            business_name=settings.get("business_name", "My Business"),
                            business_settings=settings,
                        )
                    if email_ok:
                        st.caption(f"📧 Confirmation email sent to {f_email.strip()}.")
                    else:
                        st.warning(
                            "Booking saved successfully but confirmation email could not be sent. "
                            "Please save your reference number."
                        )

    st.markdown("---")

    # ── cancellation section ──────────────────────────────────────────────────
    st.markdown("### ❌ Cancel an Existing Booking")
    st.markdown("Enter your booking reference number to cancel an appointment.")

    with st.form("cancel_form"):
        cancel_ref = st.text_input(
            "Booking Reference",
            placeholder="BK-2024-XXXXXX",
            help="The reference was shown on your booking confirmation.",
        )
        lookup_btn = st.form_submit_button("🔍 Look Up Booking")

    if lookup_btn and cancel_ref.strip():
        from modules.booking_manager import _load
        all_bk = _load()
        if not all_bk.empty:
            mask = (all_bk.get("booking_reference", pd.Series()) == cancel_ref.strip()) | \
                   (all_bk.get("booking_id", pd.Series()) == cancel_ref.strip())
            found = all_bk[mask]
            if found.empty:
                st.error(f"No booking found with reference **{cancel_ref}**.")
            else:
                row = found.iloc[0]
                st.info(f"""
                **Booking found:**
                - 📅 Date: {row.get('date', 'N/A')}
                - 🕐 Time: {row.get('time_slot', 'N/A')}
                - 💼 Service: {row.get('service_type', 'N/A')}
                - 👤 Name: {row.get('customer_name', 'N/A')}
                - Status: {row.get('status', 'N/A')}
                """)
                if row.get("status") != "cancelled":
                    if st.button("✅ Confirm Cancellation", key="confirm_cancel"):
                        success, msg, details = cancel_booking(cancel_ref.strip())
                        if success:
                            st.success(f"✅ {msg}")
                            # Send cancellation email (non-fatal)
                            cust_email = str(details.get("customer_email", ""))
                            cust_name  = str(details.get("customer_name", ""))
                            if cust_email:
                                with st.spinner("Sending cancellation confirmation…"):
                                    email_ok = send_cancellation_confirmation(
                                        customer_name=cust_name,
                                        customer_email=cust_email,
                                        booking_reference=cancel_ref.strip(),
                                        appointment_date=str(details.get("date", "")),
                                        appointment_time=str(details.get("time_slot", "")),
                                        business_name=settings.get("business_name", "My Business"),
                                        business_settings=settings,
                                    )
                                if email_ok:
                                    st.caption(f"📧 Cancellation confirmation sent to {cust_email}.")
                                else:
                                    st.warning("Booking cancelled but confirmation email could not be sent.")
                        else:
                            st.error(msg)
                else:
                    st.warning("This booking is already cancelled.")
        else:
            st.warning("No bookings on record yet.")


if __name__ == "__main__":
    main()
