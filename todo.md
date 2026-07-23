# MusicHouse — TODO

## Performance

### P1. Parallelize MP3 tag reading (ThreadPoolExecutor)
- **File:** `src/musichouse/ui/main_window.py` — `ScanWorker.run()`, phase 2 loop (~line 134-212)
- **Approach:** `ThreadPoolExecutor(max_workers=12)` with `executor.map(self._process_single_file, files_to_process)`
- **Batch size:** 32-64 files per batch, collect results, emit progress
- **eyed3 is thread-safe** (stateless `load()`, C extension releases GIL, no shared state)
- **DB safe:** `LeaderboardCache` already uses `threading.local()` + WAL mode
- **Only phase 2** — phase 1 (`os.walk`) stays sequential
- **Expected speedup:** 3-5x (8000 files: ~15 min → ~3-5 min)
- **Risks:** disk contention (mitigate: modest worker count), Qt signal frequency (mitigate: batch progress emits)
- [ ] Extract `_process_single_file(file_path)` method from current inline loop
- [ ] Replace sequential loop with `ThreadPoolExecutor` map
- [ ] Batch progress signals every 32 files instead of every 10
- [ ] Test with 100+ files, verify no crashes

## Tests

### T1. Rewrite `tests/test_scanner.py` (CRITICAL — 0% coverage)
- **Source:** `src/musichouse/scanner.py`
- **Cover:** `scan()` with exclude_dirs, recursive walk, `stop()` mid-scan, `OSError` handling, callback batch emission at 100-file intervals
- **Old file was corrupted** — rewrite from scratch with `tmp_path` fixtures and mock filesystem
- [ ] Test scan finds .mp3 files recursively
- [ ] Test exclude_dirs filtering (.git, node_modules)
- [ ] Test stop() halts scan cleanly
- [ ] Test OSError on inaccessible directory is recorded in get_errors()
- [ ] Test file_callback fires every 100 files

### T2. Rewrite `tests/ui/test_fixer_tab.py` (CRITICAL — 0% coverage)
- **Source:** `src/musichouse/ui/fixer_tab.py`
- **Cover:** UserRole data-index mapping under active filter (regression test for CRITICAL wrong-file bug), `fix_selected`/`auto_fix_all` data flow, `load_from_scan` DB query, `_mark_failed_row` color logic
- **Old tests tested sorting (now disabled)** — rewrite focuses on index mapping + worker handoff
- [ ] Test UserRole mapping: populate table → apply filter → check non-contiguous rows → fix_selected → assert correct files
- [ ] Test load_from_scan loads only needs_fixing=1 rows
- [ ] Test auto_fix_all passes edited values (current_artist) not suggested values
- [ ] Test _mark_failed_row with error_type="corrupted"/"locked"/"readonly"
- [ ] Test empty files list early return

### T3. Create `tests/test_tag_fix_worker.py` (CRITICAL — 0% coverage)
- **Source:** `src/musichouse/ui/tag_fix_worker.py`
- **Cover:** `TagFixWorker.run()` success/failure/cancel, cache-match skip, `finished` ALWAYS emits (regression test for UI-hang bug)
- [ ] Test write_tags raising mid-batch → loop continues, finished still emits
- [ ] Test write_tags returns False → failure recorded with error type
- [ ] Test cancel() mid-run → loop breaks, finished emits
- [ ] Test cache-match skip: seed cache with matching tag_data → write_tags not called
- [ ] Test cache-mismatch: seed cache with wrong tag_data → write_tags called with force=True

### T4. Rewrite `tests/ui/test_main_window.py` (CRITICAL — 0% coverage)
- **Source:** `src/musichouse/ui/main_window.py`
- **Cover:** `ScanWorker.run()` 3-phase flow, all 10 signal handlers, pause/resume/stop, closeEvent
- **Old version had QThread timeouts** — rewrite with mocked MP3Scanner/LeaderboardCache + signal spies
- [ ] Test phase 1 → phase 1.5 (incremental filter) → phase 2 (tag read) → phase 3 (cache bulk insert)
- [ ] Test scan_stats emits correct new/modified/skipped counts
- [ ] Test empty-result early return path
- [ ] Test tag_data JSON serialization in bulk INSERT
- [ ] Test suggested_artist/suggested_title computed via parse_filename
- [ ] Test pause → resume → stop (no deadlock)
- [ ] Test stop while paused exits cleanly

### T5. Expand `tests/test_config.py` (HIGH — currently 5% coverage, 3 trivial tests)
- **Source:** `src/musichouse/config.py`
- **Cover:** `save_config` round-trip with exclude_dirs (regression test), `_save_config` validation, `load_config` merge, keyring ops (mocked), setters/getters
- [ ] Test save_config preserves exclude_dirs (regression for duplicate-body bug)
- [ ] Test save_config raises ValueError on missing endpoint/model
- [ ] Test save_config raises ValueError on empty endpoint/model
- [ ] Test load_config merges with DEFAULT_CONFIG
- [ ] Test load_config handles invalid JSON
- [ ] Test all setters (set_endpoint, set_model, set_api_key, set_last_directory, set_exclude_dirs)

