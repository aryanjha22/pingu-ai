import json
import threading
from backend import config
from backend.services.chat_store import chat_store
from backend.services.llm import client
from google.genai import types
from backend.logger import backend_logger as logger

def _bg_summarize_and_update(chat_id: str, to_summarize: list, current_summary: str):
    """Background target to generate summary and update database."""
    try:
        new_summary = generate_running_summary(to_summarize, current_summary)
        chat_store.update_chat_settings(chat_id, summary=new_summary)
        logger.info("Background summarization completed and saved for chat %s", chat_id)
    except Exception as e:
        logger.error("Error in background summarization thread for chat %s: %s", chat_id, str(e), exc_info=True)

def generate_running_summary(old_messages: list, current_summary: str = "") -> str:
    """
    Summarizes a chunk of conversation history and integrates it into a running summary
    using the Gemini API.
    """
    logger.info("Generating running summary for %d old messages...", len(old_messages))
    
    # Format the old messages into a legible transcript
    transcript = []
    for msg in old_messages:
        role = "User" if msg.get("role") == "user" else "Assistant"
        transcript.append(f"{role}: {msg.get('content', '')}")
    transcript_text = "\n".join(transcript)

    # Prompt construction
    prompt = (
        f"You are Pingu AI's memory manager. Update the running conversation summary by integrating the latest messages.\n\n"
        f"Current Running Summary:\n"
        f"{current_summary if current_summary else '(No existing summary)'}\n\n"
        f"New Messages to Incorporate:\n"
        f"{transcript_text}\n\n"
        f"Write an updated running summary that details the key topics discussed, requests made, preferences, decisions, and system information. "
        f"Ensure the entire updated summary is strictly under 250 words (1200 characters) to remain compact and clean. "
        f"Output ONLY the raw updated summary."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite", # Ultra-fast model for background administrative summarization
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                system_instruction=(
                    "You are a precise, objective background summarization assistant. "
                    "Keep summaries highly factual, compact, and strictly under 250 words."
                )
            )
        )
        new_summary = response.text.strip() if response.text else ""
        logger.info("Successfully updated running summary: %r", new_summary[:150] + "...")
        return new_summary
    except Exception as e:
        logger.error("Failed to generate running summary using Gemini API: %s", str(e), exc_info=True)
        # Return existing summary if summarization fails so we don't lose past memories
        return current_summary

def manage_chat_memory(chat_id: str, messages: list) -> tuple[list, str]:
    """
    Evaluates conversation length. If it exceeds CHAT_SUMMARIZE_THRESHOLD,
    instantly trims active history down to CHAT_WINDOW_SIZE and triggers background
    summarization to prevent WebSocket timeout and latency.
    """
    # Retrieve current chat details
    chat = chat_store.get_chat(chat_id)
    if not chat:
        logger.warning("Attempted to manage memory for non-existent chat: %s", chat_id)
        return messages, ""

    current_summary = chat.get("summary", "")

    # Check if history exceeds threshold
    if len(messages) > config.CHAT_SUMMARIZE_THRESHOLD:
        logger.info(
            "Chat ID %s history length (%d) exceeds threshold (%d). Trimming active history and dispatching background summarization...",
            chat_id, len(messages), config.CHAT_SUMMARIZE_THRESHOLD
        )
        
        # Split history: slice from start up to window size from the end
        to_summarize = messages[:-config.CHAT_WINDOW_SIZE]
        active_window = messages[-config.CHAT_WINDOW_SIZE:]

        # Persist updated trimmed history immediately so client/server stay in sync
        chat_store.update_chat_messages(chat_id, active_window)

        # Dispatch background thread for Gemini summarization to keep the websocket streaming immediate
        thread = threading.Thread(
            target=_bg_summarize_and_update,
            args=(chat_id, to_summarize, current_summary),
            daemon=True
        )
        thread.start()

        return active_window, current_summary

    return messages, current_summary
