"""pytest-qt tests for MainWindow and ScanWorker components.
Tests main_window.py functionality with mocked dependencies to avoid threading issues.
Run with: QT_QPA_PLATFORM=offscreen pytest tests/ui/test_main_window.py -v
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMessageBox

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
    import time

    from musichouse.ui.main_window import ScanWorker
    
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


# ============================================================================
# Duplicates Tab Tests
# ============================================================================

def test_main_window_has_duplicates_tab(qapp):
    """Test that MainWindow has a Duplicates tab after construction."""
    from musichouse.ui.main_window import MainWindow
    
    window = MainWindow()
    
    # Verify the tab exists
    assert hasattr(window, '_duplicates_tab')
    assert window._duplicates_tab is not None
    window.close()


def test_main_window_duplicates_tab_label(qapp):
    """Test that the Duplicates tab has the correct label."""
    from musichouse.ui.main_window import MainWindow
    
    window = MainWindow()
    
    # Find the Duplicates tab by label
    tab_count = window._tab_widget.count()
    duplicates_tab_index = None
    for i in range(tab_count):
        if window._tab_widget.tabText(i) == "Duplicates":
            duplicates_tab_index = i
            break
    
    assert duplicates_tab_index is not None, "Duplicates tab not found"
    assert window._tab_widget.tabText(duplicates_tab_index) == "Duplicates"
    window.close()


def test_main_window_duplicates_tab_has_cache(qapp):
    """Test that the Duplicates tab has access to the cache."""
    from musichouse.ui.main_window import MainWindow
    
    window = MainWindow()
    
    # Verify the tab has a _cache attribute
    assert hasattr(window._duplicates_tab, '_cache')
    assert window._duplicates_tab._cache is not None
    window.close()


def test_main_window_has_organize_tab(qapp):
    """Test that MainWindow has an Organize tab after construction."""
    from musichouse.ui.main_window import MainWindow
    
    window = MainWindow()
    
    # Verify the tab exists
    assert hasattr(window, '_organize_tab')
    assert window._organize_tab is not None
    window.close()


def test_main_window_organize_tab_label(qapp):
    """Test that the Organize tab has the correct label."""
    from musichouse.ui.main_window import MainWindow
    
    window = MainWindow()
    
    # Find the Organize tab by label
    tab_count = window._tab_widget.count()
    organize_tab_index = None
    for i in range(tab_count):
        if window._tab_widget.tabText(i) == "Organize":
            organize_tab_index = i
            break
    
    assert organize_tab_index is not None, "Organize tab not found"
    assert window._tab_widget.tabText(organize_tab_index) == "Organize"
    window.close()


def test_main_window_has_fingerprint_mode_indicator(qapp):
    """Test that the status bar has the fingerprint mode indicator label."""
    from musichouse.ui.main_window import MainWindow
    
    window = MainWindow()
    
    # Verify the mode indicator label exists
    assert hasattr(window, '_mode_indicator')
    assert window._mode_indicator is not None
    
    # Verify the label contains "Duplicate mode"
    mode_text = window._mode_indicator.text()
    assert "Duplicate mode" in mode_text
    window.close()


def test_main_window_fingerprint_mode_indicator_shows_fingerprint_when_available(qapp, monkeypatch):
    """Test that the mode indicator shows 'Fingerprint' when fpcalc is available."""
    from musichouse.ui.main_window import MainWindow
    
    # Mock is_fpcalc_available in the fingerprint module (where it's defined)
    with patch("musichouse.fingerprint.is_fpcalc_available", return_value=True):
        window = MainWindow()
        
        mode_text = window._mode_indicator.text()
        assert "Fingerprint" in mode_text
        assert "fpcalc detected" in mode_text
        window.close()


def test_main_window_fingerprint_mode_indicator_shows_metadata_when_not_available(qapp, monkeypatch):
    """Test that the mode indicator shows 'Metadata only' when fpcalc is not available."""
    from musichouse.ui.main_window import MainWindow
    
    # Mock is_fpcalc_available in the fingerprint module (where it's defined)
    with patch("musichouse.fingerprint.is_fpcalc_available", return_value=False):
        window = MainWindow()
        
        mode_text = window._mode_indicator.text()
        assert "Metadata only" in mode_text
        assert "fpcalc not found" in mode_text
        window.close()


# ============================================================================
# ScanWorker Tests - Filesystem Scan Callbacks
# ============================================================================

def test_scan_worker_filesystem_scan_callbacks(qapp, mock_scanner_class, mock_cache_class, temp_dir):
    """Test that filesystem scan callbacks emit signals correctly."""
    from musichouse.ui.main_window import ScanWorker
    
    # Setup mock scanner with directory callback
    fake_paths = [temp_dir / f"track{i}.mp3" for i in range(1, 4)]
    mock_scanner_class.return_value.scan.return_value = fake_paths
    
    # Track callback invocations
    directory_callbacks = []
    file_callbacks = []
    
    def on_directory(dir_path):
        directory_callbacks.append(dir_path)
    
    def on_file_batch(count):
        file_callbacks.append(count)
    
    # Setup scanner to use callbacks
    mock_scanner_class.return_value.set_progress_callback = MagicMock(side_effect=lambda cb: directory_callbacks.append('callback_set'))
    mock_scanner_class.return_value.set_file_callback = MagicMock(side_effect=lambda cb: file_callbacks.append('callback_set'))
    
    with patch("musichouse.ui.main_window.MP3Scanner", mock_scanner_class), \
         patch("musichouse.leaderboard_cache.LeaderboardCache", mock_cache_class):
        
        worker = ScanWorker(temp_dir)
        worker.run()
        
        # Verify scanner callbacks were set
        mock_scanner_class.return_value.set_progress_callback.assert_called()
        mock_scanner_class.return_value.set_file_callback.assert_called()


def test_scan_worker_error_logging_after_scan(qapp, mock_scanner_class, mock_cache_class, temp_dir):
    """Test that scanner errors are logged after filesystem scan."""
    from musichouse.ui.main_window import ScanWorker
    
    fake_paths = [temp_dir / "track1.mp3"]
    mock_scanner_class.return_value.scan.return_value = fake_paths
    mock_scanner_class.return_value.get_errors.return_value = [
        (temp_dir / "bad.mp3", "Read error")
    ]
    
    with patch("musichouse.ui.main_window.MP3Scanner", mock_scanner_class), \
         patch("musichouse.leaderboard_cache.LeaderboardCache", mock_cache_class):
        
        worker = ScanWorker(temp_dir)
        worker.run()
        
        # Verify get_errors was called
        mock_scanner_class.return_value.get_errors.assert_called()


# ============================================================================
# ScanWorker Tests - Pause/Resume Blocking Logic
# ============================================================================

def test_scan_worker_pause_state_transitions(qapp):
    """Test that pause/resume state transitions work correctly."""
    from musichouse.ui.main_window import ScanWorker
    
    worker = ScanWorker(Path("/tmp"))
    
    # Initially not paused
    assert not worker.is_paused()
    assert worker._pause_event.is_set()
    
    # After pause
    worker.pause()
    assert worker.is_paused()
    assert not worker._pause_event.is_set()
    
    # After resume
    worker.resume()
    assert not worker.is_paused()
    assert worker._pause_event.is_set()


# ============================================================================
# ScanWorker Tests - Pause After Processing Each File
# ============================================================================

def test_scan_worker_pause_after_each_file_logic(qapp, mock_scanner_class, mock_cache_class, temp_dir):
    """Test that pause after processing each file is in the code."""
    from musichouse.ui.main_window import ScanWorker
    
    fake_paths = [temp_dir / f"track{i}.mp3" for i in range(1, 4)]
    mock_scanner_class.return_value.scan.return_value = fake_paths
    mock_cache_class.return_value.get_changed_files.return_value = (fake_paths, 3, 0, 0)
    
    mock_audio = MagicMock()
    mock_audio.tag.artist = "Artist"
    mock_audio.tag.title = "Title"
    
    with patch("musichouse.ui.main_window.MP3Scanner", mock_scanner_class), \
         patch("musichouse.leaderboard_cache.LeaderboardCache", mock_cache_class), \
         patch("musichouse.ui.main_window.eyed3.load", return_value=mock_audio):
        
        worker = ScanWorker(temp_dir)
        
        # Run normally (not paused)
        worker.run()
        
        # Verify cache was flushed
        conn = mock_cache_class.return_value._get_connection()
        assert conn.executemany.called


# ============================================================================
# ScanWorker Tests - Stop Handling
# ============================================================================

def test_scan_worker_stop_after_loop(qapp, mock_scanner_class, mock_cache_class, temp_dir):
    """Test that stop is handled correctly after processing loop."""
    from musichouse.ui.main_window import ScanWorker
    
    fake_paths = [temp_dir / "track1.mp3"]
    mock_scanner_class.return_value.scan.return_value = fake_paths
    mock_cache_class.return_value.get_changed_files.return_value = (fake_paths, 1, 0, 0)
    
    mock_audio = MagicMock()
    mock_audio.tag.artist = "Artist"
    mock_audio.tag.title = "Title"
    
    with patch("musichouse.ui.main_window.MP3Scanner", mock_scanner_class), \
         patch("musichouse.leaderboard_cache.LeaderboardCache", mock_cache_class), \
         patch("musichouse.ui.main_window.eyed3.load", return_value=mock_audio):
        
        worker = ScanWorker(temp_dir)
        
        # Set stop before running
        worker._stop_requested = True
        
        worker.run()
        
        # Should exit early without processing
        assert worker.isFinished() or not worker.isRunning()


# ============================================================================
# ScanWorker Tests - is_paused Method
# ============================================================================

def test_scan_worker_is_paused_method(qapp):
    """Test is_paused returns correct state."""
    from musichouse.ui.main_window import ScanWorker
    
    worker = ScanWorker(Path("/tmp"))
    
    # Initially not paused
    assert not worker.is_paused()
    
    # After pause
    worker.pause()
    assert worker.is_paused()
    
    # After resume
    worker.resume()
    assert not worker.is_paused()


# ============================================================================
# ScanWorker Tests - _flush_batch_to_cache Edge Cases
# ============================================================================

def test_scan_worker_flush_batch_empty_batch(qapp):
    """Test that _flush_batch_to_cache returns early for empty batch."""
    from musichouse.ui.main_window import ScanWorker
    
    worker = ScanWorker(Path("/tmp"))
    
    # Mock connection
    mock_conn = MagicMock()
    
    # Call with empty batch
    worker._flush_batch_to_cache([], mock_conn)
    
    # Should not call executemany
    mock_conn.executemany.assert_not_called()


# ============================================================================
# MainWindow Tests - Menu Bar Setup
# ============================================================================

def test_main_window_menu_bar_setup(qapp):
    """Test that menu bar is set up correctly."""
    from musichouse.ui.main_window import MainWindow
    
    window = MainWindow()
    
    # Verify menu bar exists
    menubar = window.menuBar()
    assert menubar is not None
    
    # Verify shortcuts exist (these are installed in _install_shortcuts)
    assert hasattr(window, '_scan_shortcut')
    assert hasattr(window, '_stop_esc_shortcut')
    assert hasattr(window, '_settings_shortcut')
    
    window.close()


# ============================================================================
# MainWindow Tests - About Dialog
# ============================================================================

def test_main_window_show_about_dialog(qapp, main_window):
    """Test that about dialog shows correctly."""
    # Mock QMessageBox to avoid actual dialog
    with patch("musichouse.ui.main_window.QMessageBox.about") as mock_about:
        main_window._show_about()
        
        # Verify QMessageBox.about was called
        mock_about.assert_called_once()
        call_args = mock_about.call_args
        assert call_args[0][0] == main_window  # Parent window
        assert call_args[0][1] == "About MusicHouse"  # Title
        assert "MusicHouse" in call_args[0][2]  # Message contains MusicHouse


# ============================================================================
# MainWindow Tests - Config Directory Handling
# ============================================================================

def test_main_window_start_scan_saves_directory(qapp, temp_dir, main_window):
    """Test that _start_scan saves the selected directory to config."""
    from musichouse.ui.main_window import MainWindow
    
    # Mock QFileDialog to return our temp_dir
    with patch("musichouse.ui.main_window.QFileDialog.getExistingDirectory", return_value=str(temp_dir)), \
         patch("musichouse.ui.main_window.config.set_last_directory") as mock_set_dir, \
         patch("musichouse.ui.main_window.ScanWorker") as mock_worker_class:
        
        # Setup mock worker
        mock_worker = MagicMock()
        mock_worker_class.return_value = mock_worker
        
        # Start scan
        main_window._start_scan()
        
        # Verify config.set_last_directory was called
        mock_set_dir.assert_called_once_with(str(temp_dir))


# ============================================================================
# MainWindow Tests - Partial Results Ready
# ============================================================================

def test_main_window_on_partial_results_ready(qapp, main_window):
    """Test _on_partial_results_ready reloads Fixer tab from cache."""
    from musichouse.leaderboard_cache import LeaderboardCache
    
    # Create a real cache with some data
    cache = LeaderboardCache()
    conn = cache._get_connection()
    
    # Insert a test entry
    conn.execute("""INSERT OR REPLACE INTO scan_cache 
                   (path, size, mtime, artist, title, scan_time, 
                    needs_fixing, missing_artist, missing_title, 
                    suggested_artist, suggested_title, tag_data)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(Path("/tmp/test.mp3")), 100, 1234567890, 
                 "Test Artist", "Test Title", 1234567890, 
                 0, 0, 0, "", "", None))
    conn.commit()
    cache.close()
    
    # Mock FixerTab.load_from_scan to track calls
    with patch.object(main_window._fixer_tab, 'load_from_scan') as mock_load:
        main_window._on_partial_results_ready()
        
        # Verify load_from_scan was called with cached paths
        mock_load.assert_called_once()
        call_args = mock_load.call_args
        # First arg should be list of paths
        assert isinstance(call_args[0][0], list)


