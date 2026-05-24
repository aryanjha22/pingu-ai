import json
import time
from typing import List, Dict, Any, Optional
from google.cloud import firestore
from backend import config
from backend.services.firebase import db
from backend.logger import backend_logger as logger

class ChatStore:
    def __init__(self):
        self.db = db
        if not self.db:
            # Running in Offline / Local Developer Mode
            logger.info("Initializing in-memory fallback storage for Guest / Offline Developer Mode.")
            self.memory_store = {}  # Map chat_id -> chat dict

    def get_user_chats(self, uid: str) -> List[Dict[str, Any]]:
        """
        Retrieves all chat sessions for a specific user, sorted by updated time (newest first).
        """
        logger.info("Retrieving chat history for user UID: %s", uid)
        if self.db:
            try:
                # Firestore - retrieve user's chats and sort in memory to avoid composite index requirements
                docs = self.db.collection("chats").where("uid", "==", uid).stream()
                chats = []
                for doc in docs:
                    data = doc.to_dict()
                    data["chat_id"] = doc.id
                    chats.append(data)
                
                # Sort in memory by updatedAt (newest first)
                chats.sort(key=lambda x: x.get("updatedAt", 0), reverse=True)
                return chats
            except Exception as e:
                logger.error("Firestore query error for user %s: %s. Falling back to empty history.", uid, str(e), exc_info=True)
                return []
        else:
            # In-Memory fallback
            try:
                chats = []
                for chat_id, data in self.memory_store.items():
                    if data.get("uid") == uid:
                        chat_copy = dict(data)
                        chat_copy["chat_id"] = chat_id
                        chats.append(chat_copy)
                
                # Sort in memory by updatedAt (newest first)
                chats.sort(key=lambda x: x.get("updatedAt", 0), reverse=True)
                return chats
            except Exception as e:
                logger.error("In-memory query error for user %s: %s", uid, str(e), exc_info=True)
                return []

    def create_chat(
        self,
        uid: str,
        chat_id: str,
        name: str,
        persona: str = "default",
        temperature: float = 0.7,
        model: str = "gemini-2.5-flash-lite"
    ) -> bool:
        """
        Creates a new empty chat session for a user.
        """
        now = time.time()
        logger.info("Creating new chat session '%s' (ID: %s) for UID: %s", name, chat_id, uid)
        if self.db:
            try:
                # Firestore
                self.db.collection("chats").document(chat_id).set({
                    "uid": uid,
                    "name": name,
                    "persona": persona,
                    "temperature": temperature,
                    "model": model,
                    "messages": [],
                    "createdAt": now,
                    "updatedAt": now
                })
                return True
            except Exception as e:
                logger.error("Firestore insertion failed: %s", str(e), exc_info=True)
                return False
        else:
            # In-Memory fallback
            try:
                self.memory_store[chat_id] = {
                    "uid": uid,
                    "name": name,
                    "persona": persona,
                    "temperature": temperature,
                    "model": model,
                    "messages": [],
                    "createdAt": now,
                    "updatedAt": now
                }
                return True
            except Exception as e:
                logger.error("In-memory insertion failed: %s", str(e), exc_info=True)
                return False

    def update_chat_messages(self, chat_id: str, messages: List[Dict[str, str]]) -> bool:
        """
        Overwrites the entire message history list in a chat.
        """
        now = time.time()
        logger.info("Updating message history for chat ID: %s (%d messages)", chat_id, len(messages))
        if self.db:
            try:
                # Firestore
                self.db.collection("chats").document(chat_id).update({
                    "messages": messages,
                    "updatedAt": now
                })
                return True
            except Exception as e:
                logger.error("Firestore update messages failed for chat %s: %s", chat_id, str(e), exc_info=True)
                return False
        else:
            # In-Memory fallback
            try:
                if chat_id in self.memory_store:
                    self.memory_store[chat_id]["messages"] = messages
                    self.memory_store[chat_id]["updatedAt"] = now
                    return True
                logger.warning("Attempted to update messages for non-existent in-memory chat: %s", chat_id)
                return False
            except Exception as e:
                logger.error("In-memory update messages failed for chat %s: %s", chat_id, str(e), exc_info=True)
                return False

    def update_chat_settings(
        self,
        chat_id: str,
        name: Optional[str] = None,
        persona: Optional[str] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None
    ) -> bool:
        """
        Modifies general settings metadata for an existing chat session.
        """
        now = time.time()
        logger.info("Updating general settings for chat ID: %s", chat_id)
        
        updates = {"updatedAt": now}
        if name is not None:
            updates["name"] = name
        if persona is not None:
            updates["persona"] = persona
        if temperature is not None:
            updates["temperature"] = temperature
        if model is not None:
            updates["model"] = model

        if self.db:
            try:
                # Firestore
                self.db.collection("chats").document(chat_id).update(updates)
                return True
            except Exception as e:
                logger.error("Firestore update settings failed for chat %s: %s", chat_id, str(e), exc_info=True)
                return False
        else:
            # In-Memory fallback
            try:
                if chat_id in self.memory_store:
                    self.memory_store[chat_id]["updatedAt"] = now
                    if name is not None:
                        self.memory_store[chat_id]["name"] = name
                    if persona is not None:
                        self.memory_store[chat_id]["persona"] = persona
                    if temperature is not None:
                        self.memory_store[chat_id]["temperature"] = temperature
                    if model is not None:
                        self.memory_store[chat_id]["model"] = model
                    return True
                logger.warning("Attempted to update settings for non-existent in-memory chat: %s", chat_id)
                return False
            except Exception as e:
                logger.error("In-memory update settings failed for chat %s: %s", chat_id, str(e), exc_info=True)
                return False

    def delete_chat(self, chat_id: str) -> bool:
        """
        Deletes a chat session permanently.
        """
        logger.info("Permanently deleting chat session ID: %s", chat_id)
        if self.db:
            try:
                # Firestore
                self.db.collection("chats").document(chat_id).delete()
                return True
            except Exception as e:
                logger.error("Firestore delete failed for chat %s: %s", chat_id, str(e), exc_info=True)
                return False
        else:
            # In-Memory fallback
            try:
                if chat_id in self.memory_store:
                    del self.memory_store[chat_id]
                    return True
                logger.warning("Attempted to delete non-existent in-memory chat: %s", chat_id)
                return False
            except Exception as e:
                logger.error("In-memory delete failed for chat %s: %s", chat_id, str(e), exc_info=True)
                return False

# Export instantiated storage client
chat_store = ChatStore()
