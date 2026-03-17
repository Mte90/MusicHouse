"""AI Suggestions tab for MusicHouse."""

from typing import List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QTextEdit, QComboBox, QLineEdit
)
from PyQt6.QtCore import Qt

from musichouse import logging
from musichouse.ai_client import AIClient

logger = logging.get_logger(__name__)


class AITab(QWidget):
    """Tab for AI artist suggestions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._ai_client = AIClient()
        self._artists_loaded = False
        self._all_artists = []  # Store all artists for filtering
        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI components."""
        # Artist selection with search
        self._layout.addWidget(
            QLabel("Select an artist to get suggestions:")
        )
        
        # Search box
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search artists...")
        self._search_input.textChanged.connect(self._filter_artists)
        self._layout.addWidget(self._search_input)
        
        self._artist_combo = QComboBox()
        self._artist_combo.addItem("Select an artist...")
        self._artist_combo.setMaxVisibleItems(15)  # Show 15 items in dropdown
        self._layout.addWidget(self._artist_combo)

        self._artist_count_label = QLabel("0 artists available")
        self._artist_count_label.setStyleSheet("font-size: 10px; color: #666;")
        self._layout.addWidget(self._artist_count_label)

        # Get suggestions button
        self._get_suggestions_button = QPushButton("Get Similar Artists")
        self._get_suggestions_button.clicked.connect(self._get_similar_artists)
        self._layout.addWidget(self._get_suggestions_button)

        # Results display
        self._suggestions_display = QTextEdit()
        self._suggestions_display.setReadOnly(True)
        self._suggestions_display.setPlaceholderText("Select an artist and click 'Get Similar Artists'")
        self._layout.addWidget(self._suggestions_display)

        # Genre label
        self._genre_label = QLabel("Genres: None")
        self._genre_label.setStyleSheet("font-style: italic;")
        self._layout.addWidget(self._genre_label)

    def load_artists(self, artists: List[str]):
        """Populate the artist dropdown (sorted alphabetically)."""
        # Store all artists for filtering
        self._all_artists = sorted(artists)
        
        self._artist_combo.clear()
        self._artist_combo.addItem("Select an artist...")
        
        for artist in self._all_artists:
            self._artist_combo.addItem(artist)
        
        self._artist_count_label.setText(f"{len(artists)} artists available")
        self._artists_loaded = True
    
    def _filter_artists(self, search_text: str):
        """Filter artist dropdown based on search text."""
        search_text = search_text.lower().strip()
        
        if not search_text:
            # Show all artists
            filtered = self._all_artists
        else:
            # Filter artists that contain the search text
            filtered = [a for a in self._all_artists if search_text in a.lower()]
        
        # Update combo box
        current_selection = self._artist_combo.currentText()
        self._artist_combo.clear()
        self._artist_combo.addItem("Select an artist...")
        
        for artist in filtered:
            self._artist_combo.addItem(artist)
        
        # Update count label
        self._artist_count_label.setText(f"{len(filtered)} artists found")

    def load_artists_from_db(self):
        """Load artists from database on first visit."""
        if self._artists_loaded:
            return

        try:
            from musichouse import config
            from musichouse.leaderboard_cache import LeaderboardCache

            cache = LeaderboardCache(config.get_config_dir())
            artists = [row[0] for row in cache.get_all_artists()]
            cache.close()

            if artists:
                self.load_artists(artists)
            else:
                # Empty list - still mark as loaded so we don't keep trying
                self._artists_loaded = True
        except Exception as e:
            logger.error(f"Error loading artists from DB: {e}")
    def showEvent(self, event):
        """Load artists on first show."""
        super().showEvent(event)
        if not self._artists_loaded:
            self.load_artists_from_db()

    def _get_similar_artists(self):
        """Get similar artists for selected artist."""
        artist = self._artist_combo.currentText()

        if artist == "Select an artist...":
            self._suggestions_display.setText(
                "Please select an artist first."
            )
            return

        logger.info(f"Getting suggestions for: {artist}")

        self._suggestions_display.setText("Loading...")
        self._genre_label.setText("Genres: Loading...")

        try:
            similar = self._ai_client.get_similar_artists(artist)
            genres = self._ai_client.get_artist_genres(artist)

            if similar:
                self._suggestions_display.setText("\n".join(f"• {a}" for a in similar))
            else:
                self._suggestions_display.setText("No similar artists found.")

            if genres:
                self._genre_label.setText(f"Genres: {', '.join(genres)}")
            else:
                self._genre_label.setText("Genres: Unknown")

        except Exception as e:
            logger.error(f"Error getting suggestions: {e}")
            self._suggestions_display.setText(f"Error: {e}")
            self._genre_label.setText("Genres: Error")
