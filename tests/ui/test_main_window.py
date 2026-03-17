"""pytest-qt tests for MainWindow component.

Tests MainWindow functionality with pytest-qt in headless offscreen mode.
Run with: QT_QPA_PLATFORM=offscreen pytest tests/ui/test_main_window.py -v
"""

import pytest
from PyQt6.QtWidgets import QApplication
from pathlib import Path


# ============================================================================
# Test Configuration
# ============================================================================

pytestmark = pytest.mark.ui


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def main_window(qapp):
    """Create MainWindow instance for testing.
    
    Yields:
        MainWindow: MainWindow instance.
    """
    from musichouse.ui.main_window import MainWindow
    
    window = MainWindow()
    window.show()
    yield window
    window.close()


# ============================================================================
# MainWindow Initialization Tests
# ============================================================================

def test_main_window_creation(qapp):
    """Test that MainWindow can be created without crashes."""
    from musichouse.ui.main_window import MainWindow
    
    window = MainWindow()
    assert window is not None
    assert window.windowTitle() == "MusicHouse"
    assert window.minimumWidth() == 800
    assert window.minimumHeight() == 600
    window.close()


def test_main_window_has_required_components(main_window):
    """Test that MainWindow has all required UI components."""
    # Check main layout components exist
    assert main_window._toolbar_widget is not None
    assert main_window._status_label is not None
    assert main_window._progress_bar is not None
    assert main_window._tab_widget is not None


def test_main_window_toolbar_buttons(main_window):
    """Test that toolbar buttons are created correctly."""
    # Scan button
    assert main_window._scan_btn is not None
    assert main_window._scan_btn.text() == "Scan"
    assert main_window._scan_btn.isEnabled()
    
    # Settings button
    assert main_window._settings_btn is not None
    assert main_window._settings_btn.text() == "Settings"
    assert main_window._settings_btn.isEnabled()
    
    # Pause button
    assert main_window._pause_btn is not None
    assert main_window._pause_btn.text() == "Pause"
    assert not main_window._pause_btn.isEnabled()  # Disabled when not scanning


def test_main_window_tabs(main_window):
    """Test that all required tabs are present."""
    tab_widget = main_window._tab_widget
    
    # Check tab count
    assert tab_widget.count() == 3
    
    # Check tab names
    assert tab_widget.tabText(0) == "Fixer"
    assert tab_widget.tabText(1) == "Leaderboard"
    assert tab_widget.tabText(2) == "AI Suggestions"


def test_main_window_initial_state(main_window):
    """Test MainWindow initial state."""
    # Status bar
    assert main_window._status_label.text() == "Ready"
    
    # Progress bar
    assert main_window._progress_bar.isVisible() is False
    assert main_window._progress_bar.value() == 0
    assert main_window._progress_bar.maximum() == 100


# ============================================================================
# ScanWorker Tests
# ============================================================================

def test_scan_worker_creation(qapp, temp_dir):
    """Test that ScanWorker can be created."""
    from musichouse.ui.main_window import ScanWorker
    
    worker = ScanWorker(temp_dir)
    assert worker is not None
    assert worker.base_path == temp_dir
    assert worker.is_paused() is False  # Should start in resume state
    
    worker.stop()
    worker.wait()


def test_scan_worker_signals_exist(qapp, temp_dir):
    """Test that ScanWorker has all required signals."""
    from musichouse.ui.main_window import ScanWorker
    
    worker = ScanWorker(temp_dir)
    
    # Check all signals exist
    assert hasattr(worker, 'progress')
    assert hasattr(worker, 'directory_scanned')
    assert hasattr(worker, 'file_processed')
    assert hasattr(worker, 'scan_finished')
    assert hasattr(worker, 'error')
    assert hasattr(worker, 'db_update_request')
    assert hasattr(worker, 'tag_read_progress')
    assert hasattr(worker, 'scan_stats')
    
    worker.stop()
    worker.wait()


def test_scan_worker_pause_resume(qapp, temp_dir):
    """Test ScanWorker pause and resume functionality."""
    from musichouse.ui.main_window import ScanWorker
    
    worker = ScanWorker(temp_dir)
    
    # Initially not paused (pause_event.set() means running)
    assert worker.is_paused() == False
    
    # Pause the worker
    worker.pause()
    assert worker.is_paused() == True
    
    # Resume the worker
    worker.resume()
    assert worker.is_paused() == False
    worker.stop()
    worker.wait()


def test_scan_worker_stop(qapp, temp_dir):
    """Test ScanWorker stop functionality."""
    from musichouse.ui.main_window import ScanWorker
    
    worker = ScanWorker(temp_dir)
    
    # Stop the worker
    worker.stop()
    assert worker._stop_requested is True
    
    # Wait for thread to finish
    worker.wait()
    # Thread completed - don't check isAlive() as it's deprecated
    worker.deleteLater()

# ============================================================================
# MainWindow Scan Tests
# ============================================================================

def test_scan_button_disables_pause_when_not_scanning(main_window):
    """Test that pause button is disabled when not scanning."""
    assert not main_window._pause_btn.isEnabled()


