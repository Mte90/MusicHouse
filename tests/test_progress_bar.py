"""Tests for progress bar behavior in MainWindow.

These tests verify that the progress bar behaves correctly during scan operations:
- Range is set ONCE at scan start (not dynamically during progress updates)
- Value updates correctly during tag reading
- Range doesn't reset visually during scan

Run with: QT_QPA_PLATFORM=offscreen pytest tests/test_progress_bar.py -v
"""

import pytest
from pathlib import Path


pytestmark = pytest.mark.ui


class TestProgressBarRangeStability:
    """Tests for progress bar range stability during scan."""

    def test_progress_bar_range_set_once_at_start(self, qtbot, mocker):
        """Test that progress bar range is set ONCE at scan start.

        The range should be calculated and set once when scan begins,
        not dynamically updated during progress updates. This prevents
        the visual "reset" effect where the progress bar appears to jump.
        """
        from musichouse.ui.main_window import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Track setRange calls
        set_range_calls = []
        original_set_range = window._progress_bar.setRange

        def track_set_range(min_val, max_val):
            set_range_calls.append((min_val, max_val))
            original_set_range(min_val, max_val)

        window._progress_bar.setRange = track_set_range

        # Set initial range (simulating what _on_scan_total_work does)
        window._on_scan_total_work(100)
        initial_call_count = len(set_range_calls)

        # Simulate progress updates that would happen during tag reading
        # BEFORE the fix: setRange would be called here (BUG)
        # AFTER the fix: setRange should NOT be called
        for i in range(1, 10):
            window._on_tag_read_progress(i, 100)

        # Verify setRange was NOT called during progress updates
        assert len(set_range_calls) == initial_call_count, (
            f"Progress bar range changed {len(set_range_calls) - initial_call_count} times "
            f"during progress updates. Range should be set ONCE at start, not dynamically."
        )

    def test_progress_bar_value_updates_correctly(self, qtbot):
        """Test that progress bar value updates correctly during progress."""
        from musichouse.ui.main_window import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Set range first
        window._on_scan_total_work(100)
        assert window._progress_bar.minimum() == 0
        assert window._progress_bar.maximum() == 100

        # Update progress
        window._on_tag_read_progress(50, 100)
        assert window._progress_bar.value() == 50

        window._on_tag_read_progress(75, 100)
        assert window._progress_bar.value() == 75

        window._on_tag_read_progress(100, 100)
        assert window._progress_bar.value() == 100

    def test_no_process_events_in_progress_handler(self, qtbot, mocker):
        """Test that processEvents is NOT called during progress updates."""
        from musichouse.ui.main_window import MainWindow
        from PyQt6.QtWidgets import QApplication

        window = MainWindow()
        qtbot.addWidget(window)

        # Mock processEvents to detect if it's called
        mock_process = mocker.patch.object(QApplication, 'processEvents')

        # Set range and update progress
        window._on_scan_total_work(100)
        window._on_tag_read_progress(50, 100)
        window._on_tag_read_progress(75, 100)

        # processEvents should NOT have been called
        assert mock_process.call_count == 0, (
            "processEvents() should NOT be called during progress updates. "
            "This is an anti-pattern that causes reentrancy issues."
        )
