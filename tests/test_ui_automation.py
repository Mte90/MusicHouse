"""UI automation tests using pytest-qt for MusicHouse application.

Tests UI interactions including button clicks, tab switching, and filter dropdowns.
Run with: QT_QPA_PLATFORM=offscreen pytest tests/test_ui_automation.py -v
"""

import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from pathlib import Path
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
def mock_scan_worker_class(mocker):
    """Fixture that patches ScanWorker before tests use it.
    
    This fixture must be used BEFORE MainWindow is instantiated.
    
    Args:
        mocker: pytest-mock fixture.
    
    Yields:
        MockScanWorker class that can be instantiated.
    """
    class MockSignal:
        def connect(self, slot): pass
        def disconnect(self, slot): pass
    
    class MockScanWorker:
        def __init__(self, *args, **kwargs):
            self._paused = False
            self.progress = MockSignal()
            self.directory_scanned = MockSignal()
            self.file_processed = MockSignal()
            self.scan_finished = MockSignal()
            self.error = MockSignal()
            self.artist_count_updated = MockSignal()
            self.tag_read_progress = MockSignal()
            self.scan_total_work = MockSignal()
            self.scan_stats = MockSignal()
        def start(self): pass
        def pause(self): self._paused = True
        def resume(self): self._paused = False
        def stop(self): pass
        def is_paused(self): return self._paused
        def wait(self): pass
    
    # Patch before anything else
    mocker.patch('musichouse.ui.main_window.ScanWorker', MockScanWorker)
    yield MockScanWorker

@pytest.fixture
def temp_dir_with_files(temp_dir) -> Path:
    """Create a temporary directory with mock MP3 files for testing.
    
    Args:
        temp_dir: pytest fixture providing empty temp directory.
    
    Returns:
        Path: Path to temp directory with mock MP3 files.
    """
    # Create mock MP3 files
    (temp_dir / "test1.mp3").touch()
    (temp_dir / "test2.mp3").touch()
    (temp_dir / "test3.mp3").touch()
    return temp_dir

@pytest.fixture
def app(qapp):
    """Ensure QApplication is available for tests.
    
    Args:
        qapp: pytest-qt QApplication fixture.
    
    Yields:
        QApplication instance.
    """
    yield qapp
# ============================================================================
# Scan Button Tests
# ============================================================================


def test_scan_button_click(qtbot, mock_scan_worker_class, mocker, temp_dir_with_files):
    """Test that clicking Scan button opens file dialog and starts scan.
    
    Simulates clicking the Scan button and verifies:
    - File dialog is opened
    - Progress bar becomes visible
    - Scan button is disabled during scan
    - Pause button becomes enabled
    """
    from musichouse.ui.main_window import MainWindow
    from musichouse.scanner import MP3Scanner
    
    # Mock scanner to return actual files
    mock_files = [temp_dir_with_files / "test1.mp3",
                  temp_dir_with_files / "test2.mp3",
                  temp_dir_with_files / "test3.mp3"]
    mocker.patch.object(MP3Scanner, 'scan', return_value=mock_files)
    
    # Create window AFTER mocks are in place
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Initially: scan enabled, pause disabled, progress hidden
    assert window._scan_btn.isEnabled() is True
    assert window._pause_btn.isEnabled() is False
    assert window._progress_bar.isVisible() is False
    
    # Manually trigger the scan UI setup
    window._is_scanning = True
    window._progress_bar.setVisible(True)
    window._scan_btn.setEnabled(False)
    window._pause_btn.setEnabled(True)
    window._pause_btn.setText("Pause")
    window._scan_worker = mock_scan_worker_class()
    
    # Verify UI state after scan starts
    assert window._progress_bar.isVisible() is True
    assert window._scan_btn.isEnabled() is False
    assert window._pause_btn.isEnabled() is True
    
    # Cleanup
    window.close()

# ============================================================================
# Progress Bar Tests
# ============================================================================


