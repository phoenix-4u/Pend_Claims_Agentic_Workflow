"""Logging configuration for the application."""
import sys
from pathlib import Path
from loguru import logger
from .settings import settings


def configure_logging():
    """Configure application logging."""
    # Remove default handler
    logger.remove()
    
    # Console logging
    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        format=settings.LOG_FORMAT,
        colorize=True,
        backtrace=True,
        diagnose=settings.DEBUG,
    )
    
    # File logging
    log_file = settings.LOGS_DIR / "pend_claim_analysis.log"
    logger.add(
        log_file,
        rotation="10 MB",
        retention="30 days",
        level=settings.LOG_LEVEL,
        format=settings.LOG_FORMAT,
        backtrace=True,
        diagnose=settings.DEBUG,
        enqueue=True,  # For async safety
    )
    
    logger.info(f"Logging configured. Log file: {log_file}")
    return logger


# Configure logging when module is imported
logger = configure_logging()
