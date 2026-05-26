import time
import streamlit as st
from src.api import update_backend_chat, delete_backend_chat, create_backend_chat, upload_chat_document_api, delete_chat_document_api
from backend.logger import app_logger as logger

def render_settings():
    """Renders the settings panel containing models select, sliders, and chat CRUD controls."""
    st.markdown('<div class="glass-card-title">⚙️ Settings</div>', unsafe_allow_html=True)
    
    user_token = st.session_state.user.get("token")
    active_chat_id = st.session_state.active_chat_id
    active_chat = st.session_state.chats.get(active_chat_id, {})
    
    if not active_chat:
        st.info("No active chat selected.")
        return
        
    # Load settings from selected chat
    current_model = active_chat.get("model", "gemini-2.5-flash-lite")
    current_temp = active_chat.get("temperature", 0.7)
    current_persona = active_chat.get("persona", "default")
    
    model_options = [
        "gemini-2.5-flash-lite", 
        "gemini-3.1-flash-lite", 
        "gemini-2.5-flash", 
        "gemma-4-26b-a4b-it", 
        "gemma-4-31b-it"
    ]
    model_idx = model_options.index(current_model) if current_model in model_options else 0
    
    model_option = st.selectbox(
        "Model",
        options=model_options,
        index=model_idx,
        key=f"model_select_{active_chat_id}"
    )
    
    temperature = st.slider(
        "Temperature",
        min_value=0.0,
        max_value=2.0,
        value=current_temp,
        step=0.1,
        key=f"temp_slider_{active_chat_id}"
    )
    
    persona_map = {"Default": "default", "Expert Software Engineer": "coder"}
    persona_display_options = ["Default", "Expert Software Engineer"]
    persona_rev_map = {"default": "Default", "coder": "Expert Software Engineer"}
    
    persona_display_val = persona_rev_map.get(current_persona, "Default")
    persona_idx = persona_display_options.index(persona_display_val) if persona_display_val in persona_display_options else 0
    
    persona_display = st.selectbox(
        "Persona",
        options=persona_display_options,
        index=persona_idx,
        key=f"persona_select_{active_chat_id}"
    )
    persona = persona_map.get(persona_display, "default")
    
    # Detect modifications and automatically update details in persistence
    if (model_option != current_model or temperature != current_temp or persona != current_persona):
        logger.info("Chat configuration settings changed. Syncing updates with database...")
        update_backend_chat(
            chat_id=active_chat_id,
            persona=persona,
            temperature=temperature,
            model=model_option,
            token=user_token
        )
        # Update local values instantly
        active_chat["model"] = model_option
        active_chat["temperature"] = temperature
        active_chat["persona"] = persona
        active_chat["updatedAt"] = time.time()

    # 4. Knowledge Base (RAG Documents)
    st.markdown('<hr style="border: 0; border-top: 1px solid rgba(255,255,255,0.1); margin: 1.5rem 0;" />', unsafe_allow_html=True)
    st.markdown('<div class="glass-card-title">📚 Knowledge Base</div>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader(
        "Attach Document (PDF, TXT, MD)",
        type=["pdf", "txt", "md"],
        key=f"file_uploader_{active_chat_id}"
    )
    
    if uploaded_file is not None:
        uploaded_key = f"uploaded_{active_chat_id}_{uploaded_file.name}"
        if uploaded_key not in st.session_state:
            with st.spinner("Indexing document... 📚"):
                file_bytes = uploaded_file.read()
                res = upload_chat_document_api(
                    chat_id=active_chat_id,
                    file_bytes=file_bytes,
                    filename=uploaded_file.name,
                    token=user_token
                )
                if "error" in res:
                    st.error(f"Upload failed: {res['error']}")
                else:
                    st.session_state[uploaded_key] = True
                    st.success(f"Successfully indexed: {uploaded_file.name}")
                    documents_list = active_chat.setdefault("documents", [])
                    documents_list.append({
                        "doc_id": res["doc_id"],
                        "filename": res["filename"],
                        "uploadedAt": time.time()
                    })
                    st.rerun()

    # List Uploaded Documents
    documents = active_chat.get("documents", [])
    if documents:
        st.markdown('<div style="margin-top: 0.5rem; font-weight: 500;">Uploaded Documents:</div>', unsafe_allow_html=True)
        for doc in documents:
            doc_id = doc["doc_id"]
            filename = doc["filename"]
            
            col1, col2 = st.columns([0.85, 0.15])
            with col1:
                st.markdown(f'<div style="font-size: 0.85rem; padding: 4px 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #cbd5e1;">📄 {filename}</div>', unsafe_allow_html=True)
            with col2:
                if st.button("🗑️", key=f"del_doc_{doc_id}_{active_chat_id}", help="Delete document"):
                    with st.spinner("Deleting..."):
                        success = delete_chat_document_api(chat_id=active_chat_id, doc_id=doc_id, token=user_token)
                        if success:
                            active_chat["documents"] = [d for d in documents if d["doc_id"] != doc_id]
                            st.rerun()
                        else:
                            st.error("Failed to delete.")
    else:
        st.info("No documents uploaded for this chat.")

    st.write("")
    st.markdown('<div class="stats-container">', unsafe_allow_html=True)
    st.markdown(f"**Total Prompts:** {st.session_state.stats_prompts}")
    elapsed = int(time.time() - st.session_state.stats_start_time)
    minutes = elapsed // 60
    seconds = elapsed % 60
    st.markdown(f"**Duration:** {minutes:02d}:{seconds:02d}")
    st.markdown('</div>', unsafe_allow_html=True)
    st.write("")
    
    # Clear Messages CRUD Sync
    st.markdown('<div class="settings-actions-container">', unsafe_allow_html=True)
    if st.button("🧹 Clear Messages", use_container_width=True, key="clear_chat_messages_btn"):
        logger.info("Clear Chat History button clicked. Syncing with database...")
        success = update_backend_chat(chat_id=active_chat_id, messages=[], token=user_token)
        if success:
            active_chat["messages"] = []
            if not active_chat_id.startswith("chat_default"):
                # Reset name
                update_backend_chat(chat_id=active_chat_id, name="New Chat", token=user_token)
                active_chat["name"] = "New Chat"
            st.session_state.stats_prompts = 0
            st.rerun()
            
    # Delete Chat CRUD Sync
    if st.button("🗑️ Delete Chat", use_container_width=True, type="primary", key="delete_chat_btn"):
        logger.info("Delete Chat button clicked. Deleting from backend...")
        success = delete_backend_chat(chat_id=active_chat_id, token=user_token)
        if success:
            del st.session_state.chats[active_chat_id]
            if st.session_state.chats:
                st.session_state.active_chat_id = list(st.session_state.chats.keys())[0]
            else:
                # Fallback recreate
                default_id = f"chat_{int(time.time() * 1000)}"
                create_backend_chat(default_id, "🐧 Default Chat", token=user_token)
                st.session_state.active_chat_id = default_id
            st.session_state.stats_prompts = 0
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
