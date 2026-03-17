"""Tag writer and preview module for MusicHouse."""

from pathlib import Path
from typing import Dict, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QPushButton, QHBoxLayout, QHeaderView
)
from PyQt6.QtGui import QColor

import eyed3

from musichouse import logging
from musichouse.utils import load_mp3_safely

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
    """Write ID3 tags to an MP3 file.

    Args:
        file_path: Path to the MP3 file.
        artist: Artist name.
        title: Track title.
        genre: Genre (optional).
        force: If True, overwrite existing tags without checking.

    Returns:
        True if successful, False otherwise.
    """
    try:
        audiofile = load_mp3_safely(file_path)
        if audiofile is None:
            logger.error(f"Could not load MP3 file: {file_path}")
            return False

        if audiofile.tag is None:
            audiofile.initTag()

        # Check if tags already exist
        if not force and audiofile.tag.artist and audiofile.tag.title:
            logger.warning(f"Tags already exist for {file_path.name} (skipping)")
            return False

        # Update tags
        audiofile.tag.artist = artist
        audiofile.tag.title = title
        if genre:
            audiofile.tag.genre = genre

        audiofile.tag.save()
        logger.info(f"Tags written to {file_path.name}")
        return True

    except Exception as e:
        logger.error(f"Error writing tags to {file_path}: {e}")
        return False
