"""Unit tests for log_setup module."""

import logging

from musichouse import log_setup


class TestThirdPartyLoggerConfiguration:
    """Tests for third-party logger configuration."""

    def test_eyed3_logger_set_to_error_level(self):
        """Test that eyed3 logger is configured to ERROR level."""
        # Run the configuration
        log_setup.configure_third_party_loggers()
        
        # Get the eyed3 logger and check its level
        eyed3_logger = logging.getLogger("eyed3")
        assert eyed3_logger.level == logging.ERROR

    def test_eyed3_logger_suppresses_warning_messages(self):
        """Test that eyed3 warnings are suppressed after configuration."""
        # Run the configuration
        log_setup.configure_third_party_loggers()
        
        # Get the eyed3 logger
        eyed3_logger = logging.getLogger("eyed3")
        
        # Verify it won't handle WARNING level messages
        assert not eyed3_logger.isEnabledFor(logging.WARNING)
        assert eyed3_logger.isEnabledFor(logging.ERROR)