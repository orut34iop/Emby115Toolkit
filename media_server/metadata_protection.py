"""Explicit, resumable Jellyfin field protection without restoring old metadata."""

import copy
import hashlib
import json
import os
import tempfile
import time
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

FIELDS = ('Genres', 'ProductionLocations')
ITEM_TYPES = {'Movie', 'Series', 'Season', 'Episode', 'Video'}


def item_id(value):
    return UUID(str(value)).hex


def version_ids(item):
    """Only advertised, persistent video sources are members; never match by title."""
    own_id = item_id(item['Id'])
    result = {own_id}
    sources = item.get('MediaSources') or []
    if not isinstance(sources, list):
        raise ValueError('Invalid media sources')
    for source in sources:
        if not isinstance(source, dict) or not source.get('Id'):
            raise ValueError('Media source has no item identifier')
        result.add(item_id(source['Id']))
    count = item.get('MediaSourceCount', 1)
    if type(count) is not int or count < 0 or count > len(result):
        raise ValueError('Version membership is incomplete')
    return sorted(result)


def expand_versions(client, items, read_all=False, progress_callback=None):
    """Resolve every member before a caller starts writing; unreadable members fail closed."""
    queue = deque()
    discovered = {}
    resolved = {}
    pending = {}
    last_report = 0
    last_count = -1
    percent = 0

    def enqueue(candidate, force_detail=False):
        identifier = candidate['Id']
        sources = candidate.get('MediaSources') or []
        if not isinstance(sources, list) or any(not isinstance(source, dict) or not source.get('Id') for source in sources):
            raise ValueError('Invalid media sources in listing')
        has_alternates = any(str(source['Id']).replace('-', '').lower() != str(identifier).replace('-', '').lower()
                             for source in sources)
        needs_detail = force_detail or read_all or candidate.get('MediaSourceCount', 1) > 1 or has_alternates
        try:
            key = item_id(identifier)
        except ValueError:
            # Legacy single-source fixtures need not carry GUIDs.
            if needs_detail:
                raise
            key = str(identifier)
        if key not in discovered:
            discovered[key] = len(discovered)
            queue.append((key, candidate, needs_detail))

    def accept(key, current, needs_detail):
        if not isinstance(current, dict) or (needs_detail and item_id(current.get('Id')) != key):
            raise ValueError(f'Cannot read version {key}')
        if needs_detail and current.get('Type') not in ITEM_TYPES:
            raise ValueError(f'Unsupported version type: {key}')
        resolved[key] = current
        if needs_detail:
            for member in version_ids(current):
                enqueue({'Id': member}, force_detail=True)

    def report(force=False, complete=False):
        nonlocal last_report, last_count, percent
        now = time.monotonic()
        if not force and now - last_report < 5 and len(resolved) - last_count < 500:
            return
        last_report, last_count = now, len(resolved)
        # More hidden members can be discovered later; never move the bar backwards.
        percent = 100 if complete else max(percent, min(99, 100 * len(resolved) / max(1, len(discovered))))
        message = (
            f"版本检查{'完成' if complete else '进度'}：已检查 {len(resolved)}/{len(discovered)} 个条目，"
            f"正在读取 {len(pending)} 个详情"
        )
        if pending:
            message += f"，等待条目 {next(iter(pending.values()))}"
        if progress_callback is None:
            client.logger.info(message)
        else:
            client._report_progress(progress_callback, len(resolved), len(discovered), message, percent=percent)

    def read(identifier):
        if client.stop_flag.is_set():
            raise InterruptedError('Cancelled during version discovery')
        return client.get_item_info(identifier)

    for candidate in items:
        if client.stop_flag.is_set():
            raise InterruptedError('Cancelled during version discovery')
        enqueue(candidate)
    report(force=True)
    # Bound both concurrency and queued futures, even for very large libraries.
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix='version-discovery') as executor:
        try:
            while queue or pending:
                if client.stop_flag.is_set():
                    raise InterruptedError('Cancelled during version discovery')
                while queue and len(pending) < 4:
                    if client.stop_flag.is_set():
                        raise InterruptedError('Cancelled during version discovery')
                    key, candidate, needs_detail = queue.popleft()
                    if needs_detail:
                        pending[executor.submit(read, candidate['Id'])] = key
                    else:
                        accept(key, candidate, False)
                if pending:
                    done, _ = wait(pending, timeout=1, return_when=FIRST_COMPLETED)
                    for future in sorted(done, key=lambda f: discovered[pending[f]]):
                        key = pending.pop(future)
                        accept(key, future.result(), True)
                report()
            if client.stop_flag.is_set():
                raise InterruptedError('Cancelled during version discovery')
        finally:
            for future in pending:
                future.cancel()
            if pending:
                client.logger.info("版本检查正在结束，等待已发出的详情请求返回")
    report(force=True, complete=True)
    return [resolved[key] for key in discovered]


def _fields(fields):
    result = list(dict.fromkeys(fields))
    if not result or any(field not in FIELDS for field in result):
        raise ValueError('Select Genres and/or ProductionLocations')
    return result


def _snapshot(item, fields):
    locks = item.get('LockedFields')
    locks = [] if locks is None else locks
    if not isinstance(locks, list) or any(not isinstance(lock, str) for lock in locks):
        raise ValueError('Invalid field locks')
    values = {}
    for field in fields:
        value = item.get(field)
        if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
            raise ValueError(f'Missing or invalid field: {field}')
        values[field] = list(value)
    return {'values': values, 'locks': list(locks), 'lock_data': item.get('LockData')}


def _identity(item):
    return {key: item.get(key) for key in ('Name', 'Type', 'Path', 'ProviderIds')}


