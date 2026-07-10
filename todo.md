# MusicHouse — Fix Plan

Generated from UX + performance + tag-write + cross-cutting + crash-safety + parser + edge-case + developer-hygiene + security + dead-code verification. 9 phases, 76 tasks.

**Legend:** `[independent]` = no deps · `[depends on T<N>]` = runs after · Agent = who executes

---

## Phase 1 — Data Integrity (critical, do first)

Small surgical fixes that prevent data loss and broken features.

### T1: Fix sort-corruption bug — migrate Fixer table to model/view
- **Agent:** @fixer
- **Skills:** `pyqt-widgets`, `pyqt-threading`
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/ui/fixer_tab.py` — replace `QTableWidget` with `QTableView` + `QAbstractTableModel` + `QSortFilterProxyModel`; fix `get_selected_files` (348), `_on_cell_changed` (358), `fix_selected` (370) to use model indices not view rows
- **Files NOT to touch:** `main_window.py`, `ai_tab.py`
- **Problem:** Sorting enabled but `_files_data` never reorders → tags written to wrong files after sort (`fixer_tab.py:68`)
- **Acceptance:** sorting by any column then checking a box + "Fix Selected" writes to the correct file; verify with a fixture of 5 MP3s
- **Verify:** `pytest tests/ -v` + manual sort+fix test
- **Risk:** medium — touches the primary screen; must preserve checkbox/edit behavior

### T2: Add missing `import eyed3` in main_window
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/ui/main_window.py:1-23` — add `import eyed3` to imports
- **Problem:** `eyed3.load()` at line 132 raises `NameError`, caught by bare except → every file flagged broken
- **Acceptance:** scan a tagged MP3 → it appears with correct artist/title, `needs_fixing=0`
- **Verify:** `pytest tests/ -v`
- **Risk:** low — one import line

### T3: Populate `_artist_counts` and emit `artist_count_updated` signal
- **Agent:** @fixer
- **Skills:** `pyqt-threading`
- **Depends on:** T2 `[depends on T2]`
- **Files to modify:**
  - `src/musichouse/ui/main_window.py` — in `ScanWorker.run()` (58-235): count artists from parsed tags into `self._artist_counts`; emit `artist_count_updated` signal (declared at :43, never emitted) during throttled updates (around :547) and on completion
- **Files NOT to touch:** `leaderboard_tab.py` (already consumes the signal correctly)
- **Problem:** `_artist_counts` initialized `{}` (:56), emitted empty (:224) → leaderboard never populates
- **Acceptance:** after scan, Leaderboard tab shows artists with counts
- **Verify:** `pytest tests/ -v`
- **Risk:** low — data already flows, just never collected

### T4: Fix Pause button — actually wait on `_pause_event`
- **Agent:** @fixer
- **Skills:** `pyqt-threading`
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/ui/main_window.py` `ScanWorker.run()` — add `self._pause_event.wait()` check inside the per-file loop (after the `_stop_requested` check, around :90)
- **Problem:** `_pause_event` created (:51), set/cleared by `pause()`/`resume()` (236-246), but `wait()` never called → scan continues while UI says "paused"
- **Acceptance:** click Pause → scan stops; click Resume → scan continues
- **Verify:** manual test
- **Risk:** low

---

## Phase 2 — Threading & Error Surfacing (kills UI freezes)

Move blocking work off the GUI thread; surface errors to the user.

### T5: Move AI calls to a QThread worker
- **Agent:** @fixer
- **Skills:** `pyqt-threading`
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/ui/ai_tab.py` — extract `_get_similar_artists` (143-145) body into a `QThread`/worker `QObject` with `finished`, `progress`, `error` signals; connect in `ai_tab`; show loading state; disable button during work
- **Files NOT to touch:** `ai_client.py` (keep the client synchronous; the worker wraps it)
- **Problem:** two sequential 30s `urllib` calls on GUI thread → 60s freeze
- **Acceptance:** clicking "Get Similar Artists" does not freeze UI; cancel button stops the request
- **Verify:** manual test with a slow endpoint
- **Risk:** medium — signal/slot wiring

### T6: Move tag writes (fix_selected / auto_fix_all) to a QThread worker
- **Agent:** @fixer
- **Skills:** `pyqt-threading`
- **Depends on:** T1 `[depends on T1]` (model/view must be in place first)
- **Files to modify:**
  - `src/musichouse/ui/fixer_tab.py` — `fix_selected` (362-398) and `auto_fix_all` (437-465): move `write_tags()` loop into a worker; emit progress + per-file result; on completion update model incrementally (not full rebuild)
- **Problem:** synchronous per-file `write_tags` on GUI thread → freeze on bulk fix
- **Acceptance:** "Fix Selected" on 100 files shows progress bar, UI stays responsive, cancel stops mid-batch
- **Verify:** `pytest tests/ -v` + manual
- **Risk:** medium — interacts with T1's model

### T7: Stop swallowing AI errors — surface real messages instead of "Unknown Artist"
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** T5 `[depends on T5]`
- **Files to modify:**
  - `src/musichouse/ai_client.py` — `_call_api` (51-82): remove the blanket `return _get_fallback_response` on exception; raise typed exceptions (use `error_handling.py` — `MusicHouseError` subclasses) for no-key / network / timeout / parse-error; keep fallback only for explicitly empty results
  - `src/musichouse/error_handling.py` — raise the defined exceptions (currently dead code)
  - `src/musichouse/ui/ai_tab.py` — catch typed exceptions in the worker's `error` signal; show readable message to user
- **Problem:** every failure returns `{"artists": ["Unknown Artist"]}` rendered as a real suggestion
- **Acceptance:** no API key → user sees "API key not set. Open Settings to configure."; timeout → "Request timed out. Try again."
- **Verify:** manual test with missing key, bad endpoint
- **Risk:** low

### T8: Surface tag-write failures to the user
- **Agent:** @fixer
- **Skills:** `pyqt-widgets`
- **Depends on:** T6 `[depends on T6]`
- **Files to modify:**
  - `src/musichouse/ui/fixer_tab.py` — in the write worker's completion handler: show a summary ("Fixed 163, failed 37") + expandable list of failed files with reasons; keep failed rows in the table highlighted
- **Problem:** failures only logged (`fixer_tab.py:389,456`), user never informed
- **Acceptance:** after a batch with failures, user sees a non-modal summary with the failed file list
- **Verify:** manual test with a read-only file
- **Risk:** low

### T9: Add Stop/Cancel button to toolbar; disable action buttons during work
- **Agent:** @designer
- **Skills:** `pyqt-widgets`
- **Depends on:** T4, T5, T6 `[depends on T4, T5, T6]`
- **Files to modify:**
  - `src/musichouse/ui/main_window.py` — add a Stop button to the toolbar (315-339); wire to `_stop_scan` (currently only on closeEvent :584); disable Scan button during scan, re-enable after
  - `src/musichouse/ui/fixer_tab.py` — disable Fix/Auto-Fix buttons during writes (94-97)
  - `src/musichouse/ui/ai_tab.py` — disable Get Similar Artists during request (51-53)
- **Problem:** no cancel (H4); buttons stay enabled → double-execution (H5)
- **Acceptance:** Stop button cancels an in-progress scan; buttons gray out during their operations
- **Verify:** manual
- **Risk:** low

---

## Phase 3 — Performance & UX Polish

### T10: Bulk SQL query in `get_changed_files` (kill N+1)
- **Agent:** @fixer
- **Skills:** `sqlite`
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/leaderboard_cache.py:209-249` — replace per-file `get_cached_info` (:225) with one bulk `SELECT ... WHERE path IN (...)` into a `dict[str, row]`; chunk if > 500 paths
- **Problem:** N files = N `SELECT` round-trips
- **Acceptance:** scan 1000 files → `get_changed_files` runs 1 query (or chunked), not 1000
- **Verify:** add a test counting queries; `pytest tests/ -v`
- **Risk:** low

### T11: Wrap cache writes in a transaction (kill per-row fsync)
- **Agent:** @fixer
- **Skills:** `sqlite`
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/ui/main_window.py:192-203` — wrap the INSERT loop in `BEGIN`/`COMMIT` or use `executemany`
  - `src/musichouse/leaderboard_cache.py:100-106` — same for `update_artists`
- **Problem:** `isolation_level=None` → every execute is its own transaction = its own fsync
- **Acceptance:** scan 1000 files → cache write phase drops from seconds to milliseconds
- **Verify:** timing test; `pytest tests/ -v`
- **Risk:** low

### T12: Walk the directory tree once, not twice
- **Agent:** @oracle (review) → @fixer (implement)
- **Skills:** —
- **Depends on:** T10 `[depends on T10]`
- **Files to modify:**
  - `src/musichouse/leaderboard_cache.py:209` — `get_changed_files` accepts the already-scanned file list from `MP3Scanner` instead of re-walking
  - `src/musichouse/ui/main_window.py:95` — pass scanner results to `get_changed_files`
- **Problem:** `MP3Scanner.scan()` and `get_changed_files()` each do a full `os.walk`
- **Acceptance:** only one `os.walk` per scan
- **Verify:** `pytest tests/ -v`
- **Risk:** medium — changes a method signature; needs oracle review for API design