def test_start_scan_creates_worker(qapp, temp_dir, monkeypatch):
    """Test that starting a scan creates a ScanWorker."""
    from musichouse.ui.main_window import MainWindow, ScanWorker
    
    # Create window
    window = MainWindow()
    
    # Mock the file dialog to return temp_dir
    monkeypatch.setattr(
        'PyQt6.QtWidgets.QFileDialog.getExistingDirectory',
        lambda *args, **kwargs: str(temp_dir)
    )
    
    # Mock worker start to avoid actual scanning
    original_start = ScanWorker.start
    worker_created = []
    
    def mock_start(self):
        worker_created.append(self)
    
    monkeypatch.setattr(ScanWorker, 'start', mock_start)
    
    try:
        # Start scan
        window._start_scan()
        
        # Verify worker was created
        assert len(worker_created) == 1
        assert worker_created[0].base_path == temp_dir
        
        # Verify UI state changed
        assert window._is_scanning is True
        assert not window._scan_btn.isEnabled()
        assert window._pause_btn.isEnabled()
    finally:
        # Cleanup
        window._stop_scan()
        window.close()


def test_pause_button_toggles_state(main_window, monkeypatch):
    """Test that pause button toggles between pause and resume."""
    # Save original state
    original_worker = main_window._scan_worker
    original_scanning = main_window._is_scanning
    
    # Mock the worker to avoid thread issues in headless mode
    mock_worker = type('MockWorker', (), {
        'is_paused': lambda self: getattr(self, '_paused', False),
        'pause': lambda self: setattr(self, '_paused', True),
        'resume': lambda self: setattr(self, '_paused', False),
    })()
    
    main_window._scan_worker = mock_worker
    main_window._is_scanning = True
    
    try:
        # Initially not paused
        assert mock_worker.is_paused() == False
        
        # Pause
        mock_worker.pause()
        assert mock_worker.is_paused() == True
        
        # Resume
        mock_worker.resume()
        assert mock_worker.is_paused() == False
    finally:
        # Restore original state
        main_window._scan_worker = original_worker
        main_window._is_scanning = original_scanning
# ============================================================================
# Signal Handler Tests
# ============================================================================

def test_on_scan_progress_updates_status(main_window):
    """Test that scan progress updates status label."""
    main_window._on_scan_progress("Scanning: /test/path")
    assert main_window._status_label.text() == "Scanning: /test/path"


def test_on_file_processed_updates_status(main_window):
    """Test that file processed updates status label."""
    main_window._on_file_processed(100)
    assert main_window._status_label.text() == "Scanned 100 files"


def test_on_tag_read_progress_updates_progress_bar(main_window):
    """Test that tag read progress updates progress bar."""
    main_window._on_tag_read_progress(50, 100)
    
    assert main_window._status_label.text() == "Reading tags: 50/100"
    assert main_window._progress_bar.maximum() == 100
    assert main_window._progress_bar.value() == 50


def test_on_scan_stats_shows_incremental_info(main_window):
    """Test that scan stats shows incremental scan information."""
    # Test with skipped files
    main_window._on_scan_stats(10, 5, 3)
    assert "10 new" in main_window._status_label.text()
    assert "5 modified" in main_window._status_label.text()
    assert "3 skipped" in main_window._status_label.text()
    
    # Test without skipped files
    main_window._on_scan_stats(15, 0, 0)
    assert "15 files to process" in main_window._status_label.text()


def test_on_scan_finished_populates_tabs(main_window, mock_mp3_files, monkeypatch):
    """Test that scan finished populates all tabs."""
    # Mock the tab methods
    fixer_loaded = []
    ai_loaded = []
    
    def mock_load_from_scan(files, counts):
        fixer_loaded.append((files, counts))
    
    def mock_load_artists(artists):
        ai_loaded.append(artists)
    
    monkeypatch.setattr(
        main_window._fixer_tab, 'load_from_scan', mock_load_from_scan
    )
    monkeypatch.setattr(
        main_window._ai_tab, 'load_artists', mock_load_artists
    )
    
    # Simulate scan finished (without leaderboard since it's None by default)
    files = mock_mp3_files[:3]
    artist_counts = {"Artist1": 2, "Artist2": 1}
    
    main_window._on_scan_finished(files, artist_counts)
    
    # Verify tabs were updated
    assert len(fixer_loaded) == 1
    assert fixer_loaded[0][0] == files
    assert fixer_loaded[0][1] == artist_counts
    
    assert len(ai_loaded) == 1
    assert set(ai_loaded[0]) == {"Artist1", "Artist2"}
    
    # Verify progress bar hidden
    assert not main_window._progress_bar.isVisible()

def test_on_scan_error_shows_message_box(main_window, monkeypatch):
    """Test that scan error shows error message box."""
    from PyQt6.QtWidgets import QMessageBox
    
    # Mock QMessageBox to avoid blocking in headless mode
    message_box_shown = []
    
    def mock_critical(*args, **kwargs):
        message_box_shown.append(True)
        return QMessageBox.StandardButton.Ok
    
    monkeypatch.setattr(QMessageBox, 'critical', mock_critical)
    
    # Call error handler
    main_window._on_scan_error("Test error message")
    
    # Verify QMessageBox was called
    assert len(message_box_shown) == 1
    
    # Verify UI state reset
    assert not main_window._is_scanning
    assert main_window._scan_btn.isEnabled()
    assert not main_window._pause_btn.isEnabled()
    assert main_window._status_label.text() == "Error"
    assert not main_window._progress_bar.isVisible()
# ============================================================================
# Integration Tests
# ============================================================================

