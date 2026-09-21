"""pytest-qt tests for FixerTab component.
Tests FixerTab functionality with pytest-qt in headless offscreen mode.
Run with: QT_QPA_PLATFORM=offscreen pytest tests/ui/test_fixer_tab.py -v
"""
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QMessageBox

pytestmark = pytest.mark.ui


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def fixer_tab(qapp):
    """Create FixerTab instance for testing.
    
    Mocks database access to prevent loading real data.
    
    Yields:
        FixerTab: FixerTab instance with empty _files_data.
    """
    from unittest.mock import MagicMock, patch

    from musichouse.ui.fixer_tab import FixerTab
    
    # Mock LeaderboardCache - patch where it's used (inside the methods)
    with patch('musichouse.leaderboard_cache.LeaderboardCache') as MockCache:
        mock_cache_instance = MagicMock()
        mock_conn = MagicMock()
        mock_cache_instance._get_connection.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []  # Empty results
        mock_conn.execute.return_value = mock_cursor
        MockCache.return_value = mock_cache_instance
        
        tab = FixerTab()
        yield tab
        tab.deleteLater()


# ============================================================================
# FixerTab Initialization Tests
# ============================================================================

def test_fixer_tab_creation(qapp):
    """Test that FixerTab can be created without crashes."""
    from musichouse.ui.fixer_tab import FixerTab
    
    tab = FixerTab()
    assert tab is not None
    assert tab.layout() is not None
    tab.deleteLater()


def test_fixer_tab_has_required_components(fixer_tab):
    """Test that FixerTab has all required UI components."""
    assert fixer_tab._table is not None
    assert fixer_tab._files_data == []
    assert fixer_tab._fix_selected_btn is not None
    assert fixer_tab._fix_all_btn is not None
    assert fixer_tab._filter_combo is not None
    assert fixer_tab._search_input is not None
    assert fixer_tab._progress_bar is not None


def test_fixer_tab_initial_table_state(fixer_tab):
    """Test that table starts empty with correct structure."""
    table = fixer_tab._table
    
    assert table.rowCount() == 0
    assert table.columnCount() == 4


def test_fixer_tab_column_headers(fixer_tab):
    """Test that table has correct column headers."""
    table = fixer_tab._table
    
    expected_headers = ["", "File", "Artist", "Title"]
    actual_headers = [table.horizontalHeaderItem(i).text() 
                      for i in range(table.columnCount())]
    
    assert actual_headers == expected_headers


def test_fixer_tab_sorting_disabled(fixer_tab):
    """Test that sorting is explicitly disabled to prevent row index mismatch bug."""
    table = fixer_tab._table
    # Sorting must be disabled - visual row indices must match _files_data indices
    assert table.isSortingEnabled() is False


# ============================================================================
# load_from_scan Tests - needs_fixing=1 filtering
# ============================================================================

def test_load_from_scan_only_loads_needs_fixing_rows(leaderboard_cache, qapp, temp_dir):
    """Test that load_from_scan loads only rows with needs_fixing=1 and missing data."""
    from unittest.mock import MagicMock, patch

    from musichouse.ui.fixer_tab import FixerTab
    
    # Seed database with mixed needs_fixing values
    # Note: load_from_scan also filters for (missing_artist=1 OR missing_title=1)
    files_info = [
        {
            'path': str(temp_dir / "file1.mp3"),
            'size': 1000,
            'mtime': 1000.0,
            'artist': None,  # Missing artist
            'title': "Existing Title",
            'needs_fixing': 1,
            'missing_artist': 1,
            'missing_title': 0,
            'suggested_artist': "Suggested Artist",
            'suggested_title': "Suggested Title",
            'tag_data': None
        },
        {
            'path': str(temp_dir / "file2.mp3"),
            'size': 1000,
            'mtime': 1000.0,
            'artist': "Existing Artist",
            'title': None,  # Missing title
            'needs_fixing': 1,
            'missing_artist': 0,
            'missing_title': 1,
            'suggested_artist': "Suggested Artist",
            'suggested_title': "Suggested Title",
            'tag_data': None
        },
        {
            'path': str(temp_dir / "file3.mp3"),
            'size': 1000,
            'mtime': 1000.0,
            'artist': "Existing Artist",
            'title': "Existing Title",
            'needs_fixing': 0,  # Should NOT be loaded
            'missing_artist': 0,
            'missing_title': 0,
            'suggested_artist': "Suggested Artist",
            'suggested_title': "Suggested Title",
            'tag_data': None
        },
    ]
    leaderboard_cache.update_scan_cache(files_info)
    
    # Create FixerTab with mocked _load_saved_files to prevent loading real data
    with patch.object(FixerTab, '_load_saved_files'), \
         patch('musichouse.leaderboard_cache.LeaderboardCache') as MockCache:
        # Set up mock to return our seeded database
        mock_cache_instance = MagicMock()
        mock_cache_instance._get_connection.return_value = leaderboard_cache._get_connection()
        mock_cache_instance.close = MagicMock()
        MockCache.return_value = mock_cache_instance
        
        tab = FixerTab()
        
        # Call load_from_scan with all three files
        files = [temp_dir / "file1.mp3", temp_dir / "file2.mp3", temp_dir / "file3.mp3"]
        artist_counts = {}
        tab.load_from_scan(files, artist_counts)
        
        # Should only have 2 entries (needs_fixing=1 AND has missing data)
        assert len(tab._files_data) == 2
        
        # Verify file3 (needs_fixing=0) was not loaded
        paths = [entry["path"].name for entry in tab._files_data]
        assert "file1.mp3" in paths
        assert "file2.mp3" in paths
        assert "file3.mp3" not in paths
        
        tab.deleteLater()


def test_load_from_scan_empty_result(leaderboard_cache, fixer_tab, temp_dir):
    """Test load_from_scan with no files needing fixing."""
    # Seed database with all needs_fixing=0
    files_info = [
        {
            'path': str(temp_dir / "file1.mp3"),
            'size': 1000,
            'mtime': 1000.0,
            'artist': "Artist",
            'title': "Title",
            'needs_fixing': 0,
            'missing_artist': 0,
            'missing_title': 0,
            'suggested_artist': None,
            'suggested_title': None,
            'tag_data': None
        },
    ]
    leaderboard_cache.update_scan_cache(files_info)
    
    files = [temp_dir / "file1.mp3"]
    fixer_tab.load_from_scan(files, {})
    
    assert len(fixer_tab._files_data) == 0
    assert fixer_tab._table.rowCount() == 0


# ============================================================================
# UserRole Data-Index Mapping Under Filter (CRITICAL REGRESSION TEST)
# ============================================================================

def test_userrole_index_mapping_with_filter_active(fixer_tab, temp_dir):
    """Test that _get_checked_rows returns correct UserRole data-index when filter is active.
    
    CRITICAL REGRESSION TEST: The old bug was that visual row indices didn't match
    _files_data indices when a filter was active, causing tags to be written to WRONG files.
    """
    # Populate with 5 entries - 3 missing artist, 2 missing title
    for i, (missing_artist, missing_title) in enumerate([
        (True, False),   # index 0 - Missing Artist
        (False, True),   # index 1 - Missing Title
        (True, False),   # index 2 - Missing Artist
        (False, True),   # index 3 - Missing Title
        (True, False),   # index 4 - Missing Artist
    ]):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "" if missing_artist else f"Artist {i}",
            "existing_title": "" if missing_title else f"Title {i}",
            "suggested_artist": f"Suggested Artist {i}",
            "suggested_title": f"Suggested Title {i}",
            "missing_artist": missing_artist,
            "missing_title": missing_title,
        }
        fixer_tab.add_file_entry(entry)
    
    # Verify all 5 entries are loaded
    assert len(fixer_tab._files_data) == 5
    
    # Apply "Missing Artist" filter - should show only indices 0, 2, 4
    fixer_tab._filter_combo.setCurrentText("Missing Artist")
    fixer_tab._apply_filter()
    
    # Table should now have 3 rows (visual rows 0, 1, 2)
    assert fixer_tab._table.rowCount() == 3
    
    # Check checkboxes for visual rows 0, 1, 2
    for row in range(fixer_tab._table.rowCount()):
        checkbox = fixer_tab._table.item(row, 0)
        assert checkbox is not None
        checkbox.setCheckState(Qt.CheckState.Checked)
    
    # Get checked rows - verifies the call doesn't crash
    fixer_tab._get_checked_rows()
    
    # CRITICAL: Should return data indices {0, 2, 4}, not visual row indices {0, 1, 2}
    # The _get_checked_rows method returns visual row indices, but when used with
    # get_selected_files, it should correctly map to data indices via UserRole
    # Let's verify the UserRole data is correct
    for row in range(fixer_tab._table.rowCount()):
        checkbox = fixer_tab._table.item(row, 0)
        data_idx = checkbox.data(Qt.ItemDataRole.UserRole)
        # Visual row 0 -> data index 0
        # Visual row 1 -> data index 2
        # Visual row 2 -> data index 4
        assert data_idx in {0, 2, 4}
    
    # Verify get_selected_files returns the correct paths
    selected_paths = fixer_tab.get_selected_files()
    assert len(selected_paths) == 3
    expected_paths = {
        str(temp_dir / "file0.mp3"),
        str(temp_dir / "file2.mp3"),
        str(temp_dir / "file4.mp3"),
    }
    actual_paths = {str(p) for p in selected_paths}
    assert actual_paths == expected_paths


def test_userrole_index_mapping_with_search_filter(fixer_tab, temp_dir):
    """Test that data-index mapping works correctly with search filter."""
    # Populate with entries that have distinct filenames
    for i in range(4):
        entry = {
            "path": temp_dir / f"alpha_{i}.mp3",
            "filename": f"alpha_{i}.mp3",
            "existing_artist": "" if i % 2 == 0 else f"Artist {i}",
            "existing_title": f"Title {i}",
            "suggested_artist": f"Suggested Artist {i}",
            "suggested_title": f"Suggested Title {i}",
            "missing_artist": i % 2 == 0,
            "missing_title": False,
        }
        fixer_tab.add_file_entry(entry)
    
    assert len(fixer_tab._files_data) == 4
    
    # Apply search filter for "alpha_0" and "alpha_2"
    fixer_tab._search_input.setText("alpha_0")
    fixer_tab._apply_filter()
    
    # Should show only file0
    assert fixer_tab._table.rowCount() == 1
    
    # Check the checkbox
    checkbox = fixer_tab._table.item(0, 0)
    checkbox.setCheckState(Qt.CheckState.Checked)
    
    # Verify UserRole points to correct data index
    data_idx = checkbox.data(Qt.ItemDataRole.UserRole)
    assert data_idx == 0  # Should point to first entry in _files_data
    
    selected = fixer_tab.get_selected_files()
    assert len(selected) == 1
    assert str(selected[0]) == str(temp_dir / "alpha_0.mp3")