### T13: Read tags once, not twice per modified file
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** T2 `[depends on T2]`
- **Files to modify:**
  - `src/musichouse/ui/main_window.py:132` — reuse the `eyed3.load` result from `_check_needs_fixing` (called in `leaderboard_cache.py:233`) instead of re-loading
- **Problem:** modified files parsed by eyed3 twice (once for fix-check, once for extraction)
- **Acceptance:** each modified file is `eyed3.load`-ed exactly once per scan
- **Verify:** manual + code inspection
- **Risk:** low

### T14: Remove artificial `time.sleep` in scan loop
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/ui/main_window.py:175-178, 217` — delete the `time.sleep(0.01)` blocks; move `import time` to file top or remove
- **Problem:** 10s of pure sleep per 10k files
- **Acceptance:** scan loop has no sleep calls
- **Verify:** `pytest tests/ -v`
- **Risk:** low

### T15: Cache config in memory; single load+save on settings
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/config.py:86-126` — module-level cache dict with mtime check; add `update_config(partial_dict)` for atomic multi-field save; refactor setters to use it
  - `src/musichouse/ui/settings_dialog.py:136-138` — call `update_config({...})` once instead of 3 setters
- **Problem:** every getter re-reads+parses JSON; settings save does 3 load+save cycles
- **Acceptance:** `get_api_key()` called 100x → 1 disk read; settings save = 1 read + 1 write
- **Verify:** `pytest tests/ -v`
- **Risk:** low

### T16: Drop `PRAGMA wal_checkpoint(TRUNCATE)` on GUI thread
- **Agent:** @fixer
- **Skills:** `sqlite`
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/ui/fixer_tab.py:413` — remove the `TRUNCATE` checkpoint or switch to `PASSIVE`; let SQLite checkpoint naturally
- **Problem:** forced fsync on GUI thread after every fix batch
- **Acceptance:** no `wal_checkpoint(TRUNCATE)` on the main thread
- **Verify:** `pytest tests/ -v`
- **Risk:** low

### T17: Debounce AI-tab artist search
- **Agent:** @fixer
- **Skills:** `pyqt-widgets`
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/ui/ai_tab.py:38, 80-100` — add `QTimer` single-shot ~150ms on `textChanged`; rebuild combo only after debounce; or use `QSortFilterProxyModel` on the combo model
- **Problem:** full combo rebuild per keystroke
- **Acceptance:** typing fast in the search box doesn't lag
- **Verify:** manual
- **Risk:** low

### T18: Add empty-state messages
- **Agent:** @designer
- **Skills:** `pyqt-widgets`
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/ui/fixer_tab.py:51-88` — show "Click Scan to begin" overlay/placeholder when table is empty
  - `src/musichouse/ui/leaderboard_tab.py:23-42` — "No artists yet. Scan your library to populate."
  - `src/musichouse/ui/ai_tab.py` — "No artists loaded. Scan your library first."
- **Problem:** blank tables on first launch, no call to action
- **Acceptance:** first launch shows guidance text in each tab
- **Verify:** manual
- **Risk:** low

### T19: Add text search/filter to the Fixer file list
- **Agent:** @fixer
- **Skills:** `pyqt-widgets`
- **Depends on:** T1 `[depends on T1]` (model/view enables `QSortFilterProxyModel`)
- **Files to modify:**
  - `src/musichouse/ui/fixer_tab.py:56-63` — add a `QLineEdit` search box; wire to `QSortFilterProxyModel.setFilterFixedString` on filename+artist+title columns
- **Problem:** no text search among thousands of rows
- **Acceptance:** typing "beck" filters to rows matching Beck in filename/artist/title
- **Verify:** manual
- **Risk:** low

### T20: Implement "Select All" checkbox in table header
- **Agent:** @fixer
- **Skills:** `pyqt-widgets`
- **Depends on:** T1 `[depends on T1]`
- **Files to modify:**
  - `src/musichouse/ui/fixer_tab.py:350-353` — implement `_on_item_changed` (currently `pass`); toggle all checkboxes in the (filtered) proxy model
- **Problem:** stubbed `pass`, no bulk select → user checks hundreds manually
- **Acceptance:** clicking the header checkbox checks all visible rows
- **Verify:** manual
- **Risk:** low

### T21: Add keyboard shortcuts, menu bar, tooltips
- **Agent:** @designer
- **Skills:** `pyqt-widgets`
- **Depends on:** T9 `[depends on T9]`
- **Files to modify:**
  - `src/musichouse/ui/main_window.py:8, 315-339` — add menu bar (File: Scan / Settings / Exit; Edit: Stop; Help: About); add `QShortcut`s (Ctrl+O scan, Esc stop/cancel, Ctrl+, settings); add tooltips to all toolbar + action buttons
  - `src/musichouse/ui/fixer_tab.py:94-97` — tooltips on Fix/Auto-Fix explaining the difference
  - `src/musichouse/ui/settings_dialog.py:31-48` — placeholders (`https://api.openai.com/v1/...`), field tooltips, make resizable
- **Problem:** no shortcuts, no menu, no mnemonics, no tooltips, no placeholders
- **Acceptance:** Ctrl+O opens scan dialog; Esc cancels; tooltips show on hover; settings has placeholders
- **Verify:** manual
- **Risk:** low

### T22: Final review — code quality + regression test pass
- **Agent:** @oracle
- **Skills:** —
- **Depends on:** all `[depends on T1-T21]`
- **Files to modify:** none (review only; may open follow-up tasks)
- **What:** full code review for regressions, thread safety, error-handling consistency, dead code cleanup (`error_handling.py` now used? `isinstance` ternaries removed?)
- **Acceptance:** `pytest tests/ -v` green; no new lint warnings; oracle signs off
- **Verify:** `pytest tests/ -v`, `ruff check .`
- **Risk:** — (review lane)

---

## Phase 1.5 — Tag Writing Integrity (from tag-write verification)

These came out of the deep verification of MP3 tag writing + progress bar. They are data-integrity bugs not covered by the original analysis.

