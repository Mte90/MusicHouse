from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from musichouse import log_setup as logging
from musichouse.ai_client import AIClient
from musichouse.leaderboard_cache import LeaderboardCache
from musichouse.ui.apply_worker import ApplyWorker
from musichouse.ui.organize_worker import OrganizeWorker

logger = logging.get_logger(__name__)

class OrganizeTab(QWidget):
    """Tab for AI-powered folder organization with MusicBrainz genre data."""

    def __init__(self, cache: LeaderboardCache, ai_client: AIClient,
                 base_path: Path, parent=None):
        super().__init__(parent)
        self._cache = cache
        self._ai_client = ai_client
        self._base_path = base_path
        
        self._actions_data: list[dict[str, Any]] = []
        self._worker: OrganizeWorker | None = None
        self._apply_worker: ApplyWorker | None = None
        
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 1. Toolbar row
        toolbar = QHBoxLayout()
        self._analyze_btn = QPushButton("Analyze")
        self._analyze_btn.clicked.connect(self._start_analysis)
        
        self._info_label = QLabel(
            "Analyzes your folder structure, fetches artist genres from MusicBrainz, "
            "and suggests moves/renames using AI."
        )
        self._info_label.setWordWrap(True)
        self._info_label.setStyleSheet("color: gray; font-size: 11px;")
        
        toolbar.addWidget(self._analyze_btn)
        toolbar.addWidget(self._info_label)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 2. Results table
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels([
            "Select", "Type", "Current Path", "Suggested Action", "Reason"
        ])
        
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setAlternatingRowColors(True)
        # Rule #5991: Sorting disabled to prevent index mismatch with _actions_data
        self._table.setSortingEnabled(False)
        self._table.itemChanged.connect(self._on_checkbox_toggled)
        
        layout.addWidget(self._table)

        # 3. Folder analysis summary
        self._summary_group = QFrame()
        self._summary_group.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        summary_layout = QVBoxLayout(self._summary_group)
        
        self._summary_label = QLabel("Folder Analysis Summary: No data")
        self._summary_label.setStyleSheet("font-weight: bold;")
        summary_layout.addWidget(self._summary_label)
        
        self._summary_details = QLabel("Ready to analyze...")
        self._summary_details.setWordWrap(True)
        summary_layout.addWidget(self._summary_details)
        
        layout.addWidget(self._summary_group)

        # 4. Progress area
        progress_layout = QVBoxLayout()
        
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setRange(0, 0)  # Indeterminate
        
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

        # 5. Apply selected button
        self._apply_btn = QPushButton("Apply Selected")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._start_apply)
        layout.addWidget(self._apply_btn)

    def _start_analysis(self):
        self._actions_data = []
        self._table.setRowCount(0)
        
        self._worker = OrganizeWorker(self._cache, self._ai_client, self._base_path)
        self._worker.progress.connect(self._on_progress)
        self._worker.progress_percent.connect(self._on_progress_percent)
        self._worker.analysis_finished.connect(self._on_analysis_finished)
        self._worker.error.connect(self._on_error)
        
        self._set_ui_busy(True)
        self._progress_bar.setVisible(True)
        self._status_label.setText("Starting analysis...")
        self._worker.start()

    def _on_progress(self, msg: str):
        self._status_label.setText(msg)

    def _on_progress_percent(self, current: int, total: int):
        if total > 0:
            self._progress_bar.setRange(0, total)
            self._progress_bar.setValue(current)
        else:
            self._progress_bar.setRange(0, 0)

    def _on_analysis_finished(self, result: dict):
        self._set_ui_busy(False)
        self._progress_bar.setVisible(False)
        self._status_label.setText("Analysis complete.")
        
        if not result:
            return

        # 1. Populate results table
        moves = result.get("moves", [])
        renames = result.get("renames", [])
        
        self._table.setRowCount(0)
        self._actions_data = []
        
        # Combine moves and renames
        all_actions = []
        for m in moves:
            all_actions.append({"type": "Move", "from": m["from"], "to": m["to"], "reason": m["reason"]})
        for r in renames:
            all_actions.append({"type": "Rename", "from": r["from"], "to": r["to"], "reason": r["reason"]})
            
        for action in all_actions:
            self._actions_data.append(action)
            row = self._table.rowCount()
            self._table.insertRow(row)
            
            # Checkbox
            cb_item = QTableWidgetItem()
            cb_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            cb_item.setCheckState(Qt.CheckState.Unchecked)
            self._table.setItem(row, 0, cb_item)
            
            # Type
            self._table.setItem(row, 1, QTableWidgetItem(action["type"]))
            # Current Path
            self._table.setItem(row, 2, QTableWidgetItem(action["from"]))
            # Suggested Action
            self._table.setItem(row, 3, QTableWidgetItem(f"→ {action['to']}"))
            # Reason
            self._table.setItem(row, 4, QTableWidgetItem(action["reason"]))

        # 2. Populate folder summary
        folders = result.get("folders", [])
        if folders:
            counts = {
                "genre_container": 0,
                "correct_artist": 0,
                "misnamed_artist": 0,
                "mixed": 0
            }
            for f in folders:
                ftype = f.get("folder_type")
                if ftype in counts:
                    counts[ftype] += 1
            
            summary_text = (
                f"GENRE_CONTAINER: {counts['genre_container']}, "
                f"CORRECT_ARTIST: {counts['correct_artist']}, "
                f"MISNAMED_ARTIST: {counts['misnamed_artist']}, "
                f"MIXED: {counts['mixed']}"
            )
            self._summary_label.setText("Folder Analysis Summary:")
            self._summary_details.setText(summary_text)
        else:
            self._summary_details.setText("No folder data available.")

    def _on_error(self, msg: str):
        self._set_ui_busy(False)
        self._progress_bar.setVisible(False)
        self._status_label.setText(f"Error: {msg}")
        QMessageBox.critical(self, "Analysis Error", msg)

    def _on_stop_clicked(self):
        if self._worker:
            self._worker.stop()

    def _on_cancel_clicked(self):
        self._on_stop_clicked()

    def _on_checkbox_toggled(self, item):
        if item.column() == 0:
            self._update_apply_button()

    def _update_apply_button(self):
        has_selected = any(
            self._table.item(r, 0).checkState() == Qt.CheckState.Checked 
            for r in range(self._table.rowCount())
        )
        self._apply_btn.setEnabled(has_selected)

    def _start_apply(self):
        selected_actions = []
        for row in range(self._table.rowCount()):
            if self._table.item(row, 0).checkState() == Qt.CheckState.Checked:
                action = self._actions_data[row]
                selected_actions.append({
                    "type": action["type"].lower(),
                    "from": action["from"],
                    "to": action["to"]
                })
        
        if not selected_actions:
            return
            
        reply = QMessageBox.question(
            self, "Confirm Application", 
            f"Apply {len(selected_actions)} actions? This will move and rename files. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._apply_worker = ApplyWorker(selected_actions)
            self._apply_worker.file_applied.connect(self._on_file_applied)
            self._apply_worker.apply_finished.connect(self._on_apply_finished)
            self._apply_worker.error.connect(self._on_apply_error)
            
            self._set_ui_busy(True)
            self._progress_bar.setVisible(True)
            self._status_label.setText("Applying changes...")
            self._apply_worker.start()

    def _on_file_applied(self, path: str, success: bool, error: str):
        if not success:
            logger.error(f"Failed to apply action for {path}: {error}")

    def _on_apply_finished(self, count: int):
        self._set_ui_busy(False)
        self._progress_bar.setVisible(False)
        self._status_label.setText(f"Applied {count} actions successfully.")
        QMessageBox.information(self, "Apply Complete", f"Successfully applied {count} actions.")
        # Re-analyze to update table and summary
        self._start_analysis()

    def _on_apply_error(self, msg: str):
        self._set_ui_busy(False)
        self._progress_bar.setVisible(False)
        self._status_label.setText(f"Apply Error: {msg}")
        QMessageBox.critical(self, "Apply Error", msg)

    def _set_ui_busy(self, busy: bool):
        self._analyze_btn.setEnabled(not busy)
        self._apply_btn.setEnabled(not busy and self._apply_btn.isEnabled())
        if not busy:
            self._update_apply_button()

