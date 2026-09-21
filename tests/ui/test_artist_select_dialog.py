from PyQt6.QtWidgets import QApplication

from musichouse.ui.artist_select_dialog import ArtistSelectDialog

app = QApplication([])

def test_dialog_initialization():
    artists = [("Artist A", 10), ("Artist B", 5)]
    dialog = ArtistSelectDialog(artists)
    assert dialog.get_selected_artists() == []
    assert dialog._ok_button.isEnabled() is False

def test_dialog_selection():
    artists = [("Artist A", 10), ("Artist B", 5)]
    dialog = ArtistSelectDialog(artists)
    
    # Select Artist A
    cb_a = dialog._checkboxes[0]
    cb_a.click()
    assert "Artist A" in dialog.get_selected_artists()
    assert dialog._ok_button.isEnabled() is True
    
    # Deselect Artist A
    cb_a.click()
    assert "Artist A" not in dialog.get_selected_artists()
    assert dialog._ok_button.isEnabled() is False

def test_dialog_filtering():
    # Use artist names that don't share common substrings
    artists = [("Radiohead", 10), ("Muse", 5), ("Coldplay", 2)]
    dialog = ArtistSelectDialog(artists)
    dialog.show()  # Ensure widgets are fully realized
    
    # Filter for "Radio"
    dialog._filter_artists("Radio")
    assert dialog._checkboxes[0].parentWidget().isVisible() is True  # Radiohead
    assert dialog._checkboxes[1].parentWidget().isVisible() is False  # Muse
    assert dialog._checkboxes[2].parentWidget().isVisible() is False  # Coldplay
    
    # Filter for "Muse"
    dialog._filter_artists("Muse")
    assert dialog._checkboxes[0].parentWidget().isVisible() is False  # Radiohead
    assert dialog._checkboxes[1].parentWidget().isVisible() is True  # Muse
    assert dialog._checkboxes[2].parentWidget().isVisible() is False  # Coldplay
    
    # Filter for "play" (matches Coldplay)
    dialog._filter_artists("play")
    assert dialog._checkboxes[0].parentWidget().isVisible() is False  # Radiohead
    assert dialog._checkboxes[1].parentWidget().isVisible() is False  # Muse
    assert dialog._checkboxes[2].parentWidget().isVisible() is True  # Coldplay

def test_dialog_empty_artists():
    dialog = ArtistSelectDialog([])
    assert dialog.get_selected_artists() == []
    assert dialog._ok_button.isEnabled() is False


def test_populate_list_with_empty_list():
    """Test that _populate_list handles empty artist list gracefully."""
    dialog = ArtistSelectDialog([])  # Empty list
    # Should not raise any errors
    assert dialog._checkboxes == []


def test_populate_list_repopulates():
    """Test that _populate_list clears and repopulates correctly."""
    dialog = ArtistSelectDialog([("Artist A", 10)])
    initial_count = len(dialog._checkboxes)
    assert initial_count == 1
    
    # Repopulate with different artists
    dialog._artists_with_counts = [("Artist B", 5), ("Artist C", 3)]
    dialog._populate_list()
    
    assert len(dialog._checkboxes) == 2
    assert dialog._checkboxes[0].text() == "Artist B"


def test_filter_artists_with_none_row():
    """Test that _filter_artists handles checkbox with no parent gracefully."""
    dialog = ArtistSelectDialog([("Artist A", 10)])
    
    # Manually set the checkbox parent to None to test the if row: branch
    cb = dialog._checkboxes[0]
    cb.setParent(None)  # This makes parentWidget() return None
    
    # The filter should not crash even if row is None
    dialog._filter_artists("test")
    
    # Should complete without error - the if row: check handles None
