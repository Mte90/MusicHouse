"""QThread worker for applying file moves and folder renames."""

import os
import shutil
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from musichouse import log_setup as logging

logger = logging.get_logger(__name__)


class ApplyWorker(QThread):
    """Worker thread that applies file moves and folder renames.

    Processes a list of actions (move or rename) suggested by the AI folder
    organization feature. Emits per-action results and a final count signal.
    """

    file_applied = pyqtSignal(str, bool, str)  # (path, success, error_message)
    apply_finished = pyqtSignal(int)  # (count of successfully applied actions)
    error = pyqtSignal(str)  # (error_message)

    def __init__(self, actions: list[dict], parent=None):
        """Initialize the worker.

        Args:
            actions: List of action dicts with keys:
                - "type": "move" or "rename"
                - "from": source path (str)
                - "to": destination path (str)
            parent: Parent QObject.
        """
        super().__init__(parent)
        self._actions = actions
        self._stop_flag = False
        self._applied_count = 0

    def stop(self):
        """Request stop of the worker. Called from GUI thread."""
        self._stop_flag = True

    def _apply_move(self, src: str, dst: str) -> tuple[bool, str]:
        """Apply a move action, returning (success, error_message).

        Creates destination directory if needed, then moves the file.
        """
        try:
            # Create destination directory if it doesn't exist
            dst_dir = os.path.dirname(dst)
            if dst_dir and not os.path.exists(dst_dir):
                os.makedirs(dst_dir, exist_ok=True)
                logger.info(f"Created destination directory: {dst_dir}")

            shutil.move(src, dst)
            logger.info(f"Moved: {Path(src).name} -> {Path(dst).name}")
            return True, ""
        except Exception as e:
            logger.error(f"Failed to move {Path(src).name}: {e}")
            return False, str(e)

    def _apply_rename(self, src: str, dst: str) -> tuple[bool, str]:
        """Apply a rename action, returning (success, error_message).

        Renames a file or directory. Parent directory of dst must exist.
        """
        try:
            Path(src).rename(dst)
            logger.info(f"Renamed: {Path(src).name} -> {Path(dst).name}")
            return True, ""
        except Exception as e:
            logger.error(f"Failed to rename {Path(src).name}: {e}")
            return False, str(e)

    def run(self):
        """Apply each action in the list.

        Checks stop flag between actions. Emits file_applied per action.
        Emits apply_finished with success count at the end.
        """
        for action in self._actions:
            if self._stop_flag:
                logger.info("ApplyWorker stopped by user")
                break

            action_type = action.get("type")
            src = action.get("from")
            dst = action.get("to")

            if not src or not dst:
                logger.warning(f"Invalid action (missing src or dst): {action}")
                self.file_applied.emit(src or dst or "", False, "Invalid action: missing src or dst")
                continue

            # Guard: check source existence before attempting operation
            if not os.path.exists(src):
                self.file_applied.emit(src, False, "Source not found")
                logger.warning(f"Source not found, skipping: {Path(src).name}")
                continue

            if action_type == "move":
                success, error_msg = self._apply_move(src, dst)
            elif action_type == "rename":
                success, error_msg = self._apply_rename(src, dst)
            else:
                logger.warning(f"Unknown action type: {action_type}")
                self.file_applied.emit(src, False, f"Unknown action type: {action_type}")
                continue

            if success:
                self._applied_count += 1
                self.file_applied.emit(src, True, "")
            else:
                self.file_applied.emit(src, False, error_msg)

        self.apply_finished.emit(self._applied_count)
        logger.info(f"ApplyWorker completed: {self._applied_count} actions applied")