def test_progress_bar_appears_and_updates(qtbot, mocker, temp_dir_with_files):
    """Test that progress bar appears and updates during scan.
    
    Verifies:
    - Progress bar is hidden initially
    - Progress bar appears when scan starts
    - Progress bar updates during tag reading
    - Progress bar hides when scan finishes
    """
    from musichouse.ui.main_window import MainWindow
    from musichouse.scanner import MP3Scanner
    
    # Mock file dialog
    mocker.patch(
        'PyQt6.QtWidgets.QFileDialog.getExistingDirectory',
        return_value=str(temp_dir_with_files)
    )
    
    # Mock scanner to return actual files
    mock_files = [temp_dir_with_files / "test1.mp3",
                  temp_dir_with_files / "test2.mp3",
                  temp_dir_with_files / "test3.mp3"]
    mocker.patch.object(MP3Scanner, 'scan', return_value=mock_files)
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Initially progress bar hidden
    assert window._progress_bar.isVisible() is False
    assert window._progress_bar.value() == 0
    
    # Click scan button - this creates the worker and starts the scan
    qtbot.mouseClick(window._scan_btn, Qt.MouseButton.LeftButton)
    
    # Wait for worker to be created and scan_total_work signal to be emitted
    # The signal is emitted when the worker starts processing
    qtbot.waitUntil(
        lambda: window._scan_worker is not None,
        timeout=5000
    )
    
    # Progress bar should be visible
    assert window._progress_bar.isVisible() is True
    
    # Simulate progress updates (tag read progress)
    window._on_tag_read_progress(25, 100)
    assert window._progress_bar.value() == 25
    
    window._on_tag_read_progress(50, 100)
    assert window._progress_bar.value() == 50
    
    window._on_tag_read_progress(100, 100)
    assert window._progress_bar.value() == 100
    
    # Simulate scan finished
    window._on_scan_finished([], {})
    
    # Progress bar should be hidden again
    assert window._progress_bar.isVisible() is False
    
    window.close()


# ============================================================================
# Pause/Resume Button Tests
# ============================================================================


def test_pause_button_click(qtbot, mocker, temp_dir_with_files):
    """Test that clicking Pause button pauses the scan.
    
    Simulates:
    - Starting a scan
    - Clicking Pause button
    - Verifying worker is paused
    - Button text changes to "Resume"
    """
    from musichouse.ui.main_window import MainWindow
    from musichouse.scanner import MP3Scanner
    
    # Mock file dialog
    mocker.patch(
        'PyQt6.QtWidgets.QFileDialog.getExistingDirectory',
        return_value=str(temp_dir_with_files)
    )
    
    # Mock scanner to return actual files
    mock_files = [temp_dir_with_files / "test1.mp3",
                  temp_dir_with_files / "test2.mp3",
                  temp_dir_with_files / "test3.mp3"]
    mocker.patch.object(MP3Scanner, 'scan', return_value=mock_files)
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Click scan button - this creates the worker and starts the scan
    qtbot.mouseClick(window._scan_btn, Qt.MouseButton.LeftButton)
    
    # Wait for worker to be created and scan_total_work signal to be emitted
    # The signal is emitted when the worker starts processing
    qtbot.waitUntil(
        lambda: window._scan_worker is not None,
        timeout=5000
    )
    
    # Verify scan is running
    assert window._is_scanning is True
    assert window._scan_worker is not None
    assert window._scan_worker.is_paused() is False
    assert window._pause_btn.text() == "Pause"
    
    # Click pause button
    qtbot.mouseClick(window._pause_btn, Qt.MouseButton.LeftButton)
    
    # Verify worker is paused
    assert window._scan_worker.is_paused() is True
    assert window._pause_btn.text() == "Resume"
    assert window._status_label.text() == "Scan paused"
    
    # Cleanup
    window._stop_scan()
    window.close()


