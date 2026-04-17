"""
pages/01_dashboard.py
Demand Analysis Dashboard — explores historical booking patterns
for a selected target month using same-period historical comparison.
"""

import sys
import json
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import date

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.data_loader import load_data
from utils.auth import require_auth, is_authenticated, logout
from modules.analysis_engine import (
    filter_by_month, calculate_slot_demand, calculate_cancellation_rates,
    calculate_noshow_rates, calculate_customer_diversity, calculate_avg_lead_time,
    get_slot_deep_dive,
)
from modules.scoring_engine import calculate_slot_scores, classify_slots
from utils.charts import (
    plot_demand_heatmap, plot_day_bar_chart, plot_year_comparison,
    build_cancellation_table, plot_diversity_bar,
)
from utils.helpers import get_month_name, format_percentage

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Demand Dashboard", page_icon="📊", layout="wide")
st.markdown("""
<style>
  section[data-testid="stSidebar"] { background-color: #F1F8E9; }
  .stMetric label { color: #2E7D32 !important; font-weight: 600; }
  h1, h2, h3 { color: #1B5E20; }
</style>""", unsafe_allow_html=True)

SETTINGS_PATH = ROOT / "business_settings.json"
DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TIME_SLOTS = ["09:00","10:00","11:00","12:00","13:00","14:00","15:00","16:00","17:00","18:00","19:00"]


