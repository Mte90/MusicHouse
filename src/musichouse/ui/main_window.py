"""Main window for MusicHouse application."""

import threading
from pathlib import Path
from typing import Optional, List, Dict

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QToolBar, QStatusBar, QLabel, QProgressBar,
    QTabWidget, QPushButton, QFileDialog, QMessageBox,
    QStyle
)

from musichouse import logging
from musichouse import config
from musichouse.scanner import MP3Scanner
from musichouse.leaderboard import Leaderboard
from musichouse.ui.fixer_tab import FixerTab
from musichouse.ui.leaderboard_tab import LeaderboardTab
from musichouse.ui.ai_tab import AITab
from musichouse.ui.settings_dialog import SettingsDialog

logger = logging.get_logger(__name__)


class ScanWorker(QThread):
    """Worker thread for scanning directories.
    
    CRITICAL:
    - Uses threading.Event for pause/resume without freezing
    - Emits signals for all UI updates (never access UI directly)
    - All UI interactions happen via signal/slot in main thread
    """
    
    # Signals for communicating with main thread
    progress = pyqtSignal(str)  # Progress message (e.g., "Scanning: /path" or "Reading tags: 5000/12000")
    directory_scanned = pyqtSignal(str, int)  # (directory_path, file_count)
    file_processed = pyqtSignal(int)  # Total files processed
    scan_finished = pyqtSignal(list, dict)  # (files_list, artist_counts)
    error = pyqtSignal(str)  # Error message
    artist_count_updated = pyqtSignal(str, int)  # (artist_name, count) - emitted when artist count changes during scan
    file_needs_fix = pyqtSignal(dict)  # Emit when a file needs fixing during scan (real-time)
    db_update_request = pyqtSignal(list)  # Request main thread to update DB
    tag_read_progress = pyqtSignal(int, int)  # (current, total) - progress during tag reading
    scan_stats = pyqtSignal(int, int, int)  # (new_count, modified_count, skipped_count)
    
    def __init__(self, base_path: Path):
        super().__init__()
        self.base_path = base_path
        self._pause_event = threading.Event()
        self._pause_event.set()  # Start in resume state
        self._stop_requested = False
        self._scanner: Optional[MP3Scanner] = None
        self._leaderboard: Optional[Leaderboard] = None
        self._artist_counts: Dict[str, int] = {}  # Track artist counts for real-time updates
        self._files_found: List[Path] = []
        self._artist_counts: Dict[str, int] = {}
    def run(self) -> None:
        """Execute the scan in worker thread.
        
        CRITICAL:
        - FIRST finds MP3 files (fast filesystem scan)
        - THEN reads ID3 tags (slow, shows progress)
        - Uses incremental scanning to skip unchanged files
        """
        logger.info(f"Starting scan of {self.base_path}")
        
        try:
            # Initialize scanner
            self._scanner = MP3Scanner(self.base_path)
            
            # Set up callbacks that emit signals
            def on_directory(dir_path: str):
                self.progress.emit(f"Scanning: {dir_path}")
            
            def on_file_batch(file_count: int):
                self.file_processed.emit(file_count)
            
            self._scanner.set_progress_callback(on_directory)
            self._scanner.set_file_callback(on_file_batch)
            
            # Phase 1: Perform filesystem scan - ONLY finds files, does NOT read tags
            self._files_found = self._scanner.scan()
            errors = self._scanner.get_errors()
            
            if errors:
                for err_path, err_msg in errors:
                    logger.warning(f"Error scanning {err_path}: {err_msg}")
            
            logger.info(f"Scan complete: {len(self._files_found)} files found")
            
            # Phase 1.5: Incremental filtering - get only changed files
            from musichouse.leaderboard_cache import LeaderboardCache
            cache = LeaderboardCache()
            changed_files, new_count, modified_count, skipped_count = cache.get_changed_files(self.base_path)
            
            # Emit scan statistics
            self.scan_stats.emit(new_count, modified_count, skipped_count)
            logger.info(f"Incremental scan: {new_count} new, {modified_count} modified, {skipped_count} skipped")
            
            # If no files changed, skip tag reading
            if not changed_files:
                logger.info("No files changed, skipping tag reading")
                cache.close()
                self.progress.emit("No changes detected")
                self.scan_finished.emit([], {})
                return
            
            # Filter to only changed files for tag reading
            files_to_process = changed_files
            total_files = len(files_to_process)
            
            # Phase 2: Read ID3 tags, update cache, and emit real-time fixes in single pass
            if total_files > 0:
                self.progress.emit(f"Processing: 0/{total_files} files")
                
                # Single loop: read tags + update cache + emit file_needs_fix signals
                files_info = []
                for i, file_path in enumerate(files_to_process, 1):
                    # Check for stop
                    if self._stop_requested:
                        logger.info("Scan stopped by user")
                        break
                    
                    try:
                        audio_file = eyed3.load(str(file_path))
                        artist = getattr(audio_file.tag, 'artist', None) if audio_file and audio_file.tag else None
                        title = getattr(audio_file.tag, 'title', None) if audio_file and audio_file.tag else None
                        stat = file_path.stat()
                        files_info.append({
                            'path': str(file_path),
                            'size': stat.st_size,
                            'mtime': stat.st_mtime,
                            'artist': artist,
                            'title': title
                        })
                        
                        # Emit file_needs_fix signal for real-time UI update
                        if artist is None or title is None:
                            from musichouse.parser import parse_filename
                            suggested_artist, suggested_title = parse_filename(file_path.name)
                            self.file_needs_fix.emit({
                                'path': str(file_path),
                                'filename': file_path.name,
                                'existing_artist': artist or "",
                                'existing_title': title or "",
                                'suggested_artist': suggested_artist,
                                'suggested_title': suggested_title,
                                'missing_artist': artist is None,
                                'missing_title': title is None,
                            })
                    except Exception:
                        # Include failed files with None values
                        stat = file_path.stat()
                        files_info.append({
                            'path': str(file_path),
                            'size': stat.st_size,
                            'mtime': stat.st_mtime,
                            'artist': None,
                            'title': None
                        })
                        # Emit as needing fix
                        from musichouse.parser import parse_filename
                        suggested_artist, suggested_title = parse_filename(file_path.name)
                        self.file_needs_fix.emit({
                            'path': str(file_path),
                            'filename': file_path.name,
                            'existing_artist': "",
                            'existing_title': "",
                            'suggested_artist': suggested_artist,
                            'suggested_title': suggested_title,
                            'missing_artist': True,
                            'missing_title': True,
                        })
                    
                    # Update progress every 10 files
                    if i % 10 == 0 or i == total_files:
                        self.progress.emit(f"Processing: {i}/{total_files} files")
                        self.tag_read_progress.emit(i, total_files)
                
                # Update cache with new tag info
                cache.update_scan_cache(files_info)
                logger.info("Cache updated")
            
            cache.close()
            # Emit scan finished signal with file paths and artist counts
            self.scan_finished.emit(files_to_process, self._artist_counts)
            
        except Exception as e:
            logger.error(f"Scan error: {e}")
            self.error.emit(f"Scan failed: {str(e)}")
        finally:
            self._scanner = None
    def _read_tags_with_progress(self, total_files: int, files_list: Optional[List[Path]] = None) -> None:
        """Read ID3 tags from all files with progress emission.
        
        CRITICAL:
        - Emits tag_read_progress signal every 100 files
        - Allows UI to show real progress during tag reading
        - files_list: Optional list of files to process (for incremental scan)
        """
        import eyed3
        import logging
        # Suppress eyed3 debug/warning messages
        eyed3_logger = logging.getLogger('eyed3')
        eyed3_logger.setLevel(logging.ERROR)
        eyed3_logger.propagate = False
        
        # Use provided files or default to all found files
        files_to_read = files_list if files_list is not None else self._files_found

        for i, file_path in enumerate(files_to_read, 1):
            # Check for stop
            if self._stop_requested:
                logger.info("Tag reading stopped by user")
                break

            # Check for pause - BLOCK here until resumed
            while not self._pause_event.is_set():
                # Thread is paused, wait for resume signal
                self._pause_event.wait()
                # If stop requested while paused, exit immediately
                if self._stop_requested:
                    logger.info("Stopped while paused")
                    return
            # Resume detected, continue to next file

            try:
                # Read tag (non-blocking, just parsing metadata)
                audio_file = eyed3.load(str(file_path))
                # Fix: Access tags safely via audio_file.tag with getattr()
                artist = None
                title = None
                if audio_file and audio_file.tag:
                    artist = getattr(audio_file.tag, 'artist', None)
                    title = getattr(audio_file.tag, 'title', None)
                    # Update artist count for real-time leaderboard
                    if artist:
                        self._artist_counts[artist] = self._artist_counts.get(artist, 0) + 1
                        self.artist_count_updated.emit(artist, self._artist_counts[artist])
                
                # Check if file needs fixing (missing artist or title)
                if artist is None or title is None:
                    # Parse filename for suggestions
                    from musichouse.parser import parse_filename
                    suggested_artist, suggested_title = parse_filename(file_path.name)
                    # Emit signal for real-time FixerTab update
                    self.file_needs_fix.emit({
                        'path': str(file_path),
                        'filename': file_path.name,
                        'existing_artist': artist or "",
                        'existing_title': title or "",
                        'suggested_artist': suggested_artist,
                        'suggested_title': suggested_title,
                        'missing_artist': artist is None,
                        'missing_title': title is None,
                    })
            except Exception:
                # Silently handle tag read errors - file will be marked as needing fixing
                from musichouse.parser import parse_filename
                suggested_artist, suggested_title = parse_filename(file_path.name)
                self.file_needs_fix.emit({
                    'path': str(file_path),
                    'filename': file_path.name,
                    'existing_artist': "",
                    'existing_title': "",
                    'suggested_artist': suggested_artist,
                    'suggested_title': suggested_title,
                    'missing_artist': True,
                    'missing_title': True,
                })
            
            # Emit progress every 10 files for smoother UI updates
            if i % 10 == 0:
                self.tag_read_progress.emit(i, total_files)
                self.progress.emit(f"Reading tags: {i}/{total_files}")
        
        # Emit final progress for all files (including non-100 multiples)
        self.tag_read_progress.emit(total_files, total_files)
        self.progress.emit(f"Reading tags: {total_files}/{total_files} - Complete!")

    def pause(self) -> None:
        """Pause the scan."""
        logger.debug("Scan PAUSE requested - clearing event")
        self._pause_event.clear()
        logger.debug("Pause event cleared - worker will block on wait()")

    def resume(self) -> None:
        """Resume the scan."""
        logger.debug("Scan RESUME requested - setting event")
        self._pause_event.set()
        logger.debug("Resume event set - worker can continue")

    def stop(self) -> None:
        """Stop the scan."""
        logger.debug("Scan stop requested")
        self._stop_requested = True
        self._pause_event.set()  # Ensure it doesn't wait if stopped
        # Stop the scanner if it exists
        if self._scanner:
            self._scanner.stop()
    
    def is_paused(self) -> bool:
        """Check if scan is paused."""
        return not self._pause_event.is_set()


