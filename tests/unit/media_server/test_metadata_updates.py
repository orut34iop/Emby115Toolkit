"""Exercise bounded in-flight work, fresh DTO writes and confirmed result accounting."""

import copy
import threading
from unittest.mock import Mock

import pytest

from media_server.client import MediaServerClient
from media_server.metadata_updates import update_candidates


@pytest.fixture
def client():
    result = MediaServerClient('http://localhost:8096', 'test', 'admin', 'jellyfin')
    yield result
    result.close()


@pytest.mark.parametrize('local,workers', [(False, 4), (True, 8)])
def test_bounded_workers_keep_fresh_fields_and_confirmed_results(client, monkeypatch, local, workers):
    client._local_catalog = Mock() if local else None
    barrier = threading.Barrier(workers)
    lock = threading.Lock()
    active = peak = 0
    candidates = [{'Id': str(index), 'Genres': ['stale']} for index in range(workers * 2)]
    saved = []
    def get(identifier):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        barrier.wait(timeout=5)
        with lock:
            active -= 1
        return {'Id': identifier, 'Genres': ['Action'], 'Overview': 'fresh', 'LockedFields': ['Overview']}
    def save(identifier, item, field):
        saved.append(copy.deepcopy(item))
        return Mock(status_code=204)
    monkeypatch.setattr(client, 'get_item_info', get)
    monkeypatch.setattr(client, '_save_curated_field', save)
    updates = []
    result = update_candidates(client, candidates, 'Genres', lambda _: ['动作'], '流派', updates.append)
    assert peak == workers
    assert [item['Id'] for item in result] == [str(i) for i in range(workers * 2)]
    assert all(item['Overview'] == 'fresh' and item['LockedFields'] == ['Overview'] for item in saved)
    assert updates[-1]['current'] == workers * 2
    assert updates[-1]['percent'] == 100


def test_cancel_stops_scheduling_and_does_not_write_fetched_items(client, monkeypatch):
    fetched, saved = [], []
    def get(identifier):
        fetched.append(identifier)
        client.stop_flag.set()
        return {'Id': identifier, 'Genres': ['Action']}
    monkeypatch.setattr(client, 'get_item_info', get)
    monkeypatch.setattr(client, '_save_curated_field', lambda *args: saved.append(args))
    result = update_candidates(client, [{'Id': str(i)} for i in range(100)],
                               'Genres', lambda _: ['动作'], '流派', None)
    assert len(fetched) <= 4
    assert not saved and not result


def test_failures_and_fresh_unchanged_items_are_not_successes(client, monkeypatch):
    def get(identifier):
        if identifier == 'gone':
            return None
        return {'Id': identifier, 'Genres': ['动作'] if identifier == 'done' else ['Action']}
    save = Mock(return_value=Mock(status_code=0, text='unconfirmed'))
    monkeypatch.setattr(client, 'get_item_info', get)
    monkeypatch.setattr(client, '_save_curated_field', save)
    result = update_candidates(client, [{'Id': i} for i in ['gone', 'done', 'failed']],
                               'Genres', lambda _: ['动作'], '流派', None)
    assert not result
    assert client._metadata_had_errors
    save.assert_called_once()


@pytest.mark.parametrize('field,value', [('Path', '/new'), ('Type', 'Series'), ('Id', 'wrong')])
def test_snapshot_identity_changes_prevent_writes(client, monkeypatch, field, value):
    candidate = {'Id': '1', 'Path': '/old', 'Type': 'Movie', '_local_snapshot': True}
    current = {**candidate, 'Genres': ['Action'], field: value}
    monkeypatch.setattr(client, 'get_item_info', lambda _: current)
    save = Mock()
    monkeypatch.setattr(client, '_save_curated_field', save)
    assert not update_candidates(client, [candidate], 'Genres', lambda _: ['动作'], '流派', None)
    save.assert_not_called()
