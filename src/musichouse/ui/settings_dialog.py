"""Settings dialog for API configuration."""
import re
from typing import Optional

from PyQt6 import QtWidgets
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QValidator

from musichouse.config import get_endpoint, get_model, get_api_key, set_endpoint, set_model, set_api_key, get_exclude_dirs, set_exclude_dirs
from musichouse.ai_client import AIClient


class SettingsDialog(QtWidgets.QDialog):
    """Dialog for configuring API settings."""
    
    settings_saved = pyqtSignal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        """Initialize the settings dialog."""
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(600, 200)  # Reduced height - 3 fields don't need 300px

        self._setup_ui()
        self.load_settings()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QtWidgets.QVBoxLayout(self)

        # API Endpoint with Test Connection button
        endpoint_layout = QtWidgets.QHBoxLayout()
        endpoint_label = QtWidgets.QLabel("API Endpoint:")
        self.endpointLineEdit = QtWidgets.QLineEdit()
        self.endpointLineEdit.setToolTip("The URL of the AI API endpoint (e.g., http://localhost:8080)")
        self.testConnectionBtn = QtWidgets.QPushButton("Test")
        self.testConnectionBtn.setFixedWidth(70)
        self.testConnectionBtn.clicked.connect(self._test_connection)
        endpoint_layout.addWidget(endpoint_label)
        endpoint_layout.addWidget(self.endpointLineEdit)
        endpoint_layout.addWidget(self.testConnectionBtn)
        
        # Test connection status label
        self.testStatusLabel = QtWidgets.QLabel("")
        self.testStatusLabel.setFixedHeight(20)
        self.testStatusLabel.hide()

        # Model
        model_layout = QtWidgets.QHBoxLayout()
        model_label = QtWidgets.QLabel("Model:")
        self.modelLineEdit = QtWidgets.QLineEdit()
        self.modelLineEdit.setToolTip("The AI model name to use for suggestions (e.g., gpt-4, llama2)")
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.modelLineEdit)
        
        # Exclude directories
        exclude_layout = QtWidgets.QVBoxLayout()
        exclude_label = QtWidgets.QLabel("Exclude Directories (one per line):")
        self.excludeTextEdit = QtWidgets.QTextEdit()
        self.excludeTextEdit.setPlaceholderText(".git\nnode_modules\n.Trash\n__pycache__")
        self.excludeTextEdit.setMaximumHeight(80)
        exclude_layout.addWidget(exclude_label)
        exclude_layout.addWidget(self.excludeTextEdit)

        # API Key
        api_key_layout = QtWidgets.QHBoxLayout()
        api_key_label = QtWidgets.QLabel("API Key:")
        self.apiKeyLineEdit = QtWidgets.QLineEdit()
        self.apiKeyLineEdit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.apiKeyLineEdit.setToolTip("Your API key for authentication (leave empty if not required)")
        api_key_layout.addWidget(api_key_label)
        api_key_layout.addWidget(self.apiKeyLineEdit)

        # Buttons
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addStretch()
        self.saveButton = QtWidgets.QPushButton("Save")
        self.cancelButton = QtWidgets.QPushButton("Cancel")
        self.saveButton.clicked.connect(self._on_save_clicked)
        self.cancelButton.clicked.connect(self.reject)
        buttons_layout.addWidget(self.saveButton)
        buttons_layout.addWidget(self.cancelButton)

        # Add all widgets to main layout
        layout.addLayout(endpoint_layout)
        layout.addWidget(self.testStatusLabel)
        layout.addLayout(model_layout)
        layout.addLayout(exclude_layout)
        layout.addLayout(api_key_layout)
        layout.addStretch()
        layout.addLayout(buttons_layout)

    def load_settings(self) -> None:
        """Load settings from config and populate fields."""
        self.endpointLineEdit.setText(get_endpoint())
        self.modelLineEdit.setText(get_model())
        self.apiKeyLineEdit.setText(get_api_key())
        # Load exclude directories
        exclude_dirs = get_exclude_dirs()
        self.excludeTextEdit.setPlainText("\n".join(exclude_dirs))

    def _validate_input(self) -> bool:
        """Validate input fields before saving.

        Returns:
            True if all fields are valid, False otherwise.
        """
        endpoint = self.endpointLineEdit.text().strip()
        model = self.modelLineEdit.text().strip()
        api_key = self.apiKeyLineEdit.text()

        # Validate endpoint (must be a valid URL)
        if not endpoint:
            QtWidgets.QMessageBox.warning(
                self,
                "Validation Error",
                "API Endpoint cannot be empty."
            )
            return False

        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+'  # domain with dots
            r'(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # TLD required for multi-part domains
            r'[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?|'  # single hostname (e.g., my-nas)
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        if not url_pattern.match(endpoint):
            QtWidgets.QMessageBox.warning(
                self,
                "Validation Error",
                "API Endpoint must be a valid URL (e.g., http://localhost:8080)"
            )
            return False

        # Validate model (must not be empty)
        if not model:
            QtWidgets.QMessageBox.warning(
                self,
                "Validation Error",
                "Model cannot be empty."
            )
            return False

        return True

    def _on_save_clicked(self) -> None:
        """Handle save button click."""
        if self._validate_input():
            self.save_settings()
    
    def _test_connection(self) -> None:
        """Test API connection using a minimal request."""
        endpoint = self.endpointLineEdit.text().strip()
        model = self.modelLineEdit.text().strip()
        api_key = self.apiKeyLineEdit.text()
        
        # Validate endpoint first
        if not endpoint:
            self.testStatusLabel.setText("Error: Endpoint required")
            self.testStatusLabel.setStyleSheet("color: red;")
            self.testStatusLabel.show()
            return
        
        # Disable button during test
        self.testConnectionBtn.setEnabled(False)
        self.testStatusLabel.setText("Testing...")
        self.testStatusLabel.setStyleSheet("")
        self.testStatusLabel.show()
        
        # Use QThread for the test
        from PyQt6.QtCore import QThread, pyqtSignal
        
        class TestWorker(QThread):
            result = pyqtSignal(bool, str)
            
            def __init__(self, endpoint, model, api_key):
                super().__init__()
                self.endpoint = endpoint
                self.model = model
                self.api_key = api_key
            
            def run(self):
                try:
                    client = AIClient(endpoint=self.endpoint, model=self.model, api_key=self.api_key)
                    client.get_artist_genres("Test")
                    self.result.emit(True, "Connected ✓")
                except Exception as e:
                    self.result.emit(False, str(e))
        
        self._test_worker = TestWorker(endpoint, model, api_key)
        self._test_worker.result.connect(self._on_test_result)
        self._test_worker.start()
    
    def _on_test_result(self, success: bool, message: str) -> None:
        """Handle test connection result."""
        self.testConnectionBtn.setEnabled(True)
        self.testStatusLabel.setText(message)
        self.testStatusLabel.setStyleSheet("color: green;" if success else "color: red;")

    def save_settings(self) -> bool:
        """Save settings to config.

        Returns:
            True if save successful, False otherwise.
        """
        try:
            endpoint = self.endpointLineEdit.text().strip()
            model = self.modelLineEdit.text().strip()
            api_key = self.apiKeyLineEdit.text()

            # Parse exclude directories
            exclude_text = self.excludeTextEdit.toPlainText()
            exclude_dirs = [line.strip() for line in exclude_text.split("\n") if line.strip()]

            set_endpoint(endpoint)
            set_model(model)
            set_api_key(api_key)
            set_exclude_dirs(exclude_dirs)

            self.settings_saved.emit()
            self.accept()
            return True
        except Exception:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                "Failed to save settings."
            )
            return False
