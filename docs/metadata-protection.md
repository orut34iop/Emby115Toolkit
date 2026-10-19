# Historical Jellyfin field protection and merged versions

Updated: 2026-10-19. Chinese edition: [历史字段补锁与多版本](metadata-protection.zh-CN.md).

This workflow protects the **current database values**, including Chinese values, unknown values and deliberately empty lists. It does not translate, restore old values, read NFO metadata, refresh a library, or merge/split versions. A preview is read-only. Applying a reviewed preview is an explicit, separate command; installation and tests do not modify a real library.

## Scope and version discovery

Choose item IDs **or** library IDs, and explicitly select `Genres`, `ProductionLocations`, or both. IDs are Jellyfin GUIDs. There is no implicit all-library mode and no inference that Chinese text proves prior curation.

- Item scope includes the selected items and all versions advertised by their `MediaSources`. Selecting a Series ID does not implicitly select its seasons or episodes.
- Library scope recursively selects Movie, Series, Season, Episode and Video items, then expands their versions. It does not protect unrelated audio, photo or person entities.
- Discovery reads full details for every selected item and follows source item IDs transitively, deduplicating cycles. It does not use PlaybackInfo or ffprobe. Each member retains its own values; a primary's metadata is never copied to its alternate versions.
- A merged group may span libraries. Its advertised members are included even if a member is hidden from the selected library's ordinary listing. Review their IDs, types and paths in the preview before applying.
- Missing, unreadable, unsupported or non-GUID sources, or a source count larger than the discovered membership, abort preview creation. An incomplete discovery never becomes a partial executable plan. Provider-specific sources without persistent item IDs need separate support.

The existing desktop **Update genres** and **Update countries** operations also request `MediaSources` and expand merged versions before choosing translation candidates. A failure to discover a member prevents that Movie/Series pass from writing. These operations still translate only changed values and retain their existing Movie/Series scope. The independent historical workflow is what also covers unchanged values, existing empty lists, seasons and episodes.

## Preview, review, apply

Run from the toolkit repository using its Python environment. On macOS the executable is normally `.venv/bin/python`; on Windows use the configured environment's `python`. No GUI changes or new frontend are required.

Provide the API key through `JELLYFIN_API_KEY` in the process environment. Never place it in command arguments, the preview or the report. Use an account/key allowed to read and edit the chosen items. Preserve a reverse proxy base path in `--server-url`.

Create a private output directory named `metadata-protection` (gitignored), then create a preview. The examples below use a fictitious server and placeholder IDs; replace them deliberately.

```sh
python -m media_server.metadata_protection_cli --server-url https://media.example/jellyfin --username Admin plan --library-id LIBRARY_GUID --fields Genres ProductionLocations --output metadata-protection/library-plan.json
```

For an explicit item selection, replace `--library-id LIBRARY_GUID` with `--item-id ITEM_GUID`. Repeat either option to include several selected IDs. Both fields above are intentional; specify just `--fields Genres` to protect only genres.

The preview contains the server URL/ID, user scope, selected roots, expanded item IDs and relationships, identity evidence, current selected values, existing field locks and whole-item lock state. Review all entries, especially hidden or cross-library versions, before proceeding. Existing preview files are never overwritten. The file is a backup of the relevant values and locks, **not** a full Jellyfin database backup or an automatic rollback script. Back up the database separately when needed.

Only after review, explicitly run:

```sh
python -m media_server.metadata_protection_cli --server-url https://media.example/jellyfin --username Admin apply --plan metadata-protection/library-plan.json --report metadata-protection/library-report.json
```

Apply refuses a different server ID, server URL or user scope. For each item it rereads full current details, checks identity, version membership and selected values against the preview, records the current pre-write values/locks in the report, then saves **only an addition to `LockedFields`** using the current full DTO. It preserves current nonselected fields, existing locks and `LockData`. It never replaces current values with the preview's old values.

The existing full DTO endpoint does not support conditional revisions. Another writer can still race between the fresh read and POST; avoid simultaneous management of the same items. The backup and reread checks reduce risk but do not create a cross-client transaction. NFO saving remains governed by the server's existing library settings.

## Verification, failure and retry

| Latest report status | Meaning and next action |
| --- | --- |
| `confirmed` | The current values and all submitted locks were read back successfully, or all selected locks were already present on a verified current item. |
| `failed` | Read/write/verification failed. Inspect the item, then rerun with the **same plan and same report**. |
| `conflict` | Selected values, identity, version membership changed, or protection was removed after a prior confirmed run. Review the new state and create a new preview; do not restore old values automatically. |
| `prepared` | A pre-write backup exists but completion was interrupted. Resume with the same files; reread determines whether a write is needed. |
| `unprocessed` count | Cancellation left items unvisited. Resume the same files to continue. |

An ordinary timeout never triggers a blind replay of an old full DTO. A retry reads current values and locks again, preserves new unrelated metadata and locks, and verifies the result. Previously confirmed items are rechecked without redundant POSTs; an explicit later unlock is treated as a conflict instead of silently undone. The report retains attempt history and is bound to the exact preview bytes by SHA-256. Do not edit a preview while resuming, or switch to a fresh report to bypass its history.

Backups and report checkpoints are flushed before HTTP writes; a checkpoint failure stops execution. Local files are atomically replaced and created with private permissions where supported; protect the output directory with appropriate Windows ACLs. They contain private metadata and paths, so do not publish them. An OS lock prevents simultaneous application of the same preview file and is released on process exit/crash. This does not serialize different previews or other clients.

Exit code 0 means all selected items were confirmed. Nonzero means a failure, conflict, cancellation or incomplete operation; inspect the report. Ctrl+C stops execution; an in-flight request may have committed, so resume by rereading instead of assuming rollback. Batch execution is not a library-wide transaction. Power-loss atomicity across server repositories and restoration of already overwritten values are outside this workflow.

## Verification record

Automated tests cover hidden members, cycles, independent values, existing empty values, selected scope, retained locks and current unrelated metadata, changed-value/source conflicts, partial failures, interrupted checkpoints, cancellation/resume and failed local backup writes. HTTP contract tests cover both supported schema fixtures. No real user library is used.

Validated on 2026-10-19: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest` passed **384 tests**, with one Windows-only frontend test skipped on macOS. Scoped `ruff check` passed. The environment still emits its pre-existing urllib3/LibreSSL warning.

An isolated Jellyfin `12.0.0-20261019183458` instance passed five grouped checks: (1) CLI preview performs no server writes and finds the member hidden from the ordinary item list; (2) independent historical/empty values, an untouched out-of-scope item, injected partial failure, resume and repeat apply; (3) completed replace-all refresh and PlaybackInfo preserve both members' protected values; (4) normal genre/country workflows translate hidden members independently; (5) a stale preview reports conflict without restoring old values. Only generated test movies were used. Series/season/episode scope and whole-item-lock preservation have automated coverage, not live-server coverage. Native Windows CLI/file-lock execution and official unmodified server releases were not run here.
