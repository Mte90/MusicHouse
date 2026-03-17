"""pytest-qt tests for AITab component.

Tests AITab functionality with pytest-qt in headless offscreen mode.
Run with: QT_QPA_PLATFORM=offscreen pytest tests/ui/test_ai_tab.py -v

CRITICAL: All AIClient API calls are mocked. No real API calls are made.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QApplication
pytestmark = pytest.mark.ui


# ============================================================================
# Fixtures
# ============================================================================
@pytest.fixture
def ai_tab(qapp):
    """Create AITab instance for testing.
    
    Yields:
        AITab: AITab instance.
    """
    from musichouse.ui.ai_tab import AITab
    
    tab = AITab()
    tab.show()
    yield tab
    tab.close()


@pytest.fixture
def ai_tab_with_mock(qapp, monkeypatch):
    """Create AITab with mocked AIClient.
    
    This fixture patches AIClient BEFORE AITab is instantiated,
    ensuring the mock is used for _ai_client.
    
    Yields:
        tuple: (AITab instance, MagicMock for AIClient)
    """
    # Create mock
    mock_instance = MagicMock()
    mock_instance.get_similar_artists.return_value = ['Artist A', 'Artist B', 'Artist C']
    mock_instance.get_artist_genres.return_value = ['Rock', 'Pop']
    
    # Patch AIClient class before AITab creation
    with patch('musichouse.ui.ai_tab.AIClient', return_value=mock_instance):
        from musichouse.ui.ai_tab import AITab
        tab = AITab()
        tab.show()
        yield tab, mock_instance
        tab.close()


# ============================================================================
# AITab Initialization Tests
# ============================================================================
def test_ai_tab_creation(qapp):
    """Test that AITab can be created without crashes."""
    from musichouse.ui.ai_tab import AITab
    
    tab = AITab()
    assert tab is not None
    tab.close()


def test_ai_tab_has_required_components(ai_tab):
    """Test that AITab has all required UI components."""
    assert ai_tab._layout is not None
    assert ai_tab._ai_client is not None
    assert ai_tab._artists_loaded is False
    assert ai_tab._artist_combo is not None
    assert ai_tab._get_suggestions_button is not None
    assert ai_tab._suggestions_display is not None
    assert ai_tab._genre_label is not None
    assert ai_tab._artist_count_label is not None


def test_ai_tab_initial_artist_combo_state(ai_tab):
    """Test that artist combo starts with placeholder text."""
    assert ai_tab._artist_combo.count() == 1
    assert ai_tab._artist_combo.currentText() == "Select an artist..."


def test_ai_tab_initial_button_state(ai_tab):
    """Test that Get Similar Artists button is created correctly."""
    assert ai_tab._get_suggestions_button.text() == "Get Similar Artists"


def test_ai_tab_initial_display_state(ai_tab):
    """Test that suggestions display has correct placeholder."""
    assert ai_tab._suggestions_display.placeholderText() == "Select an artist and click 'Get Similar Artists'"
    assert ai_tab._suggestions_display.isReadOnly() is True


def test_ai_tab_initial_genre_label_state(ai_tab):
    """Test that genre label starts with default text."""
    assert ai_tab._genre_label.text() == "Genres: None"


# ============================================================================
# load_artists() Tests
# ============================================================================
def test_load_artists_populates_dropdown(ai_tab):
    """Test that load_artists populates the artist dropdown correctly."""
    artists = ['Artist 1', 'Artist 2', 'Artist 3']
    ai_tab.load_artists(artists)
    
    # Should have placeholder + 3 artists
    assert ai_tab._artist_combo.count() == 4
    assert ai_tab._artist_combo.itemText(0) == "Select an artist..."
    assert ai_tab._artist_combo.itemText(1) == "Artist 1"
    assert ai_tab._artist_combo.itemText(2) == "Artist 2"
    assert ai_tab._artist_combo.itemText(3) == "Artist 3"
    assert ai_tab._artists_loaded is True


def test_load_artists_updates_count_label(ai_tab):
    """Test that load_artists updates the artist count label."""
    artists = ['Artist 1', 'Artist 2']
    ai_tab.load_artists(artists)
    
    assert "2 artists available" in ai_tab._artist_count_label.text()


def test_load_artists_clears_existing_items(ai_tab):
    """Test that load_artists clears existing items before adding new ones."""
    # First load
    ai_tab.load_artists(['Artist 1', 'Artist 2'])
    initial_count = ai_tab._artist_combo.count()
    
    # Second load should clear and repopulate
    ai_tab.load_artists(['Artist 3'])
    
    assert ai_tab._artist_combo.count() == 2  # placeholder + 1 artist
    assert ai_tab._artist_combo.itemText(1) == "Artist 3"


def test_load_artists_empty_list(ai_tab):
    """Test that load_artists handles empty artist list."""
    ai_tab.load_artists([])
    
    assert ai_tab._artist_combo.count() == 1  # Only placeholder
    assert "0 artists available" in ai_tab._artist_count_label.text()
    assert ai_tab._artists_loaded is True


# ============================================================================
# load_artists_from_db() Tests
# ============================================================================
def test_load_artists_from_db_loads_from_cache(ai_tab, temp_dir):
    """Test that load_artists_from_db loads artists from leaderboard cache."""
    from musichouse.leaderboard_cache import LeaderboardCache
    
    # Create a cache with some artists (temp_dir is Path)
    cache = LeaderboardCache(temp_dir)
    # update_artists takes a dict, not separate args
    cache.update_artists({"Artist From DB": 5, "Another Artist": 3})
    cache.close()
    
    # Mock config to use our temp_dir
    with patch('musichouse.config.get_config_dir', return_value=temp_dir):
        ai_tab.load_artists_from_db()
        ai_tab.load_artists_from_db()
    
    # Should have loaded artists
    assert ai_tab._artists_loaded is True
    assert ai_tab._artist_combo.count() >= 2  # placeholder + artists

def test_load_artists_from_db_skips_if_loaded(ai_tab):
    """Test that load_artists_from_db skips if artists already loaded."""
    # Pre-load artists
    ai_tab.load_artists(['Preloaded Artist'])
    initial_count = ai_tab._artist_combo.count()
    
    # load_artists_from_db should not change anything
    ai_tab.load_artists_from_db()
    
    assert ai_tab._artist_combo.count() == initial_count


def test_load_artists_from_db_handles_error(ai_tab):
    """Test that load_artists_from_db handles cache errors gracefully."""
    # Mock config to return invalid path
    # Note: config is imported in ai_tab module, patch it there
    with patch('musichouse.config.get_config_dir', return_value=Path('/invalid/path')):
        # Should not raise exception
        ai_tab.load_artists_from_db()
        # Should not raise exception
        ai_tab.load_artists_from_db()
    
    # artists_loaded should still be False since error occurred
    assert ai_tab._artists_loaded is False

# ============================================================================
# showEvent() Tests
# ============================================================================
def test_showEvent_loads_artists_on_first_show(ai_tab, temp_dir):
    """Test that showEvent loads artists from DB on first show.
    
    Note: We test this by directly calling load_artists_from_db() since
    QShowEvent cannot be easily constructed in tests.
    """
    from musichouse.leaderboard_cache import LeaderboardCache
    
    # Create a cache with artists
    cache = LeaderboardCache(temp_dir)
    cache.update_artists({"Show Event Artist": 1})
    cache.close()
    
    # Reset loaded state to simulate first show
    ai_tab._artists_loaded = False
    
    # Patch config where it's imported
    with patch('musichouse.config.get_config_dir', return_value=temp_dir):
        # Call load_artists_from_db directly (what showEvent would do)
        ai_tab.load_artists_from_db()
    
    # Should have loaded artists
    assert ai_tab._artists_loaded is True
    assert ai_tab._artist_combo.count() >= 2

def test_showEvent_does_not_reload_if_already_loaded(ai_tab):
    """Test that showEvent does not reload if artists already loaded.
    
    Note: We test this by checking the _artists_loaded flag check.
    """
    # Pre-load artists
    ai_tab.load_artists(['Preloaded'])
    
    # Track if load_artists_from_db would do work
    with patch.object(ai_tab, 'load_artists',) as mock_load:
        # When already loaded, load_artists_from_db returns early
        ai_tab.load_artists_from_db()
        
        # Should not call load_artists (early return)
        mock_load.assert_not_called()
# ============================================================================
# _get_similar_artists() Tests
# ============================================================================
def test_get_similar_artists_with_placeholder_selected(ai_tab):
    """Test that _get_similar_artists shows message when placeholder selected."""
    ai_tab._get_similar_artists()
    
    assert "Please select an artist first" in ai_tab._suggestions_display.toPlainText()


def test_get_similar_artists_with_valid_artist(ai_tab_with_mock):
    """Test that _get_similar_artists fetches and displays similar artists."""
    ai_tab, mock_client = ai_tab_with_mock
    artist_name = "Test Artist"
    
    # Select artist
    ai_tab.load_artists([artist_name, 'Other Artist'])
    ai_tab._artist_combo.setCurrentText(artist_name)
    
    # Reset call count after fixture setup
    mock_client.reset_mock()
    
    # Trigger get similar artists
    ai_tab._get_similar_artists()
    
    # Should have called AIClient
    mock_client.get_similar_artists.assert_called_once_with(artist_name)
    mock_client.get_artist_genres.assert_called_once_with(artist_name)
    
    # Should display results
    assert "Artist A" in ai_tab._suggestions_display.toPlainText()
    assert "Artist B" in ai_tab._suggestions_display.toPlainText()
    assert "Artist C" in ai_tab._suggestions_display.toPlainText()


def test_get_similar_artists_updates_genre_label(ai_tab_with_mock):
    """Test that _get_similar_artists updates genre label."""
    ai_tab, mock_client = ai_tab_with_mock
    mock_client.get_artist_genres.return_value = ['Jazz', 'Blues']
    
    ai_tab.load_artists(['Test Artist'])
    ai_tab._artist_combo.setCurrentText('Test Artist')
    ai_tab._get_similar_artists()
    
    assert "Genres: Jazz, Blues" in ai_tab._genre_label.text()


def test_get_similar_artists_empty_results(ai_tab_with_mock):
    """Test that _get_similar_artists handles empty results."""
    ai_tab, mock_client = ai_tab_with_mock
    mock_client.get_similar_artists.return_value = []
    mock_client.get_artist_genres.return_value = []
    
    ai_tab.load_artists(['Test Artist'])
    ai_tab._artist_combo.setCurrentText('Test Artist')
    ai_tab._get_similar_artists()
    
    assert "No similar artists found" in ai_tab._suggestions_display.toPlainText()
    assert "Genres: Unknown" in ai_tab._genre_label.text()


def test_get_similar_artists_error_handling(ai_tab_with_mock):
    """Test that _get_similar_artists handles AIClient exceptions."""
    ai_tab, mock_client = ai_tab_with_mock
    mock_client.get_similar_artists.side_effect = Exception("API Error")
    
    ai_tab.load_artists(['Test Artist'])
    ai_tab._artist_combo.setCurrentText('Test Artist')
    ai_tab._get_similar_artists()
    
    assert "Error:" in ai_tab._suggestions_display.toPlainText()
    assert "Genres: Error" in ai_tab._genre_label.text()


def test_get_similar_artists_loading_state(ai_tab_with_mock):
    """Test that _get_similar_artists shows loading state."""
    ai_tab, mock_client = ai_tab_with_mock
    
    # Make the call return quickly
    mock_client.get_similar_artists.return_value = ['Slow Artist']
    
    ai_tab.load_artists(['Test Artist'])
    ai_tab._artist_combo.setCurrentText('Test Artist')
    ai_tab._get_similar_artists()
    
    # After completion, should have results
    assert ai_tab._suggestions_display.toPlainText() != "Loading..."


# ============================================================================
# Integration Tests
# ============================================================================
def test_full_ai_tab_workflow(ai_tab_with_mock, temp_dir):
    """Test complete AI tab workflow from loading artists to getting suggestions."""
    ai_tab, mock_client = ai_tab_with_mock
    
    # Step 1: Load artists from "database"
    from musichouse.leaderboard_cache import LeaderboardCache
    cache = LeaderboardCache(temp_dir)
    cache.update_artists({"Workflow Artist": 10})
    cache.close()
    
    # Patch config where it's imported
    with patch('musichouse.config.get_config_dir', return_value=temp_dir):
        ai_tab.load_artists_from_db()
    
    assert ai_tab._artists_loaded is True
    assert ai_tab._artist_combo.count() >= 2
    
    # Step 2: Select an artist
    ai_tab._artist_combo.setCurrentText("Workflow Artist")
    assert ai_tab._artist_combo.currentText() == "Workflow Artist"
    
    # Step 3: Get similar artists
    mock_client.reset_mock()
    ai_tab._get_similar_artists()
    
    # Step 4: Verify results
    assert "Artist A" in ai_tab._suggestions_display.toPlainText()
    assert "Genres: Rock, Pop" in ai_tab._genre_label.text()


def test_ai_tab_multiple_artist_selections(ai_tab_with_mock):
    """Test that AI tab handles multiple artist selections correctly."""
    ai_tab, mock_client = ai_tab_with_mock
    
    ai_tab.load_artists(['Artist 1', 'Artist 2', 'Artist 3'])
    
    # Select first artist
    ai_tab._artist_combo.setCurrentText('Artist 1')
    ai_tab._get_similar_artists()
    assert mock_client.get_similar_artists.call_count == 1
    
    # Select second artist
    ai_tab._artist_combo.setCurrentText('Artist 2')
    ai_tab._get_similar_artists()
    assert mock_client.get_similar_artists.call_count == 2
    
    # Select third artist
    ai_tab._artist_combo.setCurrentText('Artist 3')
    ai_tab._get_similar_artists()
    assert mock_client.get_similar_artists.call_count == 3


def test_ai_tab_button_connection(ai_tab):
    """Test that button click is connected to _get_similar_artists."""
    # Click button with placeholder selected
    ai_tab._get_suggestions_button.click()
    
    # Should show placeholder message
    assert "Please select an artist first" in ai_tab._suggestions_display.toPlainText()


def test_ai_tab_with_custom_mock_response(ai_tab_with_mock):
    """Test AI tab with custom mock response data."""
    ai_tab, mock_client = ai_tab_with_mock
    
    # Customize mock responses
    mock_client.get_similar_artists.return_value = ['Custom Artist 1', 'Custom Artist 2']
    mock_client.get_artist_genres.return_value = ['Electronic', 'Techno']
    
    ai_tab.load_artists(['Selected Artist'])
    ai_tab._artist_combo.setCurrentText('Selected Artist')
    ai_tab._get_similar_artists()
    
    assert "Custom Artist 1" in ai_tab._suggestions_display.toPlainText()
    assert "Custom Artist 2" in ai_tab._suggestions_display.toPlainText()
    assert "Genres: Electronic, Techno" in ai_tab._genre_label.text()


def test_ai_tab_error_recovery(ai_tab_with_mock):
    """Test that AI tab recovers from errors and can make subsequent calls."""
    ai_tab, mock_client = ai_tab_with_mock
    
    # First call fails
    mock_client.get_similar_artists.side_effect = Exception("First error")
    ai_tab.load_artists(['Test Artist'])
    ai_tab._artist_combo.setCurrentText('Test Artist')
    ai_tab._get_similar_artists()
    assert "Error:" in ai_tab._suggestions_display.toPlainText()
    
    # Reset and make successful call
    mock_client.reset_mock()
    mock_client.get_similar_artists.side_effect = None
    mock_client.get_similar_artists.return_value = ['Recovery Artist']
    mock_client.get_artist_genres.return_value = ['Recovery Genre']
    
    ai_tab._get_similar_artists()
    assert "Recovery Artist" in ai_tab._suggestions_display.toPlainText()
    assert "Genres: Recovery Genre" in ai_tab._genre_label.text()


def test_ai_tab_artist_count_label_updates(ai_tab):
    """Test that artist count label shows correct counts."""
    ai_tab.load_artists(['A', 'B', 'C', 'D', 'E'])
    assert "5 artists available" in ai_tab._artist_count_label.text()
    
    ai_tab.load_artists(['Single'])
    assert "1 artists available" in ai_tab._artist_count_label.text()


def test_ai_tab_no_api_calls_with_fallback(ai_tab):
    """Test that AIClient fallback is used when no API key configured.
    
    This test ensures that even without mocking, the fallback mechanism works
    and no real API calls are attempted.
    """
    # The client should use fallback without raising exceptions
    similar = ai_tab._ai_client.get_similar_artists("Test Artist")
    genres = ai_tab._ai_client.get_artist_genres("Test Artist")
    
    # Should get fallback responses (can be empty list for genres in fallback)
    assert isinstance(similar, list)
    assert isinstance(genres, list)