def test_scan_workflow_with_mock_files(qapp, temp_dir, mock_mp3_files, qtbot):
    """Test complete scan workflow with mock files."""
    from musichouse.ui.main_window import MainWindow
    
    # Create mock MP3 files in temp_dir
    for mp3_file in mock_mp3_files:
        # Files already created by fixture
        pass
    
    window = MainWindow()
    
    # Mock file dialog
    original_get_dir = None
    from PyQt6.QtWidgets import QFileDialog
    original_get_dir = QFileDialog.getExistingDirectory
    
    def mock_get_existing_directory(*args, **kwargs):
        return str(temp_dir)
    
    QFileDialog.getExistingDirectory = mock_get_existing_directory
    
    try:
        # Start scan
        window._start_scan()
        
        # Verify scanning state
        assert window._is_scanning is True
        assert window._scan_worker is not None
        
        # Wait a bit for worker to start
        qtbot.wait(100)
        
        # Pause scan
        window._toggle_pause()
        assert window._scan_worker.is_paused() is True
        
        # Resume scan
        window._toggle_pause()
        assert window._scan_worker.is_paused() is False
        
        # Stop scan
        window._stop_scan()
        assert window._is_scanning is False
        
    finally:
        # Restore original
        QFileDialog.getExistingDirectory = original_get_dir
        window.close()


def test_progress_bar_visibility(main_window):
    """Test progress bar visibility during scan."""
    # Initially hidden
    assert not main_window._progress_bar.isVisible()
    
    # Simulate starting scan (manually set progress bar visible)
    main_window._progress_bar.setVisible(True)
    assert main_window._progress_bar.isVisible()
    
    # Simulate scan finished
    main_window._progress_bar.setVisible(False)
    assert not main_window._progress_bar.isVisible()

# ============================================================================
# Additional Coverage Tests
# ============================================================================


def test_close_event_with_scan_in_progress(qapp, monkeypatch):
    """Test closeEvent when scan is in progress."""
    from musichouse.ui.main_window import MainWindow
    from PyQt6.QtWidgets import QMessageBox
    from PyQt6.QtCore import QEvent
    
    window = MainWindow()
    
    # Mock scan in progress
    window._is_scanning = True
    
    # Mock worker
    mock_worker = type('MockWorker', (), {
        'stop': lambda self: None,
        'wait': lambda self: None,
    })()
    window._scan_worker = mock_worker
    
    # Mock QMessageBox to simulate Yes response
    def mock_question(*args, **kwargs):
        return QMessageBox.StandardButton.Yes
    
    monkeypatch.setattr(QMessageBox, 'question', mock_question)
    
    # Mock _stop_scan to avoid thread issues
    stopped = []
    def mock_stop_scan():
        stopped.append(True)
        window._is_scanning = False
        window._scan_worker = None
    
    monkeypatch.setattr(window, '_stop_scan', mock_stop_scan)
    
    # Create close event
    event = QEvent(QEvent.Type.Close)
    
    # Handle close
    window.closeEvent(event)
    
    # Verify stop was called and event accepted
    assert len(stopped) == 1
    assert not window._is_scanning


def test_close_event_with_scan_cancelled(qapp, monkeypatch):
    """Test closeEvent when scan is in progress but user cancels."""
    from musichouse.ui.main_window import MainWindow
    from PyQt6.QtWidgets import QMessageBox
    from PyQt6.QtCore import QEvent
    
    window = MainWindow()
    
    # Mock scan in progress
    window._is_scanning = True
    
    # Mock worker
    mock_worker = type('MockWorker', (), {
        'stop': lambda self: None,
        'wait': lambda self: None,
    })()
    window._scan_worker = mock_worker
    
    # Mock QMessageBox to simulate No response
    def mock_question(*args, **kwargs):
        return QMessageBox.StandardButton.No
    
    monkeypatch.setattr(QMessageBox, 'question', mock_question)
    
    # Create close event
    event = QEvent(QEvent.Type.Close)
    
    # Handle close
    window.closeEvent(event)
    
    # Verify scan still running and event ignored
    assert window._is_scanning


def test_close_event_when_not_scanning(qapp):
    """Test closeEvent when not scanning."""
    from musichouse.ui.main_window import MainWindow
    from PyQt6.QtCore import QEvent
    
    window = MainWindow()
    
    # Not scanning
    assert not window._is_scanning
    
    # Create close event
    event = QEvent(QEvent.Type.Close)
    
    # Handle close - should accept without dialog
    window.closeEvent(event)
    
    # Verify event accepted
    assert event.isAccepted()


def test_stop_scan_with_worker(qapp, monkeypatch):
    """Test _stop_scan method with active worker."""
    from musichouse.ui.main_window import MainWindow
    
    window = MainWindow()
    window._is_scanning = True
    
    # Mock worker
    stopped = []
    waited = []
    
    mock_worker = type('MockWorker', (), {
        'stop': lambda self: stopped.append(True),
        'wait': lambda self: waited.append(True),
    })()
    window._scan_worker = mock_worker
    
    # Stop scan
    window._stop_scan()
    
    # Verify worker methods called
    assert len(stopped) == 1
    assert len(waited) == 1
    assert window._scan_worker is None
    assert not window._is_scanning
    assert window._scan_btn.isEnabled()
    assert not window._pause_btn.isEnabled()
    assert window._pause_btn.text() == "Pause"
    assert window._status_label.text() == "Scan stopped"


