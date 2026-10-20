"""Scope, backup, conflict and resume guarantees for historical field protection."""

import copy
import json
import threading
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from media_server.client import MediaServerClient
from media_server.metadata_protection import apply_plan, create_plan, expand_versions

pytestmark = pytest.mark.unit
A, B, C = [UUID(int=i).hex for i in (1, 2, 3)]


class Client(MediaServerClient):
    def __init__(self):
        super().__init__(server_url='http://test.invalid', server_type='jellyfin')
        self.user_id = 'user'
        self.server_id = 'server'
        self.items = {
            identifier: {'Id': identifier, 'Type': 'Movie', 'Name': identifier, 'Path': '/media/' + identifier,
                         'Genres': ['中文'] if identifier == A else ['Independent'], 'ProductionLocations': [],
                         'LockedFields': ['Name'], 'LockData': False, 'Overview': 'Keep',
                         'MediaSourceCount': 2, 'MediaSources': [{'Id': A}, {'Id': B}]}
            for identifier in (A, B)
        }
        self.posts = []
        self.fail_ids = set()
        self.after_post = lambda: None

    def get_item_info(self, identifier):
        return copy.deepcopy(self.items.get(identifier))

    def _get_jellyfin_items(self, params, label):
        return [copy.deepcopy(self.items[A])]

    def _request(self, method, path, **kwargs):
        if method == 'get' and path == '/System/Info/Public':
            return SimpleNamespace(raise_for_status=lambda: None,
                                   json=lambda: {'Id': self.server_id, 'ProductName': 'Jellyfin Server'})
        assert method == 'post' and path.startswith('/Items/')
        identifier = path.split('/')[-1]
        self.posts.append(copy.deepcopy(kwargs['json_body']))
        if identifier in self.fail_ids:
            return SimpleNamespace(status_code=503, text='failed')
        self.items[identifier].update(copy.deepcopy(kwargs['json_body']))
        self.after_post()
        return SimpleNamespace(status_code=204)


@pytest.fixture
def state(tmp_path):
    return Client(), tmp_path / 'plan.json', tmp_path / 'report.json'


def test_preview_includes_hidden_versions_and_backs_up_current_empty_and_nonempty_values(state):
    client, plan, _ = state
    result = create_plan(client, plan, ['Genres', 'ProductionLocations'], ids=[A])
    assert [row['id'] for row in result['items']] == [A, B]
    assert result['items'][0]['before']['values'] == {'Genres': ['中文'], 'ProductionLocations': []}
    assert result['items'][1]['before']['values']['Genres'] == ['Independent']
    assert json.loads(plan.read_text(encoding='utf-8')) == result
    assert not client.posts
    with pytest.raises(FileExistsError):
        create_plan(client, plan, ['Genres'], ids=[A])


def test_apply_only_adds_selected_locks_and_keeps_latest_unselected_data(state):
    client, plan, report = state
    create_plan(client, plan, ['Genres', 'ProductionLocations'], libraries=[C])
    client.items[B]['Overview'] = 'New concurrent overview'
    client.items[B]['LockedFields'].append('Tags')
    result = apply_plan(client, plan, report)
    assert result['summary']['confirmed'] == 2
    assert client.items[A]['Genres'] == ['中文']
    assert client.items[B]['Genres'] == ['Independent']
    assert client.items[B]['Overview'] == 'New concurrent overview'
    assert set(client.items[B]['LockedFields']) == {'Name', 'Tags', 'Genres', 'ProductionLocations'}
    assert all(not value['LockData'] for value in client.items.values())
    assert result['results'][B][0]['before']['locks'] == ['Name', 'Tags']
    apply_plan(client, plan, report)
    assert len(client.posts) == 2


@pytest.mark.parametrize('change', ['values', 'identity', 'versions'])
def test_changed_scope_conflicts_without_writing_old_values(state, change):
    client, plan, report = state
    create_plan(client, plan, ['Genres'], ids=[A])
    for item in client.items.values():
        if change == 'values':
            item['Genres'] = ['New value']
        elif change == 'identity':
            item['Path'] = '/other'
        else:
            item['MediaSourceCount'] = 1
            item['MediaSources'] = [{'Id': item['Id']}]
    result = apply_plan(client, plan, report)
    assert result['summary']['conflict'] == 2
    assert not client.posts


