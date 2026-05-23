import os
import sys
from pathlib import Path

# Add project root to sys.path to enable direct backend import
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from fastapi import FastAPI
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
