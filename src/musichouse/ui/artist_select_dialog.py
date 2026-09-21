from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class ArtistSelectDialog(QDialog):
    """Dialog for selecting one or more seed artists for AI suggestions."""

    def __init__(self, artists_with_counts: list[tuple[str, int]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Seed Artists")
        self.setMinimumSize(400, 500)
        
        self._artists_with_counts = artists_with_counts  # list of (name, count)
        self._selected_artists: set[str] = set()
        self._checkboxes: list[QCheckBox] = []
        
        self._setup_ui()
        self._populate_list()
        self._update_ok_button()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Search filter
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search artists...")
        self._search_input.textChanged.connect(self._filter_artists)
        layout.addWidget(QLabel("Search artists:"))
        layout.addWidget(self._search_input)
        
        # Scroll area for artist list
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll_content = QWidget()
        self._list_layout = QVBoxLayout(self._scroll_content)
        self._list_layout.setSpacing(5)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._scroll_content)
        layout.addWidget(self._scroll)
        
        # Buttons
        self._button_layout = QVBoxLayout() # Simplified as layout.addWidget
        self._ok_button = QPushButton("OK")
        self._ok_button.clicked.connect(self.accept)
        self._ok_button.setEnabled(False)
        
        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.clicked.connect(self.reject)
        
        # Use a horizontal layout for buttons
        from PyQt6.QtWidgets import QHBoxLayout
        btns = QHBoxLayout()
        btns.addStretch()
        btns.addWidget(self._cancel_button)
        btns.addWidget(self._ok_button)
        layout.addLayout(btns)

    def _populate_list(self):
        """Create checkboxes for each artist."""
        # Clear existing
        for i in reversed(range(self._list_layout.count())): 
            self._list_layout.itemAt(i).widget().setParent(None)
        self._checkboxes.clear()
        
        for name, count in self._artists_with_counts:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 2, 0, 2)
            
            cb = QCheckBox(name)
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.stateChanged.connect(self._on_checkbox_toggled)
            
            count_label = QLabel(str(count))
            count_label.setStyleSheet("color: gray; font-size: 10px;")
            count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            row_layout.addWidget(cb)
            row_layout.addStretch()
            row_layout.addWidget(count_label)
            
            self._list_layout.addWidget(row)
            self._checkboxes.append(cb)

    def _on_checkbox_toggled(self, state):
        # Find which checkbox was clicked
        sender = self.sender()
        artist = sender.text()
        if state == 2: # Qt.CheckState.Checked
            self._selected_artists.add(artist)
        else:
            self._selected_artists.discard(artist)
        self._update_ok_button()

    def _update_ok_button(self):
        self._ok_button.setEnabled(len(self._selected_artists) > 0)

    def _filter_artists(self, text: str):
        text = text.lower().strip()
        for cb in self._checkboxes:
            row = cb.parentWidget()
            if row:
                # Use the checkbox text to decide visibility
                visible = not text or text in cb.text().lower()
                row.setVisible(visible)

    def get_selected_artists(self) -> list[str]:
        return list(self._selected_artists)