def test_resume_retries_failed_member_without_reposting_confirmed_member(state):
    client, plan, report = state
    create_plan(client, plan, ['Genres'], ids=[A])
    client.fail_ids.add(B)
    result = apply_plan(client, plan, report)
    assert result['summary']['confirmed'] == result['summary']['failed'] == 1
    client.fail_ids.clear()
    result = apply_plan(client, plan, report)
    assert result['summary']['confirmed'] == 2
    assert [body['Id'] for body in client.posts] == [A, B, B]
    assert result['results'][B][0]['status'] == 'failed'
    assert result['results'][B][1]['status'] == 'confirmed'


@pytest.mark.parametrize('default_encoding', ['gbk', 'cp1252'])
def test_utf8_report_preserves_chinese_history_across_resume_and_reload(state, monkeypatch, default_encoding):
    client, plan, report = state
    for identifier in (A, B):
        client.items[identifier]['Name'] = '侠女内莉'
        client.items[identifier]['Genres'] = ['剧情', '冒险']
        client.items[identifier]['ProductionLocations'] = ['美国', '英国']

    read_text = Path.read_text

    def read_with_platform_default(path, encoding=None, errors=None, **kwargs):
        if path in (plan, report) and encoding is None:
            encoding = default_encoding
        return read_text(path, encoding=encoding, errors=errors, **kwargs)

    monkeypatch.setattr(Path, 'read_text', read_with_platform_default)
    preview = create_plan(client, plan, ['Genres', 'ProductionLocations'], ids=[A])
    assert json.loads(plan.read_text(encoding='utf-8')) == preview

    client.fail_ids.add(B)
    first = apply_plan(client, plan, report)
    assert first['summary']['confirmed'] == first['summary']['failed'] == 1
    assert '剧情'.encode('utf-8') in report.read_bytes()
    assert json.loads(report.read_text(encoding='utf-8')) == first
    first_history = copy.deepcopy(first['results'])

    client.fail_ids.clear()
    resumed = apply_plan(client, plan, report)
    assert resumed['summary']['confirmed'] == 2
    assert [body['Id'] for body in client.posts] == [A, B, B]
    for identifier in (A, B):
        assert resumed['results'][identifier][:-1] == first_history[identifier]
        assert resumed['results'][identifier][-1]['before']['values'] == {
            'Genres': ['剧情', '冒险'], 'ProductionLocations': ['美国', '英国'],
        }
    assert json.loads(report.read_text(encoding='utf-8')) == resumed
    resumed_history = copy.deepcopy(resumed['results'])

    reloaded = apply_plan(client, plan, report)
    assert reloaded['summary']['confirmed'] == 2
    assert [body['Id'] for body in client.posts] == [A, B, B]
    for identifier in (A, B):
        assert reloaded['results'][identifier][:-1] == resumed_history[identifier]
    assert json.loads(report.read_text(encoding='utf-8')) == reloaded


def test_resume_does_not_undo_explicit_unlock_after_success(state):
    client, plan, report = state
    create_plan(client, plan, ['Genres'], ids=[A])
    apply_plan(client, plan, report)
    client.items[A]['LockedFields'].remove('Genres')
    result = apply_plan(client, plan, report)
    assert result['results'][A][-1]['status'] == 'conflict'
    assert len(client.posts) == 2


def test_interrupted_checkpoint_reconciles_committed_values_without_post(state):
    client, plan, report = state
    create_plan(client, plan, ['Genres'], ids=[A])
    apply_plan(client, plan, report)
    saved = json.loads(report.read_text(encoding='utf-8'))
    saved['results'][A][-1]['status'] = 'prepared'
    report.write_text(json.dumps(saved, ensure_ascii=False), encoding='utf-8')
    assert apply_plan(client, plan, report)['summary']['confirmed'] == 2
    assert len(client.posts) == 2


