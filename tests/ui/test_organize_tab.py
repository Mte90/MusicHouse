from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

from musichouse.ui.organize_tab import OrganizeTab


@pytest.fixture
def app(qtbot):
    """Provide a QApplication instance."""
    return QApplication.instance() or QApplication([])

@pytest.fixture
def mock_dependencies():
    """Mock dependencies for OrganizeTab."""
    return {
        "cache": MagicMock(),
        "ai_client": MagicMock(),
        "base_path": Path("/tmp/music_test")
    }

def test_organize_tab_construction(app, mock_dependencies, qtbot):
    """Test if the tab is constructed without errors."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    tab.show()
    assert tab.isVisible()
    assert tab._analyze_btn.text() == "Analyze"
    assert not tab._apply_btn.isEnabled()

def test_on_analysis_finished_populates_table(app, mock_dependencies, qtbot):
    """Test if analysis results correctly populate the table and summary."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    
    result = {
        "moves": [
            {"from": "/path/a", "to": "/path/b", "reason": "Genre match"},
            {"from": "/path/c", "to": "/path/d", "reason": "Artist match"},
        ],
        "renames": [
            {"from": "/path/e", "to": "new_name", "reason": "AI correction"},
        ],
        "folders": [
            {"folder_type": "genre_container", "path": "/p1", "artists": [], "file_count": 0},
            {"folder_type": "mixed", "path": "/p2", "artists": ["A", "B"], "file_count": 5},
            {"folder_type": "misnamed_artist", "path": "/p3", "artists": ["C"], "file_count": 2},
            {"folder_type": "correct_artist", "path": "/p4", "artists": ["D"], "file_count": 1},
        ]
    }
    
    tab._on_analysis_finished(result)
    
    # Check table rows (2 moves + 1 rename = 3)
    assert tab._table.rowCount() == 3
    assert tab._table.item(0, 1).text() == "Move"
    assert tab._table.item(1, 1).text() == "Move"
    assert tab._table.item(2, 1).text() == "Rename"
    assert tab._table.item(0, 3).text() == "→ /path/b"
    assert tab._table.item(2, 3).text() == "→ new_name"
    
    # Check folder summary
    assert "GENRE_CONTAINER: 1" in tab._summary_details.text()
    assert "MIXED: 1" in tab._summary_details.text()
    assert "MISNAMED_ARTIST: 1" in tab._summary_details.text()
    assert "CORRECT_ARTIST: 1" in tab._summary_details.text()

def test_checkbox_enables_apply_button(app, mock_dependencies, qtbot):
    """Test if selecting rows enables the Apply Selected button."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    
    # Mock some data to populate table
    result = {
        "moves": [{"from": "a", "to": "b", "reason": "r"}],
        "renames": [],
        "folders": []
    }
    tab._on_analysis_finished(result)
    
    assert not tab._apply_btn.isEnabled()
    
    # Check the first row
    item = tab._table.item(0, 0)
    item.setCheckState(Qt.CheckState.Checked)
    
    # Trigger the callback manually or via qtbot
    tab._on_checkbox_toggled(item)
    
    assert tab._apply_btn.isEnabled()
    
    # Uncheck
    item.setCheckState(Qt.CheckState.Unchecked)
    tab._on_checkbox_toggled(item)
    assert not tab._apply_btn.isEnabled()

def test_stop_button_calls_worker_stop(app, mock_dependencies, qtbot):
    """Test if Stop button calls worker.stop()."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    
    mock_worker = MagicMock()
    tab._worker = mock_worker
    
    tab._on_stop_clicked()
    mock_worker.stop.assert_called_once()

def test_on_progress_percent_determinate_mode(app, mock_dependencies, qtbot):
    """Test _on_progress_percent handler switches to determinate mode."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    
    # Initially indeterminate
    assert tab._progress_bar.maximum() == 0
    
    # Call with current/total
    tab._on_progress_percent(5, 10)
    
    # Should be determinate with max=10
    assert tab._progress_bar.maximum() == 10
    assert tab._progress_bar.value() == 5

def test_on_progress_percent_indeterminate_mode(app, mock_dependencies, qtbot):
    """Test _on_progress_percent handler switches back to indeterminate mode."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    
    # Set to determinate mode first
    tab._progress_bar.setRange(0, 100)
    tab._progress_bar.setValue(50)
    
    # Call with total=0 (AI phase)
    tab._on_progress_percent(0, 0)
    
    # Should be indeterminate again
    assert tab._progress_bar.maximum() == 0