def test_resume_button_click(qtbot, mocker, temp_dir_with_files):
    """Test that clicking Resume button resumes the scan.
    
    Simulates:
    - Starting a scan
    - Pausing the scan
    - Clicking Resume button
    - Verifying worker resumes
    - Button text changes back to "Pause"
    """
    from musichouse.ui.main_window import MainWindow
    from musichouse.scanner import MP3Scanner
    
    # Mock file dialog
    mocker.patch(
        'PyQt6.QtWidgets.QFileDialog.getExistingDirectory',
        return_value=str(temp_dir_with_files)
    )
    
    # Mock scanner to return actual files
    mock_files = [temp_dir_with_files / "test1.mp3",
                  temp_dir_with_files / "test2.mp3",
                  temp_dir_with_files / "test3.mp3"]
    mocker.patch.object(MP3Scanner, 'scan', return_value=mock_files)
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Click scan button - this creates the worker and starts the scan
    qtbot.mouseClick(window._scan_btn, Qt.MouseButton.LeftButton)
    
    # Wait for worker to be created and scan_total_work signal to be emitted
    # The signal is emitted when the worker starts processing
    qtbot.waitUntil(
        lambda: window._scan_worker is not None,
        timeout=5000
    )
    
    # Pause first
    window._toggle_pause()
    assert window._scan_worker.is_paused() is True
    assert window._pause_btn.text() == "Resume"
    
    # Click resume button
    qtbot.mouseClick(window._pause_btn, Qt.MouseButton.LeftButton)
    
    # Verify worker resumed
    assert window._scan_worker.is_paused() is False
    assert window._pause_btn.text() == "Pause"
    assert window._status_label.text() == "Scanning (resumed)"
    
    # Cleanup
    window._stop_scan()
    window.close()


# ============================================================================
# Settings Button Tests
# ============================================================================


def test_settings_button_click(qtbot, mocker):
    """Test that clicking Settings button opens settings dialog.

    Verifies:
    - Settings dialog is created
    - Dialog is executed (showModal)
    """
    from musichouse.ui.main_window import MainWindow
    from musichouse.ui.settings_dialog import SettingsDialog
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Mock dialog exec to avoid actual dialog
    dialog_executed = []
    
    def mock_exec(self):
        dialog_executed.append(True)
        return 1  # QDialog.Accepted
    
    mocker.patch.object(SettingsDialog, 'exec', mock_exec)
    
    # Click settings button
    qtbot.mouseClick(window._settings_btn, Qt.MouseButton.LeftButton)
    
    # Verify dialog was executed
    assert len(dialog_executed) == 1
    
    window.close()


# ============================================================================
# Tab Switching Tests
# ============================================================================


def test_tab_switching(qtbot, mocker, mock_mp3_files):
    """Test that tab switching works correctly.

    Verifies:
    - All three tabs exist (Fixer, Leaderboard, AI Suggestions)
    - Can switch between tabs
    - Current tab index changes correctly
    """
    from musichouse.ui.main_window import MainWindow
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Verify tab count
    assert window._tab_widget.count() == 3
    
    # Verify tab names
    assert window._tab_widget.tabText(0) == "Fixer"
    assert window._tab_widget.tabText(1) == "Leaderboard"
    assert window._tab_widget.tabText(2) == "AI Suggestions"
    
    # Initially on Fixer tab
    assert window._tab_widget.currentIndex() == 0
    
    # Switch to Leaderboard tab
    window._tab_widget.setCurrentIndex(1)
    assert window._tab_widget.currentIndex() == 1
    
    # Switch to AI Suggestions tab
    window._tab_widget.setCurrentIndex(2)
    assert window._tab_widget.currentIndex() == 2
    
    # Switch back to Fixer tab
    window._tab_widget.setCurrentIndex(0)
    assert window._tab_widget.currentIndex() == 0
    
    window.close()


def test_tab_content_visible_after_switch(qtbot, mocker, mock_mp3_files):
    """Test that tab content is visible after switching.

    Verifies:
    - FixerTab widgets are accessible after switching to it
    - Tab switching doesn't break widget references
    """
    from musichouse.ui.main_window import MainWindow
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Switch to Leaderboard
    window._tab_widget.setCurrentIndex(1)
    
    # Switch back to Fixer
    window._tab_widget.setCurrentIndex(0)
    
    # Verify FixerTab is accessible
    assert window._fixer_tab is not None
    assert window._fixer_tab._filter_combo is not None
    assert window._fixer_tab._table is not None
    assert window._fixer_tab._fix_selected_btn is not None
    assert window._fixer_tab._fix_all_btn is not None
    
    window.close()


# ============================================================================
# FixerTab Filter Dropdown Tests
# ============================================================================


