# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Emby115Toolkit is a Python GUI utility for the 115 cloud disk + CloudDrive2 + Emby media server workflow. It creates symlinks, mirrors directory trees, manages Emby libraries, and merges scraped metadata with video files.

## Running the Application

Two entry points exist; choose based on the target platform:

- **Windows (tkinter):** `python main.py`
  - Uses `tkinterdnd2` for drag-and-drop.
  - Creating symlinks requires Administrator privileges on Windows.
- **macOS (PyQt5):** `python qt_main.py`
  - Uses native PyQt5 drag-and-drop.
  - No Administrator privileges needed for symlinks.

Both entry points share the same `config.yaml` and backend logic in `autosync/` and `emby/`.

## Installing Dependencies

```bash
pip install -r requirements.txt
# For macOS/PyQt5 version also install:
pip install PyQt5
```

## Building the Executable

```bash
build.bat
```

This runs `pyinstaller --clean build.spec` to produce `dist/Emby115Toolkit.exe`. The spec bundles `tkinterdnd2/tkdnd` data files and hidden imports required by the tkinter version.

## Project Architecture

### Dual GUI Frontends

The project maintains **two completely separate GUI layers** that do not import from each other:

- `tabs/` — tkinter tab implementations used by `main.py`. Each tab inherits from `BaseTab` which provides common widgets (path entries, log frames, drag-and-drop helpers).
- `qt_gui/` — PyQt5 tab implementations used by `qt_main.py`. Each tab is a `QWidget` subclass with native Qt drag-and-drop.

When adding a new feature or fixing a UI bug, **check both `tabs/` and `qt_gui/`** for the corresponding implementation. They are kept in sync manually.

### Backend Modules (`autosync/`)

Core business logic lives in `autosync/` and is shared by both GUIs:

- `SymlinkCreator.py` — Multi-threaded symlink/strm creation with optional path replacement.
- `MetadataCopyer.py` — Copies metadata files (nfo, posters, subtitles) alongside symlinks.
- `TreeMirror.py` — Parses a 115-exported directory tree text file and recreates an empty file tree locally.
- `FileMerger.py` — Moves video files into folders that contain matching nfo files.
- `SymlinkDeleter.py`, `SymlinkChecker.py`, `SymlinkDirChecker.py` — Folder cleanup utilities.
- `AutoUploader.py` — Automation orchestrator.
- `MedadataChecker.py` — Integrity checker for scraped metadata.

### Emby Integration (`emby/`)

- `EmbyOperator.py` — Single module wrapping Emby Server API calls. Handles duplicate checking (by TMDB ID), version merging, and genre translation (English → Chinese).

### Shared Utilities (`utils/`)

- `config.py` — Singleton `Config` class managing `config.yaml`. Uses a recursive merge strategy so new default keys are automatically added to existing user configs. Resolves `config_dir` to the EXE directory when `sys.frozen` is True, otherwise the project root.
- `logger.py` — Thread-safe `setup_logger()` that outputs to both a tkinter `Text` widget (via a queued batch handler) and rotating log files.
- `history_entry.py` — Helper for history-aware input widgets.
- `listdir.py` — Cross-platform file listing helper.

### Configuration (`config.yaml`)

Runtime configuration is stored in YAML at the project root (or next to the EXE when packaged). Sections correspond to tabs/features:

- `export_symlink` — source folders, target folder, suffixes, thread count, path replacement settings.
- `merge_file` — scrap folder and target folder.
- `merge_version`, `update_genres` — Emby URL and API key.
- `mirror_115_tree` — tree file path and export folder.
- `last_tab_index` — remembers the active tab across restarts.

**Do not commit `config.yaml`** — it is gitignored because it contains user-specific paths and API keys.

### Rust Component

A minimal `Cargo.toml` and `src/main.rs` exist but are effectively unused scaffolding (prints "Hello, world!"). The active codebase is entirely Python.