def load_settings():
    defaults = {"business_name": "My Business", "business_type": "",
                "working_days": ["Monday","Tuesday","Wednesday","Thursday","Friday"],
                "open_time": 9, "close_time": 18}
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
            st.markdown("**📊 Dataset Status**")
            st.markdown(f"- Records: **{len(df):,}**")
            try:
                mn = pd.to_datetime(df['date']).min().strftime('%d %b %Y')
                mx = pd.to_datetime(df['date']).max().strftime('%d %b %Y')
                st.markdown(f"- Range: **{mn}** → **{mx}**")
            except Exception:
                pass
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

    st.title("📊 Demand Analysis Dashboard")
    st.markdown("*Explore historical booking patterns for a selected target month using same-period comparison.*")

    if df is None or df.empty:
        st.error("No booking data found. Please upload data via the Home page or Settings.")
        return

    # ── month selector ────────────────────────────────────────────────────────
    next_month = (date.today().month % 12) + 1
    month_options = {get_month_name(m): m for m in range(1, 13)}
    selected_month_name = st.selectbox(
        "Select Target Month",
        options=list(month_options.keys()),
        index=next_month - 1,
        help="The system filters historical data for this month across all years (same-period comparison).",
    )
    target_month = month_options[selected_month_name]

    # ── filter data ───────────────────────────────────────────────────────────
    filtered = filter_by_month(df, target_month)

    if filtered.empty:
        st.warning(f"No historical data found for {selected_month_name}. Try a different month.")
        return

    # ── compute pivots ────────────────────────────────────────────────────────
    freq_pivot    = calculate_slot_demand(filtered)
    cancel_pivot  = calculate_cancellation_rates(filtered)
    noshow_pivot  = calculate_noshow_rates(filtered)
    divers_pivot  = calculate_customer_diversity(filtered)
    lead_pivot    = calculate_avg_lead_time(filtered)

    # ── metric cards ──────────────────────────────────────────────────────────
    total_bookings  = len(filtered)
    att_rate        = filtered["attended"].mean() if "attended" in filtered.columns else 0

    most_pop_slot = "N/A"
    if not freq_pivot.empty:
        flat = freq_pivot.stack()
        if not flat.empty:
            idx = flat.idxmax()
            most_pop_slot = f"{idx[1][:3]} {idx[0]}"

    high_cancel_slot = "N/A"
    if not cancel_pivot.empty:
        flat_c = cancel_pivot.stack()
        if not flat_c.empty:
            idx_c = flat_c.idxmax()
            high_cancel_slot = f"{idx_c[1][:3]} {idx_c[0]} ({flat_c.max()*100:.0f}%)"

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Bookings in Month", f"{total_bookings:,}",
                  help=f"Total historical bookings for {selected_month_name} across all years")
    with c2:
        st.metric("Avg Attendance Rate", format_percentage(att_rate),
                  help="Percentage of bookings where customer attended")
    with c3:
        st.metric("Most Popular Slot", most_pop_slot,
                  help="Day + time combination with the highest weighted demand")
    with c4:
        st.metric("Highest Cancellation Slot", high_cancel_slot,
                  help="Day + time combination with the highest cancellation rate")

    st.markdown("---")

    # ── heatmap ───────────────────────────────────────────────────────────────
    st.markdown("### 🗺️ Booking Demand Heatmap")
    st.markdown(
        "Colour intensity shows weighted booking demand. "
        "Hover over any cell for cancellation rate and average lead time."
    )
    fig_heat = plot_demand_heatmap(freq_pivot, cancel_pivot, lead_pivot)
    st.plotly_chart(fig_heat, use_container_width=True)

    # ── day bar + year comparison ──────────────────────────────────────────────
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("### 📅 Volume by Day of Week")
        st.plotly_chart(plot_day_bar_chart(filtered), use_container_width=True)
    with col_r:
        st.markdown("### 📈 Year-over-Year Comparison")
        st.plotly_chart(plot_year_comparison(filtered), use_container_width=True)

    st.markdown("---")

    # ── cancellation rate table ────────────────────────────────────────────────
    st.markdown("### ⚠️ Cancellation Rate by Time Slot")
    st.markdown("Rows highlighted in red exceed 25% cancellation — consider closing those slots.")
    cancel_tbl = build_cancellation_table(filtered)
    if not cancel_tbl.empty:
        def _row_style(row):
            if row["Cancel_Rate_%"] > 25:
                return ["background-color: #FFCDD2"] * len(row)
            return [""] * len(row)
        st.dataframe(
            cancel_tbl.style.apply(_row_style, axis=1)
                       .format({"Cancel_Rate_%": "{:.1f}%"}),
            use_container_width=True,
            hide_index=True,
        )

    # ── diversity chart ────────────────────────────────────────────────────────
    st.markdown("### 👥 Customer Diversity Score by Time Slot")
    st.markdown(
        "Score = unique customers ÷ total bookings. "
        "A score of 1.0 means every booking came from a different customer (healthy). "
        "Low scores indicate dependency on a small number of regulars.",
        help="Customer diversity penalises slots that appear busy but rely on just 1-2 loyal clients.",
    )
    st.plotly_chart(plot_diversity_bar(divers_pivot), use_container_width=True)

    st.markdown("---")

    # ── slot deep dive ────────────────────────────────────────────────────────
    with st.expander("🔍 Slot Deep Dive — Full Statistics for a Specific Day & Time"):
        dd_col1, dd_col2 = st.columns(2)
        with dd_col1:
            dive_day  = st.selectbox("Select Day",  DAY_ORDER, key="dive_day")
        with dd_col2:
            dive_slot = st.selectbox("Select Time Slot", TIME_SLOTS, key="dive_slot")

        stats = get_slot_deep_dive(df, dive_day, dive_slot)
        if not stats:
            st.info(f"No historical data for {dive_day} at {dive_slot}.")
        else:
            # Compute score for recommendation
            score_df = calculate_slot_scores(freq_pivot, cancel_pivot, noshow_pivot, divers_pivot)
            classif_df = classify_slots(score_df)

            score_val = 0.0
            classif   = "N/A"
            if (not score_df.empty
                    and dive_slot in score_df.index
                    and dive_day in score_df.columns):
                score_val = score_df.loc[dive_slot, dive_day]
                classif   = classif_df.loc[dive_slot, dive_day]

            badge_html = {
                "green": "<span style='background:#C8E6C9;color:#1B5E20;border-radius:4px;padding:3px 10px;font-weight:bold;'>✓ RECOMMENDED</span>",
                "amber": "<span style='background:#FFE0B2;color:#E65100;border-radius:4px;padding:3px 10px;font-weight:bold;'>⚠ MARGINAL</span>",
                "red":   "<span style='background:#FFCDD2;color:#B71C1C;border-radius:4px;padding:3px 10px;font-weight:bold;'>✗ NOT RECOMMENDED</span>",
            }.get(classif, "<span>N/A</span>")

            st.markdown(f"#### {dive_day} @ {dive_slot}  &nbsp;&nbsp; {badge_html}  &nbsp; Score: **{score_val:.3f}**",
                        unsafe_allow_html=True)

            m1, m2, m3 = st.columns(3)
            m1.metric("Total Bookings",     str(stats["total_bookings"]))
            m2.metric("Cancellation Rate",  format_percentage(stats["cancel_rate"]))
            m3.metric("No-Show Rate",       format_percentage(stats["noshow_rate"]))

            m4, m5, m6 = st.columns(3)
            m4.metric("Avg Lead Time",      f"{stats['avg_lead_time']:.1f} days")
            m5.metric("Repeat Customers",   format_percentage(stats["repeat_pct"]))
            m6.metric("Unique Customers",   str(stats["unique_customers"]))

            bm_col1, bm_col2 = st.columns(2)
            bm_col1.metric("Best Month for Slot",  stats["best_month"])
            bm_col2.metric("Worst Month for Slot", stats["worst_month"])


if __name__ == "__main__":
    main()