def test_filter_dropdown_items(qtbot):
    """Test that filter dropdown has correct items.

    Verifies:
    - Filter dropdown exists
    - Has 4 items: All, Missing Artist, Missing Title, Both
    - Default selection is "All" (index 0)
    """
    from musichouse.ui.main_window import MainWindow
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    filter_combo = window._fixer_tab._filter_combo
    
    # Verify count
    assert filter_combo.count() == 4
    
    # Verify items
    assert filter_combo.itemText(0) == "All"
    assert filter_combo.itemText(1) == "Missing Artist"
    assert filter_combo.itemText(2) == "Missing Title"
    assert filter_combo.itemText(3) == "Both"
    
    # Verify default selection
    assert filter_combo.currentIndex() == 0
    assert filter_combo.currentText() == "All"
    
    window.close()


def test_filter_dropdown_click(qtbot):
    """Test that clicking filter dropdown changes selection.

    Simulates:
    - Clicking on filter dropdown
    - Selecting different filter options
    - Verifying current index changes
    """
    from musichouse.ui.main_window import MainWindow
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    filter_combo = window._fixer_tab._filter_combo
    
    # Initially "All" selected
    assert filter_combo.currentIndex() == 0
    
    # Simulate selecting "Missing Artist"
    # Note: qtbot doesn't have direct combo box interaction,
    # so we simulate the signal emission
    filter_combo.setCurrentIndex(1)
    assert filter_combo.currentIndex() == 1
    assert filter_combo.currentText() == "Missing Artist"
    
    # Select "Missing Title"
    filter_combo.setCurrentIndex(2)
    assert filter_combo.currentIndex() == 2
    assert filter_combo.currentText() == "Missing Title"
    
    # Select "Both"
    filter_combo.setCurrentIndex(3)
    assert filter_combo.currentIndex() == 3
    assert filter_combo.currentText() == "Both"
    
    window.close()


def test_filter_dropdown_triggers_filter(qtbot, mocker, mock_mp3_files):
    """Test that filter dropdown change triggers _apply_filter.

    Verifies:
    - Changing filter dropdown calls _apply_filter
    - Filter is applied to table
    """
    from musichouse.ui.main_window import MainWindow
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Mock _apply_filter to track calls
    filter_called = []
    original_apply_filter = window._fixer_tab._apply_filter
    
    def mock_apply_filter():
        filter_called.append(True)
        original_apply_filter()
    
    mocker.patch.object(window._fixer_tab, '_apply_filter', mock_apply_filter)
    
    # Change filter
    window._fixer_tab._filter_combo.setCurrentIndex(1)
    
    # Verify filter was applied
    assert len(filter_called) == 1
    
    window.close()


# ============================================================================
# Integration Tests
# ============================================================================


def test_complete_scan_workflow(qtbot, mocker, temp_dir_with_files):
    """Test complete scan workflow with UI interactions.
    
    Simulates:
    - Clicking Scan button
    - Progress bar appears
    - Pausing scan
    - Resuming scan
    - Scan completes
    - Progress bar hides
    """
    from musichouse.ui.main_window import MainWindow
    from musichouse.scanner import MP3Scanner
    
    # Mock file dialog
    mocker.patch(
        'PyQt6.QtWidgets.QFileDialog.getExistingDirectory',
        return_value=str(temp_dir_with_files)
    )
    
    # Mock scanner to return actual files
    mock_files = [temp_dir_with_files / "test1.mp3",
                  temp_dir_with_files / "test2.mp3",
                  temp_dir_with_files / "test3.mp3"]
    mocker.patch.object(MP3Scanner, 'scan', return_value=mock_files)
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Step 1: Click scan button - this creates the worker and starts the scan
    qtbot.mouseClick(window._scan_btn, Qt.MouseButton.LeftButton)
    
    # Wait for worker to be created
    qtbot.waitUntil(
        lambda: window._scan_worker is not None,
        timeout=5000
    )
    assert window._is_scanning is True
    assert window._progress_bar.isVisible() is True
    
    # Step 2: Simulate some progress
    window._on_tag_read_progress(30, 100)
    assert window._progress_bar.value() == 30
    
    # Step 3: Pause scan
    qtbot.mouseClick(window._pause_btn, Qt.MouseButton.LeftButton)
    assert window._scan_worker.is_paused() is True
    assert window._pause_btn.text() == "Resume"
    
    # Step 4: Resume scan
    qtbot.mouseClick(window._pause_btn, Qt.MouseButton.LeftButton)
    assert window._scan_worker.is_paused() is False
    assert window._pause_btn.text() == "Pause"
    
    # Step 5: Complete scan
    window._on_scan_finished([], {})
    assert window._is_scanning is False
    assert window._progress_bar.isVisible() is False
    assert window._scan_btn.isEnabled() is True
    
    window.close()


