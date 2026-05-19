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
for module_name in ["backend.logger", "backend.llm"]:
    if module_name in sys.modules:
        importlib.reload(sys.modules[module_name])

from backend.llm import stream_chat_response
from backend.logger import app_logger as logger

# Log every Streamlit rerun execution flow to help understand backend cycles
logger.info("Streamlit Rerun Triggered | Message History Count: %d", len(st.session_state.messages) if "messages" in st.session_state else 0)




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
if "messages" not in st.session_state:
    logger.info("Initializing new user session state.")
    st.session_state.messages = []
if "stats_prompts" not in st.session_state:
    st.session_state.stats_prompts = 0
if "stats_start_time" not in st.session_state:
    st.session_state.stats_start_time = time.time()

# Helper to trigger prompt injection from template buttons
if "input_value" not in st.session_state:
    st.session_state.input_value = None

# ----------------- SIDEBAR CONFIG -----------------
with st.sidebar:
    st.markdown('<div class="sidebar-header">🐧 Pingu AI Controls</div>', unsafe_allow_html=True)
    
    # 1. Model Configuration
    st.markdown('<div class="glass-card"><div class="glass-card-title">🤖 Model Config</div>', unsafe_allow_html=True)
    model_option = st.selectbox(
        "Choose Gemini Model",
        options=["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro"],
        index=0,
        help="gemini-2.5-flash models are ultra-fast and cheap to use, gemini-2.5-pro is recommended for complex reasoning."
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 2. Parameters Configuration
    st.markdown('<div class="glass-card"><div class="glass-card-title">⚙️ Hyperparameters</div>', unsafe_allow_html=True)
    temperature = st.slider(
        "Temperature (Creativity)",
        min_value=0.0,
        max_value=2.0,
        value=0.7,
        step=0.1,
        help="Higher values make output more creative but less predictable."
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 3. System Instruction/Persona Builder
    st.markdown('<div class="glass-card"><div class="glass-card-title">🎭 Assistant Persona</div>', unsafe_allow_html=True)
    persona_type = st.selectbox(
        "System Persona",
        options=[
            "Default",
            # "Expert Software Engineer",
        ],
        index=0
    )
    
    system_instruction = None
    if persona_type == "Default":
        system_instruction = """
        You are Pingu AI, a helpful, polite, intelligent, and comprehensive AI assistant. Don't go in detail keep your answers short and precise to the point.
        """
    # elif persona_type == "Expert Software Engineer":
    #     system_instruction = (
    #         "You are a Senior Software Architect and Coding Expert. "
    #         "Write robust, modern, clean, and highly documented code. Explain structural choices clearly and concisely."
    #     )
    st.markdown('</div>', unsafe_allow_html=True)

    # 4. Session Statistics
    st.markdown('<div class="glass-card"><div class="glass-card-title">📈 Session Stats</div>', unsafe_allow_html=True)
    st.markdown(f"**Total Prompts:** {st.session_state.stats_prompts}")
    elapsed = int(time.time() - st.session_state.stats_start_time)
    minutes = elapsed // 60
    seconds = elapsed % 60
    st.markdown(f"**Session Duration:** {minutes:02d}:{seconds:02d}")
    st.markdown('</div>', unsafe_allow_html=True)

    # 5. Clear Chat Button
    st.write("")
    if st.button("🧹 Clear Chat History", use_container_width=True):
        logger.info("Clear Chat History button clicked. Resetting state.")
        st.session_state.messages = []
        st.session_state.stats_prompts = 0
        st.rerun()

# ----------------- MAIN UI -----------------
st.markdown('<h1 class="gradient-title">🐧 Pingu AI</h1>', unsafe_allow_html=True)
st.markdown('<div class="gradient-subtitle">Next-gen intelligence with a glassmorphic layout</div>', unsafe_allow_html=True)

# Display existing messages
for message in st.session_state.messages:
    avatar = "🐧" if message["role"] == "assistant" else "🧑‍💻"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# ----------------- CHAT PROCESSING -----------------
# Check for template prompts or standard chat inputs
prompt = st.chat_input("Ask Pingu AI anything...")

# If a template button was clicked, we override the prompt value
if st.session_state.input_value:
    prompt = st.session_state.input_value
    st.session_state.input_value = None  # Reset state

if prompt:
    logger.info("Prompt submitted by user: %r", prompt)
    # 1. User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.stats_prompts += 1
    
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(prompt)
        
    # 2. Assistant Response (Streaming)
    with st.chat_message("assistant", avatar="🐧"):
        message_placeholder = st.empty()
        
        # Prepare content container to collect the stream
        full_response = ""
        
        try:
            # We call the stream function from llm.py
            response_generator = stream_chat_response(
                messages=st.session_state.messages,
                system_instruction=system_instruction,
                temperature=temperature,
                model=model_option
            )
            
            # Use st.write_stream to natively print typewriter style
            full_response = st.write_stream(response_generator)
            
        except Exception as e:
            full_response = f"⚠️ **Error initializing client:** {str(e)}"
            message_placeholder.markdown(full_response)
            
    # Append response to chat history
    st.session_state.messages.append({"role": "assistant", "content": full_response})
    
    # Rerun to refresh stats counter
    st.rerun()
