"""Unit tests for tag_writer module.

Tests for write_tags() function and TagPreviewDialog class.
Uses mocking to avoid modifying real MP3 files.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import eyed3

from musichouse.tag_writer import write_tags, TagPreviewDialog


# ============================================================================
# write_tags() Tests
# ============================================================================

class TestWriteTags:
    """Tests for write_tags() function."""

    def test_write_tags_valid_file(self, temp_dir):
        """Test write_tags() with a valid MP3 file."""
        # Create a mock MP3 file
        mp3_file = temp_dir / "Test Artist - Test Title.mp3"
        mp3_file.write_bytes(
            b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100
        )

        # Mock eyed3 to avoid actually writing to file
        with patch('musichouse.tag_writer.load_mp3_safely') as mock_load:
            mock_audiofile = MagicMock()
            mock_tag = MagicMock()
            mock_tag.artist = ""
            mock_tag.title = ""
            mock_tag.genre = None
            mock_audiofile.tag = mock_tag
            mock_load.return_value = mock_audiofile

            result = write_tags(mp3_file, "New Artist", "New Title")

            assert result is True
            mock_audiofile.tag.save.assert_called_once()

    def test_write_tags_with_genre(self, temp_dir):
        """Test write_tags() with genre parameter."""
        mp3_file = temp_dir / "Artist - Title.mp3"
        mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

        with patch('musichouse.tag_writer.load_mp3_safely') as mock_load:
            mock_audiofile = MagicMock()
            mock_tag = MagicMock()
            mock_tag.artist = ""
            mock_tag.title = ""
            mock_tag.genre = None
            mock_audiofile.tag = mock_tag
            mock_load.return_value = mock_audiofile

            result = write_tags(mp3_file, "Artist", "Title", genre="Rock")

            assert result is True
            mock_audiofile.tag.save.assert_called_once()

    def test_write_tags_force_true_overwrites(self, temp_dir):
        """Test write_tags() with force=True overwrites existing tags."""
        mp3_file = temp_dir / "Existing - Tags.mp3"
        mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

        with patch('musichouse.tag_writer.load_mp3_safely') as mock_load:
            mock_audiofile = MagicMock()
            mock_audiofile.tag = MagicMock()
            mock_audiofile.tag.artist = "Old Artist"
            mock_audiofile.tag.title = "Old Title"
            mock_load.return_value = mock_audiofile

            result = write_tags(mp3_file, "New Artist", "New Title", force=True)

            assert result is True
            mock_audiofile.tag.save.assert_called_once()

    def test_write_tags_force_false_with_existing_tags_returns_false(self, temp_dir):
        """Test write_tags() with force=False and existing tags returns False."""
        mp3_file = temp_dir / "Existing - Tags.mp3"
        mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

        with patch('musichouse.tag_writer.load_mp3_safely') as mock_load:
            mock_audiofile = MagicMock()
            mock_audiofile.tag = MagicMock()
            mock_audiofile.tag.artist = "Old Artist"
            mock_audiofile.tag.title = "Old Title"
            mock_load.return_value = mock_audiofile

            result = write_tags(mp3_file, "New Artist", "New Title", force=False)

            assert result is False
            mock_audiofile.tag.save.assert_not_called()

    def test_write_tags_invalid_file_returns_false(self, temp_dir):
        """Test write_tags() with invalid file returns False."""
        invalid_file = temp_dir / "nonexistent.mp3"

        with patch('musichouse.tag_writer.load_mp3_safely') as mock_load:
            mock_load.return_value = None

            result = write_tags(invalid_file, "Artist", "Title")

            assert result is False

    def test_write_tags_file_without_tags_creates_them(self, temp_dir):
        """Test write_tags() creates tags if audiofile.tag is None."""
        mp3_file = temp_dir / "NoTags.mp3"
        mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

        with patch('musichouse.tag_writer.load_mp3_safely') as mock_load:
            mock_audiofile = MagicMock()
            # Simulate initTag() setting the tag attribute internally
            mock_tag = MagicMock()
            mock_tag.artist = ""  # Empty after init
            mock_tag.title = ""
            mock_audiofile.tag = None  # Initially None

            def init_tag_side_effect():
                mock_audiofile.tag = mock_tag
            mock_audiofile.initTag.side_effect = init_tag_side_effect

            mock_load.return_value = mock_audiofile

            result = write_tags(mp3_file, "Artist", "Title")

            assert result is True
            mock_audiofile.initTag.assert_called_once()
            mock_audiofile.tag.save.assert_called_once()
    def test_write_tags_exception_returns_false(self, temp_dir):
        """Test write_tags() returns False on exception."""
        mp3_file = temp_dir / "Error.mp3"
        mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

        with patch('musichouse.tag_writer.load_mp3_safely') as mock_load:
            mock_load.side_effect = Exception("Test error")

            result = write_tags(mp3_file, "Artist", "Title")

            assert result is False

    def test_write_tags_genre_none_not_set(self, temp_dir):
        """Test write_tags() doesn't set genre if None."""
        mp3_file = temp_dir / "Artist - Title.mp3"
        mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

        with patch('musichouse.tag_writer.load_mp3_safely') as mock_load:
            mock_audiofile = MagicMock()
            mock_tag = MagicMock()
            mock_tag.artist = ""
            mock_tag.title = ""
            mock_audiofile.tag = mock_tag
            mock_load.return_value = mock_audiofile

            result = write_tags(mp3_file, "Artist", "Title", genre=None)

            assert result is True
            # When genre=None, the code doesn't call audiofile.tag.genre = ...
            # So we just verify save was called
            mock_audiofile.tag.save.assert_called_once()

