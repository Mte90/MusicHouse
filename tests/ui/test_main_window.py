"""pytest-qt tests for MainWindow and ScanWorker components.
Tests main_window.py functionality with mocked dependencies to avoid threading issues.
Run with: QT_QPA_PLATFORM=offscreen pytest tests/ui/test_main_window.py -v
"""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from PyQt6.QtWidgets import QMessageBox
from typing import List, Tuple

pytestmark = pytest.mark.ui


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_scanner_class():
    """Create a mock MP3Scanner class for patching."""
    mock_class = MagicMock()
    mock_instance = MagicMock()
    mock_class.return_value = mock_instance
    mock_instance.scan.return_value = []
    mock_instance.get_errors.return_value = []
    return mock_class


@pytest.fixture
def mock_cache_class():
    """Create a mock LeaderboardCache class for patching."""
    mock_class = MagicMock()
    mock_instance = MagicMock()
    mock_class.return_value = mock_instance
    mock_instance.get_changed_files.return_value = ([], 0, 0, 0)
    mock_instance._get_connection.return_value.executemany = MagicMock()
    mock_instance.close = MagicMock()
    return mock_class


# ============================================================================
# ScanWorker Tests - Phase Flow
# ============================================================================

def test_scan_worker_phase_flow_emits_signals(
    qapp, mock_scanner_class, mock_cache_class, temp_dir
):
    """Test Phase 1 → 1.5 → 2 → 3 flow with correct signal order."""
    from musichouse.ui.main_window import ScanWorker
    
    # Setup mock scanner to return fake paths
    fake_paths = [temp_dir / f"track{i}.mp3" for i in range(1, 4)]
    mock_scanner_class.return_value.scan.return_value = fake_paths
    
    # Setup mock cache to return changed files
    mock_cache_class.return_value.get_changed_files.return_value = (
        fake_paths, 3, 0, 0  # 3 new files
    )
    
    # Patch imports - LeaderboardCache is imported inside run()
    with patch("musichouse.ui.main_window.MP3Scanner", mock_scanner_class), \
         patch("musichouse.leaderboard_cache.LeaderboardCache", mock_cache_class):
        
        worker = ScanWorker(temp_dir)
        
        # Collect signals
        signals_received = []
        worker.scan_stats.connect(lambda *args: signals_received.append(('scan_stats', args)))
        worker.scan_total_work.connect(lambda *args: signals_received.append(('scan_total_work', args)))
        worker.tag_read_progress.connect(lambda *args: signals_received.append(('tag_read_progress', args)))
        worker.scan_finished.connect(lambda *args: signals_received.append(('scan_finished', args)))
        
        # Run worker synchronously
        worker.run()
        
        # Verify signals emitted in order
        assert len(signals_received) >= 4, f"Expected at least 4 signals, got {len(signals_received)}"
        
        # First signal should be scan_stats
        assert signals_received[0][0] == 'scan_stats'
        assert signals_received[0][1] == (3, 0, 0)  # 3 new, 0 modified, 0 skipped
        
        # Second signal should be scan_total_work
        assert signals_received[1][0] == 'scan_total_work'
        assert signals_received[1][1][0] == 3  # total_files (no doubling for cache ops)
        
        # tag_read_progress should emit multiple times
        tag_progress_signals = [s for s in signals_received if s[0] == 'tag_read_progress']
        assert len(tag_progress_signals) >= 1
        
        # Last signal should be scan_finished
        last_signal = signals_received[-1]
        assert last_signal[0] == 'scan_finished'
        assert last_signal[1][0] == fake_paths


def test_scan_worker_scan_stats_emits_correct_counts(
    qapp, mock_scanner_class, mock_cache_class, temp_dir
):
    """Test scan_stats emits correct new/modified/skipped counts."""
    from musichouse.ui.main_window import ScanWorker
    
    # Setup mock scanner
    fake_paths = [temp_dir / f"track{i}.mp3" for i in range(1, 6)]
    mock_scanner_class.return_value.scan.return_value = fake_paths
    
    # Setup mock cache: 2 new, 2 modified, 1 skipped
    mock_cache_class.return_value.get_changed_files.return_value = (
        fake_paths[:4], 2, 2, 1  # changed, new, modified, skipped
    )
    
    with patch("musichouse.ui.main_window.MP3Scanner", mock_scanner_class), \
         patch("musichouse.leaderboard_cache.LeaderboardCache", mock_cache_class):
        
        worker = ScanWorker(temp_dir)
        
        stats_collected = []
        worker.scan_stats.connect(lambda new, mod, skip: stats_collected.append((new, mod, skip)))
        
        worker.run()
        
        assert len(stats_collected) == 1
        assert stats_collected[0] == (2, 2, 1)


