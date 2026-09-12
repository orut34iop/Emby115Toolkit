"""Jellyfin compatibility and incomplete-response regression tests."""

import json
from unittest.mock import Mock

import pytest
import requests

from media_server.client import MediaServerClient


def response(payload=None, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(payload).encode()
    return result


@pytest.fixture
def client():
    return MediaServerClient(
        server_url='http://localhost:8096/jellyfin/', api_key='test-key', username='admin', server_type='jellyfin'
    )


@pytest.mark.parametrize('version', ['10.11.11', '12.0', '12.0.0', '13.0', None])
def test_detect_version_without_changing_api_contract(client, monkeypatch, version):
    get = Mock(return_value=response({'ProductName': 'Jellyfin Server', 'Version': version, 'ServerName': 'My Emby'}))
    monkeypatch.setattr('media_server.client.requests.get', get)
    assert client.validate_server_type()
    assert client.server_version == version
    assert client.api_prefix == ''
    assert client.detect_server_type() == 'jellyfin'
    get.assert_called_once_with('http://localhost:8096/jellyfin/System/Info/Public', timeout=10)


def test_force_detection_clears_stale_version_and_user(client, monkeypatch):
    client.detected_server_type = 'jellyfin'
    client.server_version = '10.11.11'
    client.user_id = 'old-user'
    monkeypatch.setattr('media_server.client.requests.get', Mock(return_value=response([])))
    assert client.detect_server_type(force=True) is None
    assert client.server_version is None
    assert client.user_id is None


def test_product_name_takes_priority_over_custom_server_name(client, monkeypatch):
    monkeypatch.setattr(
        'media_server.client.requests.get',
        Mock(
            return_value=response(
                {
                    'ProductName': 'Emby Server',
                    'ServerName': 'Jellyfin',
                    'Version': '4.9.0.0',
                }
            )
        ),
    )
    with pytest.raises(RuntimeError, match='服务器类型选择不一致'):
        client.validate_server_type()


@pytest.mark.parametrize('version', ['10.11.11', '12.0'])
def test_modern_auth_uses_header_only_without_mutating_callers(client, monkeypatch, version):
    client.server_version = version
    params = {'api_key': 'test-key', 'ApiKey': 'test-key', 'UserId': 'user'}
    request = Mock(return_value=response([]))
    monkeypatch.setattr('media_server.client.requests.request', request)
    client._request('get', '/Users', params=params)
    args, kwargs = request.call_args
    assert args == ('get', 'http://localhost:8096/jellyfin/Users')
    assert kwargs['headers'] == {
        'Authorization': 'MediaBrowser Token="test-key"',
        'Content-Type': 'application/json',
    }
    assert kwargs['params'] == {'UserId': 'user'}
    assert params == {'api_key': 'test-key', 'ApiKey': 'test-key', 'UserId': 'user'}


def test_emby_auth_and_prefix_stay_compatible(monkeypatch):
    client = MediaServerClient(server_url='http://localhost:8096', api_key='test-key')
    request = Mock(return_value=response([]))
    monkeypatch.setattr('media_server.client.requests.request', request)
    client._request('get', '/Items', params={'api_key': 'test-key'})
    args, kwargs = request.call_args
    assert args == ('get', 'http://localhost:8096/emby/Items')
    assert kwargs['headers']['X-Emby-Token'] == 'test-key'
    assert 'Authorization' not in kwargs['headers']
    assert kwargs['params'] == {'api_key': 'test-key'}


def test_api_key_header_escapes_control_characters(client):
    client.api_key = 'a"b,+\r\n'
    assert client._auth_headers()['Authorization'] == 'MediaBrowser Token="a%22b%2C%2B%0D%0A"'


def test_user_lookup_ignores_jellyfin_username_case(client, monkeypatch):
    monkeypatch.setattr(client, '_request', Mock(return_value=response([{'Id': 'user', 'Name': 'Admin'}])))
    assert client.emby_get_user_id() == 'user'


def test_pagination_uses_actual_page_length_and_keeps_filters(client, monkeypatch):
    request = Mock(
        side_effect=[
            response({'Items': [{'Id': 'a'}], 'TotalRecordCount': 2}),
            response({'Items': [{'Id': 'b'}], 'TotalRecordCount': 2}),
        ]
    )
    monkeypatch.setattr(client, '_request', request)
    params = {
        'ParentId': 'library',
        'UserId': 'user',
        'IncludeItemTypes': 'Movie',
        'Fields': 'Genres,GenreItems,DateLastSaved',
    }
    assert client._get_jellyfin_items(params, 'test') == [{'Id': 'a'}, {'Id': 'b'}]
    assert [call.kwargs['params']['StartIndex'] for call in request.call_args_list] == [0, 1]
    for call in request.call_args_list:
        assert call.args == ('get', '/Items')
        query = call.kwargs['params']
        assert query['UserId'] == 'user'
        assert query['ParentId'] == 'library'
        assert query['IncludeItemTypes'] == 'Movie'
        assert query['Recursive'] == 'true'
        assert query['Fields'] == 'Genres,DateLastSaved'
        assert 'MinDateLastSaved' not in query
        assert query['Limit'] == 500
    assert params['Fields'] == 'Genres,GenreItems,DateLastSaved'


@pytest.mark.parametrize(
    'bad_page',
    [
        {'Items': [], 'TotalRecordCount': 2},
        {'Items': [{'Id': 'a'}], 'TotalRecordCount': 2},
        {'Items': [{'Name': 'missing id'}]},
        {'Items': 'invalid'},
        {'Items': [], 'TotalRecordCount': '2'},
        {},
        [],
        None,
    ],
)
def test_bad_second_page_discards_partial_results(client, monkeypatch, bad_page):
    client._begin_metadata_update()
    request = Mock(side_effect=[response({'Items': [{'Id': 'a'}], 'TotalRecordCount': 2}), response(bad_page)])
    monkeypatch.setattr(client, '_request', request)
    assert client._get_jellyfin_items({'IncludeItemTypes': 'Movie'}, 'test') is None
    assert client._metadata_had_errors


@pytest.mark.parametrize('status', [401, 403, 404])
def test_auth_or_route_error_does_not_fall_back_to_legacy_auth(client, monkeypatch, status):
    request = Mock(return_value=response({}, status))
    monkeypatch.setattr('media_server.client.requests.request', request)
    assert client._get_jellyfin_items({'IncludeItemTypes': 'Movie'}, 'test') is None
    assert request.call_count == 1
    assert client._metadata_had_errors


def test_global_duplicate_query_does_not_return_partial_results(client, monkeypatch):
    monkeypatch.setattr(
        client,
        '_request',
        Mock(
            side_effect=[
                response({'Items': [{'Id': 'a'}], 'TotalRecordCount': 2}),
                response({}, 403),
            ]
        ),
    )
    assert client.get_all_media() == []
    assert client._metadata_had_errors


def test_pagination_can_finish_without_total_count(client, monkeypatch):
    client.JELLYFIN_PAGE_SIZE = 1
    request = Mock(side_effect=[response({'Items': [{'Id': 'a'}]}), response({'Items': []})])
    monkeypatch.setattr(client, '_request', request)
    assert client._get_jellyfin_items({}, 'test') == [{'Id': 'a'}]
    assert request.call_count == 2


def test_cancel_during_pagination_discards_partial_result(client, monkeypatch):
    def get_page(*args, **kwargs):
        client.request_stop()
        return response({'Items': [{'Id': 'a'}], 'TotalRecordCount': 2})

    request = Mock(side_effect=get_page)
    monkeypatch.setattr(client, '_request', request)
    assert client._get_jellyfin_items({}, 'test') is None
    request.assert_called_once()


@pytest.mark.parametrize('bad_views', [{}, [], {'Items': None}, {'Items': [None]}])
def test_bad_library_views_report_error(client, monkeypatch, bad_views):
    client.user_id = 'user'
    monkeypatch.setattr(client, '_request', Mock(return_value=response(bad_views)))
    assert client._get_genre_update_items('Movie', {}) is None
    assert client._metadata_had_errors


def test_update_preserves_new_jellyfin_metadata_fields(client):
    item = {
        'Id': 'movie',
        'Name': '电影',
        'Genres': ['动作'],
        'GenreItems': [{'Name': 'Action', 'Id': ''}],
        'OriginalLanguage': 'ja',
        'ProviderIds': {'Tmdb': '123'},
        'LockedFields': ['Name'],
        'Overview': '保留简介',
        'Tags': ['收藏'],
        'ProductionLocations': ['日本'],
    }
    payload = client._prepare_item_update_payload(item)
    assert payload == {key: value for key, value in item.items() if key != 'GenreItems'}
    assert 'GenreItems' in item


@pytest.mark.parametrize('method', ['update_genres', 'update_countries'])
@pytest.mark.parametrize('version', ['10.11.11', '12.0'])
def test_every_run_scans_all_movies_and_series(client, monkeypatch, method, version):
    client.server_version = version
    monkeypatch.setattr(client, 'validate_server_type', lambda: True)
    reads = []
    monkeypatch.setattr(client, '_get_genre_update_items', lambda kind, params: reads.append((kind, params)) or [])
    for _ in range(2):
        task = getattr(client, method)()
        task.join(timeout=2)
        assert not task.is_alive()
    assert [kind for kind, _ in reads] == ['Movie', 'Series', 'Movie', 'Series']
    for _, params in reads:
        assert params['Recursive'] == 'true'
        assert 'MinDateLastSaved' not in params
        assert 'DateLastSaved' not in params['Fields']


@pytest.mark.parametrize('method', ['update_genres', 'update_countries'])
def test_failed_full_scan_reports_failure_and_resets_on_next_run(client, monkeypatch, method, caplog):
    monkeypatch.setattr(client, 'validate_server_type', lambda: True)

    def failed_list(*args):
        client._mark_metadata_error()
        return None

    monkeypatch.setattr(client, '_get_genre_update_items', failed_list)
    with caplog.at_level('INFO'):
        task = getattr(client, method)()
        task.join(timeout=2)
    assert not task.is_alive()
    assert client._metadata_had_errors
    assert '部分条目处理失败' in caplog.text
    monkeypatch.setattr(client, '_get_genre_update_items', lambda *args: [])
    task = getattr(client, method)()
    task.join(timeout=2)
    assert not client._metadata_had_errors
