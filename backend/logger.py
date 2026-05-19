import logging
import sys
from pathlib import Path

# Common log formatter
formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def setup_console_logger(name: str = "pingu.app") -> logging.Logger:
    """
    Logger that strictly prints to standard error (console).
    Used by app.py to display clean UI/flow logs in the terminal.
    """
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
    """
    Logger that strictly writes to a dedicated log file in the project root.
    Used by llm.py to keep backend API logs isolated from the terminal console.
    """
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
        # Fallback to console stderr if writing to file fails
        console_fallback = logging.StreamHandler(sys.stderr)
        console_fallback.setFormatter(formatter)
        logger.addHandler(console_fallback)
        logger.warning(f"Failed to initialize file logging, using fallback: {e}")
        
    logger.propagate = False
    return logger

# Export pre-configured loggers
app_logger = setup_console_logger("pingu.app")
backend_logger = setup_file_logger("pingu.backend", "pingu.log")



