"""Curated Jellyfin values and refresh protection must be confirmed together."""

import copy
from unittest.mock import Mock

import pytest
import requests

from media_server.client import MediaServerClient

pytestmark = pytest.mark.unit


@pytest.fixture
def client():
    return MediaServerClient(server_url='http://test.invalid', server_type='jellyfin')


def item():
    return {
        'Id': 'movie', 'Name': 'Keep name', 'Overview': 'Keep overview',
        'Genres': ['动作'], 'ProductionLocations': [], 'LockData': False,
        'LockedFields': ['Name', 'Overview'], 'OriginalLanguage': 'ja',
    }


@pytest.mark.parametrize('field', ['Genres', 'ProductionLocations'])
def test_save_retains_other_metadata_and_locks_and_verifies_readback(client, monkeypatch, field):
    current = item()
    before = copy.deepcopy(current)
    writes = []

    def request(*args, **kwargs):
        writes.append(copy.deepcopy(kwargs['json_body']))
        return Mock(status_code=204)

    readback = Mock(side_effect=lambda _: writes[-1])
    monkeypatch.setattr(client, '_request', request)
    monkeypatch.setattr(client, 'get_item_info', readback)
    result = client._save_curated_field('movie', current, field)
    assert result.status_code == 204
    assert writes == [{**before, 'LockedFields': ['Name', 'Overview', field]}]
    readback.assert_called_once_with('movie')


@pytest.mark.parametrize('locks', [None, [], ['Genres', 'Name']])
def test_lock_is_added_once(client, monkeypatch, locks):
    current = item()
    current['LockedFields'] = locks
    monkeypatch.setattr(client, '_request', Mock(return_value=Mock(status_code=204)))
    monkeypatch.setattr(client, 'get_item_info', lambda _: current)
    assert client._save_curated_field('movie', current, 'Genres').status_code == 204
    assert current['LockedFields'].count('Genres') == 1
    assert set(current['LockedFields']) == set(locks or []) | {'Genres'}


@pytest.mark.parametrize('locks', ['', 'Genres', {}, [None]])
def test_invalid_locks_do_not_write(client, monkeypatch, locks):
    current = item()
    current['LockedFields'] = locks
    request = Mock()
    monkeypatch.setattr(client, '_request', request)
    assert client._save_curated_field('movie', current, 'Genres').status_code == 0
    request.assert_not_called()


@pytest.mark.parametrize('failure', ['missing_lock', 'lost_existing_lock', 'wrong_value', 'missing_value', 'read_failed'])
@pytest.mark.parametrize('outcome', ['success', 'timeout', 'unavailable'])
def test_unconfirmed_write_is_not_success_or_replayed(client, monkeypatch, failure, outcome):
    current = item()
    actual = {**copy.deepcopy(current), 'LockedFields': ['Name', 'Overview', 'Genres']}
    if failure == 'missing_lock':
        actual['LockedFields'].remove('Genres')
    elif failure == 'lost_existing_lock':
        actual['LockedFields'].remove('Name')
    elif failure == 'wrong_value':
        actual['Genres'] = ['Concurrent edit']
    elif failure == 'missing_value':
        del actual['Genres']
    else:
        actual = None
    request = Mock(return_value=Mock(status_code=204 if outcome == 'success' else 503, text='unavailable'))
    if outcome == 'timeout':
        request.side_effect = requests.exceptions.ReadTimeout('timeout')
    monkeypatch.setattr(client, '_request', request)
    monkeypatch.setattr(client, 'get_item_info', lambda _: actual)
    assert client._save_curated_field('movie', current, 'Genres').status_code == 0
    request.assert_called_once()


def test_timeout_recognizes_committed_value_and_locks(client, monkeypatch):
    current = item()
    request = Mock(side_effect=requests.exceptions.ReadTimeout('timeout'))
    monkeypatch.setattr(client, '_request', request)
    monkeypatch.setattr(client, 'get_item_info', lambda _: {**current, 'LockedFields': [*current['LockedFields'], 'Tags']})
    assert client._save_curated_field('movie', current, 'Genres').status_code == 204
    request.assert_called_once()


def test_emby_keeps_existing_contract(monkeypatch):
    client = MediaServerClient(server_type='emby')
    current = item()
    before = copy.deepcopy(current)
    post = Mock(return_value=Mock(status_code=204))
    monkeypatch.setattr(client, '_post_item_update', post)
    assert client._save_curated_field('movie', current, 'Genres').status_code == 204
    assert current == before
    post.assert_called_once_with('movie', current)


@pytest.mark.parametrize('version,curated,omitted', [
    ('12.0', True, True), ('12.0', False, False), ('10.11.11', True, False), (None, True, False),
])
def test_curation_skips_unchanged_jellyfin12_people_only(client, monkeypatch, version, curated, omitted):
    client.server_version = version
    current = item()
    current['People'] = [{'Id': 'actor', 'Name': 'Keep actor', 'Type': 'Actor', 'Role': 'Keep role'}]
    request = Mock(return_value=Mock(status_code=204))
    monkeypatch.setattr(client, '_request', request)
    monkeypatch.setattr(client, 'get_item_info', lambda _: current)
    if curated:
        assert client._save_curated_field('movie', current, 'Genres').status_code == 204
    else:
        assert client._post_item_update('movie', current).status_code == 204
    payload = request.call_args.kwargs['json_body']
    assert ('People' not in payload) == omitted
    assert current['People'][0]['Role'] == 'Keep role'
    assert payload['Overview'] == current['Overview']
