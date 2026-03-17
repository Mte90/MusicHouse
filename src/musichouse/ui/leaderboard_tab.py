"""Leaderboard tab for MusicHouse - displays top artists."""
from typing import List, Tuple

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView
)

from musichouse import logging

logger = logging.get_logger(__name__)


class LeaderboardTab(QWidget):
    """Tab for displaying artist leaderboard."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._setup_ui()
        self._load_saved_data()

    def _setup_ui(self):
        """Set up the UI components."""
        # Title
        title = QLabel("Top Artists")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self._layout.addWidget(title)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Artist", "Count"])
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)

        self._table.setColumnWidth(0, 250)  # Artist column - wider for long artist names
        self._table.setColumnWidth(2, 80)
        
        self._layout.addWidget(self._table)
        
    def _load_saved_data(self):
        """Load saved leaderboard data from database on startup."""
        try:
            from musichouse import config
            from musichouse.leaderboard_cache import LeaderboardCache
            
            cache = LeaderboardCache(config.get_config_dir())
            # Get top 50 artists from cache
            top_artists = cache.get_top_artists(50)
            cache.close()
            
            if top_artists:
                self.update_leaderboard(top_artists)
        except Exception as e:
            logger.error(f"Error loading saved leaderboard: {e}")
            # No data loaded, will be populated when scan runs

    def update_leaderboard(self, artists: List[Tuple[str, int]]):
        """Update the leaderboard with new data.

        Args:
            artists: List of (artist_name, count) tuples.
        """
        self._table.setRowCount(0)

        for artist, count in artists:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(artist))
            self._table.setItem(row, 1, QTableWidgetItem(str(count)))

        # logger.info(f"Leaderboard updated with {len(artists)} artists")  # Too verbose during scan