def test_backup_failure_prevents_http_write(state, monkeypatch):
    from media_server import metadata_protection
    client, plan, report = state
    create_plan(client, plan, ['Genres'], ids=[A])
    write = metadata_protection._write_json

    def fail_checkpoint(path, value, exclusive=False):
        if value.get('results'):
            raise OSError('disk full')
        write(path, value, exclusive)

    monkeypatch.setattr(metadata_protection, '_write_json', fail_checkpoint)
    with pytest.raises(OSError):
        apply_plan(client, plan, report)
    assert not client.posts


def test_cancel_leaves_resumable_unprocessed_members(state):
    client, plan, report = state
    create_plan(client, plan, ['Genres'], ids=[A])
    client.after_post = client.stop_flag.set
    result = apply_plan(client, plan, report)
    assert result['cancelled']
    assert result['summary']['unprocessed'] == 1
    client.stop_flag.clear()
    client.after_post = lambda: None
    assert apply_plan(client, plan, report)['summary']['confirmed'] == 2


def test_other_server_and_other_plan_report_are_rejected(state):
    client, plan, report = state
    create_plan(client, plan, ['Genres'], ids=[A])
    client.server_id = 'other'
    with pytest.raises(ValueError):
        apply_plan(client, plan, report)
    assert not client.posts
    client.server_id = 'server'
    report.write_text(json.dumps({'plan_sha256': 'wrong'}), encoding='utf-8')
    with pytest.raises(ValueError):
        apply_plan(client, plan, report)
    assert not client.posts


def test_unreadable_hidden_member_aborts_preview(state):
    client, plan, _ = state
    del client.items[B]
    with pytest.raises(ValueError):
        create_plan(client, plan, ['Genres'], ids=[A])
    assert not plan.exists()
    assert not client.posts


def test_normal_expansion_keeps_independent_hidden_member_values():
    client = Client()
    result = expand_versions(client, [client.items[A]])
    assert [row['Id'] for row in result] == [A, B]
    assert result[0]['Genres'] != result[1]['Genres']


def test_version_discovery_reads_in_parallel_with_bounded_concurrency(monkeypatch):
    client = Client()
    identifiers = [UUID(int=i).hex for i in range(10, 18)]
    barrier = threading.Barrier(4, timeout=3)
    lock = threading.Lock()
    calls = []
    active = peak = 0

    def read(identifier):
        nonlocal active, peak
        with lock:
            calls.append(identifier)
            active += 1
            peak = max(peak, active)
        try:
            barrier.wait()
            return {'Id': identifier, 'Type': 'Movie', 'MediaSources': [{'Id': identifier}]}
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(client, 'get_item_info', read)
    result = expand_versions(client, [{'Id': identifier} for identifier in identifiers] * 2, read_all=True)
    assert [item['Id'] for item in result] == identifiers
    assert sorted(calls) == identifiers
    assert peak == 4


def test_version_discovery_reports_waits_and_new_hidden_members(monkeypatch):
    from media_server import metadata_protection

    client = Client()
    client.items[C] = {'Id': C, 'Type': 'Movie', 'MediaSourceCount': 1}
    client.items[B]['MediaSources'].append({'Id': C})
    client.items[B]['MediaSourceCount'] = 3
    updates = []
    ticks = iter(range(0, 1000, 6))
    monkeypatch.setattr(metadata_protection, 'time', SimpleNamespace(monotonic=lambda: next(ticks)))
    actual_wait = metadata_protection.wait
    waits = []

    def wait_with_delay(pending, **kwargs):
        waits.append(True)
        if len(waits) == 1:
            return set(), set(pending)
        return actual_wait(pending, **kwargs)

    monkeypatch.setattr(metadata_protection, 'wait', wait_with_delay)
    result = expand_versions(client, [client.items[A]], progress_callback=updates.append)
    assert [item['Id'] for item in result] == [A, B, C]
    assert any('等待条目' in update['message'] for update in updates)
    assert [update['percent'] for update in updates] == sorted(update['percent'] for update in updates)
    assert updates[-1]['percent'] == 100
    assert updates[-1]['current'] == updates[-1]['total'] == 3