# ============================================================================
# TagPreviewDialog Tests
# ============================================================================

class TestTagPreviewDialog:
    """Tests for TagPreviewDialog class."""

    def test_dialog_initialization(self, qapp, temp_dir):
        """Test TagPreviewDialog initialization."""
        file_path = temp_dir / "Test.mp3"
        dialog = TagPreviewDialog(file_path)

        assert dialog.file_path == file_path
        assert dialog.windowTitle().startswith("Preview:")
        assert dialog._old_tags == {}
        assert dialog._new_tags == {}

    def test_set_old_tags(self, qapp, temp_dir):
        """Test set_old_tags() method."""
        file_path = temp_dir / "Test.mp3"
        dialog = TagPreviewDialog(file_path)

        dialog.set_old_tags("Old Artist", "Old Title", "Rock")

        assert dialog._old_tags == {
            "Artist": "Old Artist",
            "Title": "Old Title",
            "Genre": "Rock"
        }

    def test_set_old_tags_without_genre(self, qapp, temp_dir):
        """Test set_old_tags() without genre."""
        file_path = temp_dir / "Test.mp3"
        dialog = TagPreviewDialog(file_path)

        dialog.set_old_tags("Artist", "Title")

        assert dialog._old_tags == {
            "Artist": "Artist",
            "Title": "Title",
            "Genre": ""
        }

    def test_set_new_tags(self, qapp, temp_dir):
        """Test set_new_tags() method."""
        file_path = temp_dir / "Test.mp3"
        dialog = TagPreviewDialog(file_path)

        dialog.set_new_tags("New Artist", "New Title", "Pop")

        assert dialog._new_tags == {
            "Artist": "New Artist",
            "Title": "New Title",
            "Genre": "Pop"
        }

    def test_populate_table(self, qapp, temp_dir):
        """Test populate_table() method."""
        file_path = temp_dir / "Test.mp3"
        dialog = TagPreviewDialog(file_path)

        dialog.set_old_tags("Old Artist", "Old Title", "Rock")
        dialog.set_new_tags("New Artist", "New Title", "Pop")
        dialog.populate_table()

        # Check table has 3 rows (Artist, Title, Genre)
        assert dialog._table.rowCount() == 3
        assert dialog._table.columnCount() == 3

        # Check headers
        assert dialog._table.horizontalHeaderItem(0).text() == "Tag"
        assert dialog._table.horizontalHeaderItem(1).text() == "Old Value"
        assert dialog._table.horizontalHeaderItem(2).text() == "New Value"

    def test_populate_table_highlights_changes(self, qapp, temp_dir):
        """Test populate_table() highlights changed values."""
        file_path = temp_dir / "Test.mp3"
        dialog = TagPreviewDialog(file_path)

        dialog.set_old_tags("Old Artist", "Old Title")
        dialog.set_new_tags("New Artist", "New Title")
        dialog.populate_table()

        # Table should have items with background colors for changes
        # (We can't easily verify QColor in headless mode, but we can check items exist)
        assert dialog._table.rowCount() == 3

        # Find the Artist row and verify items exist
        artist_row = None
        for row in range(dialog._table.rowCount()):
            tag_item = dialog._table.item(row, 0)
            if tag_item and tag_item.text() == "Artist":
                artist_row = row
                break

        assert artist_row is not None
        assert dialog._table.item(artist_row, 1) is not None  # Old value
        assert dialog._table.item(artist_row, 2) is not None  # New value

    def test_get_approval_accepted(self, qapp, temp_dir):
        """Test get_approval() returns True when accepted."""
        file_path = temp_dir / "Test.mp3"
        dialog = TagPreviewDialog(file_path)

        # Mock exec() to return Accepted
        with patch.object(dialog, 'exec', return_value=1):  # QDialog.DialogCode.Accepted = 1
            result = dialog.get_approval()
            assert result is True

    def test_get_approval_rejected(self, qapp, temp_dir):
        """Test get_approval() returns False when rejected."""
        file_path = temp_dir / "Test.mp3"
        dialog = TagPreviewDialog(file_path)

        # Mock exec() to return Rejected
        with patch.object(dialog, 'exec', return_value=0):  # QDialog.DialogCode.Rejected = 0
            result = dialog.get_approval()
            assert result is False

    def test_get_new_tags_returns_copy(self, qapp, temp_dir):
        """Test get_new_tags() returns a copy of tags."""
        file_path = temp_dir / "Test.mp3"
        dialog = TagPreviewDialog(file_path)

        dialog.set_new_tags("Artist", "Title", "Rock")
        tags = dialog.get_new_tags()

        assert tags == {"Artist": "Artist", "Title": "Title", "Genre": "Rock"}

        # Modifying returned dict shouldn't affect internal state
        tags["Artist"] = "Modified"
        assert dialog._new_tags["Artist"] == "Artist"

    def test_populate_table_with_partial_tags(self, qapp, temp_dir):
        """Test populate_table() handles partial tag sets."""
        file_path = temp_dir / "Test.mp3"
        dialog = TagPreviewDialog(file_path)

        # Old has all, new has only artist
        dialog.set_old_tags("Old Artist", "Old Title", "Rock")
        dialog.set_new_tags("New Artist", "", "")
        dialog.populate_table()

        # Should still have 3 rows
        assert dialog._table.rowCount() == 3


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestWriteTagsEdgeCases:
    """Edge case tests for write_tags()."""

    def test_write_tags_readonly_file(self, temp_dir):
        """Test write_tags() with read-only file."""
        mp3_file = temp_dir / "ReadOnly.mp3"
        mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

        # Make file read-only
        mp3_file.chmod(0o444)

        try:
            with patch('musichouse.tag_writer.load_mp3_safely') as mock_load:
                mock_audiofile = MagicMock()
                mock_audiofile.tag = MagicMock()
                mock_audiofile.tag.artist = ""
                mock_audiofile.tag.title = ""
                mock_load.return_value = mock_audiofile

                # Even with mock, the save should fail on real read-only
                # But with our mock, we expect it to "succeed" in the mock world
                result = write_tags(mp3_file, "Artist", "Title")

                # In mock world, this succeeds
                assert result is True
        finally:
            # Restore permissions for cleanup
            mp3_file.chmod(0o644)

    def test_write_tags_empty_strings(self, temp_dir):
        """Test write_tags() with empty string values."""
        mp3_file = temp_dir / "Empty.mp3"
        mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

        with patch('musichouse.tag_writer.load_mp3_safely') as mock_load:
            mock_audiofile = MagicMock()
            mock_audiofile.tag = MagicMock()
            mock_audiofile.tag.artist = ""
            mock_audiofile.tag.title = ""
            mock_load.return_value = mock_audiofile

            result = write_tags(mp3_file, "", "")

            assert result is True

    def test_write_tags_unicode_characters(self, temp_dir):
        """Test write_tags() with unicode characters."""
        mp3_file = temp_dir / "Unicode.mp3"
        mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

        with patch('musichouse.tag_writer.load_mp3_safely') as mock_load:
            mock_audiofile = MagicMock()
            mock_audiofile.tag = MagicMock()
            mock_audiofile.tag.artist = ""
            mock_audiofile.tag.title = ""
            mock_load.return_value = mock_audiofile

            result = write_tags(
                mp3_file,
                "Artista Ñoño",
                "Título con acentos",
                genre="Música Latina"
            )

            assert result is True

    def test_write_tags_long_strings(self, temp_dir):
        """Test write_tags() with very long strings."""
        mp3_file = temp_dir / "Long.mp3"
        mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

        with patch('musichouse.tag_writer.load_mp3_safely') as mock_load:
            mock_audiofile = MagicMock()
            mock_audiofile.tag = MagicMock()
            mock_audiofile.tag.artist = ""
            mock_audiofile.tag.title = ""
            mock_load.return_value = mock_audiofile

            long_artist = "A" * 1000
            long_title = "T" * 1000

            result = write_tags(mp3_file, long_artist, long_title)

            assert result is True