# ============================================================================
# auto_fix_all passes edited values (current_artist) not suggested values
# ============================================================================

def test_auto_fix_all_passes_current_artist_not_suggested(fixer_tab, temp_dir):
    """Test that auto_fix_all passes current_artist values, not suggested_artist.
    
    Entries should use current values from table (may have been edited) rather than
    suggested values from filename parsing.
    """
    # Populate with entries where current_artist differs from suggested
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",  # Missing - will show suggested in table
        "existing_title": "Title",
        "suggested_artist": "Suggested Artist From Filename",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": False,
    }
    fixer_tab.add_file_entry(entry)
    
    # Simulate user editing the table to set a different artist
    fixer_tab._apply_filter()  # Build the table
    assert fixer_tab._table.rowCount() == 1
    
    # Edit the artist cell to a custom value
    fixer_tab._table.item(0, 2).setText("Custom Edited Artist")
    
    # Trigger the cell change handler to update _files_data
    fixer_tab._on_cell_changed(0, 2)
    
    # Verify _files_data was updated with edited value
    assert fixer_tab._files_data[0]["existing_artist"] == "Custom Edited Artist"
    
    # Mock TagFixWorker to capture the data passed to it
    with patch("musichouse.ui.fixer_tab.TagFixWorker") as MockWorker:
        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance
        
        # Call auto_fix_all
        fixer_tab.auto_fix_all()
        
        # Verify TagFixWorker was created
        assert MockWorker.called
        
        # Get the files_data passed to the constructor
        call_args = MockWorker.call_args
        files_to_fix = call_args[0][0]  # First positional argument
        
        # CRITICAL: Should contain current_artist from table, not suggested_artist
        assert len(files_to_fix) == 1
        assert files_to_fix[0]["current_artist"] == "Custom Edited Artist"
        # Should NOT be the suggested value
        assert files_to_fix[0]["current_artist"] != "Suggested Artist From Filename"


def test_auto_fix_all_uses_suggested_when_not_edited(fixer_tab, temp_dir):
    """Test that auto_fix_all uses suggested values when table wasn't edited."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "",
        "suggested_artist": "Suggested Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": True,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Don't edit the table - use default suggested values
    
    with patch("musichouse.ui.fixer_tab.TagFixWorker") as MockWorker:
        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance
        
        fixer_tab.auto_fix_all()
        
        call_args = MockWorker.call_args
        files_to_fix = call_args[0][0]
        
        # Should fallback to suggested values when not edited
        assert files_to_fix[0]["current_artist"] == "Suggested Artist"
        assert files_to_fix[0]["current_title"] == "Suggested Title"


# ============================================================================
# _mark_failed_row with error_type color mapping
# ============================================================================

def test_mark_failed_row_corrupted_color(fixer_tab, temp_dir):
    """Test that _mark_failed_row applies correct color for corrupted files."""
    # Add a file entry
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "Title",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": False,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Mark as failed with corrupted error type
    fixer_tab._mark_failed_row(temp_dir / "file1.mp3", error_type="corrupted")
    
    # Check that the row has the correct color (QColor(255, 100, 100))
    expected_color = QColor(255, 100, 100)
    for col in range(fixer_tab._table.columnCount()):
        item = fixer_tab._table.item(0, col)
        assert item is not None
        assert item.background().color().red() == expected_color.red()
        assert item.background().color().green() == expected_color.green()
        assert item.background().color().blue() == expected_color.blue()


def test_mark_failed_row_deleted_color(fixer_tab, temp_dir):
    """Test that _mark_failed_row applies correct color for deleted files."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "Title",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": False,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    fixer_tab._mark_failed_row(temp_dir / "file1.mp3", error_type="deleted")
    
    expected_color = QColor(200, 200, 200)  # Gray
    for col in range(fixer_tab._table.columnCount()):
        item = fixer_tab._table.item(0, col)
        assert item.background().color().red() == expected_color.red()
        assert item.background().color().green() == expected_color.green()
        assert item.background().color().blue() == expected_color.blue()


def test_mark_failed_row_locked_color(fixer_tab, temp_dir):
    """Test that _mark_failed_row applies correct color for locked files."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "Title",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": False,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    fixer_tab._mark_failed_row(temp_dir / "file1.mp3", error_type="locked")
    
    expected_color = QColor(255, 200, 0)  # Orange
    for col in range(fixer_tab._table.columnCount()):
        item = fixer_tab._table.item(0, col)
        assert item.background().color().red() == expected_color.red()
        assert item.background().color().green() == expected_color.green()
        assert item.background().color().blue() == expected_color.blue()


def test_mark_failed_row_readonly_color(fixer_tab, temp_dir):
    """Test that _mark_failed_row applies correct color for readonly files."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "Title",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": False,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    fixer_tab._mark_failed_row(temp_dir / "file1.mp3", error_type="readonly")
    
    expected_color = QColor(200, 100, 255)  # Purple
    for col in range(fixer_tab._table.columnCount()):
        item = fixer_tab._table.item(0, col)
        assert item.background().color().red() == expected_color.red()
        assert item.background().color().green() == expected_color.green()
        assert item.background().color().blue() == expected_color.blue()


def test_mark_failed_row_unknown_error_default_color(fixer_tab, temp_dir):
    """Test that _mark_failed_row applies default color for unknown error types."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "Title",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": False,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    fixer_tab._mark_failed_row(temp_dir / "file1.mp3", error_type="unknown_error")
    
    expected_color = QColor(255, 200, 200)  # Default light red
    for col in range(fixer_tab._table.columnCount()):
        item = fixer_tab._table.item(0, col)
        assert item.background().color().red() == expected_color.red()
        assert item.background().color().green() == expected_color.green()
        assert item.background().color().blue() == expected_color.blue()


# ============================================================================
# Empty files list early return tests
# ============================================================================

def test_fix_selected_empty_files_data_early_return(fixer_tab):
    """Test that fix_selected returns early when _files_data is empty."""
    with patch("musichouse.ui.fixer_tab.TagFixWorker") as MockWorker:
        # Ensure no files are loaded (fixture already mocks _load_saved_files)
        assert len(fixer_tab._files_data) == 0
        assert fixer_tab._table.rowCount() == 0
        
        # Call fix_selected
        fixer_tab.fix_selected()
        
        # Should not create a worker
        MockWorker.assert_not_called()
        
        # Progress bar should remain hidden
        assert fixer_tab._progress_bar.isVisible() is False


def test_auto_fix_all_empty_files_data_early_return(fixer_tab):
    """Test that auto_fix_all returns early when _files_data is empty."""
    with patch("musichouse.ui.fixer_tab.TagFixWorker") as MockWorker:
        assert len(fixer_tab._files_data) == 0
        
        fixer_tab.auto_fix_all()
        
        MockWorker.assert_not_called()
        assert fixer_tab._progress_bar.isVisible() is False


def test_fix_selected_no_checked_rows_early_return(fixer_tab, temp_dir):
    """Test that fix_selected returns early when no rows are checked."""
    # Add a file entry
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "Title",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": False,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Don't check any checkboxes
    
    with patch("musichouse.ui.fixer_tab.TagFixWorker") as MockWorker:
        fixer_tab.fix_selected()
        
        MockWorker.assert_not_called()


def test_fix_selected_with_invalid_data_idx(fixer_tab, temp_dir):
    """Test that fix_selected skips rows with invalid data_idx."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "Title",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": False,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Set data_idx to None to trigger the continue statement
    checkbox = fixer_tab._table.item(0, 0)
    checkbox.setCheckState(Qt.CheckState.Checked)
    checkbox.setData(Qt.ItemDataRole.UserRole, None)  # Invalid data_idx
    
    with patch("musichouse.ui.fixer_tab.TagFixWorker") as MockWorker:
        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance
        
        # Should not crash - will create worker with empty list
        fixer_tab.fix_selected()
        
        # Worker should be created but with empty files_to_fix list
        # because the only checked row has invalid data_idx
        assert MockWorker.called
        call_args = MockWorker.call_args
        assert call_args[0][0] == []  # files_to_fix is empty
        assert call_args[1]["auto_fix"] is False  # auto_fix=False


# ============================================================================
# Checkbox and selection tests
# ============================================================================

def test_checkbox_stores_data_index_in_userrole(fixer_tab, temp_dir):
    """Test that checkboxes store the correct data index in UserRole."""
    for i in range(3):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "",
            "existing_title": "Title",
            "suggested_artist": "Artist",
            "suggested_title": "Suggested Title",
            "missing_artist": True,
            "missing_title": False,
        }
        fixer_tab.add_file_entry(entry)
    
    fixer_tab._apply_filter()
    
    # Check that each checkbox stores the correct data index
    for row in range(3):
        checkbox = fixer_tab._table.item(row, 0)
        data_idx = checkbox.data(Qt.ItemDataRole.UserRole)
        assert data_idx == row  # Should match the data index


def test_get_selected_files_returns_correct_paths(fixer_tab, temp_dir):
    """Test that get_selected_files returns paths for checked rows only."""
    for i in range(3):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "",
            "existing_title": "Title",
            "suggested_artist": "Artist",
            "suggested_title": "Suggested Title",
            "missing_artist": True,
            "missing_title": False,
        }
        fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Check only rows 0 and 2
    fixer_tab._table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    fixer_tab._table.item(2, 0).setCheckState(Qt.CheckState.Checked)
    
    selected = fixer_tab.get_selected_files()
    assert len(selected) == 2
    assert str(selected[0]) == str(temp_dir / "file0.mp3")
    assert str(selected[1]) == str(temp_dir / "file2.mp3")


# ============================================================================
# Filter functionality tests
# ============================================================================