def test_folder_summary_empty_data(app, mock_dependencies, qtbot):
    """Test folder summary when no folders are present."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    
    tab._on_analysis_finished({"moves": [], "renames": [], "folders": []})
    assert "No folder data available" in tab._summary_details.text()


def test_start_analysis_initializes_state(app, mock_dependencies, qtbot):
    """Test that starting analysis resets state."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    
    # Set up some initial state
    tab._actions_data = [{"type": "Move", "from": "old", "to": "new", "reason": "test"}]
    tab._table.setRowCount(5)
    
    # Mock the worker
    with patch.object(tab, '_set_ui_busy') as mock_busy, \
         patch('musichouse.ui.organize_tab.OrganizeWorker') as MockWorker:
        mock_worker_instance = MagicMock()
        MockWorker.return_value = mock_worker_instance
        
        tab._start_analysis()
        
        # Verify state was reset
        assert len(tab._actions_data) == 0
        assert tab._table.rowCount() == 0
        # Verify worker was created and connected
        assert MockWorker.called
        assert mock_worker_instance.progress.connect.called
        assert mock_worker_instance.progress_percent.connect.called
        assert mock_worker_instance.analysis_finished.connect.called
        assert mock_worker_instance.error.connect.called
        # Verify UI was set to busy
        mock_busy.assert_called_with(True)


def test_on_progress_updates_status(app, mock_dependencies, qtbot):
    """Test progress handler updates status label."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    
    tab._on_progress("Analyzing files...")
    assert tab._status_label.text() == "Analyzing files..."


def test_on_error_shows_dialog(app, mock_dependencies, qtbot):
    """Test error handler shows error dialog."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    
    with patch('musichouse.ui.organize_tab.QMessageBox.critical') as mock_dialog:
        tab._on_error("Analysis failed")
        mock_dialog.assert_called_once()
        assert tab._analyze_btn.isEnabled() is True  # UI no longer busy


def test_on_analysis_finished_empty_result(app, mock_dependencies, qtbot):
    """Test analysis finished with empty result returns early."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    
    # Set up some initial state
    tab._actions_data = [{"type": "Move", "from": "old", "to": "new", "reason": "test"}]
    
    tab._on_analysis_finished({})
    
    # State should be unchanged since result was empty
    assert len(tab._actions_data) == 1


def test_folder_summary_counts_all_types(app, mock_dependencies, qtbot):
    """Test folder summary correctly counts all folder types."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    
    result = {
        "moves": [],
        "renames": [],
        "folders": [
            {"folder_type": "genre_container", "path": "/g1", "artists": [], "file_count": 0},
            {"folder_type": "genre_container", "path": "/g2", "artists": [], "file_count": 0},
            {"folder_type": "correct_artist", "path": "/c1", "artists": ["A"], "file_count": 1},
            {"folder_type": "misnamed_artist", "path": "/m1", "artists": ["B"], "file_count": 2},
            {"folder_type": "misnamed_artist", "path": "/m2", "artists": ["C"], "file_count": 3},
            {"folder_type": "misnamed_artist", "path": "/m3", "artists": ["D"], "file_count": 4},
            {"folder_type": "mixed", "path": "/x1", "artists": ["E", "F"], "file_count": 5},
        ]
    }
    
    tab._on_analysis_finished(result)
    
    summary = tab._summary_details.text()
    assert "GENRE_CONTAINER: 2" in summary
    assert "CORRECT_ARTIST: 1" in summary
    assert "MISNAMED_ARTIST: 3" in summary
    assert "MIXED: 1" in summary


