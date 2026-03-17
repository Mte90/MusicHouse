#!/usr/bin/env python3
"""MusicHouse application entry point."""

import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from PyQt6.QtWidgets import QApplication
from musichouse.ui import MainWindow
from musichouse import logging

logger = logging.get_logger(__name__)


def main():
    """Run the MusicHouse application."""
    logger.info("Starting MusicHouse application")
    
    app = QApplication(sys.argv)
    app.setApplicationName("MusicHouse")
    app.setOrganizationName("MusicHouse")
    
    window = MainWindow()
    window.show()
    
    logger.info("MusicHouse application started")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