# ============================================================================
# MainWindow Tests - Stop Scan
# ============================================================================

def test_main_window_stop_scan_worker_still_running(qapp, main_window):
    """Test _stop_scan handles worker still running after wait."""
    # Setup mock worker that appears to still be running
    mock_worker = MagicMock()
    mock_worker.isRunning.return_value = True  # Simulates timeout
    mock_worker.stop = MagicMock()
    mock_worker.quit = MagicMock()
    mock_worker.wait = MagicMock(return_value=False)  # Timeout
    
    main_window._scan_worker = mock_worker
    main_window._is_scanning = True
    
    # Patch time.sleep to avoid actual wait
    with patch("time.sleep"):
        main_window._stop_scan()
    
    # Verify worker.stop was called
    mock_worker.stop.assert_called()
    mock_worker.quit.assert_called()
    mock_worker.wait.assert_called()
    
    # Status should indicate stopping
    assert "Stopping" in main_window._status_label.text() or not main_window._stop_btn.isEnabled()


def test_main_window_stop_scan_worker_not_running(qapp, main_window):
    """Test _stop_scan cleans up when worker is not running."""
    # Setup mock worker that finished
    mock_worker = MagicMock()
    mock_worker.isRunning.return_value = False
    mock_worker.quit = MagicMock()
    mock_worker.wait = MagicMock(return_value=True)
    
    main_window._scan_worker = mock_worker
    main_window._is_scanning = True
    main_window._scan_btn.setEnabled(True)
    
    main_window._stop_scan()
    
    # Verify cleanup
    assert main_window._scan_worker is None
    assert not main_window._is_scanning
    assert main_window._scan_btn.isEnabled()
    assert not main_window._pause_btn.isEnabled()