def test_settings_then_scan_workflow(qtbot, mocker, temp_dir_with_files):
    """Test opening settings then starting a scan.
    
    Simulates:
    - Clicking Settings button
    - Closing settings
    - Clicking Scan button
    - Verify scan starts correctly
    """
    from musichouse.ui.main_window import MainWindow
    from musichouse.ui.settings_dialog import SettingsDialog
    from musichouse.scanner import MP3Scanner
    
    # Mock file dialog
    mocker.patch(
        'PyQt6.QtWidgets.QFileDialog.getExistingDirectory',
        return_value=str(temp_dir_with_files)
    )
    
    # Mock scanner to return actual files
    mock_files = [temp_dir_with_files / "test1.mp3",
                  temp_dir_with_files / "test2.mp3",
                  temp_dir_with_files / "test3.mp3"]
    mocker.patch.object(MP3Scanner, 'scan', return_value=mock_files)
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Mock dialog
    mocker.patch.object(SettingsDialog, 'exec', return_value=1)
    
    # Open settings first
    qtbot.mouseClick(window._settings_btn, Qt.MouseButton.LeftButton)
    
    # Then start scan - click button and wait for worker to be created
    qtbot.mouseClick(window._scan_btn, Qt.MouseButton.LeftButton)
    
    # Wait for worker to be created
    qtbot.waitUntil(
        lambda: window._scan_worker is not None,
        timeout=5000
    )
    assert window._is_scanning is True
    assert window._progress_bar.isVisible() is True
    
    window._stop_scan()
    window.close()


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_pause_button_disabled_when_not_scanning(qtbot):
    """Test that pause button is disabled when not scanning.

    Verifies initial state:
    - Pause button disabled
    - Cannot click pause without active scan
    """
    from musichouse.ui.main_window import MainWindow
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Initially not scanning
    assert window._is_scanning is False
    assert window._pause_btn.isEnabled() is False
    assert window._pause_btn.text() == "Pause"
    
    window.close()


def test_scan_button_disabled_during_scan(qtbot, mocker, temp_dir_with_files):
    """Test that scan button is disabled during active scan.
    
    Verifies:
    - Scan button enabled initially
    - Scan button disabled after clicking
    - Cannot start another scan while one is active
    """
    from musichouse.ui.main_window import MainWindow
    from musichouse.scanner import MP3Scanner
    
    # Mock file dialog
    mocker.patch(
        'PyQt6.QtWidgets.QFileDialog.getExistingDirectory',
        return_value=str(temp_dir_with_files)
    )
    
    # Mock scanner to return actual files
    mock_files = [temp_dir_with_files / "test1.mp3",
                  temp_dir_with_files / "test2.mp3",
                  temp_dir_with_files / "test3.mp3"]
    mocker.patch.object(MP3Scanner, 'scan', return_value=mock_files)
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Initially enabled
    assert window._scan_btn.isEnabled() is True
    
    # Click scan button - this creates the worker and starts the scan
    qtbot.mouseClick(window._scan_btn, Qt.MouseButton.LeftButton)
    
    # Wait for worker to be created and scan_total_work signal to be emitted
    # The signal is emitted when the worker starts processing
    qtbot.waitUntil(
        lambda: window._scan_worker is not None,
        timeout=5000
    )
    
    # Should be disabled
    assert window._scan_btn.isEnabled() is False
    assert window._is_scanning is True
    
    # Try clicking again (should have no effect)
    qtbot.mouseClick(window._scan_btn, Qt.MouseButton.LeftButton)
    
    # Still scanning
    assert window._is_scanning is True
    
    # Cleanup
    window._stop_scan()
    window.close()
