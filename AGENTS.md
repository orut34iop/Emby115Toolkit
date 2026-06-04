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
  - The WebUI `软链接导出` card shows a fixed checked list for `movies` and `tvshows`; checked rows with non-empty source and target are submitted in one `build_symlink_workspace` request.
  - The WebUI has a one-click full-flow button that front-end orchestrates as `build_symlink_workspace`, then one `scrape_metadata` run per checked symlink target, then `build_cloud_scraped_library` using the symlink targets as cloud-import sources and the cloud card targets as final D-drive destinations. Full flow uses upstream outputs as downstream inputs: metadata card library paths and cloud card source paths are only used for standalone card execution and are overridden by the symlink target paths during full-flow execution. While full flow is active, those overridden downstream inputs must be visually locked/disabled and display the effective symlink target path, and the downstream metadata/cloud enable checkboxes must also be locked to the effective full-flow participation state. All locked controls restore their original standalone values after the flow ends. While the full flow is active, the button becomes `取消执行`; cancellation is cooperative and must request cancellation for the currently running backend run and stop launching later steps. Full flow must automatically enter the cloud-import stage without an extra confirmation prompt. Standalone non-dry-run cloud import that moves real videos still asks for explicit confirmation because the C-drive symlink workspace will become stale. Do not add a separate CLI/full-flow backend action unless the product contract changes.
  - WebUI task execution uses `/v1/runs`, `/v1/runs/{run_id}`, `/v1/runs/{run_id}/cancel`, and `/v1/runs/{run_id}/events` for background runs plus SSE log/status streaming. `/v1/run` remains the synchronous compatibility API.
  - WebUI layout must remain usable at 100% browser zoom on common desktop widths: the workflow area and result panel use a responsive two-column layout, collapse to one column on narrower viewports, and long report paths/log lines must wrap inside their panels without creating whole-page horizontal scrolling.
  - WebUI report link groups must show a bold colored final result label: success, partial, or failed, so users can quickly audit each run without opening the report.
  - Generated HTML reports must include local filtering controls for operation records: status, action, media type, keyword search, and quick filters for `manual_review` and `failed` records. JSON report shape remains unchanged.
  - Metadata scraping must log per-library progress frequently enough for SSE: current movie file, current TV first-level show directory, matched show title/year, episode progress, and per-show summary.
  - Form parameters are restored from browser localStorage on page load; do not persist access tokens.
  - Metadata provider settings are restored from browser localStorage and may include TMDB/LLM API keys by product decision; WebUI access tokens still must not be persisted.
  - Metadata scraping media libraries are shown as a fixed WebUI checklist for `movies` and `tvshows`; checked rows run sequentially as separate `scrape_metadata` requests and generate separate reports. While the standalone metadata queue is active, its button becomes `取消执行`; cancellation must request cancellation for the currently running backend run and stop launching later checked libraries.
  - The WebUI `网盘同步` card is shown as a fixed checklist for `movies` and `tvshows`. Each row maps a local symlink workspace to a new cloud-side target directory. The card defaults to dry-run plus metadata-only so first clicks do not move real videos. Before a non-dry-run cloud import that moves real videos, standalone cloud execution also requires explicit confirmation. While this task or its CloudDrive2 probe is active, the button becomes `取消执行` and cancellation must request cancellation for the active backend run.
  - The WebUI `网盘同步` card exposes CloudDrive2 upload wait settings and a `测试 CloudDrive2 上传探测` button. The probe submits `test_clouddrive2_upload_wait` with the first checked row and writes a small probe file in non-dry-run mode.
  - Saving WebUI configuration to the V2 JSON config includes metadata provider settings and cloud library/CloudDrive2 settings. Browser localStorage remains the primary page-state restore mechanism.
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
  - Each `path_pairs[].target` local symlink workspace must be missing or an existing empty directory before execution. If it already contains files or folders, the action must fail with a report row and must not auto-delete or merge into the existing workspace.
  - This action must standardize symlink target paths by media type. Movies go under a movie title folder; TV shows go under a show title folder plus a season/version second-level folder.
  - Movie title parsing must prefer a parent folder that contains both a usable title and a year over short release filenames, so files such as `eb-1080p-fap.mkv` inside `东方男孩Eastern.Boys.2013...` group under `东方男孩Eastern.Boys (2013)`.
  - When a movie parent folder has a Chinese title/year and the video filename has a same-year English title, preserve both as `Chinese.English (year)` to improve downstream metadata matching; if the parent folder already contains the English title, keep the parent title intact.
  - TV second-level folder priority is an existing source folder that contains a season marker, then a release folder derived from the episode filename, then `Season NN`. Pure season folders such as `S01`, `Season 1`, or `第一季` must be normalized to `Season 01` for Emby/Kodi compatibility; release/version folders that include season plus quality/version text may keep their original names.
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
  - Movie scraping currently supports TMDB search/details, `zh-CN` metadata with `en-US` fallback for missing core fields, rule-based query expansion, known TMDB-ID direct matches, LLM-generated alias/original-title retry when TMDB returns no movie candidates, video-stem NFO writing, and poster/fanart downloading. Normal single-movie folders use the folder name as the search source; first-level folders without a year that contain multiple videos are treated as mixed/category folders, so each movie is searched from its own video filename instead of the parent folder name. Movie TMDB search text strips non-year bracket notes such as actor names or subtitle tags, while preserving year markers. Rule-based expansion tries known stylized aliases, romanization aliases, and Chinese title fragments before the raw title, such as `GirlS/Girls (2010)` -> `囡囡`, `JinChun (1993)` -> `禁春`, `18P2P色模SuperModels[...]` -> `色模`, `1983欲望之翼BD720P...` -> `欲望之翼`, `93女爱男欢（...）-93女爱男欢` -> `93女爱男欢`, `97风流梦（...）-97风流梦` -> `97风流梦`, and `三分之一情人（...）-三分之一情人` -> `三分之一情人`. Known direct matches cover TMDB search gaps such as `janinhan.miyongsaui (2014/2015)` -> TMDB `322587` and `96超级床上接班人` -> TMDB `926910`; local metadata overrides may preserve the user-verified title when TMDB's localized title omits a distinguishing prefix.
  - TV scraping currently supports TMDB search/details, episode details, `zh-CN` metadata with `en-US` fallback for missing core fields, LLM-generated alias/original-title retry when TMDB returns no TV candidates, `tvshow.nfo`, episode NFO, show poster/fanart downloading, season poster downloading, and episode thumbnail downloading.
  - Optional `metadata_output.auto_rename` defaults to true. Movie auto rename is per-video: after a movie scrape/write/skip-existing record, the video symlink and same-stem NFO/images/sidecars are moved under the library root into `title (year)` from the generated/existing `movie` NFO, allowing mixed folders to be split into standard first-level movie folders. TV first-level folders are renamed from `tvshow.nfo` `title` and `year`. When the target folder already exists, merge non-conflicting files into it, skip conflicting filenames, remove emptied source folders, and report the result.
  - The WebUI can submit checked movie and TV metadata libraries sequentially; each submission still uses the existing single-library `metadata_output` Context Object. CLI remains single-library through `metadata_output`.
  - LLM arbitration between multiple returned TMDB candidates and richer scoring are next-stage work.
