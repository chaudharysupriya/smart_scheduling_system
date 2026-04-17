"""
pages/03_comparison.py
Schedule Model Comparison — Fixed vs Behaviour-Based side by side,
with metrics table, grouped bar chart, and monthly improvement chart.
"""

import sys
import json
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
from datetime import date

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.data_loader import load_data
from utils.auth import require_auth, is_authenticated, logout
from modules.analysis_engine import (
    filter_by_month, calculate_slot_demand, calculate_cancellation_rates,
    calculate_noshow_rates, calculate_customer_diversity,
)
from modules.scoring_engine import calculate_slot_scores, classify_slots
from modules.scheduler import generate_fixed_schedule, generate_behaviour_schedule, apply_holiday_adjustments
from modules.simulation import compare_models
from utils.charts import plot_schedule_grid, plot_metric_comparison, plot_monthly_improvement
from utils.helpers import get_month_name, format_percentage

st.set_page_config(page_title="Model Comparison", page_icon="⚖️", layout="wide")
st.markdown("""
<style>
  section[data-testid="stSidebar"] { background-color: #F1F8E9; }
  .stMetric label { color: #2E7D32 !important; font-weight: 600; }
  h1, h2, h3 { color: #1B5E20; }
  .improve-pos { color: #2E7D32; font-weight: bold; }
  .improve-neg { color: #C62828; font-weight: bold; }
</style>""", unsafe_allow_html=True)

SETTINGS_PATH = ROOT / "business_settings.json"
DAY_ORDER = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]


