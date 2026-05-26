from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query, HTTPException, status, UploadFile, File
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from backend import config
from backend.services.firebase import verify_firebase_token
from backend.services.chat_store import chat_store
from backend.services.llm import stream_chat_response
from backend.services.rag import index_document, delete_document_vectors, query_rag_context
from backend.routes.auth import get_current_user
from backend.logger import backend_logger as logger

router = APIRouter(prefix="/api")

# Pydantic Schemas
class MessageItem(BaseModel):
    role: str
    content: str

class ChatCreateRequest(BaseModel):
    chat_id: str
    name: str
    persona: str = "default"
    temperature: float = 0.7
    model: Optional[str] = None

class ChatUpdateRequest(BaseModel):
    name: Optional[str] = None
    persona: Optional[str] = None
    temperature: Optional[float] = None
    model: Optional[str] = None
    messages: Optional[List[MessageItem]] = None


# REST ENDPOINTS

@router.get("/chats")
def list_chats(user: dict = Depends(get_current_user)):
    """List all chat sessions belonging to the authenticated user."""
    return chat_store.get_user_chats(user["uid"])

@router.post("/chats")
def create_chat(payload: ChatCreateRequest, user: dict = Depends(get_current_user)):
    """Create a new chat session for the authenticated user."""
    success = chat_store.create_chat(
        uid=user["uid"],
        chat_id=payload.chat_id,
        name=payload.name,
        persona=payload.persona,
        temperature=payload.temperature,
        model=payload.model
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register chat session in database."
        )
    return {"status": "ok", "chat_id": payload.chat_id}

@router.put("/chats/{chat_id}")
def update_chat(chat_id: str, payload: ChatUpdateRequest, user: dict = Depends(get_current_user)):
    """Update settings, title, or message history for a chat session."""
    # Handle settings update
    success = chat_store.update_chat_settings(
        chat_id=chat_id,
        name=payload.name,
        persona=payload.persona,
        temperature=payload.temperature,
        model=payload.model
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update chat settings in database."
        )
        
    # Handle messages history update if provided
    if payload.messages is not None:
        messages_list = [{"role": msg.role, "content": msg.content} for msg in payload.messages]
        success_msg = chat_store.update_chat_messages(chat_id, messages_list)
        if not success_msg:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update chat messages in database."
            )
            
    return {"status": "ok"}

@router.delete("/chats/{chat_id}")
def delete_chat(chat_id: str, user: dict = Depends(get_current_user)):
    """Delete an entire chat session permanently."""
    success = chat_store.delete_chat(chat_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete chat session from database."
        )
    return {"status": "ok"}


@router.post("/chats/{chat_id}/documents")
async def upload_chat_document(
    chat_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    """Upload and index a document for RAG in Pinecone."""
    try:
        # 1. Enforce Document Count Limit per chat (Max 5 documents)
        chat = chat_store.get_chat(chat_id)
        if chat:
            existing_docs = chat.get("documents", [])
            if len(existing_docs) >= 5:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Maximum limit of 5 documents reached for this chat. Please delete existing documents to upload new ones."
                )

        content = await file.read()
        
        # 2. Enforce File Size Limit (Max 5MB)
        MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is too large. Maximum supported document size is 5MB."
            )

        import uuid
        doc_id = f"doc_{uuid.uuid4().hex}"
        
        # Parse, chunk, and index in Pinecone
        index_document(chat_id=chat_id, doc_id=doc_id, filename=file.filename, file_content=content)
        
        # Save in database
        success = chat_store.add_chat_document(chat_id=chat_id, doc_id=doc_id, filename=file.filename)
        if not success:
            delete_document_vectors(chat_id=chat_id, doc_id=doc_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to register document in database."
            )
            
        return {"status": "ok", "doc_id": doc_id, "filename": file.filename}
    except HTTPException:
        # Re-raise HTTPExceptions so they aren't caught by the general catch-all below
        raise
    except Exception as e:
        logger.error("Error uploading document: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process and index document: {str(e)}"
        )