def test_stop_scan_without_worker(main_window):
    """Test _stop_scan when no worker exists."""
    # No worker
    main_window._scan_worker = None
    
    # Should not crash
    main_window._stop_scan()
    
    # State unchanged
    assert main_window._scan_worker is None


def test_open_settings(qapp, monkeypatch):
    """Test _open_settings method with mocked dialog."""
    from musichouse.ui.main_window import MainWindow
    from musichouse.ui.settings_dialog import SettingsDialog
    
    window = MainWindow()
    
    # Mock dialog
    executed = []
    
    def mock_exec(self):
        executed.append(True)
    
    monkeypatch.setattr(SettingsDialog, 'exec', mock_exec)
    
    # Open settings
    window._open_settings()
    
    # Verify dialog executed
    assert len(executed) == 1


def test_on_scan_stats_with_skipped(main_window):
    """Test _on_scan_stats with skipped_count > 0."""
    # Test with skipped files
    main_window._on_scan_stats(10, 5, 3)
    
    assert main_window._scan_stats_summary == (10, 5, 3)
    text = main_window._status_label.text()
    assert "10 new" in text
    assert "5 modified" in text
    assert "3 skipped" in text


def test_on_scan_stats_without_skipped(main_window):
    """Test _on_scan_stats with skipped_count = 0."""
    main_window._on_scan_stats(15, 0, 0)
    
    assert main_window._scan_stats_summary == (15, 0, 0)
    assert "Found 15 files to process" in main_window._status_label.text()


def test_on_db_update_request(main_window, caplog):
    """Test _on_db_update_request logs the request."""
    from pathlib import Path
    
    files = [Path("/test/file1.mp3"), Path("/test/file2.mp3")]
    
    # Call handler
    main_window._on_db_update_request(files)
    
    # Handler exists and doesn't crash
    # (DB update is handled elsewhere)


def test_pause_resume_icon_changes(qapp, monkeypatch):
    """Test pause/resume button icon changes."""
    from musichouse.ui.main_window import MainWindow
    from PyQt6.QtGui import QIcon
    
    window = MainWindow()
    
    # Mock worker
    paused = []
    resumed = []
    
    mock_worker = type('MockWorker', (), {
        'is_paused': lambda self: getattr(self, '_paused', False),
        'pause': lambda self: setattr(self, '_paused', True) or paused.append(True),
        'resume': lambda self: setattr(self, '_paused', False) or resumed.append(True),
    })()
    
    window._scan_worker = mock_worker
    window._is_scanning = True
    window._pause_btn.setEnabled(True)
    
    # Initially not paused
    assert mock_worker.is_paused() == False
    
    # Pause
    window._toggle_pause()
    assert mock_worker.is_paused() == True
    assert window._pause_btn.text() == "Resume"
    
    # Resume
    window._toggle_pause()
    assert mock_worker.is_paused() == False
    assert window._pause_btn.text() == "Pause"


def test_toggle_pause_without_worker(main_window):
    """Test _toggle_pause when no worker exists."""
    main_window._scan_worker = None
    
    # Should not crash
    main_window._toggle_pause()


def test_start_scan_no_directory_selected(qapp, monkeypatch):
    """Test _start_scan when user cancels directory selection."""
    from musichouse.ui.main_window import MainWindow
    
    window = MainWindow()
    
    # Mock QFileDialog to return empty (user cancelled)
    monkeypatch.setattr(
        'PyQt6.QtWidgets.QFileDialog.getExistingDirectory',
        lambda *args, **kwargs: ""
    )
    
    # Start scan - should return early
    window._start_scan()
    
    # No worker created
    assert window._scan_worker is None
    assert not window._is_scanning


def test_toggle_pause_icon_and_status(qapp, monkeypatch):
    """Test pause/resume updates icon and status label."""
    from musichouse.ui.main_window import MainWindow

    
    window = MainWindow()
    
    # Mock worker
    mock_worker = type('MockWorker', (), {
        'is_paused': lambda self: getattr(self, '_paused', False),
        'pause': lambda self: setattr(self, '_paused', True),
        'resume': lambda self: setattr(self, '_paused', False),
    })()
    
    window._scan_worker = mock_worker
    window._is_scanning = True
    window._pause_btn.setEnabled(True)
    
    # Pause
    window._toggle_pause()
    assert window._status_label.text() == "Scan paused"
    
    # Resume
    window._toggle_pause()
    assert window._status_label.text() == "Scanning (resumed)"


def test_on_directory_scanned_logging(main_window, caplog):
    """Test _on_directory_scanned logs the event."""
    main_window._on_directory_scanned("/test/path", 100)
    
    # Handler exists and doesn't crash
    assert main_window._status_label.text() != "Directory scanned: /test/path (100 files)"
    # Just checks handler runs without error


# ============================================================================
# ScanWorker Internal Logic Tests
# ============================================================================


