# Emby115Toolkit V2 Checkpoint

This document records the current V2 development baseline. Keep it updated whenever code changes affect architecture, commands, workflows, or user-visible behavior.

## Confirmed Product Direction

- First phase targets Windows only.
- WebUI is the only main graphical interface for V2.
- CLI is an official automation entry point.
- Qt/tkinter are legacy references and are not V2 feature targets.
- WebUI and CLI are facade entrances. They must call the same core service layer through Context Objects.
- Every run must produce auditable artifacts: HTML report, JSON report, and log file.

## Current Implemented Foundation

- V2 package: `emby115_v2/`
- Context contract: `emby115_v2/context.py`
- CLI facade: `emby115_v2/cli.py`
- WebUI backend and minimal browser page: `emby115_v2/web/`
- Workflow runner: `emby115_v2/workflow/runner.py`
- Report writer: `emby115_v2/reports/writer.py`
- First core service: `emby115_v2/services/symlink_service.py`
- Metadata foundation services: `emby115_v2/services/metadata_service.py`
- V2 local JSON config store: `emby115_v2/config_store.py`

## Action Names

Primary action:

```bash
python main.py --action build_symlink_workspace
```

Compatibility alias:

```bash
python main.py --action scan_and_link
```

Metadata foundation actions:

```bash
python main.py --action test_tmdb_config --config emby115_v2.config.json
python main.py --action test_llm_config --config emby115_v2.config.json
python main.py --action scrape_metadata --config emby115_v2.config.json --dry-run
```

`build_symlink_workspace` maps to the confirmed workflow step "构建本地软链接工作区":

- scan mounted CloudDrive2 source folders;
- filter video files;
- build standardized local library paths instead of blindly mirroring the source tree;
- for movies, place symlinks under a movie title folder with explicit year when the year is present;
- for TV shows, place symlinks under a show title folder and a season/version second-level folder;
- TV second-level folder priority is: existing source folder that contains a season marker, then release folder derived from episode filename, then `Season NN`;
- keep original video filenames unchanged;
- keep uncertain TV/movie items in their original relative path and mark them for manual review;
- create Windows symlinks;
- skip existing targets for incremental sync;
- report broken local symlinks without deleting them.

`scrape_metadata` maps to the confirmed workflow step "刮削媒体元数据":

- first phase uses TMDB as the primary metadata provider, with provider abstraction reserved for future sources;
- default TMDB metadata language is `zh-CN`, with `en-US` fallback for failed searches or missing fields;
- matching strategy is rules first, then TMDB search, then LLM-assisted decision only when candidates are ambiguous;
- movie TMDB search/details are implemented; movie NFO and image filenames follow each video file stem, not the first-level folder name;
- movie details use `zh-CN` first and fetch `en-US` details to fill missing title/overview fields when needed;
- non-dry-run movie scraping writes Emby-compatible movie NFO and downloads poster/fanart when TMDB image paths are available;
- TV output uses `tvshow.nfo`, show poster/fanart, and per-episode NFO/thumb filenames following each episode video stem;
- dry-run scans, parses, calls providers when implemented, and reports the plan without writing NFO or downloading images;
- default `overwrite_existing=false`; existing NFO/images are skipped unless overwrite is enabled;
- default `auto_rename=false`; when enabled after successful NFO metadata, movie first-level folders are renamed from the generated/existing `movie` NFO `title` and `year`, while TV first-level folders are renamed from `tvshow.nfo` `title` and `year`;
- auto rename uses `title (year)`, skips when the target folder already exists, and records the result in the report;
- current implementation provides the Context Object contract, WebUI/CLI actions, config testing, config persistence APIs, movie TMDB matching, movie NFO writing, poster/fanart downloading, and TV media-library scan skeleton. TV TMDB matching, `tvshow.nfo`, episode NFO, episode thumbnails, LLM candidate arbitration, and richer scoring are next-stage work.

## Current WebUI Status

Implemented:

- FastAPI app factory;
- minimal browser UI at `/`;
- path pair media type uses fixed radio options: `movies` / `tvshows`;
- WebUI form parameters are persisted in browser localStorage and restored on page load, excluding access token;
- metadata provider settings are persisted in browser localStorage, including TMDB/LLM API keys by user request;
- pending non-dry-run requests that trigger UAC are saved in browser sessionStorage, excluding access token;
- `/health`;
- `/v1/actions`;
- `/v1/admin/status`;
- `/v1/admin/restart-elevated`;
- `/v1/config/metadata`;
- `/v1/run`;
- `/v1/reports/{run_id}/report.html`;
- `/v1/reports/{run_id}/report.json`;
- access token enforcement for `/v1/*` when configured;
- single-run execution lock;
- non-dry-run symlink creation is blocked unless the Windows process is running as Administrator;
- WebUI can request an Administrator restart through Windows UAC after user confirmation, wait for the elevated WebUI to become ready, reload, and automatically resume the original request;
- WebUI metadata section includes TMDB/LLM settings, test buttons, local config load/save buttons, auto rename, and a `scrape_metadata` dry-run entry;
- `python main.py --serve-web` backend startup path.

Not yet implemented:

- real-time logs/status;
- reports center;
- review center.

Start local WebUI:

```bash
python main.py --serve-web
```

Start LAN WebUI with token:

```bash
python main.py --serve-web --host 0.0.0.0 --access-token YOUR_TOKEN
```

Listening on a non-localhost address without `--access-token` must fail.

## Documentation Rule

Every future code change must update the relevant docs in the same change set when it affects:

- CLI commands;
- WebUI/API behavior;
- workflow names;
- configuration schema;
- reports;
- service contracts;
- user-facing behavior.