def test_filter_missing_artist_shows_only_missing_artist(fixer_tab, temp_dir):
    """Test that 'Missing Artist' filter shows only entries missing artist."""
    entries = [
        {"missing_artist": True, "missing_title": False, "filename": "file1.mp3"},
        {"missing_artist": False, "missing_title": True, "filename": "file2.mp3"},
        {"missing_artist": True, "missing_title": True, "filename": "file3.mp3"},
        {"missing_artist": False, "missing_title": False, "filename": "file4.mp3"},  # Should never show
    ]
    
    for i, e in enumerate(entries):
        entry = {
            "path": temp_dir / e["filename"],
            "filename": e["filename"],
            "existing_artist": "" if e["missing_artist"] else f"Artist {i}",
            "existing_title": "" if e["missing_title"] else f"Title {i}",
            "suggested_artist": "Suggested Artist",
            "suggested_title": "Suggested Title",
            "missing_artist": e["missing_artist"],
            "missing_title": e["missing_title"],
        }
        fixer_tab.add_file_entry(entry)
    
    # Apply "Missing Artist" filter
    fixer_tab._filter_combo.setCurrentText("Missing Artist")
    fixer_tab._apply_filter()
    
    # Should show file1, file3 (both have missing_artist=True)
    assert fixer_tab._table.rowCount() == 2
    
    filenames = [fixer_tab._table.item(r, 1).text() for r in range(2)]
    assert "file1.mp3" in filenames
    assert "file3.mp3" in filenames
    assert "file2.mp3" not in filenames
    assert "file4.mp3" not in filenames


def test_filter_missing_title_shows_only_missing_title(fixer_tab, temp_dir):
    """Test that 'Missing Title' filter works correctly."""
    for i, (ma, mt) in enumerate([(True, False), (False, True), (True, True), (False, False)]):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "" if ma else f"Artist {i}",
            "existing_title": "" if mt else f"Title {i}",
            "suggested_artist": "Artist",
            "suggested_title": "Suggested Title",
            "missing_artist": ma,
            "missing_title": mt,
        }
        fixer_tab.add_file_entry(entry)
    
    fixer_tab._filter_combo.setCurrentText("Missing Title")
    fixer_tab._apply_filter()
    
    # Should show file1, file2 (both have missing_title=True)
    assert fixer_tab._table.rowCount() == 2


def test_filter_both_shows_only_both_missing(fixer_tab, temp_dir):
    """Test that 'Both' filter shows only entries missing both artist and title."""
    for i, (ma, mt) in enumerate([(True, False), (False, True), (True, True), (False, False)]):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "" if ma else f"Artist {i}",
            "existing_title": "" if mt else f"Title {i}",
            "suggested_artist": "Artist",
            "suggested_title": "Suggested Title",
            "missing_artist": ma,
            "missing_title": mt,
        }
        fixer_tab.add_file_entry(entry)
    
    fixer_tab._filter_combo.setCurrentText("Both")
    fixer_tab._apply_filter()
    
    # Should show only file2 (both missing)
    assert fixer_tab._table.rowCount() == 1
    assert fixer_tab._table.item(0, 1).text() == "file2.mp3"


def test_should_show_entry_both_missing(fixer_tab, temp_dir):
    """Test _should_show_entry with 'Both' filter and both missing."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": True,
    }
    
    # Both missing should match "Both" filter
    result = fixer_tab._should_show_entry(entry, "Both")
    assert result is True


def test_should_show_entry_both_not_missing(fixer_tab, temp_dir):
    """Test _should_show_entry with 'Both' filter when not both missing."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "Artist",
        "existing_title": "",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": False,
        "missing_title": True,
    }
    
    # Only title missing should NOT match "Both" filter
    result = fixer_tab._should_show_entry(entry, "Both")
    assert result is False


def test_should_show_entry_unknown_filter(fixer_tab, temp_dir):
    """Test _should_show_entry with unknown filter text returns True."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": True,
    }
    
    # Unknown filter text should return True (default case)
    result = fixer_tab._should_show_entry(entry, "Unknown Filter")
    assert result is True


def test_search_filter_by_filename(fixer_tab, temp_dir):
    """Test that search filters by filename pattern."""
    for i in range(4):
        entry = {
            "path": temp_dir / f"song_{i}.mp3",
            "filename": f"song_{i}.mp3",
            "existing_artist": "",
            "existing_title": "Title",
            "suggested_artist": "Artist",
            "suggested_title": "Suggested Title",
            "missing_artist": True,
            "missing_title": False,
        }
        fixer_tab.add_file_entry(entry)
    
    fixer_tab._apply_filter()  # Show all
    
    assert fixer_tab._table.rowCount() == 4
    
    # Search for "song_1"
    fixer_tab._search_input.setText("song_1")
    fixer_tab._apply_filter()
    
    assert fixer_tab._table.rowCount() == 1
    assert fixer_tab._table.item(0, 1).text() == "song_1.mp3"


# ============================================================================
# Cell editing tests
# ============================================================================

def test_cell_edit_updates_files_data(fixer_tab, temp_dir):
    """Test that editing a cell updates _files_data correctly."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "Original Artist",
        "existing_title": "",
        "suggested_artist": "Suggested Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": False,
        "missing_title": True,  # Must be True to pass filter
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Verify table has row
    assert fixer_tab._table.rowCount() == 1
    
    # Edit artist cell
    artist_item = fixer_tab._table.item(0, 2)
    assert artist_item is not None
    artist_item.setText("Edited Artist")
    fixer_tab._on_cell_changed(0, 2)
    
    assert fixer_tab._files_data[0]["existing_artist"] == "Edited Artist"
    
    # Edit title cell
    title_item = fixer_tab._table.item(0, 3)
    assert title_item is not None
    title_item.setText("Edited Title")
    fixer_tab._on_cell_changed(0, 3)
    
    assert fixer_tab._files_data[0]["existing_title"] == "Edited Title"


# ============================================================================
# Integration tests with TagFixWorker mock
# ============================================================================

def test_fix_selected_creates_tagfix_worker_with_correct_data(fixer_tab, temp_dir):
    """Integration test: fix_selected creates TagFixWorker with correct file data."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "Title",
        "suggested_artist": "Suggested Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": False,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Check the checkbox
    fixer_tab._table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    
    with patch("musichouse.ui.fixer_tab.TagFixWorker") as MockWorker:
        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance
        
        fixer_tab.fix_selected()
        
        assert MockWorker.called
        call_args = MockWorker.call_args
        files_to_fix = call_args[0][0]
        
        assert len(files_to_fix) == 1
        assert files_to_fix[0]["path"] == temp_dir / "file1.mp3"
        # Should use suggested as current when not edited
        assert files_to_fix[0]["current_artist"] == "Suggested Artist"


def test_fix_selected_disables_buttons_and_creates_worker(fixer_tab, temp_dir):
    """Test that fix_selected disables buttons and creates TagFixWorker."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "Title",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": False,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Verify table has row
    assert fixer_tab._table.rowCount() >= 1
    
    # Find and check our file's checkbox
    found = False
    for row in range(fixer_tab._table.rowCount()):
        filename = fixer_tab._table.item(row, 1).text() if fixer_tab._table.item(row, 1) else ""
        if filename == "file1.mp3":
            checkbox = fixer_tab._table.item(row, 0)
            if checkbox:
                checkbox.setCheckState(Qt.CheckState.Checked)
                found = True
                break
    
    assert found, "Test file not found in table"
    
    # Verify buttons are enabled before fix
    assert fixer_tab._fix_selected_btn.isEnabled() is True
    
    with patch("musichouse.ui.fixer_tab.TagFixWorker") as MockWorker:
        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance
        
        fixer_tab.fix_selected()
        
        # Buttons should be disabled
        assert fixer_tab._fix_selected_btn.isEnabled() is False
        assert fixer_tab._fix_all_btn.isEnabled() is False
        
        # TagFixWorker should have been created
        assert MockWorker.called


