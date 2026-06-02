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

## Action Names

Primary action:

```bash
python main.py --action build_symlink_workspace
```

Compatibility alias:

```bash
python main.py --action scan_and_link
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

## Current WebUI Status

Implemented:

- FastAPI app factory;
- minimal browser UI at `/`;
- path pair media type uses fixed radio options: `movies` / `tvshows`;
- WebUI form parameters are persisted in browser localStorage and restored on page load, excluding access token;
- `/health`;
- `/v1/actions`;
- `/v1/admin/status`;
- `/v1/admin/restart-elevated`;
- `/v1/run`;
- `/v1/reports/{run_id}/report.html`;
- `/v1/reports/{run_id}/report.json`;
- access token enforcement for `/v1/*` when configured;
- single-run execution lock;
- non-dry-run symlink creation is blocked unless the Windows process is running as Administrator;
- WebUI can request an Administrator restart through Windows UAC after user confirmation;
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