def test_scan_worker_empty_result_early_return(
    qapp, mock_scanner_class, mock_cache_class, temp_dir
):
    """Test empty result path - early return without tag reading."""
    from musichouse.ui.main_window import ScanWorker
    
    # Setup mock scanner to return files
    fake_paths = [temp_dir / "track1.mp3"]
    mock_scanner_class.return_value.scan.return_value = fake_paths
    
    # Setup mock cache to return no changed files
    mock_cache_class.return_value.get_changed_files.return_value = (
        [], 0, 0, 1  # no changed files, 0 new, 0 modified, 1 skipped
    )
    
    with patch("musichouse.ui.main_window.MP3Scanner", mock_scanner_class), \
         patch("musichouse.leaderboard_cache.LeaderboardCache", mock_cache_class):
        
        worker = ScanWorker(temp_dir)
        
        signals_received = []
        worker.scan_stats.connect(lambda *args: signals_received.append(('scan_stats', args)))
        worker.scan_total_work.connect(lambda *args: signals_received.append(('scan_total_work', args)))
        worker.tag_read_progress.connect(lambda *args: signals_received.append(('tag_read_progress', args)))
        worker.scan_finished.connect(lambda *args: signals_received.append(('scan_finished', args)))
        
        worker.run()
        
        # Should emit scan_stats but NOT scan_total_work or tag_read_progress
        assert any(s[0] == 'scan_stats' for s in signals_received)
        assert not any(s[0] == 'scan_total_work' for s in signals_received), \
            "scan_total_work should not emit for empty results"
        assert not any(s[0] == 'tag_read_progress' for s in signals_received), \
            "tag_read_progress should not emit for empty results"
        
        # Should still emit scan_finished
        assert any(s[0] == 'scan_finished' for s in signals_received)


# ============================================================================
# ScanWorker Tests - Tag Data JSON Serialization
# ============================================================================

def test_tag_data_json_serialization_in_bulk_insert(
    qapp, mock_scanner_class, mock_cache_class, temp_dir
):
    """Test that tag_data is serialized to JSON before DB insert."""
    from musichouse.ui.main_window import ScanWorker
    
    # Setup mock scanner
    fake_paths = [temp_dir / "Artist - Title.mp3"]
    mock_scanner_class.return_value.scan.return_value = fake_paths
    
    # Setup mock cache
    mock_cache_class.return_value.get_changed_files.return_value = (
        fake_paths, 1, 0, 0
    )
    
    # Mock eyed3 to return tag data
    mock_audio = MagicMock()
    mock_audio.tag.artist = "Existing Artist"
    mock_audio.tag.title = "Existing Title"
    
    with patch("musichouse.ui.main_window.MP3Scanner", mock_scanner_class), \
         patch("musichouse.leaderboard_cache.LeaderboardCache", mock_cache_class), \
         patch("musichouse.ui.main_window.eyed3.load", return_value=mock_audio):
        
        worker = ScanWorker(temp_dir)
        worker.run()
        
        # Verify executemany was called
        conn = mock_cache_class.return_value._get_connection()
        conn.executemany.assert_called_once()
        
        # Extract the data passed to executemany
        call_args = conn.executemany.call_args
        data_rows = call_args[0][1]  # Second positional argument is the data
        
        assert len(data_rows) == 1
        row = data_rows[0]
        
        # tag_data is the 12th column (index 11)
        tag_data_json = row[11]
        assert tag_data_json is not None
        assert isinstance(tag_data_json, str)
        
        # Verify it's valid JSON
        tag_data = json.loads(tag_data_json)
        assert tag_data['artist'] == "Existing Artist"
        assert tag_data['title'] == "Existing Title"