def _server(client):
    if client.server_type != 'jellyfin':
        raise ValueError('Historical protection requires Jellyfin')
    response = client._request('get', '/System/Info/Public')
    response.raise_for_status()
    info = response.json()
    if not info.get('Id') or 'jellyfin' not in str(info.get('ProductName', '')).lower():
        raise ValueError('Cannot establish Jellyfin server identity')
    client.user_id = client.user_id or client.emby_get_user_id()
    if not client.user_id:
        raise ValueError('Cannot establish user scope')
    return {'url': client.server_url, 'id': info['Id'], 'user_id': client.user_id}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _write_json(path, value, exclusive=False):
    """Flush backups/checkpoints before any HTTP write; private, atomic local files."""
    path = Path(path)
    data = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if exclusive:
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def create_plan(client, path, fields, ids=(), libraries=()):
    fields = _fields(fields)
    if bool(ids) == bool(libraries):
        raise ValueError('Select item IDs or library IDs, but not both')
    scope = {'items': sorted({item_id(i) for i in ids}), 'libraries': sorted({item_id(i) for i in libraries})}
    server = _server(client)
    seeds = [{'Id': identifier} for identifier in scope['items']]
    for library in scope['libraries']:
        found = client._get_jellyfin_items({
            'UserId': client.user_id, 'ParentId': library,
            'IncludeItemTypes': 'Movie,Series,Season,Episode,Video',
            'Fields': 'Genres,ProductionLocations,MediaSources',
        }, '历史字段保护预览')
        if found is None:
            raise ValueError('Incomplete library listing; no plan created')
        seeds.extend(found)
    records = []
    for item in expand_versions(client, seeds, read_all=True):
        records.append({'id': item_id(item['Id']), 'identity': _identity(item),
                        'versions': version_ids(item), 'before': _snapshot(item, fields)})
    plan = {'schema': 1, 'created_at': _now(), 'server': server, 'scope': scope,
            'fields': fields, 'items': sorted(records, key=lambda row: row['id'])}
    if client.stop_flag.is_set():
        raise InterruptedError('Cancelled before writing preview')
    _write_json(path, plan, exclusive=True)
    return plan


@contextmanager
def _plan_lock(path):
    """OS lock releases on crashes; the lock file is intentionally retained."""
    fd = os.open(str(path) + '.apply.lock', os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if os.name == 'nt':
            import msvcrt
            if os.fstat(fd).st_size == 0:
                os.write(fd, b'0')
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def apply_plan(client, path, report_path):
    if Path(report_path).resolve() in {Path(path).resolve(), Path(str(path) + '.apply.lock').resolve()}:
        raise ValueError('Plan and report must be different files')
    with _plan_lock(path):
        return _apply_plan(client, path, report_path)


def _apply_plan(client, path, report_path):
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    plan = json.loads(raw)
    if plan['schema'] != 1 or plan['server'] != _server(client):
        raise ValueError('Plan belongs to a different server/user or schema')
    fields = _fields(plan['fields'])
    records = plan['items']
    if len({item_id(row['id']) for row in records}) != len(records):
        raise ValueError('Duplicate plan items')
    report_path = Path(report_path)
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding='utf-8'))
        if report['plan_sha256'] != digest:
            raise ValueError('Report does not belong to this plan')
    else:
        report = {'plan_sha256': digest, 'created_at': _now(), 'results': {}}
        _write_json(report_path, report, exclusive=True)
    for row in records:
        if client.stop_flag.is_set():
            break
        identifier = row['id']
        history = report['results'].setdefault(identifier, [])
        attempt = {'started_at': _now(), 'status': 'prepared'}
        try:
            current = client.get_item_info(identifier)
            if client.stop_flag.is_set():
                break
            if not isinstance(current, dict) or item_id(current.get('Id')) != item_id(identifier):
                raise ValueError('Item missing or unreadable')
            snapshot = _snapshot(current, fields)
            attempt['before'] = copy.deepcopy(snapshot)
            if (_identity(current) != row['identity'] or version_ids(current) != row['versions']
                    or snapshot['values'] != row['before']['values']):
                attempt.update(status='conflict', reason='Values, identity or version membership changed; create a new preview')
            elif set(fields).issubset(snapshot['locks']):
                attempt['status'] = 'confirmed'
            elif any(prior['status'] == 'confirmed' for prior in history):
                attempt.update(status='conflict', reason='Protection removed after a confirmed run; create a new preview')
            else:
                history.append(attempt)
                # Backup the current values/locks before dispatch, including on a resumed attempt.
                _write_json(report_path, report)
                if client.stop_flag.is_set():
                    break
                response = client._save_curated_fields(identifier, current, fields)
                attempt['status'] = 'confirmed' if response.status_code in (200, 204) else 'failed'
                if attempt['status'] == 'failed':
                    attempt['reason'] = 'Value/lock write not confirmed; inspect item and retry this report'
        except (ValueError, KeyError, TypeError) as exc:
            attempt.update(status='failed', reason=str(exc))
        if not history or history[-1] is not attempt:
            history.append(attempt)
        attempt['finished_at'] = _now()
        _write_json(report_path, report)
    report['cancelled'] = client.stop_flag.is_set()
    report['summary'] = {status: sum(bool(report['results'].get(row['id']))
                                   and report['results'][row['id']][-1]['status'] == status for row in records)
                         for status in ('confirmed', 'failed', 'conflict', 'prepared')}
    report['summary']['unprocessed'] = sum(not report['results'].get(row['id']) for row in records)
    _write_json(report_path, report)
    return report
