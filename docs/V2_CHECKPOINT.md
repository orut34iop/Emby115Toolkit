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

CLI `scrape_metadata` still consumes one `metadata_output.media_type/library_path` at a time. WebUI may submit the fixed movie/TV checklist sequentially as separate `scrape_metadata` runs. While this standalone metadata queue is active, the metadata button displays `取消执行`; cancellation is cooperative, requests cancellation for the current backend run, and stops launching later checked libraries.

WebUI also provides a one-click full flow. This is front-end orchestration only, not a new backend workflow action: it runs one `build_symlink_workspace` request first, then derives metadata libraries from the checked symlink target directories and submits one `scrape_metadata` request per media type. While the full flow is active, the same button displays `取消执行`; cancellation is cooperative, requests cancellation for the current backend run, and stops launching later steps. CLI does not yet expose a one-click full-flow action.

`build_symlink_workspace` maps to the confirmed workflow step "构建本地软链接工作区":

- scan mounted CloudDrive2 source folders;
- WebUI presents a fixed checked list for movies and TV shows; checked rows with non-empty source/target paths are submitted together as one `build_symlink_workspace` request;
- CLI and the core Context Object continue to accept a `path_pairs` array, including multiple pairs when supplied outside the WebUI;
- filter video files;
- build standardized local library paths instead of blindly mirroring the source tree;
- for movies, place symlinks under a movie title folder with explicit year when the year is present;
- movie title parsing prefers a parent folder that contains both a usable title and a year over short release filenames, avoiding folders such as `eb (2013)` when the source folder has `东方男孩Eastern.Boys.2013...`;
- for TV shows, place symlinks under a show title folder and a season/version second-level folder;
- TV second-level folder priority is: existing source folder that contains a season marker, then release folder derived from episode filename, then `Season NN`;
- TV show title parsing treats `SxxEyy` and season markers as structural metadata rather than title text, so files such as `小镇疑云.S02E01...` are grouped under the show folder `小镇疑云` instead of one first-level folder per episode;
- keep original video filenames unchanged;
- keep uncertain TV/movie items in their original relative path and mark them for manual review;
- create Windows symlinks;
- skip existing targets for incremental sync;
- report broken local symlinks without deleting them.

`scrape_metadata` maps to the confirmed workflow step "刮削媒体元数据":

- first phase uses TMDB as the primary metadata provider, with provider abstraction reserved for future sources;
- default TMDB metadata language is `zh-CN`, with `en-US` fallback for failed searches or missing fields;
- TMDB JSON requests and image downloads retry transient timeout, HTTP 429, and HTTP 5xx failures before marking the affected record failed;
- matching strategy is rules first, then TMDB search, then LLM-assisted title expansion for movie and TV no-candidate cases; LLM-assisted decision between ambiguous TMDB candidates is reserved for a later stage;
- movie TMDB search/details are implemented; movie NFO and image filenames follow each video file stem, not the first-level folder name;
- movie details use `zh-CN` first and fetch `en-US` details to fill missing title/overview fields when needed;
- non-dry-run movie scraping writes Emby-compatible movie NFO with TMDB actors as completely as available, optional rating/certification/MPAA, directors, writers, producers, IMDb/TVDB/Wikidata IDs, movie collection, production companies/countries, spoken languages, original language, release date, genres, plot, and TMDB ID, and downloads poster/fanart when TMDB image paths are available;
- TV TMDB search/details and episode details are implemented; TV output uses `tvshow.nfo`, show poster/fanart, season posters, and per-episode NFO/thumb filenames following each episode video stem;
- TV details and episode details use `zh-CN` first and fetch `en-US` details to fill missing title/overview fields when needed;
- TV `tvshow.nfo` includes TMDB actors as completely as available, including aggregate credits when present, optional rating/certification/MPAA, directors, writers, producers, IMDb/TVDB/Wikidata IDs, production companies/countries, spoken languages, original language, first-air date, genres, plot, and TMDB ID; episode NFO includes optional episode rating and inherits show actors when available;
- when movie or TV TMDB search returns no candidates and LLM config is enabled and complete, the scraper asks the configured OpenAI-compatible LLM for alias/original-title candidates, retries TMDB with those candidates, and records the LLM suggestion and retry queries in the report;
- dry-run scans, parses, calls providers when implemented, and reports the plan without writing NFO or downloading images;
- default `overwrite_existing=false`; existing NFO/images are skipped unless overwrite is enabled;
- default `auto_rename=true`; after successful NFO metadata, movie first-level folders are renamed from the generated/existing `movie` NFO `title` and `year`, while TV first-level folders are renamed from `tvshow.nfo` `title` and `year`;
- auto rename uses `title (year)`; when the target folder already exists, it merges non-conflicting files into that folder, skips conflicting filenames, removes the emptied source folder, and records the result in the report;
- current implementation provides the Context Object contract, WebUI/CLI actions, config testing, config persistence APIs, movie and TV TMDB matching, movie/TV LLM alias retry for no-candidate cases, movie NFO, `tvshow.nfo`, episode NFO, poster/fanart downloading, season poster downloading, and episode thumbnail downloading. LLM arbitration between multiple returned TMDB candidates and richer scoring are next-stage work.

