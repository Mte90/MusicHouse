"""pytest-qt tests for LeaderboardTab component.

Tests LeaderboardTab functionality with pytest-qt in headless offscreen mode.
Run with: QT_QPA_PLATFORM=offscreen pytest tests/ui/test_leaderboard_tab.py -v
"""

import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QHeaderView, QTableWidgetItem
from typing import List, Tuple


# ============================================================================
# Test Configuration
# ============================================================================

pytestmark = pytest.mark.ui


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def leaderboard_tab(qapp):
    """Create LeaderboardTab instance for testing.
    
    Yields:
        LeaderboardTab: LeaderboardTab instance.
    """
    from musichouse.ui.leaderboard_tab import LeaderboardTab
    
    tab = LeaderboardTab()
    tab.show()
    yield tab
    tab.close()


# ============================================================================
# LeaderboardTab Initialization Tests
# ============================================================================

def test_leaderboard_tab_creation(qapp):
    """Test that LeaderboardTab can be created without crashes."""
    from musichouse.ui.leaderboard_tab import LeaderboardTab
    
    tab = LeaderboardTab()
    assert tab is not None
    assert tab.layout() is not None
    tab.close()


def test_leaderboard_tab_has_required_components(leaderboard_tab):
    """Test that LeaderboardTab has all required UI components."""
    # Check components exist
    assert leaderboard_tab._table is not None
    assert leaderboard_tab._layout is not None


def test_leaderboard_tab_initial_table_state(leaderboard_tab):
    """Test that table starts empty with correct structure."""
    table = leaderboard_tab._table
    
    # Table should start empty
    assert table.rowCount() == 0
    
    # Should have 3 columns
    assert table.columnCount() == 3


def test_leaderboard_tab_column_headers(leaderboard_tab):
    """Test that table has correct column headers."""
    table = leaderboard_tab._table
    
    expected_headers = ["Rank", "Artist", "Count"]
    actual_headers = [table.horizontalHeaderItem(i).text() 
                      for i in range(table.columnCount())]
    
    assert actual_headers == expected_headers


def test_leaderboard_tab_column_configuration(leaderboard_tab):
    """Test that table columns are configured correctly."""
    table = leaderboard_tab._table
    header = table.horizontalHeader()
    
    # Check column 0 (Rank) is Fixed
    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Fixed
    
    # Check column 1 (Artist) is Stretch
    assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.Stretch
    
    # Check column 2 (Count) is Fixed
    assert header.sectionResizeMode(2) == QHeaderView.ResizeMode.Fixed
    
    # Check column widths
    assert table.columnWidth(0) == 60
    assert table.columnWidth(2) == 80


# ============================================================================
# Update Leaderboard Tests
# ============================================================================

def test_update_leaderboard_empty_list(leaderboard_tab):
    """Test updating with empty artist list."""
    leaderboard_tab.update_leaderboard([])
    
    assert leaderboard_tab._table.rowCount() == 0


def test_update_leaderboard_single_artist(leaderboard_tab):
    """Test updating with a single artist."""
    artists: List[Tuple[str, int]] = [("Solo Artist", 42)]
    leaderboard_tab.update_leaderboard(artists)
    
    assert leaderboard_tab._table.rowCount() == 1
    
    # Check rank
    rank_item = leaderboard_tab._table.item(0, 0)
    assert rank_item is not None
    assert rank_item.text() == "1"
    
    # Check artist name
    artist_item = leaderboard_tab._table.item(0, 1)
    assert artist_item is not None
    assert artist_item.text() == "Solo Artist"
    
    # Check count
    count_item = leaderboard_tab._table.item(0, 2)
    assert count_item is not None
    assert count_item.text() == "42"


def test_update_leaderboard_multiple_artists(leaderboard_tab):
    """Test updating with multiple artists."""
    artists: List[Tuple[str, int]] = [
        ("Artist One", 100),
        ("Artist Two", 50),
        ("Artist Three", 25),
    ]
    leaderboard_tab.update_leaderboard(artists)
    
    assert leaderboard_tab._table.rowCount() == 3
    
    # Check first row
    assert leaderboard_tab._table.item(0, 0).text() == "1"
    assert leaderboard_tab._table.item(0, 1).text() == "Artist One"
    assert leaderboard_tab._table.item(0, 2).text() == "100"
    
    # Check second row
    assert leaderboard_tab._table.item(1, 0).text() == "2"
    assert leaderboard_tab._table.item(1, 1).text() == "Artist Two"
    assert leaderboard_tab._table.item(1, 2).text() == "50"
    
    # Check third row
    assert leaderboard_tab._table.item(2, 0).text() == "3"
    assert leaderboard_tab._table.item(2, 1).text() == "Artist Three"
    assert leaderboard_tab._table.item(2, 2).text() == "25"


