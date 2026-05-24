import time
import streamlit as st
from src.api import create_backend_chat
from backend.logger import app_logger as logger

def render_sidebar():
    """Renders the sidebar component containing user details, sign-out, and active chats."""
    user_token = st.session_state.user.get("token")
    
    # 1. User Profile Widget
    photo_url = st.session_state.user["photoURL"]
    disp_name = st.session_state.user["displayName"]
    disp_email = st.session_state.user["email"]
    is_guest = user_token == "demo_token"
    
    badge_html = '<span class="dev-badge">Local Guest</span>' if is_guest else '<span class="dev-badge" style="background:rgba(16,185,129,0.15);color:#34d399;border-color:rgba(16,185,129,0.3);">Cloud User</span>'
    
    st.markdown(f"""
    <div class="user-profile-card">
        <img class="user-profile-img" src="{photo_url}" width="40" height="40" />
        <div class="user-profile-info">
            <div class="user-profile-name">{disp_name}</div>
            <div class="user-profile-email">{disp_email}</div>
            {badge_html}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Sign Out Button
    st.markdown('<div class="signout-btn-container">', unsafe_allow_html=True)
    if st.button("🔓 Sign Out", use_container_width=True, key="sign_out_btn"):
        logger.info("User signed out.")
        st.session_state.user = None
        st.session_state.chats = {}
        st.session_state.active_chat_id = None
        if "chats_loaded" in st.session_state:
            del st.session_state.chats_loaded
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
        
    st.markdown('<div class="glass-card-title">🐧 Chats</div>', unsafe_allow_html=True)
    
    # 2. New Chat Button
    st.markdown('<div class="new-chat-container">', unsafe_allow_html=True)
    has_empty_chat = any(len(chat["messages"]) == 0 for chat in st.session_state.chats.values())
    
    active_chat = st.session_state.chats.get(st.session_state.active_chat_id, {})
    
    if st.button("➕ New Chat", use_container_width=True, disabled=has_empty_chat, key="new_chat_btn"):
        new_id = f"chat_{int(time.time() * 1000)}"
        success = create_backend_chat(
            chat_id=new_id,
            name="New Chat",
            persona=active_chat.get("persona", "default"),
            temperature=active_chat.get("temperature", 0.7),
            model=active_chat.get("model", "gemini-2.5-flash-lite"),
            token=user_token
        )
        if success:
            st.session_state.chats[new_id] = {
                "name": "New Chat",
                "messages": [],
                "persona": active_chat.get("persona", "default"),
                "temperature": active_chat.get("temperature", 0.7),
                "model": active_chat.get("model", "gemini-2.5-flash-lite")
            }
            st.session_state.active_chat_id = new_id
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    st.write("")
    
    # 3. Active Chats List
    st.markdown('<div class="chats-list-scrollable">', unsafe_allow_html=True)
    for chat_id_key, chat_info in list(st.session_state.chats.items()):
        is_active = (chat_id_key == st.session_state.active_chat_id)
        style_class = "sidebar-chat-active" if is_active else "sidebar-chat-inactive"
        st.markdown(f'<div class="{style_class}">', unsafe_allow_html=True)
        if st.button(chat_info["name"], key=f"select_{chat_id_key}", use_container_width=True):
            st.session_state.active_chat_id = chat_id_key
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