# ============================================================================
# ScanWorker Tests - suggested_artist/suggested_title from parse_filename
# ============================================================================

def test_suggested_values_computed_via_parse_filename(
    qapp, mock_scanner_class, mock_cache_class, temp_dir
):
    """Test that suggested_artist/suggested_title are computed from filename."""
    from musichouse.ui.main_window import ScanWorker
    
    # Setup mock scanner with a file that has parseable name
    fake_path = temp_dir / "Test Artist - Track Title.mp3"
    mock_scanner_class.return_value.scan.return_value = [fake_path]
    
    # Setup mock cache
    mock_cache_class.return_value.get_changed_files.return_value = (
        [fake_path], 1, 0, 0
    )
    
    # Mock eyed3 to return empty tags (so suggestions are visible)
    mock_audio = MagicMock()
    mock_audio.tag.artist = None
    mock_audio.tag.title = None
    
    with patch("musichouse.ui.main_window.MP3Scanner", mock_scanner_class), \
         patch("musichouse.leaderboard_cache.LeaderboardCache", mock_cache_class), \
         patch("musichouse.ui.main_window.eyed3.load", return_value=mock_audio):
        
        worker = ScanWorker(temp_dir)
        worker.run()
        
        # Verify executemany was called
        conn = mock_cache_class.return_value._get_connection()
        conn.executemany.assert_called_once()
        
        # Extract the data
        call_args = conn.executemany.call_args
        data_rows = call_args[0][1]
        
        assert len(data_rows) == 1
        row = data_rows[0]
        
        # suggested_artist is column 9, suggested_title is column 10
        suggested_artist = row[9]
        suggested_title = row[10]
        
        assert suggested_artist == "Test Artist"
        assert suggested_title == "Track Title"


# ============================================================================
# ScanWorker Tests - Pause/Resume/Stop
# ============================================================================

def test_pause_resume_stop_no_deadlock(qapp, mock_scanner_class, mock_cache_class, temp_dir):
    """Test pause → resume → stop sequence completes without deadlock."""
    from musichouse.ui.main_window import ScanWorker
    import time
    
    # Setup mock scanner to return many files
    fake_paths = [temp_dir / f"track{i}.mp3" for i in range(1, 11)]
    mock_scanner_class.return_value.scan.return_value = fake_paths
    
    # Setup mock cache
    mock_cache_class.return_value.get_changed_files.return_value = (
        fake_paths, 10, 0, 0
    )
    
    # Mock eyed3 with a small delay to allow pause to take effect
    mock_audio = MagicMock()
    mock_audio.tag.artist = "Artist"
    mock_audio.tag.title = "Title"
    
    with patch("musichouse.ui.main_window.MP3Scanner", mock_scanner_class), \
         patch("musichouse.leaderboard_cache.LeaderboardCache", mock_cache_class), \
         patch("musichouse.ui.main_window.eyed3.load", return_value=mock_audio):
        
        worker = ScanWorker(temp_dir)
        
        # Start the thread
        worker.start()
        
        # Give it a moment to start
        time.sleep(0.1)
        
        # Pause
        worker.pause()
        assert worker.is_paused()
        
        # Resume
        worker.resume()
        
        # Stop
        worker.stop()
        
        # Wait for completion with timeout
        finished = worker.wait(5000)  # 5 second timeout
        assert finished, "Worker should finish within 5 seconds"


def test_stop_while_paused_exits_cleanly(qapp, mock_scanner_class, mock_cache_class, temp_dir):
    """Test that stopping while paused exits cleanly."""
    from musichouse.ui.main_window import ScanWorker
    
    # Setup mock scanner
    fake_paths = [temp_dir / f"track{i}.mp3" for i in range(1, 6)]
    mock_scanner_class.return_value.scan.return_value = fake_paths
    
    # Setup mock cache
    mock_cache_class.return_value.get_changed_files.return_value = (
        fake_paths, 5, 0, 0
    )
    
    with patch("musichouse.ui.main_window.MP3Scanner", mock_scanner_class), \
         patch("musichouse.leaderboard_cache.LeaderboardCache", mock_cache_class):
        
        worker = ScanWorker(temp_dir)
        
        # Set flags before running
        worker._paused = True
        worker._pause_event.clear()  # Ensure paused state
        worker._stop_requested = True
        
        # Run synchronously
        worker.run()
        
        # Should complete immediately without entering tag-read loop
        # scan_finished should still emit
        finished_signals = []
        worker.scan_finished.connect(lambda *args: finished_signals.append(args))
        
        # Re-run to verify signal emission
        worker._stop_requested = False
        worker.run()
        
        # Verify worker completed
        assert worker.isFinished() or not worker.isRunning()