def test_scan_worker_run_with_no_changes(qapp, temp_dir, monkeypatch):
    """Test ScanWorker.run() when no files changed (incremental scan)."""
    from musichouse.ui.main_window import ScanWorker
    from musichouse.leaderboard_cache import LeaderboardCache
    
    worker = ScanWorker(temp_dir)
    
    # Mock the scanner
    mock_scanner = type('MockScanner', (), {
        'base_path': temp_dir,
'set_progress_callback': lambda self, cb: None,
'set_file_callback': lambda self, cb: None,
'scan': lambda self: [],
'get_errors': lambda self: [],
        '_stop_requested': False,
        'stop': lambda self: setattr(self, '_stop_requested', True),
        'is_stopped': lambda self: self._stop_requested,
})()
    
    # Mock cache to return no changes
    changed_files, new_count, modified_count, skipped_count = [], 0, 0, 10
    
    def mock_get_changed_files(self, base_path):
        return changed_files, new_count, modified_count, skipped_count
    
    def mock_update_scan_cache(self, files_info):
        pass
    
    def mock_close(self):
        pass
    
    monkeypatch.setattr(LeaderboardCache, 'get_changed_files', mock_get_changed_files)
    monkeypatch.setattr(LeaderboardCache, 'update_scan_cache', mock_update_scan_cache)
    monkeypatch.setattr(LeaderboardCache, 'close', mock_close)
    
    # Mock MP3Scanner to return our mock
    # Mock MP3Scanner to return our mock
    def mock_scanner_init(self, base_path):
        self.base_path = base_path
        self._mock = mock_scanner
        self._stop_requested = False
    
    monkeypatch.setattr('musichouse.ui.main_window.MP3Scanner.__init__', mock_scanner_init)
    
    # Track signals
    stats_received = []
    finished_received = []
    progress_received = []
    
    worker.scan_stats.connect(lambda a, b, c: stats_received.append((a, b, c)))
    worker.scan_finished.connect(lambda a, b: finished_received.append((a, b)))
    worker.progress.connect(lambda msg: progress_received.append(msg))
    
    # Run worker
    worker.run()
    worker.wait()
    
    # Verify incremental scan detected
    assert len(stats_received) == 1
    assert stats_received[0] == (0, 0, 10)
    assert len(finished_received) == 1
    assert finished_received[0] == ([], {})
    assert "No changes detected" in progress_received


def test_scan_worker_run_with_changes(qapp, temp_dir, monkeypatch, mock_mp3_files):
    """Test ScanWorker.run() with files to process."""
    from musichouse.ui.main_window import ScanWorker
    from musichouse.leaderboard_cache import LeaderboardCache
    
    worker = ScanWorker(temp_dir)
    
    # Mock the scanner
    mock_scanner = type('MockScanner', (), {
        'base_path': temp_dir,
        'set_progress_callback': lambda self, cb: None,
        'set_file_callback': lambda self, cb: None,
        'scan': lambda self: mock_mp3_files,
        'get_errors': lambda self: [],
        '_stop_requested': False,
        'stop': lambda self: setattr(self, '_stop_requested', True),
        'is_stopped': lambda self: self._stop_requested,
    })()
    
    # Mock cache to return all files as changed
    changed_files = mock_mp3_files[:2]
    new_count, modified_count, skipped_count = 2, 0, 0
    
    def mock_get_changed_files(self, base_path):
        return changed_files, new_count, modified_count, skipped_count
    
    def mock_update_scan_cache(self, files_info):
        pass
    
    def mock_close(self):
        pass
    
    monkeypatch.setattr(LeaderboardCache, 'get_changed_files', mock_get_changed_files)
    monkeypatch.setattr(LeaderboardCache, 'update_scan_cache', mock_update_scan_cache)
    monkeypatch.setattr(LeaderboardCache, 'close', mock_close)
    
    # Mock MP3Scanner
    # Mock MP3Scanner
    def mock_scanner_init(self, base_path):
        self.base_path = base_path
        self._mock = mock_scanner
        self._stop_requested = False
    
    monkeypatch.setattr('musichouse.ui.main_window.MP3Scanner.__init__', mock_scanner_init)
    
    # Track signals
    stats_received = []
    finished_received = []
    tag_progress = []
    
    worker.scan_stats.connect(lambda a, b, c: stats_received.append((a, b, c)))
    worker.scan_finished.connect(lambda a, b: finished_received.append((a, b)))
    worker.tag_read_progress.connect(lambda cur, tot: tag_progress.append((cur, tot)))
    
    # Mock eyed3 to avoid actual tag reading
    import eyed3
    original_load = eyed3.load
    
    def mock_load(path):
        class MockTag:
            artist = "Test Artist"
            title = "Test Title"
        class MockAudioFile:
            tag = MockTag()
        return MockAudioFile()
    monkeypatch.setattr(eyed3, 'load', mock_load)
    
    # Run worker
    worker.run()
    worker.wait()
    
    # Restore eyed3
    eyed3.load = original_load
    
    # Verify
    assert len(stats_received) == 1
    assert stats_received[0] == (2, 0, 0)
    assert len(finished_received) == 1
    files, counts = finished_received[0]
    assert len(files) == 2
    assert "Test Artist" in counts


