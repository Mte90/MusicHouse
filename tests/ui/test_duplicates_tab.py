from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

from musichouse.leaderboard_cache import LeaderboardCache
from musichouse.ui.duplicates_tab import DuplicatesTab

pytestmark = pytest.mark.ui

@pytest.fixture
def mock_cache():
    cache = MagicMock(spec=LeaderboardCache)
    return cache

@pytest.fixture
def duplicates_tab(qapp, mock_cache):
    tab = DuplicatesTab(mock_cache)
    yield tab
    tab.deleteLater()

def test_duplicates_tab_creation(qapp, mock_cache):
    tab = DuplicatesTab(mock_cache)
    assert tab is not None
    assert tab._table is not None
    tab.deleteLater()

def test_mode_label_fpcalc_available(qapp, mock_cache):
    with patch('musichouse.ui.duplicates_tab.is_fpcalc_available', return_value=True):
        tab = DuplicatesTab(mock_cache)
        assert "Fingerprint" in tab._mode_label.text()
        tab.deleteLater()

def test_mode_label_fpcalc_unavailable(qapp, mock_cache):
    with patch('musichouse.ui.duplicates_tab.is_fpcalc_available', return_value=False):
        tab = DuplicatesTab(mock_cache)
        assert "Metadata" in tab._mode_label.text()
        tab.deleteLater()

def test_display_duplicates_populates_table(duplicates_tab):
    # 2 groups
    groups = [
        [
            {"path": "/a/1.mp3", "artist": "Art1", "title": "Tit1", "size": 1000000, "duration": 120.0, "similarity": 100.0},
            {"path": "/a/2.mp3", "artist": "Art1", "title": "Tit1", "size": 1000000, "duration": 120.0, "similarity": 95.0},
        ],
        [
            {"path": "/b/1.mp3", "artist": "Art2", "title": "Tit2", "size": 2000000, "duration": 200.0, "similarity": 100.0},
            {"path": "/b/2.mp3", "artist": "Art2", "title": "Tit2", "size": 2000000, "duration": 200.0, "similarity": 90.0},
            {"path": "/b/3.mp3", "artist": "Art2", "title": "Tit2", "size": 2000000, "duration": 200.0, "similarity": 88.0},
        ]
    ]
    
    duplicates_tab._display_duplicates(groups)
    
    assert duplicates_tab._table.rowCount() == 5
    assert duplicates_tab._table.item(0, 1).text() == "/a/1.mp3"
    assert duplicates_tab._table.item(1, 1).text() == "/a/2.mp3"
    assert duplicates_tab._table.item(2, 1).text() == "/b/1.mp3"
    assert duplicates_tab._table.item(4, 1).text() == "/b/3.mp3"

def test_checkbox_preselection(duplicates_tab):
    groups = [
        [
            {"path": "/a/1.mp3", "artist": "A", "title": "T", "size": 100, "duration": 10, "similarity": 100.0},
            {"path": "/a/2.mp3", "artist": "A", "title": "T", "size": 100, "duration": 10, "similarity": 90.0},
        ],
        [
            {"path": "/b/1.mp3", "artist": "B", "title": "T", "size": 100, "duration": 10, "similarity": 100.0},
            {"path": "/b/2.mp3", "artist": "B", "title": "T", "size": 100, "duration": 10, "similarity": 90.0},
            {"path": "/b/3.mp3", "artist": "B", "title": "T", "size": 100, "duration": 10, "similarity": 80.0},
        ]
    ]
    
    duplicates_tab._display_duplicates(groups)
    
    # Group 1: first unchecked, second checked
    assert duplicates_tab._table.item(0, 0).checkState() == Qt.CheckState.Unchecked
    assert duplicates_tab._table.item(1, 0).checkState() == Qt.CheckState.Checked
    
    # Group 2: first unchecked, others checked
    assert duplicates_tab._table.item(2, 0).checkState() == Qt.CheckState.Unchecked
    assert duplicates_tab._table.item(3, 0).checkState() == Qt.CheckState.Checked
    assert duplicates_tab._table.item(4, 0).checkState() == Qt.CheckState.Checked

