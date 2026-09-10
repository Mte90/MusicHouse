"""Unit tests for apply_worker module.

Tests for ApplyWorker QThread worker.
"""

from unittest.mock import patch

from musichouse.ui.apply_worker import ApplyWorker

# ============================================================================
# ApplyWorker Tests
# ============================================================================

class TestApplyWorker:
    """Tests for ApplyWorker class."""

    def test_run_moves_files_successfully(self, temp_dir, qapp):
        """Test that ApplyWorker successfully moves files."""
        # Create source file
        src_file = temp_dir / "track.mp3"
        src_file.write_bytes(b"fake mp3 data")

        dst_file = temp_dir / "dest" / "track.mp3"

        actions = [
            {"type": "move", "from": str(src_file), "to": str(dst_file)},
        ]

        file_applied_args = []
        apply_finished_args = []

        def on_file_applied(path, success, error):
            file_applied_args.append((path, success, error))

        def on_finished(count):
            apply_finished_args.append(count)

        worker = ApplyWorker(actions)
        worker.file_applied.connect(on_file_applied)
        worker.apply_finished.connect(on_finished)

        worker.run()

        # Verify signal emitted correctly
        assert len(file_applied_args) == 1
        assert file_applied_args[0][0] == str(src_file)
        assert file_applied_args[0][1] is True
        assert file_applied_args[0][2] == ""

        assert len(apply_finished_args) == 1
        assert apply_finished_args[0] == 1

        # Verify file was actually moved
        assert not src_file.exists()
        assert dst_file.exists()

    def test_run_renames_files_successfully(self, temp_dir, qapp):
        """Test that ApplyWorker successfully renames files."""
        # Create source file
        src_file = temp_dir / "oldname.mp3"
        src_file.write_bytes(b"fake mp3 data")

        dst_file = temp_dir / "newname.mp3"

        actions = [
            {"type": "rename", "from": str(src_file), "to": str(dst_file)},
        ]

        file_applied_args = []
        apply_finished_args = []

        def on_file_applied(path, success, error):
            file_applied_args.append((path, success, error))

        def on_finished(count):
            apply_finished_args.append(count)

        worker = ApplyWorker(actions)
        worker.file_applied.connect(on_file_applied)
        worker.apply_finished.connect(on_finished)

        worker.run()

        # Verify signal emitted correctly
        assert len(file_applied_args) == 1
        assert file_applied_args[0][0] == str(src_file)
        assert file_applied_args[0][1] is True
        assert file_applied_args[0][2] == ""

        assert len(apply_finished_args) == 1
        assert apply_finished_args[0] == 1

        # Verify file was actually renamed
        assert not src_file.exists()
        assert dst_file.exists()

    def test_run_creates_destination_directory(self, temp_dir, qapp):
        """Test that ApplyWorker creates destination directory for move actions."""
        # Create source file
        src_file = temp_dir / "track.mp3"
        src_file.write_bytes(b"fake mp3 data")

        # Destination with non-existent parent dirs
        dst_file = temp_dir / "level1" / "level2" / "track.mp3"

        actions = [
            {"type": "move", "from": str(src_file), "to": str(dst_file)},
        ]

        file_applied_args = []
        apply_finished_args = []

        def on_file_applied(path, success, error):
            file_applied_args.append((path, success, error))

        def on_finished(count):
            apply_finished_args.append(count)

        worker = ApplyWorker(actions)
        worker.file_applied.connect(on_file_applied)
        worker.apply_finished.connect(on_finished)

        worker.run()

        # Verify success
        assert len(file_applied_args) == 1
        assert file_applied_args[0][1] is True

        assert len(apply_finished_args) == 1
        assert apply_finished_args[0] == 1

        # Verify directories were created and file moved
        assert (temp_dir / "level1" / "level2").exists()
        assert dst_file.exists()

    def test_run_handles_source_not_found(self, temp_dir, qapp):
        """Test that ApplyWorker handles source file that doesn't exist."""
        actions = [
            {"type": "move", "from": str(temp_dir / "nonexistent.mp3"), "to": str(temp_dir / "dest.mp3")},
        ]

        file_applied_args = []
        apply_finished_args = []

        def on_file_applied(path, success, error):
            file_applied_args.append((path, success, error))

        def on_finished(count):
            apply_finished_args.append(count)

        worker = ApplyWorker(actions)
        worker.file_applied.connect(on_file_applied)
        worker.apply_finished.connect(on_finished)

        worker.run()

        # Verify failure with correct error message
        assert len(file_applied_args) == 1
        assert file_applied_args[0][1] is False
        assert file_applied_args[0][2] == "Source not found"

        assert len(apply_finished_args) == 1
        assert apply_finished_args[0] == 0

    def test_run_stops_on_stop_flag(self, temp_dir, qapp):
        """Test that ApplyWorker respects the stop flag."""
        # Create source files
        src_files = []
        for i in range(5):
            src_file = temp_dir / f"track{i}.mp3"
            src_file.write_bytes(b"fake mp3 data")
            src_files.append(src_file)

        actions = [
            {"type": "move", "from": str(src), "to": str(temp_dir / "dest" / src.name)}
            for src in src_files
        ]

        file_applied_args = []
        apply_finished_args = []

        def on_file_applied(path, success, error):
            file_applied_args.append((path, success, error))
            # Stop after 2 files
            if len(file_applied_args) == 2:
                worker.stop()

        def on_finished(count):
            apply_finished_args.append(count)

        worker = ApplyWorker(actions)
        worker.file_applied.connect(on_file_applied)
        worker.apply_finished.connect(on_finished)

        worker.run()

        # Verify worker stopped after 2 files
        assert len(file_applied_args) == 2
        assert len(apply_finished_args) == 1
        assert apply_finished_args[0] == 2

    def test_run_handles_mixed_success_failure(self, temp_dir, qapp):
        """Test ApplyWorker with mix of successful and failed actions."""
        # Create one file, one doesn't exist
        existing_file = temp_dir / "existing.mp3"
        existing_file.write_bytes(b"fake mp3 data")

        actions = [
            {"type": "move", "from": str(existing_file), "to": str(temp_dir / "dest1.mp3")},
            {"type": "move", "from": str(temp_dir / "missing.mp3"), "to": str(temp_dir / "dest2.mp3")},
            {"type": "rename", "from": str(temp_dir / "missing2.mp3"), "to": str(temp_dir / "dest3.mp3")},
        ]

        file_applied_args = []
        apply_finished_args = []

        def on_file_applied(path, success, error):
            file_applied_args.append((path, success, error))

        def on_finished(count):
            apply_finished_args.append(count)

        worker = ApplyWorker(actions)
        worker.file_applied.connect(on_file_applied)
        worker.apply_finished.connect(on_finished)

        worker.run()

        # Verify correct results
        assert len(file_applied_args) == 3
        assert file_applied_args[0][1] is True  # existing
        assert file_applied_args[1][1] is False  # missing
        assert file_applied_args[2][1] is False  # missing2
        assert file_applied_args[1][2] == "Source not found"
        assert file_applied_args[2][2] == "Source not found"

        assert len(apply_finished_args) == 1
        assert apply_finished_args[0] == 1

    def test_run_empty_action_list(self, temp_dir, qapp):
        """Test that ApplyWorker handles empty action list correctly."""
        actions = []

        file_applied_args = []
        apply_finished_args = []

        def on_file_applied(path, success, error):
            file_applied_args.append((path, success, error))

        def on_finished(count):
            apply_finished_args.append(count)

        worker = ApplyWorker(actions)
        worker.file_applied.connect(on_file_applied)
        worker.apply_finished.connect(on_finished)

        worker.run()

        # Verify no file_applied signals but apply_finished was emitted
        assert len(file_applied_args) == 0
        assert len(apply_finished_args) == 1
        assert apply_finished_args[0] == 0

    def test_run_handles_move_error(self, temp_dir, qapp):
        """Test that ApplyWorker handles move operation error gracefully."""
        # Create source file
        src_file = temp_dir / "track.mp3"
        src_file.write_bytes(b"fake mp3 data")

        actions = [
            {"type": "move", "from": str(src_file), "to": "/root/protected/track.mp3"},
        ]

        file_applied_args = []
        apply_finished_args = []

        def on_file_applied(path, success, error):
            file_applied_args.append((path, success, error))

        def on_finished(count):
            apply_finished_args.append(count)

        # Mock _apply_move to simulate error
        with patch.object(ApplyWorker, '_apply_move', return_value=(False, "permission denied")):
            worker = ApplyWorker(actions)
            worker.file_applied.connect(on_file_applied)
            worker.apply_finished.connect(on_finished)
            worker.run()

            # Verify error was reported
            assert len(file_applied_args) == 1
            assert file_applied_args[0][1] is False
            assert "permission denied" in file_applied_args[0][2]

    def test_run_handles_rename_error(self, temp_dir, qapp):
        """Test that ApplyWorker handles rename operation error gracefully."""
        # Create source file
        src_file = temp_dir / "oldname.mp3"
        src_file.write_bytes(b"fake mp3 data")

        actions = [
            {"type": "rename", "from": str(src_file), "to": str(temp_dir / "newname.mp3")},
        ]

        file_applied_args = []
        apply_finished_args = []

        def on_file_applied(path, success, error):
            file_applied_args.append((path, success, error))

        def on_finished(count):
            apply_finished_args.append(count)

        # Mock _apply_rename to simulate error
        with patch.object(ApplyWorker, '_apply_rename', return_value=(False, "permission denied")):
            worker = ApplyWorker(actions)
            worker.file_applied.connect(on_file_applied)
            worker.apply_finished.connect(on_finished)
            worker.run()

            # Verify error was reported
            assert len(file_applied_args) == 1
            assert file_applied_args[0][1] is False
            assert "permission denied" in file_applied_args[0][2]
    def test_run_handles_unknown_action_type(self, temp_dir, qapp):
        """Test that ApplyWorker handles unknown action type gracefully."""
        # Create source file
        src_file = temp_dir / "track.mp3"
        src_file.write_bytes(b"fake mp3 data")

        actions = [
            {"type": "copy", "from": str(src_file), "to": str(temp_dir / "dest.mp3")},
        ]

        file_applied_args = []
        apply_finished_args = []

        def on_file_applied(path, success, error):
            file_applied_args.append((path, success, error))
        def on_finished(count):
            apply_finished_args.append(count)

        worker = ApplyWorker(actions)
        worker.file_applied.connect(on_file_applied)
        worker.apply_finished.connect(on_finished)

        worker.run()

        # Verify failure with correct error message
        assert len(file_applied_args) == 1
        assert file_applied_args[0][1] is False
        assert "Unknown action type" in file_applied_args[0][2]

        assert len(apply_finished_args) == 1
        assert apply_finished_args[0] == 0

    def test_run_handles_missing_src_or_dst(self, temp_dir, qapp):
        """Test that ApplyWorker handles actions with missing src or dst."""
        actions = [
            {"type": "move", "from": str(temp_dir / "track.mp3")},  # missing "to"
            {"type": "rename", "to": str(temp_dir / "new.mp3")},  # missing "from"
        ]

        file_applied_args = []
        apply_finished_args = []

        def on_file_applied(path, success, error):
            file_applied_args.append((path, success, error))

        def on_finished(count):
            apply_finished_args.append(count)

        worker = ApplyWorker(actions)
        worker.file_applied.connect(on_file_applied)
        worker.apply_finished.connect(on_finished)

        worker.run()

        # Verify both actions failed with correct error
        assert len(file_applied_args) == 2
        for path, success, error in file_applied_args:
            assert success is False
            assert "Invalid action" in error

        assert len(apply_finished_args) == 1
        assert apply_finished_args[0] == 0

    def test_run_apply_move_error_path(self, temp_dir, qapp):
        """Test that _apply_move error path (lines 59-61) is covered."""
        src_file = temp_dir / "track.mp3"
        src_file.write_bytes(b"fake mp3 data")

        dst_file = temp_dir / "dest.mp3"

        actions = [
            {"type": "move", "from": str(src_file), "to": str(dst_file)},
        ]

        file_applied_args = []
        apply_finished_args = []

        def on_file_applied(path, success, error):
            file_applied_args.append((path, success, error))

        def on_finished(count):
            apply_finished_args.append(count)

        # Mock shutil.move to simulate error (e.g., permission denied)
        with patch("musichouse.ui.apply_worker.shutil.move", side_effect=Exception("move failed")):
            worker = ApplyWorker(actions)
            worker.file_applied.connect(on_file_applied)
            worker.apply_finished.connect(on_finished)
            worker.run()

            # Verify error was reported
            assert len(file_applied_args) == 1
            assert file_applied_args[0][1] is False
            assert "move failed" in file_applied_args[0][2]

    def test_run_apply_rename_error_path(self, temp_dir, qapp):
        """Test that _apply_rename error path (lines 72-74) is covered."""
        src_file = temp_dir / "oldname.mp3"
        src_file.write_bytes(b"fake mp3 data")

        dst_file = temp_dir / "newname.mp3"

        actions = [
            {"type": "rename", "from": str(src_file), "to": str(dst_file)},
        ]

        file_applied_args = []
        apply_finished_args = []

        def on_file_applied(path, success, error):
            file_applied_args.append((path, success, error))

        def on_finished(count):
            apply_finished_args.append(count)

        # Mock Path.rename to simulate error
        with patch("pathlib.Path.rename", side_effect=Exception("rename failed")):
            worker = ApplyWorker(actions)
            worker.file_applied.connect(on_file_applied)
            worker.apply_finished.connect(on_finished)
            worker.run()

            # Verify error was reported
            assert len(file_applied_args) == 1
            assert file_applied_args[0][1] is False
            assert "rename failed" in file_applied_args[0][2]