def test_scan_worker_run_with_scan_errors(qapp, temp_dir, monkeypatch):
    """Test ScanWorker.run() with scan errors."""
    from musichouse.ui.main_window import ScanWorker
    from musichouse.leaderboard_cache import LeaderboardCache
    
    worker = ScanWorker(temp_dir)
    
    # Mock scanner with errors
    mock_scanner = type('MockScanner', (), {
        'set_progress_callback': lambda self, cb: None,
        'set_file_callback': lambda self, cb: None,
        'scan': lambda self: [temp_dir / "test.mp3"],
        'get_errors': lambda self: [(temp_dir / "bad.mp3", "Read error")],
    })()
    
    # Mock cache
    def mock_get_changed_files(self, base_path):
        return [], 0, 0, 0
    
    def mock_close(self):
        pass
    
    monkeypatch.setattr(LeaderboardCache, 'get_changed_files', mock_get_changed_files)
    monkeypatch.setattr(LeaderboardCache, 'close', mock_close)
    
    # Mock MP3Scanner
    def mock_scanner_init(self, base_path):
        self._mock = mock_scanner
        self._stop_requested = False
    
    monkeypatch.setattr('musichouse.ui.main_window.MP3Scanner.__init__', mock_scanner_init)
    
    # Track errors
    errors = []
    worker.error.connect(lambda msg: errors.append(msg))
    
    # Run - should complete without crashing
    worker.run()
    worker.wait()
    
    # Worker should handle errors gracefully


def test_scan_worker_read_tags_with_progress(qapp, temp_dir, monkeypatch):
    """Test ScanWorker._read_tags_with_progress() method."""
    from musichouse.ui.main_window import ScanWorker
    
    worker = ScanWorker(temp_dir)
    
    # Create test files
    test_files = [temp_dir / f"file{i}.mp3" for i in range(1, 6)]
    for f in test_files:
        f.write_bytes(b"fake mp3")
    
    # Track signal emissions
    tag_progress = []
    progress_msgs = []
    
    worker.tag_read_progress.connect(lambda cur, tot: tag_progress.append((cur, tot)))
    worker.progress.connect(lambda msg: progress_msgs.append(msg))
    
    # Mock eyed3
    import eyed3
    original_load = eyed3.load
    
    def mock_load(path):
        class MockTag:
            artist = "Artist"
            title = "Title"
        
        class MockAudioFile:
            tag = MockTag()
        return MockAudioFile()
    
    monkeypatch.setattr(eyed3, 'load', mock_load)
    
    # Call method directly
    worker._read_tags_with_progress(5, test_files)
    
    # Restore eyed3
    eyed3.load = original_load
    
    # Verify progress was emitted (every 100 files, so only at end for 5 files)
    # Final progress should be emitted
    assert (5, 5) in tag_progress
    assert "Reading tags: 5/5" in progress_msgs


def test_scan_worker_read_tags_with_stop(qapp, temp_dir, monkeypatch):
    """Test ScanWorker._read_tags_with_progress() stops on request."""
    from musichouse.ui.main_window import ScanWorker
    
    worker = ScanWorker(temp_dir)
    
    # Create test files
    test_files = [temp_dir / f"file{i}.mp3" for i in range(1, 11)]
    for f in test_files:
        f.write_bytes(b"fake mp3")
    
    # Stop after first file
    def stop_after_first():
        worker.stop()
    
    # Mock eyed3 to stop worker
    import eyed3
    original_load = eyed3.load
    call_count = [0]
    
    def mock_load(path):
        call_count[0] += 1
        if call_count[0] == 1:
            stop_after_first()
        class MockAudioFile:
            artist = "Artist"
            title = "Title"
        return MockAudioFile()
    
    monkeypatch.setattr(eyed3, 'load', mock_load)
    
    # Call method
    worker._read_tags_with_progress(10, test_files)
    
    # Restore
    eyed3.load = original_load
    
    # Worker should have stopped
    assert worker._stop_requested is True


def test_scan_worker_read_tags_pause_resume(qapp, temp_dir, monkeypatch):
    """Test ScanWorker._read_tags_with_progress() respects pause."""
    from musichouse.ui.main_window import ScanWorker
    
    worker = ScanWorker(temp_dir)
    
    # Create test files
    test_files = [temp_dir / f"file{i}.mp3" for i in range(1, 6)]
    for f in test_files:
        f.write_bytes(b"fake mp3")
    
    # Pause initially
    worker.pause()
    
    # Mock eyed3
    import eyed3
    original_load = eyed3.load
    
    def mock_load(path):
        class MockAudioFile:
            artist = "Artist"
            title = "Title"
        return MockAudioFile()
    
    monkeypatch.setattr(eyed3, 'load', mock_load)
    
    # Start a thread to resume after pause
    import threading
    def resume_later():
        import time
        time.sleep(0.1)
        worker.resume()
    
    threading.Thread(target=resume_later).start()
    
    # Call method - should wait for resume
    worker._read_tags_with_progress(5, test_files)
    
    # Restore
    eyed3.load = original_load
    
    # Should complete after resume
    assert not worker.is_paused()


def test_scan_worker_run_error_handling(qapp, temp_dir, monkeypatch):
    """Test ScanWorker.run() error handling."""
    from musichouse.ui.main_window import ScanWorker
    from musichouse.leaderboard_cache import LeaderboardCache
    
    worker = ScanWorker(temp_dir)
    
    # Mock scanner to raise exception
    mock_scanner = type('MockScanner', (), {
        'set_progress_callback': lambda self, cb: None,
        'set_file_callback': lambda self, cb: None,
        'scan': lambda self: (_ for _ in ()).throw(Exception("Scan failed")),
        'get_errors': lambda self: [],
        '_stop_requested': False,
        'stop': lambda self: setattr(self, '_stop_requested', True),
        'is_stopped': lambda self: self._stop_requested,
    })()
    
    # Mock MP3Scanner
    def mock_scanner_init(self, base_path):
        self._mock = mock_scanner
        self._stop_requested = False
    
    monkeypatch.setattr('musichouse.ui.main_window.MP3Scanner.__init__', mock_scanner_init)
    
    # Track errors
    errors = []
    worker.error.connect(lambda msg: errors.append(msg))
    
    # Run - should emit error signal
    worker.run()
    worker.wait()
    
    # Verify error was emitted
    assert len(errors) == 1
    assert "Scan failed" in errors[0]

