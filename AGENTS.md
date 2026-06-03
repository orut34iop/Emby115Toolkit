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
  - The WebUI symlink workspace card shows a fixed checked list for `movies` and `tvshows`; checked rows with non-empty source and target are submitted in one `build_symlink_workspace` request.
  - The WebUI has a one-click full-flow button that front-end orchestrates as `build_symlink_workspace` followed by one `scrape_metadata` run per checked symlink target. While the full flow is active, the button becomes `取消执行`; cancellation is cooperative and must request cancellation for the currently running backend run and stop launching later steps. Do not add a separate CLI/full-flow backend action unless the product contract changes.
  - WebUI task execution uses `/v1/runs`, `/v1/runs/{run_id}`, `/v1/runs/{run_id}/cancel`, and `/v1/runs/{run_id}/events` for background runs plus SSE log/status streaming. `/v1/run` remains the synchronous compatibility API.
  - WebUI report link groups must show a bold colored final result label: success, partial, or failed, so users can quickly audit each run without opening the report.
  - Metadata scraping must log per-library progress frequently enough for SSE: current movie file, current TV first-level show directory, matched show title/year, episode progress, and per-show summary.
  - Form parameters are restored from browser localStorage on page load; do not persist access tokens.
  - Metadata provider settings are restored from browser localStorage and may include TMDB/LLM API keys by product decision; WebUI access tokens still must not be persisted.
  - Metadata scraping media libraries are shown as a fixed WebUI checklist for `movies` and `tvshows`; checked rows run sequentially as separate `scrape_metadata` requests and generate separate reports. While the standalone metadata queue is active, its button becomes `取消执行`; cancellation must request cancellation for the currently running backend run and stop launching later checked libraries.
  - Non-dry-run symlink creation on Windows must check whether the current process can actually create symlinks. If it cannot, WebUI must tell the user to enable Windows Developer Mode; WebUI must not start a UAC Administrator restart flow.
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
- `emby115_v2/config_store.py` — V2-only JSON config store. The default file is `emby115_v2.config.json` in the project root during development or next to the EXE when packaged.

Core services must only accept Context Objects and must not care whether the request came from WebUI, CLI, SSH, or a scheduled task.

Current V2 action names:

- `build_symlink_workspace` — Build the local symlink workspace from mounted CloudDrive2 source folders.
  - This action must standardize symlink target paths by media type. Movies go under a movie title folder; TV shows go under a show title folder plus a season/version second-level folder.
  - Movie title parsing must prefer a parent folder that contains both a usable title and a year over short release filenames, so files such as `eb-1080p-fap.mkv` inside `东方男孩Eastern.Boys.2013...` group under `东方男孩Eastern.Boys (2013)`.
  - When a movie parent folder has a Chinese title/year and the video filename has a same-year English title, preserve both as `Chinese.English (year)` to improve downstream metadata matching; if the parent folder already contains the English title, keep the parent title intact.
  - TV second-level folder priority is an existing source folder that contains a season marker, then a release folder derived from the episode filename, then `Season NN`.
  - TV title parsing must treat `SxxEyy` and other season markers as structural metadata, not part of the show title, so episode filenames like `小镇疑云.S02E01...` must still group under `小镇疑云`.
  - It must preserve original video filenames and mark uncertain items for manual review instead of inventing missing metadata.
  - WebUI is fixed to one movies row and one tvshows row in the first phase; CLI and core Context still accept multiple `path_pairs`.
- `scan_and_link` — Backward-compatible alias for `build_symlink_workspace`.
- `test_tmdb_config` — Test TMDB connectivity and configuration through the shared service layer.
- `test_llm_config` — Test the configured LLM provider through the shared service layer.
- `scrape_metadata` — Metadata scraping workflow for the standardized symlink media library.
  - First phase uses TMDB as the primary metadata provider and reserves provider abstraction for future sources.
  - Default TMDB language is `zh-CN`; fallback language is `en-US`.
  - TMDB JSON requests and image downloads retry transient timeout, rate-limit, and 5xx failures before marking an item failed.
  - TMDB metadata NFO output should collect actor lists as completely as TMDB provides, including TV aggregate credits when available. Rating and certification/MPAA are optional enrichment fields; missing values must not fail scraping. Episode NFO inherits show actors and includes episode rating when available.
  - TMDB NFO output should preserve available director, writer, producer, IMDb/TVDB/Wikidata IDs, movie collection, production companies/countries, spoken languages, original language, and release/first-air dates.
  - Matching strategy is rules first, TMDB search second, and LLM-assisted title expansion for movie/TV no-candidate cases. LLM-assisted decision between ambiguous TMDB candidates is reserved for a later stage.
  - Dry-run may call providers and generate a full report but must not write NFO files or download images.
  - Movie scraping currently supports TMDB search/details, `zh-CN` metadata with `en-US` fallback for missing core fields, LLM-generated alias/original-title retry when TMDB returns no movie candidates, video-stem NFO writing, and poster/fanart downloading.
  - TV scraping currently supports TMDB search/details, episode details, `zh-CN` metadata with `en-US` fallback for missing core fields, LLM-generated alias/original-title retry when TMDB returns no TV candidates, `tvshow.nfo`, episode NFO, show poster/fanart downloading, season poster downloading, and episode thumbnail downloading.
  - Optional `metadata_output.auto_rename` defaults to true. Movie first-level folders are renamed from the generated/existing `movie` NFO `title` and `year`; TV first-level folders are renamed from `tvshow.nfo` `title` and `year`. When the target folder already exists, merge non-conflicting files into it, skip conflicting filenames, remove the emptied source folder, and report the result.
  - The WebUI can submit checked movie and TV metadata libraries sequentially; each submission still uses the existing single-library `metadata_output` Context Object. CLI remains single-library through `metadata_output`.
  - LLM arbitration between multiple returned TMDB candidates and richer scoring are next-stage work.

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

V2 runtime configuration uses `emby115_v2.config.json`, not `config.yaml`. It is also gitignored and may contain TMDB/LLM API keys.

### Rust Component

A minimal `Cargo.toml` and `src/main.rs` exist but are effectively unused scaffolding (prints "Hello, world!"). The active codebase is entirely Python.
