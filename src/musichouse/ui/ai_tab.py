"""AI Suggestions tab for MusicHouse."""


from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from musichouse import log_setup as logging
from musichouse.ai_client import AIClient
from musichouse.ui.ai_worker import AIWorker
from musichouse.ui.artist_select_dialog import ArtistSelectDialog
from musichouse.ui.suggest_worker import SuggestWorker

logger = logging.get_logger(__name__)


class AITab(QWidget):
    """Tab for AI artist suggestions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        # Deferred: constructing AIClient() eagerly would call config.get_api_key(),
        # which hits the OS keyring and prompts the user at startup. Build it on
        # first use via _get_ai_client() instead.
        self._ai_client: AIClient | None = None
        self._artists_loaded = False
        self._all_artists = []  # Store all artists for filtering
        self._worker: AIWorker | None = None
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._refresh_artist_combo)
        self._empty_label: QLabel | None = None
        self._load_attempted = False  # Track if load_artists_from_db was called
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
        # Get suggestions button
        self._get_suggestions_button = QPushButton("Get Similar Artists")
        self._get_suggestions_button.clicked.connect(self._get_similar_artists)
        self._layout.addWidget(self._get_suggestions_button)

        # Suggest artists button
        self._suggest_artists_button = QPushButton("Suggest artists for me")
        self._suggest_artists_button.clicked.connect(self._suggest_artists_flow)
        self._layout.addWidget(self._suggest_artists_button)

        # Cancel button
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
        self._empty_label = QLabel("No AI suggestions yet. Click 'Get Similar Artists'.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: gray; font-style: italic;")
        self._empty_label.setVisible(False)
        self._layout.addWidget(self._empty_label)

    def load_artists(self, artists: list[str]):
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
        self._artist_combo.clear()
        self._artist_combo.addItem("Select an artist...")
        
        for artist in filtered:
            self._artist_combo.addItem(artist)
        
        # Update count label
        self._artist_count_label.setText(f"{len(filtered)} artists found")
        
        # Update empty state based on whether any artists are available
        self._update_empty_state(len(filtered) > 0)
    
    def _update_empty_state(self, has_data: bool) -> None:
        """Show the empty-state label only when there is NO data."""
        if self._empty_label:
            self._empty_label.setVisible(not has_data)

    def _get_ai_client(self) -> AIClient:
        """Build AIClient lazily on first use.

        Keyring access (config.get_api_key) is deferred until the user actually
        requests AI suggestions, avoiding a startup prompt.
        """
        if self._ai_client is None:
            self._ai_client = AIClient()
        return self._ai_client

    def refresh_ai_client(self) -> None:
        """Recreate AIClient with fresh config from settings."""
        logger.info("Refreshing AIClient with updated settings")
        self._ai_client = AIClient()
        logger.info(f"New client configured: endpoint={self._ai_client.endpoint}, model={self._ai_client.model}")

    def load_artists_from_db(self, show_empty_state: bool = True) -> bool:
        """Load artists from database. Return True if artists were found.
        
        Args:
            show_empty_state: If False, don't update empty label visibility (for first show).
        """
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
                self._update_empty_state(True)
                self._artists_loaded = True
                return True
            else:
                # No artists found - don't mark as loaded, allow retry
                if show_empty_state:
                    self._update_empty_state(False)
                return False
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error loading artists from DB: {e}")
            if show_empty_state:
                self._update_empty_state(False)
            return False
    def showEvent(self, event):
        """Load artists on first show, retry if previously empty."""
        super().showEvent(event)
        if not self._artists_loaded and not self._load_attempted:
            # First show: load but don't show empty label yet
            self._load_attempted = True
            self.load_artists_from_db(show_empty_state=False)  # Don't show on first attempt
        elif not self._artists_loaded and self._load_attempted:
            # Retry load if previously failed - now show empty state if still no data
            self._update_empty_state(False)  # Hide before retry
            result = self.load_artists_from_db(show_empty_state=True)
            if not result and not self._all_artists:
                self._update_empty_state(False)

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
        self._worker = AIWorker(artist, self._get_ai_client())
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
    def _suggest_artists_flow(self):
        """Flow for suggesting artists based on multiple seed artists."""
        if not self._artists_loaded and not self.load_artists_from_db():
            self._suggestions_display.setText("No artists available in library to use as seeds.")
            return

        # 1. Artist Selection Dialog
        from musichouse import config
        from musichouse.leaderboard_cache import LeaderboardCache
        
        cache = LeaderboardCache(config.get_config_dir())
        artists_with_counts = cache.get_all_artists()
        cache.close()
        
        dialog = ArtistSelectDialog(artists_with_counts, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
            
        seeds = dialog.get_selected_artists()
        if not seeds:
            return

        # 2. Handle caching and worker
        self._set_loading_state(True)
        self._suggestions_display.clear()
        
        # Track results: { seed: [ {artist, reason}, ... ] }
        self._current_suggestions: dict[str, list[dict]] = {}
        self._remaining_seeds = list(seeds)
        
        # We use a separate cache instance for the actual suggestions loop
        self._suggestion_cache = LeaderboardCache(config.get_config_dir())
        
        # Start the processing loop
        self._process_next_seed()

    def _process_next_seed(self):
        """Process seeds one by one: check cache, then worker."""
        if not self._remaining_seeds:
            self._finalize_suggestions()
            return
            
        seed = self._remaining_seeds.pop(0)
        
        # Check cache first
        cached = self._suggestion_cache.get_similar_artists(seed)
        if cached:
            logger.info(f"Cache hit for seed: {seed}")
            self._handle_seed_result(seed, cached)
            # Immediately process next
            self._process_next_seed()
        else:
            logger.info(f"Cache miss for seed: {seed}. Starting worker...")
            # Use SuggestWorker for a single seed (or we could use SuggestWorker for all, 
            # but the contract says SuggestWorker takes seeds: list[str]. 
            # Let's use it for all remaining seeds + the current one to be efficient, 
            # but we must manage the state).
            
            # Actually, the contract says SuggestWorker(seeds: list[str], ai_client) 
            # and emits seed_result(str, list). Let's just start it once for all seeds.
            
            # Re-evaluating: If some are cached, we only need the worker for the non-cached ones.
            non_cached_seeds = [seed] + self._remaining_seeds
            self._remaining_seeds = [] # Worker will handle the rest
            
            self._worker = SuggestWorker(non_cached_seeds, self._get_ai_client())
            self._worker.progress.connect(self._on_suggest_progress)
            self._worker.seed_result.connect(self._on_suggest_seed_result)
            self._worker.error.connect(self._on_suggest_error)
            self._worker.finished.connect(self._on_suggest_finished)
            self._worker.start()

    def _on_suggest_progress(self, message: str):
        self._suggestions_display.append(f"Processing: {message}...")

    def _on_suggest_seed_result(self, seed: str, results: list[dict]):
        # results is list of {"artist": str, "reason": str}
        self._handle_seed_result(seed, results)

    def _handle_seed_result(self, seed: str, results: list[dict]):
        # Filter out artists already in library and the seeds themselves
        from musichouse import config
        from musichouse.leaderboard_cache import LeaderboardCache
        
        # Get current indexed artists to filter
        temp_cache = LeaderboardCache(config.get_config_dir())
        indexed_artists = temp_cache.get_all_indexed_artists()
        temp_cache.close()
        
        filtered = [
            r for r in results 
            if r["artist"] not in indexed_artists and r["artist"] != seed
        ]
        
        if filtered:
            self._current_suggestions[seed] = filtered
            # Save raw suggestions to cache (as per contract, cache stores raw, filtering at display)
            # Wait, contract says: save_similar_artists(seed, filtered_suggestions)
            # Let's follow the contract exactly.
            self._suggestion_cache.save_similar_artists(seed, filtered)
        
    def _on_suggest_finished(self):
        self._finalize_suggestions()

    def _finalize_suggestions(self):
        self._set_loading_state(False)
        if not self._current_suggestions:
            self._suggestions_display.setText("No new suggestions — all similar artists are already in your library.")
            return
            
        # Display grouped results
        output = []
        for seed, results in self._current_suggestions.items():
            output.append(f"Because you listen to {seed}:")
            for r in results:
                output.append(f"  • {r['artist']}: {r['reason']}")
            output.append("") # Spacer
            
        self._suggestions_display.setText("\n".join(output))
        
        if hasattr(self, '_suggestion_cache'):
            self._suggestion_cache.close()

    def _on_suggest_error(self, error_msg: str):
        """Handle error for suggest artists flow."""
        # Reuse existing _on_worker_error logic
        self._on_worker_error(error_msg)
        if hasattr(self, '_suggestion_cache'):
            self._suggestion_cache.close()
        self._genre_label.setText("Genres: Error")

    def _cancel_request(self):
        """Cancel the current worker request."""
        if self._worker:
            logger.info("Cancelling worker request")
            self._worker.stop()
            self._set_loading_state(False)
            self._suggestions_display.append("Request cancelled.")
            if hasattr(self, '_suggestion_cache'):
                self._suggestion_cache.close()
