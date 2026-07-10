"""MusicHouse application entry point."""

import sys

from PyQt6.QtWidgets import QApplication

from musichouse.ui.main_window import MainWindow
from musichouse.utils.lock import SingleInstanceLock


def main() -> int:
    """Launch the MusicHouse application.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Acquire single-instance lock
    try:
        SingleInstanceLock()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
