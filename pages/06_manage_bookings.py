"""
pages/06_manage_bookings.py
Owner Booking Management — view and update today's appointments,
upcoming bookings, and merge new portal bookings into the main dataset.
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

from modules.data_loader import load_data, merge_new_bookings, load_new_bookings
from modules.booking_manager import update_attendance, get_bookings_for_date, get_upcoming_bookings
from utils.auth import require_auth, is_authenticated, logout

st.set_page_config(page_title="Manage Bookings", page_icon="📋", layout="wide")
st.markdown("""
<style>
  section[data-testid="stSidebar"] { background-color: #F1F8E9; }
  .stMetric label { color: #2E7D32 !important; font-weight: 600; }
  h1, h2, h3 { color: #1B5E20; }
  .appt-card {
    background: #F8F9FA; border-radius: 10px; padding: 16px;
    border-left: 4px solid #2E7D32; margin-bottom: 12px;
  }
</style>""", unsafe_allow_html=True)

SETTINGS_PATH = ROOT / "business_settings.json"


def load_settings():
    defaults = {"business_name": "My Business", "business_type": ""}
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
        st.page_link("pages/05_customer_booking.py", label="📝 Book Appointment")
        if is_authenticated():
            st.markdown("**Owner Pages**")
            st.page_link("pages/01_dashboard.py",       label="📊 Dashboard")
            st.page_link("pages/02_recommendations.py", label="🗓️ Recommendations")
            st.page_link("pages/03_comparison.py",      label="⚖️ Model Comparison")
            st.page_link("pages/04_simulation.py",      label="🔬 Simulation")
            st.page_link("pages/06_manage_bookings.py", label="📋 Manage Bookings")
            st.page_link("pages/07_settings.py",        label="⚙️ Settings")
            st.markdown("---")
            if st.button("🚪 Sign Out", use_container_width=True):
                logout()


def _action_buttons(ref: str, row_idx: int) -> None:
    """Renders three attendance action buttons for a booking."""
    b1, b2, b3 = st.columns(3)
    if b1.button("✅ Attended",   key=f"att_{ref}_{row_idx}"):
        ok, msg = update_attendance(ref, "attended")
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)
    if b2.button("❌ Cancelled",  key=f"can_{ref}_{row_idx}"):
        ok, msg = update_attendance(ref, "cancelled")
        if ok:
            st.warning(msg)
            st.rerun()
        else:
            st.error(msg)
    if b3.button("⚠️ No-Show",   key=f"nos_{ref}_{row_idx}"):
        ok, msg = update_attendance(ref, "noshow")
        if ok:
            st.warning(msg)
            st.rerun()
        else:
            st.error(msg)


def main():
    require_auth()
    settings = load_settings()
    if "df" not in st.session_state:
        st.session_state["df"] = load_data()
    df: pd.DataFrame = st.session_state["df"]
    render_sidebar(df, settings)

    st.title("📋 Manage Bookings")
    st.markdown("*View and update today's appointments, upcoming bookings, and portal submissions.*")

    today = date.today()

    # ── today's appointments ───────────────────────────────────────────────────
    st.markdown(f"### 📅 Today's Appointments — {today.strftime('%A, %d %B %Y')}")
    todays = get_bookings_for_date(today)

    if todays.empty:
        st.info("No appointments scheduled for today via the customer portal.")
    else:
        todays_active = todays[todays.get("status", "confirmed").isin(
            ["confirmed", "attended", "noshow"]
        )] if "status" in todays.columns else todays

        if todays_active.empty:
            st.info("No active appointments today.")
        else:
            for idx, row in todays_active.iterrows():
                ref = str(row.get("booking_reference", row.get("booking_id", f"ROW{idx}")))
                with st.container():
                    st.markdown(f"""
                    <div class="appt-card">
                      <b>🕐 {row.get('time_slot','N/A')}</b> &nbsp;|&nbsp;
                      👤 <b>{row.get('customer_name','Unknown')}</b> &nbsp;|&nbsp;
                      💼 {row.get('service_type','N/A')} &nbsp;|&nbsp;
                      📋 Ref: <code>{ref}</code> &nbsp;|&nbsp;
                      Status: <b>{str(row.get('status','confirmed')).upper()}</b>
                    </div>
                    """, unsafe_allow_html=True)
                    _action_buttons(ref, idx)
                st.markdown("")

    st.markdown("---")

    # ── upcoming appointments ─────────────────────────────────────────────────
    st.markdown("### 🗓️ Upcoming Appointments (Next 7 Days)")
    upcoming = get_upcoming_bookings(days_ahead=7)

    if upcoming.empty:
        st.info("No upcoming appointments in the next 7 days.")
    else:
        active_cols = ["date", "time_slot", "customer_name", "service_type",
                       "customer_phone", "booking_reference", "status"]
        display_cols = [c for c in active_cols if c in upcoming.columns]
        upcoming_display = upcoming[display_cols].copy()
        if "date" in upcoming_display.columns:
            upcoming_display["date"] = pd.to_datetime(upcoming_display["date"]).dt.strftime("%a %d %b %Y")

        st.dataframe(upcoming_display, use_container_width=True, hide_index=True)

        st.markdown("**Update Attendance for Upcoming Booking:**")
        ref_input = st.text_input("Booking Reference", placeholder="BK-2024-XXXXXX", key="upd_ref")
        if ref_input:
            ucol1, ucol2, ucol3 = st.columns(3)
            if ucol1.button("✅ Mark Attended",  key="upd_att"):
                ok, msg = update_attendance(ref_input.strip(), "attended")
                (st.success if ok else st.error)(msg)
                if ok: st.rerun()
            if ucol2.button("❌ Mark Cancelled", key="upd_can"):
                ok, msg = update_attendance(ref_input.strip(), "cancelled")
                (st.warning if ok else st.error)(msg)
                if ok: st.rerun()
            if ucol3.button("⚠️ Mark No-Show",  key="upd_nos"):
                ok, msg = update_attendance(ref_input.strip(), "noshow")
                (st.warning if ok else st.error)(msg)
                if ok: st.rerun()

    st.markdown("---")

    # ── new bookings summary ──────────────────────────────────────────────────
    st.markdown("### 📬 Customer Portal Submissions")
    new_bk = load_new_bookings()

    if new_bk.empty:
        st.info("No new bookings submitted via the customer portal.")
    else:
        total_new  = len(new_bk)
        confirmed  = int((new_bk.get("status", pd.Series()) == "confirmed").sum()) if "status" in new_bk.columns else total_new
        cancelled  = int((new_bk.get("status", pd.Series()) == "cancelled").sum()) if "status" in new_bk.columns else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Portal Bookings", str(total_new))
        c2.metric("Confirmed",             str(confirmed))
        c3.metric("Cancelled",             str(cancelled))

        display_cols_nb = ["date", "time_slot", "customer_name", "service_type",
                           "customer_phone", "booking_reference", "status"]
        show_cols = [c for c in display_cols_nb if c in new_bk.columns]
        st.dataframe(new_bk[show_cols].sort_values("date") if "date" in new_bk.columns else new_bk[show_cols],
                     use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── merge section ─────────────────────────────────────────────────────────
    st.markdown("### 🔄 Update Main Dataset")
    st.markdown(
        "Merging confirmed portal bookings into the main dataset (`booking_data.csv`) improves "
        "future demand analysis and recommendations. Only confirmed or attended records are merged."
    )

    if st.button("📥 Update Dataset (Merge Portal Bookings)", use_container_width=False):
        with st.spinner("Merging records…"):
            count, msg = merge_new_bookings()
        if count > 0:
            st.success(f"✅ {msg}")
            # Refresh session state data
            st.session_state["df"] = load_data()
            st.rerun()
        else:
            st.info(msg)

    st.markdown("---")

    # ── monthly summary ───────────────────────────────────────────────────────
    st.markdown("### 📊 This Month's Booking Summary")
    current_month = today.month
    current_year  = today.year

    all_bk = new_bk.copy() if not new_bk.empty else pd.DataFrame()

    if not all_bk.empty and "date" in all_bk.columns:
        all_bk["_date"] = pd.to_datetime(all_bk["date"], errors="coerce")
        this_month_bk = all_bk[
            (all_bk["_date"].dt.month == current_month) &
            (all_bk["_date"].dt.year == current_year)
        ]

        if this_month_bk.empty:
            st.info("No portal bookings for the current month.")
        else:
            total_m     = len(this_month_bk)
            attended_m  = int((this_month_bk.get("status", pd.Series()) == "attended").sum()) if "status" in this_month_bk.columns else 0
            cancelled_m = int((this_month_bk.get("status", pd.Series()) == "cancelled").sum()) if "status" in this_month_bk.columns else 0
            noshow_m    = int((this_month_bk.get("status", pd.Series()) == "noshow").sum()) if "status" in this_month_bk.columns else 0

            summary_df = pd.DataFrame([{
                "Month": today.strftime("%B %Y"),
                "Total Bookings": total_m,
                "Attended": attended_m,
                "Cancelled": cancelled_m,
                "No-Show": noshow_m,
                "Attendance Rate": f"{attended_m/total_m*100:.1f}%" if total_m > 0 else "N/A",
            }])
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
    else:
        st.info("No portal bookings to summarise for this month.")


if __name__ == "__main__":
    main()
