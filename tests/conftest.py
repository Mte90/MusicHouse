"""Shared pytest fixtures and configuration for MusicHouse tests."""

import os
import sqlite3
import tempfile
from pathlib import Path
from typing import List, Generator

import pytest
from PyQt6.QtWidgets import QApplication


# ============================================================================
# Pytest Markers
# ============================================================================
def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers", "ui: mark test as UI test requiring Qt"
    )
    config.addinivalue_line(
        "markers", "fast: mark test as fast test (no real files)"
    )


# ============================================================================
# Qt Application Fixture
# ============================================================================
@pytest.fixture(scope="session", autouse=True)
def qapp() -> Generator[QApplication, None, None]:
    """Create QApplication instance for pytest-qt tests.
    
    Runs headless via QT_QPA_PLATFORM=offscreen environment variable.
    Set QT_QPA_PLATFORM=offscreen before running pytest for headless mode.
    
    Usage:
        QT_QPA_PLATFORM=offscreen pytest -v
    """
    # Ensure headless mode if not already set
    if "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    
    yield app
    
    app.quit()


# ============================================================================
# Temporary Database Fixture
# ============================================================================
@pytest.fixture
def temp_db() -> Generator[sqlite3.Connection, None, None]:
    """Create a temporary in-memory SQLite database for testing.
    
    Returns:
        sqlite3.Connection: Connection to in-memory database.
        
    Usage:
        def test_cache(temp_db):
            cursor = temp_db.execute("SELECT * FROM ...")
    """
    # Use :memory: for true in-memory database (fastest, isolated per test)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    
    yield conn
    
    conn.close()


# Alternative: temporary file-based database (useful for testing persistence)
@pytest.fixture
def temp_db_file() -> Generator[Path, None, None]:
    """Create a temporary file-based SQLite database for testing.
    
    Returns:
        Path: Path to temporary database file.
        
    Usage:
        def test_cache(temp_db_file):
            cache = LeaderboardCache(temp_db_file)
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    
    yield db_path
    
    # Cleanup
    if db_path.exists():
        db_path.unlink()
    # Remove WAL and SHM files if they exist
    for ext in ["-wal", "-shm"]:
        wal_path = db_path.with_suffix(f".db{ext}")
        if wal_path.exists():
            wal_path.unlink()


# ============================================================================
# Temporary Directory Fixture
# ============================================================================
@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files.
    
    Returns:
        Path: Path to temporary directory.
        
    Usage:
        def test_scanner(temp_dir):
            test_file = temp_dir / "test.mp3"
            test_file.write_bytes(b"fake mp3 data")
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ============================================================================
# Mock MP3 Files Fixture
# ============================================================================
@pytest.fixture
def mock_mp3_files(temp_dir) -> List[Path]:
    """Create mock MP3 files in temporary directory for testing.
    
    Creates mock MP3 files with standard test data patterns.
    Files are created in temp_dir with structure:
        temp_dir/
            artist1/
                track1.mp3
                track2.mp3
            artist2/
                track1.mp3
    
    Returns:
        List[Path]: List of paths to mock MP3 files.
        
    Usage:
        def test_scanner(mock_mp3_files):
            scanner = MP3Scanner(temp_dir)
            files = scanner.scan()
    """
    # Create mock directory structure
    artists = ["Test Artist 1", "Test Artist 2", "Another Artist"]
    mock_files = []
    
    for artist in artists:
        artist_dir = temp_dir / artist
        artist_dir.mkdir(parents=True, exist_ok=True)
        
        # Create 2-3 mock MP3 files per artist
        for i in range(1, 3):
            filename = f"{artist} - Track {i}.mp3"
            file_path = artist_dir / filename
            
            # Create minimal valid MP3 file (ID3v2 header + dummy data)
            # This is a minimal valid MP3 frame structure
            mp3_data = (
                b"ID3\x04\x00\x00\x00\x00\x00\x00"  # ID3v2.4 header
                b"\x00" * 100  # Dummy data to simulate MP3 content
            )
            file_path.write_bytes(mp3_data)
            mock_files.append(file_path)
    
    return mock_files


# ============================================================================
# LeaderboardCache Fixtures
# ============================================================================
@pytest.fixture
def leaderboard_cache(temp_db_file):
    """Create LeaderboardCache instance with temporary database.
    
    Returns:
        LeaderboardCache: Cache instance using temp file database.
    """
    from musichouse.leaderboard_cache import LeaderboardCache
    
    cache = LeaderboardCache(temp_db_file)
    yield cache
    cache.close()


# ============================================================================
# MainWindow Fixture
# ============================================================================
@pytest.fixture
def main_window(qapp):
    """Create MainWindow instance for UI testing.
    
    Returns:
        MainWindow: MainWindow instance.
        
    Usage:
        def test_main_window(main_window):
            assert main_window.isVisible()
    """
    from musichouse.ui.main_window import MainWindow
    
    window = MainWindow()
    yield window
    window.close()
