"""
# =============================================================================
# INTELLIGENT APPOINTMENT SCHEDULING SYSTEM
# =============================================================================
# SETUP INSTRUCTIONS:
#
#   1. Install Python 3.10+ and pip.
#
#   2. Install dependencies:
#        pip install -r requirements.txt
#
#   3. Ensure booking_data.csv is in the  scheduling_system/data/  folder.
#
#   4. From the  scheduling_system/  directory, run:
#        streamlit run app.py
#
#   5. The app opens at  http://localhost:8501
#
#   Default owner login (change in Settings on first run):
#     Username: admin   Password: admin123
# =============================================================================
"""

import sys
import json
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
from datetime import date

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.data_loader import load_data
from utils.helpers import get_month_name, get_page_config
from utils.auth import is_authenticated, logout

# ── page config ───────────────────────────────────────────────────────────────
cfg = get_page_config()
st.set_page_config(**cfg)

st.markdown("""
<style>
  section[data-testid="stSidebar"] { background-color: #F1F8E9; }
  .stMetric label { color: #2E7D32 !important; font-weight: 600; }
  .stMetric [data-testid="metric-container"] { background:#E8F5E9; border-radius:10px; padding:12px; }
  h1, h2, h3 { color: #1B5E20; }
  .hero-box {
    background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%);
    padding: 40px 48px; border-radius: 16px; margin-bottom: 28px;
  }
  .info-card {
    background: #FFFFFF; border: 1px solid #C8E6C9;
    border-radius: 12px; padding: 20px 24px; margin-bottom: 16px;
  }
</style>
""", unsafe_allow_html=True)

SETTINGS_PATH = ROOT / "business_settings.json"

DEFAULT_SETTINGS = {
    "business_name":       "My Appointment Business",
    "business_type":       "Home Salon",
    "working_days":        ["Monday","Tuesday","Wednesday","Thursday","Friday"],
    "open_time":           9,
    "close_time":          18,
    "services":            ["Hair Cut", "Styling", "Colour Treatment"],
    "avg_service_duration": 60,
    "same_day_bookings":   False,
    "contact_phone":       "",
    "contact_email":       "",
}


def load_settings() -> dict:
    s = dict(DEFAULT_SETTINGS)
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH) as f:
                s.update(json.load(f))
        except Exception:
            pass
    return s


def render_sidebar(settings: dict) -> None:
    authenticated = is_authenticated()
    with st.sidebar:
        st.markdown(f"### 📅 {settings.get('business_name','My Business')}")
        st.markdown(f"*{settings.get('business_type','')}*")
        st.markdown("---")
        st.markdown("**🔗 Navigation**")
        st.page_link("app.py",                       label="🏠 Home")
        st.page_link("pages/05_customer_booking.py", label="📝 Book Appointment")

        if authenticated:
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
    settings = load_settings()

    if "df" not in st.session_state:
        with st.spinner("Loading…"):
            st.session_state["df"] = load_data()

    render_sidebar(settings)

    biz_name = settings["business_name"]
    biz_type = settings.get("business_type", "")
    services_raw = settings.get("services", [])
    services = services_raw if isinstance(services_raw, list) else [s.strip() for s in services_raw.split("\n") if s.strip()]
    open_h   = settings.get("open_time", 9)
    close_h  = settings.get("close_time", 18)
    working  = settings.get("working_days", ["Monday","Tuesday","Wednesday","Thursday","Friday"])
    phone    = settings.get("contact_phone", "")
    email    = settings.get("contact_email", "")

    # ── hero section ──────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="hero-box">
      <h1 style="color:#1B5E20;margin:0 0 8px 0;">📅 {biz_name}</h1>
      <p style="color:#2E7D32;font-size:1.15rem;margin:0 0 20px 0;">
        {biz_type} &nbsp;·&nbsp; Professional appointment booking
      </p>
      <p style="color:#388E3C;font-size:1.05rem;margin:0;">
        Browse our availability and book your appointment online — quick, easy, and instant confirmation.
      </p>
    </div>
    """, unsafe_allow_html=True)

    # ── book now button ───────────────────────────────────────────────────────
    _, btn_col, _ = st.columns([1, 1, 1])
    with btn_col:
        st.page_link(
            "pages/05_customer_booking.py",
            label="📝 Book an Appointment",
            use_container_width=True,
        )

    st.markdown("---")

    # ── info cards ────────────────────────────────────────────────────────────
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("#### 💼 Our Services")
        if services:
            for svc in services:
                st.markdown(f"- {svc}")
        else:
            st.markdown("*Contact us to find out about available services.*")

    with col_r:
        st.markdown("#### 🕐 Opening Hours")
        days_str = ", ".join(working) if working else "By appointment"
        st.markdown(f"**Days:** {days_str}")
        st.markdown(f"**Hours:** {open_h:02d}:00 – {close_h:02d}:00")
        st.markdown("")
        if phone or email:
            st.markdown("#### 📞 Contact")
            if phone:
                st.markdown(f"**Phone:** {phone}")
            if email:
                st.markdown(f"**Email:** {email}")

    st.markdown("---")

    # ── owner sign-in link (discreet, at the bottom) ─────────────────────────
    if not is_authenticated():
        st.markdown(
            "<p style='text-align:center;color:#BDBDBD;font-size:12px;'>"
            "Business owner? "
            "<a href='/07_settings' style='color:#9E9E9E;'>Sign in</a> "
            "to access your dashboard.</p>",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