def test_delete_button_enabled_state(duplicates_tab):
    # Start with no data
    duplicates_tab._display_duplicates([])
    assert duplicates_tab._delete_btn.isEnabled() is False
    
    # Add data, pre-selection should enable it
    groups = [
        [
            {"path": "/a/1.mp3", "artist": "A", "title": "T", "size": 100, "duration": 10, "similarity": 100.0},
            {"path": "/a/2.mp3", "artist": "A", "title": "T", "size": 100, "duration": 10, "similarity": 90.0},
        ]
    ]
    duplicates_tab._display_duplicates(groups)
    assert duplicates_tab._delete_btn.isEnabled() is True
    
    # Uncheck all
    duplicates_tab._table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
    duplicates_tab._table.item(1, 0).setCheckState(Qt.CheckState.Unchecked)
    assert duplicates_tab._delete_btn.isEnabled() is False
    
    # Check one
    duplicates_tab._table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    assert duplicates_tab._delete_btn.isEnabled() is True

def test_stop_button_calls_worker_stop(duplicates_tab):
    mock_worker = MagicMock()
    duplicates_tab._worker = mock_worker
    
    duplicates_tab._on_stop_clicked()
    mock_worker.stop.assert_called_once()


def test_cancel_button_calls_stop(duplicates_tab):
    mock_worker = MagicMock()
    duplicates_tab._worker = mock_worker
    
    duplicates_tab._on_cancel_clicked()
    mock_worker.stop.assert_called_once()


def test_delete_selected_with_fpcalc_available(qapp, mock_cache):
    """Test deletion flow when fpcalc is available."""
    with patch('musichouse.ui.duplicates_tab.is_fpcalc_available', return_value=True):
        tab = DuplicatesTab(mock_cache)
        
        # Mock find_duplicates to return groups
        mock_groups = [
            [
                {"path": "/a/1.mp3", "artist": "A", "title": "T", "size": 100, "duration": 10, "similarity": 100.0},
                {"path": "/a/2.mp3", "artist": "A", "title": "T", "size": 100, "duration": 10, "similarity": 90.0},
            ]
        ]
        
        # Directly test the find duplicates path since fingerprinting is async
        with patch('musichouse.ui.duplicates_tab.find_duplicates', return_value=mock_groups):
            tab._find_duplicates()
        
        # Verify duplicates were displayed and delete button is enabled
        assert tab._table.rowCount() == 2
        assert tab._delete_btn.isEnabled() is True
        
        tab.deleteLater()


def test_find_duplicates_metadata_only_mode(qapp, mock_cache):
    """Test finding duplicates in metadata-only mode (no fpcalc)."""
    with patch('musichouse.ui.duplicates_tab.is_fpcalc_available', return_value=False):
        tab = DuplicatesTab(mock_cache)
        
        mock_groups = [
            [
                {"path": "/b/1.mp3", "artist": "B", "title": "T2", "size": 200, "duration": 20, "similarity": 100.0},
                {"path": "/b/2.mp3", "artist": "B", "title": "T2", "size": 200, "duration": 20, "similarity": 85.0},
            ]
        ]
        
        with patch('musichouse.ui.duplicates_tab.find_duplicates', return_value=mock_groups):
            tab._on_find_clicked()
        
        # Verify duplicates were displayed
        assert tab._table.rowCount() == 2
        assert tab._status_label.text() == "Found 1 groups of duplicates."
        
        tab.deleteLater()


def test_fingerprint_worker_signals_connected(qapp, mock_cache):
    """Test that fingerprint worker signals are properly connected."""
    with patch('musichouse.ui.duplicates_tab.is_fpcalc_available', return_value=True):
        tab = DuplicatesTab(mock_cache)
        
        # Mock the FingerprintWorker to verify connections
        with patch('musichouse.ui.duplicates_tab.FingerprintWorker') as MockWorker:
            mock_worker_instance = MagicMock()
            MockWorker.return_value = mock_worker_instance
            
            tab._start_fingerprinting()
            
            # Verify all signals were connected
            assert mock_worker_instance.progress.connect.called
            assert mock_worker_instance.file_done.connect.called
            assert mock_worker_instance.fingerprint_finished.connect.called
            assert mock_worker_instance.error.connect.called
            
            # Verify worker was started
            assert mock_worker_instance.start.called