- `build_cloud_scraped_library` — Build a cloud-side scraped library from the local symlink workspace.
  - `path_pairs[].source` is the local C-drive symlink workspace; `path_pairs[].target` is the new D-drive organized cloud library directory.
  - Stage A mirrors the whole workspace directory tree to the target and copies every non-symlink file while excluding symlink files/directories.
  - After Stage A, the default `cloud_library_output.upload_wait_strategy=fixed` waits `cloud_library_output.wait_minutes` minutes, default `60`, to allow CloudDrive2/115 asynchronous upload cache to flush before moving videos.
  - `cloud_library_output.upload_wait_strategy=clouddrive2` uses CloudDrive2 gRPC upload task polling instead of fixed waiting. It monitors mounted-filesystem upload tasks (`UploadFileInfo.operatorType=Mount`) under the target path. Defaults are `poll_interval_seconds=0.5` and `settle_seconds=30` because `GetUploadFileList` behaves like a short-lived active-task snapshot. If no matching tasks are observed through the first quiet window, treat the upload queue as already quiet and continue because small metadata files may upload before polling can see them; cloud-library reports must record this as wait success while preserving `raw_status=not_observed`. Once a matching task is observed, the upload is considered started; completion is confirmed only after the task reaches a terminal success state or after a later continuous quiet window with no matching tasks. If confirmation times out, Stage B is skipped and the run reports `partial`; real CloudDrive2 upload task errors still fail before moving videos.
  - `cloud_library_output.upload_wait_strategy=clouddrive2_or_fixed` is the recommended real-world transition mode: it first tries CloudDrive2 upload task polling and falls back to the fixed minute wait when tasks are not observable or the API is unavailable.
  - Stage B walks the original workspace symlinks, resolves each real video target, and moves that real D-drive video into the same relative path under the new cloud library target. Symlink target resolution must prefer `os.readlink()` and normalize Windows extended-length paths such as `\\?\D:\...`; CloudDrive2/WinFSP targets may be directly readable while `Path.resolve(strict=True)` raises WinError 1005.
  - Cloud-side target directory creation must tolerate CloudDrive2/WinFSP transient unsupported-operation errors. Retry directory creation and record unrecoverable `create_directory` failures in the report instead of letting the background run crash without a report.
  - Dry-run must not create directories, copy files, wait, or move videos; it only reports the planned copy/move operations.
  - Existing metadata and video targets are skipped by default. `overwrite_metadata` and `overwrite_videos` are separate explicit options.
  - This is a high-risk final migration/archive step because moving real videos makes the original symlink workspace links stale.
- `test_clouddrive2_upload_wait` — Verify whether CloudDrive2 mounted-disk writes can be observed through gRPC upload task polling.
  - The action writes a small probe file under `path_pairs[0].target/.emby115_cd2_probe/`, waits for matching `Mount` upload tasks, then deletes the local probe file after successful observation.
  - It uses `clouddrive2.endpoint`, `clouddrive2.api_token`, `poll_interval_seconds`, `settle_seconds`, and `max_wait_minutes`; by default it polls every 0.5 seconds and uses a 30-second quiet window.
  - Dry-run only reports the probe plan and does not write files or connect to CloudDrive2.
  - This action is the required validation step before changing production cloud-library runs from fixed waiting to CloudDrive2 task-based waiting.

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
