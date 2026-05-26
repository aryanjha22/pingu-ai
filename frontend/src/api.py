import json
import os
import sys
import requests
from pathlib import Path
import websocket

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from backend.logger import app_logger as logger

def get_backend_url() -> str:
    """Retrieves backend API base URL from env or defaults to local host."""
    return os.getenv("PINGU_BACKEND_URL", "http://localhost:8000")

def get_headers(token: str = None) -> dict:
    """Generates standard request headers with Authorization Bearer token."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

def fetch_user_chats(token: str = None) -> list:
    """Fetches all stored chat sessions from the backend for the current user."""
    url = f"{get_backend_url()}/api/chats"
    logger.info("REST: Fetching user chats from backend URL: %s", url)
    try:
        response = requests.get(url, headers=get_headers(token), timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error("Failed to fetch chats: HTTP %d - %s", response.status_code, response.text)
            return []
    except Exception as e:
        logger.error("REST: Connection error during fetch_user_chats: %s", str(e))
        return []

def create_backend_chat(
    chat_id: str,
    name: str,
    persona: str = "default",
    temperature: float = 0.7,
    model: str = "gemini-2.5-flash-lite",
    token: str = None
) -> bool:
    """Registers a new chat session metadata in backend persistence."""
    url = f"{get_backend_url()}/api/chats"
    payload = {
        "chat_id": chat_id,
        "name": name,
        "persona": persona,
        "temperature": temperature,
        "model": model
    }
    logger.info("REST: Registering new chat '%s' (ID: %s)", name, chat_id)
    try:
        response = requests.post(url, json=payload, headers=get_headers(token), timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error("REST: Connection error during create_backend_chat: %s", str(e))
        return False

def update_backend_chat(
    chat_id: str,
    name: str = None,
    persona: str = None,
    temperature: float = None,
    model: str = None,
    token: str = None,
    messages: list = None
) -> bool:
    """Updates settings, name, or messages for a chat session in backend persistence."""
    url = f"{get_backend_url()}/api/chats/{chat_id}"
    payload = {}
    if name is not None:
        payload["name"] = name
    if persona is not None:
        payload["persona"] = persona
    if temperature is not None:
        payload["temperature"] = temperature
    if model is not None:
        payload["model"] = model
    if messages is not None:
        payload["messages"] = messages

    logger.info("REST: Updating chat metadata for ID: %s - Data keys: %s", chat_id, list(payload.keys()))
    try:
        response = requests.put(url, json=payload, headers=get_headers(token), timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error("REST: Connection error during update_backend_chat: %s", str(e))
        return False

def delete_backend_chat(chat_id: str, token: str = None) -> bool:
    """Deletes a chat session permanently in backend persistence."""
    url = f"{get_backend_url()}/api/chats/{chat_id}"
    logger.info("REST: Deleting chat ID: %s", chat_id)
    try:
        response = requests.delete(url, headers=get_headers(token), timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error("REST: Connection error during delete_backend_chat: %s", str(e))
        return False

def stream_chat_from_api(
    messages: list,
    chat_id: str = None,
    persona: str = "default",
    temperature: float = 0.7,
    model: str = "gemini-2.5-flash-lite",
    token: str = None
):
    """
    Streams response from the Pingu FastAPI backend using a WebSocket connection.
    Passes the auth JWT as a query param and session metadata in payload.
    """
    backend_url = get_backend_url()
    # Convert HTTP URL to WS URL
    ws_url = backend_url.replace("http://", "ws://").replace("https://", "wss://")
    
    ws_endpoint = f"{ws_url}/api/ws/chat"
    if token:
        ws_endpoint += f"?token={token}"

    logger.info("Establishing WebSocket connection to authenticated endpoint: %s", ws_url + "/api/ws/chat")
    try:
        ws = websocket.create_connection(ws_endpoint, timeout=90)
    except Exception as e:
        logger.error("Failed to connect to WebSocket: %s", str(e))
        yield f"⚠️ **WebSocket Connection Error:** Could not connect to the Pingu backend server at `{ws_endpoint}`. Please make sure the backend is running."
        return

    payload = {
        "chat_id": chat_id,
        "messages": messages,
        "persona": persona,
        "temperature": temperature,
        "model": model
    }

    try:
        logger.info("Sending chat request to FastAPI backend via WebSocket")
        ws.send(json.dumps(payload))

        while True:
            response = ws.recv()
            if not response:
                break
            
            data = json.loads(response)
            msg_type = data.get("type")
            
            if msg_type == "chunk":
                yield data.get("text", "")
            elif msg_type == "error":
                yield f"⚠️ **Backend Error:** {data.get('text', 'Unknown error')}"
                break
            elif msg_type == "done":
                break
                
    except websocket.WebSocketConnectionClosedException:
        yield "⚠️ **Connection Closed:** The WebSocket connection was terminated by the server."
    except Exception as e:
        logger.error("Error during WebSocket communication: %s", str(e), exc_info=True)
        yield f"⚠️ **WebSocket Error:** An unexpected error occurred: {str(e)}"
    finally:
        try:
            ws.close()
            logger.info("WebSocket connection closed cleanly.")
        except Exception:
            pass

def upload_chat_document_api(chat_id: str, file_bytes: bytes, filename: str, token: str = None) -> dict:
    """Uploads a document for RAG indexing to the backend."""
    url = f"{get_backend_url()}/api/chats/{chat_id}/documents"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    files = {"file": (filename, file_bytes, "application/octet-stream")}
    logger.info("REST: Uploading document '%s' to chat ID: %s", filename, chat_id)
    try:
        response = requests.post(url, headers=headers, files=files, timeout=60)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error("Failed to upload document: HTTP %d - %s", response.status_code, response.text)
            return {"error": response.text}
    except Exception as e:
        logger.error("REST: Connection error during upload_chat_document_api: %s", str(e))
        return {"error": str(e)}

def delete_chat_document_api(chat_id: str, doc_id: str, token: str = None) -> bool:
    """Deletes an uploaded RAG document from the backend."""
    url = f"{get_backend_url()}/api/chats/{chat_id}/documents/{doc_id}"
    logger.info("REST: Deleting document ID: %s from chat ID: %s", doc_id, chat_id)
    try:
        response = requests.delete(url, headers=get_headers(token), timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error("REST: Connection error during delete_chat_document_api: %s", str(e))
        return False

