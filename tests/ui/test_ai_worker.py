"""Unit tests for ai_worker module.

Tests for AIWorker QThread worker.
Uses mocking to avoid real API calls.
"""

from unittest.mock import MagicMock

from musichouse.ai_client import AIClient
from musichouse.ui.ai_worker import AIWorker

# ============================================================================
# AIWorker Tests
# ============================================================================

class TestAIWorker:
    """Tests for AIWorker class."""

    def test_run_successful_full_analysis(self, qapp):
        """Test successful full run: get similar artists and genres."""
        artist = "Metallica"
        ai_client = MagicMock(spec=AIClient)
        ai_client.get_similar_artists.return_value = ["Iron Maiden", "Judas Priest", "Slayer"]
        ai_client.get_artist_genres.return_value = ["heavy metal", "thrash metal"]

        progress_args = []
        finished_args = []

        def on_progress(msg):
            progress_args.append(msg)

        def on_finished(result):
            finished_args.append(result)

        worker = AIWorker(artist, ai_client)

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)

        worker.run()

        # Verify progress signals
        assert "Fetching similar artists..." in progress_args
        assert "Fetching artist genres..." in progress_args

        # Verify finished emitted with correct result
        assert len(finished_args) == 1
        result = finished_args[0]
        assert "Iron Maiden" in result
        assert "Judas Priest" in result
        assert "heavy metal" in result
        assert "thrash metal" in result

        # Verify AIClient methods were called
        ai_client.get_similar_artists.assert_called_once_with(artist)
        ai_client.get_artist_genres.assert_called_once_with(artist)

    def test_run_handles_ai_error(self, qapp):
        """Test that AI error emits error signal."""
        artist = "Metallica"
        ai_client = MagicMock(spec=AIClient)
        ai_client.get_similar_artists.side_effect = Exception("API connection failed")

        progress_args = []
        error_args = []

        def on_progress(msg):
            progress_args.append(msg)

        def on_error(msg):
            error_args.append(msg)

        worker = AIWorker(artist, ai_client)

        worker.progress.connect(on_progress)
        worker.error.connect(on_error)

        worker.run()

        # Verify progress signal was emitted before error
        assert "Fetching similar artists..." in progress_args

        # Verify error signal was emitted
        assert len(error_args) == 1
        assert "API connection failed" in error_args[0]

        # Verify finished was not emitted
        assert len(error_args) == 1

    def test_run_stops_during_genre_fetching(self, qapp):
        """Test that worker exits early when stop flag is set during genre fetching."""
        artist = "Metallica"
        ai_client = MagicMock(spec=AIClient)
        ai_client.get_similar_artists.return_value = ["Iron Maiden"]

        progress_args = []

        def on_progress(msg):
            progress_args.append(msg)
            # Stop after similar artists but before genres
            if "Fetching similar artists..." in msg:
                worker.stop()

        worker = AIWorker(artist, ai_client)

        worker.progress.connect(on_progress)

        worker.run()

        # Verify worker stopped early
        assert "Fetching similar artists..." in progress_args
        assert "Fetching artist genres..." not in progress_args

        # Verify AIClient.get_artist_genres was not called
        ai_client.get_artist_genres.assert_not_called()

    def test_run_stops_after_genre_fetching(self, qapp):
        """Test that worker exits early when stop flag is set after genre fetching completes."""
        artist = "Metallica"
        ai_client = MagicMock(spec=AIClient)
        ai_client.get_similar_artists.return_value = ["Iron Maiden"]
        ai_client.get_artist_genres.return_value = ["heavy metal"]

        progress_args = []
        finished_args = []

        def on_progress(msg):
            progress_args.append(msg)
            # Stop after genre fetching completes (triggers stop check before emit)
            if "Fetching artist genres..." in msg:
                worker.stop()

        def on_finished(result):
            finished_args.append(result)

        worker = AIWorker(artist, ai_client)

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)

        worker.run()

        # Verify both progress signals were emitted
        assert "Fetching similar artists..." in progress_args
        assert "Fetching artist genres..." in progress_args

        # Verify finished was not emitted due to stop flag
        assert len(finished_args) == 0

    def test_run_handles_empty_similar_artists(self, qapp):
        """Test worker handles empty similar artists list."""
        artist = "UnknownArtist"
        ai_client = MagicMock(spec=AIClient)
        ai_client.get_similar_artists.return_value = []
        ai_client.get_artist_genres.return_value = ["rock"]

        progress_args = []
        finished_args = []

        def on_progress(msg):
            progress_args.append(msg)

        def on_finished(result):
            finished_args.append(result)

        worker = AIWorker(artist, ai_client)

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)

        worker.run()

        # Verify finished emitted with fallback message
        assert len(finished_args) == 1
        result = finished_args[0]
        assert "No similar artists found." in result
        assert "Genres: rock" in result

    def test_run_handles_empty_genres(self, qapp):
        """Test worker handles empty genres list."""
        artist = "UnknownArtist"
        ai_client = MagicMock(spec=AIClient)
        ai_client.get_similar_artists.return_value = ["Similar Artist"]
        ai_client.get_artist_genres.return_value = []

        progress_args = []
        finished_args = []

        def on_progress(msg):
            progress_args.append(msg)

        def on_finished(result):
            finished_args.append(result)

        worker = AIWorker(artist, ai_client)

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)

        worker.run()

        # Verify finished emitted with Unknown genre
        assert len(finished_args) == 1
        result = finished_args[0]
        assert "Similar Artist" in result
        assert "Genres: Unknown" in result

    def test_stop_method_sets_flag_and_exits(self, qapp):
        """Test that stop method sets flag and worker exits cleanly."""
        artist = "Metallica"
        ai_client = MagicMock(spec=AIClient)
        ai_client.get_similar_artists.return_value = ["Iron Maiden"]

        progress_args = []

        def on_progress(msg):
            progress_args.append(msg)
            if "Fetching similar artists..." in msg:
                worker.stop()

        worker = AIWorker(artist, ai_client)
        worker.progress.connect(on_progress)

        worker.run()

        # Verify worker completed without error
        assert "Fetching similar artists..." in progress_args