### T6. Create `tests/test_error_handling.py` (MEDIUM — 0% coverage)
- **Source:** `src/musichouse/error_handling.py`
- **Cover:** Instantiate each of 12 exception classes, verify file_path/reason/suggestion attributes
- [ ] Test CorruptedFileError, FileLockedError, ReadOnlyFileError custom __init__
- [ ] Test all exceptions inherit from MusicHouseError
- [ ] Test write_tags actually raises these typed errors (contract verification)

## UX Improvements

### UX1. Fixed files feedback (P1)
- **Problem:** Fixed files vanish from table silently — user loses sense of accomplishment
- **File:** `src/musichouse/ui/fixer_tab.py` — `_remove_fixed_rows()`
- **Fix:** Show a temporary success toast/notification "X files fixed successfully" or move fixed files to a collapsible "Recently Fixed" section
- [ ] Implement success counter or toast after fix completes

### UX2. AI tab setup guidance (P1)
- **Problem:** AI features are useless until complex API setup is done in a separate dialog
- **File:** `src/musichouse/ui/ai_tab.py`
- **Fix:** Add "Configure API" button directly in AITab that opens SettingsDialog; add setup guide tooltip
- [ ] Add CTA button in AI tab empty state

### UX3. Undo last fix (P1)
- **Problem:** No way to revert a tag fix if the suggestion was wrong
- **File:** `src/musichouse/ui/fixer_tab.py`, `src/musichouse/tag_writer.py`
- **Fix:** Store original tag values before writing; add "Revert Last Fix" button
- [ ] Implement backup of original artist/title before write_tags
- [ ] Add revert button that restores previous values

### UX4. Error color legend (P2)
- **Problem:** Failed rows are colored but there's no legend explaining what each color means
- **File:** `src/musichouse/ui/fixer_tab.py`
- **Fix:** Add a small QLabel at the bottom: "🔴 Corrupted  🟠 Locked  🟡 Read-only"
- [ ] Add legend widget

### UX5. Leaderboard empty state CTA (P2)
- **Problem:** "No scan data yet" is the only info shown when DB is empty
- **File:** `src/musichouse/ui/leaderboard_tab.py`
- **Fix:** Add "Start New Scan" button in the empty state that triggers the scan dialog
- [ ] Add CTA button in empty state

### UX6. Leaderboard → Fixer interaction (P2)
- **Problem:** Can't click an artist in the leaderboard to see their files in the Fixer tab
- **Files:** `src/musichouse/ui/leaderboard_tab.py`, `src/musichouse/ui/fixer_tab.py`
- **Fix:** Make leaderboard rows clickable → switch to Fixer tab filtered by that artist
- [ ] Implement cross-tab artist filter

### UX7. Search filter performance (P2)
- **Problem:** Table is cleared and rebuilt on every keystroke in the search box
- **File:** `src/musichouse/ui/fixer_tab.py` — `_apply_filter()`
- **Fix:** Use `QSortFilterProxyModel` instead of manual `setRowCount(0)` + rebuild
- [ ] Refactor filter to use proxy model

### UX8. About dialog polish (P3)
- **Problem:** Basic `QMessageBox.about` feels unpolished
- **File:** `src/musichouse/ui/main_window.py`
- **Fix:** Custom AboutDialog with logo and project link
- [ ] Create custom about dialog

## Code Quality

### CQ1. Duplicated query block in fixer_tab.py
- **File:** `src/musichouse/ui/fixer_tab.py` — lines 134-145 build a cursor that's immediately overwritten at 155-164
- **Fix:** Remove the first unused query block
- [ ] Audit and remove dead query code

### CQ2. Dead code: `update_scan_cache()` in leaderboard_cache.py
- **File:** `src/musichouse/leaderboard_cache.py:195`
- Never called from production — scan worker uses inline SQL instead
- **Fix:** Either call it from ScanWorker (replacing inline SQL) or remove it
- [ ] Decide: integrate or remove

### CQ3. Dead code: `_load_file_entry()` and `add_file_entry()` in fixer_tab.py
- **File:** `src/musichouse/ui/fixer_tab.py:295, 327`
- Never called — suggestions are now computed during scan (H2 fix)
- **Fix:** Remove if confirmed unused
- [ ] Remove dead methods

### CQ4. Sorting disabled in FixerTab
- **File:** `src/musichouse/ui/fixer_tab.py:84`
- Disabled to prevent a critical bug — huge UX hit
- **Fix:** Re-enable sorting now that UserRole index mapping is in place (C1 fix)
- [ ] Test sorting with UserRole mapping
- [ ] Re-enable column sorting if safe
