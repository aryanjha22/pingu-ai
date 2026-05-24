import json
import os
import sys
from pathlib import Path
import streamlit as st
import websocket

# Ensure backend logger can be imported if needed
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from backend.logger import app_logger as logger

def stream_chat_from_api(
    messages: list,
    persona: str = "default",
    temperature: float = 0.7,
    model: str = "gemini-2.5-flash-lite"
):
    """
    Streams response from the Pingu FastAPI backend using a WebSocket connection.
    Establishes a connection for the duration of the request and closes it cleanly.
    """
    backend_url = os.getenv("PINGU_BACKEND_URL", "http://localhost:8000")
    # Convert HTTP URL to WS URL
    ws_url = backend_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_endpoint = f"{ws_url}/api/ws/chat"

    logger.info("Establishing WebSocket connection to %s", ws_endpoint)
    try:
        ws = websocket.create_connection(ws_endpoint, timeout=90)
    except Exception as e:
        logger.error("Failed to connect to WebSocket: %s", str(e))
        yield f"⚠️ **WebSocket Connection Error:** Could not connect to the Pingu backend server at `{ws_endpoint}`. Please make sure the backend is running."
        return

    payload = {
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
