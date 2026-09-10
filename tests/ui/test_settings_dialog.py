"""Tests for SettingsDialog."""
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QMessageBox

from musichouse.config import DEFAULT_CONFIG
from musichouse.ui.settings_dialog import SettingsDialog


class TestSettingsDialogConstruction:
    """Test dialog construction and initial state."""

    def test_dialog_construction(self, qapp, qtbot):
        """Test dialog creates without errors and has expected widgets."""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        assert dialog.windowTitle() == "Settings"
        assert dialog.isModal()
        
        assert dialog.endpointLineEdit is not None
        assert dialog.modelLineEdit is not None
        assert dialog.apiKeyLineEdit is not None
        assert dialog.excludeTextEdit is not None
        assert dialog.testConnectionBtn is not None
        assert dialog.testStatusLabel is not None
        assert dialog.saveButton is not None
        assert dialog.cancelButton is not None
        
        dialog.close()

    def test_password_echo_mode(self, qapp, qtbot):
        """Test API key field uses password echo mode."""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        assert dialog.apiKeyLineEdit.echoMode() == dialog.apiKeyLineEdit.EchoMode.Password
        
        dialog.close()

    def test_test_connection_button_disabled_during_test(self, qapp, qtbot):
        """Test test connection button gets disabled during test."""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        assert dialog.testConnectionBtn.isEnabled()
        
        dialog.close()

    def test_test_status_label_hidden_initially(self, qapp, qtbot):
        """Test status label is hidden before any test."""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        assert not dialog.testStatusLabel.isVisible()
        
        dialog.close()


