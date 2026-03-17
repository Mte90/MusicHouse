"""Integration tests for MusicHouse scan → parse → leaderboard workflow."""

import pytest
from pathlib import Path
from typing import Dict, List, Tuple


@pytest.mark.integration
class TestScanParseLeaderboardFlow:
    """Integration tests for the complete scanning and leaderboard update flow."""

    def test_full_scan_parse_leaderboard_flow_with_mock_files(
        self, temp_dir, mock_mp3_files, leaderboard_cache
    ):
        """Test complete flow: scan directory → parse filenames → update leaderboard.
        
        This test verifies:
        1. Scanner finds all MP3 files in directory
        2. Parser extracts artist/title from filenames
        3. Leaderboard cache is updated correctly
        4. Scan cache is populated with file info
        """
        from musichouse.scanner import MP3Scanner
        from musichouse.parser import parse_filename
        from musichouse.leaderboard_cache import LeaderboardCache

        # Step 1: Scan the directory
        scanner = MP3Scanner(temp_dir)
        scanned_files = scanner.scan()
        
        # Verify scanner found all mock files
        assert len(scanned_files) == len(mock_mp3_files)
        assert scanner.get_file_count() == len(mock_mp3_files)
        assert len(scanner.get_errors()) == 0

        # Step 2: Parse filenames and collect artist counts
        artist_counts: Dict[str, int] = {}
        files_info = []
        
        for file_path in scanned_files:
            # Parse filename
            filename = file_path.name
            artist, title = parse_filename(filename)
            
            # Count artists
            if artist:
                artist_counts[artist] = artist_counts.get(artist, 0) + 1
            
            # Build file info for scan cache
            stat = file_path.stat()
            files_info.append({
                'path': str(file_path),
                'size': stat.st_size,
                'mtime': stat.st_mtime,
                'artist': artist,
                'title': title
            })

        # Verify parsing worked correctly
        assert len(artist_counts) > 0
        # We created 3 artists with 2 tracks each
        assert len(artist_counts) == 3
        for artist, count in artist_counts.items():
            assert count == 2, f"Artist {artist} should have 2 tracks"

        # Step 3: Update leaderboard cache
        leaderboard_cache.update_artists(artist_counts)
        
        # Verify leaderboard was updated
        top_artists = leaderboard_cache.get_top_artists(limit=10)
        assert len(top_artists) == 3
        
        # All artists should have count of 2
        for artist, count in top_artists:
            assert count == 2

        # Step 4: Update scan cache
        leaderboard_cache.update_scan_cache(files_info)
        
        # Verify scan cache was populated
        for file_info in files_info:
            cached = leaderboard_cache.get_cached_info(file_info['path'])
            assert cached is not None
            assert cached['artist'] == file_info['artist']
            assert cached['title'] == file_info['title']
            assert cached['size'] == file_info['size']

    def test_incremental_scan_detects_new_files(
        self, temp_dir, leaderboard_cache
    ):
        """Test that incremental scanning correctly detects new files.
        
        This test:
        1. Creates initial files and caches them
        2. Adds new files
        3. Verifies get_changed_files detects only the new files
        """
        from musichouse.scanner import MP3Scanner
        from musichouse.parser import parse_filename
        from musichouse.leaderboard_cache import LeaderboardCache

        # Step 1: Create initial files and cache them
        artist1_dir = temp_dir / "Artist One"
        artist1_dir.mkdir()
        
        initial_files = []
        for i in range(2):
            file_path = artist1_dir / f"Artist One - Track {i}.mp3"
            file_path.write_bytes(
                b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100
            )
            initial_files.append(file_path)

        # Cache initial files
        initial_info = []
        for file_path in initial_files:
            stat = file_path.stat()
            artist, title = parse_filename(file_path.name)
            initial_info.append({
                'path': str(file_path),
                'size': stat.st_size,
                'mtime': stat.st_mtime,
                'artist': artist,
                'title': title
            })
        
        leaderboard_cache.update_scan_cache(initial_info)

        # Step 2: Add new files
        artist2_dir = temp_dir / "Artist Two"
        artist2_dir.mkdir()
        
        new_files = []
        for i in range(2):
            file_path = artist2_dir / f"Artist Two - Song {i}.mp3"
            file_path.write_bytes(
                b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100
            )
            new_files.append(file_path)

        # Step 3: Check for changed files
        changed, new_count, modified_count, skipped_count = leaderboard_cache.get_changed_files(temp_dir)
        
        # Should detect only the new files
        assert len(changed) == 2
        assert new_count == 2
        assert modified_count == 0
        assert skipped_count == 2  # Initial files were skipped

    def test_leaderboard_updates_with_new_artists(
        self,
    ):
        """Test that leaderboard correctly accumulates artist counts.
        
        This test verifies:
        1. First scan adds artists
        2. Second scan with same artists increments counts
        3. Third scan with new artists adds them
        """
        import tempfile
        from musichouse.scanner import MP3Scanner
        from musichouse.parser import parse_filename
        from musichouse.leaderboard_cache import LeaderboardCache
        
        # Create completely isolated temp directory and database for this test
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)
            test_db_path = Path(tmpdir) / "test_leaderboard.db"
            
            # Remove DB if it exists from previous run
            if test_db_path.exists():
                test_db_path.unlink()
            # Also remove WAL/SHM files
            for ext in ["-wal", "-shm"]:
                p = test_db_path.with_suffix(f".db{ext}")
                if p.exists():
                    p.unlink()
            
            # Create a fresh leaderboard cache for this test
            test_cache = LeaderboardCache(test_db_path)
            artist_a_dir = temp_dir / "Artist A"
            artist_a_dir.mkdir()
            
            for i in range(2):
                file_path = artist_a_dir / f"Artist A - Track {i}.mp3"
                file_path.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
            
            scanner1 = MP3Scanner(temp_dir)
            files1 = scanner1.scan()
            
            artist_counts1 = {}
            for file_path in files1:
                artist, _ = parse_filename(file_path.name)
                if artist:
                    artist_counts1[artist] = artist_counts1.get(artist, 0) + 1
            
            test_cache.update_artists(artist_counts1)
            
            # Verify Artist A has count 2
            top1 = test_cache.get_top_artists(limit=10)
            assert len(top1) == 1
            assert top1[0] == ("Artist A", 2)
            
            # Second scan: Artist A with 3 more tracks (same dir, new files)
            for i in range(3, 6):
                file_path = artist_a_dir / f"Artist A - Track {i}.mp3"
                file_path.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
            
            scanner2 = MP3Scanner(temp_dir)
            files2 = scanner2.scan()
            
            artist_counts2 = {}
            for file_path in files2:
                artist, _ = parse_filename(file_path.name)
                if artist:
                    artist_counts2[artist] = artist_counts2.get(artist, 0) + 1
            
            test_cache.update_artists(artist_counts2)
            
            # Verify Artist A now has count 7 (2 + 5, cumulative)
            top2 = test_cache.get_top_artists(limit=10)
            assert len(top2) == 1
            assert top2[0] == ("Artist A", 7)
            
            # Third scan: Add Artist B with 1 track
            artist_b_dir = temp_dir / "Artist B"
            artist_b_dir.mkdir()
            file_path = artist_b_dir / "Artist B - Solo.mp3"
            file_path.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
            
            scanner3 = MP3Scanner(temp_dir)
            files3 = scanner3.scan()
            
            artist_counts3 = {}
            for file_path in files3:
                artist, _ = parse_filename(file_path.name)
                if artist:
                    artist_counts3[artist] = artist_counts3.get(artist, 0) + 1
            
            test_cache.update_artists(artist_counts3)
            
            # Verify both artists present, Artist A still on top
            # Artist A: 7 + 6 = 13 (all 6 tracks counted again)
            top3 = test_cache.get_top_artists(limit=10)
            assert len(top3) == 2
            assert top3[0][0] == "Artist A"  # Artist A still on top
            assert top3[0][1] == 12  # 7 + 5 = 12 cumulative
            assert top3[1] == ("Artist B", 1)
            
            test_cache.close()
    def test_scan_cache_persists_across_instances(self, temp_db_file, temp_dir):
        """Test that scan cache persists when creating new cache instances.
        
        This verifies the thread-local connection pattern works correctly
        and data is actually written to disk.
        """
        from musichouse.leaderboard_cache import LeaderboardCache

        # Create first cache instance and add data
        cache1 = LeaderboardCache(temp_db_file)
        
        files_info = [
            {
                'path': '/test/file1.mp3',
                'size': 1000,
                'mtime': 12345.0,
                'artist': 'Test Artist',
                'title': 'Test Title'
            }
        ]
        cache1.update_scan_cache(files_info)
        cache1.close()

        # Create new cache instance and verify data persists
        cache2 = LeaderboardCache(temp_db_file)
        
        cached = cache2.get_cached_info('/test/file1.mp3')
        assert cached is not None
        assert cached['artist'] == 'Test Artist'
        assert cached['title'] == 'Test Title'
        assert cached['size'] == 1000
        
        cache2.close()

    def test_parser_integration_with_real_filename_patterns(self, temp_dir):
        """Test parser handles various filename patterns correctly.
        
        Tests patterns:
        - Standard: "Artist - Title.mp3"
        - Multiple hyphens: "Artist - Title - Remix.mp3"
        - Solo title: "SoloTitle.mp3"
        - Unicode: "Artiste - Titre.mp3"
        """
        from musichouse.parser import parse_filename

        # Standard pattern
        artist, title = parse_filename("The Band - Song Name.mp3")
        assert artist == "The Band"
        assert title == "Song Name"

        # Multiple hyphens (first part is artist, rest is title)
        artist, title = parse_filename("DJ Artist - Track - Remix 2024.mp3")
        assert artist == "DJ Artist"
        assert title == "Track - Remix 2024"

        # Solo title (no hyphen)
        artist, title = parse_filename("JustATitle.mp3")
        assert artist == "JustATitle"
        assert title == "JustATitle"

        # Unicode characters
        artist, title = parse_filename("Artiste Français - Chanson.mp3")
        assert artist == "Artiste Français"
        assert title == "Chanson"

        # Case insensitive extension
        artist, title = parse_filename("Artist - Title.MP3")
        assert artist == "Artist"
        assert title == "Title"

    @pytest.mark.skipif(
        not Path("/media/disk3part1/Musica/Sigle/").exists(),
        reason="Sigle directory not mounted"
    )
    def test_scan_with_real_sigle_directory(self, leaderboard_cache):
        """Test scanning the real /media/disk3part1/Musica/Sigle/ directory.
        
        This is an optional test that runs only if the Sigle directory exists.
        It verifies the scanner works with real MP3 files.
        """
        from musichouse.scanner import MP3Scanner
        from musichouse.parser import parse_filename

        sigle_dir = Path("/media/disk3part1/Musica/Sigle/")
        
        # Scan the directory
        scanner = MP3Scanner(sigle_dir)
        files = scanner.scan()
        
        # Should find some files
        assert len(files) > 0
        
        # Parse a few files to verify parser works
        for file_path in files[:5]:
            artist, title = parse_filename(file_path.name)
            # At minimum, parser should return non-empty strings
            assert artist or title

    def test_error_handling_with_corrupted_files(self, temp_dir):
        """Test that scanner handles corrupted/invalid MP3 files gracefully.
        
        Creates files with invalid MP3 data and verifies:
        1. Scanner still finds them
        2. Parser handles their names correctly
        3. No crashes occur
        """
        from musichouse.scanner import MP3Scanner
        from musichouse.parser import parse_filename

        # Create directory with "corrupted" files (invalid MP3 data)
        corrupted_dir = temp_dir / "Corrupted"
        corrupted_dir.mkdir()
        
        # File with invalid MP3 header
        invalid_file = corrupted_dir / "Bad Artist - Bad Title.mp3"
        invalid_file.write_bytes(b"NOT AN MP3 FILE" + b"\x00" * 100)

        # Scanner should still find the file
        scanner = MP3Scanner(temp_dir)
        files = scanner.scan()
        
        assert len(files) == 1
        assert files[0] == invalid_file
        
        # Parser should still work on the filename
        artist, title = parse_filename(invalid_file.name)
        assert artist == "Bad Artist"
        assert title == "Bad Title"

    def test_nested_directory_structure(self, temp_dir):
        """Test scanning deeply nested directory structures.
        
        Verifies scanner handles:
        - Multiple levels of nesting
        - Mixed depth directories
        - Empty subdirectories
        """
        from musichouse.scanner import MP3Scanner
        from musichouse.parser import parse_filename

        # Create nested structure
        level1 = temp_dir / "Level1"
        level1.mkdir()
        
        level2 = level1 / "Level2"
        level2.mkdir()
        
        level3 = level2 / "Level3"
        level3.mkdir()
        
        # Add files at different levels
        file1 = temp_dir / "Root Artist - Root Track.mp3"
        file1.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
        
        file2 = level2 / "Deep Artist - Deep Track.mp3"
        file2.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
        
        file3 = level3 / "Deepest Artist - Deepest Track.mp3"
        file3.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

        # Empty directory (should be ignored)
        empty_dir = level1 / "Empty"
        empty_dir.mkdir()

        # Scan
        scanner = MP3Scanner(temp_dir)
        files = scanner.scan()
        
        # Should find all 3 files
        assert len(files) == 3
        
        # Verify all files found
        file_paths = [str(f) for f in files]
        assert str(file1) in file_paths
        assert str(file2) in file_paths
        assert str(file3) in file_paths

    def test_get_changed_files_with_modified_files(self, temp_db_file, temp_dir):
        """Test that get_changed_files detects modified files.
        
        This test:
        1. Caches initial file state
        2. Modifies file (changes mtime)
        3. Verifies modified file is detected
        """
        from musichouse.parser import parse_filename
        from musichouse.leaderboard_cache import LeaderboardCache
        import time

        # Create file
        artist_dir = temp_dir / "Mod Artist"
        artist_dir.mkdir()
        file_path = artist_dir / "Mod Artist - Mod Track.mp3"
        file_path.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

        # Cache initial state
        cache = LeaderboardCache(temp_db_file)
        stat = file_path.stat()
        
        initial_info = [{
            'path': str(file_path),
            'size': stat.st_size,
            'mtime': stat.st_mtime,
            'artist': 'Mod Artist',
            'title': 'Mod Track'
        }]
        cache.update_scan_cache(initial_info)
        cache.close()

        # Modify file (write new data, changes mtime)
        time.sleep(0.1)  # Ensure mtime changes
        file_path.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 200)

        # Check for changes
        cache2 = LeaderboardCache(temp_db_file)
        changed, new_count, modified_count, skipped_count = cache2.get_changed_files(temp_dir)
        cache2.close()

        # Should detect modified file
        assert len(changed) == 1
        assert changed[0] == file_path
        assert new_count == 0
        assert modified_count == 1
        assert skipped_count == 0
