import os
import sys
import requests
import urllib.parse
from pathlib import Path
import streamlit as st

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from backend.logger import app_logger as logger

# Credentials Configuration
GOOGLE_CLIENT_ID = None
GOOGLE_CLIENT_SECRET = None
FIREBASE_WEB_API_KEY = None

try:
    GOOGLE_CLIENT_ID = st.secrets.get("GOOGLE_CLIENT_ID") or st.secrets.get("google_client_id")
    GOOGLE_CLIENT_SECRET = st.secrets.get("GOOGLE_CLIENT_SECRET")
    FIREBASE_WEB_API_KEY = st.secrets.get("FIREBASE_WEB_API_KEY")
except Exception:
    pass

if not GOOGLE_CLIENT_ID:
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
if not GOOGLE_CLIENT_SECRET:
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
if not FIREBASE_WEB_API_KEY:
    FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY")

auth_configured = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and FIREBASE_WEB_API_KEY)
redirect_uri = os.getenv("REDIRECT_URI", "http://localhost:8501")


def exchange_code_for_firebase_user(auth_code: str):
    """Exchanges Google auth code for Google ID token, then signs in to Firebase."""
    logger.info("Exchanging authorization code for Google tokens...")
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": auth_code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }
    
    try:
        # Get Google ID Token
        res = requests.post(token_url, data=data, timeout=10)
        if res.status_code != 200:
            st.error(f"Failed to fetch Google OAuth tokens: {res.text}")
            logger.error("Google OAuth token exchange failed: %s", res.text)
            return None
            
        tokens = res.json()
        google_id_token = tokens.get("id_token")
        if not google_id_token:
            st.error("No id_token returned in Google OAuth response.")
            return None
            
        # Swap Google token for Firebase ID Token
        logger.info("Exchanging Google ID token for Firebase credentials...")
        firebase_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key={FIREBASE_WEB_API_KEY}"
        payload = {
            "postBody": f"id_token={google_id_token}&providerId=google.com",
            "requestUri": redirect_uri,
            "returnIdpCredential": True,
            "returnSecureToken": True
        }
        
        fb_res = requests.post(firebase_url, json=payload, timeout=10)
        if fb_res.status_code != 200:
            st.error(f"Failed to authenticate with Firebase: {fb_res.text}")
            logger.error("Firebase accounts exchange failed: %s", fb_res.text)
            return None
            
        fb_data = fb_res.json()
        user_info = {
            "uid": fb_data.get("localId"),
            "email": fb_data.get("email"),
            "displayName": fb_data.get("displayName", "Firebase User"),
            "photoURL": fb_data.get("photoUrl") or f"https://api.dicebear.com/7.x/bottts/svg?seed={fb_data.get('email')}",
            "token": fb_data.get("idToken"),
            "refreshToken": fb_data.get("refreshToken")
        }
        logger.info("Successfully authenticated user: %s via Google & Firebase Auth", user_info["email"])
        return user_info
        
    except Exception as e:
        st.error(f"An unexpected authentication error occurred: {str(e)}")
        logger.error("OAuth exchange failed with exception: %s", str(e), exc_info=True)
        return None

def handle_oauth_callback():
    """Checks query params for Google OAuth callback code and signs in user."""
    if st.session_state.user is None and auth_configured:
        q_params = st.query_params
        if "code" in q_params:
            auth_code = q_params["code"]
            with st.spinner("Exchanging secure authentication credentials..."):
                user_profile = exchange_code_for_firebase_user(auth_code)
                if user_profile:
                    st.session_state.user = user_profile
                    st.query_params.clear()
                    st.rerun()

def get_google_auth_url() -> str:
    """Generates the Google OAuth redirection URL."""
    google_auth_params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "prompt": "select_account"
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(google_auth_params)}"