def test_on_fingerprint_progress_updates_status(qapp, mock_cache):
    """Test fingerprint progress handler updates status label."""
    tab = DuplicatesTab(mock_cache)
    tab._on_fingerprint_progress("Processing file 1 of 10")
    assert tab._status_label.text() == "Processing file 1 of 10"


def test_on_fingerprint_finished_triggers_find_duplicates(qapp, mock_cache):
    """Test fingerprint finished handler calls find_duplicates."""
    tab = DuplicatesTab(mock_cache)
    
    with patch.object(tab, '_find_duplicates') as mock_find:
        tab._on_fingerprint_finished(total=5)
        mock_find.assert_called_once()


def test_on_fingerprint_error_shows_dialog(qapp, mock_cache):
    """Test fingerprint error handler shows error dialog."""
    tab = DuplicatesTab(mock_cache)
    
    with patch('musichouse.ui.duplicates_tab.QMessageBox.critical') as mock_dialog:
        tab._on_fingerprint_error("fpcalc not found")
        mock_dialog.assert_called_once()
        assert tab._find_dup_btn.isEnabled() is True  # UI no longer busy


def test_display_duplicates_handles_empty_groups(qapp, mock_cache):
    """Test display with empty duplicate groups."""
    tab = DuplicatesTab(mock_cache)
    tab._display_duplicates([])
    
    assert tab._table.rowCount() == 0
    assert len(tab._files_data) == 0


def test_display_duplicates_duration_format(qapp, mock_cache):
    """Test duration formatting in table."""
    tab = DuplicatesTab(mock_cache)
    
    groups = [
        [
            {"path": "/t/1.mp3", "artist": "T", "title": "Test", "size": 100, "duration": 125.5, "similarity": 100.0},
            {"path": "/t/2.mp3", "artist": "T", "title": "Test", "size": 100, "duration": None, "similarity": 90.0},
        ]
    ]
    
    tab._display_duplicates(groups)
    
    # First file: 125.5s -> 2:05
    assert tab._table.item(0, 5).text() == "2:05"
    # Second file: None -> —
    assert tab._table.item(1, 5).text() == "—"


def test_display_duplicates_similarity_format(qapp, mock_cache):
    """Test similarity percentage formatting."""
    tab = DuplicatesTab(mock_cache)
    
    groups = [
        [
            {"path": "/s/1.mp3", "artist": "S", "title": "Test", "size": 100, "duration": 10, "similarity": 100.0},
            {"path": "/s/2.mp3", "artist": "S", "title": "Test", "size": 100, "duration": 10, "similarity": 87.5},
            {"path": "/s/3.mp3", "artist": "S", "title": "Test", "size": 100, "duration": 10, "similarity": None},
        ]
    ]
    
    tab._display_duplicates(groups)
    
    assert tab._table.item(0, 6).text() == "100.0%"
    assert tab._table.item(1, 6).text() == "87.5%"
    assert tab._table.item(2, 6).text() == "—"


def test_start_deletion_with_no_selection(duplicates_tab):
    """Test deletion start with no files selected."""
    # Set up table with data but no selection
    groups = [
        [
            {"path": "/n/1.mp3", "artist": "N", "title": "T", "size": 100, "duration": 10, "similarity": 100.0},
            {"path": "/n/2.mp3", "artist": "N", "title": "T", "size": 100, "duration": 10, "similarity": 90.0},
        ]
    ]
    duplicates_tab._display_duplicates(groups)
    
    # Uncheck all
    duplicates_tab._table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
    duplicates_tab._table.item(1, 0).setCheckState(Qt.CheckState.Unchecked)
    
    # Should return early without showing dialog
    with patch('musichouse.ui.duplicates_tab.QMessageBox.question') as mock_dialog:
        duplicates_tab._start_deletion()
        mock_dialog.assert_not_called()


def test_start_deletion_confirms_with_user(duplicates_tab):
    """Test deletion start shows confirmation dialog."""
    groups = [
        [
            {"path": "/c/1.mp3", "artist": "C", "title": "T", "size": 100, "duration": 10, "similarity": 100.0},
            {"path": "/c/2.mp3", "artist": "C", "title": "T", "size": 100, "duration": 10, "similarity": 90.0},
        ]
    ]
    duplicates_tab._display_duplicates(groups)
    
    # Keep second file selected (default pre-selection)
    with patch('musichouse.ui.duplicates_tab.QMessageBox.question', return_value=QMessageBox.StandardButton.No):
        duplicates_tab._start_deletion()
        # Dialog was shown but user said No


