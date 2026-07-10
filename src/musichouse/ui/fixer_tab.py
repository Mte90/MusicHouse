"""Fixer tab for MP3 tag correction in MusicHouse."""
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QComboBox, QPushButton, QHeaderView, QLabel, QProgressBar, QMessageBox, QVBoxLayout, QTextEdit, QLineEdit, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from musichouse.parser import parse_filename, get_artist_from_folder
from musichouse.utils import load_mp3_safely
from musichouse.ui.tag_fix_worker import TagFixWorker, TagUpdateWorker
from musichouse import config
from musichouse.leaderboard_cache import LeaderboardCache
from musichouse import log_setup as logging
from musichouse.error_handling import (
    CorruptedFileError, FileLockedError, ReadOnlyFileError, TagWriteError
)


logger = logging.get_logger(__name__)

class FixerTab(QWidget):
    """Tab for scanning and fixing MP3 tags."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._files_data: List[Dict[str, Any]] = []  # All entries must have "path" as Path object
        self._empty_label: Optional[QLabel] = None
        self._select_all_cb: Optional[QCheckBox] = None  # Header checkbox
        self._setup_ui()
        self._load_saved_files()
        self._setup_select_all_header()
        # T43: Track failure details with error types
        self._failure_details: List[Tuple[str, str, str]] = []  # (filename, error_type, error_message)

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Filter dropdown
        filter_layout = QHBoxLayout()
        filter_label = QLabel("Filter:")
        self._filter_combo = QComboBox()
        self._filter_combo.addItems(["All", "Missing Artist", "Missing Title", "Both"])
        self._filter_combo.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self._filter_combo)
        
        # Search input
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search files...")
        self._search_input.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(self._search_input)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Table widget - sorting DISABLED to prevent data corruption
        # When sorting is enabled, visual row indices don't match _files_data indices,
        # causing tags to be written to wrong files (critical bug)
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["", "File", "Artist", "Title"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        # Disable selection for the entire table (checkboxes don't need row selection)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.itemChanged.connect(self._on_item_changed)
        self._table.cellChanged.connect(self._on_cell_changed)
        self._table.setAlternatingRowColors(True)
        # CRITICAL: Disable sorting to prevent row index mismatch bug
        self._table.setSortingEnabled(False)
        self._table.itemChanged.connect(self._on_item_changed)
        self._table.cellChanged.connect(self._on_cell_changed)
        self._table.setAlternatingRowColors(True)
        
        layout.addWidget(self._table)
        
        # Empty state label
        self._empty_label = QLabel("No files to fix. Click 'Scan' to find problematic files.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: gray; font-style: italic;")
        self._empty_label.setVisible(False)
        layout.addWidget(self._empty_label)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._fix_selected_btn = QPushButton("Fix Selected")
        self._fix_selected_btn.clicked.connect(self.fix_selected)
        self._fix_selected_btn.setToolTip("Fix only the files you've selected with checkboxes. Use when you want to review and fix specific files.")
        
        self._fix_all_btn = QPushButton("Auto-Fix All")
        self._fix_all_btn.clicked.connect(self.auto_fix_all)
        self._fix_all_btn.setToolTip("Automatically fix ALL files without review. Uses suggested values from filename parsing for all missing tags.")

        button_layout.addWidget(self._fix_selected_btn)
        button_layout.addWidget(self._fix_all_btn)

        layout.addLayout(button_layout)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

    def load_from_scan(self, files: List[Path], artist_counts: Dict[str, int]):
        """Load files from a scan result.
        
        Loads from database instead of re-reading files to avoid blocking UI.
        
        Args:
            files: List of MP3 file paths (used to filter which files to load).
            artist_counts: Dictionary of artist name counts (for filtering).
        """
        # Load from database instead of re-reading files
        # The scan already read tags and stored them in scan_cache
        try:
            from musichouse import config as app_config
            from musichouse.leaderboard_cache import LeaderboardCache
            
            cache = LeaderboardCache(app_config.get_config_dir())
            conn = cache.query(
                """SELECT path, artist, title,
                       needs_fixing, missing_artist, missing_title,
                       suggested_artist, suggested_title
                 FROM scan_cache
                WHERE path IN ({})
                  AND needs_fixing = 1
                  AND (missing_artist = 1 OR missing_title = 1)""".format(
                    ','.join('?' * len(files))
                ),
                [str(f) for f in files]
            )
            
            # Get file paths as strings for SQL
            file_paths_str = [str(f) for f in files]
            if not file_paths_str:
                cache.close()
                return
            
            # Query for files that need fixing from the scan results
            placeholders = ','.join('?' * len(file_paths_str))
            cursor = conn.execute(
                f"""SELECT path, artist, title,
                       needs_fixing, missing_artist, missing_title,
                       suggested_artist, suggested_title
                  FROM scan_cache
                 WHERE path IN ({placeholders})
                   AND needs_fixing = 1
                   AND (missing_artist = 1 OR missing_title = 1)""",
                file_paths_str
            )
            
            self._files_data = []
            for row in cursor.fetchall():
                path = Path(row["path"])
                entry = {
                    "path": path,
                    "filename": path.name,
                    "existing_artist": row["artist"] or "",
                    "existing_title": row["title"] or "",
                    "suggested_artist": row["suggested_artist"] or "",
                    "suggested_title": row["suggested_title"] or "",
                    "missing_artist": bool(row["missing_artist"]),
                    "missing_title": bool(row["missing_title"]),
                }
                self._files_data.append(entry)
            
            cache.close()
            logger.info(f"Loaded {len(self._files_data)} files from scan cache (no file I/O)")
            
            self._apply_filter()
            self._update_empty_state(len(self._files_data) > 0)
        except Exception as e:
            logger.error(f"Error loading scan results from DB: {e}")
            # Fallback: clear data
            self._files_data = []
            self._apply_filter()
            self._update_empty_state(False)
    
    def _load_saved_files(self):
        """Load files with needs_fixing=1 from database on startup."""
        try:
            from musichouse import config as app_config
            from musichouse.leaderboard_cache import LeaderboardCache
            
            cache = LeaderboardCache(app_config.get_config_dir())
            cursor = cache.query(
                """SELECT path, artist, title,
                       needs_fixing, missing_artist, missing_title,
                       suggested_artist, suggested_title
                 FROM scan_cache
                WHERE needs_fixing = 1 AND (missing_artist = 1 OR missing_title = 1)"""
            )
            
            self._files_data = []
            for row in cursor.fetchall():
                path = Path(row["path"])  # Convert str to Path
                entry = {
                    "path": path,
                    "filename": path.name,
                    "existing_artist": row["artist"] or "",
                    "existing_title": row["title"] or "",
                    "suggested_artist": row["suggested_artist"] or "",
                    "suggested_title": row["suggested_title"] or "",
                    "missing_artist": bool(row["missing_artist"]),
                    "missing_title": bool(row["missing_title"]),
}
                self._files_data.append(entry)
            
            cache.close()
            
            if self._files_data:
                self._apply_filter()
                self._update_empty_state(True)
                logger.info(f"Loaded {len(self._files_data)} files needing fix from DB")
            else:
                self._update_empty_state(False)
        except Exception as e:
            logger.error(f"Error loading saved files from DB: {e}")
            self._update_empty_state(False)
    
    def _setup_select_all_header(self):
        """Add Select All checkbox to table header."""
        if not self._select_all_cb:
            # Create custom checkbox for header
            self._select_all_cb = QCheckBox("Select All")
            self._select_all_cb.stateChanged.connect(self._toggle_all_rows)
            
            # Set header clickable and connect section click
            header = self._table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionsClickable(True)
            header.sectionClicked.connect(self._on_header_clicked)
    
    def _on_header_clicked(self, logical_index: int):
        """Handle header click - toggle select all if first column clicked."""
        if logical_index == 0 and self._select_all_cb:
            # Toggle the header checkbox
            current_state = self._select_all_cb.checkState()
            new_state = Qt.CheckState.Unchecked if current_state == Qt.CheckState.Checked else Qt.CheckState.Checked
            self._select_all_cb.setCheckState(new_state)
            self._toggle_all_rows(new_state)
    
    def _toggle_all_rows(self, state):
        """Toggle all row checkboxes based on header checkbox state."""
        checked = state == Qt.CheckState.Checked
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
    
    def _update_header_checkbox_state(self):
        """Update header checkbox state based on row checkbox states."""
        if not self._select_all_cb:
            return
        
        # Check if all rows are checked
        all_checked = True
        any_checked = False
        
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item:
                if item.checkState() == Qt.CheckState.Checked:
                    any_checked = True
                else:
                    all_checked = False
        
        # Set header checkbox state
        if all_checked and any_checked:
            self._select_all_cb.setCheckState(Qt.CheckState.Checked)
        elif any_checked:
            # Some checked - use partial state (Unchecked for simplicity)
            self._select_all_cb.setCheckState(Qt.CheckState.Unchecked)
        else:
            self._select_all_cb.setCheckState(Qt.CheckState.Unchecked)
    
    def _load_file_entry(self, file_path: Path, artist_counts: Dict[str, int]) -> Optional[Dict]:
        """Load a single file entry."""
        audiofile = load_mp3_safely(file_path)

        if audiofile is None or audiofile.tag is None:
            return None

        existing_artist = audiofile.tag.artist or ""
        existing_title = audiofile.tag.title or ""

        # Parse filename for suggested fix (uses folder name if no hyphen)
        suggested_artist, suggested_title = parse_filename(file_path.name, file_path)
        
        # If suggested artist is a number, use folder name instead
        if suggested_artist.strip().isdigit():
            suggested_artist = get_artist_from_folder(file_path)
        # Determine if file needs fixing
        missing_artist = not existing_artist
        missing_title = not existing_title

        # Store entry with current and suggested values
        return {
            "path": file_path,
            "filename": file_path.name,
            "existing_artist": existing_artist,
            "existing_title": existing_title,
            "suggested_artist": suggested_artist,
            "suggested_title": suggested_title,
            "missing_artist": missing_artist,
            "missing_title": missing_title,
        }

    def add_file_entry(self, entry: Dict[str, Any]) -> None:
        """Add a single file entry to the table in real-time.
        
        Only adds the row if it passes the current filter (efficient - no table rebuild).
        
        Args:
            entry: Dict with path (must be Path object), filename, existing_artist, existing_title,
                   suggested_artist, suggested_title, missing_artist, missing_title.
        """
        # Ensure path is a Path object (convert string paths for consistency)
        if isinstance(entry["path"], str):
            entry["path"] = Path(entry["path"])
        
        # Add to internal data list
        self._files_data.append(entry)
        
        # Only add row if it passes the current filter (efficient - no table rebuild)
        filter_text = self._filter_combo.currentText()
        if self._should_show_entry(entry, filter_text):
            self._add_row_to_table(entry)

    def _apply_filter(self):
        """Apply the current filter to the table."""
        filter_text = self._filter_combo.currentText()
        search_pattern = self._search_input.text().lower()

        self._table.setRowCount(0)

        for entry in self._files_data:
            should_show = self._should_show_entry(entry, filter_text)
            # Also check search pattern
            if should_show and search_pattern:
                should_show = search_pattern in entry["filename"].lower()
            if should_show:
                self._add_row_to_table(entry)
        
        # Update empty state based on filtered results
        self._update_empty_state(self._table.rowCount() == 0)

    def _should_show_entry(self, entry: Dict, filter_text: str) -> bool:
        """Check if entry should be shown based on filter.
        
        CRITICAL: Only show entries that actually need fixing.
        """
        # First check: entry MUST have at least one missing tag
        if not (entry["missing_artist"] or entry["missing_title"]):
            return False  # Skip files with complete metadata
        
        # Then apply specific filter
        if filter_text == "All":
            return True  # Already filtered above, show all files needing fix
        elif filter_text == "Missing Artist":
            return entry["missing_artist"]
        elif filter_text == "Missing Title":
            return entry["missing_title"]
        elif filter_text == "Both":
            return entry["missing_artist"] and entry["missing_title"]
        return True

    def _filter_table(self, pattern: str):
        """Filter table rows by filename."""
        self._proxy_model.setFilterFixedString(pattern)

    def _add_row_to_table(self, entry: Dict):
        """Add a row to the table."""
        row = self._table.rowCount()
        self._table.insertRow(row)

        # Checkbox
        checkbox_item = QTableWidgetItem()
        # Enable both selection and checking
        checkbox_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
        checkbox_item.setCheckState(Qt.CheckState.Unchecked)
        self._table.setItem(row, 0, checkbox_item)

        # File name with tooltip showing full path
        filename_item = QTableWidgetItem(entry["filename"])
        filename_item.setToolTip(str(entry["path"]))  # Show full path on hover
        self._table.setItem(row, 1, filename_item)

        # Artist: show existing, or suggested if missing
        artist_display = entry["existing_artist"] if entry["existing_artist"] else entry["suggested_artist"]
        artist_item = QTableWidgetItem(artist_display)
        artist_item.setFlags(artist_item.flags() | Qt.ItemFlag.ItemIsEditable)
        if entry["missing_artist"]:
            artist_item.setForeground(Qt.GlobalColor.red)
        self._table.setItem(row, 2, artist_item)

        # Title: show existing, or suggested if missing
        title_display = entry["existing_title"] if entry["existing_title"] else entry["suggested_title"]
        title_item = QTableWidgetItem(title_display)
        title_item.setFlags(title_item.flags() | Qt.ItemFlag.ItemIsEditable)
        if entry["missing_title"]:
            title_item.setForeground(Qt.GlobalColor.red)
        self._table.setItem(row, 3, title_item)

    def _get_checked_rows(self) -> set:
        """Get set of row indices that are checked."""
        checked = set()
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                checked.add(row)
        return checked

    def _set_all_checkboxes(self, checked: bool):
        """Set all checkboxes to the given state."""
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item:
                item.setCheckState(state)

    def get_selected_files(self) -> List[Path]:
        """Get list of selected file paths (from checkboxes)."""
        checked_rows = self._get_checked_rows()
        if not checked_rows:
            return []

        return [self._files_data[row]["path"] for row in checked_rows]

    def _on_item_changed(self, item: QTableWidgetItem):
        """Handle item changes (e.g., checkbox toggling)."""
        # Header click detection - column 0 header click toggles all checkboxes
        pass

    def _on_cell_changed(self, row: int, column: int):
        """Handle cell editing."""
        if column == 2:  # Artist column
            self._files_data[row]["existing_artist"] = self._table.item(row, 2).text()
        elif column == 3:  # Title column
            self._files_data[row]["existing_title"] = self._table.item(row, 3).text()

    def fix_selected(self) -> None:
        """Apply fixes to selected files using worker thread."""
        checked_rows = sorted(self._get_checked_rows())
        if not checked_rows:
            return
        
        # Prepare files data with current table values
        files_to_fix = []
        for row in checked_rows:
            entry = self._files_data[row].copy()
            # Get current values from table (may have been edited)
            artist_item = self._table.item(row, 2)
            title_item = self._table.item(row, 3)
            entry["current_artist"] = artist_item.text() if artist_item else entry["suggested_artist"]
            entry["current_title"] = title_item.text() if title_item else entry["suggested_title"]
            files_to_fix.append(entry)
        
        # Create and configure worker
        self._worker = TagFixWorker(files_to_fix, auto_fix=False)
        self._worker.progress.connect(self._on_fix_progress)
        self._worker.file_fixed.connect(self._on_file_fixed)
        self._worker.failures.connect(self._on_failures)
        self._worker.finished.connect(self._on_fix_finished)
        
        # Store fixed paths for DB update
        self._fixed_paths: List[Path] = []
        self._failed_paths: List[Path] = []
        self._failure_details: List[Tuple[str, str]] = []  # (filename, error_message)
        
        # Update UI
        self._set_buttons_enabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setMaximum(len(files_to_fix))
        self._progress_bar.setValue(0)
        
        # Start worker
        self._worker.start()
    
    def auto_fix_all(self) -> None:
        """Apply fixes to all files using worker thread."""
        import time
        start_time = time.perf_counter()
        
        if not self._files_data:
            return
        
        # Prepare files data with current table values (same as fix_selected)
        files_to_fix = []
        for row in range(self._table.rowCount()):
            entry = self._files_data[row].copy()
            # Get current values from table (may have been edited)
            artist_item = self._table.item(row, 2)
            title_item = self._table.item(row, 3)
            entry["current_artist"] = artist_item.text() if artist_item else entry["suggested_artist"]
            entry["current_title"] = title_item.text() if title_item else entry["suggested_title"]
            files_to_fix.append(entry)
        
        # Create and configure worker
        self._worker = TagFixWorker(files_to_fix, auto_fix=True)
        self._worker.progress.connect(self._on_fix_progress)
        self._worker.file_fixed.connect(self._on_file_fixed)
        self._worker.failures.connect(self._on_failures)
        self._worker.finished.connect(self._on_fix_finished)
        
        # Store fixed paths for DB update
        self._fixed_paths: List[Path] = []
        self._failed_paths: List[Path] = []
        self._failure_details: List[Tuple[str, str]] = []  # (filename, error_message)
        
        # Update UI
        self._set_buttons_enabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setMaximum(len(self._files_data))
        self._progress_bar.setValue(0)
        
        # Store start time for duration logging
        self._fix_start_time = start_time
        
        # Start worker
        self._worker.start()
    
    def _set_buttons_enabled(self, enabled: bool):
        """Enable or disable fix buttons."""
        self._fix_selected_btn.setEnabled(enabled)
        self._fix_all_btn.setEnabled(enabled)
    
    def _on_fix_progress(self, index: int, filename: str):
        """Handle progress signal from worker."""
        self._progress_bar.setValue(index + 1)
    
    def _on_file_fixed(self, filename: str, success: bool, error_type: Optional[str] = None):
        """Handle file_fixed signal from worker.
        
        Args:
            filename: Name of the file that was processed.
            success: True if file was fixed successfully.
            error_type: Error type if failed (e.g., "corrupted", "deleted", "locked", "readonly").
        """
        if success:
            # Find the path for this filename
            for entry in self._files_data:
                if entry["filename"] == filename:
                    path = entry["path"] if isinstance(entry["path"], Path) else Path(entry["path"])
                    self._fixed_paths.append(path)
                    break
        else:
            # Find the path for this filename
            for entry in self._files_data:
                if entry["filename"] == filename:
                    path = entry["path"] if isinstance(entry["path"], Path) else Path(entry["path"])
                    self._failed_paths.append(path)
                    break
    
    def _on_failures(self, failures: List[Tuple[str, str, str]]):
        """Handle failures signal from worker - collect failure details with error types.
        
        Args:
            failures: List of (filename, error_type, error_message) tuples.
        """
        self._failure_details.extend(failures)
    
    def _show_failure_summary(self, failures: List[Tuple[str, str, str]], success_count: int):
        """Show a non-modal summary dialog with failure details grouped by error type.
        
        Args:
            failures: List of (filename, error_type, error_message) tuples.
            success_count: Number of successfully fixed files.
        """
        failure_count = len(failures)
        
        # Create summary message
        summary_text = f"<b>Fix Complete</b><br/>"
        summary_text += f"Fixed: {success_count} files<br/>"
        summary_text += f"Failed: {failure_count} files"
        
        if failure_count == 0:
            # No failures - show simple success message
            msg = QMessageBox(self)
            msg.setWindowTitle("Fix Complete")
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText(f"Successfully fixed {success_count} files.")
            msg.exec()
            return
        
        # Create custom dialog for failures
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QTextEdit, QLabel
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Fix Complete - Some Files Failed")
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Summary label
        summary_label = QLabel(summary_text)
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)
        
        # T43: Group failures by error type
        layout.addWidget(QLabel("<b>Failed Files by Error Type:</b>"))
        failure_text = QTextEdit()
        failure_text.setReadOnly(True)
        failure_text.setMinimumHeight(200)
        
        # Group by error type
        error_groups: Dict[str, List[Tuple[str, str]]] = {}
        for filename, error_type, error_msg in failures:
            if error_type not in error_groups:
                error_groups[error_type] = []
            error_groups[error_type].append((filename, error_msg))
        
        # Format grouped failures
        error_type_labels = {
            "corrupted": "🔴 Corrupted Files",
            "deleted": "📁 File No Longer Exists",
            "locked": "🔒 File Locked",
            "readonly": "🔐 Read-Only File",
            "write_error": "⚠️ Write Error"
        }
        
        failure_html = []
        for error_type, files in error_groups.items():
            label = error_type_labels.get(error_type, f"{error_type.title()} Errors")
            failure_html.append(f"<h4>{label}</h4><ul>")
            for filename, error_msg in files:
                failure_html.append(f"<li><b>{filename}</b>: {error_msg}</li>")
            failure_html.append("</ul>")
        
        failure_text.setHtml("<br/>".join(failure_html))
        layout.addWidget(failure_text)
        
        # OK button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        
        # Show dialog (non-modal since it's a QDialog with parent)
        dialog.exec()
    
    def _on_fix_finished(self, success_count: int, failure_count: int):
        """Handle finished signal from worker."""
        # Update DB for fixed files
        if self._fixed_paths:
            self._update_db_after_fix(self._fixed_paths)
        
        # Remove fixed files from table
        if self._fixed_paths:
            self._remove_fixed_rows(self._fixed_paths)
        
        # If auto-fix all, clear everything
        if self._worker._auto_fix and self._files_data:
            self._files_data = []
            self._table.setRowCount(0)
        
        # Show failure summary if there were failures
        if self._failure_details:
            self._show_failure_summary(self._failure_details, success_count)
        
        # Mark failed rows in the table with red background
        for failed_path in self._failed_paths:
            self._mark_failed_row(failed_path)
        
        # Reset UI
        self._progress_bar.setVisible(False)
        self._set_buttons_enabled(True)
        
        # Log summary
        if failure_count > 0:
            logger.warning(f"Fix complete: {success_count} succeeded, {failure_count} failed")
        else:
            logger.info(f"Fix complete: {success_count} files fixed")
    
    def _mark_failed_row(self, failed_path: Path, error_type: Optional[str] = None):
        """Mark a failed row in the table with a color based on error type.
        
        Args:
            failed_path: Path of the failed file.
            error_type: Type of error ("corrupted", "deleted", "locked", "readonly").
        """
        failed_path_str = str(failed_path)
        
        # T40/T41/T42/T43: Different colors for different error types
        color_map = {
            "corrupted": QColor(255, 100, 100),  # Bright red for corrupted
            "deleted": QColor(200, 200, 200),     # Gray for deleted
            "locked": QColor(255, 200, 0),        # Orange for locked
            "readonly": QColor(200, 100, 255),    # Purple for readonly
        }
        bg_color = color_map.get(error_type, QColor(255, 200, 200))  # Default light red
        
        # Find the row in the table that matches this path
        for row in range(self._table.rowCount()):
            filename_item = self._table.item(row, 1)
            if filename_item:
                # Find the entry in _files_data that matches this row
                # We need to match by filename since the table is filtered
                entry_filename = filename_item.text()
                for entry in self._files_data:
                    if entry["filename"] == entry_filename and str(entry["path"]) == failed_path_str:
                        # Apply colored background to all cells in this row
                        for col in range(self._table.columnCount()):
                            item = self._table.item(row, col)
                            if item:
                                item.setBackground(bg_color)
                        
                        # T40: Add error label for corrupted files
                        if error_type == "corrupted":
                            filename_item.setForeground(QColor(255, 0, 0))  # Red text
                            filename_item.setToolTip("Corrupted file - cannot read MP3 data")
                        elif error_type == "deleted":
                            filename_item.setToolTip("File no longer exists")
                        elif error_type == "locked":
                            filename_item.setToolTip("File is locked by another process")
                        elif error_type == "readonly":
                            filename_item.setToolTip("File is read-only")
                        break
    
    def _update_db_after_fix(self, fixed_paths: List[Path]) -> None:
        """Update database to mark files as fixed."""
        try:
            cache = LeaderboardCache(config.get_config_dir())
            conn = cache._get_connection()
            for path in fixed_paths:
                conn.execute(
                    "UPDATE scan_cache SET needs_fixing = 0, missing_artist = 0, missing_title = 0 WHERE path = ?",
                    (str(path),)
                )
            # WAL checkpoint in PASSIVE mode to avoid blocking GUI thread.
            # TRUNCATE forces fsync and can freeze UI; PASSIVE checkpoints what's safe
            # without blocking. SQLite will checkpoint naturally otherwise.
            conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            cache.close()
            logger.info(f"Updated DB for {len(fixed_paths)} fixed files")
        except Exception as e:
            logger.error(f"Error updating DB after fix: {e}")
    
    def closeEvent(self, a0):
        """Handle tab close - cancel worker if running."""
        if hasattr(self, '_worker') and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()
        a0.accept()
    def _remove_fixed_rows(self, fixed_paths: List[Path]) -> None:
        """Remove fixed rows from the table (in reverse order to preserve indices)."""
        # Find row indices that match the fixed paths
        rows_to_remove = []
        # Convert fixed_paths to set of strings for efficient comparison
        fixed_paths_str = {str(p) for p in fixed_paths}
        for i, entry in enumerate(self._files_data):
            # Compare as strings to handle both Path and str entries
            if str(entry["path"]) in fixed_paths_str:
                rows_to_remove.append(i)

        # Remove from _files_data in reverse order to preserve indices
        for data_index in sorted(rows_to_remove, reverse=True):
            del self._files_data[data_index]

        # Rebuild the table (proxy model will handle sorting automatically)
        self._table.setRowCount(0)
        for entry in self._files_data:
            self._add_row_to_table(entry)
        
        # Update empty state
        self._update_empty_state(self._table.rowCount() == 0)
    
    def _update_empty_state(self, has_data: bool) -> None:
        """Show/hide empty state label."""
        if self._empty_label:
            self._empty_label.setVisible(not has_data)
    
