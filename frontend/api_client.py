import os
import requests
import sys
from pathlib import Path

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
    Streams response from the Pingu FastAPI backend.
    """
    backend_url = os.getenv("PINGU_BACKEND_URL", "http://localhost:8000")
    chat_endpoint = f"{backend_url}/api/chat"
    
    payload = {
        "messages": messages,
        "persona": persona,
        "temperature": temperature,
        "model": model
    }
    
    try:
        logger.info("Sending chat request to FastAPI backend: %s", chat_endpoint)
        response = requests.post(chat_endpoint, json=payload, stream=True, timeout=20)
        
        if response.status_code == 200:
            for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                if chunk:
                    yield chunk
        else:
            try:
                error_detail = response.json().get("detail", response.text)
            except Exception:
                error_detail = response.text
            yield f"⚠️ **Backend Error ({response.status_code}):** {error_detail}"
            
    except requests.exceptions.ConnectionError:
        yield "**Connection Error:** Could not connect to the Pingu FastAPI backend server. Please make sure the backend is running (`uvicorn backend.main:app --port 8000`) and accessible."
    except requests.exceptions.Timeout:
        yield "**Timeout Error:** The backend server timed out while waiting for a response."
    except Exception as e:
        yield f"**Error:** An unexpected error occurred: {str(e)}"