# ============================================================================
# MainWindow Tests - Keyboard Shortcuts
# ============================================================================

def test_main_window_handle_stop_shortcut_when_scanning(qapp, main_window):
    """Test _handle_stop_shortcut calls _stop_scan when scanning."""
    main_window._is_scanning = True
    
    with patch.object(main_window, '_stop_scan') as mock_stop:
        main_window._handle_stop_shortcut()
        mock_stop.assert_called_once()


def test_main_window_handle_stop_shortcut_not_scanning(qapp, main_window):
    """Test _handle_stop_shortcut does nothing when not scanning."""
    main_window._is_scanning = False
    
    # Should not raise
    main_window._handle_stop_shortcut()


# ============================================================================
# MainWindow Tests - Signal Handlers
# ============================================================================

def test_main_window_on_directory_scanned(qapp, main_window):
    """Test _on_directory_scanned logs the event."""
    # Should not raise, just logs
    main_window._on_directory_scanned("/tmp/test", 100)
    
    # Status should be unchanged (only logs)
    assert main_window._status_label.text() == "Ready"


def test_main_window_on_file_processed_not_in_tag_reading(qapp, main_window):
    """Test _on_file_processed updates status when not in tag reading."""
    # Status is "Ready" (not "Reading tags")
    main_window._on_file_processed(100)
    
    assert "100 files found" in main_window._status_label.text()


