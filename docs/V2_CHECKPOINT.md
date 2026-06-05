# Emby115Toolkit V2 Checkpoint

This document records the current V2 development baseline. Keep it updated whenever code changes affect architecture, commands, workflows, or user-visible behavior.

## Latest Checkpoint

- 2026-06-04: `v2.0-checkpoint-20260604-reviewed-movie-metadata` records the current baseline after the full workflow/cloud-import milestone and the latest manual-review movie metadata corrections. This checkpoint includes mixed-folder per-video scraping, CJK/bracket search cleanup, rule-based aliases, known TMDB-ID direct matches, the local title override for `96超级床上接班人`, and the WebUI full-flow/cloud-import behavior already documented below. Full test suite status at checkpoint creation: `python -m pytest -q` -> 182 passed.

## Confirmed Product Direction

- First phase targets Windows only.
- WebUI is the only main graphical interface for V2.
- CLI is an official automation entry point.
- Qt/tkinter are legacy references and are not V2 feature targets.
- WebUI and CLI are facade entrances. They must call the same core service layer through Context Objects.
- Every run must produce auditable artifacts: HTML report, JSON report, and log file.
- HTML reports include local operation-record filtering controls for status, action, media type, keyword search, and quick filters for `manual_review` and `failed`, so audit work can focus on rows that need review.

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
python main.py --action build_cloud_scraped_library --config emby115_v2.config.json --dry-run
```

CLI `scrape_metadata` still consumes one `metadata_output.media_type/library_path` at a time. WebUI may submit the fixed movie/TV checklist sequentially as separate `scrape_metadata` runs. While this standalone metadata queue is active, the metadata button displays `取消执行`; cancellation is cooperative, requests cancellation for the current backend run, and stops launching later checked libraries.

WebUI also provides a one-click full flow. This is front-end orchestration only, not a new backend workflow action: it runs one `build_symlink_workspace` request first, then derives metadata libraries from the checked symlink target directories and submits one `scrape_metadata` request per media type, then submits `build_cloud_scraped_library` with the symlink target directories as cloud-import sources. Full flow uses upstream outputs as downstream inputs: metadata card library paths and cloud card source paths are only used for standalone card execution and are overridden by the symlink target paths during full-flow execution. While the full flow is active, the overridden downstream path inputs are visually locked/disabled and display the effective symlink target path, and the downstream metadata/cloud enable checkboxes are also locked to the effective full-flow participation state; after the flow ends, their original standalone values are restored. While the full flow is active, the same button displays `取消执行`; cancellation is cooperative, requests cancellation for the current backend run, and stops launching later steps. Full flow automatically enters the cloud-import stage without an extra confirmation prompt. CLI does not yet expose a one-click full-flow action.

`build_symlink_workspace` maps to the confirmed workflow step "软链接导出":

- scan mounted CloudDrive2 source folders;
- WebUI presents a fixed checked list for movies and TV shows; checked rows with non-empty source/target paths are submitted together as one `build_symlink_workspace` request. The WebUI also exposes an `自动清空工作区` checkbox in the symlink execution action area, enabled by default;
- CLI and the core Context Object continue to accept a `path_pairs` array, including multiple pairs when supplied outside the WebUI. CLI defaults to automatic target cleanup and can disable it with `--no-auto-clear-workspace`;
- each local symlink workspace target defaults to automatic cleanup through `symlink.auto_clear_workspace=true`. If the target already contains files or folders, the action clears that target workspace first and reports `clear_target_workspace`; if automatic cleanup is disabled, a non-empty target fails and reports `validate_target_workspace`. Automatic cleanup refuses unsafe paths such as disk roots, the source path itself, or source/target paths that contain one another;
- filter video files;
- build standardized local library paths instead of blindly mirroring the source tree;
- for movies, place symlinks under a movie title folder with explicit year when the year is present;
- movie title parsing prefers a parent folder that contains both a usable title and a year over short release filenames, avoiding folders such as `eb (2013)` when the source folder has `东方男孩Eastern.Boys.2013...`;
- when a movie parent folder has a Chinese title/year and the video filename has a same-year English title, the standardized first-level folder preserves both as `Chinese.English (year)`, for example `惊蛰无声.Scare Out (2026)`; if the parent folder already contains the English title, the parent title is kept intact, for example `莎拉·丝沃曼：生离笑别.Sarah.Silverman.PostMortem (2025)`;
- for TV shows, place symlinks under a show title folder and a season/version second-level folder;
- TV second-level folder priority is: existing source folder that contains a season marker, then release folder derived from episode filename, then `Season NN`;
- pure TV season folders such as `S01`, `Season 1`, or `第一季` are normalized to `Season 01` for Emby/Kodi compatibility; release/version folders that include season plus quality/version text may keep their original names;
- TV show title parsing treats `SxxEyy` and season markers as structural metadata rather than title text, so files such as `小镇疑云.S02E01...` are grouped under the show folder `小镇疑云` instead of one first-level folder per episode;
- keep original video filenames unchanged;
- keep uncertain TV/movie items in their original relative path and mark them for manual review;
- create Windows symlinks;
- report broken local symlinks without deleting them.

`scrape_metadata` maps to the confirmed workflow step "元数据刮削":

- first phase uses TMDB as the primary metadata provider, with provider abstraction reserved for future sources;
- default TMDB metadata language is `zh-CN`, with `en-US` fallback for failed searches or missing fields;
- TMDB JSON requests and image downloads retry transient timeout, HTTP 429, and HTTP 5xx failures before marking the affected record failed;
- matching strategy is rules first, then TMDB search, then LLM-assisted title expansion for movie and TV no-candidate cases; LLM-assisted decision between ambiguous TMDB candidates is reserved for a later stage;
- movie TMDB search/details are implemented; movie NFO and image filenames follow each video file stem, not the first-level folder name;
- movie search source keeps the normal standardized-library behavior of using the single-movie parent folder, but a first-level folder without a year that contains multiple videos is treated as a mixed/category folder and each video is searched from its own filename;
- movie TMDB search text strips non-year bracket notes such as actor names or subtitle tags before provider lookup, while preserving year markers, so files like `聊斋艳谭之艳魔大战（叶子楣）.mkv` search as `聊斋艳谭之艳魔大战`;
- movie search performs rule-based query expansion before raw-title and LLM fallback: known stylized aliases such as `GirlS/Girls (2010)` -> `囡囡`, romanization aliases such as `JinChun (1993)` -> `禁春`, and Chinese title fragments extracted from mixed Chinese/English release names are tried before generic English titles that can return broad TMDB candidates. Current fragment examples include `18P2P色模SuperModels[...]` -> `色模`, `1983欲望之翼BD720P...` -> `欲望之翼`, `93女爱男欢（...）-93女爱男欢` -> `93女爱男欢`, `97风流梦（...）-97风流梦` -> `97风流梦`, and `三分之一情人（...）-三分之一情人` -> `三分之一情人`;
- movie matching can use known TMDB-ID direct rules when TMDB search cannot find a known title, for example `janinhan.miyongsaui (2014/2015)` -> TMDB `322587` (`热点服务：一个残忍的理发师`) and `96超级床上接班人` -> TMDB `926910`. Direct rules may also apply local title overrides when TMDB's localized title omits a user-verified distinguishing prefix;
- movie details use `zh-CN` first and fetch `en-US` details to fill missing title/overview fields when needed;
- non-dry-run movie scraping writes Emby-compatible movie NFO with TMDB actors as completely as available, optional rating/certification/MPAA, directors, writers, producers, IMDb/TVDB/Wikidata IDs, movie collection, production companies/countries, spoken languages, original language, release date, genres, plot, and TMDB ID, and downloads poster/fanart/clearlogo when TMDB image paths are available;
- TV TMDB search/details and episode details are implemented; TV output uses `tvshow.nfo`, show poster/fanart/clearlogo, season posters, and per-episode NFO/thumb filenames following each episode video stem;
- TV details and episode details use `zh-CN` first and fetch `en-US` details to fill missing title/overview fields when needed;
- TV `tvshow.nfo` includes TMDB actors as completely as available, including aggregate credits when present, optional rating/certification/MPAA, directors, writers, producers, IMDb/TVDB/Wikidata IDs, production companies/countries, spoken languages, original language, first-air date, genres, plot, and TMDB ID; episode NFO includes optional episode rating and inherits show actors when available;
- when movie or TV TMDB search returns no candidates and LLM config is enabled and complete, the scraper asks the configured OpenAI-compatible LLM for alias/original-title candidates, retries TMDB with those candidates, and records the LLM suggestion and retry queries in the report;
- dry-run scans, parses, calls providers when implemented, and reports the plan without writing NFO or downloading images;
- default `overwrite_existing=false`; existing NFO/images are skipped unless overwrite is enabled;
- default `auto_rename=true`; after successful movie metadata, each movie video symlink and same-stem NFO/images/sidecars are moved under the library root into a `title (year)` first-level folder derived from the generated/existing `movie` NFO, while TV first-level folders are renamed from `tvshow.nfo` `title` and `year`;
- auto rename uses `title (year)`; when the target folder already exists, it merges non-conflicting files into that folder, skips conflicting filenames, removes emptied source folders, and records each movie/TV rename or move result in the report;
- current implementation provides the Context Object contract, WebUI/CLI actions, config testing, config persistence APIs, movie and TV TMDB matching, movie/TV LLM alias retry for no-candidate cases, movie NFO, `tvshow.nfo`, episode NFO, poster/fanart/clearlogo downloading, season poster downloading, and episode thumbnail downloading. LLM arbitration between multiple returned TMDB candidates and richer scoring are next-stage work.

`build_cloud_scraped_library` maps to the confirmed workflow step "网盘同步":

- input `path_pairs` map local symlink workspaces to new cloud-side organized library roots. `source` is the C-drive symlink workspace and `target` is the new D-drive CloudDrive2/115 library directory;
- Stage A mirrors the whole local workspace directory tree and copies every non-symlink file to the target while excluding symlink files and symlink directories. This preserves the already-scraped folder structure exactly and carries future metadata file types without special-case extension lists;
- Stage A does not move real videos;
- symlink videos only enter the Stage B real-video move plan when the same directory contains a same-stem NFO file, for example `movie.mkv` requires `movie.nfo`. If that NFO is missing, the symlink is reported as skipped, no real-video move plan is created in real runs, and the run is marked `partial`;
- after Stage A, non-dry-run execution defaults to `cloud_library_output.upload_wait_strategy=fixed`, which waits `cloud_library_output.wait_minutes` minutes, default `60`, so CloudDrive2/115 has time to upload copied metadata from its local cache before videos are moved;
- CloudDrive2 task-based waiting is available through `upload_wait_strategy=clouddrive2` or `clouddrive2_or_fixed`. It polls CloudDrive2 gRPC `GetUploadFileList` for mounted-filesystem uploads (`operatorType=Mount`) matching the target path. Defaults are `clouddrive2.poll_interval_seconds=0.5` and `clouddrive2.settle_seconds=30` because CloudDrive2's upload list behaves like a short-lived active-task snapshot. Strict `clouddrive2` does not fall back; if no matching tasks are observed through the first quiet window, Stage B continues because small metadata files may finish before polling can see them, and cloud-library reports record the wait as `success` while preserving `raw_status=not_observed`. Once any matching task is observed, upload start is confirmed; completion is confirmed only when the task reaches a terminal success state or after a later continuous quiet window with no active matching tasks. CloudDrive2 task `Error` / `FatalError` states are recorded in the wait reason and `error_count`, but they are not treated as final failure by themselves because CloudDrive2 can later upload files successfully despite transient task errors. If confirmation times out, Stage B is skipped and the run reports `partial`. `clouddrive2_or_fixed` falls back to the fixed minute wait when confirmation times out or the API is unavailable;
- Stage B resolves each video symlink in the local workspace and moves the real video file into the same relative path under the new cloud target directory. Resolution prefers `os.readlink()` and normalizes Windows extended-length targets such as `\\?\D:\...`, because CloudDrive2/WinFSP paths can be accessible through the raw symlink target while `Path.resolve(strict=True)` reports WinError 1005;
- target directory creation is CloudDrive2/WinFSP tolerant: transient unsupported-operation errors are retried, and unrecoverable directory creation failures are recorded as `create_directory` report rows instead of crashing the background run without a report;
- dry-run only generates the copy/move plan and report. It does not create target folders, copy metadata, wait, or move videos;
- existing metadata targets and video targets are skipped by default. `cloud_library_output.overwrite_metadata` and `cloud_library_output.overwrite_videos` are explicit separate options;
- the CLI supports `--cloud-wait-minutes`, `--cloud-upload-wait-strategy`, `--overwrite-metadata`, `--overwrite-videos`, and CloudDrive2 connection options such as `--cd2-endpoint` / `--cd2-api-token`. The old metadata-copy-only behavior is removed; non-dry-run cloud sync always moves eligible real videos after the configured wait;
- this step is a final migration/archive operation: moving real videos makes the original C-drive symlink workspace stale and requires rebuilding symlinks if the workflow needs to run again against the moved library.

`test_clouddrive2_upload_wait` is the validation action for replacing fixed waiting:

- it writes a small probe file to `path_pairs[0].target/.emby115_cd2_probe/` in non-dry-run mode;
- it maps the mounted Windows path to CloudDrive2's cloud path using `GetMountPoints`, then observes `GetUploadFileList` every 0.5 seconds by default. If a matching `Mount` upload task is observed once, upload start is confirmed; upload completion is confirmed by a terminal success state or by a later continuous 30-second quiet window without matching tasks;
- successful probe runs delete the local probe file after the upload task has been observed complete;
- dry-run reports the probe plan only and does not write to the virtual disk;
- the recommended first real test is:

```bash
python main.py --action test_clouddrive2_upload_wait --target D:\115open\tmp\organized-probe --source C:\working-emby\movies --cd2-api-token YOUR_CD2_TOKEN
```

## Current WebUI Status

Implemented:

- FastAPI app factory;
- minimal browser UI at `/`;
- symlink workspace media libraries use a fixed checked list for `movies` / `tvshows`;
- WebUI form parameters are persisted in browser localStorage and restored on page load, excluding access token;
- metadata provider settings are persisted in browser localStorage, including TMDB/LLM API keys by user request;
- metadata media libraries are displayed as a fixed checklist with movies and TV shows rows; checked rows with non-empty paths run sequentially as separate `scrape_metadata` requests and receive separate report links. During this standalone metadata queue, the execution button changes to `取消执行` and can cooperatively cancel the active backend run plus subsequent checked libraries;
- one-click full flow executes `软链接导出 -> 元数据刮削 -> 网盘同步` from WebUI. Metadata paths in this mode come from checked symlink target directories, not from the metadata card's manually entered paths. The cloud-import stage also uses those symlink target directories as sources and uses the cloud card's checked target directories as final D-drive destinations. When downstream card input paths differ from the symlink targets, the full flow keeps the upstream symlink targets and logs the override; standalone card execution still uses each card's own inputs. During full-flow execution, overridden metadata library path inputs and cloud source inputs are greyed/disabled, show a lock badge, and temporarily display the effective symlink target path; downstream metadata/cloud enable checkboxes are also disabled with a compact lock badge so users cannot change participation mid-run, and the fixed table columns reserve enough space to avoid overlapping media labels. All locked controls restore their previous standalone values at the end. Full flow automatically enters the cloud-import stage without an extra confirmation prompt; standalone non-dry-run cloud import that moves real videos still asks for explicit confirmation because the C-drive symlink workspace will become stale. The full-flow button changes to `取消执行` during execution and can cooperatively cancel the active backend run plus subsequent steps;
- cloud scraped library import is available as a WebUI card with fixed `movies` / `tvshows` rows. Each checked row maps a local symlink workspace to a new cloud-side target directory and submits one `build_cloud_scraped_library` request. The card defaults to dry-run to avoid accidental writes; non-dry-run execution always moves eligible real videos after the configured wait and still asks for explicit confirmation in standalone mode;
- the cloud card exposes CloudDrive2 gRPC endpoint/token and upload wait strategy settings, plus a `测试 CloudDrive2 上传探测` button that submits `test_clouddrive2_upload_wait` for the first checked row;
- cloud card execution and CloudDrive2 probe execution use the same background run and SSE stack. During execution the cloud button changes to `取消执行` and can request cancellation for the active backend run. Standalone cloud import also asks for explicit confirmation before a non-dry-run run that moves real videos;
- WebUI layout is optimized for 100% browser zoom on common desktop widths: the workflow area and execution result panel use a responsive two-column layout, collapse to one column below medium widths, and long report paths wrap inside the result panel instead of creating whole-page horizontal scrolling;
- WebUI single-step and full-flow execution use background run APIs with SSE logs/status while preserving `/v1/run` as a synchronous compatibility endpoint;
- report link groups in the WebUI execution result panel show a bold colored final result label: green `成功`, orange `部分成功`, or red `失败`;
- generated HTML reports include a local filtering toolbar for operation records: status/action/media type selects, keyword search, and quick buttons for `待人工 review` and `失败`;
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

Windows one-click startup:

```bat
start_webui.bat
```

`start_webui.bat` starts the local WebUI backend, waits for `/health`, then opens `http://127.0.0.1:8765/`. The underlying `scripts/start_webui.ps1` supports `-Port`, `-BindAddress`, `-NoOpen`, and `-Restart` for local troubleshooting.

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
