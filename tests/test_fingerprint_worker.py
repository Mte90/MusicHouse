"""Unit tests for fingerprint_worker module.

Tests for FingerprintWorker QThread worker.
Uses mocking to avoid needing real fpcalc binary and MP3 files.
"""

from unittest.mock import patch

from musichouse.leaderboard_cache import LeaderboardCache
from musichouse.ui.fingerprint_worker import FingerprintWorker

# ============================================================================
# FingerprintWorker Tests
# ============================================================================

class TestFingerprintWorker:
    """Tests for FingerprintWorker class."""

    def test_run_skips_fingerprinted_files(self, temp_dir, qapp):
        """Test that FingerprintWorker skips files that already have fingerprints."""
        # Create mock MP3 file
        mp3_file = temp_dir / "Artist - Title.mp3"
        mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
        
        # Create cache and add file with existing fingerprint
        cache = LeaderboardCache(temp_dir / "test.db")
        cache.set_fingerprint(str(mp3_file), b"existing_fingerprint", 120.5)
        
        file_done_args = []
        fingerprint_finished_args = []
        
        def on_file_done(count):
            file_done_args.append(count)
        
        def on_finished(total):
            fingerprint_finished_args.append(total)
        
        with patch("musichouse.ui.fingerprint_worker.is_fpcalc_available", return_value=True):
            worker = FingerprintWorker(cache)
            
            worker.file_done.connect(on_file_done)
            worker.fingerprint_finished.connect(on_finished)
            
            worker.run()
        
        # Verify no files were fingerprinted (already had fingerprint)
        assert len(file_done_args) == 0
        assert len(fingerprint_finished_args) == 1
        assert fingerprint_finished_args[0] == 0
        
        cache.close()

    def test_run_batch_progress_logging(self, temp_dir, qapp, caplog):
        """Test that batch progress logging emits INFO every 50 files."""
        import logging
        
        # Create 60 mock MP3 files (to test 50-file boundary and final partial)
        mp3_files = []
        for i in range(60):
            mp3_file = temp_dir / f"Artist - Title {i}.mp3"
            mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
            mp3_files.append(mp3_file)
        
        # Create cache and add files without fingerprints
        cache = LeaderboardCache(temp_dir / "test.db")
        from musichouse.scanner import MP3Scanner
        scanner = MP3Scanner(temp_dir)
        paths = scanner.scan()
        cache.update_scan_cache([
            {
                "path": str(p),
                "size": p.stat().st_size,
                "mtime": p.stat().st_mtime,
                "artist": "Artist",
                "title": f"Title {i}",
                "needs_fixing": 0,
                "missing_artist": 0,
                "missing_title": 0,
                "suggested_artist": None,
                "suggested_title": None,
                "tag_data": None,
            }
            for i, p in enumerate(paths)
        ])
        
        mock_fingerprint = (b"mock_fingerprint_data", 180.0)
        
        with patch("musichouse.ui.fingerprint_worker.is_fpcalc_available", return_value=True), \
             patch("musichouse.ui.fingerprint_worker.compute_fingerprint", return_value=mock_fingerprint):
            worker = FingerprintWorker(cache)
            worker.run()
        
        # Check INFO level logs
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        info_messages = [r.message for r in info_records]
        
        # Should have batch progress at 50 and final summary
        assert any("Fingerprinted 50/60" in msg for msg in info_messages), \
            f"Expected batch progress at 50, got: {info_messages}"
        assert any("FingerprintWorker completed: 60 files fingerprinted" in msg for msg in info_messages), \
            f"Expected final summary, got: {info_messages}"
        
        # Check DEBUG level logs - per-file fingerprinted messages should be DEBUG
        debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
        debug_messages = [r.message for r in debug_records]
        
        # Should have per-file fingerprinted messages at DEBUG
        assert any("Fingerprinted:" in msg for msg in debug_messages), \
            f"Expected per-file DEBUG logs, got debug: {debug_messages}"
        
        # Should have no per-file INFO logs (only batch and summary)
        per_file_info = [msg for msg in info_messages if msg.startswith("Fingerprinted:")]
        assert len(per_file_info) == 0, f"Per-file logs should be DEBUG, not INFO: {per_file_info}"
        
        cache.close()

    def test_run_batch_logging_with_non_multiple_of_50(self, temp_dir, qapp, caplog):
        """Test batch logging with file count that is not a multiple of 50 (e.g., 73)."""
        import logging
        
        # Create 73 mock MP3 files
        mp3_files = []
        for i in range(73):
            mp3_file = temp_dir / f"Artist - Title {i}.mp3"
            mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
            mp3_files.append(mp3_file)
        
        # Create cache and add files without fingerprints
        cache = LeaderboardCache(temp_dir / "test.db")
        from musichouse.scanner import MP3Scanner
        scanner = MP3Scanner(temp_dir)
        paths = scanner.scan()
        cache.update_scan_cache([
            {
                "path": str(p),
                "size": p.stat().st_size,
                "mtime": p.stat().st_mtime,
                "artist": "Artist",
                "title": f"Title {i}",
                "needs_fixing": 0,
                "missing_artist": 0,
                "missing_title": 0,
                "suggested_artist": None,
                "suggested_title": None,
                "tag_data": None,
            }
            for i, p in enumerate(paths)
        ])
        
        mock_fingerprint = (b"mock_fingerprint_data", 180.0)
        
        with patch("musichouse.ui.fingerprint_worker.is_fpcalc_available", return_value=True), \
             patch("musichouse.ui.fingerprint_worker.compute_fingerprint", return_value=mock_fingerprint):
            worker = FingerprintWorker(cache)
            worker.run()
        
        # Check INFO level logs
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        info_messages = [r.message for r in info_records]
        
        # Should have batch progress at 50 and final summary (no progress at 100 since only 73 files)
        assert any("Fingerprinted 50/73" in msg for msg in info_messages), \
            f"Expected batch progress at 50, got: {info_messages}"
        assert any("FingerprintWorker completed: 73 files fingerprinted" in msg for msg in info_messages), \
            f"Expected final summary, got: {info_messages}"
        
        # No progress at 100
        assert not any("Fingerprinted 100/" in msg for msg in info_messages), \
            f"Should not have progress at 100, got: {info_messages}"
        
        cache.close()

    def test_run_fingerprintes_missing_files(self, temp_dir, qapp):
        """Test that FingerprintWorker fingerprints files missing fingerprints."""
        # Create mock MP3 files
        mp3_files = []
        for i in range(3):
            mp3_file = temp_dir / f"Artist - Title {i}.mp3"
            mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
            mp3_files.append(mp3_file)
        
        # Create cache and add files without fingerprints
        cache = LeaderboardCache(temp_dir / "test.db")
        # Files are in cache but without fingerprints (fingerprint/duration are NULL)
        from musichouse.scanner import MP3Scanner
        scanner = MP3Scanner(temp_dir)
        paths = scanner.scan()
        cache.update_scan_cache([
            {
                "path": str(p),
                "size": p.stat().st_size,
                "mtime": p.stat().st_mtime,
                "artist": "Artist",
                "title": f"Title {i}",
                "needs_fixing": 0,
                "missing_artist": 0,
                "missing_title": 0,
                "suggested_artist": None,
                "suggested_title": None,
                "tag_data": None,
            }
            for i, p in enumerate(paths)
        ])
        
        file_done_args = []
        fingerprint_finished_args = []
        progress_args = []
        
        def on_file_done(count):
            file_done_args.append(count)
        
        def on_finished(total):
            fingerprint_finished_args.append(total)
        
        def on_progress(msg):
            progress_args.append(msg)
        
        mock_fingerprint = (b"mock_fingerprint_data", 180.0)
        
        with patch("musichouse.ui.fingerprint_worker.is_fpcalc_available", return_value=True), \
             patch("musichouse.ui.fingerprint_worker.compute_fingerprint", return_value=mock_fingerprint):
            worker = FingerprintWorker(cache)
            
            worker.file_done.connect(on_file_done)
            worker.fingerprint_finished.connect(on_finished)
            worker.progress.connect(on_progress)
            
            worker.run()
        
        # Verify all files were fingerprinted
        assert len(file_done_args) == 3
        assert file_done_args == [1, 2, 3]
        assert len(fingerprint_finished_args) == 1
        assert fingerprint_finished_args[0] == 3
        assert len(progress_args) == 3
        
        # Verify fingerprints were written
        for mp3_file in mp3_files:
            fp, duration = cache.get_fingerprint(str(mp3_file))
            assert fp == b"mock_fingerprint_data"
            assert duration == 180.0
        
        cache.close()

    def test_run_handles_fingerprint_error(self, temp_dir, qapp):
        """Test that FingerprintWorker handles FingerprintError gracefully."""
        # Create mock MP3 file
        mp3_file = temp_dir / "corrupt.mp3"
        mp3_file.write_bytes(b"not a valid mp3")
        
        # Create cache and add file
        cache = LeaderboardCache(temp_dir / "test.db")
        from musichouse.scanner import MP3Scanner
        scanner = MP3Scanner(temp_dir)
        paths = scanner.scan()
        cache.update_scan_cache([
            {
                "path": str(p),
                "size": p.stat().st_size,
                "mtime": p.stat().st_mtime,
                "artist": None,
                "title": None,
                "needs_fixing": 0,
                "missing_artist": 1,
                "missing_title": 1,
                "suggested_artist": None,
                "suggested_title": None,
                "tag_data": None,
            }
            for p in paths
        ])
        
        file_done_args = []
        fingerprint_finished_args = []
        progress_args = []
        
        def on_file_done(count):
            file_done_args.append(count)
        
        def on_finished(total):
            fingerprint_finished_args.append(total)
        
        def on_progress(msg):
            progress_args.append(msg)
        
        from musichouse.fingerprint import FingerprintError
        
        with patch("musichouse.ui.fingerprint_worker.is_fpcalc_available", return_value=True), \
             patch("musichouse.ui.fingerprint_worker.compute_fingerprint", side_effect=FingerprintError("fpcalc failed")):
            worker = FingerprintWorker(cache)
            
            worker.file_done.connect(on_file_done)
            worker.fingerprint_finished.connect(on_finished)
            worker.progress.connect(on_progress)
            
            worker.run()
        
        # Verify no files were fingerprinted (all failed)
        assert len(file_done_args) == 0
        assert len(fingerprint_finished_args) == 1
        assert fingerprint_finished_args[0] == 0
        # Verify error message was emitted in progress
        assert any("Error fingerprinting" in msg for msg in progress_args)
        
        cache.close()

    def test_run_stops_on_stop_flag(self, temp_dir, qapp):
        """Test that FingerprintWorker respects the stop flag."""
        # Create mock MP3 files
        mp3_files = []
        for i in range(5):
            mp3_file = temp_dir / f"Artist - Title {i}.mp3"
            mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
            mp3_files.append(mp3_file)
        
        # Create cache and add files
        cache = LeaderboardCache(temp_dir / "test.db")
        from musichouse.scanner import MP3Scanner
        scanner = MP3Scanner(temp_dir)
        paths = scanner.scan()
        cache.update_scan_cache([
            {
                "path": str(p),
                "size": p.stat().st_size,
                "mtime": p.stat().st_mtime,
                "artist": "Artist",
                "title": f"Title {i}",
                "needs_fixing": 0,
                "missing_artist": 0,
                "missing_title": 0,
                "suggested_artist": None,
                "suggested_title": None,
                "tag_data": None,
            }
            for i, p in enumerate(paths)
        ])
        
        file_done_args = []
        fingerprint_finished_args = []
        
        def on_file_done(count):
            file_done_args.append(count)
            # Stop after 2 files
            if count == 2:
                worker.stop()
        
        def on_finished(total):
            fingerprint_finished_args.append(total)
        
        mock_fingerprint = (b"mock_fingerprint_data", 180.0)
        
        with patch("musichouse.ui.fingerprint_worker.is_fpcalc_available", return_value=True), \
             patch("musichouse.ui.fingerprint_worker.compute_fingerprint", return_value=mock_fingerprint):
            worker = FingerprintWorker(cache)
            
            worker.file_done.connect(on_file_done)
            worker.fingerprint_finished.connect(on_finished)
            
            worker.run()
        
        # Verify worker stopped after 2 files
        assert len(file_done_args) == 2
        assert file_done_args == [1, 2]
        assert len(fingerprint_finished_args) == 1
        assert fingerprint_finished_args[0] == 2
        
        cache.close()

    def test_run_emits_finished_even_when_fpcalc_unavailable(self, temp_dir, qapp):
        """Test that FingerprintWorker emits finished signal even when fpcalc is unavailable."""
        cache = LeaderboardCache(temp_dir / "test.db")
        
        fingerprint_finished_args = []
        error_args = []
        
        def on_finished(total):
            fingerprint_finished_args.append(total)
        
        def on_error(msg):
            error_args.append(msg)
        
        with patch("musichouse.ui.fingerprint_worker.is_fpcalc_available", return_value=False):
            worker = FingerprintWorker(cache)
            
            worker.fingerprint_finished.connect(on_finished)
            worker.error.connect(on_error)
            
            worker.run()
        
        # Verify finished signal was emitted with 0 count
        assert len(fingerprint_finished_args) == 1
        assert fingerprint_finished_args[0] == 0
        # Verify error message was emitted
        assert len(error_args) == 1
        assert "fpcalc not available" in error_args[0]
        
        cache.close()

    def test_get_all_scanned_paths(self, temp_dir):
        """Test that get_all_scanned_paths returns all file paths."""
        cache = LeaderboardCache(temp_dir / "test.db")
        
        # Add some files to cache
        cache.update_scan_cache([
            {
                "path": "/path/to/file1.mp3",
                "size": 1000,
                "mtime": 1234567890.0,
                "artist": "Artist 1",
                "title": "Title 1",
                "needs_fixing": 0,
                "missing_artist": 0,
                "missing_title": 0,
                "suggested_artist": None,
                "suggested_title": None,
                "tag_data": None,
            },
            {
                "path": "/path/to/file2.mp3",
                "size": 2000,
                "mtime": 1234567891.0,
                "artist": "Artist 2",
                "title": "Title 2",
                "needs_fixing": 0,
                "missing_artist": 0,
                "missing_title": 0,
                "suggested_artist": None,
                "suggested_title": None,
                "tag_data": None,
            },
        ])
        
        paths = cache.get_all_scanned_paths()
        
        assert len(paths) == 2
        assert "/path/to/file1.mp3" in paths
        assert "/path/to/file2.mp3" in paths
        
        cache.close()

    def test_get_all_scanned_paths_empty(self, temp_dir):
        """Test that get_all_scanned_paths returns empty list when cache is empty."""
        cache = LeaderboardCache(temp_dir / "test.db")
        
        paths = cache.get_all_scanned_paths()
        
        assert len(paths) == 0
        
        cache.close()

    def test_run_skips_already_fingerprinted_cache_hit_path(self, temp_dir, qapp):
        """Test that already-fingerprinted files are skipped (lines 66-67)."""
        # Create mock MP3 files
        mp3_files = []
        for i in range(3):
            mp3_file = temp_dir / f"Artist - Title {i}.mp3"
            mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
            mp3_files.append(mp3_file)
        
        # Create cache and add files WITH existing fingerprints to scan_cache
        cache = LeaderboardCache(temp_dir / "test.db")
        # Must add files to scan_cache first so get_all_scanned_paths returns them
        cache.update_scan_cache([
            {
                "path": str(mp3_file),
                "size": mp3_file.stat().st_size,
                "mtime": mp3_file.stat().st_mtime,
                "artist": "Artist",
                "title": f"Title {i}",
                "needs_fixing": 0,
                "missing_artist": 0,
                "missing_title": 0,
                "suggested_artist": None,
                "suggested_title": None,
                "tag_data": None,
            }
            for i, mp3_file in enumerate(mp3_files)
        ])
        # Now add fingerprints to all files
        for mp3_file in mp3_files:
            cache.set_fingerprint(str(mp3_file), b"existing_fp", 120.0)
        
        file_done_args = []
        fingerprint_finished_args = []
        progress_args = []
        
        def on_file_done(count):
            file_done_args.append(count)
        
        def on_finished(total):
            fingerprint_finished_args.append(total)
        
        def on_progress(msg):
            progress_args.append(msg)
        
        with patch("musichouse.ui.fingerprint_worker.is_fpcalc_available", return_value=True), \
             patch("musichouse.ui.fingerprint_worker.compute_fingerprint") as mock_compute:
            worker = FingerprintWorker(cache)
            
            worker.file_done.connect(on_file_done)
            worker.fingerprint_finished.connect(on_finished)
            worker.progress.connect(on_progress)
            
            worker.run()
        
        # Verify compute_fingerprint was NEVER called (all files skipped)
        mock_compute.assert_not_called()
        
        # Verify no files were fingerprinted
        assert len(file_done_args) == 0
        assert len(fingerprint_finished_args) == 1
        assert fingerprint_finished_args[0] == 0
        
        # Verify progress was emitted for each file (but then skipped at line 67)
        assert len(progress_args) == 3
        
        cache.close()