@router.delete("/chats/{chat_id}/documents/{doc_id}")
def delete_chat_document(
    chat_id: str,
    doc_id: str,
    user: dict = Depends(get_current_user)
):
    """Remove a document's vector indices and database metadata."""
    try:
        delete_document_vectors(chat_id=chat_id, doc_id=doc_id)
        success = chat_store.remove_chat_document(chat_id=chat_id, doc_id=doc_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to remove document reference from database."
            )
        return {"status": "ok"}
    except Exception as e:
        logger.error("Error deleting document: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# WEBSOCKET STREAMING ENDPOINT

@router.websocket("/ws/chat")
async def websocket_chat_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    """
    Persistent WebSocket endpoint for bidirectional, real-time streamed chat.
    Performs user authentication using Firebase Token or developer bypass and
    automatically persists conversations in the active database storage.
    """
    await websocket.accept()
    logger.info("WebSocket connection requested.")

    # WebSocket authentication
    user = None
    try:
        if token:
            user = verify_firebase_token(token)
        else:
            # Check if we can use developer local fallback
            if not config.firebase_configured:
                user = {
                    "uid": "demo_user",
                    "email": "demo@pingu.ai",
                    "displayName": "Demo Pingu",
                    "photoURL": "https://api.dicebear.com/7.x/bottts/svg?seed=Pingu"
                }
                logger.info("WebSocket accepted anonymous developer bypass connection.")
            else:
                logger.warning("WebSocket credentials missing in production environment.")
    except Exception as e:
        logger.error("WebSocket credentials verification error: %s", str(e))
        
    if not user:
        logger.warning("Closing WebSocket connection due to authentication failure.")
        await websocket.send_json({"type": "error", "text": "Unauthorized connection."})
        await websocket.close()
        return

    try:
        while True:
            # Await incoming message payload
            data = await websocket.receive_json()
            logger.info("Received WebSocket chat payload from UID %s: %s", user["uid"], {k: v for k, v in data.items() if k != "messages"})

            chat_id = data.get("chat_id")
            messages = data.get("messages", [])
            persona = data.get("persona", "default")
            temperature = data.get("temperature", 0.7)
            model = data.get("model") or config.DEFAULT_MODEL

            # Convert JSON structure to backend lists
            messages_dict = [{"role": msg["role"], "content": msg["content"]} for msg in messages]

            current_summary = ""
            # Save the user's latest incoming message to persistence if chat_id is present
            if chat_id:
                chat_store.update_chat_messages(chat_id, messages_dict)
                # Apply context trimming & background summarization
                from backend.services.memory import manage_chat_memory
                messages_dict, current_summary = manage_chat_memory(chat_id, messages_dict)

            # RAG Context retrieval and injection
            augmented_messages = list(messages_dict)
            if chat_id and messages_dict:
                # Find last user message
                last_user_idx = -1
                for idx in range(len(messages_dict) - 1, -1, -1):
                    if messages_dict[idx]["role"] == "user":
                        last_user_idx = idx
                        break
                
                if last_user_idx != -1:
                    user_query = messages_dict[last_user_idx]["content"]
                    rag_context = query_rag_context(chat_id, user_query)
                    if rag_context:
                        augmented_query = (
                            f"[CONTEXT FROM UPLOADED DOCUMENTS]\n"
                            f"{rag_context}\n"
                            f"[END OF CONTEXT]\n\n"
                            f"Use the above context to answer the user query accurately. If the answer is not in the context, use your best knowledge but prioritize the context.\n\n"
                            f"User: {user_query}"
                        )
                        augmented_messages[last_user_idx] = {
                            "role": "user",
                            "content": augmented_query
                        }

            try:
                # Trigger generation stream
                generator = stream_chat_response(
                    messages=augmented_messages,
                    persona=persona,
                    temperature=temperature,
                    model=model,
                    summary=current_summary
                )

                full_response = ""
                try:
                    for chunk in generator:
                        full_response += chunk
                        await websocket.send_json({"type": "chunk", "text": chunk})
                except WebSocketDisconnect:
                    logger.info("WebSocket disconnected during stream. Saving partial response to database.")
                    raise
                finally:
                    # Append assistant response (even if partial/interrupted) and persist to database
                    if chat_id and full_response:
                        messages_dict.append({"role": "assistant", "content": full_response})
                        chat_store.update_chat_messages(chat_id, messages_dict)

                await websocket.send_json({"type": "done"})
            except WebSocketDisconnect:
                # Propagate this up so that the outer WebSocketDisconnect handler catches it cleanly
                raise
            except Exception as e:
                logger.error("Error generating stream response over WS: %s", str(e), exc_info=True)
                await websocket.send_json({"type": "error", "text": str(e)})

    except WebSocketDisconnect:
        logger.info("WebSocket connection disconnected by client: %s", user["uid"])
    except Exception as e:
        logger.error("WebSocket server connection error: %s", str(e), exc_info=True)
