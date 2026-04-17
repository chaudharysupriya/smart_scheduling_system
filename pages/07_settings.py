"""
pages/07_settings.py
Business Settings — configure business profile, working hours, and services.
Settings are saved to business_settings.json and loaded by all pages.
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

from modules.data_loader import load_data, append_uploaded_data, BOOKING_DATA_PATH
from utils.auth import require_auth, hash_password, is_authenticated, logout
from utils.email_sender import send_test_email

st.set_page_config(page_title="Business Settings", page_icon="⚙️", layout="wide")
st.markdown("""
<style>
  section[data-testid="stSidebar"] { background-color: #F1F8E9; }
  .stMetric label { color: #2E7D32 !important; font-weight: 600; }
  h1, h2, h3 { color: #1B5E20; }
</style>""", unsafe_allow_html=True)

SETTINGS_PATH = ROOT / "business_settings.json"

DEFAULT_SETTINGS = {
    "business_name":       "My Appointment Business",
    "business_type":       "Home Salon",
    "working_days":        ["Monday","Tuesday","Wednesday","Thursday","Friday"],
    "open_time":           9,
    "close_time":          18,
    "max_bookings_per_day": 8,
    "services":            ["Hair Cut", "Styling", "Colour Treatment"],
    "avg_service_duration": 60,
    "same_day_bookings":   False,
}

DAY_ORDER = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
HOUR_OPTIONS = list(range(6, 23))
BUSINESS_TYPES = ["Home Salon", "Mobile Hairdresser", "Beautician", "Tutor", "Repair Service", "Other"]


def load_settings() -> dict:
    s = dict(DEFAULT_SETTINGS)
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH) as f:
                s.update(json.load(f))
        except Exception:
            pass
    return s


def save_settings(s: dict) -> None:
    with open(SETTINGS_PATH, "w") as f:
        json.dump(s, f, indent=2)


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

    st.title("⚙️ Business Settings")
    st.markdown("*Configure your business profile. Settings are saved to `business_settings.json` and applied across all pages.*")

    # ── first-time setup banner ────────────────────────────────────────────────
    if not settings.get("owner_username"):
        st.warning(
            "👋 **Welcome! First-Time Setup** — Please set your owner username and "
            "password in the **Owner Account** section below before using the system. "
            "Default credentials are `admin` / `admin123`."
        )

    # ── settings form ─────────────────────────────────────────────────────────
    with st.form("settings_form"):
        st.markdown("### 🏢 Business Profile")
        col1, col2 = st.columns(2)
        with col1:
            biz_name = st.text_input(
                "Business Name",
                value=settings.get("business_name", DEFAULT_SETTINGS["business_name"]),
                help="Displayed on every page and in customer confirmations.",
            )
        with col2:
            biz_type = st.selectbox(
                "Business Type",
                BUSINESS_TYPES,
                index=BUSINESS_TYPES.index(settings.get("business_type", "Home Salon"))
                      if settings.get("business_type") in BUSINESS_TYPES else 0,
                help="Used to tailor default settings and display.",
            )

        st.markdown("### 📅 Working Days")
        current_days = settings.get("working_days", DEFAULT_SETTINGS["working_days"])
        day_cols = st.columns(7)
        selected_days = []
        for i, day in enumerate(DAY_ORDER):
            checked = day_cols[i].checkbox(day[:3], value=(day in current_days), key=f"day_{day}")
            if checked:
                selected_days.append(day)

        st.markdown("### 🕐 Opening Hours")
        h_col1, h_col2, h_col3 = st.columns(3)
        with h_col1:
            open_time = st.selectbox(
                "Opening Time",
                HOUR_OPTIONS,
                index=HOUR_OPTIONS.index(settings.get("open_time", 9)),
                format_func=lambda h: f"{h:02d}:00",
            )
        with h_col2:
            close_time = st.selectbox(
                "Closing Time",
                HOUR_OPTIONS,
                index=HOUR_OPTIONS.index(settings.get("close_time", 18)),
                format_func=lambda h: f"{h:02d}:00",
            )
        with h_col3:
            max_bookings = st.number_input(
                "Max Bookings per Day",
                min_value=1, max_value=50,
                value=int(settings.get("max_bookings_per_day", 8)),
                help="Hard cap on daily bookings. System will not open more slots than this.",
            )

        st.markdown("### 💼 Services")
        services_raw = settings.get("services", DEFAULT_SETTINGS["services"])
        if isinstance(services_raw, list):
            services_str = "\n".join(services_raw)
        else:
            services_str = str(services_raw)

        services_input = st.text_area(
            "Services Offered (one per line)",
            value=services_str,
            height=120,
            help="These appear in the customer booking dropdown.",
        )
        avg_duration = st.number_input(
            "Average Service Duration (minutes)",
            min_value=15, max_value=480, step=15,
            value=int(settings.get("avg_service_duration", 60)),
            help="Used as the default when calculating capacity and buffer gaps.",
        )

        st.markdown("### ⚡ Booking Rules")
        same_day = st.toggle(
            "Accept Same-Day Bookings",
            value=bool(settings.get("same_day_bookings", False)),
            help="If OFF, customers cannot book for today's date.",
        )

        submitted = st.form_submit_button("💾 Save Settings", use_container_width=False)

    if submitted:
        services_list = [s.strip() for s in services_input.split("\n") if s.strip()]
        if open_time >= close_time:
            st.error("Opening time must be before closing time.")
        elif not selected_days:
            st.error("Please select at least one working day.")
        else:
            new_settings = {
                "business_name":        biz_name.strip() or "My Business",
                "business_type":        biz_type,
                "working_days":         selected_days,
                "open_time":            int(open_time),
                "close_time":           int(close_time),
                "max_bookings_per_day": int(max_bookings),
                "services":             services_list,
                "avg_service_duration": int(avg_duration),
                "same_day_bookings":    bool(same_day),
            }
            save_settings(new_settings)
            st.success("✅ Settings saved successfully! Changes will apply on next page load.")

    st.markdown("---")

    # ── owner account ─────────────────────────────────────────────────────────
    st.markdown("### 🔐 Owner Account")
    st.markdown("Update the username and password used to access owner-only pages.")

    with st.form("credentials_form"):
        new_username = st.text_input(
            "Owner Username",
            value=settings.get("owner_username", "admin"),
            help="Used to log in to all owner pages.",
        )
        new_password = st.text_input(
            "New Password",
            type="password",
            placeholder="Leave blank to keep current password",
        )
        confirm_password = st.text_input(
            "Confirm New Password",
            type="password",
            placeholder="Repeat new password",
        )
        cred_submit = st.form_submit_button("🔑 Update Credentials")

    if cred_submit:
        if not new_username.strip():
            st.error("Username cannot be empty.")
        elif new_password and new_password != confirm_password:
            st.error("Passwords do not match.")
        else:
            current = load_settings()
            current["owner_username"] = new_username.strip()
            if new_password:
                current["owner_password_hash"] = hash_password(new_password)
            save_settings(current)
            st.success("✅ Credentials updated successfully.")

    st.markdown("---")

    # ── email settings ─────────────────────────────────────────────────────────
    st.markdown("### 📧 Email Settings")
    st.markdown("Configure SMTP settings to send booking confirmation emails to customers.")

    with st.form("email_form"):
        sender_email = st.text_input(
            "Sender Email Address",
            value=settings.get("sender_email", ""),
            placeholder="youraddress@gmail.com",
        )
        sender_password = st.text_input(
            "Sender Email Password",
            type="password",
            placeholder="App Password (not your regular Gmail password)",
            value=settings.get("sender_password", ""),
        )
        col_smtp, col_port = st.columns(2)
        with col_smtp:
            smtp_host = st.text_input(
                "SMTP Server",
                value=settings.get("smtp_host", "smtp.gmail.com"),
            )
        with col_port:
            smtp_port = st.number_input(
                "SMTP Port",
                min_value=1, max_value=65535,
                value=int(settings.get("smtp_port", 587)),
            )
        email_enabled = st.toggle(
            "Email Notifications Enabled",
            value=bool(settings.get("email_notifications_enabled", True)),
            help="When OFF, no emails are sent but bookings still save normally.",
        )
        email_submit = st.form_submit_button("💾 Save Email Settings")

    st.caption(
        "ℹ️ For Gmail accounts you must use an **App Password**, not your regular Gmail password. "
        "Generate one at myaccount.google.com → Security → 2-Step Verification → App Passwords."
    )

    if email_submit:
        current = load_settings()
        current["sender_email"]                = sender_email.strip()
        current["sender_password"]             = sender_password
        current["smtp_host"]                   = smtp_host.strip()
        current["smtp_port"]                   = int(smtp_port)
        current["email_notifications_enabled"] = bool(email_enabled)
        save_settings(current)
        st.success("✅ Email settings saved.")

    if st.button("📤 Send Test Email"):
        current = load_settings()
        with st.spinner("Sending test email…"):
            ok, msg = send_test_email(current)
        if ok:
            st.success(f"✅ {msg}")
        else:
            st.error(f"❌ Failed to send test email: {msg}")

    st.markdown("---")

    # ── data management ───────────────────────────────────────────────────────
    st.markdown("### 📂 Data Management")

    if df is not None and not df.empty:
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Total Records",    f"{len(df):,}")
        d2.metric("Date Range Start", pd.to_datetime(df["date"]).min().strftime("%d %b %Y") if "date" in df.columns else "N/A")
        d3.metric("Date Range End",   pd.to_datetime(df["date"]).max().strftime("%d %b %Y") if "date" in df.columns else "N/A")
        d4.metric("Years of Data",    str(df["year"].nunique()) if "year" in df.columns else "N/A")
    else:
        st.warning("No data currently loaded.")

    st.markdown("#### ⬆️ Upload New Booking Data")
    st.markdown("Upload a CSV with the same column structure as the main dataset.")
    up_mode = st.radio("Upload Mode", ["Append to existing data", "Replace existing data"], horizontal=True)
    uploaded_file = st.file_uploader("Choose CSV file", type=["csv"], key="settings_upload")

    if uploaded_file and st.button("📥 Process Upload"):
        mode = "append" if "Append" in up_mode else "replace"
        ok, msg = append_uploaded_data(uploaded_file, mode=mode)
        if ok:
            st.success(f"✅ {msg}")
            st.session_state["df"] = load_data()
        else:
            st.error(f"❌ {msg}")

    st.markdown("---")
    st.markdown("#### ⬇️ Download Full Dataset")
    if df is not None and not df.empty:
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download booking_data.csv",
            data=csv_bytes,
            file_name=f"booking_data_export_{date.today().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.info("No data available to download.")


if __name__ == "__main__":
    main()
