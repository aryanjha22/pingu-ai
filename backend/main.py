import os
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path for direct imports
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from backend import config
from backend.routes.chat import router as chat_router
from backend.logger import backend_logger as logger

app = FastAPI(
    title="Pingu AI Backend",
    description="FastAPI-based streaming backend for the Pingu AI Assistant",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory IP-based rate limiting for basic DDoS mitigation
RATE_LIMIT_STORE = {}
RATE_LIMIT_WINDOW = 60       # seconds
RATE_LIMIT_MAX_REQUESTS = 60 

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api"):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Prune expired requests
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

app.include_router(chat_router)

@app.get("/health")
def health_check():
    logger.info("Health check endpoint hit.")
    return {"status": "ok", "message": "Pingu AI Backend is up and running!"}
