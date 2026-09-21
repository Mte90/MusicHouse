"""Worker thread for batch artist suggestions."""

from PyQt6.QtCore import QThread, pyqtSignal

from musichouse import log_setup as logging

logger = logging.get_logger(__name__)


class SuggestWorker(QThread):
    """Worker thread for batch AI artist suggestions.
    
    Runs multiple seed artists sequentially, calling the AI client for each.
    Emits progress, results, and errors as signals.
    
    Signals:
        progress: Emitted with current seed name before each request
        seed_result: Emitted with (seed, list of {"artist", "reason"} dicts) on success
        error: Emitted with (seed, error_message) on failure for a seed
        finished: Emitted when all seeds processed or stopped
    """
    
    progress = pyqtSignal(str)
    seed_result = pyqtSignal(str, list)
    error = pyqtSignal(str, str)
    finished = pyqtSignal()
    
    def __init__(self, seeds: list[str], ai_client):
        super().__init__()
        self._seeds = seeds
        self._ai_client = ai_client
        self._stop = False
    
    def run(self):
        """Execute batch suggestions in background thread."""
        try:
            for seed in self._seeds:
                if self._stop:
                    logger.info(f"Stop requested, stopping after {seed}")
                    break
                
                self.progress.emit(seed)
                
                try:
                    suggestions = self._ai_client.get_similar_artists_json(seed)
                    self.seed_result.emit(seed, suggestions)
                except Exception as e:  # noqa: BLE001
                    error_msg = str(e)
                    logger.error(f"Error getting suggestions for {seed}: {error_msg}")
                    self.error.emit(seed, error_msg)
            
            self.finished.emit()
            
        except Exception as e:  # noqa: BLE001
            logger.error(f"Unexpected error in SuggestWorker: {e}")
            self.error.emit("__worker__", str(e))
            self.finished.emit()
    
    def stop(self):
        """Stop the worker gracefully."""
        self._stop = True
        self.quit()