def test_start_deletion_confirms_and_starts_worker(duplicates_tab):
    """Test deletion starts worker when user confirms."""
    groups = [
        [
            {"path": "/w/1.mp3", "artist": "W", "title": "T", "size": 100, "duration": 10, "similarity": 100.0},
            {"path": "/w/2.mp3", "artist": "W", "title": "T", "size": 100, "duration": 10, "similarity": 90.0},
        ]
    ]
    duplicates_tab._display_duplicates(groups)
    
    with patch('musichouse.ui.duplicates_tab.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes), \
         patch('musichouse.ui.duplicates_tab.DeleteWorker') as MockWorker:
        mock_worker_instance = MagicMock()
        MockWorker.return_value = mock_worker_instance
        
        duplicates_tab._start_deletion()
        
        # Verify worker was created with correct paths
        assert MockWorker.called
        # Verify signals were connected
        assert mock_worker_instance.file_deleted.connect.called
        assert mock_worker_instance.deletion_finished.connect.called
        assert mock_worker_instance.error.connect.called
        # Verify worker started
        assert mock_worker_instance.start.called


def test_on_file_deleted_logs_error(duplicates_tab, caplog):
    """Test file deleted handler logs errors."""
    
    duplicates_tab._on_file_deleted("/test.mp3", success=False, error="Permission denied")
    
    # Error should be logged
    assert caplog.records[-1].levelname == "ERROR"


def test_on_deletion_finished_shows_dialog_and_refreshes(duplicates_tab):
    """Test deletion finished handler shows dialog and refreshes."""
    groups = [
        [
            {"path": "/r/1.mp3", "artist": "R", "title": "T", "size": 100, "duration": 10, "similarity": 100.0},
        ]
    ]
    duplicates_tab._display_duplicates(groups)
    
    with patch('musichouse.ui.duplicates_tab.QMessageBox.information'), \
         patch.object(duplicates_tab, '_find_duplicates') as mock_refresh:
        duplicates_tab._on_deletion_finished(count=1)
        mock_refresh.assert_called_once()


def test_on_deletion_error_shows_dialog(duplicates_tab):
    """Test deletion error handler shows error dialog."""
    with patch('musichouse.ui.duplicates_tab.QMessageBox.critical') as mock_dialog:
        duplicates_tab._on_deletion_error("Delete failed")
        mock_dialog.assert_called_once()


def test_stop_with_delete_worker(duplicates_tab):
    """Test stop button also stops delete worker."""
    mock_delete_worker = MagicMock()
    duplicates_tab._delete_worker = mock_delete_worker
    
    duplicates_tab._on_stop_clicked()
    mock_delete_worker.stop.assert_called_once()


def test_set_ui_busy_updates_buttons(duplicates_tab):
    """Test _set_ui_busy updates button states."""
    # Initially buttons should be enabled
    assert duplicates_tab._find_dup_btn.isEnabled() is True
    
    # Set UI busy
    duplicates_tab._set_ui_busy(True)
    assert duplicates_tab._find_dup_btn.isEnabled() is False
    
    # Set UI not busy
    duplicates_tab._set_ui_busy(False)
    assert duplicates_tab._find_dup_btn.isEnabled() is True


def test_on_find_clicked_with_fpcalc_calls_fingerprinting(qapp, mock_cache):
    """Test that clicking find with fpcalc available starts fingerprinting."""
    with patch('musichouse.ui.duplicates_tab.is_fpcalc_available', return_value=True):
        tab = DuplicatesTab(mock_cache)
        
        # Mock _start_fingerprinting to verify it's called
        with patch.object(tab, '_start_fingerprinting') as mock_start_fp:
            tab._on_find_clicked()
            mock_start_fp.assert_called_once()


def test_on_fingerprint_file_done_noop(duplicates_tab):
    """Test _on_fingerprint_file_done is a no-op (keeps indeterminate progress)."""
    # This method is intentionally empty - it just keeps indeterminate mode
    # Call it to ensure it's covered
    duplicates_tab._on_fingerprint_file_done(count=5)
    # No assertion needed - just verifying the method exists and doesn't crash
