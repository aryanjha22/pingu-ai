import streamlit as st
from src.api import update_backend_chat, stream_chat_from_api
from backend.logger import app_logger as logger

def render_chat_area():
    """Renders the chat viewport, message log, input prompts, and triggers WebSocket streaming."""
    user_token = st.session_state.user.get("token")
    active_chat_id = st.session_state.active_chat_id
    active_chat = st.session_state.chats.get(active_chat_id, {})
    
    if not active_chat:
        st.info("Please select or create a chat session.")
        return
        
    active_messages = active_chat["messages"]
    
    # Render Chat Area Title
    st.markdown('<h1 class="gradient-title">🐧 Pingu AI</h1>', unsafe_allow_html=True)
    
    # 1. Message Logs Viewer (Always wrapped in a height-constrained container)
    with st.container(height=500, border=False):
        if len(active_messages) == 0:
            st.markdown('<div class="empty-chat-welcome">', unsafe_allow_html=True)
            st.markdown('<h2 style="color: #64748b; font-weight: 500; text-align: center; margin-top: 3rem;">How can I help you today?</h2>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            for message in active_messages:
                avatar = "🐧" if message["role"] == "assistant" else ""
                with st.chat_message(message["role"], avatar=avatar if avatar else None):
                    st.markdown(message["content"])
            
            # Check if we have a user prompt that was just appended and requires an assistant stream
            if active_messages and active_messages[-1]["role"] == "user":
                with st.chat_message("assistant", avatar="🐧"):
                    message_placeholder = st.empty()
                    
                    import random
                    thinking_messages = [
                        "Pingu is thinking... sliding through the snow for answers! ❄️",
                        "Pingu is thinking... fishing for the perfect response! 🐟",
                        "Pingu is thinking... crunching some ice blocks! 🧊",
                        "Pingu is thinking... waddling as fast as he can! 🐾",
                        "Noot noot! Pingu is summoning the answers! 🎺",
                        "Pingu is thinking... consulting the elder penguins! 🏔️",
                        "Pingu is thinking... keeping his cool! 🧊"
                    ]
                    thinking_msg = random.choice(thinking_messages)
                    
                    thinking_placeholder = st.empty()
                    thinking_placeholder.markdown(
                        f'<div class="pingu-thinking-container">'
                        f'<span class="pingu-thinking-emoji">🐧</span>'
                        f'<span class="pingu-thinking-text">{thinking_msg}</span>'
                        f'</div>', 
                        unsafe_allow_html=True
                    )
                    
                    full_response = ""
                    try:
                        # Establish WebSocket streaming and pass details
                        response_generator = stream_chat_from_api(
                            messages=active_messages,
                            chat_id=active_chat_id,
                            persona=active_chat.get("persona", "default"),
                            temperature=active_chat.get("temperature", 0.7),
                            model=active_chat.get("model", "gemini-2.5-flash-lite"),
                            token=user_token
                        )
                        
                        def generator_with_cleared_thinking():
                            cleared = False
                            for chunk in response_generator:
                                if not cleared:
                                    thinking_placeholder.empty()
                                    cleared = True
                                yield chunk
                        
                        full_response = st.write_stream(generator_with_cleared_thinking())
                    except Exception as e:
                        thinking_placeholder.empty()
                        full_response = f"⚠️ **Error initializing client:** {str(e)}"
                        message_placeholder.markdown(full_response)
                        
                # Sync locally (database is automatically updated on done inside WebSocket backend)
                active_messages.append({"role": "assistant", "content": full_response})
                st.rerun()
                
    # 2. Chat Processing & Input Bar
    prompt = st.chat_input("Message Pingu...")
    
    if st.session_state.input_value:
        prompt = st.session_state.input_value
        st.session_state.input_value = None
        
    if prompt:
        logger.info("Prompt submitted by user: %r", prompt)
        
        # Dynamic chat renaming on the first prompt submission
        if active_chat.get("name") == "New Chat" and len(active_messages) == 0:
            words = prompt.strip().split()
            title = " ".join(words[:4])
            if len(prompt) > 25:
                title += "..."
            new_title = f"💬 {title}"
            
            # Save renamed chat in database
            logger.info("Automatically renaming chat from first prompt...")
            success = update_backend_chat(chat_id=active_chat_id, name=new_title, token=user_token)
            if success:
                active_chat["name"] = new_title
                
        # Append locally
        active_messages.append({"role": "user", "content": prompt})
        st.session_state.stats_prompts += 1
        
        # Force redraw user's message immediately and start streaming
        st.rerun()