### T23: Fix `auto_fix_all` — use table values + `force=True`
- **Agent:** @fixer
- **Skills:** `pyqt-widgets`
- **Depends on:** T1 `[depends on T1]` (model/view must be in place first; reads edited values from the model)
- **Files to modify:**
  - `src/musichouse/ui/fixer_tab.py:437-465` — `auto_fix_all`: read artist/title from the table/model (the user's edits), not from `entry["suggested_artist"]`; pass `force=True` to `write_tags` to match `fix_selected` behavior
- **Files NOT to touch:** `tag_writer.py` (the function signature is fine)
- **Problem:** `auto_fix_all` ignores user edits (uses `suggested_*` from `_files_data`) and omits `force=True` (skips files that already have tags, even if wrong) — inconsistent with `fix_selected` which uses table values + `force=True`
- **Acceptance:** user edits 5 artist cells → clicks "Auto-Fix All" → the 5 edited values are written; files with pre-existing (wrong) tags are overwritten
- **Verify:** `pytest tests/ -v` + add a test that edits a cell then runs `auto_fix_all` and asserts the edited value (not the suggested one) reaches `write_tags`
- **Risk:** low — small change, but behavior-critical

### T24: Fix `load_mp3_safely` — `NameError` on `result` swallows the real error
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/utils.py:43-55` — initialize `result = None` before the `try`; in the `finally`, check `if stderr_output and result is None` (already there, but `result` is unbound if `eyed3.load` raised); better: move the `stderr_output` check into the `try` block after the load, or guard `result` with a default
- **Problem:** if `eyed3.load(file_path)` raises, `result` is never assigned → the `finally` block's `if stderr_output and result is None` raises `NameError`, caught by the outer `except`, returns `None` — the original eyed3 error is lost and never logged
- **Acceptance:** loading a corrupted MP3 logs the actual eyed3 stderr/error, not a silent `None`
- **Verify:** `pytest tests/test_utils.py -v` + add a test that mocks `eyed3.load` to raise and asserts the error is logged
- **Risk:** low — pure error-path fix, no behavior change on success

### T25: Remove redundant `_tags_already_exist` reload after `write_tags`
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** T1 `[depends on T1]` (touches the same `fix_selected` flow)
- **Files to modify:**
  - `src/musichouse/ui/fixer_tab.py:385` — remove the `_tags_already_exist(file_path, new_artist, new_title)` call; `write_tags` already returns `True` on success and `False` only when tags exist and `force=False` — with `force=True` (used in `fix_selected`), `False` means a real failure, not "already exists"
  - `src/musichouse/ui/fixer_tab.py:21-40` — delete `_tags_already_exist` (dead after the call site is removed) OR keep only if `auto_fix_all` (which uses `force=False`) still needs it — see T23
- **Problem:** after `write_tags` loads + writes the file, `_tags_already_exist` loads the same file again with `load_mp3_safely` — a second full eyed3 parse per file. For 500 files that's 500 redundant parses
- **Acceptance:** `fix_selected` on 100 files does 100 `eyed3.load` calls, not 200
- **Verify:** `pytest tests/ -v` + add a test counting `eyed3.load` calls during `fix_selected`
- **Risk:** low — but must confirm T23 changes `auto_fix_all` to `force=True` first, otherwise `auto_fix_all` still needs the existence check

### T26: Replace fragile `file_path.split('/')[-1]` with `Path.name`
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/ui/fixer_tab.py:387, 389` — both lines use `file_path.split('/')[-1] if isinstance(file_path, str) else file_path.name`; replace with `Path(file_path).name` (one line, handles both str and Path)
- **Problem:** `Path` objects don't have `.split` — the `isinstance` check avoids the crash but is fragile and verbose. On Windows (if ever ported) `split('/')` would break on `\` paths
- **Acceptance:** log lines show the filename for both str and Path inputs; no `isinstance` branch
- **Verify:** `pytest tests/ -v`; `ruff check .`
- **Risk:** low — cosmetic/robustness

### T27: Add regression tests — `fix_selected` + `auto_fix_all` with sorted table
- **Agent:** @fixer
- **Skills:** `pytest`, `pyqt-testing`
- **Depends on:** T1, T23, T25 `[depends on T1, T23, T25]` (must run against the fixed code)
- **Files to modify:**
  - `tests/test_fixer_tab_sort.py` (NEW) — test fixture: 5 MP3s in `tmp_path`, load into `FixerTab`, sort by "Artist" column, check 2 boxes, call `fix_selected`, assert tags written to the *correct* files (not the pre-sort indices); same for `auto_fix_all` after editing 2 cells
  - `tests/test_tag_writer.py` — add a test that `auto_fix_all` writes the *edited* value, not the suggested value (guards T23's regression)
- **Files NOT to touch:** `fixer_tab.py` (test-only task)
- **Problem:** no test covers the sort-corruption scenario (the original T1 bug) or the `auto_fix_all` edit-ignoring bug (T23). Without tests, both can silently regress
- **Acceptance:** tests fail if the sort bug or the edit-ignoring bug is reintroduced; tests pass on the fixed code
- **Verify:** `QT_QPA_PLATFORM=offscreen uv run --extra test pytest tests/test_fixer_tab_sort.py tests/test_tag_writer.py -v`
- **Risk:** low — test-only; install `pytest-mock` if missing (currently 3 tests error on missing `mocker` fixture)

---

## Phase 1.6 — Cross-Cutting Integrity (found in deep verification)

Bugs found by reading closeEvent, parser, settings, config, and AI tab flows.

### T28: Remove `self._leaderboard.reset()` from closeEvent — it wipes the entire DB on every close
- **Agent:** @fixer
- **Skills:** `sqlite`
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/ui/main_window.py:592-593` — delete the `if self._leaderboard: self._leaderboard.reset(); self._leaderboard = None` block. `reset()` calls `LeaderboardCache.clear()` which runs `DELETE FROM artists`, `DELETE FROM similar_artists`, `DELETE FROM scan_cache` — destroying all cached data on every window close. Replace with `self._leaderboard = None` only (drop the reference; let GC clean up the in-memory object)
- **Files NOT to touch:** `leaderboard_cache.py` (`clear()` method stays — it may be useful elsewhere, just not called on close)
- **Problem:** every close wipes the scan_cache → incremental scanning is useless (always reprocesses everything), `_load_saved_files` loads nothing on startup, AI tab never loads artists from DB. This is the single most damaging bug in the app — it negates the entire caching architecture
- **Acceptance:** after scan + close + reopen, `_load_saved_files` populates the Fixer tab with previously-found files; a second scan skips unchanged files (incremental scan works)
- **Verify:** `pytest tests/ -v`; manual: scan → close → reopen → Fixer tab shows files from last session
- **Risk:** low — removing a destructive call; but must verify no other code path depends on the wipe-on-close behavior (e.g., stale data cleanup)
- **Blocking:** unblocks T3 (leaderboard populates), T18 (empty states), and the entire incremental-scan value proposition

### T29: Fix parser for artists with hyphens in their names (AC-DC, Jay-Z, Blink-182)
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/parser.py:27-40` — the regex `^(.+?)\s*[-–]\s*(.+\.mp3)$` uses non-greedy `(.+?)` which stops at the first hyphen, splitting `AC-DC - Highway to Hell.mp3` into artist=`AC`, title=`DC - Highway to Hell`. The fallback `filename.index('-')` is worse — finds the first hyphen anywhere. Fix: match the LAST ` - ` (space-hyphen-space) separator instead of the first; or require the separator to be surrounded by spaces (the regex already does `\s*[-–]\s*`, but `.+?` is non-greedy so it matches the shortest possible artist). Change `(.+?)` to `(.+)` (greedy) so it consumes up to the LAST separator, OR split on `\s+[-–]\s+` and take the last segment as title
  - Add test cases: `AC-DC - Highway to Hell.mp3`, `Jay-Z - 99 Problems.mp3`, `Blink-182 - All The Small Things.mp3`
- **Files NOT to touch:** `fixer_tab.py` (only consumes the parser output)
- **Problem:** artists with hyphens get their names truncated → suggested tags are wrong → user fixes with wrong data → silent corruption
- **Acceptance:** `parse_filename("AC-DC - Highway to Hell.mp3")` returns `("AC-DC", "Highway to Hell")`; same for Jay-Z, Blink-182
- **Verify:** `pytest tests/test_parser.py -v` (add test cases if not present)
- **Risk:** low — pure parsing logic, well-testable

### T30: Fix settings URL validation — accept hostnames without TLD (LAN servers)
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/ui/settings_dialog.py:92-99` — the URL validation regex requires a TLD (`.com`, `.org`) or `localhost` or an IP. A user with a LAN server at `http://my-nas:8080/v1` cannot save settings. Relax the regex to accept any `http(s)://hostname[:port]/path` where hostname is a valid hostname (letters, digits, hyphens, dots). Use `urllib.parse.urlparse` + check `scheme` in (`http`, `https`) and `netloc` is non-empty, instead of a regex
- **Problem:** valid self-hosted/local API endpoints are rejected → user can't configure the app for their server
- **Acceptance:** `http://my-nas:8080/v1` is accepted; `http://192.168.1.100:8080` is accepted; `http://api.openai.com/v1` is accepted; `not-a-url` is rejected; empty string is rejected
- **Verify:** `pytest tests/ -v`; add a test for the URL validation function
- **Risk:** low — input validation only

### T31: Fix `update_artists` — replace counts, don't accumulate (ON CONFLICT DO UPDATE SET count = count + ?)
- **Agent:** @fixer
- **Skills:** `sqlite`
- **Depends on:** T28 `[depends on T28]` (once the DB survives between sessions, accumulation becomes a real bug — right now it's masked by the wipe-on-close)
- **Files to modify:**
  - `src/musichouse/leaderboard_cache.py:100-106` — change `ON CONFLICT(name) DO UPDATE SET count = count + ?` to `ON CONFLICT(name) DO UPDATE SET count = excluded.count` (replace, not add). Currently every scan doubles the counts for existing artists. The `+ ?` was probably intended for incremental updates, but since `update_artists` receives full counts (not deltas), it should replace
- **Problem:** scanning the same library twice doubles every artist's count in the leaderboard
- **Acceptance:** scan the same library twice → artist counts are correct (not doubled)
- **Verify:** `pytest tests/ -v`; add a test that scans twice and checks counts
- **Risk:** low — but must verify that callers always pass absolute counts, not deltas (check `Leaderboard.update_from_files` call site)

### T32: Atomic config.json write (write to temp file + rename)
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/config.py:79-81` — replace `with open(config_path, "w") as f: json.dump(...)` with: write to `config_path.with_suffix(".tmp")`, flush, `os.fsync`, then `os.replace(tmp, config_path)` (atomic on POSIX and Windows). If the process crashes mid-write, the `.tmp` file is orphaned but `config.json` stays intact. On next load, the old valid config is read
- **Problem:** a crash or power loss during `json.dump` leaves `config.json` truncated → `load_config()` catches `JSONDecodeError` and returns defaults → **the user's API key is silently lost**
- **Acceptance:** simulate a crash mid-write (kill process during `json.dump`) → next launch loads the previous valid config with the API key intact
- **Verify:** `pytest tests/ -v`; add a test that writes config, simulates truncation, and verifies recovery
- **Risk:** low — standard atomic-write pattern

### T33: Fix AI tab `showEvent` — retry loading artists after a scan (currently caches "empty" forever)
- **Agent:** @fixer
- **Skills:** `pyqt-widgets`
- **Depends on:** T28 `[depends on T28]` (the DB must survive between sessions for the retry to find data)
- **Files to modify:**
  - `src/musichouse/ui/ai_tab.py:102-126` — `load_artists_from_db` sets `self._artists_loaded = True` even when the DB is empty (line 119). After that, `showEvent` never retries. Fix: only set `_artists_loaded = True` when artists are actually found; OR add a `refresh_artists()` method called from `MainWindow._on_scan_finished` to repopulate the combo after every scan; OR connect to the `artist_count_updated` signal (once T3 emits it) to trigger a reload
- **Problem:** if the user opens the AI tab before scanning, the combo is empty and never repopulates, even after a scan
- **Acceptance:** open AI tab before scan (empty) → run scan → switch to AI tab → combo is populated
- **Verify:** manual test; `pytest tests/ -v`
- **Risk:** low — but needs coordination with T3 (signal emission) for the cleanest fix

---

## Phase 1.7 — Crash Safety & Concurrency

Data integrity under abnormal conditions: crashes, concurrent instances, race conditions.

### T34: Fix closeEvent race condition — ensure scan thread is fully stopped before DB access
- **Agent:** @fixer
- **Skills:** `pyqt-threading`
- **Depends on:** T28 `[depends on T28]` (T28 removes `reset()`, but the race with the thread's DB connection remains)
- **Files to modify:**
  - `src/musichouse/ui/main_window.py:573-594` — after `_stop_scan()` (which calls `wait()`), add an explicit `self._scan_worker = None` check; ensure the worker's SQLite connection is closed before the main thread does any DB cleanup. Currently `_stop_scan` waits for the thread, but the thread may still hold an open SQLite connection (thread-local). Add `connection.close()` in `ScanWorker.run()`'s `finally` block, or ensure the worker never shares a connection with the main thread
- **Problem:** if the scan thread's DB connection is still open when the main thread accesses the DB (even just to close it), WAL-mode SQLite can hit a race. The thread uses thread-local connections that may not be cleaned up
- **Acceptance:** closing the window during a scan never produces SQLite warnings or WAL contention errors in the log
- **Verify:** manual test (close during scan, check logs); `pytest tests/ -v`
- **Risk:** medium — threading + DB lifecycle

### T35: Add single-instance lock (prevent two instances from corrupting config + DB)
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/__init__.py` or `src/musichouse/main.py` — add a lock file (`config_dir / .lock`) using `fcntl.flock` (Linux) or a cross-platform approach. On second launch, show a dialog "MusicHouse is already running" and exit. Release the lock on exit (atexit + closeEvent)
- **Problem:** two instances reading/writing the same `config.json` and SQLite DB → last-write-wins on config (API key lost), double-counted artists, inconsistent cache
- **Acceptance:** launching a second instance shows "already running" dialog and exits
- **Verify:** manual test (launch twice)
- **Risk:** low — standard pattern

### T36: Crash recovery — write scan_cache incrementally (transaction per batch, not all-at-end)
- **Agent:** @fixer
- **Skills:** `sqlite`
- **Depends on:** T11 `[depends on T11]` (transaction batching infrastructure), T28 `[depends on T28]` (DB must survive between sessions for this to matter)
- **Files to modify:**
  - `src/musichouse/ui/main_window.py:192-203` — instead of collecting all INSERTs and executing at the end of the scan, commit in batches (every 100 files) within a single transaction. If the app crashes mid-scan, the committed batches survive and the next scan resumes from where it left off (incremental scan picks up the rest)
- **Problem:** if the app crashes during a scan, the entire scan_cache write is lost (no COMMIT was issued). On restart, `_load_saved_files` finds nothing, and the next scan reprocesses everything
- **Acceptance:** kill the app mid-scan → reopen → Fixer tab shows the files processed before the crash
- **Verify:** manual test (kill -9 during scan, check DB)
- **Risk:** medium — transaction management in the scan loop

### T37: Crash recovery — atomic tag writes (backup file before overwrite)
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** T6 `[depends on T6]` (tag writes are in a worker thread, making backup/restore cleaner)
- **Files to modify:**
  - `src/musichouse/tag_writer.py` — before `eyed3.save()`, copy the file to `file_path.with_suffix('.bak')`; if `save()` raises, restore from `.bak`; delete `.bak` on success. Alternatively, write to a temp file and `os.replace` (but eyed3 modifies in-place, so backup is the safer approach)
- **Problem:** if `eyed3.save()` crashes mid-write (power loss, disk full), the MP3 can be left with partially-written tags — corrupted. The user has no way to recover
- **Acceptance:** simulate a crash during `save()` → file is restored to its pre-write state
- **Verify:** add a test that mocks `eyed3.save` to raise, assert file is unchanged
- **Risk:** medium — must handle the backup lifecycle correctly (don't leave .bak files around)

---

## Phase 1.8 — Parser Robustness

The parser fails on common filename patterns. T29 covers hyphenated artists; these cover other patterns.

### T38: Handle track-number filename patterns (01. Artist - Title, 01 - Artist - Title, Artist - 01 - Title)
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** T29 `[depends on T29]` (T29 fixes the greedy match; this adds new patterns on top)
- **Files to modify:**
  - `src/musichouse/parser.py:8-58` — add regex patterns for:
    - `01. Artist - Title.mp3` → strip leading track number + dot
    - `01 - Artist - Title.mp3` → strip leading track number
    - `Artist - 01 - Title.mp3` → strip middle track number
    - `01 Track.mp3` → no artist, title=`Track`
  - Add test cases for each pattern
- **Problem:** files with track numbers get the number parsed as the artist or prepended to the title → wrong suggested tags
- **Acceptance:** `parse_filename("01. Beck - Loser.mp3")` → `("Beck", "Loser")`; `parse_filename("01 - Beck - Loser.mp3")` → `("Beck", "Loser")`
- **Verify:** `pytest tests/test_parser.py -v` (add cases)
- **Risk:** low — pure parsing logic

### T39: Handle underscore separator and em-dash in filenames
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** T29 `[depends on T29]`
- **Files to modify:**
  - `src/musichouse/parser.py:27` — the regex matches `[-–]` (hyphen + en-dash) but NOT em-dash `—` (U+2014). Add it: `[-–—]`. Also add underscore as separator: `_` (but only when surrounded by content, not inside words). Add test cases: `Artist_Title.mp3`, `Artist — Title.mp3`
- **Problem:** files using em-dash or underscore as separator are not parsed → artist/title extraction fails
- **Acceptance:** `parse_filename("Beck — Loser.mp3")` → `("Beck", "Loser")`; `parse_filename("Beck_Loser.mp3")` → `("Beck", "Loser")`
- **Verify:** `pytest tests/test_parser.py -v`
- **Risk:** low

---

## Phase 2.5 — Error Handling Edge Cases (user-facing)

The app silently fails on real-world file conditions. These tasks surface errors and handle edge cases the user will encounter.

### T40: Handle corrupted MP3 files gracefully (0 bytes, invalid header)
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** T24 `[depends on T24]` (T24 fixes `load_mp3_safely` error logging; this builds on it)
- **Files to modify:**
  - `src/musichouse/utils.py:43-55` — when `load_mp3_safely` returns `None`, log the file size and whether the header is valid (`ID3` magic bytes). Return a typed result or raise `CorruptedFileError` (from `error_handling.py`)
  - `src/musichouse/ui/fixer_tab.py` — show corrupted files in a distinct state (red background, "Corrupted" label) instead of "needs fixing" with empty suggestions
  - `src/musichouse/ui/main_window.py:132` — in the scan loop, distinguish "no tag" (fixable) from "corrupted file" (not fixable) and handle accordingly
- **Problem:** a 0-byte file or invalid MP3 is flagged as "needs fixing" with empty artist/title suggestions. The user thinks they can fix it, but `write_tags` will fail. No distinction between "missing tag" and "corrupted file"
- **Acceptance:** corrupted files appear with a clear "Corrupted" state, not as fixable files with empty suggestions
- **Verify:** `pytest tests/ -v`; manual test with a 0-byte .mp3
- **Risk:** low

### T41: Handle file deleted between scan and fix
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** T8 `[depends on T8]` (T8 surfaces write failures; this handles the specific pre-write check)
- **Files to modify:**
  - `src/musichouse/tag_writer.py` — before loading the file with `eyed3.load`, check `file_path.exists()`. If it doesn't exist, raise `FileNotFoundError` with a clear message instead of letting `eyed3.load` return `None` (which becomes a silent failure)
  - `src/musichouse/ui/fixer_tab.py` — in the write worker, catch `FileNotFoundError` and mark the row as "File no longer exists" (not just "failed")
- **Problem:** user scans, then deletes/moves files outside the app, then clicks Fix → `write_tags` silently fails, row stays, user confused
- **Acceptance:** fixing a deleted file shows "File no longer exists" and removes the row from the table
- **Verify:** `pytest tests/ -v`; manual test
- **Risk:** low

### T42: Handle file locked by another process (music player, finder preview)
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** T8 `[depends on T8]`
- **Files to modify:**
  - `src/musichouse/tag_writer.py` — catch `PermissionError` and `OSError` (EBUSY/ETXTBSY on Linux, sharing violation on Windows) from `eyed3.save()`. Raise `FileLockedError` (from `error_handling.py`) with the file path and a suggestion to close the application using the file
- **Problem:** if a music player or file previewer has the file open, `eyed3.save()` fails with a permission/lock error that is only logged. The user sees a generic "failed" with no actionable info
- **Acceptance:** fixing a file open in a music player shows "File is locked. Close the application using this file and try again."
- **Verify:** manual test (open a file in a player, try to fix)
- **Risk:** low

### T43: Handle read-only files during fix
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** T8 `[depends on T8]`
- **Files to modify:**
  - `src/musichouse/tag_writer.py` — catch `PermissionError` (EACCES) from `eyed3.save()` separately from lock errors. Raise `ReadOnlyFileError` with a suggestion to check file permissions
  - `src/musichouse/ui/fixer_tab.py` — in the failure summary, group by error type: "3 files are read-only, 2 files are locked, 1 file was deleted"
- **Problem:** read-only files fail silently with a generic error. The user doesn't know the fix is a permissions issue
- **Acceptance:** fixing a read-only file shows "File is read-only. Check file permissions."
- **Verify:** manual test (`chmod 444 file.mp3`, try to fix)
- **Risk:** low

### T44: Test and fix unicode filenames (Beyoncé, Sigur Rós, Björk)
- **Agent:** @fixer
- **Skills:** `pytest`
- **Depends on:** T29 `[depends on T29]` (parser must be fixed first)
- **Files to modify:**
  - `tests/test_parser.py` — add test cases: `Beyoncé - Halo.mp3`, `Sigur Rós - Hoppípolla.mp3`, `Björk - Hyperballad.mp3`, `北京 - 歌曲.mp3`
  - `src/musichouse/parser.py` — fix if any unicode issues are found (Python 3 strings are unicode, but regex `\w` may not match non-ASCII; use `re.UNICODE` or `[^/\\]` instead of `\w`)
  - `src/musichouse/scanner.py` — verify `os.walk` handles unicode paths (it should on Python 3, but verify)
- **Problem:** non-ASCII filenames may not parse correctly, producing wrong artist/title suggestions for a significant portion of non-English music libraries
- **Acceptance:** all unicode test cases parse correctly; scan a directory with unicode filenames without errors
- **Verify:** `pytest tests/test_parser.py -v`
- **Risk:** low

---

## Phase 3.5 — Scanner & Cache Robustness

### T45: Filter hidden directories in scanner (.git, node_modules, .Trash)
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/scanner.py:42` — in the `os.walk` loop, use `dirs[:] = [d for d in dirs if not d.startswith('.')]` to prune hidden directories. Add a configurable exclude list (default: `.git`, `.Trash`, `node_modules`, `__pycache__`, `.venv`). Log how many directories were skipped
- **Problem:** scanning the home directory finds MP3s inside `.git/`, browser caches, `node_modules/`, trash — files the user doesn't want to fix
- **Acceptance:** scanning a directory containing `.git/` or `node_modules/` does not scan those subdirectories
- **Verify:** `pytest tests/ -v`; add a test with a `.git` dir containing a fake .mp3
- **Risk:** low

### T46: Add no-op quick check in get_changed_files (skip full walk when nothing changed)
- **Agent:** @fixer
- **Skills:** `sqlite`
- **Depends on:** T10 `[depends on T10]` (T10 fixes the N+1; this adds a pre-check to skip the walk entirely)
- **Files to modify:**
  - `src/musichouse/leaderboard_cache.py:209-249` — before the full `os.walk` + per-file stat, run `SELECT MAX(mtime) FROM scan_cache WHERE path LIKE prefix%`. Compare with a quick `os.scandir` to find the newest mtime in the tree. If the cache's max mtime >= tree's max mtime, return `[]` (nothing changed). Only do the full walk if the quick check indicates changes
- **Problem:** even with T10's bulk query, a no-op incremental scan still does a full `os.walk` + stat per file. For 10k files, that's 10k stat calls just to confirm nothing changed
- **Acceptance:** a no-op incremental scan (no files changed) completes in <100ms instead of seconds
- **Verify:** timing test; `pytest tests/ -v`
- **Risk:** medium — must handle edge cases (deleted files, new files with older mtime)

### T47: Eliminate triple eyed3.load — parse once, pass result through
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** T13 `[depends on T13]` (T13 eliminates the double load; this finds and eliminates the third)
- **Files to modify:**
  - `src/musichouse/ui/main_window.py:132` — the scan loop calls `eyed3.load()` (via `_check_needs_fixing` in leaderboard_cache, then again in `run()` at line 132, then again in `Leaderboard.update_from_files()` if called). Refactor: call `eyed3.load()` once, pass the `audiofile` object to `_check_needs_fixing`, to the extraction code, and to `update_from_files`. This requires changing method signatures to accept a pre-loaded `audiofile` instead of a `file_path`
- **Files NOT to touch:** `tag_writer.py` (uses `eyed3.load` for writing, which is a separate operation)
- **Problem:** each modified file is parsed by eyed3 up to 3 times per scan. eyed3 parsing is the single most expensive per-file operation. 3x = 3x scan time
- **Acceptance:** each file is `eyed3.load`-ed exactly once per scan (verifiable by mocking and counting calls)
- **Verify:** add a test counting `eyed3.load` calls during a scan; `pytest tests/ -v`
- **Risk:** medium — changes method signatures across 3 files

---

## Phase 3.6 — Developer Hygiene

Code quality issues that affect maintainability and debuggability.

### T48: Add DB schema versioning (enable future migrations)
- **Agent:** @fixer
- **Skills:** `sqlite`
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/leaderboard_cache.py` — add a `schema_version` table (`CREATE TABLE IF NOT EXISTS schema_version (version INTEGER)`); on init, check the current version; if missing, create and set to 1. Future schema changes check this version and run migrations. Current tables have no version → any future change breaks existing DBs
- **Problem:** no schema versioning → any future table structure change (new column, new index, renamed field) silently breaks existing user databases. No migration path
- **Acceptance:** a fresh DB has `schema_version = 1`; an existing DB (pre-versioning) gets versioned to 1 on first open; a test that simulates a v0 → v1 migration passes
- **Verify:** `pytest tests/ -v`
- **Risk:** low — additive, no existing behavior changes

### T49: Fix Leaderboard connection leak (`__del__` closes `self._cache` but methods create new connections)
- **Agent:** @fixer
- **Skills:** `sqlite`
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/leaderboard.py` — `__del__` calls `self._cache.close()`, but methods like `update_from_files` call `self._cache._get_connection()` which creates a NEW connection each time (thread-local). These are never closed. Each leaderboard update leaks a connection. Fix: either reuse a single connection (not thread-safe but leaderboard is used from the main thread) or explicitly close connections in a `finally` block after each operation
- **Problem:** connection leak — every leaderboard update creates a new SQLite connection that is never closed. Over a long session, this exhausts file descriptors
- **Acceptance:** after 100 leaderboard updates, `lsof` shows no leaked SQLite connections
- **Verify:** manual test + `pytest tests/ -v`
- **Risk:** low — resource cleanup

### T50: Remove or repurpose empty `threading.py` module
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** T6 `[depends on T6]` (T6 adds real threading for tag writes; this module should host the shared worker infrastructure)
- **Files to modify:**
  - `src/musichouse/threading.py` — currently 108 bytes (effectively empty). Either: (a) delete it and remove any imports, or (b) repurpose it as the shared worker infrastructure module (base `WorkerThread` class with `progress`, `finished`, `error`, `cancel` signals that T5/T6/T9 can inherit from). Option (b) is recommended — it eliminates the signal/slot duplication that T5 and T6 would otherwise create
- **Problem:** dead module — 108 bytes of nothing. Misleading name suggests threading infrastructure exists when it doesn't
- **Acceptance:** `threading.py` is either deleted (no references) or contains a reusable `WorkerThread` base class used by T5 and T6's workers
- **Verify:** `pytest tests/ -v`; `ruff check .`
- **Risk:** low

### T51: Fix `cache._get_connection()` encapsulation violation in fixer_tab
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** T1 `[depends on T1]` (T1 refactors fixer_tab; this fix should land during the refactor)
- **Files to modify:**
  - `src/musichouse/leaderboard_cache.py` — add a public `query(sql, params=None)` method (or `get_connection()` context manager) that `fixer_tab.py` can use without accessing `_get_connection()` directly
  - `src/musichouse/ui/fixer_tab.py:120, 173` — replace `cache._get_connection()` with the new public API
- **Problem:** `fixer_tab.py` accesses `LeaderboardCache._get_connection()` (a private method) to run raw SQL. This breaks encapsulation and couples the UI to the cache's internal connection management
- **Acceptance:** no `_get_connection()` calls outside `leaderboard_cache.py`; `grep -r "_get_connection" src/musichouse/ui/` returns nothing
- **Verify:** `grep -r "_get_connection" src/musichouse/ui/`; `pytest tests/ -v`
- **Risk:** low

### T52: Add operation duration logging (profiling)
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/ui/main_window.py` — wrap `ScanWorker.run()` phases (walk, parse, cache write) with `time.perf_counter()` and log durations at INFO level: `"Scan phase: walked 10000 files in 2.3s"`, `"Scan phase: parsed 5000 modified files in 18.4s"`, `"Scan phase: wrote 5000 cache entries in 0.8s"`
  - `src/musichouse/ui/fixer_tab.py` — log `fix_selected`/`auto_fix_all` duration and files/sec
  - `src/musichouse/leaderboard_cache.py` — log `get_changed_files` duration
- **Problem:** no timing data → impossible to profile slow scans or identify which phase is the bottleneck. Users report "it's slow" but there's no data to diagnose
- **Acceptance:** scan log shows per-phase timings; fix log shows files/sec
- **Verify:** manual test (check log output)
- **Risk:** low — logging only

### T53: WAL checkpoint on scan completion (not just on fix)
- **Agent:** @fixer
- **Skills:** `sqlite`
- **Depends on:** T16 `[depends on T16]` (T16 removes the TRUNCATE checkpoint from the fix path; this adds a PASSIVE checkpoint to the scan path)
- **Files to modify:**
  - `src/musichouse/ui/main_window.py` — in `_on_scan_finished`, run `PRAGMA wal_checkpoint(PASSIVE)` on the cache DB. This lets SQLite merge the WAL back into the main DB without a forced fsync. Currently WAL only checkpoints on fix (and T16 removes that), so after a scan-only session the WAL file grows unbounded
- **Problem:** WAL file grows indefinitely during scan-only sessions (no fix to trigger checkpoint). Large WAL files slow down startup and consume disk
- **Acceptance:** after a scan, the WAL file is checkpointed (PASSIVE); WAL file stays small
- **Verify:** manual test (check WAL file size after scan)
- **Risk:** low — PASSIVE is non-blocking

### T54: Use `error_handling.py` exceptions or remove the dead code
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** T7, T40, T41, T42, T43 `[depends on T7, T40, T41, T42, T43]` (these tasks define new exceptions; this task reconciles them with the existing `error_handling.py` hierarchy)
- **Files to modify:**
  - `src/musichouse/error_handling.py` — currently defines `MusicHouseError`, `ScanError`, `TagWriteError` — all never raised. After T7/T40-T43 add new exceptions (`CorruptedFileError`, `FileLockedError`, `ReadOnlyFileError`, `FileNotFoundError`), reconcile the hierarchy: make them all subclasses of `MusicHouseError`, remove unused ones, ensure the UI catches `MusicHouseError` as the base for display
- **Problem:** dead exception hierarchy. Either use it or remove it — having unused custom exceptions is misleading
- **Acceptance:** every exception in `error_handling.py` is raised somewhere; the UI catches `MusicHouseError` as the base; no dead exception classes
- **Verify:** `grep -r "MusicHouseError\|ScanError\|TagWriteError" src/musichouse/`; `pytest tests/ -v`
- **Risk:** low — cleanup

---

## Phase 3.7 — UX Polish (additional)

### T55: Add Ctrl+C / Ctrl+Q keyboard handler to stop scan and quit
- **Agent:** @designer
- **Skills:** `pyqt-widgets`
- **Depends on:** T9 `[depends on T9]` (T9 adds the Stop button; this adds the keyboard equivalent)
- **Files to modify:**
  - `src/musichouse/ui/main_window.py` — add `QShortcut(QKeySequence("Ctrl+C"), self)` → if scanning, `_stop_scan()`; else close the window. Same for `Ctrl+Q` (close window). `Ctrl+,` → open settings (matching macOS convention)
- **Problem:** no way to cancel a scan or quit with keyboard. User must use the mouse
- **Acceptance:** Ctrl+C stops a running scan; Ctrl+Q quits the app
- **Verify:** manual test
- **Risk:** low

### T56: DPI scaling — make status label height dynamic
- **Agent:** @designer
- **Skills:** `pyqt-widgets`
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/ui/main_window.py` — the status label has `setFixedHeight(25)` which clips text on HiDPI/4K displays where font scaling is >1x. Replace with `setMinimumHeight(fontMetrics().height() + 4)` or use a size policy that allows the label to grow. Alternatively, remove the fixed height entirely and let the layout handle it
- **Problem:** on 4K/HIDPI displays with font scaling, the 25px fixed height clips the status text, making it unreadable
- **Acceptance:** status text is fully visible at 150% and 200% display scaling
- **Verify:** manual test with `QT_SCALE_FACTOR=2` env var
- **Risk:** low

### T57: Add "Test Connection" button in settings dialog
- **Agent:** @designer
- **Skills:** `pyqt-widgets`, `pyqt-threading`
- **Depends on:** T5 `[depends on T5]` (uses the AI worker thread to avoid freezing during the test)
- **Files to modify:**
  - `src/musichouse/ui/settings_dialog.py` — add a "Test Connection" button next to the API URL field. On click, send a minimal request (e.g., `GET /v1/models` or a 1-token completion) using the AI worker from T5. Show "Connected ✓" (green) or the error message (red) inline. Disable the button during the test
- **Problem:** user enters API key + URL, clicks Save, switches to AI tab, tries to get similar artists, gets "Unknown Artist" (T7 will fix the error message, but the user still doesn't know if their config is valid until they try). A test button validates before saving
- **Acceptance:** clicking "Test Connection" with valid credentials shows success; with invalid URL/key shows the error
- **Verify:** manual test with valid and invalid credentials
- **Risk:** low

### T58: Add "Exclude directories" setting (complement to T45)
- **Agent:** @designer
- **Skills:** `pyqt-widgets`
- **Depends on:** T45 `[depends on T45]` (T45 adds the default exclude list; this adds a UI for it)
- **Files to modify:**
  - `src/musichouse/ui/settings_dialog.py` — add a text area for exclude patterns (one per line, default: `.git\nnode_modules\n.Trash\n__pycache__`). Save to `config.json` under `exclude_dirs`
  - `src/musichouse/scanner.py` — read `exclude_dirs` from config (merged with defaults) and use in the `os.walk` prune step from T45
  - `src/musichouse/config.py` — add `exclude_dirs` to the default config schema
- **Problem:** T45 hardcodes the exclude list. Users may want to exclude additional dirs (e.g., `Downloads`, `Podcasts`, a sample library)
- **Acceptance:** user adds `Downloads` to the exclude list → next scan skips `Downloads/`
- **Verify:** manual test
- **Risk:** low

---

---

## Phase 1.9 — Security & Configuration

API key exposure, broken entry point, config coupling, and missing security boundaries.

### T59: Create `main.py` entry point (CLI is broken)
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/main.py` (new) — create entry point with `def main():` that creates `QApplication`, instantiates `MainWindow`, calls `app.exec()`. `pyproject.toml` declares `musichouse = "main:main"` but `main.py` does not exist — the `musichouse` CLI command fails with `ModuleNotFoundError`
- **Problem:** the documented `musichouse` CLI entry point is broken. The app can only be launched by importing internals directly. Users who `pip install` and run `musichouse` get an error
- **Acceptance:** `musichouse` command launches the app; `python -m musichouse` also works
- **Verify:** `python -c "from musichouse.main import main; print('ok')"`; manual launch
- **Risk:** low

### T60: Add `config.json`, `*.db`, `*.db-wal`, `*.db-shm` to `.gitignore`
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `.gitignore` — add `config.json`, `*.db`, `*.db-wal`, `*.db-shm`. Currently `.gitignore` excludes `*.db-wal` and `*.db-shm` but NOT `*.db` or `config.json`. The API key (stored in `config.json`) and the user's music library metadata (in `leaderboard.db`) could be committed accidentally
- **Problem:** `config.json` contains the user's API key in plain text. `leaderboard.db` contains the user's music library structure. Neither is in `.gitignore`. A user who runs `git add .` exposes their API key
- **Acceptance:** `git status` does not show `config.json` or `*.db` files after creation
- **Verify:** `git status --ignored | grep config.json`
- **Risk:** low

### T61: Use OS keychain for API key storage
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** T32 `[depends on T32]` (T32 makes config writes atomic; this moves the API key out of config.json entirely)
- **Files to modify:**
  - `src/musichouse/config.py` — use the `keyring` library (add to dependencies) to store/retrieve the API key under service name `musichouse`. `get_api_key()` checks keyring first, falls back to `config.json` for migration. `set_api_key()` stores in keyring and removes from `config.json`
  - `pyproject.toml` — add `keyring>=24.0.0` to dependencies
- **Problem:** API key is stored in `config.json` as plain text. Anyone with read access to the config file can steal the key. No OS-level encryption
- **Acceptance:** API key is stored in the OS keychain (Secret Service on Linux, Keychain on macOS, Credential Manager on Windows), not in `config.json`
- **Verify:** set API key in settings → `cat config.json` shows no `api_key` field; `python -c "import keyring; print(keyring.get_password('musichouse', 'api_key'))"` returns the key
- **Risk:** medium — new dependency, cross-platform keyring behavior varies

### T62: Add file logging with rotation
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/logging.py` — add a `RotatingFileHandler` writing to `config_dir / musichouse.log` (max 5MB, 3 backups) alongside the existing `StreamHandler`. Set the root logger level to `INFO` by default (not `DEBUG`). Add a `--debug` CLI flag or `MUSICHOUSE_DEBUG=1` env var to enable `DEBUG` level
- **Problem:** logs go to stdout only and are lost when the app closes. No log file to examine when a user reports an issue. Logging at `DEBUG` level in production is too verbose
- **Acceptance:** `musichouse.log` exists in the config dir after running the app; default level is INFO; `MUSICHOUSE_DEBUG=1` enables DEBUG
- **Verify:** run app, check `musichouse.log` exists and contains INFO entries (not DEBUG)
- **Risk:** low

### T63: Rename `logging.py` to avoid shadowing stdlib
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** T62 `[depends on T62]` (do the rename during the logging rework)
- **Files to modify:**
  - `src/musichouse/logging.py` → rename to `src/musichouse/log_setup.py`
  - All files: `from musichouse import logging` → `from musichouse import log_setup as logging` (or update the import pattern). The file is named `logging.py`, which shadows the stdlib `logging` module. Inside the module, `import logging` works (Python 3 absolute imports), but it's confusing and fragile — any `import logging` in a file that also does `from musichouse import logging` can get the wrong module
- **Problem:** module name collision with stdlib `logging`. Fragile import system. Confusing for new developers
- **Acceptance:** no module named `logging.py` in `musichouse/`; all imports work; `python -c "from musichouse.log_setup import get_logger"` succeeds
- **Verify:** `grep -r "from musichouse import logging" src/` returns nothing; `pytest tests/ -v`
- **Risk:** low — mechanical rename, but touches many files

### T64: Decouple config.py from PyQt6
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/config.py:7` — replace `from PyQt6.QtCore import QStandardPaths` with a stdlib approach: `os.environ.get("XDG_CONFIG_HOME")` on Linux, `~/Library/Application Support` on macOS, `%APPDATA%` on Windows. Or use `platformdirs` library (add to dependencies). Currently `config.py` imports PyQt6, meaning config CANNOT be used without a QApplication instance — `QStandardPaths` may return empty paths without a Qt app
- **Problem:** config module is coupled to PyQt6. Cannot test config without `QApplication`. `QStandardPaths` may not work correctly without a running Qt app. Config should be framework-agnostic
- **Acceptance:** `config.py` has no PyQt6 imports; config tests pass without `qapp` fixture; `python -c "from musichouse import config; print(config.get_config_dir())"` works without a QApplication
- **Verify:** `grep "PyQt6" src/musichouse/config.py` returns nothing; `pytest tests/test_config.py -v`
- **Risk:** medium — must verify config path resolution matches across platforms

---

## Phase 3.8 — Dead Code, Logging & Test Gaps

### T65: Wire up TagPreviewDialog or remove it
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** T6 `[depends on T6]` (T6 adds the tag-write worker; the preview dialog should be shown from the worker's UI callback, or removed if not wanted)
- **Files to modify:**
  - `src/musichouse/tag_writer.py` — `TagPreviewDialog` is defined (lines 20-109) and has tests (`tests/test_tag_writer.py:166-180`) but is NEVER instantiated in the app. `fixer_tab.py` calls `write_tags()` directly. Either: (a) wire up the preview dialog in `fixer_tab.py` before each `write_tags` call (show old vs new tags, require confirmation), or (b) remove the class and its tests. Option (a) is recommended — it adds a safety check before writing tags
- **Problem:** 90 lines of dead code + tests for a feature that was never wired up. Misleading — looks like preview exists but it doesn't
- **Acceptance:** either the preview dialog is shown before tag writes, or it's deleted with its tests
- **Verify:** `grep -r "TagPreviewDialog" src/musichouse/` — either shows usage in fixer_tab or returns nothing
- **Risk:** low

### T66: Add settings_changed signal — propagate to AITab without restart
- **Agent:** @fixer
- **Skills:** `pyqt-core`
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/ui/settings_dialog.py` — after `save_settings`, emit a `settings_changed` signal (or call a callback)
  - `src/musichouse/ui/main_window.py:_open_settings` — after the dialog closes, if settings changed, call `self._ai_tab.refresh_client()` (new method)
  - `src/musichouse/ui/ai_tab.py` — add `refresh_client()` method that creates a new `AIClient()` with current config. Currently `AITab.__init__` creates `self._ai_client = AIClient()` once. When the user changes settings, the existing client still holds the OLD endpoint/key/model. User must restart the app for changes to take effect
- **Problem:** settings changes don't propagate to the AI client. User changes API key, switches to AI tab, gets the same "Unknown Artist" fallback because the old (empty) key is still in use
- **Acceptance:** change API key in settings → immediately use AI tab → new key is used (no restart)
- **Verify:** manual test; add a test that changes config and calls `refresh_client`, then verifies `_ai_client.api_key` matches
- **Risk:** low

### T67: Leaderboard should reuse self._cache instead of creating new connections
- **Agent:** @fixer
- **Skills:** `sqlite`
- **Depends on:** T49 `[depends on T49]` (T49 fixes the connection leak; this fixes the root cause — not reusing the connection)
- **Files to modify:**
  - `src/musichouse/leaderboard.py:47, 68, 81` — `update_from_files`, `update_from_artist_counts`, and `reset` all create `cache = leaderboard_cache.LeaderboardCache(self.cache_path)` instead of using `self._cache`. This creates a new SQLite connection + runs table creation SQL on EVERY call. During scan, `_on_artist_count_updated` calls `update_from_artist_counts` every 100 artists → many connection creations
- **Problem:** every leaderboard update creates a new SQLite connection, runs table DDL, writes, closes. Expensive and wasteful. `self._cache` (created in `__init__`) sits unused for writes
- **Acceptance:** leaderboard uses `self._cache` for all operations; no `LeaderboardCache(self.cache_path)` calls inside leaderboard methods (only in `__init__`)
- **Verify:** `grep "LeaderboardCache(" src/musichouse/leaderboard.py` returns only the `__init__` call; `pytest tests/ -v`
- **Risk:** low — but must verify thread safety (scan worker may call leaderboard from a different thread)

### T68: AI client — robust JSON extraction from LLM responses
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** T7 `[depends on T7]` (T7 surfaces AI errors; this fixes the parsing that causes silent failures)
- **Files to modify:**
  - `src/musichouse/ai_client.py:84-103` — `_extract_result` uses `content.find('{')` + `content.rfind('}')` to find JSON. This breaks if: (a) the LLM returns explanatory text with braces before the JSON, (b) the JSON has nested objects and `rfind('}')` finds the wrong brace, (c) the LLM returns a JSON array wrapped in text. Replace with `json.JSONDecoder().raw_decode()` which parses JSON starting at a given offset and returns the parsed object + the end index. Try parsing at each `{` and `[` position until one succeeds
- **Problem:** fragile JSON extraction silently fails on common LLM response formats, returning `{"error": "Parse failed"}` which becomes "Unknown Artist"
- **Acceptance:** LLM responses with explanatory text before/after JSON parse correctly; nested JSON objects parse correctly
- **Verify:** add test cases with: plain JSON, JSON with text prefix, JSON with nested objects, JSON array, invalid JSON
- **Risk:** low

### T69: AI client — cache responses in similar_artists DB table
- **Agent:** @fixer
- **Skills:** `sqlite`
- **Depends on:** T67 `[depends on T67]` (T67 fixes leaderboard connection reuse; this adds a cache layer using the same pattern)
- **Files to modify:**
  - `src/musichouse/ai_client.py` — before making an API call for `get_similar_artists` or `get_artist_genres`, check the `similar_artists` table in the DB. If a cached response exists (with a TTL, e.g., 7 days), return it. The `similar_artists` table already exists in the DB schema but is never read. Save new responses to the table after a successful API call
- **Problem:** querying the same artist twice makes two API calls. The `similar_artists` table exists but is write-only (never read). No caching = wasted API calls = wasted money/time
- **Acceptance:** querying "Beck" twice makes only 1 API call; second query returns cached result in <10ms
- **Verify:** mock the API, query twice, assert `urlopen` called once
- **Risk:** low — additive caching layer

### T70: AI client — add SSL verification toggle for self-signed certs
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/ai_client.py:76` — `urllib.request.urlopen(req, timeout=30)` uses the default SSL context, which verifies certificates. For local LLM servers (Ollama, vLLM, LM Studio) with self-signed certs, this fails. Add an `ssl._create_unverified_context()` option controlled by a `verify_ssl` config setting (default: `True`)
  - `src/musichouse/config.py` — add `verify_ssl` to `DEFAULT_CONFIG`
  - `src/musichouse/ui/settings_dialog.py` — add a checkbox "Verify SSL certificates" (default: checked)
- **Problem:** users running local LLM servers with self-signed HTTPS certs cannot use the AI features. The SSL error is caught and swallowed into "Unknown Artist" with no indication of the cause
- **Acceptance:** unchecking "Verify SSL" allows connections to self-signed cert servers
- **Verify:** manual test with a self-signed cert server
- **Risk:** low — opt-in, default is secure

### T71: Remove `silence_stderr` dead code
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `src/musichouse/utils.py:15-28` — `silence_stderr` class is defined but never used. `load_mp3_safely` reimplements the same logic manually (lines 43-55). Remove the class. It also leaks file descriptors: `__init__` opens `os.devnull` but if the object is created without being used as a context manager, the handle is never closed
- **Problem:** dead code with a resource leak. Misleading — looks like it's used but isn't
- **Acceptance:** `silence_stderr` class is removed; `grep -r "silence_stderr" src/` returns nothing
- **Verify:** `grep -r "silence_stderr" src/`; `pytest tests/ -v`
- **Risk:** low

### T72: `write_tags` — catch specific exceptions, not bare `Exception`
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** T40, T41, T42, T43 `[depends on T40, T41, T42, T43]` (these tasks add specific exception types; this task ensures `write_tags` catches them properly)
- **Files to modify:**
  - `src/musichouse/tag_writer.py:155` — `except Exception as e:` catches everything including programming errors (e.g., the `NameError` from `load_mp3_safely`'s bug in T24). Replace with specific catches: `except (OSError, IOError) as e:` for file errors, `except eyed3.Error as e:` for eyed3 errors, let `TypeError`/`AttributeError`/`NameError` propagate as programming bugs
- **Problem:** bare `except Exception` hides programming errors as "failed to write tags." A `NameError` in `load_mp3_safely` (T24) was silently caught and returned as `False` for every file
- **Acceptance:** programming errors propagate (crash, visible); file/eyed3 errors are caught and returned as `False` with a clear log message
- **Verify:** `pytest tests/ -v`; add a test that a `TypeError` is not caught
- **Risk:** low

### T73: Add `pytest-mock` to test dependencies
- **Agent:** @fixer
- **Skills:** —
- **Depends on:** — `[independent]`
- **Files to modify:**
  - `pyproject.toml` — add `pytest-mock>=3.10.0` to `[project.optional-dependencies] test`. Currently 3 tests (`test_threading.py`, `test_progress_bar.py`) fail with `ModuleNotFoundError: pytest_mock` because they use `mocker` fixture without the dependency being declared
- **Problem:** 3 test files are broken because `pytest-mock` is not in test dependencies. The test suite reports 3 errors instead of running all tests
- **Acceptance:** `pytest tests/ -v` runs all tests with 0 errors (only failures/pass)
- **Verify:** `pytest tests/ -v 2>&1 | grep -c "ERROR"` returns 0
- **Risk:** low

### T74: Add regression test for sort corruption bug
- **Agent:** @fixer
- **Skills:** `pytest`
- **Depends on:** T1 `[depends on T1]` (T1 fixes the sort corruption; this adds the test that would have caught it)
- **Files to modify:**
  - `tests/test_fixer_tab.py` (new or existing) — add a test that: (1) loads files into the fixer tab, (2) enables sorting, (3) clicks a column header to sort, (4) edits a cell, (5) clicks Fix, (6) verifies the tags were written to the CORRECT file (not the file that was in that row position before the sort). The most critical bug in the app has no test coverage
- **Problem:** the sort corruption bug (writing tags to the wrong file after sorting) has no test. If someone re-enables sorting without syncing `_files_data`, the bug returns silently
- **Acceptance:** the test passes after T1's fix; the test fails if `setSortingEnabled(True)` is re-enabled without `_files_data` sync
- **Verify:** `pytest tests/test_fixer_tab.py -v -k sort`
- **Risk:** low

### T75: Add test for settings propagation to AITab
- **Agent:** @fixer
- **Skills:** `pytest`
- **Depends on:** T66 `[depends on T66]` (T66 adds the `refresh_client` method; this tests it)
- **Files to modify:**
  - `tests/test_ai_tab.py` (new or existing) — add a test that: (1) creates an AITab with a default AIClient (empty API key), (2) sets an API key in config, (3) calls `refresh_client()`, (4) verifies `_ai_client.api_key` matches the new key. Currently no test verifies that settings changes propagate to the AI client
- **Problem:** the "settings don't take effect without restart" bug has no test. A regression could silently re-introduce it
- **Acceptance:** test passes after T66's fix; test fails if `refresh_client()` is not called after settings change
- **Verify:** `pytest tests/test_ai_tab.py -v -k refresh`
- **Risk:** low

### T76: Add FixerTab virtualization for large libraries (10k+ files)
- **Agent:** @fixer
- **Skills:** `pyqt-widgets`
- **Depends on:** T1, T6 `[depends on T1, T6]` (T1 refactors the fixer tab; T6 adds threading; virtualization builds on the refactored tab)
- **Files to modify:**
  - `src/musichouse/ui/fixer_tab.py:47` — `_files_data: List[Dict]` holds ALL files in memory. For 10k+ files, this is 10k dict entries + 10k QTableWidget rows. QTableWidget creates a QTableWidgetItem for each cell — for 10k files × 5 columns = 50k items. Switch to `QTableView` + `QAbstractTableModel` (or `QStandardItemModel`) with `setUniformRowHeights(True)` and only render visible rows. Alternatively, use `QListWidget` with `setUniformItemSizes(True)` and custom delegates
- **Problem:** for large libraries (10k+ files), the fixer tab consumes significant memory (50k+ QTableWidgetItems) and is slow to populate (each `insertRow` triggers a layout pass). No virtualization — all rows are created upfront
- **Acceptance:** a 10k-file scan populates the fixer tab in <1s; memory usage stays flat regardless of file count
- **Verify:** benchmark test with 10k mock files
- **Risk:** high — large refactor from QTableWidget to QTableView+Model

---

## Dependency graph

```
Phase 1 (parallel):  T1 ─┬─→ T6 ──→ T8 ──→ T41, T42, T43
                      T2 ──┼─→ T3
                      T4 ──┘
Phase 1.5:           T23 (needs T1)
                      T24 (independent)
                      T25 (needs T1)
                      T26 (independent)
                      T27 (needs T1, T23, T25)
Phase 1.6:           T28 (independent) ← highest priority, unblocks caching
                      T29 (independent)
                      T30 (independent)
                      T31 (needs T28)
                      T32 (independent)
                      T33 (needs T28, optionally T3)
Phase 1.7:           T34 (needs T28)
                      T35 (independent)
                      T36 (needs T11, T28)
                      T37 (needs T6)
Phase 1.8:           T38 (needs T29)
                      T39 (needs T29)
Phase 1.9:           T59 (independent) ← broken CLI entry point
                      T60 (independent)
                      T61 (needs T32)
                      T62 (independent)
                      T63 (needs T62)
                      T64 (independent)
Phase 2:             T5 ──→ T7
                      T9 (needs T4, T5, T6)
Phase 2.5:           T40 (needs T24)
                      T41 (needs T8)
                      T42 (needs T8)
                      T43 (needs T8)
                      T44 (needs T29)
Phase 3 (parallel):  T10 ──→ T12
                      T11
                      T13 (needs T2)
                      T14, T15, T16, T17
                      T18
                      T19 (needs T1), T20 (needs T1)
                      T21 (needs T9)
Phase 3.5:           T45 (independent)
                      T46 (needs T10)
                      T47 (needs T13)
Phase 3.6:           T48 (independent)
                      T49 (independent)
                      T50 (needs T6)
                      T51 (needs T1)
                      T52 (independent)
                      T53 (needs T16)
                      T54 (needs T7, T40, T41, T42, T43)
Phase 3.7:           T55 (needs T9)
                      T56 (independent)
                      T57 (needs T5)
                      T58 (needs T45)
Phase 3.8:           T65 (needs T6)
                      T66 (independent)
                      T67 (needs T49)
                      T68 (needs T7)
                      T69 (needs T67)
                      T70 (independent)
                      T71 (independent)
                      T72 (needs T40, T41, T42, T43)
                      T73 (independent)
                      T74 (needs T1)
                      T75 (needs T66)
                      T76 (needs T1, T6)
                      T22 (needs all)
```

## Execution order suggestion

### Wave 1 (all independent — launch in parallel, max 4 concurrent)
1. **T28** (highest priority — unblocks caching architecture)
2. **T1** (unblocks T6, T19, T20, T23, T25, T50, T51, T65, T74, T76)
3. **T2** (unblocks T3, T13, T47)
4. **T4, T14, T24, T26, T29, T30, T32, T35, T45, T48, T49, T52, T56, T59, T60, T62, T64, T66, T70, T71, T73** (all independent, no file overlap)

### Wave 2 (after wave 1 deps resolve)
- **T3** (after T2), **T5, T10, T11, T15, T16, T17, T18** in parallel
- **T23, T25** (after T1), **T31** (after T28), **T33** (after T28), **T34** (after T28)
- **T38, T39** (after T29), **T44** (after T29), **T46** (after T10)
- **T61** (after T32), **T63** (after T62), **T67** (after T49), **T75** (after T66)

### Wave 3
- **T6** (after T1), **T7** (after T5), **T12** (after T10), **T13** (after T2), **T36** (after T11+T28), **T47** (after T13)
- **T68** (after T7), **T69** (after T67)

### Wave 4
- **T8** (after T6), **T37** (after T6), **T50** (after T6), **T51** (after T1)
- **T9** (after T4+T5+T6), **T19, T20** (after T1), **T21** (after T9)
- **T27** (after T1+T23+T25), **T53** (after T16), **T57** (after T5), **T58** (after T45)
- **T65** (after T6), **T74** (after T1), **T76** (after T1+T6)

### Wave 5
- **T40** (after T24), **T41, T42, T43** (after T8)
- **T55** (after T9), **T72** (after T40+T41+T42+T43)

### Wave 6
- **T54** (after T7+T40+T41+T42+T43)

### Wave 7
- **T22** (after all)

Max parallelism at any point: ~4 concurrent @fixer sessions (respecting non-overlapping file scopes).
Note: T28 should be done FIRST in wave 1 if parallelism is limited — it unblocks T31, T33, T34, T36, and makes incremental scanning actually work.
Note: T59 (broken CLI) and T60 (gitignore security) are quick wins — do them early in wave 1.
