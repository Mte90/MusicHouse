"""Fixer tab for MP3 tag correction in MusicHouse."""
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QComboBox, QPushButton, QHeaderView, QLabel
)
from PyQt6.QtCore import Qt

from musichouse.parser import parse_filename
from musichouse.utils import load_mp3_safely
from musichouse.tag_writer import write_tags
from musichouse import config
from musichouse.leaderboard_cache import LeaderboardCache
from musichouse import logging as app_logging


logger = app_logging.get_logger(__name__)

def _tags_already_exist(file_path: Path, artist: str, title: str) -> bool:
    """Check if file already has the target artist and title tags.

    Args:
        file_path: Path to the MP3 file.
        artist: Expected artist name.
        title: Expected title.

    Returns:
        True if tags already match the target values.
    """
    try:
        audiofile = load_mp3_safely(file_path)
        if audiofile is None or audiofile.tag is None:
            return False
        existing_artist = getattr(audiofile.tag, 'artist', None) or ''
        existing_title = getattr(audiofile.tag, 'title', None) or ''
        return existing_artist == artist and existing_title == title
    except Exception:
        return False

class FixerTab(QWidget):
    """Tab for scanning and fixing MP3 tags."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._files_data: List[Dict] = []
        self._setup_ui()
        self._load_saved_files()

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
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Table widget
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
        self._table.itemChanged.connect(self._on_item_changed)
        self._table.cellChanged.connect(self._on_cell_changed)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._fix_selected_btn = QPushButton("Fix Selected")
        self._fix_selected_btn.clicked.connect(self.fix_selected)
        self._fix_all_btn = QPushButton("Auto-Fix All")
        self._fix_all_btn.clicked.connect(self.auto_fix_all)

        button_layout.addWidget(self._fix_selected_btn)
        button_layout.addWidget(self._fix_all_btn)

        layout.addLayout(button_layout)

    def load_from_scan(self, files: List[Path], artist_counts: Dict[str, int]):
        """Load files from a scan result.

        Args:
            files: List of MP3 file paths.
            artist_counts: Dictionary of artist name counts (for filtering).
        """
        # Only clear and reload if we actually scanned new files
        # If files is empty (incremental scan found no changes), keep existing data
        if files:
            self._files_data = []

            for file_path in files:
                entry = self._load_file_entry(file_path, artist_counts)
                if entry:
                    self._files_data.append(entry)

            self._apply_filter()
    
    def _load_saved_files(self):
        """Load files with needs_fixing=1 from database on startup."""
        try:
            from musichouse import config as app_config
            from musichouse.leaderboard_cache import LeaderboardCache
            
            cache = LeaderboardCache(app_config.get_config_dir())
            conn = cache._get_connection()
            
            # Get all files with needs_fixing=1
            cursor = conn.execute(
                """SELECT path, artist, title, 
                       needs_fixing, missing_artist, missing_title,
                       suggested_artist, suggested_title
                  FROM scan_cache
                 WHERE needs_fixing = 1"""
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
                logger.info(f"Loaded {len(self._files_data)} files needing fix from DB")
        except Exception as e:
            logger.error(f"Error loading saved files from DB: {e}")
    
    def _load_file_entry(self, file_path: Path, artist_counts: Dict[str, int]) -> Optional[Dict]:
        """Load a single file entry."""
        audiofile = load_mp3_safely(file_path)

        if audiofile is None or audiofile.tag is None:
            return None

        existing_artist = audiofile.tag.artist or ""
        existing_title = audiofile.tag.title or ""

        # Parse filename for suggested fix
        suggested_artist, suggested_title = parse_filename(file_path.name)

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

    def add_file_entry(self, entry: dict):
        """Add a single file entry to the table in real-time.
        
        Only adds the row if it passes the current filter (efficient - no table rebuild).
        
        Args:
            entry: Dict with path, filename, existing_artist, existing_title,
                   suggested_artist, suggested_title, missing_artist, missing_title.
        """
        # Add to internal data list
        self._files_data.append(entry)
        
        # Only add row if it passes the current filter (efficient - no table rebuild)
        filter_text = self._filter_combo.currentText()
        if self._should_show_entry(entry, filter_text):
            self._add_row_to_table(entry)

    def _apply_filter(self):
        """Apply the current filter to the table."""
        filter_text = self._filter_combo.currentText()

        self._table.setRowCount(0)

        for entry in self._files_data:
            should_show = self._should_show_entry(entry, filter_text)
            if should_show:
                self._add_row_to_table(entry)

    def _should_show_entry(self, entry: Dict, filter_text: str) -> bool:
        """Check if entry should be shown based on filter."""
        if filter_text == "All":
            return True
        elif filter_text == "Missing Artist":
            return entry["missing_artist"]
        elif filter_text == "Missing Title":
            return entry["missing_title"]
        elif filter_text == "Both":
            return entry["missing_artist"] and entry["missing_title"]
        return True

    def _add_row_to_table(self, entry: Dict):
        """Add a row to the table."""
        row = self._table.rowCount()
        self._table.insertRow(row)

        # Checkbox
        checkbox_item = QTableWidgetItem()
        checkbox_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
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

    def fix_selected(self) -> List[Path]:
        """Apply fixes to selected files and update DB."""
        checked_rows = sorted(self._get_checked_rows())
        if not checked_rows:
            return []
        
        fixed_paths = []
        for row in checked_rows:
            entry = self._files_data[row]
            file_path = entry["path"]
            
            # Get the current (possibly edited) values from the table
            artist_item = self._table.item(row, 2)
            title_item = self._table.item(row, 3)
            new_artist = artist_item.text() if artist_item else entry["suggested_artist"]
            new_title = title_item.text() if title_item else entry["suggested_title"]
            # Write tags to file
            success = write_tags(file_path, new_artist, new_title)
            # Consider success if:
            # - write_tags returned True (tags were written)
            # - write_tags returned False because tags already exist (file is already fixed)
            if success or _tags_already_exist(file_path, new_artist, new_title):
                fixed_paths.append(file_path)
                logger.info(f"Fixed: {file_path.name}")
            else:
                logger.error(f"Failed to fix: {file_path.name}")

        # Update DB: mark fixed files as not needing fixing
        if fixed_paths:
            self._update_db_after_fix(fixed_paths)
        
        # Remove ONLY successfully fixed files from the table
        self._remove_fixed_rows(fixed_paths)  # Pass fixed_paths instead of checked_rows

        return fixed_paths
    
    def _update_db_after_fix(self, fixed_paths: List[Path]) -> None:
        """Update database to mark files as fixed."""
        try:
            cache = LeaderboardCache(config.get_config_dir())
            for path in fixed_paths:
                # Update the scan_cache row to set needs_fixing = 0
                conn = cache._get_connection()
                conn.execute(
                    "UPDATE scan_cache SET needs_fixing = 0, missing_artist = 0, missing_title = 0 WHERE path = ?",
                    (str(path),)
                )
            conn.commit()
            cache.close()
            logger.info(f"Updated DB for {len(fixed_paths)} fixed files")
        except Exception as e:
            logger.error(f"Error updating DB after fix: {e}")
    
    def _remove_fixed_rows(self, fixed_paths: List[Path]) -> None:
        """Remove fixed rows from the table (in reverse order to preserve indices)."""
        # Find row indices that match the fixed paths
        rows_to_remove = []
        for i, entry in enumerate(self._files_data):
            if entry["path"] in fixed_paths:
                rows_to_remove.append(i)

        for row in sorted(rows_to_remove, reverse=True):
            del self._files_data[row]

        # Rebuild the table
        self._table.setRowCount(0)
        for entry in self._files_data:
            self._add_row_to_table(entry)
    
    def auto_fix_all(self) -> List[Path]:
        """Apply fixes to all files in the list."""
        if not self._files_data:
            return []
        
        fixed_paths = []
        for entry in self._files_data:
            file_path = entry["path"]
            new_artist = entry["suggested_artist"]
            new_title = entry["suggested_title"]
            
            # Write tags to file
            success = write_tags(file_path, new_artist, new_title)
            if success:
                fixed_paths.append(file_path)
                logger.info(f"Fixed: {file_path.name}")
            else:
                logger.error(f"Failed to fix: {file_path.name}")
        
        # Update DB
        if fixed_paths:
            self._update_db_after_fix(fixed_paths)
        
        # Clear the table
        self._files_data = []
        self._table.setRowCount(0)
        
        return fixed_paths