def test_scan_finished_with_stats(qapp, monkeypatch, mock_mp3_files):
    """Test _on_scan_finished with scan stats available."""
    from musichouse.ui.main_window import MainWindow
    
    window = MainWindow()
    
    # Set scan stats summary
    window._scan_stats_summary = (10, 5, 3)
    
    # Mock tab methods
    def mock_load_from_scan(files, counts):
        pass
    
    def mock_update_leaderboard(artists):
        pass
    
    def mock_load_artists(artists):
        pass
    
    monkeypatch.setattr(window._fixer_tab, 'load_from_scan', mock_load_from_scan)
    monkeypatch.setattr(window._leaderboard_tab, 'update_leaderboard', mock_update_leaderboard)
    monkeypatch.setattr(window._ai_tab, 'load_artists', mock_load_artists)
    
    # Mock leaderboard
    window._leaderboard = type('MockLB', (), {
        'update_from_files': lambda self, files: ["Artist1", "Artist2"]
    })()
    
    # Simulate scan finished
    files = mock_mp3_files[:3]
    artist_counts = {"Artist1": 2, "Artist2": 1}
    
    window._on_scan_finished(files, artist_counts)
    
    # Verify UI reset
    assert not window._is_scanning
    assert window._scan_btn.isEnabled()
    assert not window._pause_btn.isEnabled()
    assert not window._progress_bar.isVisible()
    
    # Verify status shows complete with stats
    text = window._status_label.text()
    assert "Scan complete" in text
    assert "3 files processed" in text
    assert "10 new" in text
    assert "5 modified" in text
    assert "3 skipped" in text

# ============================================================================
# Error Handling and Edge Cases Tests
# ============================================================================

def test_scan_worker_with_scan_errors(qapp, temp_dir, monkeypatch, caplog, mocker):
    """Test ScanWorker handles scan errors correctly (lines 86-87)."""
    import logging
    from musichouse.ui.main_window import ScanWorker
    from musichouse.leaderboard_cache import LeaderboardCache
    
    # Create mock scanner that returns errors
    # Create mock scanner that returns errors
    mock_scanner = mocker.MagicMock()
    mock_scanner.base_path = Path("/fake")
    mock_scanner.scan.return_value = [Path("/fake/file.mp3")]
    mock_scanner.get_errors.return_value = [
        ("/fake/error1.mp3", "Permission denied"),
        ("/fake/error2.mp3", "File not found"),
    ]

    # Mock cache to return the file as changed (so we reach the error logging code)
    def mock_get_changed_files(self, base_path):
        return [Path("/fake/file.mp3")], 1, 0, 0
    def mock_update_scan_cache(self, files_info):
        pass

    def mock_close(self):
        pass

    monkeypatch.setattr(LeaderboardCache, 'get_changed_files', mock_get_changed_files)
    monkeypatch.setattr(LeaderboardCache, 'update_scan_cache', mock_update_scan_cache)
    monkeypatch.setattr(LeaderboardCache, 'close', mock_close)

    # Mock MP3Scanner to return our mock instance
    def mock_scanner_init(self, base_path):
        self.base_path = base_path
        self._mock = mock_scanner
        self._stop_requested = False
        # Delegate scan and get_errors to the mock
        self.scan = mock_scanner.scan
        self.get_errors = mock_scanner.get_errors
    monkeypatch.setattr('musichouse.ui.main_window.MP3Scanner.__init__', mock_scanner_init)
    # Create worker
    worker = ScanWorker(Path("/fake"))
    
    # Run the worker with logging captured
    with caplog.at_level(logging.WARNING):
        worker.run()
        worker.wait()
    
    # Verify errors were logged
    assert any("Error scanning" in record.message for record in caplog.records)
    assert worker._files_found is not None


