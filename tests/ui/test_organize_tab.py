import pytest
from pathlib import Path
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

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
