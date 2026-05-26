import logging
import sys
from pathlib import Path

# Common log format
formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def setup_console_logger(name: str = "pingu.app") -> logging.Logger:
    """Console-only logger for terminal logging (app/UI flow)."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if logger.handlers:
        logger.handlers.clear()
        
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    logger.propagate = False
    return logger
 
def setup_file_logger(name: str = "pingu.backend", filename: str = "pingu.log") -> logging.Logger:
    """File-only logger for backend API/service traces to keep console clean."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if logger.handlers:
        logger.handlers.clear()
        
    root_dir = Path(__file__).resolve().parent.parent
    log_file_path = root_dir / filename
    
    try:
        file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # Fallback to stderr if file path is unwritable
        console_fallback = logging.StreamHandler(sys.stderr)
        console_fallback.setFormatter(formatter)
        logger.addHandler(console_fallback)
        logger.warning(f"Failed to initialize file logging, using fallback: {e}")
        
    logger.propagate = False
    return logger

app_logger = setup_console_logger("pingu.app")
backend_logger = setup_file_logger("pingu.backend", "pingu.log")