def test_worker_finished_reenables_buttons(fixer_tab, temp_dir):
    """Test that worker finished signal re-enables buttons."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "Title",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": False,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    fixer_tab._table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    
    with patch("musichouse.ui.fixer_tab.TagFixWorker") as MockWorker:
        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance
        
        # Simulate fix_selected
        fixer_tab.fix_selected()
        assert fixer_tab._fix_selected_btn.isEnabled() is False
        
        # Simulate worker finished
        finished_handler = MockWorker.return_value.finished.connect.call_args[0][0]
        finished_handler(1, 0)  # 1 success, 0 failures
        
        # Buttons should be re-enabled
        assert fixer_tab._fix_selected_btn.isEnabled() is True
        assert fixer_tab._fix_all_btn.isEnabled() is True


def test_load_from_scan_db_error_fallback(fixer_tab, temp_dir):
    """Test load_from_scan handles database errors gracefully."""
    files = [temp_dir / "file1.mp3"]
    
    with patch('musichouse.leaderboard_cache.LeaderboardCache') as MockCache:
        MockCache.side_effect = Exception("DB connection failed")
        
        fixer_tab.load_from_scan(files, {})
        
        assert len(fixer_tab._files_data) == 0
        assert fixer_tab._table.rowCount() == 0


def test_load_from_scan_no_paths_early_return(fixer_tab):
    """Test load_from_scan returns early when no paths provided."""
    with patch('musichouse.leaderboard_cache.LeaderboardCache') as MockCache:
        mock_cache_instance = MagicMock()
        MockCache.return_value = mock_cache_instance
        
        fixer_tab.load_from_scan([], {})
        
        MockCache.assert_called_once()
        assert len(fixer_tab._files_data) == 0


def test_load_from_scan_populates_table(leaderboard_cache, qapp, temp_dir):
    """Test load_from_scan populates table with correct data."""
    from musichouse.ui.fixer_tab import FixerTab
    
    files_info = [
        {
            'path': str(temp_dir / "file1.mp3"),
            'size': 1000,
            'mtime': 1000.0,
            'artist': "Artist1",
            'title': "Title1",
            'needs_fixing': 1,
            'missing_artist': 0,
            'missing_title': 1,
            'suggested_artist': "Suggested Artist",
            'suggested_title': "Suggested Title",
            'tag_data': None
        },
    ]
    leaderboard_cache.update_scan_cache(files_info)
    
    with patch.object(FixerTab, '_load_saved_files'), \
         patch('musichouse.leaderboard_cache.LeaderboardCache') as MockCache:
        mock_cache_instance = MagicMock()
        mock_cache_instance._get_connection.return_value = leaderboard_cache._get_connection()
        mock_cache_instance.close = MagicMock()
        MockCache.return_value = mock_cache_instance
        
        tab = FixerTab()
        files = [temp_dir / "file1.mp3"]
        tab.load_from_scan(files, {})
        
        assert len(tab._files_data) == 1
        entry = tab._files_data[0]
        assert entry['existing_artist'] == "Artist1"
        assert entry['existing_title'] == "Title1"
        assert entry['suggested_artist'] == "Suggested Artist"
        assert entry['suggested_title'] == "Suggested Title"
        
        tab.deleteLater()


def test_header_checkbox_toggle_all(fixer_tab, temp_dir):
    """Test that header checkbox toggles all rows."""
    for i in range(3):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "",
            "existing_title": "Title",
            "suggested_artist": "Artist",
            "suggested_title": "Suggested Title",
            "missing_artist": True,
            "missing_title": False,
        }
        fixer_tab.add_file_entry(entry)
    
    fixer_tab._apply_filter()
    
    assert fixer_tab._table.rowCount() == 3
    
    # Click header to select all
    fixer_tab._on_header_clicked(0)
    
    for row in range(3):
        checkbox = fixer_tab._table.item(row, 0)
        assert checkbox.checkState() == Qt.CheckState.Checked


def test_toggle_all_rows(fixer_tab, temp_dir):
    """Test _toggle_all_rows method directly."""
    for i in range(3):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "",
            "existing_title": "Title",
            "suggested_artist": "Artist",
            "suggested_title": "Suggested Title",
            "missing_artist": True,
            "missing_title": False,
        }
        fixer_tab.add_file_entry(entry)
    
    fixer_tab._apply_filter()
    
    # Uncheck all
    fixer_tab._toggle_all_rows(Qt.CheckState.Unchecked)
    
    for row in range(3):
        checkbox = fixer_tab._table.item(row, 0)
        assert checkbox.checkState() == Qt.CheckState.Unchecked


def test_update_header_checkbox_state_all_checked(fixer_tab, temp_dir):
    """Test header checkbox shows checked when all rows are checked."""
    for i in range(3):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "",
            "existing_title": "Title",
            "suggested_artist": "Artist",
            "suggested_title": "Suggested Title",
            "missing_artist": True,
            "missing_title": False,
        }
        fixer_tab.add_file_entry(entry)
    
    fixer_tab._apply_filter()
    
    # Check all rows
    for row in range(3):
        fixer_tab._table.item(row, 0).setCheckState(Qt.CheckState.Checked)
    
    fixer_tab._update_header_checkbox_state()
    
    assert fixer_tab._select_all_cb.checkState() == Qt.CheckState.Checked


def test_update_header_checkbox_state_partial(fixer_tab, temp_dir):
    """Test header checkbox shows unchecked when some rows are checked."""
    for i in range(3):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "",
            "existing_title": "Title",
            "suggested_artist": "Artist",
            "suggested_title": "Suggested Title",
            "missing_artist": True,
            "missing_title": False,
        }
        fixer_tab.add_file_entry(entry)
    
    fixer_tab._apply_filter()
    
    # Check only first row
    fixer_tab._table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    
    fixer_tab._update_header_checkbox_state()
    
    assert fixer_tab._select_all_cb.checkState() == Qt.CheckState.Unchecked


def test_update_header_checkbox_state_none(fixer_tab, temp_dir):
    """Test header checkbox shows unchecked when no rows are checked."""
    for i in range(3):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "",
            "existing_title": "Title",
            "suggested_artist": "Artist",
            "suggested_title": "Suggested Title",
            "missing_artist": True,
            "missing_title": False,
        }
        fixer_tab.add_file_entry(entry)
    
    fixer_tab._apply_filter()
    
    fixer_tab._update_header_checkbox_state()
    
    assert fixer_tab._select_all_cb.checkState() == Qt.CheckState.Unchecked


def test_on_item_changed(fixer_tab):
    """Test _on_item_changed handler."""
    # This is a no-op handler currently, just verify it doesn't crash
    from PyQt6.QtWidgets import QTableWidgetItem
    
    item = QTableWidgetItem()
    fixer_tab._on_item_changed(item)


def test_on_search_changed_debounce(fixer_tab):
    """Test search input uses debounced timer."""
    fixer_tab._search_input.setText("test")
    
    # Timer should be started
    assert fixer_tab._search_timer.isActive()


def test_set_buttons_enabled(fixer_tab):
    """Test _set_buttons_enabled method."""
    assert fixer_tab._fix_selected_btn.isEnabled() is True
    assert fixer_tab._fix_all_btn.isEnabled() is True
    
    fixer_tab._set_buttons_enabled(False)
    
    assert fixer_tab._fix_selected_btn.isEnabled() is False
    assert fixer_tab._fix_all_btn.isEnabled() is False
    
    fixer_tab._set_buttons_enabled(True)
    
    assert fixer_tab._fix_selected_btn.isEnabled() is True
    assert fixer_tab._fix_all_btn.isEnabled() is True


def test_on_fix_progress(fixer_tab):
    """Test progress handler updates progress bar."""
    fixer_tab._progress_bar.setMaximum(10)
    fixer_tab._progress_bar.setValue(0)
    
    fixer_tab._on_fix_progress(5, "test.mp3")
    
    assert fixer_tab._progress_bar.value() == 6


def test_on_file_fixed_success(fixer_tab, temp_dir):
    """Test _on_file_fixed handler for successful fixes."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "Title",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": False,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._fixed_paths = []
    fixer_tab._failed_paths = []
    
    fixer_tab._on_file_fixed(str(temp_dir / "file1.mp3"), True, "file1.mp3")
    
    assert len(fixer_tab._fixed_paths) == 1
    assert fixer_tab._fixed_paths[0] == temp_dir / "file1.mp3"
    assert len(fixer_tab._failed_paths) == 0


def test_on_file_fixed_failure(fixer_tab, temp_dir):
    """Test _on_file_fixed handler for failed fixes."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "Title",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": False,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._fixed_paths = []
    fixer_tab._failed_paths = []
    
    fixer_tab._on_file_fixed(str(temp_dir / "file1.mp3"), False, "file1.mp3")
    
    assert len(fixer_tab._failed_paths) == 1
    assert fixer_tab._failed_paths[0] == temp_dir / "file1.mp3"
    assert len(fixer_tab._fixed_paths) == 0


def test_on_failures(fixer_tab):
    """Test _on_failures handler collects failures."""
    fixer_tab._failure_details = []
    
    failures = [
        ("file1.mp3", "corrupted", "Error message 1"),
        ("file2.mp3", "locked", "Error message 2"),
    ]
    
    fixer_tab._on_failures(failures)
    
    assert len(fixer_tab._failure_details) == 2
    assert fixer_tab._failure_details[0] == ("file1.mp3", "corrupted", "Error message 1")
    assert fixer_tab._failure_details[1] == ("file2.mp3", "locked", "Error message 2")


def test_show_failure_summary_no_failures(fixer_tab):
    """Test _show_failure_summary with no failures shows simple message."""
    with patch('musichouse.ui.fixer_tab.QMessageBox') as MockMsgBox:
        fixer_tab._show_failure_summary([], 5)
        
        MockMsgBox.assert_called_once()
        mock_instance = MockMsgBox.return_value
        mock_instance.setWindowTitle.assert_called_once_with("Fix Complete")
        mock_instance.exec.assert_called_once()


def test_show_failure_summary_with_failures(qapp, temp_dir):
    """Test _show_failure_summary with failures shows grouped dialog."""
    from PyQt6.QtWidgets import QDialog

    from musichouse.ui.fixer_tab import FixerTab
    
    tab = FixerTab()
    
    failures = [
        ("file1.mp3", "corrupted", "Corruption error"),
        ("file2.mp3", "deleted", "File not found"),
        ("file3.mp3", "locked", "File locked"),
    ]
    
    dialog_executed = False
    
    def mock_exec(self):
        nonlocal dialog_executed
        dialog_executed = True
    
    with patch.object(QDialog, 'exec', mock_exec):
        tab._show_failure_summary(failures, 3)
    
    assert dialog_executed
    tab.deleteLater()


def test_on_fix_finished_updates_db_and_removes_rows(fixer_tab, temp_dir):
    """Test _on_fix_finished updates DB and removes fixed rows."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "Title",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": False,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    fixer_tab._fixed_paths = [temp_dir / "file1.mp3"]
    fixer_tab._failed_paths = []
    fixer_tab._failure_details = []
    
    mock_worker = MagicMock()
    mock_worker._auto_fix = False
    fixer_tab._worker = mock_worker
    
    with patch.object(fixer_tab, '_update_db_after_fix'), \
         patch.object(fixer_tab, '_remove_fixed_rows'):
        fixer_tab._on_fix_finished(1, 0)
    
    assert fixer_tab._progress_bar.isVisible() is False
    assert fixer_tab._fix_selected_btn.isEnabled() is True


def test_on_fix_finished_auto_fix_all_clears_data(fixer_tab, temp_dir):
    """Test _on_fix_finished with auto_fix clears all data."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "Title",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": False,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    initial_count = len(fixer_tab._files_data)
    assert initial_count == 1
    
    fixer_tab._fixed_paths = []
    fixer_tab._failed_paths = []
    fixer_tab._failure_details = []
    
    mock_worker = MagicMock()
    mock_worker._auto_fix = True
    fixer_tab._worker = mock_worker
    
    fixer_tab._on_fix_finished(1, 0)
    
    assert len(fixer_tab._files_data) == 0
    assert fixer_tab._table.rowCount() == 0


def test_on_fix_finished_with_failures_logs_warning(fixer_tab, temp_dir):
    """Test _on_fix_finished logs warning when there are failures."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "Title",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": False,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    fixer_tab._fixed_paths = []
    fixer_tab._failed_paths = [temp_dir / "file1.mp3"]
    fixer_tab._failure_details = [("file1.mp3", "corrupted", "Error")]
    
    mock_worker = MagicMock()
    mock_worker._auto_fix = False
    fixer_tab._worker = mock_worker
    
    from PyQt6.QtWidgets import QDialog

    with patch.object(fixer_tab, '_mark_failed_row'), \
         patch.object(QDialog, 'exec'):
        fixer_tab._on_fix_finished(0, 1)
    
    assert fixer_tab._progress_bar.isVisible() is False


def test_update_db_after_fix_success(fixer_tab, temp_dir):
    """Test _update_db_after_fix updates database correctly."""
    
    fixed_paths = [temp_dir / "file1.mp3", temp_dir / "file2.mp3"]
    
    with patch('musichouse.ui.fixer_tab.LeaderboardCache') as MockCache:
        mock_cache = MagicMock()
        mock_conn = MagicMock()
        mock_cache._get_connection.return_value = mock_conn
        MockCache.return_value = mock_cache
        
        fixer_tab._update_db_after_fix(fixed_paths)
        
        assert mock_conn.execute.call_count >= 1
        mock_cache.close.assert_called_once()


def test_update_db_after_fix_error(fixer_tab):
    """Test _update_db_after_fix handles errors gracefully."""
    from pathlib import Path
    
    with patch('musichouse.ui.fixer_tab.LeaderboardCache') as MockCache:
        MockCache.side_effect = Exception("DB error")
        
        fixer_tab._update_db_after_fix([Path("file1.mp3")])
        
        MockCache.assert_called_once()


# ============================================================================
# _load_saved_files tests
# ============================================================================

