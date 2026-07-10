"""AI worker thread for off-GUI-thread API calls."""

from PyQt6.QtCore import QThread, pyqtSignal, QObject
from musichouse.ai_client import AIClient
from musichouse import log_setup as logging

logger = logging.get_logger(__name__)


class AIWorker(QThread):
    """Worker thread for AI API calls.
    
    Signals:
        finished: Emitted when work completes with result string
        progress: Emitted with progress messages
        error: Emitted when an error occurs
    """
    
    finished = pyqtSignal(str)
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, artist: str, ai_client: AIClient):
        super().__init__()
        self._artist = artist
        self._ai_client = ai_client
        self._stop = False
    
    def run(self):
        """Execute AI calls in background thread."""
        try:
            self.progress.emit("Fetching similar artists...")
            
            # First call: get similar artists
            similar = self._ai_client.get_similar_artists(self._artist)
            
            if self._stop:
                return
            
            self.progress.emit("Fetching artist genres...")
            
            # Second call: get genres
            genres = self._ai_client.get_artist_genres(self._artist)
            
            if self._stop:
                return
            
            # Format results
            similar_str = "\n".join(f"• {a}" for a in similar) if similar else "No similar artists found."
            genres_str = ", ".join(genres) if genres else "Unknown"
            
            result = f"{similar_str}\n\nGenres: {genres_str}"
            self.finished.emit(result)
            
        except Exception as e:
            logger.error(f"Error in AI worker: {e}")
            self.error.emit(str(e))
    
    def stop(self):
        """Stop the worker gracefully."""
        self._stop = True
        self.quit()
