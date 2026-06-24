# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Emby115Toolkit is a Python desktop utility for integrating 115 cloud drive, CloudDrive2, and Emby media server. It creates symlinks, manages Emby libraries, merges metadata with video files, and mirrors 115 directory trees locally.

## Stack

- **Language**: Python 3.x
- **GUI**: Dual frontend — tkinter (`windows_main.py`) for Windows and PyQt5 (`macos_main.py`) for macOS
- **Testing**: pytest
- **Config**: YAML via `utils/config.py` singleton

## Commands

### Run
- `python windows_main.py` — Launch tkinter version (Windows only)
- `python macos_main.py` — Launch PyQt5 version (macOS only)

### Test
- `pytest` — Run all tests
- `pytest -m unit` — Run unit tests only
- `pytest -m integration` — Run integration tests
- `pytest -m "not slow"` — Exclude slow tests
- `pytest tests/unit/services/test_symlink_creator.py` — Run single test file

### Dependencies
- `pip install -r requirements.txt`

## Architecture

### Dual GUI Frontends
The app maintains **two parallel GUI implementations** that share the same business logic:

- **tkinter** (`windows_main.py` + `windows_gui/`): Windows only. Uses `TkinterDnD.Tk` for drag-and-drop. Each tab inherits from `windows_gui/base_tab.py`. Do not add macOS- or Linux-specific tkinter behavior.
- **PyQt5** (`macos_main.py` + `macos_gui/`): macOS only. Uses native Qt drag-and-drop. `macos_gui/main_window.py` wires tabs directly as QWidgets.

When adding a new tab or UI feature, both frontends may need updates unless the change is backend-only. macOS support should be implemented only in the PyQt5 frontend. Linux is not supported.

### Business Logic (`services/`)
Core operations are GUI-agnostic classes:

- `SymlinkCreator` — Creates symlinks or `.strm` files with optional path replacement and multi-threading
- `TreeMirror` — Parses 115-exported directory tree files and generates local empty-file mirrors
- `FileMerger` — Moves video files into matching NFO folders
- `SymlinkDeleter`, `SymlinkChecker`, `SymlinkDirChecker` — Symlink maintenance
- `MetadataCopier`, `MetadataChecker` — Metadata file operations
- `AutoUploader` — Auto-upload functionality

These classes accept a `logger` parameter and use `threading.Event` (`stop_flag`) for cancellation.

### Media Server Integration (`media_server/`)
`MediaServerClient` encapsulates Emby/Jellyfin API calls:
- Queries movies by TMDB ID for duplicate detection
- Merges multi-version movies
- Updates genre names from English to Chinese
- Uses explicit constructor names: `(server_url, api_key, username, server_type)`

### Utilities (`utils/`)
- `config.py` — Singleton `Config` class backed by `config.yaml` in project root. Uses recursive merge to ensure default keys exist and migrates legacy config keys to the current schema.
- `logger.py` — `setup_logger()` returns a logger with optional `tk.Text` widget handler (`TextHandler` uses a queue + `after` polling for thread safety) and `RotatingFileHandler`.
- `listdir.py` — Cross-platform directory listing helper
- `history_entry.py` — Input history persistence

### Testing (`tests/`)
- `conftest.py` ensures the project root is first in `sys.path` and provides shared fixtures (`temp_dir`, `sample_nfo_content`, `mock_emby_response`, `create_test_file_structure`, etc.)
- Tests are organized under `tests/unit/` and `tests/integration/`
- pytest markers: `slow`, `integration`, `unit`, `performance`

## Verification
- Run `pytest` before shipping changes.
- If changing GUI code, verify the affected frontend: `windows_main.py` for Windows tkinter, `macos_main.py` for macOS PyQt5.

## Working agreement
- Prefer small, reviewable changes.
- Keep shared defaults in `.claw.json`; reserve `.claw/settings.local.json` for machine-local overrides.
- Do not overwrite existing `CLAUDE.md` content automatically; update it intentionally when repo workflows change.