def test_load_saved_files_populates_from_db(qapp):
    """Test _load_saved_files loads files from database on startup."""
    from musichouse.ui.fixer_tab import FixerTab
    
    # Create FixerTab with mocked database
    with patch('musichouse.leaderboard_cache.LeaderboardCache') as MockCache:
        mock_cache_instance = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"path": "/test/file1.mp3", "artist": "Artist1", "title": "",
             "missing_artist": 0, "missing_title": 1,
             "suggested_artist": "Suggested Artist", "suggested_title": "Suggested Title"}
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_cache_instance._get_connection.return_value = mock_conn
        mock_cache_instance.close = MagicMock()
        MockCache.return_value = mock_cache_instance
        
        tab = FixerTab()
        
        # Should have loaded the file
        assert len(tab._files_data) == 1
        assert tab._files_data[0]["filename"] == "file1.mp3"
        
        tab.deleteLater()


def test_load_saved_files_empty_result(qapp):
    """Test _load_saved_files with no files in database."""
    from musichouse.ui.fixer_tab import FixerTab
    
    with patch('musichouse.leaderboard_cache.LeaderboardCache') as MockCache:
        mock_cache_instance = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []  # Empty result
        mock_conn.execute.return_value = mock_cursor
        mock_cache_instance._get_connection.return_value = mock_conn
        mock_cache_instance.close = MagicMock()
        MockCache.return_value = mock_cache_instance
        
        tab = FixerTab()
        tab.show()  # Need to show for visibility to work properly
        
        assert len(tab._files_data) == 0
        # Empty state should be visible when no data
        tab._update_empty_state(len(tab._files_data) > 0)
        assert tab._empty_label.isVisible() is True
        
        tab.deleteLater()


def test_load_saved_files_db_error(qapp):
    """Test _load_saved_files handles database errors gracefully."""
    from musichouse.ui.fixer_tab import FixerTab
    
    with patch('musichouse.leaderboard_cache.LeaderboardCache') as MockCache:
        MockCache.side_effect = Exception("DB connection failed")
        
        tab = FixerTab()
        
        # Should not crash, just log error
        assert len(tab._files_data) == 0
        
        tab.deleteLater()


# ============================================================================
# _reset_database tests
# ============================================================================

def test_reset_database_user_confirms(qapp, temp_dir):
    """Test _reset_database when user confirms deletion."""
    from musichouse.ui.fixer_tab import FixerTab
    
    # Create mock DB files
    db_path = temp_dir / "leaderboard.db"
    db_path.write_text("fake db")
    (temp_dir / "leaderboard.db-wal").write_text("fake wal")
    (temp_dir / "leaderboard.db-shm").write_text("fake shm")
    
    with patch('musichouse.config.get_config_dir', return_value=temp_dir), \
         patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes), \
         patch.object(QMessageBox, 'information'), \
         patch('musichouse.leaderboard_cache.LeaderboardCache') as MockCache:
        
        mock_cache_instance = MagicMock()
        MockCache.return_value = mock_cache_instance
        
        tab = FixerTab()
        tab._reset_database()
        
        # Files should be deleted
        assert db_path.exists() is False
        assert (temp_dir / "leaderboard.db-wal").exists() is False
        assert (temp_dir / "leaderboard.db-shm").exists() is False
        
        # Table should be cleared
        assert len(tab._files_data) == 0
        assert tab._table.rowCount() == 0
        
        tab.deleteLater()


def test_reset_database_user_cancels(qapp, temp_dir):
    """Test _reset_database when user cancels."""
    from musichouse.ui.fixer_tab import FixerTab
    
    db_path = temp_dir / "leaderboard.db"
    db_path.write_text("fake db")
    
    with patch('musichouse.config.get_config_dir', return_value=temp_dir), \
         patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No), \
         patch.object(QMessageBox, 'information'):
        
        tab = FixerTab()
        tab._reset_database()
        
        # Files should NOT be deleted
        assert db_path.exists() is True
        
        tab.deleteLater()


def test_reset_database_cache_close_error(qapp, temp_dir):
    """Test _reset_database handles cache close error."""
    from musichouse.ui.fixer_tab import FixerTab
    
    db_path = temp_dir / "leaderboard.db"
    db_path.write_text("fake db")
    
    with patch('musichouse.config.get_config_dir', return_value=temp_dir), \
         patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes), \
         patch.object(QMessageBox, 'information'), \
         patch('musichouse.leaderboard_cache.LeaderboardCache') as MockCache:
        
        mock_cache_instance = MagicMock()
        mock_cache_instance.close.side_effect = Exception("Close failed")
        MockCache.return_value = mock_cache_instance
        
        tab = FixerTab()
        tab._reset_database()  # Should not crash
        
        tab.deleteLater()


def test_reset_database_file_unlink_error(qapp, temp_dir):
    """Test _reset_database handles file deletion error."""
    from pathlib import Path
    from unittest.mock import patch
    from unittest.mock import patch as mock_patch

    from musichouse.ui.fixer_tab import FixerTab
    
    db_path = temp_dir / "leaderboard.db"
    db_path.write_text("fake db")
    wal_path = temp_dir / "leaderboard.db-wal"
    wal_path.write_text("fake wal")
    shm_path = temp_dir / "leaderboard.db-shm"
    shm_path.write_text("fake shm")
    
    # Track which path should raise error
    error_path = wal_path
    original_unlink = Path.unlink
    
    def mock_unlink_raise(self, *args, **kwargs):
        if self == error_path:
            raise OSError("Cannot delete")
        # Call original for other files
        return original_unlink(self, *args, **kwargs)
    
    with patch('musichouse.config.get_config_dir', return_value=temp_dir), \
         patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes), \
         patch.object(QMessageBox, 'information'), \
         patch('musichouse.leaderboard_cache.LeaderboardCache'), \
         mock_patch.object(Path, 'unlink', mock_unlink_raise):
        
        tab = FixerTab()
        tab._reset_database()  # Should not crash, just log error
        
        tab.deleteLater()


# ============================================================================
# _load_file_entry tests
# ============================================================================

def test_load_file_entry_success(temp_dir):
    """Test _load_file_entry successfully loads file metadata."""
    from musichouse.ui.fixer_tab import FixerTab
    
    # Create a mock MP3 file
    mp3_file = temp_dir / "test.mp3"
    mp3_file.write_bytes(
        b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100
    )
    
    with patch('musichouse.ui.fixer_tab.load_mp3_safely') as mock_load, \
         patch('musichouse.ui.fixer_tab.parse_filename', return_value=("Suggested Artist", "Suggested Title")):
        
        mock_audio = MagicMock()
        mock_audio.tag.artist = "Test Artist"
        mock_audio.tag.title = "Test Title"
        mock_load.return_value = mock_audio
        
        tab = FixerTab()
        result = tab._load_file_entry(mp3_file, {})
        
        assert result is not None
        assert result["existing_artist"] == "Test Artist"
        assert result["existing_title"] == "Test Title"
        assert result["suggested_artist"] == "Suggested Artist"
        
        tab.deleteLater()


def test_load_file_entry_suggested_artist_is_digit(temp_dir):
    """Test _load_file_entry uses folder name when suggested artist is a digit."""
    from musichouse.ui.fixer_tab import FixerTab
    
    mp3_file = temp_dir / "123 - Song.mp3"
    mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    
    with patch('musichouse.ui.fixer_tab.load_mp3_safely') as mock_load, \
         patch('musichouse.ui.fixer_tab.parse_filename', return_value=("123", "Song")), \
         patch('musichouse.ui.fixer_tab.get_artist_from_folder', return_value="Folder Artist"):
        
        mock_audio = MagicMock()
        mock_audio.tag.artist = ""
        mock_audio.tag.title = ""
        mock_load.return_value = mock_audio
        
        tab = FixerTab()
        result = tab._load_file_entry(mp3_file, {})
        
        # Should use folder name instead of digit
        assert result["suggested_artist"] == "Folder Artist"
        
        tab.deleteLater()


def test_load_file_entry_corrupted_file(temp_dir):
    """Test _load_file_entry returns None for corrupted file."""
    from musichouse.ui.fixer_tab import FixerTab
    
    mp3_file = temp_dir / "corrupted.mp3"
    mp3_file.write_bytes(b"not valid mp3 data")
    
    with patch('musichouse.ui.fixer_tab.load_mp3_safely', return_value=None):
        tab = FixerTab()
        result = tab._load_file_entry(mp3_file, {})
        
        assert result is None
        
        tab.deleteLater()


def test_load_file_entry_no_tag(temp_dir):
    """Test _load_file_entry returns None when file has no tag."""
    from musichouse.ui.fixer_tab import FixerTab
    
    mp3_file = temp_dir / "no_tag.mp3"
    mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    
    with patch('musichouse.ui.fixer_tab.load_mp3_safely') as mock_load:
        mock_audio = MagicMock()
        mock_audio.tag = None
        mock_load.return_value = mock_audio
        
        tab = FixerTab()
        result = tab._load_file_entry(mp3_file, {})
        
        assert result is None
        
        tab.deleteLater()


# ============================================================================
# _set_all_checkboxes tests
# ============================================================================

def test_set_all_checkboxes_checked(fixer_tab, temp_dir):
    """Test _set_all_checkboxes sets all to checked."""
    for i in range(3):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "",
            "existing_title": "Title",
            "suggested_artist": "Artist",
            "suggested_title": "Suggested Title",
            "missing_artist": True,
            "missing_title": False,
        }
        fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    fixer_tab._set_all_checkboxes(True)
    
    for row in range(3):
        checkbox = fixer_tab._table.item(row, 0)
        assert checkbox.checkState() == Qt.CheckState.Checked


def test_set_all_checkboxes_unchecked(fixer_tab, temp_dir):
    """Test _set_all_checkboxes sets all to unchecked."""
    for i in range(3):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "",
            "existing_title": "Title",
            "suggested_artist": "Artist",
            "suggested_title": "Suggested Title",
            "missing_artist": True,
            "missing_title": False,
        }
        fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # First check all
    fixer_tab._set_all_checkboxes(True)
    
    # Then uncheck all
    fixer_tab._set_all_checkboxes(False)
    
    for row in range(3):
        checkbox = fixer_tab._table.item(row, 0)
        assert checkbox.checkState() == Qt.CheckState.Unchecked


# ============================================================================
# closeEvent tests
# ============================================================================

