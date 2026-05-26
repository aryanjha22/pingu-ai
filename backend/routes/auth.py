from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from backend import config
from backend.services.firebase import verify_firebase_token
from backend.logger import backend_logger as logger

# Initialize HTTP Bearer security scheme
security = HTTPBearer(auto_error=False)

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> dict:
    """
    Dependency to fetch and validate the Firebase auth token from the request.
    If credentials are correct, returns the verified user dictionary:
        { "uid": ..., "email": ..., "displayName": ..., "photoURL": ... }
    
    If running in Local Developer Mode (Firebase not configured), allows "demo_token"
    to bypass auth with a mock profile.
    """
    if not credentials:
        # Check if auth is configured
        if not config.firebase_configured:
            if config.IS_PROD:
                logger.error("Attempted anonymous access in production mode.")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Anonymous developer bypass is disabled in production mode."
                )
            # Fallback user in unconfigured dev mode
            logger.info("Accessing endpoint in Local Developer Mode without credentials. Granting mock demo user.")
            return {
                "uid": "demo_user",
                "email": "demo@pingu.ai",
                "displayName": "Demo Pingu",
                "photoURL": "https://api.dicebear.com/7.x/bottts/svg?seed=Pingu"
            }
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization Header Bearer Token."
        )

    token = credentials.credentials
    try:
        user_profile = verify_firebase_token(token)
        return user_profile
    except Exception as e:
        logger.error("Security Authentication Failed: %s", str(e))
        # If in unconfigured developer mode, we can allow simple bypass
        if not config.firebase_configured:
            if config.IS_PROD:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication failed. Bypass is disabled in production mode."
                )
            logger.info("Local mode token validation failure. Returning demo user.")
            return {
                "uid": "demo_user",
                "email": "demo@pingu.ai",
                "displayName": "Demo Pingu",
                "photoURL": "https://api.dicebear.com/7.x/bottts/svg?seed=Pingu"
            }
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired security credentials: {str(e)}"
        )