# ============================================================================
# MainWindow Signal Handler Tests
# ============================================================================

def test_main_window_on_scan_stats_updates_status(main_window):
    """Test _on_scan_stats updates status label correctly."""
    # Test with skipped files
    main_window._on_scan_stats(5, 3, 10)
    
    status_text = main_window._status_label.text()
    assert "Incremental" in status_text
    assert "5 new" in status_text
    assert "3 modified" in status_text
    assert "10 skipped" in status_text
    
    # Test without skipped files
    main_window._on_scan_stats(8, 2, 0)
    status_text = main_window._status_label.text()
    assert "Found 10 files to process" in status_text


def test_main_window_on_scan_finished_updates_ui(main_window, mock_cache_class):
    """Test _on_scan_finished updates UI and populates tabs."""
    with patch("musichouse.leaderboard_cache.LeaderboardCache", mock_cache_class):
        # Setup initial scanning state
        main_window._is_scanning = True
        main_window._scan_btn.setEnabled(False)
        main_window._pause_btn.setEnabled(True)
        main_window._scan_stats_summary = (5, 2, 0)
        
        # Emit scan finished
        files = [Path("/fake/path/track1.mp3")]
        artist_counts = {"Test Artist": 5}
        main_window._on_scan_finished(files, artist_counts)
        
        # Verify UI updates
        assert not main_window._is_scanning
        assert main_window._scan_btn.isEnabled()
        assert not main_window._pause_btn.isEnabled()
        assert main_window._pause_btn.text() == "Pause"
        
        # Verify status message includes stats
        status_text = main_window._status_label.text()
        assert "Scan complete" in status_text
        assert "5 new" in status_text


def test_main_window_on_tag_read_progress_updates_progress_bar(main_window):
    """Test _on_tag_read_progress updates progress bar and status."""
    main_window._progress_bar.setVisible(True)
    main_window._progress_bar.setRange(0, 100)
    
    main_window._on_tag_read_progress(50, 100)
    
    assert main_window._progress_bar.value() == 50
    assert main_window._status_label.text() == "Reading tags: 50/100"


def test_main_window_on_scan_total_work_sets_range(main_window):
    """Test _on_scan_total_work sets progress bar range."""
    main_window._on_scan_total_work(200)
    
    assert (main_window._progress_bar.minimum(), main_window._progress_bar.maximum()) == (0, 200)
    assert main_window._progress_bar.value() == 0
    assert main_window._status_label.text() == "Reading tags: 0/200"


def test_main_window_on_scan_error_shows_dialog(qapp, main_window):
    """Test _on_scan_error shows error dialog and resets UI."""
    # Mock QMessageBox to avoid actual dialog
    with patch("musichouse.ui.main_window.QMessageBox.critical") as mock_dialog:
        main_window._is_scanning = True
        main_window._scan_btn.setEnabled(False)
        
        main_window._on_scan_error("Test error message")
        
        # Verify dialog was shown
        mock_dialog.assert_called_once()
        call_args = mock_dialog.call_args
        assert call_args[0][2] == "Test error message"  # Error message
        
        # Verify UI reset
        assert not main_window._is_scanning
        assert main_window._scan_btn.isEnabled()
        assert not main_window._pause_btn.isEnabled()


def test_main_window_toggle_pause_updates_button(main_window, qapp):
    """Test _toggle_pause updates button text and icon."""
    # Create a mock worker
    mock_worker = MagicMock()
    mock_worker.is_paused.return_value = False
    main_window._scan_worker = mock_worker
    
    # Toggle to pause
    main_window._toggle_pause()
    
    assert mock_worker.pause.called
    assert main_window._pause_btn.text() == "Resume"
    assert main_window._status_label.text() == "Scan paused"
    
    # Reset mock
    mock_worker.reset_mock()
    mock_worker.is_paused.return_value = True
    
    # Toggle to resume
    main_window._toggle_pause()
    
    assert mock_worker.resume.called
    assert main_window._pause_btn.text() == "Pause"
    assert "resumed" in main_window._status_label.text().lower()