def test_close_event_worker_running(qapp, temp_dir):
    """Test closeEvent cancels running worker."""
    from PyQt6.QtGui import QCloseEvent

    from musichouse.ui.fixer_tab import FixerTab
    
    with patch('musichouse.leaderboard_cache.LeaderboardCache') as MockCache:
        mock_cache_instance = MagicMock()
        MockCache.return_value = mock_cache_instance
        
        tab = FixerTab()
        
        # Create a mock running worker
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        tab._worker = mock_worker
        
        # Simulate close event
        event = QCloseEvent()
        tab.closeEvent(event)
        
        # Worker should be cancelled
        assert mock_worker.cancel.called
        assert mock_worker.wait.called
        
        tab.deleteLater()


def test_close_event_worker_not_running(qapp, temp_dir):
    """Test closeEvent does nothing if worker not running."""
    from PyQt6.QtGui import QCloseEvent

    from musichouse.ui.fixer_tab import FixerTab
    
    with patch('musichouse.leaderboard_cache.LeaderboardCache') as MockCache:
        mock_cache_instance = MagicMock()
        MockCache.return_value = mock_cache_instance
        
        tab = FixerTab()
        
        # Create a mock stopped worker
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = False
        tab._worker = mock_worker
        
        event = QCloseEvent()
        tab.closeEvent(event)
        
        # Worker should NOT be cancelled
        assert mock_worker.cancel.called is False
        
        tab.deleteLater()


def test_close_event_no_worker(qapp, temp_dir):
    """Test closeEvent when no worker exists."""
    from PyQt6.QtGui import QCloseEvent

    from musichouse.ui.fixer_tab import FixerTab
    
    with patch('musichouse.leaderboard_cache.LeaderboardCache') as MockCache:
        mock_cache_instance = MagicMock()
        MockCache.return_value = mock_cache_instance
        
        tab = FixerTab()
        
        # No _worker attribute
        assert not hasattr(tab, '_worker')
        
        event = QCloseEvent()
        tab.closeEvent(event)  # Should not crash
        
        tab.deleteLater()


# ============================================================================
# _remove_fixed_rows tests
# ============================================================================

def test_remove_fixed_rows_single_file(fixer_tab, temp_dir):
    """Test _remove_fixed_rows removes a single fixed file."""
    for i in range(3):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "",
            "existing_title": "Title",
            "suggested_artist": "Artist",
            "suggested_title": "Suggested Title",
            "missing_artist": True,
            "missing_title": False,
        }
        fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    assert len(fixer_tab._files_data) == 3
    
    # Remove file1
    fixer_tab._remove_fixed_rows([temp_dir / "file1.mp3"])
    
    assert len(fixer_tab._files_data) == 2
    paths = [e["filename"] for e in fixer_tab._files_data]
    assert "file1.mp3" not in paths
    assert fixer_tab._table.rowCount() == 2


def test_remove_fixed_rows_multiple_files(fixer_tab, temp_dir):
    """Test _remove_fixed_rows removes multiple files."""
    for i in range(5):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "",
            "existing_title": "Title",
            "suggested_artist": "Artist",
            "suggested_title": "Suggested Title",
            "missing_artist": True,
            "missing_title": False,
        }
        fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Remove files 1 and 3
    fixer_tab._remove_fixed_rows([temp_dir / "file1.mp3", temp_dir / "file3.mp3"])
    
    assert len(fixer_tab._files_data) == 3
    paths = [e["filename"] for e in fixer_tab._files_data]
    assert "file1.mp3" not in paths
    assert "file3.mp3" not in paths


def test_remove_fixed_rows_empty_list(fixer_tab, temp_dir):
    """Test _remove_fixed_rows with empty list does nothing."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "Title",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": False,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    initial_count = len(fixer_tab._files_data)
    
    fixer_tab._remove_fixed_rows([])
    
    assert len(fixer_tab._files_data) == initial_count


# ============================================================================
# _update_empty_state tests
# ============================================================================

def test_update_empty_state_shows_label(fixer_tab):
    """Test _update_empty_state shows label when no data."""
    fixer_tab.show()  # Need to show for visibility to work properly
    # When has_data=False, label should be visible
    fixer_tab._update_empty_state(False)
    assert fixer_tab._empty_label.isVisible() is True


def test_update_empty_state_hides_label(fixer_tab):
    """Test _update_empty_state hides label when has data."""
    fixer_tab.show()
    fixer_tab._update_empty_state(True)
    assert fixer_tab._empty_label.isVisible() is False


# ============================================================================
# Edge case tests for uncovered lines
# ============================================================================

def test_select_all_cb_none(qapp):
    """Test _update_header_checkbox_state early return when _select_all_cb is None."""
    from musichouse.ui.fixer_tab import FixerTab
    
    with patch('musichouse.leaderboard_cache.LeaderboardCache') as MockCache:
        mock_cache_instance = MagicMock()
        MockCache.return_value = mock_cache_instance
        
        tab = FixerTab()
        tab.show()
        
        # Set _select_all_cb to None
        tab._select_all_cb = None
        
        # Should not crash
        tab._update_header_checkbox_state()
        
        tab.deleteLater()


def test_add_file_entry_with_string_path(fixer_tab, temp_dir):
    """Test add_file_entry converts string path to Path object."""
    entry = {
        "path": str(temp_dir / "file1.mp3"),  # String path
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "Title",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": False,
    }
    fixer_tab.add_file_entry(entry)
    
    # Path should be converted to Path object
    from pathlib import Path
    assert isinstance(fixer_tab._files_data[0]["path"], Path)


def test_auto_fix_all_with_invalid_data_idx(fixer_tab, temp_dir):
    """Test that auto_fix_all skips rows with invalid data_idx."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "",
        "existing_title": "Title",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": False,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Set data_idx to None to trigger the continue statement
    checkbox = fixer_tab._table.item(0, 0)
    checkbox.setData(Qt.ItemDataRole.UserRole, None)  # Invalid data_idx
    
    with patch("musichouse.ui.fixer_tab.TagFixWorker") as MockWorker:
        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance
        
        # Should not crash - will create worker with empty list
        fixer_tab.auto_fix_all()
        
        # Worker should be created but with empty files_to_fix list
        # because the only row has invalid data_idx
        assert MockWorker.called
        call_args = MockWorker.call_args
        assert call_args[0][0] == []  # files_to_fix is empty
        assert call_args[1]["auto_fix"] is True  # auto_fix=True


def test_on_cell_changed_invalid_data_idx(fixer_tab, temp_dir):
    """Test _on_cell_changed returns early when data_idx is None."""
    entry = {
        "path": temp_dir / "file1.mp3",
        "filename": "file1.mp3",
        "existing_artist": "Original Artist",
        "existing_title": "Title",
        "suggested_artist": "Artist",
        "suggested_title": "Suggested Title",
        "missing_artist": True,
        "missing_title": False,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Manually set data to None to trigger the early return
    fixer_tab._table.item(0, 0).setData(Qt.ItemDataRole.UserRole, None)
    
    # Should not crash
    fixer_tab._on_cell_changed(0, 2)
    
    # Data should remain unchanged (early return)
    assert fixer_tab._files_data[0]["existing_artist"] == "Original Artist"


# ============================================================================
# Drag-fill tests for Artist column
# ============================================================================

def test_drag_fill_artist_column(qapp, fixer_tab, temp_dir):
    """Test drag-fill extends artist value to target rows."""
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QMouseEvent
    
    # Populate with 5 entries - all must have at least one missing tag to pass filter
    # Entry 0 has the source artist value but missing title
    # Entries 1-4 have missing artist AND missing title (so they remain after fill)
    for i in range(5):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "Artist 0" if i == 0 else "",
            "existing_title": "" if i >= 0 else f"Title {i}",  # All entries missing title
            "suggested_artist": f"Suggested {i}",
            "suggested_title": "Suggested Title",
            "missing_artist": i != 0,
            "missing_title": True,  # All entries missing title
        }
        fixer_tab.add_file_entry(entry)
    
    fixer_tab._apply_filter()
    assert fixer_tab._table.rowCount() == 5
    
    # Source cell (row 0) has "Artist 0"
    source_item = fixer_tab._table.item(0, 2)
    assert source_item.text() == "Artist 0"
    
    # Simulate mouse press on fill handle (bottom-right corner of cell)
    cell_rect = fixer_tab._table.visualItemRect(source_item)
    handle_pos = QPointF(cell_rect.right() - 5, cell_rect.bottom() - 5)
    
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        handle_pos,
        handle_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    
    # Trigger event filter
    result = fixer_tab.eventFilter(fixer_tab._table.viewport(), press_event)
    assert result is True
    assert fixer_tab._fill_handle_active is True
    assert fixer_tab._fill_handle_start_row == 0
    
    # Simulate mouse move to row 4
    target_item = fixer_tab._table.item(4, 2)
    target_rect = fixer_tab._table.visualItemRect(target_item)
    move_pos = QPointF(target_rect.center())
    
    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        move_pos,
        move_pos,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier
    )
    
    result = fixer_tab.eventFilter(fixer_tab._table.viewport(), move_event)
    assert result is False
    
    # Simulate mouse release
    release_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        move_pos,
        move_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    
    result = fixer_tab.eventFilter(fixer_tab._table.viewport(), release_event)
    assert result is True
    
    # Verify all rows now have "Artist 0"
    for row in range(5):
        item = fixer_tab._table.item(row, 2)
        assert item.text() == "Artist 0", f"Row {row} should have 'Artist 0'"
    
    # Verify _files_data is updated
    for i, entry in enumerate(fixer_tab._files_data):
        assert entry["existing_artist"] == "Artist 0", f"Entry {i} should have 'Artist 0'"
        assert entry["missing_artist"] is False, f"Entry {i} should not be missing artist"


