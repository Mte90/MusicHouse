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
    with patch('PyQt6.QtWidgets.QMessageBox') as MockMsgBox:
        fixer_tab._show_failure_summary([], 5)
        
        MockMsgBox.assert_called_once()
        mock_instance = MockMsgBox.return_value
        mock_instance.setWindowTitle.assert_called_once_with("Fix Complete")
        mock_instance.exec.assert_called_once()


def test_show_failure_summary_with_failures(qapp, temp_dir):
    """Test _show_failure_summary with failures shows grouped dialog."""
    from musichouse.ui.fixer_tab import FixerTab
    from PyQt6.QtWidgets import QDialog
    
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
    
    with patch.object(fixer_tab, '_mark_failed_row'):
        fixer_tab._on_fix_finished(0, 1)
    
    assert fixer_tab._progress_bar.isVisible() is False


def test_update_db_after_fix_success(fixer_tab, temp_dir):
    """Test _update_db_after_fix updates database correctly."""
    from pathlib import Path
    
    fixed_paths = [temp_dir / "file1.mp3", temp_dir / "file2.mp3"]
    
    with patch('musichouse.leaderboard_cache.LeaderboardCache') as MockCache:
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
    
    with patch('musichouse.leaderboard_cache.LeaderboardCache') as MockCache:
        MockCache.side_effect = Exception("DB error")
        
        fixer_tab._update_db_after_fix([Path("file1.mp3")])
        
        MockCache.assert_called_once()