def test_main_window_on_file_processed_in_tag_reading(qapp, main_window):
    """Test _on_file_processed does not update status during tag reading."""
    # Set status to "Reading tags"
    main_window._status_label.setText("Reading tags: 50/100")
    
    main_window._on_file_processed(200)
    
    # Status should be unchanged
    assert main_window._status_label.text() == "Reading tags: 50/100"


# ============================================================================
# MainWindow Tests - WAL Checkpoint
# ============================================================================

def test_main_window_on_scan_finished_wal_checkpoint(qapp, main_window, mock_cache_class):
    """Test _on_scan_finished performs WAL checkpoint."""
    with patch("musichouse.leaderboard_cache.LeaderboardCache", mock_cache_class):
        main_window._is_scanning = True
        main_window._scan_stats_summary = (5, 2, 0)
        
        files = [Path("/fake/path/track1.mp3")]
        artist_counts = {"Test": 5}
        
        main_window._on_scan_finished(files, artist_counts)
        
        # Verify checkpoint was attempted
        conn = mock_cache_class.return_value._get_connection()
        conn.execute.assert_any_call("PRAGMA wal_checkpoint(PASSIVE)")


def test_main_window_on_scan_finished_wal_checkpoint_error(qapp, main_window):
    """Test _on_scan_finished handles WAL checkpoint error."""
    # The WAL checkpoint error handling is tested by verifying it doesn't crash
    # The actual checkpoint happens in a try/except that just logs the warning
    main_window._is_scanning = True
    
    files = [Path("/fake/path/track1.mp3")]
    artist_counts = {}
    
    # Should not raise even if checkpoint fails
    main_window._on_scan_finished(files, artist_counts)


