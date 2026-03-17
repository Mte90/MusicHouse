# musichouse
[![License](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](http://www.gnu.org/licenses/gpl-3.0)   

MP3 metadata fixer and AI artist suggestions tool.

## Features

- Scan MP3 files recursively in a directory
- Fix missing ID3 tags using filename pattern "artist - title"
- Artist inference from parent folder name
- AI suggestions for similar artists (OpenAI-compatible API)
- Artist leaderboard with caching

<img width="815" height="639" alt="Image" src="https://github.com/user-attachments/assets/d8e76e40-c708-498e-b34e-4f0a20d8b249" />
<img width="815" height="639" alt="Image" src="https://github.com/user-attachments/assets/c5c43262-beac-4a38-8446-3e6b873c3f1a" />
<img width="815" height="639" alt="Image" src="https://github.com/user-attachments/assets/4059afa4-6526-4dc1-8a27-651538b73444" />

## Requirements

- Python 3.10+
- PyQt6
- eyed3

## Usage

From the project directory:

```bash
cd /home/mte90/Desktop/Prog/MusicHouse
python3.12 main.py
```

The configuration (API endpoint, model, key) is set via the Settings dialog in the app.

The scan directory selection remembers the last used directory.

## Development

```bash
pip3.12 install pytest pytest-qt
pytest3.12 -v
```