class TestSettingsLoadSave:
    """Test settings load/save round-trip."""

    def test_load_settings_populates_fields(self, qapp, qtbot):
        """Test load_settings populates fields from config."""
        with (
            patch("musichouse.ui.settings_dialog.get_endpoint", return_value="http://test.local:9000"),
            patch("musichouse.ui.settings_dialog.get_model", return_value="test-model-v2"),
            patch("musichouse.ui.settings_dialog.get_api_key", return_value="test-key-123"),
            patch("musichouse.ui.settings_dialog.get_exclude_dirs", return_value=[".git", "venv", "build"]),
        ):
            dialog = SettingsDialog()
            qtbot.addWidget(dialog)
            
            assert dialog.endpointLineEdit.text() == "http://test.local:9000"
            assert dialog.modelLineEdit.text() == "test-model-v2"
            assert dialog.apiKeyLineEdit.text() == "test-key-123"
            assert dialog.excludeTextEdit.toPlainText() == ".git\nvenv\nbuild"
            
            dialog.close()

    def test_load_settings_uses_defaults_when_empty(self, qapp, qtbot):
        """Test load_settings uses defaults when config is empty."""
        with (
            patch("musichouse.ui.settings_dialog.get_endpoint", return_value=DEFAULT_CONFIG["endpoint"]),
            patch("musichouse.ui.settings_dialog.get_model", return_value=DEFAULT_CONFIG["model"]),
            patch("musichouse.ui.settings_dialog.get_api_key", return_value=""),
            patch("musichouse.ui.settings_dialog.get_exclude_dirs", return_value=DEFAULT_CONFIG["exclude_dirs"]),
        ):
            dialog = SettingsDialog()
            qtbot.addWidget(dialog)
            
            assert dialog.endpointLineEdit.text() == DEFAULT_CONFIG["endpoint"]
            assert dialog.modelLineEdit.text() == DEFAULT_CONFIG["model"]
            assert dialog.apiKeyLineEdit.text() == ""
            assert dialog.excludeTextEdit.toPlainText() == "\n".join(DEFAULT_CONFIG["exclude_dirs"])
            
            dialog.close()

    def test_save_settings_saves_all_fields(self, qapp, qtbot, monkeypatch):
        """Test save_settings saves all fields to config."""
        mock_set_endpoint = MagicMock()
        mock_set_model = MagicMock()
        mock_set_api_key = MagicMock()
        mock_set_exclude_dirs = MagicMock()
        
        monkeypatch.setattr("musichouse.ui.settings_dialog.set_endpoint", mock_set_endpoint)
        monkeypatch.setattr("musichouse.ui.settings_dialog.set_model", mock_set_model)
        monkeypatch.setattr("musichouse.ui.settings_dialog.set_api_key", mock_set_api_key)
        monkeypatch.setattr("musichouse.ui.settings_dialog.set_exclude_dirs", mock_set_exclude_dirs)
        
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        dialog.endpointLineEdit.setText("http://new.local:8888")
        dialog.modelLineEdit.setText("new-model")
        dialog.apiKeyLineEdit.setText("new-key")
        dialog.excludeTextEdit.setPlainText("/tmp\n/cache")
        
        result = dialog.save_settings()
        
        assert result is True
        mock_set_endpoint.assert_called_once_with("http://new.local:8888")
        mock_set_model.assert_called_once_with("new-model")
        mock_set_api_key.assert_called_once_with("new-key")
        mock_set_exclude_dirs.assert_called_once_with(["/tmp", "/cache"])
        
        dialog.close()

    def test_save_settings_emits_signal(self, qapp, qtbot):
        """Test save_settings emits settings_saved signal."""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        dialog.endpointLineEdit.setText("http://test.local:8080")
        dialog.modelLineEdit.setText("test")
        dialog.apiKeyLineEdit.setText("key")
        dialog.excludeTextEdit.setPlainText("")
        
        with qtbot.waitSignal(dialog.settings_saved, timeout=5000):
            dialog.save_settings()
        
        dialog.close()

    def test_save_settings_rejects_dialog(self, qapp, qtbot):
        """Test save_settings calls accept on dialog."""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        dialog.endpointLineEdit.setText("http://test.local:8080")
        dialog.modelLineEdit.setText("test")
        dialog.apiKeyLineEdit.setText("key")
        dialog.excludeTextEdit.setPlainText("")
        
        with qtbot.waitSignal(dialog.accepted, timeout=5000):
            dialog.save_settings()
        
        dialog.close()

    def test_save_settings_handles_exception(self, qapp, qtbot, monkeypatch):
        """Test save_settings shows error dialog on exception."""
        def mock_set_endpoint(_):
            raise RuntimeError("Save failed")
        
        monkeypatch.setattr("musichouse.ui.settings_dialog.set_endpoint", mock_set_endpoint)
        
        with patch.object(QMessageBox, "critical") as mock_critical:
            dialog = SettingsDialog()
            qtbot.addWidget(dialog)
            
            dialog.endpointLineEdit.setText("http://test.local:8080")
            dialog.modelLineEdit.setText("test")
            dialog.apiKeyLineEdit.setText("key")
            dialog.excludeTextEdit.setPlainText("")
            
            result = dialog.save_settings()
            
            assert result is False
            mock_critical.assert_called_once()
            
            dialog.close()

    def test_on_save_clicked_validates_then_saves(self, qapp, qtbot):
        """Test _on_save_clicked validates input before saving."""
        with patch("musichouse.ui.settings_dialog.set_endpoint") as mock_save:
            dialog = SettingsDialog()
            qtbot.addWidget(dialog)
            dialog.show()
            
            dialog.endpointLineEdit.setText("http://test.local:8080")
            dialog.modelLineEdit.setText("test")
            dialog.apiKeyLineEdit.setText("key")
            dialog.excludeTextEdit.setPlainText("")
            
            with qtbot.waitSignal(dialog.settings_saved, timeout=5000):
                dialog._on_save_clicked()
            
            mock_save.assert_called()
            
            dialog.close()