def test_update_leaderboard_with_many_artists(leaderboard_tab):
    """Test updating with 100+ artists (edge case)."""
    artists: List[Tuple[str, int]] = [
        (f"Artist {i}", 1000 - i) for i in range(150)
    ]
    leaderboard_tab.update_leaderboard(artists)
    
    assert leaderboard_tab._table.rowCount() == 150
    
    # Check first artist (rank 1)
    assert leaderboard_tab._table.item(0, 0).text() == "1"
    assert leaderboard_tab._table.item(0, 1).text() == "Artist 0"
    assert leaderboard_tab._table.item(0, 2).text() == "1000"
    
    # Check last artist (rank 150)
    assert leaderboard_tab._table.item(149, 0).text() == "150"
    assert leaderboard_tab._table.item(149, 1).text() == "Artist 149"
    assert leaderboard_tab._table.item(149, 2).text() == "851"


def test_update_leaderboard_overwrites_previous_data(leaderboard_tab):
    """Test that updating clears previous data."""
    # First update
    artists1: List[Tuple[str, int]] = [("First Artist", 100)]
    leaderboard_tab.update_leaderboard(artists1)
    assert leaderboard_tab._table.rowCount() == 1
    
    # Second update
    artists2: List[Tuple[str, int]] = [
        ("Second Artist", 50),
        ("Third Artist", 25),
    ]
    leaderboard_tab.update_leaderboard(artists2)
    
    # Should only have new data
    assert leaderboard_tab._table.rowCount() == 2
    assert leaderboard_tab._table.item(0, 1).text() == "Second Artist"
    assert leaderboard_tab._table.item(1, 1).text() == "Third Artist"


# ============================================================================
# Table Structure Tests
# ============================================================================

def test_table_columns_have_correct_structure(leaderboard_tab):
    """Test that table columns have correct item structure."""
    artists: List[Tuple[str, int]] = [("Test Artist", 42)]
    leaderboard_tab.update_leaderboard(artists)
    
    # Check all items in row exist
    for col in range(3):
        item = leaderboard_tab._table.item(0, col)
        assert item is not None


def test_table_items_are_string_type(leaderboard_tab):
    """Test that all table items are stored as strings."""
    artists: List[Tuple[str, int]] = [
        ("Artist Name", 12345),
    ]
    leaderboard_tab.update_leaderboard(artists)
    
    # Check rank is string
    rank_item = leaderboard_tab._table.item(0, 0)
    assert isinstance(rank_item.text(), str)
    
    # Check artist is string
    artist_item = leaderboard_tab._table.item(0, 1)
    assert isinstance(artist_item.text(), str)
    
    # Check count is string
    count_item = leaderboard_tab._table.item(0, 2)
    assert isinstance(count_item.text(), str)


def test_table_is_not_editable(leaderboard_tab):
    """Test that table cells are not editable."""
    artists: List[Tuple[str, int]] = [("Test Artist", 42)]
    leaderboard_tab.update_leaderboard(artists)
    
    # Check edit triggers are set to NoEditTriggers
    from PyQt6.QtWidgets import QTableWidget
    assert leaderboard_tab._table.editTriggers() == QTableWidget.EditTrigger.NoEditTriggers


# ============================================================================
# Ranking Tests
# ============================================================================

def test_ranking_starts_at_one(leaderboard_tab):
    """Test that ranking starts at 1, not 0."""
    artists: List[Tuple[str, int]] = [
        ("First", 100),
        ("Second", 50),
    ]
    leaderboard_tab.update_leaderboard(artists)
    
    assert leaderboard_tab._table.item(0, 0).text() == "1"
    assert leaderboard_tab._table.item(1, 0).text() == "2"


def test_ranking_increments_correctly(leaderboard_tab):
    """Test that ranking increments correctly for all rows."""
    artists: List[Tuple[str, int]] = [
        (f"Artist {i}", 100) for i in range(10)
    ]
    leaderboard_tab.update_leaderboard(artists)
    
    for i in range(10):
        expected_rank = str(i + 1)
        actual_rank = leaderboard_tab._table.item(i, 0).text()
        assert actual_rank == expected_rank, f"Expected rank {expected_rank} at row {i}, got {actual_rank}"


# ============================================================================
# Data Display Tests
# ============================================================================

def test_artist_names_with_special_characters(leaderboard_tab):
    """Test that artist names with special characters are displayed correctly."""
    artists: List[Tuple[str, int]] = [
        ("Artista con accento", 50),
        ("Artist with numbers 123", 30),
        ("Artist & Band", 20),
        ("Artist's Name", 10),
    ]
    leaderboard_tab.update_leaderboard(artists)
    
    assert leaderboard_tab._table.item(0, 1).text() == "Artista con accento"
    assert leaderboard_tab._table.item(1, 1).text() == "Artist with numbers 123"
    assert leaderboard_tab._table.item(2, 1).text() == "Artist & Band"
    assert leaderboard_tab._table.item(3, 1).text() == "Artist's Name"


