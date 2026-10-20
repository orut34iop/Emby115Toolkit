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


def test_merge_lists_pages_without_expanding_historical_versions(client, monkeypatch):
    """A large already-merged library must not trigger one detail GET per version."""
    client.user_id = 'user'
    movies = [
        {'Id': str(i), 'Name': f'Movie {i}', 'MediaSourceCount': 2, 'ProviderIds': {'Tmdb': str(i)}}
        for i in range(1200)
    ]
    movies.append({'Id': 'new', 'Name': 'New version', 'MediaSourceCount': 1, 'ProviderIds': {'Tmdb': '0'}})
    updates, offsets, merged = [], [], []

    def request(method, path, params=None, **kwargs):
        if path == '/UserViews':
            return response({'Items': [
                {'Id': 'movies', 'Name': 'Movies', 'CollectionType': 'movies'},
                {'Id': 'empty', 'Name': 'Empty', 'CollectionType': 'movies'},
            ]})
        if path == '/Items':
            assert method == 'get'
            assert 'MediaSources' not in params['Fields'].split(',')
            if params['ParentId'] == 'empty':
                return response({'Items': [], 'TotalRecordCount': 0})
            start = params['StartIndex']
            offsets.append(start)
            # Progress must reach the UI before the next page request starts.
            if start:
                assert any(update.get('current') == start and update.get('percent', 0) > 1 for update in updates)
            return response({'Items': movies[start:start + params['Limit']], 'TotalRecordCount': len(movies)})
        assert path == '/Videos/MergeVersions'
        assert method == 'post'
        merged.append(params['ids'])
        return response(status=204)

    monkeypatch.setattr(client, '_request', request)
    monkeypatch.setattr(client, 'get_item_info', Mock(side_effect=AssertionError('Unnecessary detail request')))
    monkeypatch.setattr(client, 'validate_server_type', lambda: True)
    monkeypatch.setattr(client, '_start_background_task', lambda target, name: target())
    result = client.merge_versions(lambda payload: updates.append(payload) if isinstance(payload, dict) else None)

    assert offsets == [0, 500, 1000]
    assert merged == ['0,new']
    assert [movie['Id'] for movie in result] == ['0']
    percentages = [update['percent'] for update in updates if 'percent' in update]
    assert percentages == sorted(percentages)
    assert all(percent < 100 for percent in percentages)
    assert updates[-1]['message'] == '合并版本处理完成'
    assert any('Empty' in update['message'] for update in updates)


@pytest.mark.parametrize('cancel', [False, True])
def test_merge_never_writes_after_incomplete_or_cancelled_listing(client, monkeypatch, caplog, cancel):
    client.user_id = 'user'
    calls, updates = [], []

    def request(method, path, **kwargs):
        calls.append((method, path))
        if path == '/UserViews':
            return response({'Items': [{'Id': 'movies', 'CollectionType': 'movies'}]})
        assert path == '/Items'
        if cancel:
            client.stop_flag.set()
        # Empty page despite a nonzero total is an incomplete response.
        return response({'Items': [], 'TotalRecordCount': 100})

    monkeypatch.setattr(client, '_request', request)
    monkeypatch.setattr(client, 'validate_server_type', lambda: True)
    monkeypatch.setattr(client, '_start_background_task', lambda target, name: target())
    with caplog.at_level('INFO'):
        client.merge_versions(updates.append)
    assert all(method == 'get' for method, _ in calls)
    assert not any(update.get('message') == '合并版本处理完成' for update in updates)
    assert '库里没有影片' not in caplog.text
    assert ('已停止合并版本' if cancel else '影片列表读取不完整') in caplog.text


def test_merge_progress_does_not_finish_or_go_backwards_between_tmdb_and_av(client, monkeypatch):
    movies = [
        {'Id': 'a', 'Name': 'A', 'ProviderIds': {'Tmdb': '1'}},
        {'Id': 'b', 'Name': 'B', 'ProviderIds': {'Tmdb': '1'}},
        {'Id': 'c', 'Name': 'C', 'ProviderIds': {'Num': 'TEST-123'}},
        {'Id': 'd', 'Name': 'D', 'ProviderIds': {'Num': 'TEST-123'}},
    ]
    updates = []
    monkeypatch.setattr(client, 'get_movie_media', lambda callback=None: movies)
    monkeypatch.setattr(client, 'validate_server_type', lambda: True)
    monkeypatch.setattr(client, '_start_background_task', lambda target, name: target())
    monkeypatch.setattr(client, '_request', Mock(return_value=response(status=204)))
    client.merge_versions(lambda payload: updates.append(payload) if isinstance(payload, dict) else None)
    percentages = [
        update.get('percent', 100 * update['current'] / update['total'] if update['total'] else 0)
        for update in updates
    ]
    assert percentages == sorted(percentages)
    assert percentages[-1] == 100
    assert all(percent < 100 for percent in percentages[:-1])


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
