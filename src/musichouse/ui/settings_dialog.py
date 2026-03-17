"""Settings dialog for API configuration."""
import re
from typing import Optional

from PyQt6 import QtWidgets
from PyQt6.QtGui import QValidator

from musichouse.config import get_endpoint, get_model, get_api_key, set_endpoint, set_model, set_api_key


class SettingsDialog(QtWidgets.QDialog):
    """Dialog for configuring API settings."""

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

        # API Endpoint
        endpoint_layout = QtWidgets.QHBoxLayout()
        endpoint_label = QtWidgets.QLabel("API Endpoint:")
        self.endpointLineEdit = QtWidgets.QLineEdit()
        endpoint_layout.addWidget(endpoint_label)
        endpoint_layout.addWidget(self.endpointLineEdit)

        # Model
        model_layout = QtWidgets.QHBoxLayout()
        model_label = QtWidgets.QLabel("Model:")
        self.modelLineEdit = QtWidgets.QLineEdit()
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.modelLineEdit)

        # API Key
        api_key_layout = QtWidgets.QHBoxLayout()
        api_key_label = QtWidgets.QLabel("API Key:")
        self.apiKeyLineEdit = QtWidgets.QLineEdit()
        self.apiKeyLineEdit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
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
        layout.addLayout(model_layout)
        layout.addLayout(api_key_layout)
        layout.addStretch()
        layout.addLayout(buttons_layout)

    def load_settings(self) -> None:
        """Load settings from config and populate fields."""
        self.endpointLineEdit.setText(get_endpoint())
        self.modelLineEdit.setText(get_model())
        self.apiKeyLineEdit.setText(get_api_key())

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
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+'  # domain
            r'(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain name
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

    def save_settings(self) -> bool:
        """Save settings to config.

        Returns:
            True if save successful, False otherwise.
        """
        try:
            endpoint = self.endpointLineEdit.text().strip()
            model = self.modelLineEdit.text().strip()
            api_key = self.apiKeyLineEdit.text()

            set_endpoint(endpoint)
            set_model(model)
            set_api_key(api_key)

            self.accept()
            return True
        except Exception:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                "Failed to save settings."
            )
            return False