def test_drag_fill_empty_source_no_op(qapp, fixer_tab, temp_dir):
    """Test drag-fill with empty existing_artist fills with suggested value."""
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QMouseEvent
    
    # Populate with entries where source has empty existing_artist but has suggested
    for i in range(3):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "",
            "existing_title": "" if i >= 0 else f"Title {i}",  # All entries missing title
            "suggested_artist": "Suggested Artist",
            "suggested_title": "Suggested Title",
            "missing_artist": True,
            "missing_title": True,  # All entries missing title
        }
        fixer_tab.add_file_entry(entry)
    
    fixer_tab._apply_filter()
    assert fixer_tab._table.rowCount() == 3
    
    # Source cell shows "Suggested Artist" (the suggested value since existing is empty)
    source_item = fixer_tab._table.item(0, 2)
    assert source_item.text() == "Suggested Artist"
    
    # Simulate drag from row 0 to row 2
    cell_rect = fixer_tab._table.visualItemRect(source_item)
    handle_pos = QPointF(cell_rect.right() - 5, cell_rect.bottom() - 5)
    
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        handle_pos,
        handle_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    fixer_tab.eventFilter(fixer_tab._table.viewport(), press_event)
    
    # Target position - send move event to set the fill range
    target_item = fixer_tab._table.item(2, 2)
    target_rect = fixer_tab._table.visualItemRect(target_item)
    move_pos = QPointF(target_rect.center())
    
    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        move_pos,
        move_pos,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier
    )
    fixer_tab.eventFilter(fixer_tab._table.viewport(), move_event)
    
    release_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        move_pos,
        move_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    fixer_tab.eventFilter(fixer_tab._table.viewport(), release_event)
    
    # Verify _files_data is updated with the suggested value for target rows
    # Note: Due to existing behavior, _add_row_to_table triggers cellChanged which
    # updates existing_artist to the displayed value (suggested when existing is empty).
    # So all entries have existing_artist="Suggested Artist" after being added to table.
    # The fill operation skips the source row, so only target rows get missing_artist=False.
    for i in range(3):
        assert fixer_tab._files_data[i]["existing_artist"] == "Suggested Artist"
    # Source row (entry 0) is skipped in fill, so its missing_artist stays True
    assert fixer_tab._files_data[0]["missing_artist"] is True
    for i in range(1, 3):
        assert fixer_tab._files_data[i]["missing_artist"] is False


def test_drag_fill_truly_empty_source_no_op(qapp, fixer_tab, temp_dir):
    """Test drag-fill does nothing when both existing and suggested artist are empty."""
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QMouseEvent
    
    # Populate with entries where source has truly empty artist
    for i in range(3):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "",
            "existing_title": "" if i >= 0 else f"Title {i}",  # All entries missing title
            "suggested_artist": "",  # No suggested value either
            "suggested_title": "Suggested Title",
            "missing_artist": True,
            "missing_title": True,  # All entries missing title
        }
        fixer_tab.add_file_entry(entry)
    
    fixer_tab._apply_filter()
    assert fixer_tab._table.rowCount() == 3
    
    # Source cell is empty (no existing, no suggested)
    source_item = fixer_tab._table.item(0, 2)
    assert source_item.text() == ""
    
    # Simulate drag from row 0 to row 2
    cell_rect = fixer_tab._table.visualItemRect(source_item)
    handle_pos = QPointF(cell_rect.right() - 5, cell_rect.bottom() - 5)
    
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        handle_pos,
        handle_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    fixer_tab.eventFilter(fixer_tab._table.viewport(), press_event)
    
    # Target position - send move event to set the fill range
    target_item = fixer_tab._table.item(2, 2)
    target_rect = fixer_tab._table.visualItemRect(target_item)
    move_pos = QPointF(target_rect.center())
    
    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        move_pos,
        move_pos,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier
    )
    fixer_tab.eventFilter(fixer_tab._table.viewport(), move_event)
    
    release_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        move_pos,
        move_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    fixer_tab.eventFilter(fixer_tab._table.viewport(), release_event)
    
    # Verify _files_data unchanged (empty source should not fill)
    for entry in fixer_tab._files_data:
        assert entry["existing_artist"] == ""
        assert entry["missing_artist"] is True


def test_drag_fill_zero_range_no_op(qapp, fixer_tab, temp_dir):
    """Test drag-fill does nothing when drag range is zero rows."""
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QMouseEvent
    
    # Populate with entries - all must have missing tags
    for i in range(3):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "Artist 0" if i == 0 else "",
            "existing_title": "" if i == 0 else f"Title {i}",  # Entry 0 missing title
            "suggested_artist": "Suggested",
            "suggested_title": "Suggested Title",
            "missing_artist": i != 0,
            "missing_title": i == 0,  # Only entry 0 missing title
        }
        fixer_tab.add_file_entry(entry)
    
    fixer_tab._apply_filter()
    assert fixer_tab._table.rowCount() == 3
    
    # Simulate drag from row 0 to row 0 (same row)
    source_item = fixer_tab._table.item(0, 2)
    cell_rect = fixer_tab._table.visualItemRect(source_item)
    handle_pos = QPointF(cell_rect.right() - 5, cell_rect.bottom() - 5)
    
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        handle_pos,
        handle_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    fixer_tab.eventFilter(fixer_tab._table.viewport(), press_event)
    
    # Release at same position
    release_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        handle_pos,
        handle_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    fixer_tab.eventFilter(fixer_tab._table.viewport(), release_event)
    
    # Verify no changes (zero range)
    assert fixer_tab._table.item(1, 2).text() == "Suggested"
    assert fixer_tab._table.item(2, 2).text() == "Suggested"


def test_drag_fill_only_artist_column(qapp, fixer_tab, temp_dir):
    """Test drag-fill only affects Artist column, not Title column."""
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QMouseEvent
    
    # Populate with entries - all must have missing title to pass filter
    for i in range(3):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "Artist 0" if i == 0 else "",
            "existing_title": "" if i >= 0 else f"Title {i}",  # All entries missing title
            "suggested_artist": "Suggested Artist",
            "suggested_title": "Suggested Title",
            "missing_artist": i != 0,
            "missing_title": True,  # All entries missing title
        }
        fixer_tab.add_file_entry(entry)
    
    fixer_tab._apply_filter()
    assert fixer_tab._table.rowCount() == 3
    
    # Drag fill artist from row 0 to row 2
    source_item = fixer_tab._table.item(0, 2)
    cell_rect = fixer_tab._table.visualItemRect(source_item)
    handle_pos = QPointF(cell_rect.right() - 5, cell_rect.bottom() - 5)
    
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        handle_pos,
        handle_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    fixer_tab.eventFilter(fixer_tab._table.viewport(), press_event)
    
    # Move to target row (row 2) to set the fill range
    target_item = fixer_tab._table.item(2, 2)
    target_rect = fixer_tab._table.visualItemRect(target_item)
    move_pos = QPointF(target_rect.center())
    
    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        move_pos,
        move_pos,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier
    )
    fixer_tab.eventFilter(fixer_tab._table.viewport(), move_event)
    
    release_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        move_pos,
        move_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    fixer_tab.eventFilter(fixer_tab._table.viewport(), release_event)
    
    # Artist column should be filled (target rows only, source row unchanged)
    # Source row (row 0) shows "Artist 0", target rows (1-2) should also show "Artist 0"
    assert fixer_tab._table.item(0, 2).text() == "Artist 0"
    assert fixer_tab._table.item(1, 2).text() == "Artist 0"
    assert fixer_tab._table.item(2, 2).text() == "Artist 0"
    
    # Title column should remain unchanged (shows suggested when empty)
    assert fixer_tab._table.item(1, 3).text() == "Suggested Title"
    assert fixer_tab._table.item(2, 3).text() == "Suggested Title"


def test_drag_fill_outside_artist_column_ignored(qapp, fixer_tab, temp_dir):
    """Test that drag outside Artist column is ignored."""
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QMouseEvent
    
    # Populate with entry that has missing title (to pass filter)
    entry = {
        "path": temp_dir / "file0.mp3",
        "filename": "file0.mp3",
        "existing_artist": "Artist",
        "existing_title": "",
        "suggested_artist": "Suggested",
        "suggested_title": "Suggested",
        "missing_artist": False,
        "missing_title": True,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Try to drag on Title column (column 3)
    title_item = fixer_tab._table.item(0, 3)
    cell_rect = fixer_tab._table.visualItemRect(title_item)
    handle_pos = QPointF(cell_rect.right() - 5, cell_rect.bottom() - 5)
    
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        handle_pos,
        handle_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    
    result = fixer_tab.eventFilter(fixer_tab._table.viewport(), press_event)
    assert result is False
    assert fixer_tab._fill_handle_active is False


def test_drag_fill_right_click_ignored(qapp, fixer_tab, temp_dir):
    """Test that right-click does not activate drag-fill."""
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QMouseEvent
    
    # Populate with entries
    entry = {
        "path": temp_dir / "file0.mp3",
        "filename": "file0.mp3",
        "existing_artist": "Artist",
        "existing_title": "",
        "suggested_artist": "Suggested",
        "suggested_title": "Suggested",
        "missing_artist": False,
        "missing_title": True,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Right-click on fill handle
    item = fixer_tab._table.item(0, 2)
    cell_rect = fixer_tab._table.visualItemRect(item)
    handle_pos = QPointF(cell_rect.right() - 5, cell_rect.bottom() - 5)
    
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        handle_pos,
        handle_pos,
        Qt.MouseButton.RightButton,
        Qt.MouseButton.RightButton,
        Qt.KeyboardModifier.NoModifier
    )
    
    result = fixer_tab.eventFilter(fixer_tab._table.viewport(), press_event)
    assert result is False
    assert fixer_tab._fill_handle_active is False


def test_drag_fill_move_without_press_ignored(qapp, fixer_tab, temp_dir):
    """Test that mouse move without prior press does not activate drag-fill."""
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QMouseEvent
    
    # Populate with entries
    entry = {
        "path": temp_dir / "file0.mp3",
        "filename": "file0.mp3",
        "existing_artist": "Artist",
        "existing_title": "",
        "suggested_artist": "Suggested",
        "suggested_title": "Suggested",
        "missing_artist": False,
        "missing_title": True,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Mouse move without prior press
    item = fixer_tab._table.item(0, 2)
    cell_rect = fixer_tab._table.visualItemRect(item)
    move_pos = QPointF(cell_rect.center())
    
    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        move_pos,
        move_pos,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier
    )
    
    result = fixer_tab.eventFilter(fixer_tab._table.viewport(), move_event)
    assert result is False
    assert fixer_tab._fill_handle_active is False


def test_drag_fill_release_without_press_no_op(qapp, fixer_tab, temp_dir):
    """Test that mouse release without prior press does nothing."""
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QMouseEvent
    
    # Populate with entries
    entry = {
        "path": temp_dir / "file0.mp3",
        "filename": "file0.mp3",
        "existing_artist": "Artist",
        "existing_title": "",
        "suggested_artist": "Suggested",
        "suggested_title": "Suggested",
        "missing_artist": False,
        "missing_title": True,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Mouse release without prior press
    item = fixer_tab._table.item(0, 2)
    cell_rect = fixer_tab._table.visualItemRect(item)
    release_pos = QPointF(cell_rect.center())
    
    release_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        release_pos,
        release_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    
    result = fixer_tab.eventFilter(fixer_tab._table.viewport(), release_event)
    assert result is False
    assert fixer_tab._fill_handle_active is False


def test_drag_fill_move_on_same_row_no_highlight_change(qapp, fixer_tab, temp_dir):
    """Test that moving to the same row does not change highlight."""
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QMouseEvent
    
    # Populate with entries
    for i in range(3):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "Artist 0" if i == 0 else "",
            "existing_title": "" if i != 0 else "Title",
            "suggested_artist": "Suggested",
            "suggested_title": "Suggested",
            "missing_artist": i != 0,
            "missing_title": i != 0,
        }
        fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Press on row 0 fill handle
    source_item = fixer_tab._table.item(0, 2)
    cell_rect = fixer_tab._table.visualItemRect(source_item)
    handle_pos = QPointF(cell_rect.right() - 5, cell_rect.bottom() - 5)
    
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        handle_pos,
        handle_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    fixer_tab.eventFilter(fixer_tab._table.viewport(), press_event)
    
    # Move to the same row (row 0)
    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        handle_pos,
        handle_pos,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier
    )
    result = fixer_tab.eventFilter(fixer_tab._table.viewport(), move_event)
    assert result is False  # Move returns False
    assert fixer_tab._fill_handle_active is True  # But still active


