"""Unit tests for organizer module."""

from pathlib import Path

import pytest

from musichouse.organizer import FolderType, FolderInfo, analyze_folder_structure, _normalize_name


# ============================================================================
# Fixtures
# ============================================================================
@pytest.fixture
def organizer_cache(temp_db_file):
    """Create LeaderboardCache instance with temporary database."""
    from musichouse.leaderboard_cache import LeaderboardCache

    cache = LeaderboardCache(temp_db_file)
    yield cache
    cache.close()


# ============================================================================
# Test: _normalize_name()
# ============================================================================
def test_normalize_name_lowercase():
    """Test that normalization converts to lowercase."""
    assert _normalize_name("Metallica") == "metallica"
    assert _normalize_name("METALLICA") == "metallica"


def test_normalize_name_strips_whitespace():
    """Test that normalization strips leading/trailing whitespace."""
    assert _normalize_name("  Metallica  ") == "metallica"
    assert _normalize_name("Metallica") == "metallica"


def test_normalize_name_collapses_whitespace():
    """Test that normalization collapses multiple spaces."""
    assert _normalize_name("Metal  lica") == "metal lica"
    assert _normalize_name("  Metallica   Track  ") == "metallica track"


# ============================================================================
# Test: FolderInfo repr
# ============================================================================
def test_folder_info_repr():
    """Test FolderInfo string representation."""
    info = FolderInfo(
        path=Path("/test"),
        folder_type=FolderType.CORRECT_ARTIST,
        artists=["Metallica"],
        file_count=5
    )
    repr_str = repr(info)
    assert "FolderInfo" in repr_str
    assert "correct_artist" in repr_str
    assert "metallica" in repr_str.lower() or "Metallica" in repr_str


# ============================================================================
# Test: analyze_folder_structure - GENRE_CONTAINER
# ============================================================================
def test_genre_container(organizer_cache, temp_dir):
    """Test detection of genre container (subfolders, no direct MP3s)."""
    # Create structure: temp_dir/Genre/Artist1/track.mp3
    genre_dir = temp_dir / "Rock"
    artist_dir = genre_dir / "Metallica"
    artist_dir.mkdir(parents=True)

    # Add file to subfolder
    track = artist_dir / "track.mp3"
    track.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

    # Cache the file
    organizer_cache.update_scan_cache([
        {
            'path': str(track),
            'size': 100,
            'mtime': 123456.0,
            'artist': 'Metallica',
            'title': 'Track 1'
        }
    ])

    # Analyze
    results = analyze_folder_structure(temp_dir, organizer_cache)

    # Should find both folders
    assert len(results) == 2

    # Find the Rock folder
    rock_folder = next((r for r in results if r.path.name == "Rock"), None)
    assert rock_folder is not None
    assert rock_folder.folder_type == FolderType.GENRE_CONTAINER
    assert rock_folder.file_count == 0
    assert rock_folder.artists == []


# ============================================================================
# Test: analyze_folder_structure - CORRECT_ARTIST
# ============================================================================
def test_correct_artist(organizer_cache, temp_dir):
    """Test detection of correctly named artist folder."""
    # Create structure: temp_dir/Metallica/track.mp3
    artist_dir = temp_dir / "Metallica"
    artist_dir.mkdir()

    track = artist_dir / "track.mp3"
    track.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

    # Cache the file
    organizer_cache.update_scan_cache([
        {
            'path': str(track),
            'size': 100,
            'mtime': 123456.0,
            'artist': 'Metallica',
            'title': 'Track 1'
        }
    ])

    # Analyze
    results = analyze_folder_structure(temp_dir, organizer_cache)

    assert len(results) == 1
    info = results[0]
    assert info.folder_type == FolderType.CORRECT_ARTIST
    assert info.artists == ["Metallica"]
    assert info.file_count == 1
    assert info.suggested_name is None


# ============================================================================
# Test: analyze_folder_structure - MISNAMED_ARTIST
# ============================================================================
def test_misnamed_artist(organizer_cache, temp_dir):
    """Test detection of misnamed artist folder."""
    # Create structure: temp_dir/Rock/track.mp3 (but artist is Iron Maiden)
    folder = temp_dir / "Rock"
    folder.mkdir()

    track = folder / "track.mp3"
    track.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

    # Cache the file with different artist
    organizer_cache.update_scan_cache([
        {
            'path': str(track),
            'size': 100,
            'mtime': 123456.0,
            'artist': 'Iron Maiden',
            'title': 'Track 1'
        }
    ])

    # Analyze
    results = analyze_folder_structure(temp_dir, organizer_cache)

    assert len(results) == 1
    info = results[0]
    assert info.folder_type == FolderType.MISNAMED_ARTIST
    assert info.artists == ["Iron Maiden"]
    assert info.file_count == 1
    assert info.suggested_name == "Iron Maiden"


