# Pingu AI

Pingu AI is an LLM-powered chat application that supports real-time streaming over WebSockets and session-isolated Retrieval-Augmented Generation (RAG). 

The system is built as a split-architecture codebase:
1. **Backend:** A FastAPI service handling chat sessions, document parsing, Pinecone vector indexing, and Gemini model interactions.
2. **Frontend:** A Streamlit dashboard utilizing custom CSS layouts and component-level files to coordinate session state, configuration inputs, and live socket streaming.

---

## System Architecture

```mermaid
graph TD
    A[Streamlit Frontend] <-->|WebSockets / HTTP| B[FastAPI Backend]
    B <-->|Session Persistence| C[(Google Firestore / Memory Fallback)]
    B -->|Authentication| D[Firebase Auth]
    B -->|Embeddings & Completion| E[Google Gemini API]
    B <-->|Vector Retrieval| F[(Pinecone Vector DB)]
```

### Core Features
* **Streaming Responses:** Real-time generation streaming powered by the `google-genai` SDK and the `gemini-2.5-flash-lite` model.
* **Session-Isolated RAG:** Document indexing (PDF, TXT, MD) using `gemini-embedding-001` (768 dimensions) stored under chat-specific Pinecone namespaces.
* **Hybrid Storage Layer:** Saves chat history and document metadata directly to Firestore, with a local in-memory fallback for offline development.
* **User Authentication:** Firebase ID token validation with a local developer bypass (`demo_token`).
* **Production Abuse Safeguards:** 
  * **IP-based Rate Limiting:** Built-in in-memory rate-limiter middleware (max 60 requests per minute per IP) to prevent bot spamming.
  * **Document Constraints:** Strict 5MB file size limit and a maximum of 5 active documents per chat session to protect free-tier Pinecone storage.
  * **Dynamic CORS:** Restricts requests only to specified frontend domains.
  * **Zero-File Deployments:** Support for injecting Firebase credentials directly as a raw JSON string content environment variable.

---

## Directory Structure

```text
pingu-ai/
├── README.md               # System overview and setup (this file)
├── requirements.txt        # Shared dependencies
├── backend/                # FastAPI service
│   ├── README.md           # Backend routes, RAG processing, and architecture details
│   ├── .env                # Local backend environment secrets
│   ├── main.py             # Server entry point & CORS configuration
│   ├── config.py           # Configuration mapping and dynamic .env loading
│   ├── logger.py           # Multi-target logger (console & file)
│   ├── routes/             
│   │   ├── auth.py         # Auth validation dependency
│   │   └── chat.py         # REST chat endpoints and WebSocket stream loop
│   └── services/           
│       ├── chat_store.py   # Firestore / in-memory storage adapter
│       ├── firebase.py     # Firebase Admin SDK initializer
│       ├── llm.py          # Gemini API wrapper for stream generation
│       └── rag.py          # Pinecone vector indexing and PDF/text parsing pipeline
└── frontend/               # Streamlit application
    ├── README.md           # Component definitions, state sync, and custom styling
    ├── app.py              # Main dashboard entry point & layout definition
    ├── style.css           # Custom CSS overrides for Streamlit
    └── src/                
        ├── api.py          # API connector client (HTTP & WebSockets)
        ├── auth.py         # OAuth callbacks and credential storage
        ├── state.py        # Streamlit SessionState initialization & sync engine
        └── components/     # UI components
            ├── chat_view.py      # Core chat dialog & websocket message stream
            ├── login_view.py     # User authentication UI
            ├── settings_view.py  # Model controls & RAG file manager
            └── sidebar.py        # History thread list & deletion utility
```

---

## Environmental Setup

Create a `.env` file in the `backend/` directory (or specify them directly in your cloud provider's dashboard). The frontend will automatically detect backend variables if loaded from the root or backend directories.

```env
# Gemini API Key
GEMINI_API_KEY="your-gemini-api-key"

# Firebase Client Configuration (Frontend Auth)
GOOGLE_CLIENT_ID="your-google-client-id"
GOOGLE_CLIENT_SECRET="your-google-client-secret"
FIREBASE_WEB_API_KEY="your-firebase-web-api-key"

# Firebase Admin SDK Configuration (Backend Persistence)
# Support either a filepath or a raw JSON string content representation:
FIREBASE_SERVICE_ACCOUNT_JSON="pingu-52f3f-firebase-adminsdk-g8i1m-6f16c1d817.json"
# FIREBASE_SERVICE_ACCOUNT_JSON_CONTENT='{"type": "service_account", ...}'

# Pinecone Configuration (RAG)
PINECONE_API_KEY="your-pinecone-api-key"
PINECONE_INDEX_NAME="pingu-rag"

# Deployed Environment Settings
ENV="development" # Set to "production" in cloud hosting to enforce strict auth
ALLOWED_ORIGINS="*" # Set to your deployed frontend domain in production (comma-separated list)
```

---

## Getting Started

### 1. Installation

Clone the repository and set up a virtual environment:

```bash
# Clone the repository
git clone https://github.com/aryanjha22/pingu-ai.git
cd pingu-ai

# Set up virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run the Backend

Launch the FastAPI server on port `8000`:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
* **API Docs:** Interactive Swagger UI is available at `http://localhost:8000/docs`.
* **Health Check:** `http://localhost:8000/health` returns standard status flags.

### 3. Run the Frontend

In a separate terminal shell (with the virtual environment active), run:

```bash
streamlit run frontend/app.py
```
The interface will be hosted locally at `http://localhost:8501`.

---

## Production Security Settings vs Local Sandbox

To simplify local development and safeguard cloud operations in production, the codebase runs in two modes:

### Local Developer Bypass (Offline Sandbox)
If `ENV` is not set to `production`:
* **No Firebase Credentials:** Gracefully degrades to **Local Mode**, persisting chat sessions in-memory. Logging in on the frontend with the "Guest Login" button uses a mock profile (`demo_user`) backed by `demo_token` validation.
* **No Pinecone Credentials:** Bypasses vector database initializations. Normal chat remains active, but document upload and RAG indexing will be disabled.

### Strict Production Mode (Cloud Showcase)
If `ENV` is set to `production` or `PROD` is set to `true`:
* **Bypass Disabled:** The `demo_token` guest bypass is **completely disabled**. Unauthenticated or anonymous connection requests are strictly rejected.
* **Rate Limits Active:** Rejects clients that make more than 60 backend API requests per minute.
* **Upload Limits Active:** Document size is strictly capped at 5MB, and a maximum of 5 files can be uploaded per chat session in Pinecone to prevent memory exhaustion.
* **Origin Locking:** CORS headers restrict API access only to the domains defined under `ALLOWED_ORIGINS`.
