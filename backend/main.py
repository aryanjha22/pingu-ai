import os
import sys
from pathlib import Path

# Add project root to sys.path to enable direct backend import
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routes.chat import router as chat_router
from backend.logger import backend_logger as logger

# Initialize FastAPI application
app = FastAPI(
    title="Pingu AI Backend",
    description="FastAPI-based streaming backend for the Pingu AI Assistant",
    version="1.1.0"
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount APIRouters
app.include_router(chat_router)

@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    logger.info("Health check endpoint hit.")
    return {"status": "ok", "message": "Pingu AI Backend is up and running!"}