# ============================================================================
# Test: analyze_folder_structure - MIXED
# ============================================================================
def test_mixed_artists(organizer_cache, temp_dir):
    """Test detection of folder with multiple artists."""
    folder = temp_dir / "Mixed"
    folder.mkdir()

    track1 = folder / "track1.mp3"
    track2 = folder / "track2.mp3"
    track1.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    track2.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

    # Cache with different artists
    organizer_cache.update_scan_cache([
        {
            'path': str(track1),
            'size': 100,
            'mtime': 123456.0,
            'artist': 'Metallica',
            'title': 'Track 1'
        },
        {
            'path': str(track2),
            'size': 100,
            'mtime': 123456.0,
            'artist': 'Iron Maiden',
            'title': 'Track 2'
        }
    ])

    # Analyze
    results = analyze_folder_structure(temp_dir, organizer_cache)

    assert len(results) == 1
    info = results[0]
    assert info.folder_type == FolderType.MIXED
    assert sorted(info.artists) == ["Iron Maiden", "Metallica"]
    assert info.file_count == 2
    assert info.suggested_name is None


# ============================================================================
# Test: analyze_folder_structure - EMPTY
# ============================================================================
def test_empty_folder(organizer_cache, temp_dir):
    """Test detection of empty folder."""
    folder = temp_dir / "EmptyFolder"
    folder.mkdir()

    # Analyze
    results = analyze_folder_structure(temp_dir, organizer_cache)

    assert len(results) == 1
    info = results[0]
    assert info.folder_type == FolderType.EMPTY
    assert info.artists == []
    assert info.file_count == 0
    assert info.suggested_name is None


# ============================================================================
# Test: nested structure - genre container with artist subfolders
# ============================================================================
def test_nested_genre_with_artists(organizer_cache, temp_dir):
    """Test nested structure: genre container with multiple artist subfolders."""
    # Create: temp_dir/Rock/Metallica/track1.mp3, Iron Maiden/track2.mp3
    rock_dir = temp_dir / "Rock"
    metallica_dir = rock_dir / "Metallica"
    iron_maiden_dir = rock_dir / "Iron Maiden"
    metallica_dir.mkdir(parents=True)
    iron_maiden_dir.mkdir(parents=True)

    track1 = metallica_dir / "track1.mp3"
    track2 = iron_maiden_dir / "track2.mp3"
    track1.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    track2.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

    # Cache files
    organizer_cache.update_scan_cache([
        {
            'path': str(track1),
            'size': 100,
            'mtime': 123456.0,
            'artist': 'Metallica',
            'title': 'Track 1'
        },
        {
            'path': str(track2),
            'size': 100,
            'mtime': 123456.0,
            'artist': 'Iron Maiden',
            'title': 'Track 2'
        }
    ])

    # Analyze
    results = analyze_folder_structure(temp_dir, organizer_cache)

    # Should find all 3 folders
    assert len(results) == 3

    # Rock is genre container
    rock = next((r for r in results if r.path.name == "Rock"), None)
    assert rock is not None
    assert rock.folder_type == FolderType.GENRE_CONTAINER
    assert rock.file_count == 0

    # Metallica is correct artist
    metallica = next((r for r in results if r.path.name == "Metallica"), None)
    assert metallica is not None
    assert metallica.folder_type == FolderType.CORRECT_ARTIST
    assert metallica.artists == ["Metallica"]

    # Iron Maiden is correct artist
    iron_maiden = next((r for r in results if r.path.name == "Iron Maiden"), None)
    assert iron_maiden is not None
    assert iron_maiden.folder_type == FolderType.CORRECT_ARTIST
    assert iron_maiden.artists == ["Iron Maiden"]


