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
        from musichouse.ui.main_window import MainWindow, ScanWorker
        from musichouse.scanner import MP3Scanner

        window = MainWindow()
        qtbot.addWidget(window)

        # Mock scanner to return known file count
        mock_files = [Path('/test1.mp3'), Path('/test2.mp3'), Path('/test3.mp3')]
        mocker.patch.object(MP3Scanner, 'scan', return_value=mock_files)

        # Track setRange calls
        set_range_calls = []
        original_set_range = window._progress_bar.setRange

        def track_set_range(min_val, max_val):
            set_range_calls.append((min_val, max_val))
            original_set_range(min_val, max_val)

        window._progress_bar.setRange = track_set_range

        # Start scan with mocked path
        mocker.patch(
            'PyQt6.QtWidgets.QFileDialog.getExistingDirectory',
            return_value=str(Path('/test'))
        )

        # Mock worker to avoid actual threading
        original_worker_init = ScanWorker.__init__
        worker_instances = []

        def mock_worker_init(self, base_path):
            original_worker_init(self, base_path)
            worker_instances.append(self)

        mocker.patch.object(ScanWorker, '__init__', mock_worker_init)

        window._start_scan()

        # Verify setRange was called (at least once for initial setup)
        # The bug is that it gets called multiple times during progress updates
        initial_call_count = len(set_range_calls)

        # Simulate progress updates that would happen during tag reading
        for i in range(1, 4):
            window._on_tag_read_progress(i, 3)

        # PROBLEM: With the bug, setRange is called every time _on_tag_read_progress runs
        # EXPECTED: setRange should NOT be called again after initial setup
        # This test will FAIL initially because the bug exists
        assert len(set_range_calls) == initial_call_count, (
            f"Progress bar range changed {len(set_range_calls) - initial_call_count} times "
            f"during progress updates. Range should be set ONCE at start, not dynamically."
        )

        window.close()

    def test_progress_bar_value_updates_correctly(self, qtbot):
        """Test that progress bar value updates correctly during tag reading.

        The progress bar value should increment from 0 to total as items are processed.
        """
        from musichouse.ui.main_window import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Set up progress bar range (simulating what should happen at scan start)
        window._progress_bar.setRange(0, 100)
        window._progress_bar.setVisible(True)

        # Simulate progress updates
        for current in [10, 25, 50, 75, 100]:
            window._on_tag_read_progress(current, 100)
            assert window._progress_bar.value() == current, (
                f"Progress bar value should be {current}, but got {window._progress_bar.value()}"
            )

        window.close()

    def test_progress_bar_does_not_reset_during_scan(self, qtbot, mocker):
        """Test that progress bar doesn't visually reset during scan.

        This is the main bug: when setRange(0, total) is called with the same
        or different total values, the progress bar visually resets even if
        the value is the same. This creates a jarring user experience.

        The fix: Calculate total work ONCE at start, set range ONCE,
        then only update the value.
        """
        from musichouse.ui.main_window import MainWindow, ScanWorker
        from musichouse.scanner import MP3Scanner

        window = MainWindow()
        qtbot.addWidget(window)

        # Mock scanner
        mock_files = [Path(f'/test{i}.mp3') for i in range(1, 6)]
        mocker.patch.object(MP3Scanner, 'scan', return_value=mock_files)

        # Capture initial range after setup
        initial_min = window._progress_bar.minimum()
        initial_max = window._progress_bar.maximum()
        initial_range = (initial_min, initial_max)

        # Simulate what happens during a real scan with varying totals
        # (This simulates the bug where total changes dynamically)
        progress_updates = [
            (1, 5),
            (2, 5),
            (3, 5),
            (4, 5),
            (5, 5),
        ]

        for current, total in progress_updates:
            window._on_tag_read_progress(current, total)

            # Check that range hasn't changed
            current_range = (window._progress_bar.minimum(), window._progress_bar.maximum())
            assert current_range == initial_range, (
                f"Progress bar range changed from {initial_range} to {current_range} "
                f"during scan! Range should stay stable. "
                f"This causes visual reset effect at current={current}, total={total}"
            )

            # Check that value is correct
            assert window._progress_bar.value() == current

        window.close()

    def test_progress_bar_range_initialized_correctly(self, qtbot):
        """Test that progress bar has correct initial range.

        The progress bar should start with a reasonable default range (0-100)
        and be hidden initially.
        """
        from musichouse.ui.main_window import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Check initial state
        assert window._progress_bar.minimum() == 0
        assert window._progress_bar.maximum() == 100
        assert window._progress_bar.value() == 0
        assert window._progress_bar.isVisible() is False

        window.close()

    def test_progress_bar_visible_during_scan(self, qtbot, mocker):
        """Test that progress bar becomes visible when scan starts.

        The progress bar should be hidden initially and become visible
        when a scan is started.
        """
        from musichouse.ui.main_window import MainWindow, ScanWorker
        from musichouse.scanner import MP3Scanner

        window = MainWindow()
        qtbot.addWidget(window)

        # Initially hidden
        assert window._progress_bar.isVisible() is False

        # Mock scanner
        mocker.patch.object(MP3Scanner, 'scan', return_value=[Path('/test.mp3')])

        # Mock file dialog
        mocker.patch(
            'PyQt6.QtWidgets.QFileDialog.getExistingDirectory',
            return_value=str(Path('/test'))
        )

        # Mock worker to avoid threading issues
        original_start = ScanWorker.start
        def mock_start(self):
            pass  # Don't actually start the thread
        mocker.patch.object(ScanWorker, 'start', mock_start)

        # Start scan
        window._start_scan()

        # Should be visible now
        assert window._progress_bar.isVisible() is True

        # Cleanup
        window._stop_scan()
        window.close()

    def test_progress_bar_hidden_after_scan_complete(self, qtbot, mocker):
        """Test that progress bar is hidden after scan completes.

        After the scan finishes, the progress bar should be hidden
        to indicate the operation is complete.
        """
        from musichouse.ui.main_window import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Simulate scan start
        window._progress_bar.setVisible(True)
        window._progress_bar.setRange(0, 100)
        window._progress_bar.setValue(100)

        # Simulate scan completion
        window._on_scan_finished([], {})

        # Should be hidden again
        assert window._progress_bar.isVisible() is False

        window.close()
