import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables
backend_env = BASE_DIR / "backend" / ".env"
root_env = BASE_DIR / ".env"
if backend_env.exists():
    load_dotenv(backend_env)
elif root_env.exists():
    load_dotenv(root_env)
else:
    load_dotenv()

IS_PROD = os.getenv("ENV", "development").lower() == "production" or os.getenv("PROD", "false").lower() == "true"

CORS_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_RAW.split(",")] if CORS_ORIGINS_RAW else ["*"]

# Credentials & APIs
GEMINI_API_KEY = os.getenv("Gemini_API_Key") or os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "pingu-rag")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY")

FIREBASE_SERVICE_ACCOUNT_JSON = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
FIREBASE_SERVICE_ACCOUNT_JSON_CONTENT = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON_CONTENT")

# Resolve relative path for Firebase Service Account JSON
if FIREBASE_SERVICE_ACCOUNT_JSON:
    sa_path = Path(FIREBASE_SERVICE_ACCOUNT_JSON)
    if not sa_path.is_absolute():
        possible_paths = [
            BASE_DIR / sa_path,
            BASE_DIR / "backend" / sa_path
        ]
        for p in possible_paths:
            if p.exists():
                FIREBASE_SERVICE_ACCOUNT_JSON = str(p.resolve())
                break

# Parse service account JSON dict if provided directly as env string
firebase_sa_dict = None
if FIREBASE_SERVICE_ACCOUNT_JSON_CONTENT:
    try:
        firebase_sa_dict = json.loads(FIREBASE_SERVICE_ACCOUNT_JSON_CONTENT)
    except Exception:
        pass

firebase_configured = False
if firebase_sa_dict or (FIREBASE_SERVICE_ACCOUNT_JSON and os.path.exists(FIREBASE_SERVICE_ACCOUNT_JSON)):
    firebase_configured = True

auth_configured = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and FIREBASE_WEB_API_KEY)

# Session / Memory thresholds
CHAT_WINDOW_SIZE = 10
CHAT_SUMMARIZE_THRESHOLD = 20

DEFAULT_MODEL = "gemma-4-26b-a4b-it"

SYSTEM_PROMPTS = {
    "default": (
        "You are Pingu AI, a helpful, polite, intelligent, and comprehensive AI assistant. "
        "Don't go in detail keep your answers short and precise to the point. "
        "Also don't mention anything about google or LLM. Be whatever the user wants you to be just don't be rude"
    ),
    "coder": (
        "You are a Senior Software Architect and Coding Expert. "
        "Write robust, modern, clean, and highly documented code. Explain structural choices clearly and concisely."
    )
}

