"""Error handling utilities for MusicHouse."""

from musichouse import log_setup as logging

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


class CorruptedFileError(MusicHouseError):
    """Corrupted MP3 file error."""
    def __init__(self, file_path: str, reason: str = "File is corrupted"):
        self.file_path = file_path
        self.reason = reason
        super().__init__(f"Corrupted file: {file_path} - {reason}")


class FileLockedError(MusicHouseError):
    """File is locked by another process."""
    def __init__(self, file_path: str, suggestion: str = "Close any application using this file"):
        self.file_path = file_path
        self.suggestion = suggestion
        super().__init__(f"File locked: {file_path} - {suggestion}")


class ReadOnlyFileError(MusicHouseError):
    """File is read-only."""
    def __init__(self, file_path: str, suggestion: str = "Check file permissions"):
        self.file_path = file_path
        self.suggestion = suggestion
        super().__init__(f"Read-only file: {file_path} - {suggestion}")


class APIError(MusicHouseError):
    """Base exception for AI API errors."""
    pass


class APIKeyError(APIError):
    """API key not configured or invalid."""
    pass


class APITimeoutError(APIError):
    """API request timed out."""
    pass


class APIParseError(APIError):
    """Failed to parse API response."""
    pass


class APIConnectionError(APIError):
    """Failed to connect to API server."""
    pass