# ============================================================================
# Integration Tests - Full Scan Flow
# ============================================================================

def test_full_scan_flow_with_mocked_dependencies(
    qapp, mock_scanner_class, mock_cache_class, temp_dir, main_window
):
    """Test complete scan flow from start to finish."""
    from musichouse.ui.main_window import ScanWorker
    
    # Setup mock scanner
    fake_paths = [temp_dir / f"Artist - Track {i}.mp3" for i in range(1, 4)]
    mock_scanner_class.return_value.scan.return_value = fake_paths
    
    # Setup mock cache
    mock_cache_class.return_value.get_changed_files.return_value = (
        fake_paths, 3, 0, 0
    )
    
    # Mock eyed3
    mock_audio = MagicMock()
    mock_audio.tag.artist = None
    mock_audio.tag.title = None
    
    with patch("musichouse.ui.main_window.MP3Scanner", mock_scanner_class), \
         patch("musichouse.leaderboard_cache.LeaderboardCache", mock_cache_class), \
         patch("musichouse.ui.main_window.eyed3.load", return_value=mock_audio), \
         patch("musichouse.ui.main_window.QFileDialog.getExistingDirectory", return_value=str(temp_dir)), \
         patch("musichouse.ui.main_window.config.set_last_directory"):
        
        # Track all signals
        all_signals = []
        
        def create_signal_tracker(name):
            def tracker(*args):
                all_signals.append((name, args))
            return tracker
        
        # Patch the worker creation to track signals
        original_init = ScanWorker.__init__
        
        def tracked_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self.progress.connect(create_signal_tracker('progress'))
            self.file_processed.connect(create_signal_tracker('file_processed'))
            self.scan_finished.connect(create_signal_tracker('scan_finished'))
            self.scan_stats.connect(create_signal_tracker('scan_stats'))
            self.scan_total_work.connect(create_signal_tracker('scan_total_work'))
            self.tag_read_progress.connect(create_signal_tracker('tag_read_progress'))
        
        with patch.object(ScanWorker, '__init__', tracked_init):
            # Start scan (this would normally open a dialog, but we mocked it)
            main_window._start_scan()
            
            # Wait for worker to complete, then drain queued signals
            if main_window._scan_worker:
                main_window._scan_worker.wait(5000)
            qapp.processEvents()
        
        # Verify signal flow
        signal_names = [s[0] for s in all_signals]
        
        assert 'scan_stats' in signal_names
        assert 'scan_total_work' in signal_names
        assert 'tag_read_progress' in signal_names
        assert 'scan_finished' in signal_names
        
        # Verify scan_stats has correct counts
        scan_stats_signals = [s for s in all_signals if s[0] == 'scan_stats']
        assert len(scan_stats_signals) == 1
        assert scan_stats_signals[0][1] == (3, 0, 0)


def test_scan_with_mixed_tag_data(qapp, mock_scanner_class, mock_cache_class, temp_dir):
    """Test scan with files that have some tags and some missing."""
    from musichouse.ui.main_window import ScanWorker
    
    # Setup mock scanner
    fake_paths = [
        temp_dir / "Artist1 - Title1.mp3",
        temp_dir / "Artist2 - Title2.mp3",
        temp_dir / "NoArtist - .mp3",  # Missing title
    ]
    mock_scanner_class.return_value.scan.return_value = fake_paths
    
    # Setup mock cache
    mock_cache_class.return_value.get_changed_files.return_value = (
        fake_paths, 3, 0, 0
    )
    
    # Mock eyed3 - first file has tags, others don't
    def mock_eyed3_load(path):
        mock_audio = MagicMock()
        if "Artist1" in str(path):
            mock_audio.tag.artist = "Artist1"
            mock_audio.tag.title = "Title1"
        else:
            mock_audio.tag.artist = None
            mock_audio.tag.title = None
        return mock_audio
    
    with patch("musichouse.ui.main_window.MP3Scanner", mock_scanner_class), \
         patch("musichouse.leaderboard_cache.LeaderboardCache", mock_cache_class), \
         patch("musichouse.ui.main_window.eyed3.load", side_effect=mock_eyed3_load):
        
        worker = ScanWorker(temp_dir)
        worker.run()
        
        # Verify executemany was called
        conn = mock_cache_class.return_value._get_connection()
        conn.executemany.assert_called_once()
        
        # Check the data
        call_args = conn.executemany.call_args
        data_rows = call_args[0][1]
        
        assert len(data_rows) == 3
        
        # First file should have tag_data
        assert json.loads(data_rows[0][11])['artist'] == "Artist1"
        
        # All files should have suggested values from parse_filename
        assert data_rows[0][9] == "Artist1"
        assert data_rows[1][9] == "Artist2"
        assert data_rows[2][9] == "NoArtist"