class MainWindow(QMainWindow):
    """Main window for MusicHouse application.
    
    CRITICAL:
    - All UI operations happen in main thread
    - ScanWorker communicates via signals only
    - DB updates happen via signal/request pattern
    """
    
    def __init__(self):
        super().__init__()
        self._scan_worker: Optional[ScanWorker] = None
        self._leaderboard: Optional[Leaderboard] = None
        self._artist_counts: Dict[str, int] = {}  # Track artist counts for real-time updates
        self._artist_update_counter: int = 0  # Counter to throttle leaderboard updates
        self._file_update_counter: int = 0  # Counter to throttle FixerTab updates
        # Load last scan directory from config
        last_dir = config.get_last_directory()
        self._last_scan_path: Optional[Path] = Path(last_dir) if last_dir else None
        self._is_scanning = False
        self._scan_stats_summary: Optional[Tuple[int, int, int]] = None
        self._last_scan_path: Optional[Path] = Path(last_dir) if last_dir else None
        self._is_scanning = False
        self._scan_stats_summary: Optional[Tuple[int, int, int]] = None
        self._setup_ui()
        self._connect_signals()
        logger.info("MainWindow initialized")
    
    def _setup_ui(self) -> None:
        """Set up the main window UI."""
        self.setWindowTitle("MusicHouse")
        self.setMinimumSize(800, 600)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Toolbar
        self._setup_toolbar()
        
        # Status bar
        self._setup_statusbar()
        
        # Progress bar
        self._setup_progress_bar()
        
        # Tab widget
        self._setup_tabs()
        
        # Layout
        main_layout.addWidget(self._toolbar_widget)
        main_layout.addWidget(self._status_label)
        main_layout.addWidget(self._progress_bar)
        main_layout.addWidget(self._tab_widget)
    
    def _setup_toolbar(self) -> None:
        """Set up the toolbar."""
        self._toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout(self._toolbar_widget)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        # Scan button
        self._scan_btn = QPushButton("Scan")
        self._scan_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        self._scan_btn.clicked.connect(self._start_scan)
        toolbar_layout.addWidget(self._scan_btn)
        
        # Settings button
        self._settings_btn = QPushButton("Settings")
        self._settings_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self._settings_btn.clicked.connect(self._open_settings)
        toolbar_layout.addWidget(self._settings_btn)
        
        # Pause/Resume button
        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self._pause_btn.clicked.connect(self._toggle_pause)
        self._pause_btn.setEnabled(False)
        toolbar_layout.addWidget(self._pause_btn)
        toolbar_layout.addStretch()
    
    def _setup_statusbar(self) -> None:
        """Set up the status bar."""
        self._status_label = QLabel("Ready")
        self._status_label.setFixedHeight(25)
    
    def _setup_progress_bar(self) -> None:
        """Set up the progress bar."""
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)  # Default range, will be updated during tag reading
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
    def _setup_tabs(self) -> None:
        """Set up the tab widget."""
        self._tab_widget = QTabWidget()
        
        # Fixer tab
        self._fixer_tab = FixerTab()
        self._tab_widget.addTab(self._fixer_tab, "Fixer")
        
        # Leaderboard tab
        self._leaderboard_tab = LeaderboardTab()
        self._tab_widget.addTab(self._leaderboard_tab, "Leaderboard")
        
        # AI tab
        self._ai_tab = AITab()
        self._tab_widget.addTab(self._ai_tab, "AI Suggestions")
    
    def _connect_signals(self) -> None:
        """Connect signals from ScanWorker to slots."""
        # Note: Signals are connected when worker is created
        # This is done in _start_scan to ensure worker exists
        pass
    
    def _start_scan(self) -> None:
        """Start scanning a directory."""
        # Select directory
        # Use last directory from config as default
        last_dir = config.get_last_directory() or str(Path.home())
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select directory to scan",
            last_dir
        )
        
        if not directory:
            return
        
        # Save selected directory for next time
        config.set_last_directory(directory)
        
        self._last_scan_path = Path(directory)
        self._is_scanning = True
        
        # Update UI
        self._status_label.setText(f"Scanning: {directory}")
        self._progress_bar.setVisible(True)
        self._scan_btn.setEnabled(False)
        self._pause_btn.setEnabled(True)
        self._pause_btn.setText("Pause")
        
        # Initialize leaderboard
        self._leaderboard = Leaderboard()
        
        # Create and start worker
        self._scan_worker = ScanWorker(Path(directory))
        # Reset artist counts for new scan
        self._artist_counts = {}
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.directory_scanned.connect(self._on_directory_scanned)
        self._scan_worker.file_processed.connect(self._on_file_processed)
        self._scan_worker.scan_finished.connect(self._on_scan_finished)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.artist_count_updated.connect(self._on_artist_count_updated)
        self._scan_worker.file_needs_fix.connect(self._on_file_needs_fix)
        self._scan_worker.db_update_request.connect(self._on_db_update_request)
        self._scan_worker.tag_read_progress.connect(self._on_tag_read_progress)
        self._scan_worker.scan_stats.connect(self._on_scan_stats)
        
        self._scan_worker.start()
        logger.info(f"Scan started for {directory}")
    
    def _toggle_pause(self) -> None:
        """Toggle pause/resume of scan."""
        if not self._scan_worker:
            return
        
        if self._scan_worker.is_paused():
            self._scan_worker.resume()
            self._pause_btn.setText("Pause")
            self._pause_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
            self._status_label.setText("Scanning (resumed)")
            logger.debug("Scan resumed")
        else:
            self._scan_worker.pause()
            self._pause_btn.setText("Resume")
            self._pause_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self._status_label.setText("Scan paused")
            logger.debug("Scan paused")
    
    def _stop_scan(self) -> None:
        """Stop the current scan."""
        if not self._scan_worker:
            return
        
        self._scan_worker.stop()
        self._scan_worker.wait()  # Wait for thread to finish
        self._scan_worker = None
        self._is_scanning = False
        
        # Reset UI
        self._scan_btn.setEnabled(True)
        self._pause_btn.setEnabled(False)
        self._pause_btn.setText("Pause")
        self._status_label.setText("Scan stopped")
        logger.info("Scan stopped")
    
    def _open_settings(self) -> None:
        """Open settings dialog."""
        dialog = SettingsDialog(self)
        dialog.exec()
        logger.info("Settings opened")
    
    # Signal handlers (all run in main thread)
    
    def _on_scan_progress(self, message: str) -> None:
        """Handle progress update from scan worker."""
        self._status_label.setText(message)

    def _on_directory_scanned(self, directory: str, file_count: int) -> None:
        """Handle directory scanned event."""
        logger.debug(f"Directory scanned: {directory} ({file_count} files)")

    def _on_file_processed(self, file_count: int) -> None:
        """Handle file processed event during filesystem scan."""
        # Only update if not in tag reading phase
        if not self._status_label.text().startswith("Reading tags"):
            self._status_label.setText(f"Scanned {file_count} files")

    def _on_tag_read_progress(self, current: int, total: int) -> None:
        """Handle tag reading progress update."""
        self._status_label.setText(f"Reading tags: {current}/{total}")
        # Update progress bar with real progress
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(current)
    def _on_scan_stats(self, new_count: int, modified_count: int, skipped_count: int) -> None:
        """Handle scan statistics from incremental scan."""
        self._scan_stats_summary = (new_count, modified_count, skipped_count)
        if skipped_count > 0:
            self._status_label.setText(
                f"Incremental: {new_count} new, {modified_count} modified, {skipped_count} skipped"
            )
        else:
            self._status_label.setText(f"Found {new_count + modified_count} files to process")
    def _on_scan_finished(self, files: List[Path], artist_counts: Dict[str, int]) -> None:
        """Handle scan completion."""
        logger.info(f"Scan finished: {len(files)} files, {len(artist_counts)} artists")
        
        # Update UI
        self._is_scanning = False
        self._scan_btn.setEnabled(True)
        self._pause_btn.setEnabled(False)
        self._pause_btn.setText("Pause")
        # Show final status with statistics if available
        if self._scan_stats_summary:
            new_count, modified_count, skipped_count = self._scan_stats_summary
            total = new_count + modified_count + skipped_count
            if skipped_count > 0:
                self._status_label.setText(
                    f"Scan complete: {len(files)} files processed "
                    f"({new_count} new, {modified_count} modified, {skipped_count} skipped)"
                )
            else:
                self._status_label.setText(f"Scan complete: {len(files)} files found")
        else:
            self._status_label.setText(f"Scan complete: {len(files)} files found")
        
        # Populate fixer tab
        self._fixer_tab.load_from_scan(files, artist_counts)
        
        # Update leaderboard
        if self._leaderboard:
            top_artists = self._leaderboard.update_from_files(files)
            self._leaderboard_tab.update_leaderboard(top_artists)
        
        # Update AI tab artist list
        self._ai_tab.load_artists(list(artist_counts.keys()))
        
        self._progress_bar.setVisible(False)
    
    def _on_artist_count_updated(self, artist: str, count: int) -> None:
        """Handle artist count update during scan (throttled for UI performance)."""
        # Update local artist counts
        self._artist_counts[artist] = count
        # Throttle leaderboard updates to every 100 artist updates (prevents UI blocking)
        self._artist_update_counter += 1
        if self._artist_update_counter % 100 != 0:
            return  # Skip UI update
        # Update leaderboard every 100 updates
        if self._leaderboard:
            top_artists = self._leaderboard.update_from_artist_counts(self._artist_counts)
            self._leaderboard_tab.update_leaderboard(top_artists)
        # Note: AI tab dropdown will be updated on first show via load_artists()
        # We don't update it here to avoid disrupting user's current selection

    def _on_file_needs_fix(self, file_entry: dict) -> None:
        """Handle file scanned that needs fixing (throttled for UI performance)."""
        # ALWAYS save to DB (not throttled)
        self._save_file_to_db(file_entry)
        
        # Throttle FixerTab updates to every 50 files (prevents UI blocking)
        self._file_update_counter += 1
        if self._file_update_counter % 50 != 0:
            return  # Skip UI update
        # Add file to FixerTab every 50 updates
        self._fixer_tab.add_file_entry(file_entry)
    
    def _save_file_to_db(self, file_entry: dict) -> None:
        """Save file entry to database during scan."""
        try:
            from musichouse import config as app_config
            from musichouse.leaderboard_cache import LeaderboardCache
            import time
            
            cache = LeaderboardCache(app_config.get_config_dir())
            conn = cache._get_connection()
            
            # Get file stats
            import os
            stat = os.stat(file_entry['path'])
            
            # Insert/update scan_cache with needs_fixing = 1
            conn.execute(
                """INSERT OR REPLACE INTO scan_cache
                   (path, size, mtime, artist, title, scan_time,
                    needs_fixing, missing_artist, missing_title,
                    suggested_artist, suggested_title)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    file_entry['path'],
                    stat.st_size,
                    stat.st_mtime,
                    file_entry.get('existing_artist', ''),
                    file_entry.get('existing_title', ''),
                    time.time(),
                    1,  # needs_fixing = 1
                    1 if file_entry.get('missing_artist') else 0,
                    1 if file_entry.get('missing_title') else 0,
                    file_entry.get('suggested_artist', ''),
                    file_entry.get('suggested_title', ''),
                )
            )
            conn.commit()
            # Force WAL checkpoint to ensure data is written to main DB
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            cache.close()
        except Exception as e:
            logger.error(f"Error saving file to DB: {e}")

    def _on_scan_error(self, error_msg: str) -> None:
        """Handle scan error."""
        logger.error(f"Scan error: {error_msg}")
        self._is_scanning = False
        self._scan_btn.setEnabled(True)
        self._pause_btn.setEnabled(False)
        self._pause_btn.setText("Pause")
        self._status_label.setText("Error")
        QMessageBox.critical(self, "Scan Error", error_msg)
        self._progress_bar.setVisible(False)
    
    def _on_db_update_request(self, files: List[Path]) -> None:
        """Handle DB update request from worker.
        
        This runs in main thread, safe to update UI and DB.
        """
        logger.debug(f"DB update request for {len(files)} files")
        # DB update is already handled in _on_scan_finished via leaderboard.update_from_files
        # This signal is available for future extensions
    
    def closeEvent(self, event):
        """Handle window close."""
        if self._is_scanning and self._scan_worker:
            reply = QMessageBox.question(
                self,
                "Scan in Progress",
                "Scan is still running. Stop and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self._stop_scan()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
        
        # Cleanup
        if self._leaderboard:
            self._leaderboard.reset()
            self._leaderboard = None
