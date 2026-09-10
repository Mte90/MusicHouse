"""QThread worker for deleting MP3 files in batches."""

import os
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from musichouse import log_setup as logging

logger = logging.get_logger(__name__)


class DeleteWorker(QThread):
    """Worker thread that deletes a list of MP3 files.

    Tries send2trash first (if installed), falls back to permanent delete.
    Emits per-file results and a final count signal.
    """

    file_deleted = pyqtSignal(str, bool, str)  # (path, success, error_message)
    deletion_finished = pyqtSignal(int)  # (count of successfully deleted files)
    error = pyqtSignal(str)  # (error_message)

    def __init__(self, paths: list[str], parent=None):
        """Initialize the worker.

        Args:
            paths: List of file paths to delete.
            parent: Parent QObject.
        """
        super().__init__(parent)
        self._paths = paths
        self._stop_flag = False
        self._deleted_count = 0

    def stop(self):
        """Request stop of the worker. Called from GUI thread."""
        self._stop_flag = True

    def _try_delete(self, path_str: str, path: Path) -> tuple[bool, str]:
        """Try to delete a file, returning (success, error_message).

        Tries send2trash first, falls back to os.remove.
        """
        # Try send2trash first
        send2trash_func: callable | None
        try:
            from send2trash import send2trash as send2trash_func
        except ImportError:
            send2trash_func = None

        if send2trash_func is not None:
            try:
                send2trash_func(path_str)
                logger.info(f"Moved to trash: {path.name}")
                return True, ""
            except Exception as e:  # noqa: BLE001
                logger.warning(f"send2trash failed for {path.name}: {e}")
                # Fall through to os.remove

        # Fallback to permanent delete
        try:
            os.remove(path)
            logger.info(f"Permanently deleted: {path.name}")
            return True, ""
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to delete {path.name}: {e}")
            return False, str(e)

    def run(self):
        """Delete each file in the list.

        Checks stop flag between files. Emits file_deleted per file.
        Emits deletion_finished with success count at the end.
        """
        for path_str in self._paths:
            if self._stop_flag:
                logger.info("DeleteWorker stopped by user")
                break

            path = Path(path_str)

            # Guard: check file existence before attempting delete
            if not os.path.exists(path):
                self.file_deleted.emit(path_str, False, "File not found")
                logger.warning(f"File not found, skipping: {path.name}")
                continue

            success, error_msg = self._try_delete(path_str, path)

            if success:
                self._deleted_count += 1
                self.file_deleted.emit(path_str, True, "")
            else:
                self.file_deleted.emit(path_str, False, error_msg)

        self.deletion_finished.emit(self._deleted_count)
        logger.info(f"DeleteWorker completed: {self._deleted_count} files deleted")