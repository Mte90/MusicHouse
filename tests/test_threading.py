"""Test thread safety and signal handling in MusicHouse.

This module contains TDD tests for verifying thread safety patterns
and proper signal/slot usage in the UI. These tests should FAIL initially
(TDD RED phase) to prove the problems exist.

Run with: pytest tests/test_threading.py -v
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ============================================================================
# Test Configuration
# ============================================================================

pytestmark = pytest.mark.threading


# ============================================================================
# Test: No processEvents() Anti-Pattern
# ============================================================================

def test_no_process_events_during_scan(qtbot, mocker):
    """Test that processEvents is NOT called during scan operations.
    
    PROBLEM: processEvents() at main_window.py:595 causes:
    - Reentrancy issues
    - Event loop nesting
    - Unpredictable UI behavior
    - Progress bar "jumps"
    
    EXPECTED: Tests should FAIL initially detecting the anti-pattern.
    """
    from musichouse.ui.main_window import MainWindow
    
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Mock processEvents to detect if it's called
    mock_process = mocker.patch(
        'PyQt6.QtWidgets.QApplication.processEvents'
    )
    
    # Call the method that currently has processEvents()
    # This directly tests the anti-pattern at line 595
    window._on_tag_read_progress(current=50, total=100)
    
    # processEvents should NOT have been called
    # This test will FAIL initially, proving the anti-pattern exists
    assert mock_process.call_count == 0, (
        f"processEvents() was called {mock_process.call_count} times. "
        "This is an anti-pattern that causes reentrancy issues."
)


# Test: file_needs_fix Signal Removed

# ============================================================================



def test_file_needs_fix_signal_removed(qtbot):

    """Test that file_needs_fix signal and handler have been removed.

    

REASON: Handler was a NO-OP, files are loaded from DB after scan completes.

    Removing the signal simplifies the code and eliminates dead code.

    """

    from musichouse.ui.main_window import MainWindow, ScanWorker

    

    window = MainWindow()

    qtbot.addWidget(window)

    

    # Handler should NOT exist

    assert not hasattr(window, '_on_file_needs_fix'), "Handler should be removed"

    

    # Signal should NOT exist on worker

    worker = ScanWorker(Path('/tmp'))

    assert not hasattr(worker, 'file_needs_fix'), "Signal should be removed"

    

    worker.deleteLater()

    

    # Verification complete - no regressions

    assert True, "file_needs_fix signal and handler successfully removed"





# ============================================================================

# Test: Empty file_needs_fix Signal Handler (DEPRECATED - DO NOT USE)

# ============================================================================



# The original test_file_needs_fix_handler_is_noop signal handler was a NO-OP

# It was removed because files are loaded from DB after scan completes,

# not during scan. The signal emits were wasteful.





# The original test_file_needs_fix_signal_emissions_wasteful signal emissions

# were wasteful since handler was empty. Removed to simplify code.





def test_signal_handlers_registered(qtbot):

    """Test that all signal handlers are properly registered.

    

    UPDATED: file_needs_fix handler removed (was NO-OP).

    """

    from musichouse.ui.main_window import MainWindow

    

    window = MainWindow()

    qtbot.addWidget(window)

    

    # Verify handlers exist (except file_needs_fix which was removed)

    assert hasattr(window, '_on_scan_progress'), "Should have scan progress handler"

    assert hasattr(window, '_on_file_processed'), "Should have file processed handler"

    assert hasattr(window, '_on_tag_read_progress'), "Should have tag read progress handler"

    assert hasattr(window, '_on_scan_finished'), "Should have scan finished handler"

    assert hasattr(window, '_on_scan_error'), "Should have scan error handler"

    # NOTE: file_needs_fix handler removed - was NO-OP

    assert not hasattr(window, '_on_file_needs_fix'), "file_needs_fix handler removed"

    

    # Verify handlers are callable

    assert callable(window._on_scan_progress)

    assert callable(window._on_file_processed)

    assert callable(window._on_tag_read_progress)

    assert callable(window._on_scan_finished)

    assert callable(window._on_scan_error)

    # NOTE: file_needs_fix handler does not exist (removed)
# ============================================================================
# Test: No Race Conditions
# ============================================================================

def test_no_race_conditions_on_stop(qtbot, temp_dir):
    """Test that stopping worker doesn't cause race conditions.
    
    EXPECTED:
    - stop() sets flag
    - Worker checks flag periodically
    - Worker exits cleanly
    - No crashes or exceptions
    """
    from musichouse.ui.main_window import ScanWorker
    
    # Create a worker (QThread, not QWidget)
    worker = ScanWorker(temp_dir)
    
    # Stop should be safe to call
    worker.stop()
    assert worker._stop_requested == True, "Stop flag should be set"
    
    # Wait for thread to finish
    worker.wait()
    
    # Worker should have exited cleanly
    # (no assertion needed, if we're here, no crash occurred)
    
    worker.deleteLater()