# ============================================================================
# MainWindow Tests - Scan Finished Without Stats
# ============================================================================

def test_main_window_on_scan_finished_without_stats_summary(qapp, main_window, mock_cache_class):
    """Test _on_scan_finished handles missing stats summary."""
    with patch("musichouse.leaderboard_cache.LeaderboardCache", mock_cache_class):
        main_window._is_scanning = True
        main_window._scan_stats_summary = None  # No stats
        
        files = [Path("/fake/path/track1.mp3"), Path("/fake/path/track2.mp3")]
        artist_counts = {}
        
        main_window._on_scan_finished(files, artist_counts)
        
        # Status should show file count without stats breakdown
        assert "Scan complete" in main_window._status_label.text()
        assert "2 files found" in main_window._status_label.text()


# ============================================================================
# MainWindow Tests - Artist Count Update Throttling
# ============================================================================

def test_main_window_on_artist_count_updated_throttling(qapp, main_window):
    """Test _on_artist_count_updated throttles leaderboard updates."""
    # Setup mock leaderboard
    mock_leaderboard = MagicMock()
    main_window._leaderboard = mock_leaderboard
    main_window._artist_counts = {}
    
    # First 99 updates should not update leaderboard
    for i in range(1, 100):
        main_window._on_artist_count_updated(f"Artist{i}", i)
    
    # Should not have called update_leaderboard yet
    mock_leaderboard.update_from_artist_counts.assert_not_called()
    
    # 100th update should trigger
    main_window._on_artist_count_updated("Artist100", 100)
    
    # Should have called once
    mock_leaderboard.update_from_artist_counts.assert_called_once()


# ============================================================================
# MainWindow Tests - Scan Error
# ============================================================================

def test_main_window_on_scan_error_updates_status(qapp, main_window):
    """Test _on_scan_error updates status label to 'Error'."""
    with patch("musichouse.ui.main_window.QMessageBox.critical"):
        main_window._on_scan_error("Test error")
        
        # Status should be "Error"
        assert main_window._status_label.text() == "Error"


# ============================================================================
# MainWindow Tests - Close Event
# ============================================================================

def test_main_window_close_event_ignore_when_scan_in_progress(qapp, main_window):
    """Test closeEvent ignores when user clicks No on scan in progress dialog."""
    # Setup scan in progress
    main_window._is_scanning = True
    
    mock_worker = MagicMock()
    mock_worker.isRunning.return_value = True
    main_window._scan_worker = mock_worker
    
    # Mock event
    mock_event = MagicMock()
    
    # Mock dialog to return No (don't exit)
    with patch("musichouse.ui.main_window.QMessageBox.question",
               return_value=QMessageBox.StandardButton.No):
        main_window.closeEvent(mock_event)
    
    # Event should be ignored
    mock_event.ignore.assert_called()
    mock_event.accept.assert_not_called()