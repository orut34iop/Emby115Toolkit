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
- Web backend facade skeleton: `emby115_v2/web/api.py`
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
- recreate relative folder structure in the local workspace;
- create Windows symlinks;
- skip existing targets for incremental sync;
- report broken local symlinks without deleting them.

## Current WebUI Status

Implemented:

- FastAPI app factory;
- `/health`;
- `/v1/actions`;
- `/v1/run`;
- `python main.py --serve-web` backend startup path.

Not yet implemented:

- browser UI;
- access token enforcement;
- single-run execution lock;
- real-time logs/status;
- reports center;
- review center.

## Documentation Rule

Every future code change must update the relevant docs in the same change set when it affects:

- CLI commands;
- WebUI/API behavior;
- workflow names;
- configuration schema;
- reports;
- service contracts;
- user-facing behavior.