def test_start_apply_with_no_selection(app, mock_dependencies, qtbot):
    """Test apply start with no actions selected."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    
    # Mock some data
    result = {
        "moves": [{"from": "a", "to": "b", "reason": "r"}],
        "renames": [],
        "folders": []
    }
    tab._on_analysis_finished(result)
    
    # Ensure nothing is selected
    assert not tab._apply_btn.isEnabled()
    
    # Should return early without showing dialog
    with patch('musichouse.ui.organize_tab.QMessageBox.question') as mock_dialog:
        tab._start_apply()
        mock_dialog.assert_not_called()


def test_start_apply_confirms_with_user(app, mock_dependencies, qtbot):
    """Test apply start shows confirmation dialog."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    
    result = {
        "moves": [{"from": "x", "to": "y", "reason": "r"}],
        "renames": [],
        "folders": []
    }
    tab._on_analysis_finished(result)
    
    # Select the row
    tab._table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    tab._on_checkbox_toggled(tab._table.item(0, 0))
    
    with patch('musichouse.ui.organize_tab.QMessageBox.question', return_value=QMessageBox.StandardButton.No):
        tab._start_apply()
        # Dialog shown but user said No


def test_start_apply_confirms_and_starts_worker(app, mock_dependencies, qtbot):
    """Test apply starts worker when user confirms."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    
    result = {
        "moves": [{"from": "/src/a.mp3", "to": "/dst/a.mp3", "reason": "genre match"}],
        "renames": [{"from": "/old/b.mp3", "to": "new_b.mp3", "reason": "AI correction"}],
        "folders": []
    }
    tab._on_analysis_finished(result)
    
    # Select both rows
    tab._table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    tab._table.item(1, 0).setCheckState(Qt.CheckState.Checked)
    tab._on_checkbox_toggled(tab._table.item(0, 0))
    
    with patch('musichouse.ui.organize_tab.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes), \
         patch('musichouse.ui.organize_tab.ApplyWorker') as MockWorker:
        mock_worker_instance = MagicMock()
        MockWorker.return_value = mock_worker_instance
        
        tab._start_apply()
        
        # Verify worker was created with correct actions
        assert MockWorker.called
        call_args = MockWorker.call_args[0][0]  # First positional arg
        assert len(call_args) == 2
        assert call_args[0]["type"] == "move"
        assert call_args[1]["type"] == "rename"
        
        # Verify signals were connected
        assert mock_worker_instance.file_applied.connect.called
        assert mock_worker_instance.apply_finished.connect.called
        assert mock_worker_instance.error.connect.called


def test_on_file_applied_logs_error(app, mock_dependencies, qtbot, caplog):
    """Test file applied handler logs errors."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    
    tab._on_file_applied("/test.mp3", success=False, error="Permission denied")
    
    # Error should be logged
    assert caplog.records[-1].levelname == "ERROR"


def test_on_apply_finished_shows_dialog_and_reanalyzes(app, mock_dependencies, qtbot):
    """Test apply finished handler shows dialog and re-analyzes."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    
    with patch('musichouse.ui.organize_tab.QMessageBox.information'), \
         patch.object(tab, '_start_analysis') as mock_reanalyze:
        tab._on_apply_finished(count=3)
        mock_reanalyze.assert_called_once()


def test_on_apply_error_shows_dialog(app, mock_dependencies, qtbot):
    """Test apply error handler shows error dialog."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    
    with patch('musichouse.ui.organize_tab.QMessageBox.critical') as mock_dialog:
        tab._on_apply_error("Apply failed")
        mock_dialog.assert_called_once()


def test_stop_with_no_worker(app, mock_dependencies, qtbot):
    """Test stop button when no worker exists."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    
    # Should not raise an error
    tab._on_stop_clicked()


def test_cancel_button_calls_stop(app, mock_dependencies, qtbot):
    """Test cancel button calls stop."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    
    mock_worker = MagicMock()
    tab._worker = mock_worker
    
    tab._on_cancel_clicked()
    mock_worker.stop.assert_called_once()


def test_set_ui_busy_updates_buttons(app, mock_dependencies, qtbot):
    """Test _set_ui_busy updates button states."""
    tab = OrganizeTab(
        cache=mock_dependencies["cache"],
        ai_client=mock_dependencies["ai_client"],
        base_path=mock_dependencies["base_path"]
    )
    qtbot.addWidget(tab)
    
    # Initially buttons should be enabled
    assert tab._analyze_btn.isEnabled() is True
    
    # Set UI busy
    tab._set_ui_busy(True)
    assert tab._analyze_btn.isEnabled() is False
    
    # Set UI not busy
    tab._set_ui_busy(False)
    assert tab._analyze_btn.isEnabled() is True