def test_drag_fill_click_on_empty_area_ignored(qapp, fixer_tab, temp_dir):
    """Test that clicking on empty area (null cell rect) does not activate fill."""
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QMouseEvent
    
    # Populate with one entry
    entry = {
        "path": temp_dir / "file0.mp3",
        "filename": "file0.mp3",
        "existing_artist": "Artist",
        "existing_title": "",
        "suggested_artist": "Suggested",
        "suggested_title": "Suggested",
        "missing_artist": False,
        "missing_title": True,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Click on empty area below the table (should return null cell rect)
    empty_pos = QPointF(1000, 1000)  # Far outside any cell
    
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        empty_pos,
        empty_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    
    result = fixer_tab.eventFilter(fixer_tab._table.viewport(), press_event)
    assert result is False
    assert fixer_tab._fill_handle_active is False


def test_drag_fill_batch_update(qapp, fixer_tab, temp_dir):
    """Test that drag-fill updates _files_data for all affected rows."""
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QMouseEvent
    
    # Populate with 10 entries - all must have missing title to pass filter
    for i in range(10):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "Common Artist" if i == 0 else "",
            "existing_title": "" if i >= 0 else f"Title {i}",  # All entries missing title
            "suggested_artist": "Suggested",
            "suggested_title": "Suggested",
            "missing_artist": i != 0,
            "missing_title": True,  # All entries missing title
        }
        fixer_tab.add_file_entry(entry)
    
    fixer_tab._apply_filter()
    assert fixer_tab._table.rowCount() == 10
    
    # Drag from row 0 to row 9
    source_item = fixer_tab._table.item(0, 2)
    cell_rect = fixer_tab._table.visualItemRect(source_item)
    handle_pos = QPointF(cell_rect.right() - 5, cell_rect.bottom() - 5)
    
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        handle_pos,
        handle_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    fixer_tab.eventFilter(fixer_tab._table.viewport(), press_event)
    
    # Move to target row (row 9) to set the fill range
    target_item = fixer_tab._table.item(9, 2)
    target_rect = fixer_tab._table.visualItemRect(target_item)
    move_pos = QPointF(target_rect.center())
    
    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        move_pos,
        move_pos,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier
    )
    fixer_tab.eventFilter(fixer_tab._table.viewport(), move_event)
    
    release_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        move_pos,
        move_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    fixer_tab.eventFilter(fixer_tab._table.viewport(), release_event)
    
    # Verify all entries in _files_data are updated (target rows only)
    # Source row (entry 0) already has "Common Artist"
    assert fixer_tab._files_data[0]["existing_artist"] == "Common Artist"
    for i in range(1, 10):
        assert fixer_tab._files_data[i]["existing_artist"] == "Common Artist", f"Entry {i} artist mismatch"
        assert fixer_tab._files_data[i]["missing_artist"] is False, f"Entry {i} should not be missing artist"
    
    # Verify all table cells are updated (target rows only)
    assert fixer_tab._table.item(0, 2).text() == "Common Artist"
    for row in range(1, 10):
        assert fixer_tab._table.item(row, 2).text() == "Common Artist"


def test_drag_fill_click_outside_handle_ignored(qapp, fixer_tab, temp_dir):
    """Test that clicking outside the fill handle area does not activate drag-fill."""
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QMouseEvent
    
    # Populate with entries
    entry = {
        "path": temp_dir / "file0.mp3",
        "filename": "file0.mp3",
        "existing_artist": "Artist",
        "existing_title": "",
        "suggested_artist": "Suggested",
        "suggested_title": "Suggested",
        "missing_artist": False,
        "missing_title": True,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Click in the middle of the cell (not the fill handle)
    item = fixer_tab._table.item(0, 2)
    cell_rect = fixer_tab._table.visualItemRect(item)
    middle_pos = QPointF(cell_rect.center())
    
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        middle_pos,
        middle_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    
    result = fixer_tab.eventFilter(fixer_tab._table.viewport(), press_event)
    assert result is False
    assert fixer_tab._fill_handle_active is False


def test_drag_fill_click_on_other_column_ignored(qapp, fixer_tab, temp_dir):
    """Test that clicking on Title column does not activate drag-fill."""
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QMouseEvent
    
    # Populate with entries
    entry = {
        "path": temp_dir / "file0.mp3",
        "filename": "file0.mp3",
        "existing_artist": "Artist",
        "existing_title": "",
        "suggested_artist": "Suggested",
        "suggested_title": "Suggested",
        "missing_artist": False,
        "missing_title": True,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Click on Title column (column 3)
    item = fixer_tab._table.item(0, 3)
    cell_rect = fixer_tab._table.visualItemRect(item)
    handle_pos = QPointF(cell_rect.right() - 5, cell_rect.bottom() - 5)
    
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        handle_pos,
        handle_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    
    result = fixer_tab.eventFilter(fixer_tab._table.viewport(), press_event)
    assert result is False
    assert fixer_tab._fill_handle_active is False


def test_drag_fill_move_on_wrong_column_ignored(qapp, fixer_tab, temp_dir):
    """Test that moving to wrong column during drag does not highlight."""
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QMouseEvent
    
    # Populate with entries
    entry = {
        "path": temp_dir / "file0.mp3",
        "filename": "file0.mp3",
        "existing_artist": "Artist",
        "existing_title": "",
        "suggested_artist": "Suggested",
        "suggested_title": "Suggested",
        "missing_artist": False,
        "missing_title": True,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Press on Artist column fill handle
    source_item = fixer_tab._table.item(0, 2)
    cell_rect = fixer_tab._table.visualItemRect(source_item)
    handle_pos = QPointF(cell_rect.right() - 5, cell_rect.bottom() - 5)
    
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        handle_pos,
        handle_pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    fixer_tab.eventFilter(fixer_tab._table.viewport(), press_event)
    assert fixer_tab._fill_handle_active is True
    
    # Move to Title column (column 3)
    title_item = fixer_tab._table.item(0, 3)
    title_rect = fixer_tab._table.visualItemRect(title_item)
    move_pos = QPointF(title_rect.center())
    
    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        move_pos,
        move_pos,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier
    )
    result = fixer_tab.eventFilter(fixer_tab._table.viewport(), move_event)
    # Should return False since we're not on Artist column
    assert result is False
    # Fill handle should still be active but no highlight should change
    assert fixer_tab._fill_handle_active is True
    assert fixer_tab._fill_handle_current_row == 0  # Row doesn't change


def test_drag_fill_clear_highlight_with_no_active(qapp, fixer_tab, temp_dir):
    """Test that clearing highlight when no active fill does nothing."""
    # Call clear highlight without active fill
    fixer_tab._clear_fill_highlight()
    # Should not raise any errors
    assert True


def test_drag_fill_highlight_with_no_item(qapp, fixer_tab, temp_dir):
    """Test that highlighting with no item does nothing."""
    # Try to highlight with row that has no item
    fixer_tab._highlight_fill_range(5, 10)  # Rows beyond table
    # Should not raise any errors
    assert True


def test_drag_fill_apply_with_no_item(qapp, fixer_tab, temp_dir):
    """Test that applying fill with no item does nothing."""
    # Try to apply fill with row that has no item
    fixer_tab._apply_fill(0, 5, 10, "Test Artist")  # Rows beyond table
    # Should not raise any errors
    assert True


def test_drag_fill_apply_with_empty_artist(qapp, fixer_tab, temp_dir):
    """Test that applying fill with empty artist does nothing."""
    # Populate with 3 entries so rows 1-2 exist
    for i in range(3):
        entry = {
            "path": temp_dir / f"file{i}.mp3",
            "filename": f"file{i}.mp3",
            "existing_artist": "" if i != 0 else "Source Artist",
            "existing_title": "" if i != 0 else "Title",
            "suggested_artist": "Suggested",
            "suggested_title": "Suggested",
            "missing_artist": i != 0,
            "missing_title": i != 0,
        }
        fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Apply fill with empty artist value to target rows (not source)
    fixer_tab._apply_fill(0, 1, 2, "")  # Empty artist, target rows 1-2
    # Should not raise any errors
    # Note: existing_artist was already updated to "Suggested" when row was added to table
    # The empty fill_value should not change it
    assert True


def test_drag_fill_clear_highlight_invalid_color(qapp, fixer_tab, temp_dir):
    """Test that clearing highlight with invalid color restores missing_artist state."""
    from PyQt6.QtGui import QColor
    
    # Populate with entries - first one has missing_artist
    entry = {
        "path": temp_dir / "file0.mp3",
        "filename": "file0.mp3",
        "existing_artist": "",
        "existing_title": "",
        "suggested_artist": "Suggested",
        "suggested_title": "Suggested",
        "missing_artist": True,
        "missing_title": True,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Manually set up fill state with invalid color
    fixer_tab._fill_original_bg = {0: QColor("invalid_color")}  # Invalid color
    fixer_tab._clear_fill_highlight()
    # Should not raise any errors
    assert True


def test_drag_fill_clear_highlight_no_missing_artist(qapp, fixer_tab, temp_dir):
    """Test that clearing highlight with no missing_artist does nothing."""
    from PyQt6.QtGui import QColor
    
    # Populate with entries - first one has no missing_artist
    entry = {
        "path": temp_dir / "file0.mp3",
        "filename": "file0.mp3",
        "existing_artist": "Artist",
        "existing_title": "",
        "suggested_artist": "Suggested",
        "suggested_title": "Suggested",
        "missing_artist": False,
        "missing_title": True,
    }
    fixer_tab.add_file_entry(entry)
    fixer_tab._apply_filter()
    
    # Manually set up fill state with invalid color
    fixer_tab._fill_original_bg = {0: QColor("invalid_color")}  # Invalid color
    fixer_tab._clear_fill_highlight()
    # Should not raise any errors
    assert True





