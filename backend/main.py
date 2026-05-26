import os
import sys
import time
from pathlib import Path

# Add project root to sys.path to enable direct backend import
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from backend import config
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
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory rate-limiter store
# Map IP address -> list of request timestamps
RATE_LIMIT_STORE = {}
RATE_LIMIT_WINDOW = 60       # 1 minute window
RATE_LIMIT_MAX_REQUESTS = 60 # max 60 requests per minute

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Built-in IP-based rate limiting to prevent endpoint abuse on free tiers."""
    # Only rate limit backend API paths
    if request.url.path.startswith("/api"):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Get and clean client history
        timestamps = RATE_LIMIT_STORE.get(client_ip, [])
        timestamps = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
        
        if len(timestamps) >= RATE_LIMIT_MAX_REQUESTS:
            logger.warning("Rate limit exceeded for IP: %s on path: %s", client_ip, request.url.path)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again after 60 seconds."}
            )
            
        timestamps.append(now)
        RATE_LIMIT_STORE[client_ip] = timestamps
        
    return await call_next(request)

# Mount APIRouters
app.include_router(chat_router)

@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    logger.info("Health check endpoint hit.")
    return {"status": "ok", "message": "Pingu AI Backend is up and running!"}
