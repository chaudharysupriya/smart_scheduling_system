"""
pages/04_simulation.py
Simulation Engine — runs N weeks of synthetic booking requests through
both scheduling models and reports comparative performance metrics.
"""

import sys
import json
import time
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
    calculate_noshow_rates, calculate_customer_diversity,
)
from modules.scoring_engine import calculate_slot_scores, classify_slots
from modules.scheduler import generate_fixed_schedule, generate_behaviour_schedule, apply_holiday_adjustments
from modules.simulation import generate_requests, run_simulation, calculate_metrics, compare_models
from utils.charts import plot_simulation_lines, plot_metric_comparison
from utils.helpers import get_month_name, format_percentage

st.set_page_config(page_title="Simulation Engine", page_icon="🔬", layout="wide")
st.markdown("""
<style>
  section[data-testid="stSidebar"] { background-color: #F1F8E9; }
  .stMetric label { color: #2E7D32 !important; font-weight: 600; }
  h1, h2, h3 { color: #1B5E20; }
</style>""", unsafe_allow_html=True)

SETTINGS_PATH = ROOT / "business_settings.json"


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


def main():
    require_auth()
    settings = load_settings()
    if "df" not in st.session_state:
        st.session_state["df"] = load_data()
    df: pd.DataFrame = st.session_state["df"]
    render_sidebar(df, settings)

    st.title("🔬 Simulation Engine")
    st.markdown(
        "*Generates synthetic booking requests and routes them through both scheduling models "
        "to produce reproducible performance metrics for research comparison.*"
    )

    if df is None or df.empty:
        st.error("No booking data found. Please upload data from the Home page.")
        return

    # ── settings panel ────────────────────────────────────────────────────────
    st.markdown("### ⚙️ Simulation Settings")
    month_options = {get_month_name(m): m for m in range(1, 13)}
    next_month = (date.today().month % 12) + 1

    col1, col2, col3 = st.columns(3)
    with col1:
        sel_month_name = st.selectbox(
            "Month to Simulate",
            list(month_options.keys()),
            index=next_month - 1,
            help="Historical demand from this month drives the request probability distribution.",
        )
    with col2:
        num_weeks = st.number_input(
            "Simulation Weeks",
            min_value=1, max_value=52, value=6, step=1,
            help="Number of weeks to simulate. Default 6 weeks (recommended for dissertation).",
        )
    with col3:
        seed = st.number_input(
            "Random Seed",
            min_value=0, max_value=99999, value=42, step=1,
            help="Fixed seed makes results reproducible. Change to test different demand scenarios.",
        )

    target_month = month_options[sel_month_name]
    target_year  = date.today().year

    run_btn = st.button("▶ Run Simulation", use_container_width=False)

    if not run_btn and "sim_results" not in st.session_state:
        st.info("Configure settings above and click **Run Simulation** to begin.")
        return

    if run_btn:
        progress = st.progress(0, text="Initialising…")

        progress.progress(10, text="Filtering historical data for selected month…")
        filtered = filter_by_month(df, target_month)
        if filtered.empty:
            st.warning(f"No historical data for {sel_month_name}.")
            return
        time.sleep(0.2)

        progress.progress(25, text="Computing slot quality scores…")
        freq_p   = calculate_slot_demand(filtered)
        cancel_p = calculate_cancellation_rates(filtered)
        noshow_p = calculate_noshow_rates(filtered)
        divers_p = calculate_customer_diversity(filtered)
        score_df = calculate_slot_scores(freq_p, cancel_p, noshow_p, divers_p)
        class_df = classify_slots(score_df)
        time.sleep(0.2)

        progress.progress(40, text="Generating synthetic booking requests…")
        requests = generate_requests(filtered, num_weeks=int(num_weeks), seed=int(seed))
        time.sleep(0.3)

        progress.progress(55, text="Building Fixed Schedule…")
        fixed_sched = generate_fixed_schedule(settings)
        time.sleep(0.2)

        progress.progress(65, text="Building Behaviour-Based Schedule…")
        beh_base = generate_behaviour_schedule(class_df, settings, target_month, filtered, target_year)
        beh_sched, holiday_info = apply_holiday_adjustments(beh_base, target_month, target_year)
        time.sleep(0.2)

        progress.progress(75, text="Routing requests through Fixed Model…")
        fixed_res  = run_simulation(requests, fixed_sched)
        fixed_m    = calculate_metrics(fixed_res, fixed_sched)
        time.sleep(0.2)

        progress.progress(88, text="Routing requests through Behaviour-Based Model…")
        beh_res = run_simulation(requests, beh_sched)
        beh_m   = calculate_metrics(beh_res, beh_sched)
        time.sleep(0.2)

        progress.progress(95, text="Calculating final metrics…")
        import numpy as np

        def _avg(m_dict, key):
            vals = [v[key] for v in m_dict.values() if key in v]
            return round(float(np.mean(vals)), 4) if vals else 0.0

        avg_fixed = {
            "idle_time_pct":         _avg(fixed_m, "idle_time_pct"),
            "booking_success_rate":  _avg(fixed_m, "booking_success_rate"),
            "slot_utilisation_rate": _avg(fixed_m, "slot_utilisation_rate"),
            "total_requests":        sum(v.get("requests", 0) for v in fixed_m.values()),
            "total_successful":      sum(v.get("successful", 0) for v in fixed_m.values()),
            "total_rejected":        sum(v.get("rejected", 0) for v in fixed_m.values()),
        }
        avg_beh = {
            "idle_time_pct":         _avg(beh_m, "idle_time_pct"),
            "booking_success_rate":  _avg(beh_m, "booking_success_rate"),
            "slot_utilisation_rate": _avg(beh_m, "slot_utilisation_rate"),
            "total_requests":        sum(v.get("requests", 0) for v in beh_m.values()),
            "total_successful":      sum(v.get("successful", 0) for v in beh_m.values()),
            "total_rejected":        sum(v.get("rejected", 0) for v in beh_m.values()),
        }

        rows = []
        for week in range(1, int(num_weeks) + 1):
            fm = fixed_m.get(week, {})
            bm = beh_m.get(week, {})
            rows.append({
                "Week": week,
                "Fixed - Success Rate":    fm.get("booking_success_rate", 0),
                "Fixed - Idle Time":       fm.get("idle_time_pct", 0),
                "Fixed - Utilisation":     fm.get("slot_utilisation_rate", 0),
                "Fixed - Requests":        fm.get("requests", 0),
                "Fixed - Successful":      fm.get("successful", 0),
                "Fixed - Rejected":        fm.get("rejected", 0),
                "Behaviour - Success Rate":    bm.get("booking_success_rate", 0),
                "Behaviour - Idle Time":       bm.get("idle_time_pct", 0),
                "Behaviour - Utilisation":     bm.get("slot_utilisation_rate", 0),
                "Behaviour - Requests":        bm.get("requests", 0),
                "Behaviour - Successful":      bm.get("successful", 0),
                "Behaviour - Rejected":        bm.get("rejected", 0),
            })
        comparison_df = pd.DataFrame(rows)

        progress.progress(100, text="Done!")
        time.sleep(0.3)
        progress.empty()

        st.session_state["sim_results"] = {
            "avg_fixed": avg_fixed, "avg_beh": avg_beh,
            "comparison_df": comparison_df,
            "month_label": sel_month_name,
            "num_weeks": int(num_weeks),
            "seed": int(seed),
            "total_requests": len(requests),
        }

    # ── render ─────────────────────────────────────────────────────────────────
    if "sim_results" not in st.session_state:
        return

    res        = st.session_state["sim_results"]
    avg_fixed  = res["avg_fixed"]
    avg_beh    = res["avg_beh"]
    comp_df    = res["comparison_df"]
    month_lbl  = res["month_label"]
    n_weeks    = res["num_weeks"]

    st.success(
        f"✅ Simulation complete — **{n_weeks} weeks** for **{month_lbl}** "
        f"(seed={res['seed']}, total requests={res['total_requests']:,})"
    )

    # ── summary metrics ───────────────────────────────────────────────────────
    st.markdown("### 🏁 Averaged Results (over all simulated weeks)")
    col_a, col_b, col_c = st.columns(3)
    col_a.markdown("#### Fixed Schedule")
    col_a.metric("Idle Time",       format_percentage(avg_fixed["idle_time_pct"]))
    col_a.metric("Success Rate",    format_percentage(avg_fixed["booking_success_rate"]))
    col_a.metric("Utilisation",     format_percentage(avg_fixed["slot_utilisation_rate"]))
    col_a.metric("Total Requests",  str(avg_fixed["total_requests"]))
    col_a.metric("Successful",      str(avg_fixed["total_successful"]))
    col_a.metric("Rejected",        str(avg_fixed["total_rejected"]))

    col_b.markdown("#### Behaviour-Based Schedule")
    col_b.metric("Idle Time",       format_percentage(avg_beh["idle_time_pct"]))
    col_b.metric("Success Rate",    format_percentage(avg_beh["booking_success_rate"]))
    col_b.metric("Utilisation",     format_percentage(avg_beh["slot_utilisation_rate"]))
    col_b.metric("Total Requests",  str(avg_beh["total_requests"]))
    col_b.metric("Successful",      str(avg_beh["total_successful"]))
    col_b.metric("Rejected",        str(avg_beh["total_rejected"]))

    col_c.markdown("#### Improvement (Behaviour vs Fixed)")

    def _delta(fixed_v, beh_v, lower_better=False):
        d = (beh_v - fixed_v) * 100
        if lower_better:
            d = -d
        arrow = "▲" if d >= 0 else "▼"
        colour = "green" if d >= 0 else "red"
        return f":{colour}[{arrow} {abs(d):.1f} pp]"

    col_c.markdown(f"Idle Time: {_delta(avg_fixed['idle_time_pct'], avg_beh['idle_time_pct'], lower_better=True)}")
    col_c.markdown(f"Success Rate: {_delta(avg_fixed['booking_success_rate'], avg_beh['booking_success_rate'])}")
    col_c.markdown(f"Utilisation: {_delta(avg_fixed['slot_utilisation_rate'], avg_beh['slot_utilisation_rate'])}")

    st.markdown("---")

    # ── bar chart ─────────────────────────────────────────────────────────────
    st.markdown("### 📊 Metric Comparison Chart")
    st.plotly_chart(plot_metric_comparison(avg_fixed, avg_beh), use_container_width=True)

    st.markdown("---")

    # ── week-by-week line chart ───────────────────────────────────────────────
    st.markdown("### 📈 Booking Success Rate — Week by Week")
    st.markdown(
        "Each line shows how the booking success rate evolves over the simulated weeks. "
        "A consistent gap between lines indicates the behaviour-based schedule reliably "
        "outperforms the fixed model rather than just getting lucky in one week."
    )
    st.plotly_chart(plot_simulation_lines(comp_df), use_container_width=True)

    st.markdown("---")

    # ── week breakdown table ──────────────────────────────────────────────────
    st.markdown("### 🗓️ Week-by-Week Breakdown")
    if not comp_df.empty:
        display = comp_df.copy()
        pct_cols = [c for c in display.columns if "Rate" in c or "Idle" in c or "Utilisation" in c]
        for c in pct_cols:
            display[c] = (display[c] * 100).round(1).astype(str) + "%"
        st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── download ──────────────────────────────────────────────────────────────
    st.markdown("### ⬇️ Export Simulation Results")
    csv_bytes = comp_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Simulation Results (CSV)",
        data=csv_bytes,
        file_name=f"simulation_results_{month_lbl.lower()}_{n_weeks}weeks_seed{res['seed']}.csv",
        mime="text/csv",
        help="Use this CSV in your dissertation appendix or analysis.",
    )


if __name__ == "__main__":
    main()
