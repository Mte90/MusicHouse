"""Error handling utilities for MusicHouse."""

from musichouse import logging

logger = logging.get_logger(__name__)


class MusicHouseError(Exception):
    """Base exception for MusicHouse."""
    pass


class DatabaseError(MusicHouseError):
    """Database-related error."""
    pass


class ScanError(MusicHouseError):
    """Scanning-related error."""
    pass


class TagWriteError(MusicHouseError):
    """Tag writing error."""
    pass
