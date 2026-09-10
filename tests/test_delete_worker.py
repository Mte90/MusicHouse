"""Unit tests for delete_worker module.

Tests for DeleteWorker QThread worker.
"""

from unittest.mock import patch

from musichouse.ui.delete_worker import DeleteWorker

# ============================================================================
# DeleteWorker Tests
# ============================================================================

class TestDeleteWorker:
    """Tests for DeleteWorker class."""

    def test_run_deletes_files_successfully(self, temp_dir, qapp):
        """Test that DeleteWorker successfully deletes files that exist."""
        # Create mock MP3 files
        mp3_files = []
        for i in range(3):
            mp3_file = temp_dir / f"Track {i}.mp3"
            mp3_file.write_bytes(b"fake mp3 data")
            mp3_files.append(mp3_file)

        paths = [str(p) for p in mp3_files]
        file_deleted_args = []
        deletion_finished_args = []

        def on_file_deleted(path, success, error):
            file_deleted_args.append((path, success, error))

        def on_finished(count):
            deletion_finished_args.append(count)

        worker = DeleteWorker(paths)
        worker.file_deleted.connect(on_file_deleted)
        worker.deletion_finished.connect(on_finished)

        worker.run()

        # Verify all files were deleted
        assert len(file_deleted_args) == 3
        for path, success, error in file_deleted_args:
            assert success is True
            assert error == ""

        assert len(deletion_finished_args) == 1
        assert deletion_finished_args[0] == 3

        # Verify files are actually deleted
        for mp3_file in mp3_files:
            assert not mp3_file.exists()

    def test_run_handles_missing_files(self, temp_dir, qapp):
        """Test that DeleteWorker handles files that don't exist."""
        # Create one file, one doesn't exist
        existing_file = temp_dir / "existing.mp3"
        existing_file.write_bytes(b"fake mp3 data")

        paths = [
            str(existing_file),
            str(temp_dir / "nonexistent.mp3"),
        ]

        file_deleted_args = []
        deletion_finished_args = []

        def on_file_deleted(path, success, error):
            file_deleted_args.append((path, success, error))

        def on_finished(count):
            deletion_finished_args.append(count)

        worker = DeleteWorker(paths)
        worker.file_deleted.connect(on_file_deleted)
        worker.deletion_finished.connect(on_finished)

        worker.run()

        # Verify signals emitted correctly
        assert len(file_deleted_args) == 2

        # First file (exists) - success
        assert file_deleted_args[0][0] == str(existing_file)
        assert file_deleted_args[0][1] is True
        assert file_deleted_args[0][2] == ""

        # Second file (doesn't exist) - failure with error message
        assert "nonexistent.mp3" in file_deleted_args[1][0]
        assert file_deleted_args[1][1] is False
        assert file_deleted_args[1][2] == "File not found"

        assert deletion_finished_args[0] == 1

    def test_run_stops_on_stop_flag(self, temp_dir, qapp):
        """Test that DeleteWorker respects the stop flag."""
        # Create mock MP3 files
        mp3_files = []
        for i in range(5):
            mp3_file = temp_dir / f"Track {i}.mp3"
            mp3_file.write_bytes(b"fake mp3 data")
            mp3_files.append(mp3_file)

        paths = [str(p) for p in mp3_files]
        file_deleted_args = []
        deletion_finished_args = []

        def on_file_deleted(path, success, error):
            file_deleted_args.append((path, success, error))
            # Stop after 2 files
            if len(file_deleted_args) == 2:
                worker.stop()

        def on_finished(count):
            deletion_finished_args.append(count)

        worker = DeleteWorker(paths)
        worker.file_deleted.connect(on_file_deleted)
        worker.deletion_finished.connect(on_finished)

        worker.run()

        # Verify worker stopped after 2 files
        assert len(file_deleted_args) == 2
        assert len(deletion_finished_args) == 1
        assert deletion_finished_args[0] == 2

    def test_run_uses_send2trash_when_available(self, temp_dir, qapp):
        """Test that DeleteWorker uses send2trash when it's installed."""
        mp3_file = temp_dir / "track.mp3"
        mp3_file.write_bytes(b"fake mp3 data")

        paths = [str(mp3_file)]
        file_deleted_args = []

        def on_file_deleted(path, success, error):
            file_deleted_args.append((path, success, error))

        # Mock _try_delete to simulate send2trash success
        with patch.object(DeleteWorker, '_try_delete', return_value=(True, "")) as mock_try_delete:
            worker = DeleteWorker(paths)
            worker.file_deleted.connect(on_file_deleted)
            worker.run()

            # Verify _try_delete was called
            mock_try_delete.assert_called_once()
            assert file_deleted_args[0][1] is True

    def test_run_falls_back_to_os_remove_when_send2trash_unavailable(self, temp_dir, qapp):
        """Test that DeleteWorker falls back to os.remove when send2trash ImportError."""
        mp3_file = temp_dir / "track.mp3"
        mp3_file.write_bytes(b"fake mp3 data")

        paths = [str(mp3_file)]
        file_deleted_args = []

        def on_file_deleted(path, success, error):
            file_deleted_args.append((path, success, error))

        # Mock _try_delete to simulate send2trash ImportError and os.remove success
        with patch.object(DeleteWorker, '_try_delete', return_value=(True, "")):
            worker = DeleteWorker(paths)
            worker.file_deleted.connect(on_file_deleted)
            worker.run()

            assert file_deleted_args[0][1] is True

    def test_run_handles_send2trash_error(self, temp_dir, qapp):
        """Test that DeleteWorker handles send2trash error and continues."""
        mp3_file = temp_dir / "track.mp3"
        mp3_file.write_bytes(b"fake mp3 data")

        paths = [str(mp3_file)]
        file_deleted_args = []

        def on_file_deleted(path, success, error):
            file_deleted_args.append((path, success, error))

        # Mock _try_delete to simulate send2trash error
        with patch.object(DeleteWorker, '_try_delete', return_value=(False, "trash error")):
            worker = DeleteWorker(paths)
            worker.file_deleted.connect(on_file_deleted)
            worker.run()

            # Verify error was reported
            assert file_deleted_args[0][1] is False
            assert "trash error" in file_deleted_args[0][2]

    def test_run_handles_os_remove_error(self, temp_dir, qapp):
        """Test that DeleteWorker handles os.remove error gracefully."""
        mp3_file = temp_dir / "protected.mp3"
        mp3_file.write_bytes(b"fake mp3 data")

        paths = [str(mp3_file)]
        file_deleted_args = []

        def on_file_deleted(path, success, error):
            file_deleted_args.append((path, success, error))

        # Mock _try_delete to simulate os.remove error
        with patch.object(DeleteWorker, '_try_delete', return_value=(False, "permission denied")):
            worker = DeleteWorker(paths)
            worker.file_deleted.connect(on_file_deleted)
            worker.run()

            # Verify error was reported
            assert file_deleted_args[0][1] is False
            assert "permission denied" in file_deleted_args[0][2]

    def test_run_empty_path_list(self, temp_dir, qapp):
        """Test that DeleteWorker handles empty path list correctly."""
        paths = []
        file_deleted_args = []
        deletion_finished_args = []

        def on_file_deleted(path, success, error):
            file_deleted_args.append((path, success, error))

        def on_finished(count):
            deletion_finished_args.append(count)

        worker = DeleteWorker(paths)
        worker.file_deleted.connect(on_file_deleted)
        worker.deletion_finished.connect(on_finished)

        worker.run()

        # Verify no file_deleted signals but deletion_finished was emitted
        assert len(file_deleted_args) == 0
        assert len(deletion_finished_args) == 1
        assert deletion_finished_args[0] == 0

    def test_run_mixed_success_failure(self, temp_dir, qapp):
        """Test DeleteWorker with mix of successful and failed deletions."""
        # Create some files
        existing_file = temp_dir / "existing.mp3"
        existing_file.write_bytes(b"fake mp3 data")

        paths = [
            str(existing_file),
            str(temp_dir / "missing1.mp3"),
            str(temp_dir / "missing2.mp3"),
        ]

        file_deleted_args = []
        deletion_finished_args = []

        def on_file_deleted(path, success, error):
            file_deleted_args.append((path, success, error))

        def on_finished(count):
            deletion_finished_args.append(count)

        worker = DeleteWorker(paths)
        worker.file_deleted.connect(on_file_deleted)
        worker.deletion_finished.connect(on_finished)

        worker.run()

        # Verify correct results
        assert len(file_deleted_args) == 3
        assert file_deleted_args[0][1] is True  # existing
        assert file_deleted_args[1][1] is False  # missing1
        assert file_deleted_args[2][1] is False  # missing2
        assert deletion_finished_args[0] == 1

    def test_run_uses_send2trash_success_path(self, temp_dir, qapp):
        """Test that DeleteWorker successfully uses send2trash when available (covers lines 53-58)."""
        mp3_file = temp_dir / "track.mp3"
        mp3_file.write_bytes(b"fake mp3 data")

        paths = [str(mp3_file)]
        file_deleted_args = []

        def on_file_deleted(path, success, error):
            file_deleted_args.append((path, success, error))

        # Mock send2trash import to succeed - patch where it's imported FROM
        import send2trash
        with patch.object(send2trash, 'send2trash', return_value=None):
            worker = DeleteWorker(paths)
            worker.file_deleted.connect(on_file_deleted)
            worker.run()

            # Verify send2trash path succeeded
            assert len(file_deleted_args) == 1
            assert file_deleted_args[0][1] is True
            assert file_deleted_args[0][2] == ""

    def test_run_send2trash_falls_back_to_os_remove_on_error(self, temp_dir, qapp):
        """Test that DeleteWorker falls back to os.remove when send2trash fails."""
        mp3_file = temp_dir / "track.mp3"
        mp3_file.write_bytes(b"fake mp3 data")

        paths = [str(mp3_file)]
        file_deleted_args = []

        def on_file_deleted(path, success, error):
            file_deleted_args.append((path, success, error))

        # Mock send2trash import to fail, but os.remove succeeds
        import send2trash
        with patch.object(send2trash, 'send2trash', side_effect=Exception("send2trash failed")):
            worker = DeleteWorker(paths)
            worker.file_deleted.connect(on_file_deleted)
            worker.run()

            # Should fall back to os.remove and succeed
            assert len(file_deleted_args) == 1
            assert file_deleted_args[0][1] is True
            assert file_deleted_args[0][2] == ""

    def test_run_both_send2trash_and_os_remove_fail(self, temp_dir, qapp):
        """Test DeleteWorker when both send2trash and os.remove fail (covers lines 66-68)."""
        mp3_file = temp_dir / "protected.mp3"
        mp3_file.write_bytes(b"fake mp3 data")

        paths = [str(mp3_file)]
        file_deleted_args = []

        def on_file_deleted(path, success, error):
            file_deleted_args.append((path, success, error))

        # Mock both send2trash and os.remove to fail
        import send2trash
        with patch.object(send2trash, 'send2trash', side_effect=Exception("send2trash failed")), \
             patch("os.remove", side_effect=Exception("permission denied")):
            worker = DeleteWorker(paths)
            worker.file_deleted.connect(on_file_deleted)
            worker.run()

            # Both failed, should report error
        assert len(file_deleted_args) == 1
        assert file_deleted_args[0][1] is False
        assert "permission denied" in file_deleted_args[0][2]

    def test_run_importerror_fallback_when_send2trash_not_installed(self, temp_dir, qapp):
        """Test that ImportError path (lines 49-50) is covered when send2trash is not installed."""
        mp3_file = temp_dir / "track.mp3"
        mp3_file.write_bytes(b"fake mp3 data")

        file_deleted_args = []
        deletion_finished_args = []

        def on_file_deleted(path, success, error):
            file_deleted_args.append((path, success, error))

        def on_finished(count):
            deletion_finished_args.append(count)

        # Patch send2trash import to fail
        with patch.dict("sys.modules", {"send2trash": None}):
            # Force reimport to trigger ImportError
            import importlib

            import musichouse.ui.delete_worker
            importlib.reload(musichouse.ui.delete_worker)
            
            worker = musichouse.ui.delete_worker.DeleteWorker([str(mp3_file)])
            worker.file_deleted.connect(on_file_deleted)
            worker.deletion_finished.connect(on_finished)
            worker.run()

            # Should fall back to os.remove and succeed
            assert len(file_deleted_args) == 1
            assert file_deleted_args[0][1] is True
            assert file_deleted_args[0][2] == ""