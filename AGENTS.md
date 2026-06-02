# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

Emby115Toolkit is a Windows-first utility for the 115 cloud disk + CloudDrive2 + Emby media server workflow. Version 1.x is a Python desktop GUI utility. Version 2.0 is being developed as a WebUI + CLI automation system with a shared core service layer, Context Object contracts, reports, LLM-assisted library normalization, and TMDB metadata acquisition.

## Development Discipline

- Every code change must include matching documentation updates when behavior, commands, architecture, configuration, workflow names, or user-visible output changes.
- Commit and push promptly after verified work. Keep commits scoped and intentional.
- Do not silently stage unrelated files. Confirm scope with `git status -sb` before committing.
- Run focused tests for changed areas and the full test suite when practical before pushing.

## Running the Application

Version 2.0 is Windows-only in the first phase and has two official facades:

- **CLI:** `python main.py --action build_symlink_workspace ...`
  - Supports local Windows Terminal, PowerShell/CMD, Windows OpenSSH remote sessions, and non-interactive scheduled execution.
  - CLI must not depend on GUI imports, pop dialogs, or wait for stdin in non-interactive mode.
- **WebUI backend:** `python main.py --serve-web`
  - Current state: minimal browser UI exists for `build_symlink_workspace`.
  - Path pair media type must stay as fixed radio choices (`movies` / `tvshows`), not free-form text.
  - Non-dry-run symlink creation on Windows must check Administrator status and route through the user-confirmed UAC restart flow when needed.
  - Non-localhost listening requires `--access-token`.

Version 1.x legacy desktop entry points still exist:

- **Windows (tkinter legacy):** `python main.py`
  - Uses `tkinterdnd2` for drag-and-drop.
  - Creating symlinks requires Administrator privileges on Windows.
- **macOS (PyQt5 legacy/incomplete):** `python qt_main.py`
  - Uses native PyQt5 drag-and-drop.
  - No Administrator privileges needed for symlinks.

V2 explicit CLI/WebUI flags are routed before tkinter imports, so headless CLI usage remains independent of the legacy GUI dependencies.

## Installing Dependencies

```bash
pip install -r requirements.txt
# For legacy macOS/PyQt5 version also install:
pip install PyQt5
```

## Building the Executable

```bash
build.bat
```

This runs `pyinstaller --clean build.spec` to produce `dist/Emby115Toolkit.exe`. The spec bundles `tkinterdnd2/tkdnd` data files and hidden imports required by the tkinter version.

## Project Architecture

### V2 Architecture

V2 uses a strict facade architecture:

- `emby115_v2/context.py` — Standard Context Object data contracts. WebUI JSON and CLI args must be deserialized into these objects before entering core services.
- `emby115_v2/cli.py` — CLI facade.
- `emby115_v2/web/` — WebUI backend facade.
- `emby115_v2/workflow/` — Workflow runner and service dispatch.
- `emby115_v2/services/` — Core services shared by WebUI and CLI.
- `emby115_v2/reports/` — HTML/JSON report generation.

Core services must only accept Context Objects and must not care whether the request came from WebUI, CLI, SSH, or a scheduled task.

Current V2 action names:

- `build_symlink_workspace` — Build the local symlink workspace from mounted CloudDrive2 source folders.
  - This action must standardize symlink target paths by media type. Movies go under a movie title folder; TV shows go under a show title folder plus a season/version second-level folder.
  - TV second-level folder priority is existing source season/version folder, then a release folder derived from the episode filename, then `Season NN`.
  - It must preserve original video filenames and mark uncertain items for manual review instead of inventing missing metadata.
- `scan_and_link` — Backward-compatible alias for `build_symlink_workspace`.

### Legacy Dual GUI Frontends

Version 1.x maintains two GUI layers:

- `tabs/` — tkinter tab implementations used by `main.py`. Each tab inherits from `BaseTab` which provides common widgets (path entries, log frames, drag-and-drop helpers).
- `qt_gui/` — PyQt5 tab implementations used by `qt_main.py`. Each tab is a `QWidget` subclass with native Qt drag-and-drop.

Do not add V2 features to `tabs/` or `qt_gui/`. They are legacy references only unless the user explicitly asks to fix 1.x behavior.

### Legacy Backend Modules (`autosync/`)

Version 1.x business logic lives in `autosync/` and is shared by legacy GUIs:

- `SymlinkCreator.py` — Multi-threaded symlink/strm creation with optional path replacement.
- `MetadataCopyer.py` — Copies metadata files (nfo, posters, subtitles) alongside symlinks.
- `TreeMirror.py` — Parses a 115-exported directory tree text file and recreates an empty file tree locally.
- `FileMerger.py` — Moves video files into folders that contain matching nfo files.
- `SymlinkDeleter.py` — Folder cleanup utility.

Some older documentation may mention modules such as `SymlinkChecker.py`, `SymlinkDirChecker.py`, `AutoUploader.py`, or `MedadataChecker.py`; these files are not present in the current workspace.

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
