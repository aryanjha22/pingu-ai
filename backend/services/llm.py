import os
import time
from typing import Optional
from google import genai
from google.genai import types
from backend import config
from backend.logger import backend_logger as logger

# Initialize Gemini Client
client = genai.Client()

def stream_chat_response(
    messages: list,
    persona: str = "default",
    temperature: float = 0.7,
    model: Optional[str] = None,
    summary: str = ""
):
    """
    Streams responses from the Gemini API using system instructions and configuration.

    Args:
        messages (list): List of messages in Streamlit format: [{'role': 'user'|'assistant', 'content': '...'}]
        persona (str): Key of the system prompt to use
        temperature (float): Controls creativity (0.0 to 2.0)
        model (str): Gemini model identifier
        summary (str): Optional running summary of older messages

    Yields:
        str: Response text chunks
    """
    active_model = model or config.DEFAULT_MODEL
    logger.info("Initializing chat stream. Model: %s | Temp: %s | Persona: %s", active_model, temperature, persona)
    
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

    # Retrieve the system instruction securely from configuration prompts mapping
    system_instruction = config.SYSTEM_PROMPTS.get(persona, config.SYSTEM_PROMPTS["default"])
    if summary:
        system_instruction += f"\n\n[SUMMARY OF OLDER MESSAGES IN THIS CHAT]\n{summary}\n[END OF SUMMARY]"

    config_params = types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system_instruction
    )

    start_time = time.time()
    first_token_time = None
    chunks_count = 0
    total_chars = 0

    try:
        response = client.models.generate_content_stream(
            model=active_model,
            contents=contents,
            config=config_params
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
