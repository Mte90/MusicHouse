"""Logging configuration for MusicHouse."""

import logging
import sys


def configure_third_party_loggers():
    """Configure log levels for third-party libraries to reduce noise."""
    logging.getLogger("eyed3").setLevel(logging.ERROR)


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger instance.
    
    Args:
        name: Logger name. If None, returns root logger.
        
    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name or "musichouse")
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    
    return logger
