import firebase_admin
from firebase_admin import credentials, auth, firestore
from backend import config
from backend.logger import backend_logger as logger

db = None
firebase_app = None

# Initialize Firebase Admin SDK
if config.firebase_configured:
    try:
        logger.info("Initializing Firebase Admin SDK using Service Account JSON: %s", config.FIREBASE_SERVICE_ACCOUNT_JSON)
        cred = credentials.Certificate(config.FIREBASE_SERVICE_ACCOUNT_JSON)
        firebase_app = firebase_admin.initialize_app(cred)
        db = firestore.client()
        logger.info("Firebase Admin SDK initialized successfully with Firestore database connection.")
    except Exception as e:
        logger.error("Failed to initialize Firebase Admin with credentials: %s. Falling back to local offline mode.", str(e), exc_info=True)
        db = None
else:
    logger.info("No Firebase Service Account JSON provided. Pingu AI Backend is running in Local/Offline Developer Mode.")
    db = None


def verify_firebase_token(token: str) -> dict:
    """
    Verifies a Firebase ID token.
    If the token is 'demo_token', immediately returns the mock guest profile.
    If Firebase is configured, it performs real token verification.
    """
    if token == "demo_token":
        logger.info("Bypassing Firebase Auth for guest demo_token.")
        return {
            "uid": "demo_user",
            "email": "demo@pingu.ai",
            "displayName": "Demo Pingu",
            "photoURL": "https://api.dicebear.com/7.x/bottts/svg?seed=Pingu"
        }

    if config.firebase_configured and firebase_app:
        try:
            decoded_token = auth.verify_id_token(token)
            return {
                "uid": decoded_token.get("uid"),
                "email": decoded_token.get("email"),
                "displayName": decoded_token.get("name", "Firebase User"),
                "photoURL": decoded_token.get("picture", "https://api.dicebear.com/7.x/bottts/svg?seed=Pingu")
            }
        except Exception as e:
            logger.error("Token verification failed: %s", str(e))
            raise e
    else:
        raise ValueError("Firebase is not configured and token is not demo_token.")