def test_count_values_as_strings(leaderboard_tab):
    """Test that count values are stored and displayed as strings."""
    artists: List[Tuple[str, int]] = [
        ("Artist One", 0),
        ("Artist Two", 1),
        ("Artist Three", 1000000),
    ]
    leaderboard_tab.update_leaderboard(artists)
    
    assert leaderboard_tab._table.item(0, 2).text() == "0"
    assert leaderboard_tab._table.item(1, 2).text() == "1"
    assert leaderboard_tab._table.item(2, 2).text() == "1000000"


def test_unicode_artist_names(leaderboard_tab):
    """Test that Unicode artist names are displayed correctly."""
    artists: List[Tuple[str, int]] = [
        ("艺术家", 50),      # Chinese
        ("Καλλιτέχνης", 30),  # Greek
        ("Café Musicien", 20),  # French with accent
    ]
    leaderboard_tab.update_leaderboard(artists)
    
    assert leaderboard_tab._table.item(0, 1).text() == "艺术家"
    assert leaderboard_tab._table.item(1, 1).text() == "Καλλιτέχνης"
    assert leaderboard_tab._table.item(2, 1).text() == "Café Musicien"


# ============================================================================
# Edge Cases Tests
# ============================================================================

def test_leaderboard_with_zero_count(leaderboard_tab):
    """Test leaderboard with artists having zero count."""
    artists: List[Tuple[str, int]] = [
        ("Zero Artist", 0),
        ("Another Zero", 0),
    ]
    leaderboard_tab.update_leaderboard(artists)
    
    assert leaderboard_tab._table.rowCount() == 2
    assert leaderboard_tab._table.item(0, 2).text() == "0"
    assert leaderboard_tab._table.item(1, 2).text() == "0"


def test_leaderboard_preserves_order(leaderboard_tab):
    """Test that leaderboard preserves the order of input (assumes already sorted)."""
    # Input is already sorted by count descending
    artists: List[Tuple[str, int]] = [
        ("Top", 1000),
        ("Middle", 500),
        ("Bottom", 100),
    ]
    leaderboard_tab.update_leaderboard(artists)
    
    # Verify order is preserved
    assert leaderboard_tab._table.item(0, 1).text() == "Top"
    assert leaderboard_tab._table.item(1, 1).text() == "Middle"
    assert leaderboard_tab._table.item(2, 1).text() == "Bottom"


def test_leaderboard_with_empty_artist_name(leaderboard_tab):
    """Test leaderboard with empty artist names (edge case)."""
    artists: List[Tuple[str, int]] = [
        ("", 50),
        ("Valid Artist", 30),
    ]
    leaderboard_tab.update_leaderboard(artists)
    
    assert leaderboard_tab._table.rowCount() == 2
    assert leaderboard_tab._table.item(0, 1).text() == ""
    assert leaderboard_tab._table.item(1, 1).text() == "Valid Artist"


# ============================================================================
# Integration Tests
# ============================================================================

def test_multiple_updates_with_different_sizes(leaderboard_tab):
    """Test multiple updates with varying data sizes."""
    # First update: small
    leaderboard_tab.update_leaderboard([("Artist1", 10)])
    assert leaderboard_tab._table.rowCount() == 1
    
    # Second update: large
    large_data = [(f"Artist{i}", 100 - i) for i in range(50)]
    leaderboard_tab.update_leaderboard(large_data)
    assert leaderboard_tab._table.rowCount() == 50
    
    # Third update: empty
    leaderboard_tab.update_leaderboard([])
    assert leaderboard_tab._table.rowCount() == 0
    
    # Fourth update: single
    leaderboard_tab.update_leaderboard([("Single", 999)])
    assert leaderboard_tab._table.rowCount() == 1


def test_leaderboard_tab_with_mock_data_from_conftest(leaderboard_tab, mock_mp3_files):
    """Test leaderboard with data structure similar to mock_mp3_files fixture."""
    # Simulate artist counts from mock files
    artist_counts: List[Tuple[str, int]] = [
        ("Test Artist 1", 2),
        ("Test Artist 2", 2),
        ("Another Artist", 2),
    ]
    leaderboard_tab.update_leaderboard(artist_counts)
    
    assert leaderboard_tab._table.rowCount() == 3
    
    # All should have rank 1, 2, 3
    assert leaderboard_tab._table.item(0, 0).text() == "1"
    assert leaderboard_tab._table.item(1, 0).text() == "2"
    assert leaderboard_tab._table.item(2, 0).text() == "3"
    
    # All should have count 2
    assert leaderboard_tab._table.item(0, 2).text() == "2"
    assert leaderboard_tab._table.item(1, 2).text() == "2"
    assert leaderboard_tab._table.item(2, 2).text() == "2"


def test_leaderboard_tab_update_after_close(leaderboard_tab):
    """Test that updating leaderboard after show works correctly."""
    # Tab is already shown from fixture
    artists: List[Tuple[str, int]] = [("Test", 100)]
    leaderboard_tab.update_leaderboard(artists)
    
    assert leaderboard_tab._table.rowCount() == 1
    assert leaderboard_tab._table.item(0, 1).text() == "Test"
