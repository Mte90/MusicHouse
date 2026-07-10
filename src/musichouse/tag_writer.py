"""Tag writer and preview module for MusicHouse."""

import shutil
from pathlib import Path
from typing import Dict, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QPushButton, QHBoxLayout, QHeaderView
)
from PyQt6.QtGui import QColor

import eyed3

from musichouse import log_setup as logging
from musichouse.utils import load_mp3_safely
from musichouse.error_handling import (
    CorruptedFileError, FileLockedError, ReadOnlyFileError, TagWriteError
)

logger = logging.get_logger(__name__)


class TagPreviewDialog(QDialog):
    """Dialog to preview and confirm tag changes."""

    def __init__(self, file_path: Path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setWindowTitle(f"Preview: {file_path.name}")
        self.setMinimumWidth(500)
        self._old_tags: Dict[str, str] = {}
        self._new_tags: Dict[str, str] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # File info
        file_label = QLabel(f"File: {self.file_path.name}")
        file_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(file_label)

        # Table for tag comparison
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Tag", "Old Value", "New Value"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._table)

        # Buttons
        button_layout = QHBoxLayout()
        self._apply_button = QPushButton("Apply")
        self._skip_button = QPushButton("Skip")

        self._apply_button.clicked.connect(self.accept)
        self._skip_button.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(self._apply_button)
        button_layout.addWidget(self._skip_button)
        layout.addLayout(button_layout)

    def set_old_tags(self, artist: str, title: str, genre: Optional[str] = None):
        self._old_tags = {
            "Artist": artist,
            "Title": title,
            "Genre": genre or ""
        }

    def set_new_tags(self, artist: str, title: str, genre: Optional[str] = None):
        self._new_tags = {
            "Artist": artist,
            "Title": title,
            "Genre": genre or ""
        }

    def populate_table(self):
        self._table.setRowCount(0)
        all_keys = set(self._old_tags.keys()) | set(self._new_tags.keys())

        for key in all_keys:
            row = self._table.rowCount()
            self._table.insertRow(row)

            self._table.setItem(row, 0, QTableWidgetItem(key))
            self._table.setItem(
                row, 1, 
                QTableWidgetItem(self._old_tags.get(key, ""))
            )
            self._table.setItem(
                row, 2, 
                QTableWidgetItem(self._new_tags.get(key, ""))
            )

            # Highlight changed values
            if self._old_tags.get(key) != self._new_tags.get(key):
                self._table.item(row, 1).setBackground(QColor(255, 200, 200))
                self._table.item(row, 2).setBackground(QColor(200, 255, 200))

    def get_approval(self) -> bool:
        return self.exec() == QDialog.DialogCode.Accepted

    def get_new_tags(self) -> Dict[str, str]:
        return self._new_tags.copy()


def write_tags(
    file_path: Path,
    artist: str,
    title: str,
    genre: Optional[str] = None,
    force: bool = False,
) -> bool:
    """Write ID3 tags to an MP3 file with crash recovery support.

    Before saving, creates a backup (.bak). If save fails, restores from backup.
    Deletes backup on success.

    Args:
        file_path: Path to the MP3 file.
        artist: Artist name.
        title: Track title.
        genre: Genre (optional).
        force: If True, overwrite existing tags without checking.

    Returns:
        True if successful, False otherwise.

    Raises:
        FileNotFoundError: If file doesn't exist before loading.
        CorruptedFileError: If file cannot be loaded as MP3.
        FileLockedError: If file is locked by another process.
        ReadOnlyFileError: If file is read-only.
        TagWriteError: If tag writing fails for other reasons.
    """
    # T41: Check file exists before loading
    if not file_path.exists():
        logger.error(f"File no longer exists: {file_path}")
        raise FileNotFoundError(f"File no longer exists: {file_path}")

    backup_path = file_path.with_suffix(".bak")
    
    try:
        # T37: Create backup before modification
        logger.debug(f"Creating backup: {backup_path}")
        shutil.copy2(file_path, backup_path)

        audiofile = load_mp3_safely(file_path)
        if audiofile is None:
            # T40: This is a corrupted file
            raise CorruptedFileError(str(file_path), "Failed to load MP3 data")

        if audiofile.tag is None:
            audiofile.initTag()

        # Check if tags already exist
        if not force and audiofile.tag.artist and audiofile.tag.title:
            logger.warning(f"Tags already exist for {file_path.name} (skipping)")
            return True  # Backup will be cleaned up on success

        # Update tags
        audiofile.tag.artist = artist
        audiofile.tag.title = title
        if genre:
            audiofile.tag.genre = genre

        # T42/T43: Save with specific error handling
        try:
            audiofile.tag.save()
        except PermissionError as e:
            # T43: Read-only file (EACCES)
            logger.error(f"Permission denied writing to {file_path}: {e}")
            raise ReadOnlyFileError(str(file_path)) from e
        except OSError as e:
            # T42: File locked or other OS error
            logger.error(f"OS error writing to {file_path}: {e}")
            if "lock" in str(e).lower() or e.errno == 11:  # EAGAIN/EWOULDBLOCK
                raise FileLockedError(str(file_path)) from e
            raise TagWriteError(f"OS error writing {file_path}: {e}") from e

        logger.info(f"Tags written to {file_path.name}")
        return True

    except (CorruptedFileError, FileLockedError, ReadOnlyFileError, FileNotFoundError):
        # Re-raise these specific errors
        raise
    except TagWriteError:
        # Re-raise TagWriteError
        raise
    except Exception as e:
        # T37: Restore from backup on any error
        logger.error(f"Error writing tags to {file_path}: {e}, restoring from backup")
        if backup_path.exists():
            try:
                shutil.copy2(backup_path, file_path)
                logger.info(f"Restored {file_path} from backup")
            except Exception as restore_error:
                logger.error(f"Failed to restore from backup: {restore_error}")
        raise TagWriteError(f"Failed to write tags to {file_path}: {e}") from e
    finally:
        # T37: Clean up backup on success or if we have a specific error
        if backup_path.exists():
            try:
                backup_path.unlink()
                logger.debug(f"Removed backup: {backup_path}")
            except Exception as e:
                logger.warning(f"Failed to remove backup {backup_path}: {e}")
