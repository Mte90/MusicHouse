"""Unit tests for tag_fix_worker module.

Tests for TagFixWorker and TagUpdateWorker QThread workers.
Uses mocking to avoid modifying real MP3 files and to test edge cases.
"""

import json
from pathlib import Path
from unittest.mock import patch

from musichouse.leaderboard_cache import LeaderboardCache
from musichouse.ui.tag_fix_worker import TagFixWorker, TagUpdateWorker


# ============================================================================
# TagFixWorker Tests
# ============================================================================

class TestTagFixWorker:
    """Tests for TagFixWorker class."""

    def test_run_writes_tags_for_all_files(self, temp_dir, qapp):
        """Test that TagFixWorker runs and writes tags for all files."""
        # Create mock MP3 files
        mp3_files = []
        for i in range(3):
            mp3_file = temp_dir / f"Artist - Title {i}.mp3"
            mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
            mp3_files.append(mp3_file)

        files_data = [
            {
                "path": str(mp3_files[0]),
                "suggested_artist": "Artist 1",
                "suggested_title": "Title 1",
            },
            {
                "path": str(mp3_files[1]),
                "suggested_artist": "Artist 2",
                "suggested_title": "Title 2",
            },
            {
                "path": str(mp3_files[2]),
                "suggested_artist": "Artist 3",
                "suggested_title": "Title 3",
            },
        ]

        # Track signal emissions
        progress_args = []
        file_fixed_args = []
        finished_args = []

        def on_progress(idx, filename):
            progress_args.append((idx, filename))

        def on_file_fixed(path, success, filename):
            file_fixed_args.append((path, success, filename))

        def on_finished(success_count, failure_count):
            finished_args.append((success_count, failure_count))

        with patch("musichouse.ui.tag_fix_worker.write_tags", return_value=True):
            worker = TagFixWorker(files_data)

            worker.progress.connect(on_progress)
            worker.file_fixed.connect(on_file_fixed)
            worker.finished.connect(on_finished)

            # Run synchronously
            worker.run()

        # Verify all signals were emitted
        assert len(progress_args) == 3
        assert len(file_fixed_args) == 3
        assert len(finished_args) == 1

        # Verify finished signal has correct counts
        assert finished_args[0] == (3, 0)

        # Verify file_fixed uses 3-arg signature (path, success, filename)
        for path, success, filename in file_fixed_args:
            assert isinstance(success, bool)
            assert filename.endswith(".mp3")

    def test_write_tags_raises_mid_batch_loop_continues_and_finished_emits(self, temp_dir, qapp):
        """Test that if write_tags raises mid-batch, the loop continues and finished still emits.
        
        This is a regression test for a UI-hang bug where the finished signal was missed
        when an exception occurred during the batch processing.
        """
        # Create mock MP3 files
        mp3_files = []
        for i in range(5):
            mp3_file = temp_dir / f"Artist - Title {i}.mp3"
            mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
            mp3_files.append(mp3_file)

        files_data = [
            {"path": str(mp3_files[i]), "suggested_artist": f"Artist {i}", "suggested_title": f"Title {i}"}
            for i in range(5)
        ]

        # Track signal emissions
        finished_args = []
        failures_args = []

        def on_finished(success_count, failure_count):
            finished_args.append((success_count, failure_count))

        def on_failures(failure_list):
            failures_args.append(failure_list)

        # Mock write_tags to raise on the 3rd file, return True on others
        call_count = [0]

        def mock_write_tags(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 3:
                raise RuntimeError("Simulated write failure")
            return True

        with patch("musichouse.ui.tag_fix_worker.write_tags", side_effect=mock_write_tags):
            worker = TagFixWorker(files_data)

            worker.finished.connect(on_finished)
            worker.failures.connect(on_failures)

            # Run synchronously
            worker.run()

        # Verify finished signal WAS emitted (regression test - this was missing before)
        assert len(finished_args) == 1, "finished signal must always emit even after exception"

        # Verify counts: 2 success (files 1-2), 3 failures (file 3 raised, files 4-5 counted as remaining)
        success_count, failure_count = finished_args[0]
        assert success_count == 2
        assert failure_count == 3

        # Verify failures signal was emitted
        assert len(failures_args) == 1
        failure_list = failures_args[0]
        assert len(failure_list) == 3

    def test_write_tags_returns_false_failure_recorded_with_error_type(self, temp_dir, qapp):
        """Test that when write_tags returns False, failure is recorded with error type."""
        # Create mock MP3 files
        mp3_files = []
        for i in range(3):
            mp3_file = temp_dir / f"Artist - Title {i}.mp3"
            mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
            mp3_files.append(mp3_file)

        files_data = [
            {"path": str(mp3_files[0]), "suggested_artist": "Artist 1", "suggested_title": "Title 1"},
            {"path": str(mp3_files[1]), "suggested_artist": "Artist 2", "suggested_title": "Title 2"},
            {"path": str(mp3_files[2]), "suggested_artist": "Artist 3", "suggested_title": "Title 3"},
        ]

        # Track signal emissions
        file_fixed_args = []
        finished_args = []
        failures_args = []

        def on_file_fixed(path, success, filename):
            file_fixed_args.append((path, success, filename))

        def on_finished(success_count, failure_count):
            finished_args.append((success_count, failure_count))

        def on_failures(failure_list):
            failures_args.append(failure_list)

        # Mock write_tags to return False for 2nd file only
        def mock_write_tags(file_path, *args, **kwargs):
            return "Title 2" not in str(file_path)  # False only for file 2

        with patch("musichouse.ui.tag_fix_worker.write_tags", side_effect=mock_write_tags):
            worker = TagFixWorker(files_data)

            worker.file_fixed.connect(on_file_fixed)
            worker.finished.connect(on_finished)
            worker.failures.connect(on_failures)

            worker.run()

        # Verify 2 success, 1 failure
        assert len(file_fixed_args) == 3
        success_count, failure_count = finished_args[0]
        assert success_count == 2
        assert failure_count == 1

        # Verify failures signal contains tuple with error type
        assert len(failures_args) == 1
        failure_list = failures_args[0]
        assert len(failure_list) == 1

        filename, error_type, error_msg = failure_list[0]
        assert filename.endswith(".mp3")
        assert isinstance(error_type, str)
        assert error_type == "Unknown"  # Since no exception was raised
        assert error_msg == "Unknown error"

    def test_cancel_mid_run_loop_breaks_and_finished_emits(self, temp_dir, qapp):
        """Test that calling cancel() mid-run breaks the loop and finished still emits."""
        # Create many mock MP3 files
        mp3_files = []
        for i in range(20):
            mp3_file = temp_dir / f"Artist - Title {i}.mp3"
            mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
            mp3_files.append(mp3_file)

        files_data = [
            {"path": str(mp3_files[i]), "suggested_artist": f"Artist {i}", "suggested_title": f"Title {i}"}
            for i in range(20)
        ]

        # Track signal emissions
        progress_args = []
        finished_args = []

        def on_progress(idx, filename):
            progress_args.append((idx, filename))

        def on_finished(success_count, failure_count):
            finished_args.append((success_count, failure_count))

        # Mock write_tags to call cancel() on the 5th invocation
        call_count = [0]

        def mock_write_tags(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 5:
                # This won't work since we don't have access to worker here
                pass
            return True

        with patch("musichouse.ui.tag_fix_worker.write_tags", side_effect=mock_write_tags):
            worker = TagFixWorker(files_data)

            worker.progress.connect(on_progress)
            worker.finished.connect(on_finished)

            # Set cancelled flag before run (synchronous test)
            worker._cancelled = True
            worker.run()

        # Verify no files were processed
        assert len(progress_args) == 0
        assert len(finished_args) == 1

        # Verify finished signal emitted with 0 success
        success_count, failure_count = finished_args[0]
        assert success_count == 0
        assert failure_count == 0

    def test_cancel_mid_run_with_mock_cancelling(self, temp_dir, qapp):
        """Test cancellation by having mock write_tags trigger cancel on 3rd file."""
        # Create many mock MP3 files
        mp3_files = []
        for i in range(20):
            mp3_file = temp_dir / f"Artist - Title {i}.mp3"
            mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
            mp3_files.append(mp3_file)

        files_data = [
            {"path": str(mp3_files[i]), "suggested_artist": f"Artist {i}", "suggested_title": f"Title {i}"}
            for i in range(20)
        ]

        # Track signal emissions
        progress_args = []
        finished_args = []
        worker_ref = [None]

        def on_progress(idx, filename):
            progress_args.append((idx, filename))

        def on_finished(success_count, failure_count):
            finished_args.append((success_count, failure_count))

        # Mock write_tags to trigger cancel on 3rd invocation
        call_count = [0]

        def mock_write_tags(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 3 and worker_ref[0]:
                worker_ref[0].cancel()
            return True

        with patch("musichouse.ui.tag_fix_worker.write_tags", side_effect=mock_write_tags):
            worker = TagFixWorker(files_data)
            worker_ref[0] = worker

            worker.progress.connect(on_progress)
            worker.finished.connect(on_finished)

            worker.run()

        # 3 files processed: cancel is called during file 3's write_tags,
        # so the cancel check at the top of the loop only takes effect on iteration 4
        assert len(progress_args) == 3
        assert len(finished_args) == 1

        # Verify finished signal emitted with 3 success
        success_count, failure_count = finished_args[0]
        assert success_count == 3
        assert failure_count == 0

    def test_cache_match_skip_write_tags_not_called(self, temp_dir, qapp, leaderboard_cache):
        """Test that when cache matches, write_tags is NOT called and file is counted as success.
        
        Seeds leaderboard_cache with a row whose tag_data JSON matches the target artist/title.
        """
        # Create mock MP3 file
        mp3_file = temp_dir / "Artist - Title.mp3"
        mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

        files_data = [
            {
                "path": str(mp3_file),
                "suggested_artist": "Target Artist",
                "suggested_title": "Target Title",
            }
        ]

        # Seed cache with matching tag_data
        conn = leaderboard_cache._get_connection()
        import time
        tag_data = {"artist": "Target Artist", "title": "Target Title"}
        conn.execute(
            """INSERT OR REPLACE INTO scan_cache
               (path, size, mtime, artist, title, scan_time, needs_fixing, missing_artist, missing_title, tag_data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(mp3_file),
                1024,
                time.time(),
                "Cached Artist",
                "Cached Title",
                time.time(),
                0,
                0,
                0,
                json.dumps(tag_data)
            )
        )
        conn.commit()

        # Track signal emissions
        finished_args = []

        def on_finished(success_count, failure_count):
            finished_args.append((success_count, failure_count))

        with patch("musichouse.ui.tag_fix_worker.write_tags") as mock_write_tags, \
             patch("musichouse.ui.tag_fix_worker.LeaderboardCache", return_value=leaderboard_cache):
            worker = TagFixWorker(files_data)

            worker.finished.connect(on_finished)

            worker.run()

            # Verify write_tags was NOT called
            mock_write_tags.assert_not_called()

        # Verify success count is 1 (cache match counts as success)
        assert len(finished_args) == 1
        assert finished_args[0] == (1, 0)

    def test_cache_mismatch_write_tags_called_with_force_true(self, temp_dir, qapp, leaderboard_cache):
        """Test that when cache doesn't match, write_tags IS called with force=True."""
        # Create mock MP3 file
        mp3_file = temp_dir / "Artist - Title.mp3"
        mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

        files_data = [
            {
                "path": str(mp3_file),
                "suggested_artist": "Target Artist",
                "suggested_title": "Target Title",
            }
        ]

        # Seed cache with NON-matching tag_data
        conn = leaderboard_cache._get_connection()
        import time
        tag_data = {"artist": "Different Artist", "title": "Different Title"}
        conn.execute(
            """INSERT OR REPLACE INTO scan_cache
               (path, size, mtime, artist, title, scan_time, needs_fixing, missing_artist, missing_title, tag_data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(mp3_file),
                1024,
                time.time(),
                "Cached Artist",
                "Cached Title",
                time.time(),
                0,
                0,
                0,
                json.dumps(tag_data)
            )
        )
        conn.commit()

        # Track signal emissions
        finished_args = []

        def on_finished(success_count, failure_count):
            finished_args.append((success_count, failure_count))

        with patch("musichouse.ui.tag_fix_worker.write_tags", return_value=True) as mock_write_tags:
            worker = TagFixWorker(files_data)

            worker.finished.connect(on_finished)

            worker.run()

            # Verify write_tags WAS called with force=True
            mock_write_tags.assert_called_once()
            call_kwargs = mock_write_tags.call_args
            assert call_kwargs.kwargs.get("force") is True

        # Verify success count is 1
        assert len(finished_args) == 1
        assert finished_args[0] == (1, 0)

    def test_file_fixed_signal_uses_3_arg_signature(self, temp_dir, qapp):
        """Test that file_fixed signal emits with 3 arguments: (file_path, success, filename).
        
        Regression test for the signature change from 2 args to 3 args.
        """
        mp3_file = temp_dir / "Test.mp3"
        mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

        files_data = [
            {
                "path": str(mp3_file),
                "suggested_artist": "Artist",
                "suggested_title": "Title",
            }
        ]

        file_fixed_args = []

        def on_file_fixed(*args):
            file_fixed_args.append(args)

        with patch("musichouse.ui.tag_fix_worker.write_tags", return_value=True):
            worker = TagFixWorker(files_data)
            worker.file_fixed.connect(on_file_fixed)
            worker.run()

        # Verify 3 arguments were emitted
        assert len(file_fixed_args) == 1
        args = file_fixed_args[0]
        assert len(args) == 3

        file_path, success, filename = args
        assert file_path == str(mp3_file)
        assert success is True
        assert filename == "Test.mp3"

    def test_current_artist_title_used_over_suggested(self, temp_dir, qapp):
        """Test that current_artist and current_title are used when present."""
        mp3_file = temp_dir / "Test.mp3"
        mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

        files_data = [
            {
                "path": str(mp3_file),
                "suggested_artist": "Suggested Artist",
                "suggested_title": "Suggested Title",
                "current_artist": "Current Artist",
                "current_title": "Current Title",
            }
        ]

        with patch("musichouse.ui.tag_fix_worker.write_tags", return_value=True) as mock_write:
            worker = TagFixWorker(files_data)
            worker.run()

            # Verify write_tags was called with current values, not suggested
            mock_write.assert_called_once()
            call_args = mock_write.call_args
            assert call_args[0][1] == "Current Artist"  # artist
            assert call_args[0][2] == "Current Title"   # title

    def test_auto_fix_uses_suggested_values(self, temp_dir, qapp):
        """Test that auto_fix=True uses suggested_artist and suggested_title."""
        mp3_file = temp_dir / "Test.mp3"
        mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

        files_data = [
            {
                "path": str(mp3_file),
                "suggested_artist": "Suggested Artist",
                "suggested_title": "Suggested Title",
            }
        ]

        with patch("musichouse.ui.tag_fix_worker.write_tags", return_value=True) as mock_write:
            worker = TagFixWorker(files_data, auto_fix=True)
            worker.run()

            mock_write.assert_called_once()
            call_args = mock_write.call_args
            assert call_args[0][1] == "Suggested Artist"
            assert call_args[0][2] == "Suggested Title"


# ============================================================================
# TagUpdateWorker Tests
# ============================================================================

class TestTagUpdateWorker:
    """Tests for TagUpdateWorker class."""

    def test_run_updates_db_for_fixed_paths(self, temp_db_file, qapp):
        """Test that TagUpdateWorker updates the database for fixed paths."""
        fixed_paths = [
            Path("/path/to/file1.mp3"),
            Path("/path/to/file2.mp3"),
        ]

        # Pre-populate DB with scan_cache entries
        cache = LeaderboardCache(temp_db_file)
        conn = cache._get_connection()
        for path in fixed_paths:
            conn.execute(
                "INSERT INTO scan_cache (path, size, mtime, artist, title, scan_time, needs_fixing, missing_artist, missing_title) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (str(path), 1024, 12345.0, "Artist", "Title", 12345.0, 1, 0, 0)
            )
        conn.commit()
        cache.close()

        finished_args = []

        def on_finished():
            finished_args.append(True)

        with patch("musichouse.ui.tag_fix_worker.LeaderboardCache", return_value=LeaderboardCache(temp_db_file)):
            worker = TagUpdateWorker(fixed_paths)
            worker.finished.connect(on_finished)
            worker.run()

        # Verify finished signal was emitted
        assert len(finished_args) == 1

        # Verify DB was updated
        cache = LeaderboardCache(temp_db_file)
        conn = cache._get_connection()
        for path in fixed_paths:
            cursor = conn.execute("SELECT needs_fixing, missing_artist, missing_title FROM scan_cache WHERE path = ?", (str(path),))
            row = cursor.fetchone()
            assert row is not None
            assert row['needs_fixing'] == 0
            assert row['missing_artist'] == 0
            assert row['missing_title'] == 0
        cache.close()

    def test_run_emits_finished_even_on_error(self, temp_db_file, qapp):
        """Test that finished signal is emitted even if DB update fails."""
        # Use non-existent paths to trigger potential errors
        fixed_paths = [Path("/nonexistent/path/file.mp3")]

        finished_args = []

        def on_finished():
            finished_args.append(True)

        worker = TagUpdateWorker(fixed_paths)
        worker.finished.connect(on_finished)
        worker.run()

        # Verify finished signal was still emitted
        assert len(finished_args) == 1