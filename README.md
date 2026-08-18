# musichouse
[![License](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](http://www.gnu.org/licenses/gpl-3.0)   

MP3 metadata fixer and AI artist suggestions tool.

## Features

- Scan MP3 files recursively in a directory
- Fix missing ID3 tags using filename pattern "artist - title"
- Artist inference from parent folder name
- AI suggestions for similar artists (OpenAI-compatible API)
- Artist leaderboard with caching
- Duplicate MP3 detection (fingerprint-based with metadata fallback)
- AI folder organization analysis (MusicBrainz-assisted)

<img width="815" height="639" alt="Image" src="https://github.com/user-attachments/assets/d8e76e40-c708-498e-b34e-4f0a20d8b249" />
<img width="815" height="639" alt="Image" src="https://github.com/user-attachments/assets/c5c43262-beac-4a38-8446-3e6b873c3f1a" />
<img width="815" height="639" alt="Image" src="https://github.com/user-attachments/assets/4059afa4-6526-4dc1-8a27-651538b73444" />

## Requirements

- Python 3.10+
- PyQt6
- eyed3

### Optional: Chromaprint for Duplicate Detection

For fingerprint-based duplicate detection (more accurate than metadata-only mode), install `fpcalc`:

- **Linux (Debian/Ubuntu)**: `sudo apt install chromaprint-tools`
- **macOS**: `brew install chromaprint`
- **Windows**: Download from the [Chromaprint releases page](https://github.com/acoustid/chromaprint/releases)

The app automatically detects `fpcalc` on startup and uses it if available.

## Usage

From the project directory:

```bash
cd /home/mte90/Desktop/Prog/MusicHouse
python3.12 main.py
```

The configuration (API endpoint, model, key) is set via the Settings dialog in the app.

The scan directory selection remembers the last used directory.

## Duplicate Detection

The Duplicates tab finds identical or near-identical MP3 files using two modes:

**Fingerprint mode** (requires `fpcalc`):
- Computes audio fingerprints using Chromaprint
- Groups files by duration (±2s tolerance), then compares fingerprints
- Uses ≥85% similarity threshold to identify duplicates
- Detects duplicates even when metadata differs (e.g., different tags, renamed files)

**Metadata-only mode** (default, no dependencies):
- Groups files by normalized artist + title
- Useful when `fpcalc` is not installed
- Less accurate — relies on tag consistency

### How to use

1. Navigate to the **Duplicates** tab
2. Click **Find Duplicates**
3. If `fpcalc` is available, fingerprinting runs first (status bar shows progress)
4. Duplicate groups are displayed in a table, with similarity percentages and durations
5. Checkboxes pre-select all but the first file in each group (the reference copy)
6. Review the selected files, adjust checkboxes if needed
7. Click **Delete Selected** — files are sent to trash (via `send2trash`) first, falling back to permanent deletion
8. Confirm deletion in the dialog

Example duplicate group:
```
Group 1:
  - /music/Artist1/Song.mp3 (Reference, 100% similarity)
  - /music/Backup/Song (1).mp3 (98.5% similarity, 3:42 duration)
  - /music/Old/Song.mp3 (97.2% similarity, 3:41 duration)
```

## AI Folder Organization

The Organize tab analyzes your folder structure and suggests improvements using AI and MusicBrainz genre data.

### How it works

1. **Folder classification**: Scans the directory tree, classifying each folder:
   - **GENRE_CONTAINER**: Has subfolders, no direct MP3s (already organized — skipped)
   - **CORRECT_ARTIST**: Single artist, folder name matches artist (no action needed)
   - **MISNAMED_ARTIST**: Single artist, folder name doesn't match (suggested rename)
   - **MIXED**: Multiple artists in one folder (flagged for splitting)
   - **EMPTY**: No files, no subfolders

2. **MusicBrainz integration**:
   - Fetches artist genres from the free MusicBrainz API
   - No authentication required, rate-limited to 1 request/second
   - Requires `User-Agent` header (set to `MusicHouse/1.0.0`)
   - Genres are cached in SQLite to avoid redundant API calls

3. **AI suggestions**:
   - Uses the configured LLM backend (local or remote, set in Settings)
   - Analyzes genre distribution and folder structure
   - Suggests file moves to appropriate artist/genre folders
   - Suggests folder renames for misnamed artist folders

### How to use

1. Navigate to the **Organize** tab
2. Click **Analyze**
3. Wait for the analysis to complete (progress shown in status bar)
4. Review suggestions in the table:
   - **Move** suggestions: File should be moved to a different folder
   - **Rename** suggestions: Folder name should be updated to match artist
5. Each suggestion includes a reason (e.g., "Artist 'The Beatles' belongs in folder 'The Beatles'")
6. Check the actions you want to apply
7. Click **Apply Selected** — confirm in the dialog
8. Changes are applied one by one (move/rename operations)

All actions require explicit user confirmation — nothing is auto-applied.

### Example suggestions

```
Move: /music/Misc/Abbey Road.mp3 → /music/The Beatles/Abbey Road.mp3
Reason: Artist 'The Beatles' detected from metadata; folder 'The Beatles' exists.

Rename: /music/Beatles, The → /music/The Beatles
Reason: Folder name 'Beatles, The' doesn't match artist 'The Beatles'.
```

## Development

```bash
pip3.12 install pytest pytest-qt
pytest3.12 -v
```
