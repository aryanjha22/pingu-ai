import sys
import time
from pathlib import Path

# Add project root to sys.path to enable direct backend import
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

import importlib
import streamlit as st

# Force hot-reloading of backend modules during development
for module_name in ["backend.logger"]:
    if module_name in sys.modules:
        importlib.reload(sys.modules[module_name])

from backend.logger import app_logger as logger
from api_client import stream_chat_from_api


# Log every Streamlit rerun execution flow to help understand backend cycles
active_msg_count = 0
if "chats" in st.session_state and "active_chat_id" in st.session_state:
    act_id = st.session_state.active_chat_id
    if act_id in st.session_state.chats:
        active_msg_count = len(st.session_state.chats[act_id]["messages"])
logger.info("Streamlit Rerun Triggered | Message History Count (Active Chat): %d", active_msg_count)


# ----------------- PAGE CONFIG & THEME -----------------
st.set_page_config(
    page_title="Pingu - A cool AI Assistant",
    page_icon="🐧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load and inject custom CSS from external file
css_path = Path(__file__).resolve().parent / "style.css"
if css_path.exists():
    with open(css_path, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ----------------- SESSION STATE -----------------
if "chats" not in st.session_state:
    logger.info("Initializing multi-chat session state.")
    st.session_state.chats = {
        "chat_default": {
            "name": "🐧 Default Chat",
            "messages": []
        }
    }
if "active_chat_id" not in st.session_state:
    st.session_state.active_chat_id = "chat_default"

# Migrate old single-chat format to the new structure
if "messages" in st.session_state and st.session_state.messages:
    logger.info("Migrating legacy single-chat messages to Default Chat.")
    st.session_state.chats["chat_default"]["messages"] = st.session_state.messages
    del st.session_state.messages

if "stats_prompts" not in st.session_state:
    st.session_state.stats_prompts = 0
if "stats_start_time" not in st.session_state:
    st.session_state.stats_start_time = time.time()

# Helper to trigger prompt injection from template/quick-start buttons
if "input_value" not in st.session_state:
    st.session_state.input_value = None


# ----------------- LEFT PANEL: CHATS (SIDEBAR) -----------------
with st.sidebar:
    st.markdown('<div class="sidebar-header">🐧 Chats</div>', unsafe_allow_html=True)
    
    # New Chat Button
    st.markdown('<div class="new-chat-container">', unsafe_allow_html=True)
    has_empty_chat = any(len(chat["messages"]) == 0 for chat in st.session_state.chats.values())
    if st.button("➕ New Chat", use_container_width=True, disabled=has_empty_chat):
        new_id = f"chat_{int(time.time() * 1000)}"
        st.session_state.chats[new_id] = {
            "name": "New Chat",
            "messages": []
        }
        st.session_state.active_chat_id = new_id
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    st.write("")
    
    # Active Chats List
    for chat_id, chat_info in list(st.session_state.chats.items()):
        is_active = (chat_id == st.session_state.active_chat_id)
        
        style_class = "sidebar-chat-active" if is_active else "sidebar-chat-inactive"
        st.markdown(f'<div class="{style_class}">', unsafe_allow_html=True)
        if st.button(chat_info["name"], key=f"select_{chat_id}", use_container_width=True):
            st.session_state.active_chat_id = chat_id
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


# ----------------- MAIN UI (TWO COLUMNS) -----------------
main_chat_col, right_controls_col = st.columns([0.75, 0.25], gap="large")

# Right Panel: Controls
with right_controls_col:
    st.markdown('<div class="glass-card"><div class="glass-card-title">⚙️ Settings</div>', unsafe_allow_html=True)
    model_option = st.selectbox(
        "Model",
        options=["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro"],
        index=0
    )
    
    temperature = st.slider(
        "Temperature",
        min_value=0.0,
        max_value=2.0,
        value=0.7,
        step=0.1
    )
    
    persona_display = st.selectbox(
        "Persona",
        options=["Default", "Expert Software Engineer"],
        index=0
    )
    persona_map = {"Default": "default", "Expert Software Engineer": "coder"}
    persona = persona_map.get(persona_display, "default")
    
    st.write("")
    st.markdown(f"**Total Prompts:** {st.session_state.stats_prompts}")
    elapsed = int(time.time() - st.session_state.stats_start_time)
    minutes = elapsed // 60
    seconds = elapsed % 60
    st.markdown(f"**Duration:** {minutes:02d}:{seconds:02d}")
    st.write("")
    
    if st.button("🧹 Clear Messages", use_container_width=True):
        logger.info("Clear Chat History button clicked.")
        if st.session_state.active_chat_id in st.session_state.chats:
            st.session_state.chats[st.session_state.active_chat_id]["messages"] = []
            if not st.session_state.active_chat_id.startswith("chat_default"):
                st.session_state.chats[st.session_state.active_chat_id]["name"] = "New Chat"
        st.session_state.stats_prompts = 0
        st.rerun()
        
    if st.button("🗑️ Delete Chat", use_container_width=True, type="primary"):
        logger.info("Delete Chat button clicked.")
        if st.session_state.active_chat_id in st.session_state.chats:
            del st.session_state.chats[st.session_state.active_chat_id]
        if st.session_state.chats:
            st.session_state.active_chat_id = list(st.session_state.chats.keys())[0]
        else:
            st.session_state.chats = {
                "chat_default": {
                    "name": "New Chat",
                    "messages": []
                }
            }
            st.session_state.active_chat_id = "chat_default"
        st.session_state.stats_prompts = 0
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# Left Panel: Chats
with main_chat_col:
    st.markdown('<h1 class="gradient-title">🐧 Pingu AI</h1>', unsafe_allow_html=True)
    
    active_chat_id = st.session_state.active_chat_id
    if active_chat_id not in st.session_state.chats:
        st.session_state.active_chat_id = list(st.session_state.chats.keys())[0]
        active_chat_id = st.session_state.active_chat_id
    
    active_chat = st.session_state.chats[active_chat_id]
    active_messages = active_chat["messages"]
    
    if len(active_messages) == 0:
        st.markdown('<div>', unsafe_allow_html=True)
        st.markdown('<h2 style="color: #64748b; font-weight: 500;">How can I help you today?</h2>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        for message in active_messages:
            # We use an empty avatar string for the user to completely hide it and rely on CSS
            avatar = "🐧" if message["role"] == "assistant" else ""
            with st.chat_message(message["role"], avatar=avatar if avatar else None):
                st.markdown(message["content"])

# ----------------- CHAT PROCESSING -----------------
# Chat input must be at the root level to stick to the bottom
prompt = st.chat_input("Message Pingu...")

if st.session_state.input_value:
    prompt = st.session_state.input_value
    st.session_state.input_value = None

if prompt:
    logger.info("Prompt submitted by user: %r", prompt)
    
    if active_chat["name"] == "New Chat" and len(active_messages) == 0:
        words = prompt.strip().split()
        title = " ".join(words[:4])
        if len(prompt) > 25:
            title += "..."
        active_chat["name"] = f"💬 {title}"
    
    active_messages.append({"role": "user", "content": prompt})
    st.session_state.stats_prompts += 1
    
    # Render user message and stream assistant response immediately inside the main chat column
    with main_chat_col:
        with st.chat_message("user", avatar=None):
            st.markdown(prompt)
            
        with st.chat_message("assistant", avatar="🐧"):
            message_placeholder = st.empty()
            full_response = ""
            
            try:
                response_generator = stream_chat_from_api(
                    messages=active_messages,
                    persona=persona,
                    temperature=temperature,
                    model=model_option
                )
                full_response = st.write_stream(response_generator)
            except Exception as e:
                full_response = f"⚠️ **Error initializing client:** {str(e)}"
                message_placeholder.markdown(full_response)
                
        active_messages.append({"role": "assistant", "content": full_response})
        st.rerun()
