import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
if str(root_dir / "frontend") not in sys.path:
    sys.path.insert(1, str(root_dir / "frontend"))

import importlib
import streamlit as st

# Force hot-reloading of local backend logging module in Streamlit runtime
for module_name in ["backend.logger"]:
    if module_name in sys.modules:
        importlib.reload(sys.modules[module_name])

# Load environment configuration
backend_env = root_dir / "backend" / ".env"
root_env = root_dir / ".env"
if backend_env.exists():
    load_dotenv(backend_env)
elif root_env.exists():
    load_dotenv(root_env)
else:
    load_dotenv()

from src.state import init_session_state, sync_user_chats
from src.auth import handle_oauth_callback
from src.components.login_view import render_login_view
from src.components.sidebar import render_sidebar
from src.components.settings_view import render_settings
from src.components.chat_view import render_chat_area

st.set_page_config(
    page_title="Pingu AI - Your Cool Assistant",
    page_icon="🐧",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Inject custom styling sheet
css_path = Path(__file__).resolve().parent / "style.css"
if css_path.exists():
    with open(css_path, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Initialization & authentication callbacks
init_session_state()
handle_oauth_callback()

# Enforce authentication guard
if st.session_state.user is None:
    render_login_view()
    st.stop()

sync_user_chats()

# Main UI layout
left_chats_col, main_chat_col, right_controls_col = st.columns([0.22, 0.56, 0.22], gap="medium")

with left_chats_col:
    render_sidebar()

with right_controls_col:
    render_settings()

with main_chat_col:
    render_chat_area()
