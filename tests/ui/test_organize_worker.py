"""Unit tests for organize_worker module.

Tests for OrganizeWorker QThread worker.
Uses mocking to avoid real API calls and file system operations.
"""

from unittest.mock import MagicMock, patch

from musichouse.ai_client import AIClient
from musichouse.leaderboard_cache import LeaderboardCache
from musichouse.organizer import FolderInfo, FolderType
from musichouse.ui.organize_worker import OrganizeWorker

# ============================================================================
# OrganizeWorker Tests
# ============================================================================

class TestOrganizeWorker:
    """Tests for OrganizeWorker class."""

    def test_run_successful_full_analysis(self, temp_dir, qapp):
        """Test successful full run: analyze, fetch genres, get AI suggestions."""
        base_path = temp_dir / "music"
        base_path.mkdir()

        # Create mock FolderInfo objects
        mock_folders = [
            FolderInfo(
                path=base_path / "OldName",
                folder_type=FolderType.MISNAMED_ARTIST,
                artists=["Metallica"],
                file_count=5,
                suggested_name="Metallica"
            ),
            FolderInfo(
                path=base_path / "Mixed",
                folder_type=FolderType.MIXED,
                artists=["Iron Maiden", "Judas Priest"],
                file_count=10,
                suggested_name=None
            ),
            FolderInfo(
                path=base_path / "Correct",
                folder_type=FolderType.CORRECT_ARTIST,
                artists=["Black Sabbath"],
                file_count=3,
                suggested_name=None
            ),
        ]

        cache = LeaderboardCache(temp_dir / "test.db")
        ai_client = AIClient()

        # Mock file data in cache
        cache.update_scan_cache([
            {
                "path": str(base_path / "OldName" / "song1.mp3"),
                "size": 1000,
                "mtime": 1234567890.0,
                "artist": "Metallica",
                "title": "Song 1",
                "needs_fixing": 0,
                "missing_artist": 0,
                "missing_title": 0,
                "suggested_artist": None,
                "suggested_title": None,
                "tag_data": None,
            },
            {
                "path": str(base_path / "Mixed" / "song2.mp3"),
                "size": 2000,
                "mtime": 1234567891.0,
                "artist": "Iron Maiden",
                "title": "Song 2",
                "needs_fixing": 0,
                "missing_artist": 0,
                "missing_title": 0,
                "suggested_artist": None,
                "suggested_title": None,
                "tag_data": None,
            },
        ])

        progress_args = []
        analysis_finished_args = []

        def on_progress(msg):
            progress_args.append(msg)

        def on_finished(result):
            analysis_finished_args.append(result)

        with patch("musichouse.ui.organize_worker.analyze_folder_structure", return_value=mock_folders):  # noqa: SIM117
            with patch("musichouse.ui.organize_worker.MusicBrainzClient") as mock_mb_client_class:
                mock_mb_client = MagicMock()
                mock_mb_client.get_artist_genres.side_effect = lambda artist: {
                    "Metallica": ["heavy metal", "thrash metal"],
                    "Iron Maiden": ["heavy metal", "NWOBHM"],
                    "Judas Priest": ["heavy metal", "hard rock"],
                }.get(artist, [])
                mock_mb_client_class.return_value = mock_mb_client

                with patch.object(ai_client, "analyze_folder_organization", return_value={
                    "moves": [{"from": "OldName", "to": "Metallica", "reason": "Rename folder"}],
                    "renames": []
                }):
                    worker = OrganizeWorker(cache, ai_client, base_path)

                    worker.progress.connect(on_progress)
                    worker.analysis_finished.connect(on_finished)

                    worker.run()

        # Verify progress signals
        assert "Analyzing folder structure..." in progress_args
        assert "Analyzing with AI..." in progress_args
        assert any("Fetching genre 1/" in msg for msg in progress_args)

        # Verify analysis_finished emitted with correct structure
        assert len(analysis_finished_args) == 1
        result = analysis_finished_args[0]
        assert "moves" in result
        assert "renames" in result
        assert "folders" in result
        assert len(result["moves"]) == 1
        assert len(result["folders"]) == 3

        cache.close()

    def test_run_stops_during_genre_fetching(self, temp_dir, qapp):
        """Test that worker exits early when stop flag is set during genre fetching."""
        base_path = temp_dir / "music"
        base_path.mkdir()

        mock_folders = [
            FolderInfo(
                path=base_path / "Mixed",
                folder_type=FolderType.MIXED,
                artists=["Artist1", "Artist2", "Artist3"],
                file_count=10,
                suggested_name=None
            ),
        ]

        cache = LeaderboardCache(temp_dir / "test.db")
        ai_client = AIClient()

        progress_args = []
        analysis_finished_args = []
        progress_percent_args = []

        def on_progress(msg):
            progress_args.append(msg)
            # Stop during first genre fetch
            if "Fetching genre" in msg and len(progress_args) == 2:
                worker.stop()

        def on_progress_percent(current, total):
            progress_percent_args.append((current, total))

        def on_finished(result):
            analysis_finished_args.append(result)

        with patch("musichouse.ui.organize_worker.analyze_folder_structure", return_value=mock_folders):  # noqa: SIM117
            with patch("musichouse.ui.organize_worker.MusicBrainzClient") as mock_mb_client_class:
                mock_mb_client = MagicMock()
                mock_mb_client.get_artist_genres.side_effect = lambda artist: ["genre"]
                mock_mb_client_class.return_value = mock_mb_client

                worker = OrganizeWorker(cache, ai_client, base_path)

                worker.progress.connect(on_progress)
                worker.progress_percent.connect(on_progress_percent)
                worker.analysis_finished.connect(on_finished)

                worker.run()

        # Verify worker stopped early and emitted empty result
        assert len(analysis_finished_args) == 1
        assert analysis_finished_args[0] == {}

        cache.close()

    def test_run_handles_musicbrainz_error_for_one_artist(self, temp_dir, qapp):
        """Test that MusicBrainzError for one artist doesn't stop processing others."""
        base_path = temp_dir / "music"
        base_path.mkdir()

        mock_folders = [
            FolderInfo(
                path=base_path / "Mixed",
                folder_type=FolderType.MIXED,
                artists=["ValidArtist", "NotFoundArtist"],
                file_count=5,
                suggested_name=None
            ),
        ]

        cache = LeaderboardCache(temp_dir / "test.db")
        ai_client = AIClient()

        from musichouse.musicbrainz_client import MusicBrainzError
        progress_args = []
        analysis_finished_args = []
        progress_percent_args = []

        def on_progress(msg):
            progress_args.append(msg)

        def on_progress_percent(current, total):
            progress_percent_args.append((current, total))

        def on_finished(result):
            analysis_finished_args.append(result)

        with patch("musichouse.ui.organize_worker.analyze_folder_structure", return_value=mock_folders):  # noqa: SIM117
            with patch("musichouse.ui.organize_worker.MusicBrainzClient") as mock_mb_client_class:
                mock_mb_client = MagicMock()

                def get_genres(artist):
                    if artist == "NotFoundArtist":
                        raise MusicBrainzError("Artist not found")
                    return ["rock"]

                mock_mb_client.get_artist_genres.side_effect = get_genres
                mock_mb_client_class.return_value = mock_mb_client

                with patch.object(ai_client, "analyze_folder_organization", return_value={
                    "moves": [],
                    "renames": []
                }):
                    worker = OrganizeWorker(cache, ai_client, base_path)

                    worker.progress.connect(on_progress)
                    worker.progress_percent.connect(on_progress_percent)
                    worker.analysis_finished.connect(on_finished)
                    worker.run()

        # Verify both artists were processed (one with error, one successful)
        assert len(analysis_finished_args) == 1
        result = analysis_finished_args[0]
        assert "folders" in result

        cache.close()

    def test_run_handles_ai_call_error(self, temp_dir, qapp):
        """Test that AI call error emits error signal."""
        base_path = temp_dir / "music"
        base_path.mkdir()

        mock_folders = [
            FolderInfo(
                path=base_path / "OldName",
                folder_type=FolderType.MISNAMED_ARTIST,
                artists=["Metallica"],
                file_count=5,
                suggested_name="Metallica"
            ),
        ]

        cache = LeaderboardCache(temp_dir / "test.db")
        ai_client = AIClient()
        progress_args = []
        error_args = []
        progress_percent_args = []

        def on_progress(msg):
            progress_args.append(msg)

        def on_progress_percent(current, total):
            progress_percent_args.append((current, total))

        def on_error(msg):
            error_args.append(msg)

        with patch("musichouse.ui.organize_worker.analyze_folder_structure", return_value=mock_folders):  # noqa: SIM117
            with patch("musichouse.ui.organize_worker.MusicBrainzClient") as mock_mb_client_class:
                mock_mb_client = MagicMock()
                mock_mb_client.get_artist_genres.return_value = ["heavy metal"]
                mock_mb_client_class.return_value = mock_mb_client

                with patch.object(ai_client, "analyze_folder_organization", side_effect=Exception("AI service unavailable")):
                    worker = OrganizeWorker(cache, ai_client, base_path)

                    worker.progress.connect(on_progress)
                    worker.progress_percent.connect(on_progress_percent)
                    worker.error.connect(on_error)
                    worker.run()

        # Verify error signal was emitted
        assert len(error_args) == 1
        assert "AI service unavailable" in error_args[0]

        cache.close()

    def test_run_stops_before_ai_call(self, temp_dir, qapp):
        """Test that worker stops before AI call if stop flag is set."""
        base_path = temp_dir / "music"
        base_path.mkdir()

        mock_folders = [
            FolderInfo(
                path=base_path / "OldName",
                folder_type=FolderType.MISNAMED_ARTIST,
                artists=["Metallica"],
                file_count=5,
                suggested_name="Metallica"
            ),
        ]

        cache = LeaderboardCache(temp_dir / "test.db")
        ai_client = AIClient()
        progress_args = []
        analysis_finished_args = []
        progress_percent_args = []

        def on_progress(msg):
            progress_args.append(msg)
            # Stop after genre fetching completes
            if "Fetching genre" in msg:
                worker.stop()

        def on_progress_percent(current, total):
            progress_percent_args.append((current, total))

        def on_finished(result):
            analysis_finished_args.append(result)

        with patch("musichouse.ui.organize_worker.analyze_folder_structure", return_value=mock_folders):  # noqa: SIM117
            with patch("musichouse.ui.organize_worker.MusicBrainzClient") as mock_mb_client_class:
                mock_mb_client = MagicMock()
                mock_mb_client.get_artist_genres.return_value = ["heavy metal"]
                mock_mb_client_class.return_value = mock_mb_client

                worker = OrganizeWorker(cache, ai_client, base_path)

                worker.progress.connect(on_progress)
                worker.progress_percent.connect(on_progress_percent)
                worker.analysis_finished.connect(on_finished)
                worker.run()

        # Verify worker stopped before AI call (empty result)
        assert len(analysis_finished_args) == 1
        assert analysis_finished_args[0] == {}
        # AI should not have been called
        assert not hasattr(ai_client, '_called') or not getattr(ai_client, '_called', False)

        cache.close()

    def test_build_folder_structure_only_includes_misnamed_and_mixed(self, temp_dir, qapp):
        """Test that folder_structure only includes MISNAMED_ARTIST and MIXED folders."""
        base_path = temp_dir / "music"
        base_path.mkdir()

        mock_folders = [
            FolderInfo(
                path=base_path / "OldName",
                folder_type=FolderType.MISNAMED_ARTIST,
                artists=["Metallica"],
                file_count=5,
                suggested_name="Metallica"
            ),
            FolderInfo(
                path=base_path / "Correct",
                folder_type=FolderType.CORRECT_ARTIST,
                artists=["Black Sabbath"],
                file_count=3,
                suggested_name=None
            ),
            FolderInfo(
                path=base_path / "Genre",
                folder_type=FolderType.GENRE_CONTAINER,
                artists=[],
                file_count=0,
                suggested_name=None
            ),
        ]

        cache = LeaderboardCache(temp_dir / "test.db")
        ai_client = AIClient()

        cache.update_scan_cache([
            {
                "path": str(base_path / "OldName" / "song1.mp3"),
                "size": 1000,
                "mtime": 1234567890.0,
                "artist": "Metallica",
                "title": "Song 1",
                "needs_fixing": 0,
                "missing_artist": 0,
                "missing_title": 0,
                "suggested_artist": None,
                "suggested_title": None,
                "tag_data": None,
            },
            {
                "path": str(base_path / "Correct" / "song2.mp3"),
                "size": 2000,
                "mtime": 1234567891.0,
                "artist": "Black Sabbath",
                "title": "Song 2",
                "needs_fixing": 0,
                "missing_artist": 0,
                "missing_title": 0,
                "suggested_artist": None,
                "suggested_title": None,
                "tag_data": None,
            },
        ])
        progress_args = []
        analysis_finished_args = []
        progress_percent_args = []

        def on_progress(msg):
            progress_args.append(msg)

        def on_progress_percent(current, total):
            progress_percent_args.append((current, total))

        def on_finished(result):
            analysis_finished_args.append(result)

        with patch("musichouse.ui.organize_worker.analyze_folder_structure", return_value=mock_folders):  # noqa: SIM117
            with patch("musichouse.ui.organize_worker.MusicBrainzClient") as mock_mb_client_class:
                mock_mb_client = MagicMock()
                mock_mb_client.get_artist_genres.return_value = ["heavy metal"]
                mock_mb_client_class.return_value = mock_mb_client

                with patch.object(ai_client, "analyze_folder_organization", return_value={
                    "moves": [],
                    "renames": []
                }):
                    worker = OrganizeWorker(cache, ai_client, base_path)

                    worker.progress.connect(on_progress)
                    worker.progress_percent.connect(on_progress_percent)
                    worker.analysis_finished.connect(on_finished)
                    worker.run()

        # Verify result contains correct data
        result = analysis_finished_args[0]
        assert len(result["folders"]) == 3

        cache.close()

    def test_run_empty_artists_list(self, temp_dir, qapp):
        """Test worker handles case where no artists need genre fetching."""
        base_path = temp_dir / "music"
        base_path.mkdir()

        mock_folders = [
            FolderInfo(
                path=base_path / "Correct",
                folder_type=FolderType.CORRECT_ARTIST,
                artists=["Metallica"],
                file_count=5,
                suggested_name=None
            ),
            FolderInfo(
                path=base_path / "Genre",
                folder_type=FolderType.GENRE_CONTAINER,
                artists=[],
                file_count=0,
                suggested_name=None
            ),
        ]

        cache = LeaderboardCache(temp_dir / "test.db")
        ai_client = AIClient()
        progress_args = []
        analysis_finished_args = []
        progress_percent_args = []

        def on_progress(msg):
            progress_args.append(msg)

        def on_progress_percent(current, total):
            progress_percent_args.append((current, total))

        def on_finished(result):
            analysis_finished_args.append(result)

        with patch("musichouse.ui.organize_worker.analyze_folder_structure", return_value=mock_folders):  # noqa: SIM117
            with patch.object(ai_client, "analyze_folder_organization", return_value={
                "moves": [],
                "renames": []
            }):
                worker = OrganizeWorker(cache, ai_client, base_path)

                worker.progress.connect(on_progress)
                worker.progress_percent.connect(on_progress_percent)
                worker.analysis_finished.connect(on_finished)
                worker.run()

        assert len(analysis_finished_args) == 1
        result = analysis_finished_args[0]
        assert "moves" in result
        assert "renames" in result
        assert "folders" in result

        cache.close()