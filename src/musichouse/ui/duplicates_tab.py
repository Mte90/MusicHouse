"""Tab for finding and managing duplicate MP3 files."""

from typing import Any, Dict, List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QLabel, QProgressBar, QMessageBox
)
from PyQt6.QtCore import Qt

from musichouse.duplicates import find_duplicates
from musichouse.fingerprint import is_fpcalc_available
from musichouse.leaderboard_cache import LeaderboardCache
from musichouse.ui.fingerprint_worker import FingerprintWorker
from musichouse.ui.delete_worker import DeleteWorker
from musichouse import log_setup as logging

logger = logging.get_logger(__name__)

class DuplicatesTab(QWidget):
    """Tab for finding and managing duplicate MP3 files."""

    def __init__(self, cache: LeaderboardCache, parent=None):
        super().__init__(parent)
        self._cache = cache
        self._files_data: List[Dict[str, Any]] = []
        self._worker: Optional[FingerprintWorker] = None
        self._delete_worker: Optional[DeleteWorker] = None
        
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 1. Toolbar row
        toolbar = QHBoxLayout()
        self._find_dup_btn = QPushButton("Find Duplicates")
        self._find_dup_btn.clicked.connect(self._on_find_clicked)
        
        # Mode label
        fp_available = is_fpcalc_available()
        mode_text = "Mode: Fingerprint (fpcalc detected)" if fp_available else "Mode: Metadata only (fpcalc not found)"
        self._mode_label = QLabel(mode_text)
        
        toolbar.addWidget(self._find_dup_btn)
        toolbar.addWidget(self._mode_label)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 2. Results table
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "Delete", "Path", "Artist", "Title", "Size", "Duration", "Similarity%"
        ])
        
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setAlternatingRowColors(True)
        # Rule #5991: Sorting disabled as we don't implement sync for _files_data mapping
        self._table.setSortingEnabled(False)
        self._table.itemChanged.connect(self._on_checkbox_toggled)
        
        layout.addWidget(self._table)

        # 3. Progress area
        progress_layout = QVBoxLayout()
        
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        
        self._status_label = QLabel("")
        
        button_row = QHBoxLayout()
        button_row.addStretch()
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        
        button_row.addWidget(self._stop_btn)
        button_row.addWidget(self._cancel_btn)
        
        progress_layout.addWidget(self._progress_bar)
        progress_layout.addWidget(self._status_label)
        progress_layout.addLayout(button_row)
        layout.addLayout(progress_layout)

        # 4. Delete selected button
        self._delete_btn = QPushButton("Delete Selected")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._start_deletion)
        layout.addWidget(self._delete_btn)

    def _on_find_clicked(self):
        if is_fpcalc_available():
            # Need to check if we actually need to fingerprint more files
            # For simplicity in this implementation, we start the worker. 
            # The worker itself checks for existing fingerprints.
            self._start_fingerprinting()
        else:
            self._find_duplicates()

    def _start_fingerprinting(self):
        self._worker = FingerprintWorker(self._cache)
        self._worker.progress.connect(self._on_fingerprint_progress)
        self._worker.file_done.connect(self._on_fingerprint_file_done)
        self._worker.fingerprint_finished.connect(self._on_fingerprint_finished)
        self._worker.error.connect(self._on_fingerprint_error)
        
        self._set_ui_busy(True)
        self._progress_bar.setRange(0, 0)  # Indeterminate
        self._worker.start()

    def _on_fingerprint_progress(self, msg: str):
        self._status_label.setText(msg)

    def _on_fingerprint_file_done(self, count: int):
        # We don't know total yet, so keep indeterminate
        pass

    def _on_fingerprint_finished(self, total: int):
        self._status_label.setText(f"Fingerprinting complete. Found {total} new fingerprints.")
        self._find_duplicates()

    def _on_fingerprint_error(self, msg: str):
        QMessageBox.critical(self, "Fingerprint Error", msg)
        self._set_ui_busy(False)

    def _find_duplicates(self):
        self._status_label.setText("Searching for duplicates...")
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 0)
        
        # Use the helper to find duplicates based on cache
        groups = find_duplicates(self._cache)
        
        self._display_duplicates(groups)
        self._progress_bar.setVisible(False)
        self._status_label.setText(f"Found {len(groups)} groups of duplicates.")
        self._set_ui_busy(False)

    def _display_duplicates(self, groups: list[list[dict]]):
        self._table.setRowCount(0)
        self._files_data = []
        
        global_file_idx = 0
        for group_id, group in enumerate(groups, 1):
            for i, file_info in enumerate(group):
                # Store data
                self._files_data.append(file_info)
                
                row = self._table.rowCount()
                self._table.insertRow(row)
                
                # Checkbox: Pre-select all but the first file in each group
                cb_item = QTableWidgetItem()
                cb_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                cb_item.setCheckState(Qt.CheckState.Checked if i > 0 else Qt.CheckState.Unchecked)
                self._table.setItem(row, 0, cb_item)
                
                # Path
                self._table.setItem(row, 1, QTableWidgetItem(file_info['path']))
                # Artist
                self._table.setItem(row, 2, QTableWidgetItem(file_info['artist']))
                # Title
                self._table.setItem(row, 3, QTableWidgetItem(file_info['title']))
                # Size
                size_mb = file_info['size'] / (1024 * 1024)
                self._table.setItem(row, 4, QTableWidgetItem(f"{size_mb:.1f} MB"))
                # Duration
                duration = file_info.get('duration')
                duration_text = "—"
                if duration:
                    mins, secs = divmod(int(duration), 60)
                    duration_text = f"{mins}:{secs:02d}"
                self._table.setItem(row, 5, QTableWidgetItem(duration_text))
                # Similarity
                sim = file_info.get('similarity')
                sim_text = f"{sim:.1f}%" if sim is not None else "—"
                self._table.setItem(row, 6, QTableWidgetItem(sim_text))
                
                # Group number (stored in tooltip or a hidden column, but user wants visual grouping)
                # We can just use the row color or a label. Let's use a tooltip on the path.
                self._table.item(row, 1).setToolTip(f"Group {group_id}")
                
                global_file_idx += 1

        self._update_delete_button()

    def _on_checkbox_toggled(self, item):
        if item.column() == 0:
            self._update_delete_button()

    def _update_delete_button(self):
        has_selected = any(
            self._table.item(r, 0).checkState() == Qt.CheckState.Checked 
            for r in range(self._table.rowCount())
        )
        self._delete_btn.setEnabled(has_selected)

    def _start_deletion(self):
        paths_to_delete = []
        for row in range(self._table.rowCount()):
            if self._table.item(row, 0).checkState() == Qt.CheckState.Checked:
                paths_to_delete.append(self._table.item(row, 1).text())
        
        if not paths_to_delete:
            return
            
        reply = QMessageBox.question(
            self, "Confirm Deletion", 
            f"Delete {len(paths_to_delete)} files? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._delete_worker = DeleteWorker(paths_to_delete)
            self._delete_worker.file_deleted.connect(self._on_file_deleted)
            self._delete_worker.deletion_finished.connect(self._on_deletion_finished)
            self._delete_worker.error.connect(self._on_deletion_error)
            
            self._set_ui_busy(True)
            self._progress_bar.setVisible(True)
            self._progress_bar.setRange(0, 0)
            self._delete_worker.start()

    def _on_file_deleted(self, path: str, success: bool, error: str):
        if not success:
            logger.error(f"Failed to delete {path}: {error}")

    def _on_deletion_finished(self, count: int):
        QMessageBox.information(self, "Deletion Complete", f"Successfully deleted {count} files.")
        self._set_ui_busy(False)
        self._progress_bar.setVisible(False)
        # Refresh the view
        self._find_duplicates()

    def _on_deletion_error(self, msg: str):
        QMessageBox.critical(self, "Deletion Error", msg)
        self._set_ui_busy(False)
        self._progress_bar.setVisible(False)

    def _on_stop_clicked(self):
        if self._worker:
            self._worker.stop()
        if self._delete_worker:
            self._delete_worker.stop()

    def _on_cancel_clicked(self):
        self._on_stop_clicked()

    def _set_ui_busy(self, busy: bool):
        self._find_dup_btn.setEnabled(not busy)
        self._delete_btn.setEnabled(not busy and self._delete_btn.isEnabled()) # keep state if not busy
        if not busy:
            self._update_delete_button()
