"""
pages/02_recommendations.py
Schedule Recommendations — generates an intelligent weekly schedule
for a target month based on slot quality scores.
"""

import sys
import json
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import date, datetime

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.data_loader import load_data
from utils.auth import require_auth, is_authenticated, logout
from modules.analysis_engine import (
    filter_by_month, calculate_slot_demand, calculate_cancellation_rates,
    calculate_noshow_rates, calculate_customer_diversity,
)
from modules.scoring_engine import calculate_slot_scores, classify_slots, build_quality_table
from modules.scheduler import (
    generate_behaviour_schedule, apply_holiday_adjustments, estimate_daily_bookings,
)
from utils.charts import plot_schedule_grid
from utils.helpers import get_month_name, format_percentage

st.set_page_config(page_title="Schedule Recommendations", page_icon="🗓️", layout="wide")
st.markdown("""
<style>
  section[data-testid="stSidebar"] { background-color: #F1F8E9; }
  .stMetric label { color: #2E7D32 !important; font-weight: 600; }
  h1, h2, h3 { color: #1B5E20; }
</style>""", unsafe_allow_html=True)

SETTINGS_PATH = ROOT / "business_settings.json"
DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def load_settings():
    defaults = {
        "business_name": "My Business", "business_type": "",
        "working_days": ["Monday","Tuesday","Wednesday","Thursday","Friday"],
        "open_time": 9, "close_time": 18, "max_bookings_per_day": 8,
        "avg_service_duration": 60,
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
            st.markdown("**📊 Dataset**")
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


def main():
    require_auth()
    settings = load_settings()
    if "df" not in st.session_state:
        st.session_state["df"] = load_data()
    df: pd.DataFrame = st.session_state["df"]
    render_sidebar(df, settings)

    st.title("🗓️ Schedule Recommendations")
    st.markdown("*Generates an intelligent weekly schedule template based on demand patterns for the target month.*")

    if df is None or df.empty:
        st.error("No booking data found. Please upload data from the Home page.")
        return

    # ── controls ──────────────────────────────────────────────────────────────
    next_month = (date.today().month % 12) + 1
    month_options = {get_month_name(m): m for m in range(1, 13)}
    col_sel, col_btn = st.columns([3, 1])
    with col_sel:
        sel_month_name = st.selectbox(
            "Target Month",
            list(month_options.keys()),
            index=next_month - 1,
            help="The recommended schedule is tailored to this month's demand patterns.",
        )
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        generate = st.button("🚀 Generate Recommended Schedule", use_container_width=True)

    target_month = month_options[sel_month_name]
    target_year  = date.today().year

    if not generate and "rec_schedule" not in st.session_state:
        st.info("Select a target month and click **Generate Recommended Schedule** to begin.")
        return

    if generate:
        with st.spinner(f"Analysing demand patterns for {sel_month_name}…"):
            filtered = filter_by_month(df, target_month)

            if filtered.empty:
                st.warning(f"No historical data for {sel_month_name}.")
                return

            freq_pivot   = calculate_slot_demand(filtered)
            cancel_pivot = calculate_cancellation_rates(filtered)
            noshow_pivot = calculate_noshow_rates(filtered)
            divers_pivot = calculate_customer_diversity(filtered)

            score_df     = calculate_slot_scores(freq_pivot, cancel_pivot, noshow_pivot, divers_pivot)
            classif_df   = classify_slots(score_df)

            schedule_df  = generate_behaviour_schedule(
                classif_df, settings, target_month, filtered, target_year
            )
            schedule_df, holiday_info = apply_holiday_adjustments(
                schedule_df, target_month, target_year
            )
            quality_tbl  = build_quality_table(
                score_df, freq_pivot, cancel_pivot, divers_pivot, classif_df
            )
            est_bookings = estimate_daily_bookings(schedule_df, freq_pivot)

            # Stash results
            st.session_state["rec_schedule"]     = schedule_df
            st.session_state["rec_classif"]      = classif_df
            st.session_state["rec_freq"]         = freq_pivot
            st.session_state["rec_cancel"]       = cancel_pivot
            st.session_state["rec_divers"]       = divers_pivot
            st.session_state["rec_quality_tbl"]  = quality_tbl
            st.session_state["rec_est"]          = est_bookings
            st.session_state["rec_holiday"]      = holiday_info
            st.session_state["rec_month_name"]   = sel_month_name
            st.session_state["rec_target_month"] = target_month
            st.session_state["rec_target_year"]  = target_year
            # Reset override init so checkboxes reinitialise from the new schedule
            st.session_state.pop(f"override_init_{sel_month_name}", None)

    # ── render stored results ─────────────────────────────────────────────────
    if "rec_schedule" not in st.session_state:
        return

    schedule_df   = st.session_state["rec_schedule"]
    quality_tbl   = st.session_state["rec_quality_tbl"]
    est_bookings  = st.session_state["rec_est"]
    holiday_info  = st.session_state["rec_holiday"]
    month_label   = st.session_state["rec_month_name"]
    rec_month_num = st.session_state.get("rec_target_month", target_month)
    rec_year      = st.session_state.get("rec_target_year",  target_year)

    st.success(f"✅ Recommended schedule generated for **{month_label}**")

    # ── legend ────────────────────────────────────────────────────────────────
    st.markdown("""
    **Legend:** &nbsp;
    <span style='background:#C8E6C9;color:#1B5E20;border-radius:4px;padding:2px 8px;font-weight:bold;'>✓ Open — Recommended</span>
    &nbsp;
    <span style='background:#FFE0B2;color:#E65100;border-radius:4px;padding:2px 8px;font-weight:bold;'>⚠ Open — Marginal (Fri/Sat only)</span>
    &nbsp;
    <span style='background:#F5F5F5;color:#9E9E9E;border-radius:4px;padding:2px 8px;font-weight:bold;'>✗ Closed</span>
    &nbsp;
    <span style='background:#FFCDD2;color:#B71C1C;border-radius:4px;padding:2px 8px;font-weight:bold;'>★ Bank Holiday</span>
    """, unsafe_allow_html=True)

    # ── schedule grid ─────────────────────────────────────────────────────────
    grid_html = plot_schedule_grid(schedule_df, holiday_info)
    st.markdown(grid_html, unsafe_allow_html=True)

    if holiday_info:
        st.info(
            "🏖️ **Bank Holidays detected:** "
            + ", ".join(f"{d} ({dt})" for d, dt in holiday_info.items())
            + " — weekend demand patterns applied on those days."
        )

    st.markdown("---")

    # ── manual override ───────────────────────────────────────────────────────
    st.markdown("### ✏️ Manual Override")
    st.markdown(
        "Tick or untick any slot to override the algorithm's recommendation. "
        "Every ticked slot will be open for customer booking. "
        "When you are satisfied, click **Publish Schedule** to make it live."
    )

    override_days = [d for d in DAY_ORDER if d in schedule_df.columns]
    open_hour_s  = int(settings.get("open_time", 9))
    close_hour_s = int(settings.get("close_time", 18))
    working_slots = [
        s for s in schedule_df.index
        if open_hour_s <= int(s.split(":")[0]) < close_hour_s
    ]

    # Initialise checkbox state from the algorithm schedule (once per generated schedule)
    override_init_key = f"override_init_{month_label}"
    if override_init_key not in st.session_state:
        for slot in working_slots:
            for day in override_days:
                ck = f"override_{day}_{slot}"
                if ck not in st.session_state:
                    st.session_state[ck] = (schedule_df.loc[slot, day] == "open")
        st.session_state[override_init_key] = True

    # Render checkbox grid
    hdr_cols = st.columns([1] + [1] * len(override_days))
    hdr_cols[0].markdown("**Time**")
    for i, day in enumerate(override_days):
        hdr_cols[i + 1].markdown(f"**{day[:3]}**")

    for slot in working_slots:
        row_cols = st.columns([1] + [1] * len(override_days))
        row_cols[0].markdown(f"**{slot}**")
        for i, day in enumerate(override_days):
            ck = f"override_{day}_{slot}"
            row_cols[i + 1].checkbox(
                "", key=ck, label_visibility="collapsed"
            )

    st.markdown("")

    # Publish button
    if st.button("📤 Publish Schedule", type="primary"):
        # Collect ticked slots per day
        final_schedule = {}
        for day in DAY_ORDER:
            open_times = []
            for slot in schedule_df.index:
                ck = f"override_{day}_{slot}"
                if st.session_state.get(ck, False):
                    open_times.append(slot)
            final_schedule[day] = sorted(open_times)

        published_data = {
            "month":        rec_month_num,
            "year":         rec_year,
            "month_name":   month_label,
            "published_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "schedule":     final_schedule,
        }

        pub_path = ROOT / "data" / "published_schedule.json"
        pub_path.parent.mkdir(parents=True, exist_ok=True)
        with open(pub_path, "w") as f:
            json.dump(published_data, f, indent=2)

        st.success(
            f"✅ Schedule published successfully. "
            f"Customer booking page will now show these slots as available for "
            f"**{month_label} {rec_year}**."
        )

    st.markdown("---")

    # ── capacity summary ──────────────────────────────────────────────────────
    st.markdown("### 📊 Estimated Bookings per Day")
    st.markdown(
        "Based on historical slot acceptance rates for open slots in the recommended schedule."
    )
    est_df = pd.DataFrame(
        [{"Day": day, "Estimated Bookings": est_bookings.get(day, 0)}
         for day in DAY_ORDER if day in schedule_df.columns]
    )
    open_counts = {
        day: int((schedule_df[day] == "open").sum())
        for day in DAY_ORDER if day in schedule_df.columns
    }
    est_df["Open Slots"] = est_df["Day"].map(open_counts)
    st.dataframe(est_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── quality table ─────────────────────────────────────────────────────────
    st.markdown("### 🏅 Slot Quality Ranking")
    st.markdown(
        "All day × time-slot combinations ranked by quality score. "
        "Score formula: 40% demand frequency + 25% customer diversity + 20% reliability (cancellation) + 15% attendance (no-show).",
        help="Only slots within your configured working hours are scored.",
    )
    if not quality_tbl.empty:
        def _badge(classif):
            colours = {
                "green": ("C8E6C9", "1B5E20", "✓ Recommended"),
                "amber": ("FFE0B2", "E65100", "⚠ Marginal"),
                "red":   ("FFCDD2", "B71C1C", "✗ Not Recommended"),
            }
            bg, fg, label = colours.get(classif, ("EEEEEE", "333333", classif))
            return f"<span style='background:#{bg};color:#{fg};border-radius:4px;padding:1px 6px;font-weight:bold;'>{label}</span>"

        display_tbl = quality_tbl.head(50).copy()
        display_tbl["Badge"] = display_tbl["Classification"].apply(_badge)

        st.dataframe(
            display_tbl[["Day","Time Slot","Quality Score","Booking Frequency",
                          "Cancellation Rate","Diversity Score"]],
            use_container_width=True,
            hide_index=True,
        )

    # ── download button ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### ⬇️ Export Recommended Schedule")

    # Build a flat CSV representation of the schedule grid
    flat_rows = []
    for slot in schedule_df.index:
        for day in DAY_ORDER:
            if day in schedule_df.columns:
                flat_rows.append({
                    "Month": month_label,
                    "Day": day,
                    "Time Slot": slot,
                    "Status": schedule_df.loc[slot, day],
                    "Bank Holiday": "Yes" if day in holiday_info else "No",
                })
    flat_df = pd.DataFrame(flat_rows)

    csv_bytes = flat_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Schedule as CSV",
        data=csv_bytes,
        file_name=f"recommended_schedule_{month_label.lower()}.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
