import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import Qt
from musichouse.ui.duplicates_tab import DuplicatesTab
from musichouse.leaderboard_cache import LeaderboardCache

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