## Current WebUI Status

Implemented:

- FastAPI app factory;
- minimal browser UI at `/`;
- symlink workspace media libraries use a fixed checked list for `movies` / `tvshows`;
- WebUI form parameters are persisted in browser localStorage and restored on page load, excluding access token;
- metadata provider settings are persisted in browser localStorage, including TMDB/LLM API keys by user request;
- metadata media libraries are displayed as a fixed checklist with movies and TV shows rows; checked rows with non-empty paths run sequentially as separate `scrape_metadata` requests and receive separate report links. During this standalone metadata queue, the execution button changes to `取消执行` and can cooperatively cancel the active backend run plus subsequent checked libraries;
- one-click full flow executes `构建本地软链接工作区 -> 刮削媒体元数据` from WebUI. Metadata paths in this mode come from checked symlink target directories, not from the metadata card's manually entered paths. The full-flow button changes to `取消执行` during execution and can cooperatively cancel the active backend run plus subsequent steps;
- WebUI single-step and full-flow execution use background run APIs with SSE logs/status while preserving `/v1/run` as a synchronous compatibility endpoint;
- report link groups in the WebUI execution result panel show a bold colored final result label: green `成功`, orange `部分成功`, or red `失败`;
- metadata scraping emits progress logs for SSE, including current movie file, current TV first-level directory, matched show title/year, episode progress, and per-show summary;
- non-dry-run symlink requests check actual symlink creation capability before running; when unavailable on Windows, WebUI tells the user to enable Developer Mode instead of starting UAC elevation;
- `/health`;
- `/v1/actions`;
- `/v1/symlink/capability`;
- `/v1/config/metadata`;
- `/v1/run`;
- `/v1/runs`;
- `/v1/runs/{run_id}`;
- `/v1/runs/{run_id}/cancel`;
- `/v1/runs/{run_id}/events`;
- `/v1/reports/{run_id}/report.html`;
- `/v1/reports/{run_id}/report.json`;
- access token enforcement for `/v1/*` when configured;
- single-run execution lock;
- non-dry-run symlink creation is blocked unless the current process can create symlinks; on Windows, users should enable Developer Mode when capability is unavailable;
- WebUI metadata section includes TMDB/LLM settings, test buttons, local config load/save buttons, fixed movie/TV metadata library checklist, auto rename, and a `scrape_metadata` dry-run entry;
- `python main.py --serve-web` backend startup path.

Not yet implemented:

- reports center;
- review center.

Real-time run state is currently in memory only. If the WebUI backend restarts, in-flight status and the in-memory report route index are not restored; the report files remain on disk for a later reports-center feature to rediscover.

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