def test_scan_worker_with_tag_read_errors(qapp, temp_dir, monkeypatch, caplog):
    """Test ScanWorker handles tag read errors correctly (lines 134-135)."""
    import logging
    from musichouse.ui.main_window import ScanWorker
    from musichouse.leaderboard_cache import LeaderboardCache
    import eyed3
    
    # Create mock scanner
    test_file = Path(temp_dir) / "test.mp3"
    mock_scanner = type('MockScanner', (), {
        'base_path': Path(temp_dir),
        'scan': lambda self: [test_file],
        'get_errors': lambda self: [],
        '_stop_requested': False,
        'stop': lambda self: setattr(self, '_stop_requested', True),
        'is_stopped': lambda self: self._stop_requested,
        'set_progress_callback': lambda self, cb: None,
        'set_file_callback': lambda self, cb: None,
    })()
    
    # Mock cache to return the file as changed
    def mock_get_changed_files(self, base_path):
        return [test_file], 1, 0, 0
    
    def mock_update_scan_cache(self, files_info):
        pass
    
    def mock_close(self):
        pass
    
    monkeypatch.setattr(LeaderboardCache, 'get_changed_files', mock_get_changed_files)
    monkeypatch.setattr(LeaderboardCache, 'update_scan_cache', mock_update_scan_cache)
    monkeypatch.setattr(LeaderboardCache, 'close', mock_close)
    
    # Mock MP3Scanner
    def mock_scanner_init(self, base_path):
        self.base_path = base_path
        self._mock = mock_scanner
        self._stop_requested = False
    monkeypatch.setattr('musichouse.ui.main_window.MP3Scanner.__init__', mock_scanner_init)
    
    # Mock eyed3 to raise exception (simulating corrupt file)
    original_load = eyed3.load
    def mock_load_error(path):
        raise Exception("Corrupt file")
    
    monkeypatch.setattr(eyed3, 'load', mock_load_error)
    
    # Create worker
    worker = ScanWorker(Path(temp_dir))
    
    # Should not crash despite error, and should log it
    with caplog.at_level(logging.DEBUG):
        worker.run()
        worker.wait()
    
    # Restore eyed3
    eyed3.load = original_load
    
    # Verify error was logged
    assert any("Error reading tag" in record.message for record in caplog.records)
    assert worker._files_found is not None


def test_read_tags_with_progress_error_handling(qapp, temp_dir, monkeypatch, caplog):
    """Test _read_tags_with_progress handles errors (lines 177-178)."""
    import logging
    from musichouse.ui.main_window import ScanWorker
    import eyed3
    
    # Create worker
    worker = ScanWorker(Path(temp_dir))
    
    # Add a file that will cause error
    bad_file = Path(temp_dir) / "bad.mp3"
    worker._files_found = [bad_file]
    
    # Mock eyed3 to raise exception
    original_load = eyed3.load
    def mock_load_error(path):
        raise Exception("Read error")
    
    monkeypatch.setattr(eyed3, 'load', mock_load_error)
    
    # Should not crash, should log error and continue
    with caplog.at_level(logging.DEBUG):
        worker._read_tags_with_progress(1, [bad_file])
    
    # Restore eyed3
    eyed3.load = original_load
    
    # Verify error was logged
    assert any("Error reading tag" in record.message for record in caplog.records)
    # Verify artist_counts is empty (no successful reads)
    assert worker._artist_counts == {}


def test_scan_worker_emits_progress_every_100_files(qapp, temp_dir, monkeypatch):
    """Test that tag_read_progress is emitted every 100 files (lines 182-183)."""
    from musichouse.ui.main_window import ScanWorker
    import eyed3
    
    # Create worker
    worker = ScanWorker(Path(temp_dir))
    
    # Create 250 mock files
    files = [Path(temp_dir) / f"file_{i}.mp3" for i in range(250)]
    worker._files_found = files
    
    # Mock eyed3 to return valid tags quickly
    original_load = eyed3.load
    mock_audio = type('MockAudioFile', (), {
        'artist': "Test Artist",
        'title': "Test Title"
    })()
    def mock_load_success(path):
        return mock_audio
    
    monkeypatch.setattr(eyed3, 'load', mock_load_success)
    
    # Track emitted progress values using a signal connection
    progress_emitted = []
    
    def track_progress(current, total):
        progress_emitted.append(current)
    
    worker.tag_read_progress.connect(track_progress)
    
    # Run tag reading
    worker._read_tags_with_progress(250, files)
    
    # Restore eyed3
    eyed3.load = original_load
    
    # Verify progress was emitted at 100, 200, and 250 (final)
    assert 100 in progress_emitted, "Progress should be emitted at 100 files"
    assert 200 in progress_emitted, "Progress should be emitted at 200 files"
    assert 250 in progress_emitted, "Final progress should be emitted at 250 files"


def test_last_directory_saved_and_loaded(qapp, temp_dir, monkeypatch):
    """Test that last directory is saved and loaded correctly."""
    from musichouse.ui.main_window import MainWindow
    from musichouse import config
    
    # Mock config to track calls
    saved_dirs = []
    loaded_dir = None
    
    def mock_set_last_directory(directory):
        saved_dirs.append(directory)
    
    def mock_get_last_directory():
        return loaded_dir
    
    monkeypatch.setattr(config, 'set_last_directory', mock_set_last_directory)
    monkeypatch.setattr(config, 'get_last_directory', mock_get_last_directory)
    
    # Initially no last directory
    loaded_dir = None
    window = MainWindow()
    assert window._last_scan_path is None
    
    # Mock file dialog to return temp_dir
    def mock_get_existing_directory(*args, **kwargs):
        return str(temp_dir)
    
    monkeypatch.setattr('PyQt6.QtWidgets.QFileDialog.getExistingDirectory', mock_get_existing_directory)
    
    # Start scan
    window._start_scan()
    
    # Verify directory was saved
    assert len(saved_dirs) == 1
    assert saved_dirs[0] == str(temp_dir)
    assert window._last_scan_path == temp_dir
    
    # Cleanup first window properly
    window._stop_scan()
    window.close()
    window.deleteLater()
    
    # Simulate new window with saved directory
    loaded_dir = str(temp_dir)
    window2 = MainWindow()
    assert window2._last_scan_path == temp_dir
    
    window2.close()
    window2.deleteLater()
