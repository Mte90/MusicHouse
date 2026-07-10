"""AI Suggestions tab for MusicHouse."""

from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QTextEdit, QComboBox, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer

from musichouse import log_setup as logging
from musichouse.ai_client import AIClient
from musichouse.error_handling import (
    APIKeyError,
    APITimeoutError,
    APIParseError,
    APIConnectionError
)
from musichouse.ui.ai_worker import AIWorker

logger = logging.get_logger(__name__)


class AITab(QWidget):
    """Tab for AI artist suggestions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._ai_client = AIClient()
        self._artists_loaded = False
        self._all_artists = []  # Store all artists for filtering
        self._worker: Optional[AIWorker] = None
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._refresh_artist_combo)
        self._empty_label: Optional[QLabel] = None
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
        self._search_input.textChanged.connect(self._on_search_changed)
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

        # Cancel button
        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.clicked.connect(self._cancel_request)
        self._cancel_button.setEnabled(False)
        self._layout.addWidget(self._cancel_button)

        # Results display
        self._suggestions_display = QTextEdit()
        self._suggestions_display.setReadOnly(True)
        self._suggestions_display.setPlaceholderText("Select an artist and click 'Get Similar Artists'")
        self._layout.addWidget(self._suggestions_display)

        # Genre label
        self._genre_label = QLabel("Genres: None")
        self._genre_label.setStyleSheet("font-style: italic;")
        self._layout.addWidget(self._genre_label)
        
        # Empty state label
        self._empty_label = QLabel("No AI suggestions yet. Click 'Generate Suggestions'.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: gray; font-style: italic;")
        self._empty_label.setVisible(False)
        self._layout.addWidget(self._empty_label)

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
    
    def _on_search_changed(self, text: str):
        """Handle search input change with debounce."""
        self._search_timer.stop()
        self._search_timer.start(150)  # 150ms debounce

    def _refresh_artist_combo(self):
        """Refresh artist combo box (called after debounce)."""
        search_text = self._search_input.text().lower()
        search_text = search_text.strip()
        
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
        
        # Update empty state based on whether any artists are available
        self._update_empty_state(len(filtered) == 0)
    
    def _update_empty_state(self, has_data: bool) -> None:
        """Show/hide empty state label."""
        if self._empty_label:
            self._empty_label.setVisible(not has_data)

    def refresh_ai_client(self) -> None:
        """Recreate AIClient with fresh config from settings."""
        logger.info("Refreshing AIClient with updated settings")
        self._ai_client = AIClient()
        logger.info(f"New client configured: endpoint={self._ai_client.endpoint}, model={self._ai_client.model}")

    def load_artists_from_db(self) -> bool:
        """Load artists from database. Return True if artists were found."""
        if self._artists_loaded:
            return True

        try:
            from musichouse import config
            from musichouse.leaderboard_cache import LeaderboardCache

            cache = LeaderboardCache(config.get_config_dir())
            artists = [row[0] for row in cache.get_all_artists()]
            cache.close()

            if artists:
                self.load_artists(artists)
                self._update_empty_state(False)
                self._artists_loaded = True
                return True
            else:
                # No artists found - don't mark as loaded, allow retry
                self._update_empty_state(True)
                return False
        except Exception as e:
            logger.error(f"Error loading artists from DB: {e}")
            self._update_empty_state(True)
            return False
    def showEvent(self, event):
        """Load artists on first show, retry if previously empty."""
        super().showEvent(event)
        if not self._artists_loaded:
            self.load_artists_from_db()  # Will retry if DB was empty

    def _get_similar_artists(self):
        """Get similar artists for selected artist using background worker."""
        artist = self._artist_combo.currentText()

        if artist == "Select an artist...":
            self._suggestions_display.setText(
                "Please select an artist first."
            )
            return

        logger.info(f"Getting suggestions for: {artist}")

        # Show loading state
        self._set_loading_state(True)

        # Create and configure worker
        self._worker = AIWorker(artist, self._ai_client)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    def _set_loading_state(self, loading: bool):
        """Set UI loading state."""
        self._get_suggestions_button.setEnabled(not loading)
        self._cancel_button.setEnabled(loading)
        self._search_input.setEnabled(not loading)
        self._artist_combo.setEnabled(not loading)
        
        if loading:
            self._suggestions_display.setText("Loading...")
            self._genre_label.setText("Genres: Loading...")

    def _on_worker_progress(self, message: str):
        """Handle progress update from worker."""
        logger.info(f"Worker progress: {message}")
        # Update suggestions display with progress
        current = self._suggestions_display.toPlainText()
        if current == "Loading...":
            self._suggestions_display.setText(message)
        else:
            self._suggestions_display.append(message)

    def _on_worker_finished(self, result: str):
        """Handle worker completion."""
        logger.info("Worker completed successfully")
        self._set_loading_state(False)
        
        # Parse result to separate suggestions and genres
        lines = result.split("\n\n")
        if len(lines) >= 2:
            suggestions = lines[0]
            genres_line = lines[1]  # e.g., "Genres: Rock, Pop"
            
            self._suggestions_display.setText(suggestions)
            if genres_line.startswith("Genres: "):
                genres = genres_line[8:]  # Remove "Genres: " prefix
                self._genre_label.setText(f"Genres: {genres}")
        else:
            self._suggestions_display.setText(result)

    def _on_worker_error(self, error_msg: str):
        """Handle worker error."""
        # Map error messages to user-friendly messages
        if "API key not configured" in error_msg or "APIKeyError" in error_msg:
            user_msg = "API key not set. Open Settings to configure."
        elif "timed out" in error_msg.lower() or "APITimeoutError" in error_msg:
            user_msg = "Request timed out. Try again."
        elif "cannot connect" in error_msg.lower() or "Network error" in error_msg or "APIConnectionError" in error_msg:
            user_msg = "Cannot connect to API. Check your endpoint."
        elif "Failed to parse" in error_msg or "APIParseError" in error_msg:
            user_msg = "Invalid response from AI service. Try again."
        else:
            user_msg = f"Error: {error_msg}"
        
        logger.error(f"Worker error: {error_msg}")
        self._set_loading_state(False)
        self._suggestions_display.setText(user_msg)
        self._genre_label.setText("Genres: Error")

    def _cancel_request(self):
        """Cancel the current worker request."""
        if self._worker:
            logger.info("Cancelling worker request")
            self._worker.stop()
            self._set_loading_state(False)
            self._suggestions_display.append("Request cancelled.")