# ============================================================================
# Test: case-insensitive artist matching
# ============================================================================
def test_case_insensitive_matching(organizer_cache, temp_dir):
    """Test that folder name matches artist tag case-insensitively."""
    # Create: temp_dir/metallica/track.mp3 (folder lowercase)
    # But artist tag is "Metallica" (capitalized)
    folder = temp_dir / "metallica"
    folder.mkdir()

    track = folder / "track.mp3"
    track.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

    # Cache with capitalized artist
    organizer_cache.update_scan_cache([
        {
            'path': str(track),
            'size': 100,
            'mtime': 123456.0,
            'artist': 'Metallica',
            'title': 'Track 1'
        }
    ])

    # Analyze
    results = analyze_folder_structure(temp_dir, organizer_cache)

    assert len(results) == 1
    info = results[0]
    # Should match case-insensitively
    assert info.folder_type == FolderType.CORRECT_ARTIST
    assert info.artists == ["Metallica"]
    assert info.suggested_name is None


# ============================================================================
# Test: multiple files, same artist
# ============================================================================
def test_multiple_files_same_artist(organizer_cache, temp_dir):
    """Test folder with multiple files all by same artist."""
    folder = temp_dir / "Metallica"
    folder.mkdir()

    tracks = [folder / f"track{i}.mp3" for i in range(1, 6)]
    for track in tracks:
        track.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

    # Cache all files
    cache_data = [
        {
            'path': str(track),
            'size': 100,
            'mtime': 123456.0,
            'artist': 'Metallica',
            'title': f'Track {i}'
        }
        for i, track in enumerate(tracks, 1)
    ]
    organizer_cache.update_scan_cache(cache_data)

    # Analyze
    results = analyze_folder_structure(temp_dir, organizer_cache)

    assert len(results) == 1
    info = results[0]
    assert info.folder_type == FolderType.CORRECT_ARTIST
    assert info.artists == ["Metallica"]
    assert info.file_count == 5


# ============================================================================
# Test: folder name with spaces vs artist name
# ============================================================================
def test_folder_name_with_spaces(organizer_cache, temp_dir):
    """Test matching folder name with spaces to artist name."""
    # Folder "Metal lica" (double space) should match "Metallica" after normalization
    folder = temp_dir / "Metal lica"
    folder.mkdir()

    track = folder / "track.mp3"
    track.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

    # Cache with normal artist name
    organizer_cache.update_scan_cache([
        {
            'path': str(track),
            'size': 100,
            'mtime': 123456.0,
            'artist': 'Metallica',
            'title': 'Track 1'
        }
    ])

    # Analyze
    results = analyze_folder_structure(temp_dir, organizer_cache)

    assert len(results) == 1
    info = results[0]
    # After normalization, "metal lica" != "metallica"
    assert info.folder_type == FolderType.MISNAMED_ARTIST
    assert info.suggested_name == "Metallica"


# ============================================================================
# Test: files without artist tag are ignored
# ============================================================================
def test_files_without_artist_ignored(organizer_cache, temp_dir):
    """Test that files without artist tag don't contribute to artist count."""
    folder = temp_dir / "Folder"
    folder.mkdir()

    track = folder / "track.mp3"
    track.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)

    # Cache without artist
    organizer_cache.update_scan_cache([
        {
            'path': str(track),
            'size': 100,
            'mtime': 123456.0,
            'artist': None,
            'title': 'Track 1'
        }
    ])

    # Analyze
    results = analyze_folder_structure(temp_dir, organizer_cache)

    # File has no artist, so folder appears empty from artist perspective
    # But it has a file, so it's not EMPTY
    # This is an edge case - the folder has files but no artists
    assert len(results) == 1
    info = results[0]
    # Since artists_in_folder is empty and has_files is True but num_artists is 0,
    # it falls through to the has_subfolders and has_files case
    # Actually, no subfolders, has files, 0 artists -> falls to else -> EMPTY
    assert info.folder_type == FolderType.EMPTY


# ============================================================================
# Test: non-mp3 files are ignored
# ============================================================================
def test_non_mp3_files_ignored(organizer_cache, temp_dir):
    """Test that non-MP3 files are not counted."""
    folder = temp_dir / "Folder"
    folder.mkdir()

    # Create MP3 and non-MP3 files
    mp3_file = folder / "track.mp3"
    txt_file = folder / "readme.txt"
    mp3_file.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 100)
    txt_file.write_text("readme")

    # Cache only the MP3
    organizer_cache.update_scan_cache([
        {
            'path': str(mp3_file),
            'size': 100,
            'mtime': 123456.0,
            'artist': 'Metallica',
            'title': 'Track 1'
        }
    ])

    # Analyze
    results = analyze_folder_structure(temp_dir, organizer_cache)

    assert len(results) == 1
    info = results[0]
    assert info.file_count == 1  # Only MP3 counted
    assert info.artists == ["Metallica"]