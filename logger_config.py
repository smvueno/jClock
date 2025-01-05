import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging(log_file: Path, level=logging.INFO):
    """Configure logging to file in script directory"""
    try:
        # Ensure the log directory exists
        log_dir = log_file.parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create rotating file handler
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=1024*1024,  # 1MB
            backupCount=5,
            encoding='utf-8'  # Add explicit encoding
        )
        
        # Configure root logger
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                file_handler,
                logging.StreamHandler()
            ]
        )
        
        # Suppress some noisy loggers
        logging.getLogger('asyncio').setLevel(logging.WARNING)
        logging.getLogger('PIL').setLevel(logging.WARNING)
        logging.getLogger('PySide6').setLevel(logging.WARNING)
        
        return logging.getLogger('FloatingClock')
        
    except Exception as e:
        print(f"Error setting up logging: {e}")
        raise

def get_logger(name: str):
    """Get a logger with the specified name"""
    return logging.getLogger(name)
