"""MusicHouse application entry point."""

import sys
from PyQt6.QtWidgets import QApplication

from musichouse.ui.main_window import MainWindow


def main() -> int:
    """Launch the MusicHouse application.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