def test_cancelled_discovery_does_not_schedule_hidden_members_or_report_completion(monkeypatch):
    client = Client()
    reads, updates = [], []
    original = client.get_item_info

    def read(identifier):
        reads.append(identifier)
        client.stop_flag.set()
        return original(identifier)

    monkeypatch.setattr(client, 'get_item_info', read)
    with pytest.raises(InterruptedError):
        expand_versions(client, [client.items[A]], progress_callback=updates.append)
    assert reads == [A]
    assert not any(update['percent'] == 100 for update in updates)


@pytest.mark.parametrize('kwargs', [{}, {'ids': [A], 'libraries': [B]}])
def test_explicit_unambiguous_scope_is_required(state, kwargs):
    client, plan, _ = state
    with pytest.raises(ValueError):
        create_plan(client, plan, ['Genres'], **kwargs)
    assert not plan.exists()


def test_cli_preview_never_calls_apply(state, monkeypatch):
    from media_server import metadata_protection_cli as cli
    client, path, _ = state
    monkeypatch.setenv('JELLYFIN_API_KEY', 'test')
    monkeypatch.setattr(cli, 'MediaServerClient', lambda **kwargs: client)
    assert cli.main(['--server-url', client.server_url, '--username', 'test', 'plan',
                     '--item-id', A, '--fields', 'Genres', '--output', str(path)]) == 0
    assert not client.posts


def test_cancel_during_read_does_not_start_write(state, monkeypatch):
    client, plan, report = state
    create_plan(client, plan, ['Genres'], ids=[A])
    read = client.get_item_info

    def cancel_read(identifier):
        result = read(identifier)
        client.stop_flag.set()
        return result

    monkeypatch.setattr(client, 'get_item_info', cancel_read)
    result = apply_plan(client, plan, report)
    assert result['cancelled']
    assert result['summary']['unprocessed'] == 2
    assert not client.posts


def test_same_plan_cannot_be_applied_concurrently(state):
    from media_server.metadata_protection import _plan_lock
    client, plan, report = state
    create_plan(client, plan, ['Genres'], ids=[A])
    with _plan_lock(plan), pytest.raises(OSError):
        apply_plan(client, plan, report)
    assert not client.posts


def test_missing_member_during_apply_is_reported_without_recreating_it(state):
    client, plan, report = state
    create_plan(client, plan, ['Genres'], ids=[A])
    del client.items[B]
    result = apply_plan(client, plan, report)
    assert result['summary']['failed'] == 1
    assert result['results'][B][-1]['reason'] == 'Item missing or unreadable'
    assert all(body['Id'] != B for body in client.posts)


def test_normal_unmerged_listing_does_not_fetch_every_unchanged_detail(monkeypatch):
    client = Client()
    candidate = copy.deepcopy(client.items[A])
    candidate.update(MediaSourceCount=1, MediaSources=[{'Id': A}])

    def unexpected_read(identifier):
        pytest.fail('Ordinary single-source listing needs no expansion detail request')

    monkeypatch.setattr(client, 'get_item_info', unexpected_read)
    assert expand_versions(client, [candidate]) == [candidate]


def test_library_scope_protects_series_seasons_episodes_and_hidden_movies(state, monkeypatch):
    client, plan, report = state
    for number, kind in [(3, 'Series'), (4, 'Season'), (5, 'Episode')]:
        identifier = UUID(int=number).hex
        client.items[identifier] = {
            'Id': identifier, 'Type': kind, 'Name': kind, 'Genres': [], 'ProductionLocations': [],
            'LockedFields': ['Overview'], 'LockData': True,
        }

    def listing(params, label):
        assert set(params['IncludeItemTypes'].split(',')) == {'Movie', 'Series', 'Season', 'Episode', 'Video'}
        return [copy.deepcopy(value) for key, value in client.items.items() if key != B]

    monkeypatch.setattr(client, '_get_jellyfin_items', listing)
    assert len(create_plan(client, plan, ['Genres', 'ProductionLocations'], libraries=[UUID(int=99).hex])['items']) == 5
    assert apply_plan(client, plan, report)['summary']['confirmed'] == 5
    for number in [3, 4, 5]:
        current = client.items[UUID(int=number).hex]
        assert current['LockData'] is True
        assert current['Genres'] == current['ProductionLocations'] == []
        assert set(current['LockedFields']) == {'Overview', 'Genres', 'ProductionLocations'}