def load_settings():
    defaults = {
        "business_name": "My Business", "business_type": "",
        "working_days": ["Monday","Tuesday","Wednesday","Thursday","Friday"],
        "open_time": 9, "close_time": 18,
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


def _improvement_cell(fixed_val: float, beh_val: float, lower_is_better: bool = False) -> str:
    """Returns coloured HTML showing improvement delta."""
    delta = beh_val - fixed_val
    if lower_is_better:
        delta = -delta
    pct = delta * 100
    colour = "#2E7D32" if delta >= 0 else "#C62828"
    arrow = "▲" if delta >= 0 else "▼"
    return f"<span style='color:{colour};font-weight:bold;'>{arrow} {abs(pct):.1f}pp</span>"


def main():
    require_auth()
    settings = load_settings()
    if "df" not in st.session_state:
        st.session_state["df"] = load_data()
    df: pd.DataFrame = st.session_state["df"]
    render_sidebar(df, settings)

    st.title("⚖️ Schedule Model Comparison")
    st.markdown("*Compare the Fixed (always-open) schedule against the Behaviour-Based intelligent schedule side by side.*")

    if df is None or df.empty:
        st.error("No booking data found. Please upload data from the Home page.")
        return

    # ── controls ──────────────────────────────────────────────────────────────
    next_month = (date.today().month % 12) + 1
    month_options = {get_month_name(m): m for m in range(1, 13)}
    col_sel, col_btn = st.columns([3, 1])
    with col_sel:
        sel_name = st.selectbox(
            "Target Month",
            list(month_options.keys()),
            index=next_month - 1,
        )
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        run_btn = st.button("▶ Run Comparison", use_container_width=True)

    target_month = month_options[sel_name]
    target_year  = date.today().year

    if not run_btn and "cmp_fixed_metrics" not in st.session_state:
        st.info("Select a month and click **Run Comparison** to begin.")
        return

    if run_btn:
        with st.spinner("Building both schedules and running simulation…"):
            filtered = filter_by_month(df, target_month)
            if filtered.empty:
                st.warning(f"No data for {sel_name}.")
                return

            freq_p   = calculate_slot_demand(filtered)
            cancel_p = calculate_cancellation_rates(filtered)
            noshow_p = calculate_noshow_rates(filtered)
            divers_p = calculate_customer_diversity(filtered)
            score_df = calculate_slot_scores(freq_p, cancel_p, noshow_p, divers_p)
            class_df = classify_slots(score_df)

            fixed_sched = generate_fixed_schedule(settings)
            beh_sched, holiday_info = apply_holiday_adjustments(
                generate_behaviour_schedule(class_df, settings, target_month, filtered, target_year),
                target_month, target_year,
            )

            avg_fixed, avg_beh, comparison_df = compare_models(
                filtered, fixed_sched, beh_sched, num_weeks=6, seed=42
            )

            st.session_state.update({
                "cmp_fixed_sched":   fixed_sched,
                "cmp_beh_sched":     beh_sched,
                "cmp_fixed_metrics": avg_fixed,
                "cmp_beh_metrics":   avg_beh,
                "cmp_comparison_df": comparison_df,
                "cmp_holiday_info":  holiday_info,
                "cmp_month":         sel_name,
                "cmp_df_all":        df,
            })

    # ── render ─────────────────────────────────────────────────────────────────
    if "cmp_fixed_metrics" not in st.session_state:
        return

    fixed_sched   = st.session_state["cmp_fixed_sched"]
    beh_sched     = st.session_state["cmp_beh_sched"]
    avg_fixed     = st.session_state["cmp_fixed_metrics"]
    avg_beh       = st.session_state["cmp_beh_metrics"]
    comp_df       = st.session_state["cmp_comparison_df"]
    holiday_info  = st.session_state["cmp_holiday_info"]
    month_label   = st.session_state["cmp_month"]

    st.success(f"✅ Comparison ready for **{month_label}**")

    # ── side-by-side grids ────────────────────────────────────────────────────
    st.markdown("### 📅 Schedule Grids")
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("#### 🔒 Fixed Schedule (Baseline)")
        st.markdown("*All slots open every working day — no intelligence applied.*")
        st.markdown(plot_schedule_grid(fixed_sched, {}), unsafe_allow_html=True)
    with col_r:
        st.markdown("#### 🧠 Behaviour-Based Schedule")
        st.markdown("*Slots opened based on demand quality scores for the target month.*")
        st.markdown(plot_schedule_grid(beh_sched, holiday_info), unsafe_allow_html=True)

    st.markdown("---")

    # ── metrics table ─────────────────────────────────────────────────────────
    st.markdown("### 📊 Performance Metrics Comparison")
    st.markdown(
        "Metrics are averaged over a 6-week simulation using the same booking request pool "
        "routed through each schedule independently."
    )

    metrics_data = {
        "Metric": ["Idle Time %", "Booking Success Rate %", "Slot Utilisation %"],
        "Fixed Schedule": [
            f"{avg_fixed['idle_time_pct']*100:.1f}%",
            f"{avg_fixed['booking_success_rate']*100:.1f}%",
            f"{avg_fixed['slot_utilisation_rate']*100:.1f}%",
        ],
        "Behaviour-Based": [
            f"{avg_beh['idle_time_pct']*100:.1f}%",
            f"{avg_beh['booking_success_rate']*100:.1f}%",
            f"{avg_beh['slot_utilisation_rate']*100:.1f}%",
        ],
        "Improvement": [
            _improvement_cell(avg_fixed["idle_time_pct"],         avg_beh["idle_time_pct"],         lower_is_better=True),
            _improvement_cell(avg_fixed["booking_success_rate"],  avg_beh["booking_success_rate"]),
            _improvement_cell(avg_fixed["slot_utilisation_rate"], avg_beh["slot_utilisation_rate"]),
        ],
    }
    metrics_df = pd.DataFrame(metrics_data)
    st.markdown(
        metrics_df.to_html(index=False, escape=False, classes="", border=0),
        unsafe_allow_html=True,
    )
    st.markdown("""
    <small>
    <b>Idle Time %</b> — lower is better; proportion of open slots that had no booking.<br>
    <b>Booking Success Rate %</b> — higher is better; proportion of booking requests that were successfully placed.<br>
    <b>Slot Utilisation %</b> — higher is better; proportion of open slots that were actually used.<br>
    <b>pp</b> = percentage points improvement.
    </small>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ── grouped bar chart ─────────────────────────────────────────────────────
    st.markdown("### 📊 Visual Comparison")
    fig_bar = plot_metric_comparison(avg_fixed, avg_beh)
    st.plotly_chart(fig_bar, use_container_width=True)
    st.markdown(
        "> The behaviour-based schedule is expected to have a **lower idle time** because it "
        "closes low-demand slots rather than leaving them open and empty. "
        "**Booking success rate** improves because customers are directed toward slots "
        "that historically receive high demand. "
        "**Utilisation** rises because fewer slots are wasted."
    )

    st.markdown("---")

    # ── monthly improvement chart ─────────────────────────────────────────────
    st.markdown("### 📅 Seasonal Improvement Potential — All Months")
    st.markdown(
        "This chart estimates the potential benefit of intelligent scheduling across "
        "different months. Months with high attendance and low cancellation "
        "(e.g. pre-Christmas) show greater improvement potential than quieter months."
    )
    fig_month = plot_monthly_improvement(df)
    st.plotly_chart(fig_month, use_container_width=True)
    st.markdown(
        "> **Why does this vary by month?** Demand patterns differ across seasons — "
        "a salon may be busiest in December while a tutor peaks in September. "
        "The behaviour-based model adapts to each month independently, so the gain "
        "over a fixed schedule varies seasonally."
    )

    st.markdown("---")

    # ── week-by-week breakdown ─────────────────────────────────────────────────
    st.markdown("### 🗓️ Week-by-Week Simulation Detail")
    if not comp_df.empty:
        display_cols = {
            "Week": "Week",
            "Fixed - Success Rate": "Fixed Success %",
            "Behaviour - Success Rate": "Behaviour Success %",
            "Fixed - Idle Time": "Fixed Idle %",
            "Behaviour - Idle Time": "Behaviour Idle %",
            "Fixed - Utilisation": "Fixed Util %",
            "Behaviour - Utilisation": "Behaviour Util %",
        }
        show_df = comp_df[[c for c in display_cols if c in comp_df.columns]].copy()
        for col in show_df.columns:
            if col != "Week":
                show_df[col] = (show_df[col] * 100).round(1).astype(str) + "%"
        show_df = show_df.rename(columns={k: v for k, v in display_cols.items() if k in show_df.columns})
        st.dataframe(show_df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
