import streamlit as st
from src.auth import auth_configured, get_google_auth_url
from backend.logger import app_logger as logger

def render_login_view():
    """Renders a stunning, premium, glassmorphic login view for Pingu AI."""

    # ── Handle guest login via query param (triggered by HTML <a href="?guest=1">) ──
    if st.query_params.get("guest") == "1":
        logger.info("User selected Guest Demo Mode. Logging in with mock token.")
        st.query_params.clear()
        st.session_state.user = {
            "uid": "demo_user",
            "email": "demo@pingu.ai",
            "displayName": "Demo Pingu",
            "photoURL": "https://api.dicebear.com/7.x/bottts/svg?seed=Pingu",
            "token": "demo_token"
        }
        st.rerun()

    # Inject page marker so CSS can target this page with glow/gradient effects
    st.markdown('<div class="login-marker"></div>', unsafe_allow_html=True)

    with st.container(border=False):
        # 1. Logo & Header
        st.markdown("""
        <div class="login-logo-container"><span class="login-logo">🐧</span></div>
        <div class="login-title">Pingu AI</div>
        <div class="login-subtitle">
            A high-performance, real-time streaming AI companion.<br>
            Sign in to unlock multi-session cloud chat storage.
        </div>
        """, unsafe_allow_html=True)

        # 2. Developer Warning Banner (only shown when auth creds are missing)
        if not auth_configured:
            st.markdown("""
            <div class="dev-mode-banner">
                <div class="dev-mode-banner-header">
                    <span style="font-size: 1.1rem; margin-right: 0.5rem;">🧑‍💻</span>
                    <strong>Local Developer Mode Active</strong>
                </div>
                <div class="dev-mode-banner-content">
                    Google &amp; Firebase auth credentials are missing from your environment.
                    Click <strong>'Continue as Guest'</strong> below to test using the local in-memory backend!
                </div>
            </div>
            """, unsafe_allow_html=True)

        # 3. & 4. Sign-in buttons — both rendered as pure styled HTML for pixel-perfect aesthetics
        if auth_configured:
            auth_url = get_google_auth_url()
            google_btn = f"""
            <div class="login-btn-stack">
                <a href="{auth_url}" target="_self" class="google-login-btn">
                    <img src="https://img.icons8.com/color/18/000000/google-logo.png"
                         style="margin-right: 9px; vertical-align: middle; flex-shrink: 0;" />
                    Continue with Google
                </a>
            </div>"""
        else:
            google_btn = """
            <div class="login-btn-stack">
                <button class="google-login-btn"
                        disabled
                        style="opacity: 0.45; cursor: not-allowed;"
                        title="Google Auth is not configured. Use Guest Access instead.">
                    🔑 &nbsp;Continue with Google
                </button>
            </div>"""

        guest_btn = """
        <div class="login-btn-stack">
            <a href="?guest=1" target="_self" class="guest-login-btn">
                👤 &nbsp;Continue as Guest
            </a>
        </div>"""

        st.markdown(f"""
        {google_btn}
        <div class="login-divider"><span>or</span></div>
        {guest_btn}
        """, unsafe_allow_html=True)

    # 5. Page Footer — fixed to bottom-right, outside the card
    st.markdown(
        '<div class="login-card-footer">Crafted with ❤️ by the Pingu AI Team</div>',
        unsafe_allow_html=True
    )
