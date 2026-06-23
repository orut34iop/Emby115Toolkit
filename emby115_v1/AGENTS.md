# AGENTS.md

This file provides guidance to Codex when working in the V1 desktop GUI repository.

## Project Overview

Emby115Toolkit V1 is the legacy Python desktop GUI utility for the 115 cloud disk + CloudDrive2 + Emby media server workflow. V2 WebUI/CLI automation lives in the separate `emby115_v2` tree and should not be added here.

## Development Discipline

- Every code change must include matching documentation updates when behavior, commands, architecture, configuration, workflow names, or user-visible output changes.
- Commit and push promptly after verified work. Keep commits scoped and intentional.
- Do not silently stage unrelated files. Confirm scope with `git status -sb` before committing.
- Run focused tests for changed areas and the full test suite when practical before pushing.

## Running the Application

- **Windows legacy tkinter:** `python main.py`
  - Uses `tkinterdnd2` for drag-and-drop.
  - Creating symlinks requires Administrator privileges on Windows.
- **macOS legacy PyQt5:** `python qt_main.py`
  - Uses native PyQt5 drag-and-drop.
  - No Administrator privileges needed for symlinks.

## Installing Dependencies

```bash
pip install -r requirements.txt
```

## Building the Executable

```bash
scripts/build.bat
```

This runs `pyinstaller --clean scripts/build.spec` to produce `dist/Emby115Toolkit.exe`. The spec bundles `tkinterdnd2/tkdnd` data files and hidden imports required by the tkinter version.

## Project Architecture

- `tabs/` — tkinter tab implementations used by `main.py`.
- `qt_gui/` — PyQt5 tab implementations used by `qt_main.py`.
- `autosync/` — shared V1 filesystem workflow logic.
- `emby/` — Emby Server API integration.
- `utils/` — config, logging, history, and file listing helpers.

Do not add V2 WebUI/CLI features to V1. Keep V1 changes focused on legacy desktop behavior.

## Configuration

Runtime configuration is stored in `config.yaml` in this V1 directory or next to the EXE when packaged. Do not commit `config.yaml`; it is gitignored because it contains user-specific paths and API keys.
