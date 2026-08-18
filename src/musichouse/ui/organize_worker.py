"""QThread worker for folder organization analysis."""

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from musichouse.ai_client import AIClient
from musichouse.leaderboard_cache import LeaderboardCache
from musichouse.musicbrainz_client import MusicBrainzClient, MusicBrainzError
from musichouse.organizer import FolderType, analyze_folder_structure
from musichouse import log_setup as logging

logger = logging.get_logger(__name__)


class OrganizeWorker(QThread):
    """Worker thread that analyzes folder structure, fetches genres, and gets AI suggestions.

    Orchestrates the folder organization analysis pipeline:
    1. Analyzes folder structure using analyze_folder_structure()
    2. Fetches missing artist genres via MusicBrainz
    3. Calls AI client for move/rename suggestions

    Emits progress signals for UI updates and analysis_finished with results.
    """

    progress = pyqtSignal(str)  # status message
    analysis_finished = pyqtSignal(dict)  # result dict with "moves", "renames", "folders"
    error = pyqtSignal(str)  # error message

    def __init__(self, cache: LeaderboardCache, ai_client: AIClient,
                 base_path: Path, parent=None):
        """Initialize the worker.

        Args:
            cache: LeaderboardCache instance for file metadata.
            ai_client: AIClient for organization suggestions.
            base_path: Root directory to analyze.
            parent: Parent QObject.
        """
        super().__init__(parent)
        self._cache = cache
        self._ai_client = ai_client
        self._base_path = base_path
        self._stop_flag = False

    def stop(self):
        """Request stop of the worker. Called from GUI thread."""
        self._stop_flag = True

    def run(self):
        """Main orchestration loop for folder organization analysis."""
        try:
            # Step 1: Analyze folder structure
            self.progress.emit("Analyzing folder structure...")
            folders = analyze_folder_structure(self._base_path, self._cache)

            # Step 2: Collect unique artists from folders needing reorganization
            artists_to_fetch = set()
            for folder_info in folders:
                if folder_info.folder_type in (FolderType.MISNAMED_ARTIST, FolderType.MIXED):
                    artists_to_fetch.update(folder_info.artists)

            # Step 3: Fetch genres for each artist
            artist_genres: dict[str, list[str]] = {}
            for artist in artists_to_fetch:
                if self._stop_flag:
                    logger.info("OrganizeWorker stopped by user during genre fetching")
                    self.analysis_finished.emit({})
                    return

                self.progress.emit(f"Fetching genre: {artist}")
                musicbrainz_client = MusicBrainzClient(self._cache)

                try:
                    genres = musicbrainz_client.get_artist_genres(artist)
                    artist_genres[artist] = genres
                except MusicBrainzError as e:
                    logger.warning(f"MusicBrainz error for {artist}: {e}")
                    artist_genres[artist] = []

            # Step 4: Check stop flag before AI call
            if self._stop_flag:
                logger.info("OrganizeWorker stopped by user before AI analysis")
                self.analysis_finished.emit({})
                return

            # Step 5: Build folder_structure dict for AI
            folder_structure = self._build_folder_structure(folders)

            # Step 6: Get AI suggestions
            self.progress.emit("Analyzing with AI...")
            result = self._ai_client.analyze_folder_organization(folder_structure, artist_genres)

            # Step 7: Convert FolderInfo objects to dicts for signal emission
            folders_dict = [
                {
                    "path": str(fi.path),
                    "folder_type": fi.folder_type.value,
                    "artists": fi.artists,
                    "file_count": fi.file_count,
                    "suggested_name": fi.suggested_name
                }
                for fi in folders
            ]

            # Step 8: Emit final result
            analysis_result = {
                "moves": result.get("moves", []),
                "renames": result.get("renames", []),
                "folders": folders_dict
            }
            self.analysis_finished.emit(analysis_result)
            logger.info("OrganizeWorker completed successfully")

        except Exception as e:
            logger.error(f"OrganizeWorker error: {e}")
            self.error.emit(str(e))

    def _build_folder_structure(self, folders: list) -> dict[str, list[dict[str, str]]]:
        """Build folder_structure dict for AI analysis.

        Args:
            folders: List of FolderInfo objects.

        Returns:
            Dict mapping folder paths to lists of file metadata.
        """
        folder_structure: dict[str, list[dict[str, str]]] = {}

        # Get all files from cache
        conn = self._cache._get_connection()
        cursor = conn.execute(
            "SELECT path, artist FROM scan_cache WHERE artist IS NOT NULL"
        )
        file_data = {row["path"]: row["artist"] for row in cursor.fetchall()}

        # Group files by parent directory
        files_by_dir: dict[str, list[dict[str, str]]] = {}
        for file_path, artist in file_data.items():
            parent_dir = str(Path(file_path).parent)
            if parent_dir not in files_by_dir:
                files_by_dir[parent_dir] = []
            files_by_dir[parent_dir].append({
                "file": Path(file_path).name,
                "artist": artist
            })

        # Build folder_structure for folders needing action
        for folder_info in folders:
            if folder_info.folder_type in (FolderType.MISNAMED_ARTIST, FolderType.MIXED):
                folder_path = str(folder_info.path)
                folder_structure[folder_path] = files_by_dir.get(folder_path, [])

        return folder_structure