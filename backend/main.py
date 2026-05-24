import os
import sys
from pathlib import Path

# Add project root to sys.path to enable direct backend import
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from backend.llm import stream_chat_response
from backend.logger import backend_logger as logger

# Initialize FastAPI application
app = FastAPI(
    title="Pingu AI Backend",
    description="FastAPI-based streaming backend for the Pingu AI Assistant",
    version="1.0.0"
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    persona: str = "default"
    temperature: float = 0.7
    model: str = "gemini-2.5-flash-lite"

@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    logger.info("Health check endpoint hit.")
    return {"status": "ok", "message": "Pingu AI Backend is up and running!"}

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Streams response from Gemini API through stream_chat_response.
    """
    logger.info(
        "Chat endpoint triggered. Model: %s | Temp: %f | Persona: %s | Num Messages: %d",
        request.model, request.temperature, request.persona, len(request.messages)
    )
    
    # Convert Pydantic Message models back to dict for the LLM stream_chat_response logic
    messages_dict = [{"role": msg.role, "content": msg.content} for msg in request.messages]
    
    # Generate streaming response
    generator = stream_chat_response(
        messages=messages_dict,
        persona=request.persona,
        temperature=request.temperature,
        model=request.model
    )
    
    return StreamingResponse(generator, media_type="text/plain")


@app.websocket("/api/ws/chat")
async def websocket_chat_endpoint(websocket: WebSocket):
    """
    Persistent WebSocket endpoint for bidirectional, real-time streamed chat.
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted.")
    try:
        while True:
            # Await incoming message from the client
            data = await websocket.receive_json()
            logger.info("Received WebSocket message payload: %s", data)
            
            messages = data.get("messages", [])
            persona = data.get("persona", "default")
            temperature = data.get("temperature", 0.7)
            model = data.get("model", "gemini-2.5-flash-lite")
            
            messages_dict = [{"role": msg["role"], "content": msg["content"]} for msg in messages]
            
            try:
                # Iterate through LLM generator and push chunks back to the client
                generator = stream_chat_response(
                    messages=messages_dict,
                    persona=persona,
                    temperature=temperature,
                    model=model
                )
                
                for chunk in generator:
                    await websocket.send_json({"type": "chunk", "text": chunk})
                
                await websocket.send_json({"type": "done"})
            except Exception as e:
                logger.error("Error generating stream response over WS: %s", str(e), exc_info=True)
                await websocket.send_json({"type": "error", "text": str(e)})
                
    except WebSocketDisconnect:
        logger.info("WebSocket connection disconnected by client.")
    except Exception as e:
        logger.error("WebSocket server connection error: %s", str(e), exc_info=True)

