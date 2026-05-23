import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from backend.logger import backend_logger as logger


load_dotenv()

# Map Gemini_API_Key to GEMINI_API_KEY for the SDK
key = os.getenv("Gemini_API_Key") or os.getenv("GEMINI_API_KEY")
if key:
    os.environ["GEMINI_API_KEY"] = key

client = genai.Client()

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

def stream_chat_response(
    messages: list,
    persona: str = "default",
    temperature: float = 0.7,
    model: str = "gemini-2.5-flash-lite"
):
    """
    Streams responses from the Gemini API.

    Args:
        messages (list): List of messages in Streamlit format: [{'role': 'user'|'assistant', 'content': '...'}]
        persona (str): Key of the system prompt to use
        temperature (float): Controls creativity (0.0 to 2.0)
        model (str): Gemini model identifier (e.g. "gemini-2.5-flash")

    Yields:
        str: Response text chunks
    """
    logger.info("Initializing chat stream. Model: %s | Temp: %s | Persona: %s", model, temperature, persona)
    
    # Convert frontend message structure to google-genai format
    # Roles in Streamlit are 'user' and 'assistant', but Gemini expects 'user' and 'model'
    contents = []
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append(
            types.Content(
                role=role,
                parts=[types.Part(text=msg["content"])]
            )
        )
    
    logger.info("Message history length: %d messages", len(messages))
    if messages:
        last_msg = messages[-1]
        preview = last_msg["content"][:100] + ("..." if len(last_msg["content"]) > 100 else "")
        logger.info("Latest message from %s: %s", last_msg["role"], repr(preview))

    # Retrieve the system instruction securely from backend prompts mapping
    system_instruction = SYSTEM_PROMPTS.get(persona, SYSTEM_PROMPTS["default"])

    config = types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system_instruction
    )

    start_time = time.time()
    first_token_time = None
    chunks_count = 0
    total_chars = 0

    try:
        response = client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=config
        )
        for chunk in response:
            if chunk.text:
                if first_token_time is None:
                    first_token_time = time.time()
                    latency = first_token_time - start_time
                    logger.info("Time to first token (latency): %.3f seconds", latency)
                
                chunks_count += 1
                total_chars += len(chunk.text)
                yield chunk.text
        
        total_time = time.time() - start_time
        logger.info(
            "Stream completed. Total time: %.3fs | Chunks: %d | Generated chars: %d",
            total_time, chunks_count, total_chars
        )
    except Exception as e:
        logger.error("Gemini API Error: %s", str(e), exc_info=True)
        yield f"Gemini API Error: {str(e)}"

