"""
utils/auth.py
Owner authentication — SHA-256 hashed passwords, session-based login,
5-attempt lockout, and require_auth page guard.
"""

import hashlib
import json
import streamlit as st
from pathlib import Path

ROOT = Path(__file__).parent.parent
SETTINGS_PATH = ROOT / "business_settings.json"

# Default credentials used on first run before the owner sets their own.
# Password "admin123" stored as its SHA-256 hash.
DEFAULT_USERNAME      = "admin"
DEFAULT_PASSWORD_HASH = hashlib.sha256("admin123".encode()).hexdigest()
MAX_LOGIN_ATTEMPTS    = 5


# ---------------------------------------------------------------------------
# Credential helpers
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Returns the SHA-256 hex digest of a plain-text password string."""
    return hashlib.sha256(plain.encode()).hexdigest()


def check_password(plain: str, stored_hash: str) -> bool:
    """Returns True if hash_password(plain) matches stored_hash."""
    return hash_password(plain) == stored_hash


def _load_credentials() -> tuple:
    """
    Reads owner_username and owner_password_hash from business_settings.json.
    Falls back to built-in defaults if the file or keys are absent.
    Returns (username: str, password_hash: str).
    """
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH) as f:
                data = json.load(f)
            username = data.get("owner_username", DEFAULT_USERNAME)
            pw_hash  = data.get("owner_password_hash", DEFAULT_PASSWORD_HASH)
            return username, pw_hash
        except Exception:
            pass
    return DEFAULT_USERNAME, DEFAULT_PASSWORD_HASH


def init_auth() -> tuple:
    """
    Initialises auth state and loads credentials.
    Returns (stored_username, stored_hash).
    """
    if "owner_authenticated" not in st.session_state:
        st.session_state["owner_authenticated"] = False
    if "login_attempts" not in st.session_state:
        st.session_state["login_attempts"] = 0
    return _load_credentials()


# ---------------------------------------------------------------------------
# Session state queries
# ---------------------------------------------------------------------------

def is_authenticated() -> bool:
    """Returns True if the owner is currently logged in."""
    return bool(st.session_state.get("owner_authenticated", False))


# ---------------------------------------------------------------------------
# Login UI
# ---------------------------------------------------------------------------

def login_page() -> None:
    """
    Renders a centred login form.
    On success sets owner_authenticated = True and reruns.
    Locks the form after MAX_LOGIN_ATTEMPTS failed attempts.
    """
    stored_username, stored_hash = init_auth()

    # Load business name for the header
    biz_name = "My Appointment Business"
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH) as f:
                biz_name = json.load(f).get("business_name", biz_name)
        except Exception:
            pass

    # Centre the form with padding columns
    _, centre, _ = st.columns([1, 2, 1])
    with centre:
        st.markdown(
            f"<h2 style='text-align:center;color:#1B5E20;'>📅 {biz_name}</h2>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<h3 style='text-align:center;color:#2E7D32;'>🔒 Owner Sign In</h3>",
            unsafe_allow_html=True,
        )
        st.markdown("")

        attempts = st.session_state.get("login_attempts", 0)

        if attempts >= MAX_LOGIN_ATTEMPTS:
            st.error(
                "🔒 Too many failed attempts. Please restart the application.",
                icon="🚫",
            )
            return

        with st.form("login_form"):
            username_input = st.text_input("Username", placeholder="Enter your username")
            password_input = st.text_input("Password", type="password",
                                           placeholder="Enter your password")
            sign_in = st.form_submit_button("Sign In", use_container_width=True)

        if sign_in:
            if (username_input == stored_username
                    and check_password(password_input, stored_hash)):
                st.session_state["owner_authenticated"] = True
                st.session_state["owner_username"]      = username_input
                st.session_state["login_attempts"]      = 0
                st.rerun()
            else:
                st.session_state["login_attempts"] = attempts + 1
                remaining = MAX_LOGIN_ATTEMPTS - st.session_state["login_attempts"]
                if remaining > 0:
                    st.error(
                        f"❌ Incorrect username or password. "
                        f"{remaining} attempt{'s' if remaining != 1 else ''} remaining."
                    )
                else:
                    st.error("🔒 Too many failed attempts. Please restart the application.")


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def logout() -> None:
    """Clears authentication state and reruns the app."""
    st.session_state["owner_authenticated"] = False
    st.session_state.pop("owner_username", None)
    st.session_state["login_attempts"] = 0
    st.rerun()


# ---------------------------------------------------------------------------
# Page guard
# ---------------------------------------------------------------------------

def require_auth() -> None:
    """
    Call as the first line of any owner-only page.
    If the owner is not authenticated, shows the login form and stops
    the page from rendering further via st.stop().
    """
    init_auth()
    if not is_authenticated():
        login_page()
        st.stop()
