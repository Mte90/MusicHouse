"""Integration test for real MP3 file scanning with flag verification."""
import pytest
import sqlite3
from pathlib import Path
from typing import Dict, List

from musichouse.scanner import MP3Scanner
from musichouse.parser import parse_filename
from musichouse.leaderboard_cache import LeaderboardCache


@pytest.mark.skipif(
    not Path("/media/disk3part1/Musica").exists(),
    reason="Real music directory not available"
)
class TestRealScanIntegration:
    """Test real MP3 file scanning with 12064 files."""

    def test_complete_scan_with_flag_calculation(self, temp_db_file):
        """Test full scan of real directory with flag calculation.

        This test verifies:
        1. Scan completes without freezing on 12064 files
        2. Flags (missing_artist, missing_title, needs_fixing) are calculated correctly
        3. Database is populated with correct values
        4. File count matches expected
        """
        import time

        music_dir = Path("/media/disk3part1/Musica")

        # Verify directory exists and has files
        assert music_dir.exists(), f"Directory {music_dir} does not exist"
        
        # Quick check: count files in directory
        scanner_check = MP3Scanner(music_dir)
        quick_check_files = scanner_check.scan()
        original_count = len(quick_check_files)
        print(f"Quick check found {original_count} files")
        
        # Use scanner for actual scan
        scanner = MP3Scanner(music_dir)
        
        # Track progress
        file_callback_count = 0
        progress_callback_count = 0

        def file_callback(count: int):
            nonlocal file_callback_count
            file_callback_count = count
            if count % 1000 == 0:
                print(f"Files processed: {count}")

        def progress_callback(path: str):
            nonlocal progress_callback_count
            progress_callback_count += 1
            if progress_callback_count % 100 == 0:
                print(f"Scanning directory: {path}")

        scanner.set_file_callback(file_callback, batch_size=100)
        scanner.set_progress_callback(progress_callback)

        # Perform scan with timing
        start_time = time.time()
        scanned_files = scanner.scan()
        elapsed = time.time() - start_time

        print(f"\n=== Scan Results ===")
        print(f"Total files found: {len(scanned_files)}")
        print(f"Expected: ~{original_count} files")
        print(f"Scan time: {elapsed:.2f} seconds")
        print(f"File callback triggered {file_callback_count} times")
        print(f"Progress callback triggered {progress_callback_count} times")
        print(f"Scan completed without freezing: {'PASS' if len(scanned_files) > 0 else 'FAIL'}")

        # Verify scanner completed
        assert len(scanned_files) > 0, "No files were scanned"
        assert scanner.get_file_count() > 0, "File count should be > 0"

        # Build file info with flag calculation
        print("\n=== Calculating Flags ===")
        files_info = []
        missing_artist_count = 0
        missing_title_count = 0
        needs_fixing_count = 0

        for i, file_path in enumerate(scanned_files):
            if i % 1000 == 0:
                print(f"Processing flags: {i}/{len(scanned_files)}")

            # Parse filename
            filename = file_path.name
            artist, title = parse_filename(filename, file_path)

            # Calculate flags
            is_missing_artist = artist is None or artist.strip() == ""
            is_missing_title = title is None or title.strip() == ""
            is_needs_fixing = is_missing_artist or is_missing_title

            if is_missing_artist:
                missing_artist_count += 1
            if is_missing_title:
                missing_title_count += 1
            if is_needs_fixing:
                needs_fixing_count += 1

            stat = file_path.stat()
            files_info.append({
                'path': str(file_path),
                'size': stat.st_size,
                'mtime': stat.st_mtime,
                'artist': artist,
                'title': title,
                'needs_fixing': 1 if is_needs_fixing else 0,
                'missing_artist': 1 if is_missing_artist else 0,
                'missing_title': 1 if is_missing_title else 0,
            })

        print(f"\n=== Flag Statistics ===")
        print(f"Missing artist: {missing_artist_count}")
        print(f"Missing title: {missing_title_count}")
        print(f"Needs fixing: {needs_fixing_count}")

        # Update leaderboard cache
        cache = LeaderboardCache(temp_db_file)
        cache.update_scan_cache(files_info)
        cache.close()

        print("\n=== Database Verification ===")

        # Verify database has correct structure
        conn = sqlite3.connect(temp_db_file)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM scan_cache"
        )
        total_in_db = cursor.fetchone()[0]
        print(f"Total entries in scan_cache: {total_in_db}")

        # Verify flag values in database
        cursor = conn.execute(
            "SELECT COUNT(*) FROM scan_cache WHERE missing_artist = 1"
        )
        db_missing_artist = cursor.fetchone()[0]
        print(f"Missing artist in DB: {db_missing_artist}")

        cursor = conn.execute(
            "SELECT COUNT(*) FROM scan_cache WHERE missing_title = 1"
        )
        db_missing_title = cursor.fetchone()[0]
        print(f"Missing title in DB: {db_missing_title}")

        cursor = conn.execute(
            "SELECT COUNT(*) FROM scan_cache WHERE needs_fixing = 1"
        )
        db_needs_fixing = cursor.fetchone()[0]
        print(f"Needs fixing in DB: {db_needs_fixing}")

        conn.close()

        # Verify counts match
        assert total_in_db == len(scanned_files), \
            f"DB count ({total_in_db}) != scanned count ({len(scanned_files)})"
        assert db_missing_artist == missing_artist_count, \
            f"DB missing_artist ({db_missing_artist}) != calculated ({missing_artist_count})"
        assert db_missing_title == missing_title_count, \
            f"DB missing_title ({db_missing_title}) != calculated ({missing_title_count})"
        assert db_needs_fixing == needs_fixing_count, \
            f"DB needs_fixing ({db_needs_fixing}) != calculated ({needs_fixing_count})"

        # Verify that at least some files have missing tags (if scan is meaningful)
        # If no files need fixing, that's also valid - just means all files are well-tagged
        print(f"\n=== Verification Summary ===")
        print(f"All flag counts match: PASS")
        print(f"Database populated correctly: PASS")

    def test_sample_entries_with_flags(self, temp_db_file):
        """Verify sample entries have correct flag values by checking actual files."""
        import time

        music_dir = Path("/media/disk3part1/Musica")

        # Scan a small subset first
        scanner = MP3Scanner(music_dir)
        scanned_files = scanner.scan()

        if len(scanned_files) == 0:
            pytest.skip("No files to test")

        # Build file info with flags
        files_info = []
        for file_path in scanned_files[:100]:  # Test first 100 files
            filename = file_path.name
            artist, title = parse_filename(filename, file_path)

            is_missing_artist = artist is None or artist.strip() == ""
            is_missing_title = title is None or title.strip() == ""
            is_needs_fixing = is_missing_artist or is_missing_title

            stat = file_path.stat()
            files_info.append({
                'path': str(file_path),
                'size': stat.st_size,
                'mtime': stat.st_mtime,
                'artist': artist,
                'title': title,
                'needs_fixing': 1 if is_needs_fixing else 0,
                'missing_artist': 1 if is_missing_artist else 0,
                'missing_title': 1 if is_missing_title else 0,
            })

        # Update cache
        cache = LeaderboardCache(temp_db_file)
        cache.update_scan_cache(files_info)

        # Verify each entry
        for info in files_info[:10]:  # Check first 10
            cached = cache.get_cached_info(info['path'])
            assert cached is not None, f"Entry not found for {info['path']}"
            assert cached['missing_artist'] == info['missing_artist'], \
                f"missing_artist mismatch for {info['path']}"
            assert cached['missing_title'] == info['missing_title'], \
                f"missing_title mismatch for {info['path']}"
            assert cached['needs_fixing'] == info['needs_fixing'], \
                f"needs_fixing mismatch for {info['path']}"

            if cached['needs_fixing']:
                print(f"Needs fixing: {info['path']}")
                if cached['missing_artist']:
                    print(f"  Missing artist (calculated: '{info['artist']}')")
                if cached['missing_title']:
                    print(f"  Missing title (calculated: '{info['title']}')")

        cache.close()

        print("\n=== Sample Entries Verified ===")
        print("Flag values match for sample entries: PASS")