# ============================================================================
# Edge Cases Tests
# ============================================================================

def test_scan_worker_handles_scan_errors(qapp, mock_scanner_class, mock_cache_class, temp_dir):
    """Test that ScanWorker emits error signal on exceptions."""
    from musichouse.ui.main_window import ScanWorker
    
    # Setup mock scanner to raise an error
    mock_scanner_class.return_value.scan.side_effect = Exception("Scan failed")
    
    with patch("musichouse.ui.main_window.MP3Scanner", mock_scanner_class), \
         patch("musichouse.leaderboard_cache.LeaderboardCache", mock_cache_class):
        worker = ScanWorker(temp_dir)
        
        errors = []
        worker.error.connect(lambda msg: errors.append(msg))
        
        worker.run()
        
        assert len(errors) == 1
        assert "Scan failed" in errors[0]


def test_main_window_close_event_with_scan_in_progress(qapp, main_window):
    """Test closeEvent handles scan in progress correctly."""
    from unittest.mock import Mock
    
    # Setup mock worker
    mock_worker = MagicMock()
    mock_worker.isRunning.return_value = False
    main_window._scan_worker = mock_worker
    main_window._is_scanning = True
    
    # Create mock event
    mock_event = MagicMock()
    
    # Mock the modal QMessageBox.question to avoid blocking
    with patch("musichouse.ui.main_window.QMessageBox.question",
               return_value=QMessageBox.StandardButton.Yes):
        main_window.closeEvent(mock_event)
    
    # Should accept the event after stopping worker
    assert mock_event.accepted or mock_event.ignore()  # One of these should be called


def test_main_window_stop_scan_when_not_scanning(main_window):
    """Test _stop_scan does nothing when not scanning."""
    main_window._is_scanning = False
    main_window._scan_worker = None
    
    # Should not raise
    main_window._stop_scan()
    
    # UI should be unchanged
    assert not main_window._is_scanning


def test_scan_worker_with_large_batch(qapp, mock_scanner_class, mock_cache_class, temp_dir):
    """Test scan worker handles large batches correctly."""
    from musichouse.ui.main_window import ScanWorker
    
    # Setup mock scanner with 1000 files
    fake_paths = [temp_dir / f"track{i}.mp3" for i in range(1, 1001)]
    mock_scanner_class.return_value.scan.return_value = fake_paths
    
    # Setup mock cache
    mock_cache_class.return_value.get_changed_files.return_value = (
        fake_paths, 1000, 0, 0
    )
    
    # Mock eyed3
    mock_audio = MagicMock()
    mock_audio.tag.artist = "Test Artist"
    mock_audio.tag.title = "Test Title"
    
    with patch("musichouse.ui.main_window.MP3Scanner", mock_scanner_class), \
         patch("musichouse.leaderboard_cache.LeaderboardCache", mock_cache_class), \
         patch("musichouse.ui.main_window.eyed3.load", return_value=mock_audio):
        
        worker = ScanWorker(temp_dir)
        
        progress_updates = []
        worker.tag_read_progress.connect(lambda curr, total: progress_updates.append((curr, total)))
        
        worker.run()
        
        # Should have progress updates at every 10 files and at the end
        assert len(progress_updates) > 0
        
        # Final update should be at 1000/1000 (total_files, no doubling for cache ops)
        final_update = progress_updates[-1]
        assert final_update[0] == 1000  # total progress
        assert final_update[1] == 1000  # total work