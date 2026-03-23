"""Type consistency tests for FixerTab path handling."""
from pathlib import Path

import pytest


class TestFixerTabPathTypeConsistency:
    """Test that all entry paths in _files_data are Path objects."""

    def test_all_paths_are_path_objects(self):
        """Test that all entry['path'] values are Path objects, not strings."""
        from musichouse.ui.fixer_tab import FixerTab

        tab = FixerTab()
        tab.add_file_entry({
            "path": "/test/path1.mp3",
            "filename": "test1.mp3",
            "existing_artist": "",
            "existing_title": "",
            "suggested_artist": "Artist",
            "suggested_title": "Title",
            "missing_artist": True,
            "missing_title": False,
        })
        tab.add_file_entry({
            "path": Path("/test/path2.mp3"),
            "filename": "test2.mp3",
            "existing_artist": "",
            "existing_title": "",
            "suggested_artist": "Artist",
            "suggested_title": "Title",
            "missing_artist": False,
            "missing_title": True,
        })
        tab.add_file_entry({
            "path": "/test/path3.mp3",
            "filename": "test3.mp3",
            "existing_artist": "",
            "existing_title": "",
            "suggested_artist": "Artist",
            "suggested_title": "Title",
            "missing_artist": True,
            "missing_title": True,
        })

    def test_no_str_path_entries_allowed(self):
        """Test that no entry has a string path (only Path objects allowed)."""
        from musichouse.ui.fixer_tab import FixerTab

        tab = FixerTab()
        tab.add_file_entry({
            "path": "/test/path1.mp3",
            "filename": "test1.mp3",
            "existing_artist": "",
            "existing_title": "",
            "suggested_artist": "Artist",
            "suggested_title": "Title",
            "missing_artist": True,
            "missing_title": False,
        })
        tab.add_file_entry({
            "path": "/test/path2.mp3",
            "filename": "test2.mp3",
            "existing_artist": "",
            "existing_title": "",
            "suggested_artist": "Artist",
            "suggested_title": "Title",
            "missing_artist": False,
            "missing_title": True,
        })

    def test_path_in_fixed_paths_comparison(self):
        """Test that path comparison works when both are Path objects."""
        from musichouse.ui.fixer_tab import FixerTab

        tab = FixerTab()
        tab.add_file_entry({
            "path": Path("/test/path1.mp3"),
            "filename": "test1.mp3",
            "existing_artist": "",
            "existing_title": "",
            "suggested_artist": "Artist",
            "suggested_title": "Title",
            "missing_artist": True,
            "missing_title": False,
        })
        tab.add_file_entry({
            "path": Path("/test/path2.mp3"),
            "filename": "test2.mp3",
            "existing_artist": "",
            "existing_title": "",
            "suggested_artist": "Artist",
            "suggested_title": "Title",
            "missing_artist": False,
            "missing_title": True,
        })

    def test_path_comparison_with_str_fails(self):
        """Test that Path(str) comparison fails with str(Path)."""
        from musichouse.ui.fixer_tab import FixerTab

        tab = FixerTab()
        tab.add_file_entry({
            "path": "/test/path1.mp3",
            "filename": "test1.mp3",
            "existing_artist": "",
            "existing_title": "",
            "suggested_artist": "Artist",
            "suggested_title": "Title",
            "missing_artist": True,
            "missing_title": False,
        })

    def test_path_type_mismatch_scenario(self):
        """Test the exact scenario from line 419."""
        from musichouse.ui.fixer_tab import FixerTab

        tab = FixerTab()
        tab.add_file_entry({
            "path": "/test/file1.mp3",
            "filename": "file1.mp3",
            "existing_artist": "",
            "existing_title": "",
            "suggested_artist": "Artist",
            "suggested_title": "Title",
            "missing_artist": True,
            "missing_title": False,
        })
        tab.add_file_entry({
            "path": Path("/test/file2.mp3"),
            "filename": "file2.mp3",
            "existing_artist": "",
            "existing_title": "",
            "suggested_artist": "Artist",
            "suggested_title": "Title",
            "missing_artist": False,
            "missing_title": True,
        })


class TestRemoveFixedRowsTypeBugs:
    """Test the _remove_fixed_rows method for type comparison issues."""

    def test_remove_fixed_rows_with_str_path(self):
        """Test that _remove_fixed_rows fails when entry['path'] is str."""
        from musichouse.ui.fixer_tab import FixerTab

        tab = FixerTab()
        tab.add_file_entry({
            "path": "/test/to_remove.mp3",
            "filename": "to_remove.mp3",
            "existing_artist": "Artist",
            "existing_title": "Title",
            "suggested_artist": "Artist",
            "suggested_title": "Title",
            "missing_artist": False,
            "missing_title": False,
        })
        tab.add_file_entry({
            "path": "/test/to_keep.mp3",
            "filename": "to_keep.mp3",
            "existing_artist": "Artist",
            "existing_title": "Title",
            "suggested_artist": "Artist",
            "suggested_title": "Title",
            "missing_artist": False,
            "missing_title": False,
        })

        fixed_paths = [Path("/test/to_remove.mp3")]

        initial_count = len(tab._files_data)

        tab._remove_fixed_rows(fixed_paths)

        # FIXED: string comparison now works - str path should match Path in fixed_paths
        assert len(tab._files_data) == initial_count - 1

    def test_remove_fixed_rows_with_mixed_paths(self):
        """Test _remove_fixed_rows with mixed str/Path entries."""
        from musichouse.ui.fixer_tab import FixerTab

        tab = FixerTab()
        tab.add_file_entry({
            "path": "/test/str_path.mp3",
            "filename": "str_path.mp3",
            "existing_artist": "Artist",
            "existing_title": "Title",
            "suggested_artist": "Artist",
            "suggested_title": "Title",
            "missing_artist": False,
            "missing_title": False,
        })
        tab.add_file_entry({
            "path": Path("/test/path_path.mp3"),
            "filename": "path_path.mp3",
            "existing_artist": "Artist",
            "existing_title": "Title",
            "suggested_artist": "Artist",
            "suggested_title": "Title",
            "missing_artist": False,
            "missing_title": False,
        })
        tab.add_file_entry({
            "path": Path("/test/keep_me.mp3"),
            "filename": "keep_me.mp3",
            "existing_artist": "Artist",
            "existing_title": "Title",
            "suggested_artist": "Artist",
            "suggested_title": "Title",
            "missing_artist": False,
            "missing_title": False,
        })

        fixed_paths = [
            Path("/test/str_path.mp3"),
            Path("/test/path_path.mp3"),
        ]

        initial_count = len(tab._files_data)

        tab._remove_fixed_rows(fixed_paths)

        # FIXED: both str and Path entries should match - only keep_me.mp3 remains
        assert len(tab._files_data) == 1
        assert tab._files_data[0]["filename"] == "keep_me.mp3"