class TestValidation:
    """Test input validation."""

    def test_validate_empty_endpoint(self, qapp, qtbot):
        """Test validation fails for empty endpoint."""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        dialog.endpointLineEdit.setText("")
        dialog.modelLineEdit.setText("test")
        
        with patch.object(QMessageBox, "warning") as mock_warning:
            result = dialog._validate_input()
            
            assert result is False
            mock_warning.assert_called_once()
        
        dialog.close()

    def test_validate_invalid_url(self, qapp, qtbot):
        """Test validation fails for invalid URL format."""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        dialog.endpointLineEdit.setText("not-a-valid-url")
        dialog.modelLineEdit.setText("test")
        
        with patch.object(QMessageBox, "warning") as mock_warning:
            result = dialog._validate_input()
            
            assert result is False
            mock_warning.assert_called_once()
        
        dialog.close()

    def test_validate_empty_model(self, qapp, qtbot):
        """Test validation fails for empty model."""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        dialog.endpointLineEdit.setText("http://test.local:8080")
        dialog.modelLineEdit.setText("")
        
        with patch.object(QMessageBox, "warning") as mock_warning:
            result = dialog._validate_input()
            
            assert result is False
            mock_warning.assert_called_once()
        
        dialog.close()

    def test_validate_success(self, qapp, qtbot):
        """Test validation passes with valid input."""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        dialog.endpointLineEdit.setText("http://test.local:8080")
        dialog.modelLineEdit.setText("test-model")
        
        result = dialog._validate_input()
        
        assert result is True
        
        dialog.close()

    def test_validate_https_url(self, qapp, qtbot):
        """Test validation accepts HTTPS URLs."""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        dialog.endpointLineEdit.setText("https://api.example.com/v1")
        dialog.modelLineEdit.setText("test")
        
        result = dialog._validate_input()
        
        assert result is True
        
        dialog.close()

    def test_validate_ip_address(self, qapp, qtbot):
        """Test validation accepts IP addresses."""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        dialog.endpointLineEdit.setText("http://192.168.1.100:8080")
        dialog.modelLineEdit.setText("test")
        
        result = dialog._validate_input()
        
        assert result is True
        
        dialog.close()


class TestTestConnection:
    """Test connection testing functionality."""

    def test_test_connection_success(self, qapp, qtbot, monkeypatch):
        """Test successful connection shows green status."""
        mock_get_artist_genres = MagicMock(return_value=[])
        monkeypatch.setattr("musichouse.ui.settings_dialog.AIClient.get_artist_genres", mock_get_artist_genres)
        
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        dialog.endpointLineEdit.setText("http://test.local:8080")
        dialog.modelLineEdit.setText("test-model")
        
        dialog.testConnectionBtn.click()
        
        qtbot.waitUntil(lambda: mock_get_artist_genres.called, timeout=5000)
        qtbot.waitUntil(lambda: dialog.testStatusLabel.text() != "Testing...", timeout=5000)
        
        assert "Connected" in dialog.testStatusLabel.text()
        assert "green" in dialog.testStatusLabel.styleSheet()
        
        dialog.close()

    def test_test_connection_failure(self, qapp, qtbot, monkeypatch):
        """Test failed connection shows red status with error."""
        mock_get_artist_genres = MagicMock(side_effect=ConnectionError("Connection refused"))
        monkeypatch.setattr("musichouse.ui.settings_dialog.AIClient.get_artist_genres", mock_get_artist_genres)
        
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        dialog.endpointLineEdit.setText("http://invalid.local:9999")
        dialog.modelLineEdit.setText("test-model")
        
        dialog.testConnectionBtn.click()
        
        qtbot.waitUntil(lambda: dialog.testStatusLabel.text() != "Testing...", timeout=10000)
        
        assert "Error" in dialog.testStatusLabel.text() or "refused" in dialog.testStatusLabel.text().lower()
        assert "red" in dialog.testStatusLabel.styleSheet()
        
        dialog.close()

    def test_test_connection_empty_endpoint(self, qapp, qtbot):
        """Test connection with empty endpoint shows error immediately."""
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        dialog.show()
        
        dialog.endpointLineEdit.setText("")
        dialog.testConnectionBtn.click()
        
        qapp.processEvents()
        
        assert "Error: Endpoint required" in dialog.testStatusLabel.text()
        assert "red" in dialog.testStatusLabel.styleSheet()
        assert dialog.testStatusLabel.isVisible()
        
        dialog.close()

    def test_test_connection_button_reenabled_after_result(self, qapp, qtbot, monkeypatch):
        """Test button is re-enabled after test completes."""
        mock_get_artist_genres = MagicMock(side_effect=ConnectionError("Failed"))
        monkeypatch.setattr("musichouse.ui.settings_dialog.AIClient.get_artist_genres", mock_get_artist_genres)
        
        dialog = SettingsDialog()
        qtbot.addWidget(dialog)
        
        dialog.endpointLineEdit.setText("http://invalid.local:9999")
        dialog.modelLineEdit.setText("test")
        
        assert dialog.testConnectionBtn.isEnabled()
        
        dialog.testConnectionBtn.click()
        
        assert not dialog.testConnectionBtn.isEnabled()
        
        qtbot.waitUntil(lambda: dialog.testConnectionBtn.isEnabled(), timeout=10000)
        
        dialog.close()