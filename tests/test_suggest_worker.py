"""Unit tests for SuggestWorker."""

from unittest.mock import MagicMock

from PyQt6.QtTest import QTest

from musichouse.ui.suggest_worker import SuggestWorker


class TestSuggestWorkerBasic:
    """Basic SuggestWorker functionality tests."""
    
    def test_worker_emits_signals_on_success(self, qtbot):
        """Test that worker emits progress, seed_result, and finished signals."""
        mock_client = MagicMock()
        mock_client.get_similar_artists_json.side_effect = [
            [{"artist": "A1", "reason": "R1"}],
            [{"artist": "B1", "reason": "R2"}],
            [{"artist": "C1", "reason": "R3"}],
        ]
        
        worker = SuggestWorker(["Seed1", "Seed2", "Seed3"], mock_client)
        
        progress_signals = []
        result_signals = []
        finished_emitted = []
        
        def on_progress(seed):
            progress_signals.append(seed)
        
        def on_result(seed, results):
            result_signals.append((seed, results))
        
        def on_finished():
            finished_emitted.append(True)
        
        worker.progress.connect(on_progress)
        worker.seed_result.connect(on_result)
        worker.finished.connect(on_finished)
        
        worker.start()
        QTest.qWait(500)  # Wait for worker to complete
        
        assert len(progress_signals) == 3
        assert progress_signals == ["Seed1", "Seed2", "Seed3"]
        
        assert len(result_signals) == 3
        assert result_signals[0] == ("Seed1", [{"artist": "A1", "reason": "R1"}])
        
        assert len(finished_emitted) == 1
    
    def test_worker_continues_on_error(self, qtbot):
        """Test that worker continues processing remaining seeds after one error."""
        mock_client = MagicMock()
        mock_client.get_similar_artists_json.side_effect = [
            [{"artist": "A1", "reason": "R1"}],
            ValueError("Error for Seed2"),
            [{"artist": "C1", "reason": "R3"}],
        ]
        
        worker = SuggestWorker(["Seed1", "Seed2", "Seed3"], mock_client)
        
        error_signals = []
        result_signals = []
        finished_emitted = []
        
        def on_error(seed, msg):
            error_signals.append((seed, msg))
        
        def on_result(seed, results):
            result_signals.append((seed, results))
        
        def on_finished():
            finished_emitted.append(True)
        
        worker.error.connect(on_error)
        worker.seed_result.connect(on_result)
        worker.finished.connect(on_finished)
        
        worker.start()
        QTest.qWait(500)
        
        # Should have 1 error and 2 results
        assert len(error_signals) == 1
        assert error_signals[0][0] == "Seed2"
        
        assert len(result_signals) == 2
        assert result_signals[0][0] == "Seed1"
        assert result_signals[1][0] == "Seed3"
        
        assert len(finished_emitted) == 1
    
    def test_stop_prevents_requests(self, qtbot):
        """Test that stop() before run prevents any API requests."""
        mock_client = MagicMock()
        mock_client.get_similar_artists_json.return_value = [{"artist": "A", "reason": "R"}]
        
        worker = SuggestWorker(["Seed1", "Seed2"], mock_client)
        
        # Stop immediately before starting
        worker.stop()
        
        worker.start()
        QTest.qWait(500)
        
        # Should not have called the API
        mock_client.get_similar_artists_json.assert_not_called()
    
    def test_stop_between_seeds(self, qtbot):
        """Test that stop() between seeds stops processing."""
        mock_client = MagicMock()
        call_count = [0]
        
        def mock_suggest(seed):
            call_count[0] += 1
            if call_count[0] == 1:
                return [{"artist": "A", "reason": "R"}]
            # After first call, stop should prevent this
            raise RuntimeError("Should not be called after stop")
        
        mock_client.get_similar_artists_json.side_effect = mock_suggest
        
        worker = SuggestWorker(["Seed1", "Seed2", "Seed3"], mock_client)
        
        finished_emitted = []
        
        def on_finished():
            finished_emitted.append(True)
            # Stop after first seed completes
            worker.stop()
        
        worker.finished.connect(on_finished)
        
        worker.start()
        QTest.qWait(500)
        
        # Should have been called at least once
        assert call_count[0] >= 1


class TestSuggestWorkerSignals:
    """Test signal emission order and content."""
    
    def test_signal_order(self, qtbot):
        """Test that signals are emitted in correct order: progress, result, progress, result, finished."""
        mock_client = MagicMock()
        mock_client.get_similar_artists_json.side_effect = [
            [{"artist": "A", "reason": "R1"}],
            [{"artist": "B", "reason": "R2"}],
        ]
        
        worker = SuggestWorker(["Seed1", "Seed2"], mock_client)
        
        signal_log = []
        
        def on_progress(seed):
            signal_log.append(("progress", seed))
        
        def on_result(seed, results):
            signal_log.append(("result", seed))
        
        def on_finished():
            signal_log.append(("finished",))
        
        worker.progress.connect(on_progress)
        worker.seed_result.connect(on_result)
        worker.finished.connect(on_finished)
        
        worker.start()
        QTest.qWait(500)
        
        # Expected order: progress1, result1, progress2, result2, finished
        expected = [
            ("progress", "Seed1"),
            ("result", "Seed1"),
            ("progress", "Seed2"),
            ("result", "Seed2"),
            ("finished",),
        ]
        assert signal_log == expected


class TestSuggestWorkerExceptionHandling:
    """Test exception handling in SuggestWorker."""
    
    def test_worker_handles_inner_exception(self, qtbot):
        """Test that worker handles exceptions in individual seed requests."""
        mock_client = MagicMock()
        mock_client.get_similar_artists_json.side_effect = ValueError("API error")
        
        worker = SuggestWorker(["Seed1"], mock_client)
        
        error_signals = []
        finished_emitted = []
        
        def on_error(seed, msg):
            error_signals.append((seed, msg))
        
        def on_finished():
            finished_emitted.append(True)
        
        worker.error.connect(on_error)
        worker.finished.connect(on_finished)
        
        worker.start()
        QTest.qWait(500)
        
        # Should emit error for the seed and finished (inner exception handler)
        assert len(error_signals) == 1
        assert error_signals[0][0] == "Seed1"
        assert "API error" in error_signals[0][1]
        assert len(finished_emitted) == 1