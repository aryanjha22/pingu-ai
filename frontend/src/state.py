import time
import sys
from pathlib import Path
import streamlit as st

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from backend.logger import app_logger as logger
from src.api import fetch_user_chats, create_backend_chat

def init_session_state():
    """Initializes Streamlit session state keys with default values."""
    if "user" not in st.session_state:
        st.session_state.user = None
    if "chats" not in st.session_state:
        st.session_state.chats = {}
    if "active_chat_id" not in st.session_state:
        st.session_state.active_chat_id = None
    if "stats_prompts" not in st.session_state:
        st.session_state.stats_prompts = 0
    if "stats_start_time" not in st.session_state:
        st.session_state.stats_start_time = time.time()
    if "input_value" not in st.session_state:
        st.session_state.input_value = None

def sync_user_chats():
    """Syncs the active chat sessions from Firestore backend once authenticated."""
    if st.session_state.user is None:
        return

    user_token = st.session_state.user.get("token")
    if "chats_loaded" not in st.session_state:
        try:
            db_chats = fetch_user_chats(user_token)
            synced_chats = {}
            for chat in db_chats:
                synced_chats[chat["chat_id"]] = {
                    "name": chat["name"],
                    "messages": chat["messages"],
                    "persona": chat.get("persona", "default"),
                    "temperature": chat.get("temperature", 0.7),
                    "model": chat.get("model", "gemini-2.5-flash-lite"),
                    "updatedAt": chat.get("updatedAt", chat.get("createdAt", time.time())),
                    "createdAt": chat.get("createdAt", time.time())
                }
                
            # Initialize a default chat session if the user has zero chat documents
            if not synced_chats:
                logger.info("Initializing first default chat session for user.")
                default_id = f"chat_{int(time.time() * 1000)}"
                success = create_backend_chat(default_id, "🐧 Default Chat", token=user_token)
                if success:
                    now = time.time()
                    synced_chats[default_id] = {
                        "name": "🐧 Default Chat",
                        "messages": [],
                        "persona": "default",
                        "temperature": 0.7,
                        "model": "gemini-2.5-flash-lite",
                        "updatedAt": now,
                        "createdAt": now
                    }
                    st.session_state.active_chat_id = default_id
            # Sync with session_state
            if not synced_chats:
                raise ValueError("Database returned zero chats and failed to register default session.")

            st.session_state.chats = synced_chats
            st.session_state.chats_loaded = True
            
            if not st.session_state.active_chat_id or st.session_state.active_chat_id not in st.session_state.chats:
                st.session_state.active_chat_id = list(st.session_state.chats.keys())[0]

        except Exception as e:
            logger.error("Failed to load and sync chat sessions from database: %s", str(e), exc_info=True)
            # Fallback to in-memory if sync has exceptions
            if not st.session_state.chats:
                now = time.time()
                st.session_state.chats = {
                    "chat_default": {
                        "name": "🐧 Default Chat",
                        "messages": [],
                        "persona": "default",
                        "temperature": 0.7,
                        "model": "gemini-2.5-flash-lite",
                        "updatedAt": now,
                        "createdAt": now
                    }
                }
                st.session_state.active_chat_id = "chat_default"
