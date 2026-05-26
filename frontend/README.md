# Pingu AI Frontend

The frontend is a Streamlit dashboard styled using an external CSS layer (`style.css`). It communicates with the backend via REST endpoints for setup/metadata tasks and a persistent WebSocket connection for real-time text streaming.

---

## Layout & Components

To work around the standard linear layouts of Streamlit, the application injects a custom stylesheet (`style.css`) and splits the user interface into three distinct columns `[0.22, 0.56, 0.22]`:
1. **Left Panel (Sidebar - `sidebar.py`):** Handles chat thread switching and chat creation/deletion operations.
2. **Center Panel (Chat View - `chat_view.py`):** Manages active chat logs, structures message bubbles, and implements the streaming output container.
3. **Right Panel (Settings - `settings_view.py`):** Holds LLM parameter controls (model picker, persona profiles, temperature) and handles RAG document uploads and list management.

---

## Source Structure

```text
frontend/
├── app.py                  # Streamlit entry point. Configures page layout and loads panels.
├── style.css               # CSS overrides modifying native Streamlit container styles.
└── src/
    ├── api.py              # Interface layer managing HTTP requests and WebSocket streams.
    ├── auth.py             # User authorization routines and OAuth callbacks.
    ├── state.py            # Streamlit SessionState initialization and background synchronization.
    └── components/         
        ├── chat_view.py    # Main messaging view and message rendering.
        ├── login_view.py   # Auth login card and guest developer bypass UI.
        ├── settings_view.py# Model parameter sliders and file upload controls.
        └── sidebar.py      # Thread listing panel.
```

---

## 🛠️ Deployed Compatibility Features

The frontend is built with production showcase environments in mind:

### 1. Host Agnostic Configuration
Resolves connection endpoints dynamically by reading the `PINGU_BACKEND_URL` environment variable. In your hosting dashboard, just configure:
```env
PINGU_BACKEND_URL="https://pingu-backend.onrender.com"
```
The client will automatically route all REST and WebSocket connections (`https://` matches `wss://` and `http://` matches `ws://`) seamlessly.

### 2. Standardized Error Interception
Our document upload limits (max **5MB** and **5 documents** per chat) are safely intercepted. When the server rejects a file, the frontend captures the payload and automatically displays a clean error banner in Streamlit:
```python
if "error" in res:
    st.error(f"Upload failed: {res['error']}")
```

---

## Run Instructions

### 1. Requirements
* `streamlit` for the UI.
* `requests` for REST HTTP connections.
* `websocket-client` for persistent streaming connections.

### 2. Startup Command
Launch the client from the project root:
```bash
streamlit run frontend/app.py
```
By default, the frontend attempts to connect to the backend at `http://localhost:8000`. You can override this URL by setting an environment variable:
```bash
export PINGU_BACKEND_URL="http://your-custom-backend-ip:8000"
streamlit run frontend/app.py
```
