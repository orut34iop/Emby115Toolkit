"""
media_server.client 模块单元测试
"""

import os
import time
import xml.etree.ElementTree as ET
from unittest.mock import patch

import pytest
import requests


class TestMediaServerClientInit:
    """测试 MediaServerClient 初始化"""

    def test_init_with_url_and_api(self):
        """测试使用 URL 和 API 密钥初始化"""
        from media_server.client import MediaServerClient

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        assert operator.server_url == 'http://localhost:8096'
        assert operator.api_key == 'test-api-key'

    def test_init_with_username(self):
        """测试使用用户名初始化"""
        from media_server.client import MediaServerClient

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key', username='testuser')

        assert operator.username == 'testuser'

    def test_init_with_server_type(self):
        """测试服务器类型配置"""
        from media_server.client import MediaServerClient

        emby_operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')
        jellyfin_operator = MediaServerClient(
            server_url='http://localhost:8096', api_key='test-api-key', server_type='jellyfin'
        )

        assert emby_operator.server_type == 'emby'
        assert emby_operator.api_prefix == '/emby'
        assert jellyfin_operator.server_type == 'jellyfin'
        assert jellyfin_operator.api_prefix == ''


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=''):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text
        self.content = text.encode('utf-8')

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.exceptions.HTTPError(f"status code: {self.status_code}")


class TestMediaServerClientServerType:
    """测试 Emby/Jellyfin 服务器类型选择和校验"""

    def test_validate_server_type_stops_on_mismatch(self, monkeypatch):
        from media_server.client import MediaServerClient

        def fake_get(url, timeout=10):
            if url.endswith('/System/Info/Public'):
                return FakeResponse(payload={'ProductName': 'Jellyfin Server'})
            return FakeResponse(status_code=404)

        monkeypatch.setattr('media_server.client.requests.get', fake_get)
        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key', server_type='emby')

        with pytest.raises(RuntimeError, match='服务器类型选择不一致'):
            operator.validate_server_type()

    def test_jellyfin_merge_versions_uses_jellyfin_path_and_ids_param(self, monkeypatch):
        from media_server.client import MediaServerClient

        requests_made = []

        def fake_request(method, url, **kwargs):
            requests_made.append((method, url, kwargs))
            return FakeResponse(status_code=204)

        monkeypatch.setattr('media_server.client.requests.request', fake_request)
        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key', server_type='jellyfin')

        operator.merge_movie_versions(
            {
                '12345': [
                    {'Id': '1', 'Name': 'Movie', 'ProviderIds': {'Tmdb': '12345'}},
                    {'Id': '2', 'Name': 'Movie 4K', 'ProviderIds': {'Tmdb': '12345'}},
                ]
            }
        )

        assert requests_made[0][0] == 'post'
        assert requests_made[0][1] == 'http://localhost:8096/Videos/MergeVersions'
        assert requests_made[0][2]['params']['ids'] == '1,2'
        assert 'Ids' not in requests_made[0][2]['params']

    def test_emby_merge_versions_uses_emby_path_and_ids_param(self, monkeypatch):
        from media_server.client import MediaServerClient

        requests_made = []

        def fake_request(method, url, **kwargs):
            requests_made.append((method, url, kwargs))
            return FakeResponse(status_code=204)

        monkeypatch.setattr('media_server.client.requests.request', fake_request)
        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key', server_type='emby')

        operator.merge_movie_versions(
            {
                '12345': [
                    {'Id': '1', 'Name': 'Movie', 'ProviderIds': {'Tmdb': '12345'}},
                    {'Id': '2', 'Name': 'Movie 4K', 'ProviderIds': {'Tmdb': '12345'}},
                ]
            }
        )

        assert requests_made[0][0] == 'post'
        assert requests_made[0][1] == 'http://localhost:8096/emby/Videos/MergeVersions'
        assert requests_made[0][2]['params']['Ids'] == '1,2'
        assert 'ids' not in requests_made[0][2]['params']

    def test_merge_versions_runs_tmdb_then_av_num(self, monkeypatch):
        from media_server.client import MediaServerClient

        requests_made = []

        def fake_request(method, url, **kwargs):
            requests_made.append((method, url, kwargs))
            return FakeResponse(status_code=204)

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key', server_type='emby')
        operator.validate_server_type = lambda: True
        operator._start_background_task = lambda target, task_name: target()
        operator.get_movie_media = lambda: [
            {'Id': 'tmdb-1', 'Name': 'Movie A', 'ProviderIds': {'Tmdb': '12345'}, 'Path': '/path/movie-a-1080p.mkv'},
            {'Id': 'tmdb-2', 'Name': 'Movie A 4K', 'ProviderIds': {'Tmdb': '12345'}, 'Path': '/path/movie-a-4k.mkv'},
            {'Id': 'av-1', 'Name': 'AARM-009', 'ProviderIds': {'num': 'AARM-009'}, 'Path': '/path/AARM-009.mp4'},
            {'Id': 'av-2', 'Name': 'AARM-009-C', 'ProviderIds': {'Num': 'AARM-009'}, 'Path': '/path/AARM-009-C.mp4'},
            {'Id': 'solo-1', 'Name': 'Movie B', 'ProviderIds': {'Tmdb': '67890'}, 'Path': '/path/movie-b.mkv'},
        ]
        monkeypatch.setattr('media_server.client.requests.request', fake_request)

        result = operator.merge_versions(lambda message: None)

        assert [request[2]['params']['Ids'] for request in requests_made] == [
            'tmdb-1,tmdb-2',
            'av-1,av-2',
        ]
        assert [movie['Id'] for movie in result] == ['tmdb-1', 'av-1']

    def test_merge_versions_skips_av_when_num_provider_missing(self, monkeypatch, caplog):
        from media_server.client import MediaServerClient

        requests_made = []

        def fake_request(method, url, **kwargs):
            requests_made.append((method, url, kwargs))
            return FakeResponse(status_code=204)

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key', server_type='emby')
        operator.validate_server_type = lambda: True
        operator._start_background_task = lambda target, task_name: target()
        operator.get_movie_media = lambda: [
            {'Id': 'tmdb-1', 'Name': 'Movie A', 'ProviderIds': {'Tmdb': '12345'}, 'Path': '/path/movie-a-1080p.mkv'},
            {'Id': 'tmdb-2', 'Name': 'Movie A 4K', 'ProviderIds': {'Tmdb': '12345'}, 'Path': '/path/movie-a-4k.mkv'},
            {'Id': 'solo-1', 'Name': 'Movie B', 'ProviderIds': {'Tmdb': '67890'}, 'Path': '/path/movie-b.mkv'},
        ]
        monkeypatch.setattr('media_server.client.requests.request', fake_request)

        with caplog.at_level('INFO'):
            result = operator.merge_versions(lambda message: None)

        assert [request[2]['params']['Ids'] for request in requests_made] == ['tmdb-1,tmdb-2']
        assert [movie['Id'] for movie in result] == ['tmdb-1']
        assert '未发现 AV 番号数据，跳过 AV 合并' in caplog.text

    def test_item_update_path_follows_selected_server_type(self, monkeypatch):
        from media_server.client import MediaServerClient

        requests_made = []

        def fake_request(method, url, **kwargs):
            requests_made.append((method, url, kwargs))
            return FakeResponse(status_code=204)

        monkeypatch.setattr('media_server.client.requests.request', fake_request)

        MediaServerClient(
            server_url='http://localhost:8096', api_key='test-api-key', server_type='emby'
        )._post_item_update('item1', {'Name': 'Movie'})
        MediaServerClient(
            server_url='http://localhost:8096', api_key='test-api-key', server_type='jellyfin'
        )._post_item_update('item2', {'Name': 'Movie'})

        assert requests_made[0][1] == 'http://localhost:8096/emby/Items/item1'
        assert requests_made[1][1] == 'http://localhost:8096/Items/item2'

    def test_emby_item_update_keeps_genre_items(self, monkeypatch):
        from media_server.client import MediaServerClient

        requests_made = []

        def fake_request(method, url, **kwargs):
            requests_made.append((method, url, kwargs))
            return FakeResponse(status_code=204)

        monkeypatch.setattr('media_server.client.requests.request', fake_request)

        MediaServerClient(
            server_url='http://localhost:8096', api_key='test-api-key', server_type='emby'
        )._post_item_update(
            'item1',
            {
                'Name': 'Movie',
                'Genres': ['动作'],
                'GenreItems': [{'Name': '动作', 'Id': ''}],
            },
        )

        assert requests_made[0][2]['json']['GenreItems'] == [{'Name': '动作', 'Id': ''}]
        assert requests_made[0][2]['data'] is None

    def test_jellyfin_item_update_omits_genre_items(self, monkeypatch):
        from media_server.client import MediaServerClient

        requests_made = []

        def fake_request(method, url, **kwargs):
            requests_made.append((method, url, kwargs))
            return FakeResponse(status_code=204)

        monkeypatch.setattr('media_server.client.requests.request', fake_request)

        item = {
            'Name': 'Movie',
            'Genres': ['动作', '戏剧'],
            'GenreItems': [
                {'Name': '动作', 'Id': 'genre-action'},
                {'Name': '戏剧', 'Id': ''},
            ],
        }
        MediaServerClient(
            server_url='http://localhost:8096', api_key='test-api-key', server_type='jellyfin'
        )._post_item_update('item2', item)

        assert requests_made[0][2]['json'] == {
            'Name': 'Movie',
            'Genres': ['动作', '戏剧'],
        }
        assert item['GenreItems'][1]['Id'] == ''
        assert requests_made[0][2]['data'] is None

    def test_item_update_retries_timeout(self, monkeypatch):
        from media_server.client import MediaServerClient

        requests_made = []

        def fake_request(method, url, **kwargs):
            requests_made.append((method, url, kwargs))
            if len(requests_made) == 1:
                raise requests.exceptions.ReadTimeout('slow update')
            return FakeResponse(status_code=204)

        monkeypatch.setattr('media_server.client.requests.request', fake_request)
        monkeypatch.setattr('media_server.client.time.sleep', lambda seconds: None)

        response = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')._post_item_update(
            'item1', {'Name': 'Movie'}
        )

        assert response.status_code == 204
        assert len(requests_made) == 2
        assert requests_made[0][2]['timeout'] == (5, 45)

    def test_item_update_timeout_returns_failure_response(self, monkeypatch):
        from media_server.client import MediaServerClient

        requests_made = []

        def fake_request(method, url, **kwargs):
            requests_made.append((method, url, kwargs))
            raise requests.exceptions.ReadTimeout('slow update')

        monkeypatch.setattr('media_server.client.requests.request', fake_request)
        monkeypatch.setattr('media_server.client.time.sleep', lambda seconds: None)

        response = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')._post_item_update(
            'item1', {'Name': 'Movie'}
        )

        assert response.status_code == 0
        assert 'slow update' in response.text
        assert len(requests_made) == 2

    def test_jellyfin_user_lookup_uses_users_endpoint(self, monkeypatch):
        from media_server.client import MediaServerClient

        requests_made = []

        def fake_request(method, url, **kwargs):
            requests_made.append((method, url, kwargs))
            return FakeResponse(
                payload=[
                    {'Id': 'user1', 'Name': 'other'},
                    {'Id': 'user2', 'Name': 'wiz'},
                ]
            )

        monkeypatch.setattr('media_server.client.requests.request', fake_request)
        operator = MediaServerClient(
            server_url='http://localhost:8096', api_key='test-api-key', username='wiz', server_type='jellyfin'
        )

        assert operator.emby_get_user_id() == 'user2'
        assert requests_made[0][0] == 'get'
        assert requests_made[0][1] == 'http://localhost:8096/Users'

    def test_jellyfin_item_detail_uses_user_item_endpoint(self, monkeypatch):
        from media_server.client import MediaServerClient

        requests_made = []

        def fake_request(method, url, **kwargs):
            requests_made.append((method, url, kwargs))
            return FakeResponse(payload={'Id': 'movie1', 'Name': 'Movie'})

        monkeypatch.setattr('media_server.client.requests.request', fake_request)
        operator = MediaServerClient(
            server_url='http://localhost:8096', api_key='test-api-key', username='wiz', server_type='jellyfin'
        )
        operator.user_id = 'user1'

        assert operator.jellyfin_get_item_info('movie1')['Name'] == 'Movie'
        assert requests_made[0][0] == 'get'
        assert requests_made[0][1] == 'http://localhost:8096/Users/user1/Items/movie1'

    def test_jellyfin_item_detail_timeout_returns_none(self, monkeypatch):
        from media_server.client import MediaServerClient

        requests_made = []

        def fake_request(method, url, **kwargs):
            requests_made.append((method, url, kwargs))
            raise requests.exceptions.ReadTimeout('slow detail')

        monkeypatch.setattr('media_server.client.requests.request', fake_request)
        monkeypatch.setattr('media_server.client.time.sleep', lambda seconds: None)
        operator = MediaServerClient(
            server_url='http://localhost:8096', api_key='test-api-key', username='wiz', server_type='jellyfin'
        )
        operator.user_id = 'user1'

        assert operator.jellyfin_get_item_info('movie1') is None
        assert len(requests_made) == 2

    def test_jellyfin_genre_update_uses_jellyfin_item_detail(self, monkeypatch):
        from media_server.client import MediaServerClient

        operator = MediaServerClient(
            server_url='http://localhost:8096', api_key='test-api-key', username='wiz', server_type='jellyfin'
        )
        operator.user_id = 'user1'
        requests_made = []

        def fake_request(method, url, **kwargs):
            requests_made.append((method, url, kwargs))
            assert method == 'get'
            if url == 'http://localhost:8096/Users/user1/Views':
                return FakeResponse(
                    payload={
                        'Items': [
                            {'Id': 'library1', 'Name': 'Movies', 'CollectionType': 'movies'},
                        ]
                    }
                )
            assert url == 'http://localhost:8096/Users/user1/Items'
            assert kwargs['params']['ParentId'] == 'library1'
            return FakeResponse(
                payload={
                    'Items': [
                        {
                            'Id': 'movie1',
                            'Name': 'Movie',
                            'Genres': ['Action'],
                            'GenreItems': [{'Name': 'Action', 'Id': 'genre-action'}],
                        }
                    ]
                }
            )

        def fail_emby_detail(item_id):
            pytest.fail('Jellyfin 更新流派不应该调用 Emby 用户详情接口')

        monkeypatch.setattr('media_server.client.requests.request', fake_request)
        monkeypatch.setattr(operator, 'emby_get_item_info', fail_emby_detail)
        monkeypatch.setattr(
            operator,
            'jellyfin_get_item_info',
            lambda item_id: {
                'Id': item_id,
                'Name': 'Movie',
                'Genres': ['Action'],
                'GenreItems': [{'Name': 'Action', 'Id': 'genre-action'}],
            },
        )

        updates = []
        monkeypatch.setattr(
            operator,
            '_post_item_update',
            lambda item_id, item: updates.append((item_id, item)) or FakeResponse(status_code=204),
        )

        updated_movies = operator.emby_movie_translate_genres_and_update_whole_item()

        assert len(updated_movies) == 1
        assert updates[0][0] == 'movie1'
        assert updates[0][1]['Genres'] == ['动作']
        assert [request[1] for request in requests_made] == [
            'http://localhost:8096/Users/user1/Views',
            'http://localhost:8096/Users/user1/Items',
        ]

    def test_jellyfin_genre_update_enumerates_movie_views_and_deduplicates_items(self, monkeypatch):
        from media_server.client import MediaServerClient

        operator = MediaServerClient(
            server_url='http://localhost:8096', api_key='test-api-key', username='wiz', server_type='jellyfin'
        )
        operator.user_id = 'user1'
        item_requests = []

        def fake_request(method, path, params=None, **_kwargs):
            assert method == 'get'
            if path == '/Users/user1/Views':
                return FakeResponse(
                    payload={
                        'Items': [
                            {'Id': 'movies1', 'Name': 'Movies 1', 'CollectionType': 'movies'},
                            {'Id': 'series1', 'Name': 'Series', 'CollectionType': 'tvshows'},
                            {'Id': 'movies2', 'Name': 'Movies 2', 'CollectionType': 'movies'},
                        ]
                    }
                )

            assert path == '/Users/user1/Items'
            item_requests.append(params.copy())
            if params['ParentId'] == 'movies1':
                return FakeResponse(
                    payload={
                        'Items': [
                            {'Id': 'movie1', 'Name': 'Movie 1', 'Genres': ['Action'], 'GenreItems': []},
                        ]
                    }
                )
            assert params['ParentId'] == 'movies2'
            return FakeResponse(
                payload={
                    'Items': [
                        {'Id': 'movie1', 'Name': 'Movie 1 duplicate', 'Genres': ['Action'], 'GenreItems': []},
                        {'Id': 'movie2', 'Name': 'Movie 2', 'Genres': ['Suspense'], 'GenreItems': []},
                    ]
                }
            )

        monkeypatch.setattr(operator, '_request', fake_request)
        monkeypatch.setattr(
            operator,
            'get_item_info',
            lambda item_id: {
                'Id': item_id,
                'Name': item_id,
                'Genres': ['Action'] if item_id == 'movie1' else ['Suspense'],
                'GenreItems': [],
            },
        )
        updates = []
        monkeypatch.setattr(
            operator,
            '_post_item_update',
            lambda item_id, item: updates.append((item_id, item)) or FakeResponse(status_code=204),
        )

        updated_movies = operator.emby_movie_translate_genres_and_update_whole_item()

        assert [params['ParentId'] for params in item_requests] == ['movies1', 'movies2']
        assert [movie['Id'] for movie in updated_movies] == ['movie1', 'movie2']
        assert [item_id for item_id, _ in updates] == ['movie1', 'movie2']
        assert [item['Genres'] for _, item in updates] == [['动作'], ['悬疑']]

    def test_genre_translation_resolves_chained_mapping(self):
        from media_server.client import MediaServerClient
        from media_server.genre_maps import MOVIE_GENRE_TRANSLATIONS

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        assert operator._translate_genres(['Suspense', '悬念', 'Action'], MOVIE_GENRE_TRANSLATIONS) == [
            '悬疑',
            '动作',
        ]

    def test_genre_translation_normalizes_traditional_variants(self):
        from media_server.client import MediaServerClient
        from media_server.genre_maps import MOVIE_GENRE_TRANSLATIONS

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        assert operator._translate_genres(
            ['DMM獨家', 'DMM專屬', '給女性觀眾', '業餘'],
            MOVIE_GENRE_TRANSLATIONS,
        ) == [
            'DMM独家',
            '给女性观众',
            '业余',
        ]

    def test_tv_genre_translation_handles_old_chinese_names(self):
        from media_server.client import MediaServerClient
        from media_server.genre_maps import TV_GENRE_TRANSLATIONS

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        assert operator._translate_genres(['浪漫', '真人秀电视', '纪录'], TV_GENRE_TRANSLATIONS) == [
            '爱情',
            '真人秀',
            '纪录片',
        ]

    def test_movie_genre_update_resolves_chained_mapping_before_post(self, monkeypatch):
        from media_server.client import MediaServerClient

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        monkeypatch.setattr(
            operator,
            '_request',
            lambda method, path, params=None, **_kwargs: FakeResponse(
                payload={
                    'Items': [
                        {
                            'Id': 'movie1',
                            'Name': 'Movie',
                            'Genres': ['Suspense', '悬念'],
                            'GenreItems': [],
                        }
                    ]
                }
            ),
        )
        monkeypatch.setattr(
            operator,
            'get_item_info',
            lambda item_id: {
                'Id': item_id,
                'Name': 'Movie',
                'Genres': ['Suspense', '悬念'],
                'GenreItems': [],
            },
        )
        updates = []
        monkeypatch.setattr(
            operator,
            '_post_item_update',
            lambda item_id, item: updates.append((item_id, item)) or FakeResponse(status_code=204),
        )

        updated_movies = operator.emby_movie_translate_genres_and_update_whole_item()

        assert len(updated_movies) == 1
        assert updates[0][1]['Genres'] == ['悬疑']

    def test_movie_genre_update_skips_duplicate_item_ids(self, monkeypatch):
        from media_server.client import MediaServerClient

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        monkeypatch.setattr(
            operator,
            '_request',
            lambda method, path, params=None, **_kwargs: FakeResponse(
                payload={
                    'Items': [
                        {'Id': 'movie1', 'Name': 'Movie', 'Genres': ['Action'], 'GenreItems': []},
                        {'Id': 'movie1', 'Name': 'Movie duplicate', 'Genres': ['Action'], 'GenreItems': []},
                    ]
                }
            ),
        )
        detail_calls = []
        monkeypatch.setattr(
            operator,
            'get_item_info',
            lambda item_id: detail_calls.append(item_id)
            or {'Id': item_id, 'Name': 'Movie', 'Genres': ['Action'], 'GenreItems': []},
        )
        updates = []
        monkeypatch.setattr(
            operator,
            '_post_item_update',
            lambda item_id, item: updates.append((item_id, item)) or FakeResponse(status_code=204),
        )

        operator.emby_movie_translate_genres_and_update_whole_item()

        assert detail_calls == ['movie1']
        assert [update[0] for update in updates] == ['movie1']

    def test_movie_genre_update_respects_stop_flag_before_post(self, monkeypatch):
        from media_server.client import MediaServerClient

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')
        operator.stop_flag.set()

        monkeypatch.setattr(
            operator,
            '_request',
            lambda method, path, params=None, **_kwargs: FakeResponse(
                payload={
                    'Items': [
                        {'Id': 'movie1', 'Name': 'Movie', 'Genres': ['Action'], 'GenreItems': []},
                    ]
                }
            ),
        )
        updates = []
        monkeypatch.setattr(
            operator,
            '_post_item_update',
            lambda item_id, item: updates.append((item_id, item)) or FakeResponse(status_code=204),
        )

        updated_movies = operator.emby_movie_translate_genres_and_update_whole_item()

        assert updated_movies == []
        assert updates == []

    def test_movie_genre_update_prescans_candidates_and_throttles_progress(self, monkeypatch):
        from media_server.client import MediaServerClient

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')
        movies = [
            {'Id': f'unchanged-{index}', 'Name': f'Unchanged {index}', 'Genres': ['动作'], 'GenreItems': []}
            for index in range(1000)
        ]
        movies.append(
            {
                'Id': 'movie-action',
                'Name': 'Needs Update',
                'Genres': ['Action'],
                'GenreItems': [{'Name': 'Action', 'Id': 'genre-action'}],
            }
        )

        monkeypatch.setattr(
            operator,
            '_request',
            lambda method, path, params=None, **_kwargs: FakeResponse(payload={'Items': movies}),
        )
        detail_calls = []
        monkeypatch.setattr(
            operator,
            'get_item_info',
            lambda item_id: detail_calls.append(item_id)
            or {'Id': item_id, 'Name': 'Needs Update', 'Genres': ['Action'], 'GenreItems': []},
        )
        updates = []
        monkeypatch.setattr(
            operator,
            '_post_item_update',
            lambda item_id, item: updates.append((item_id, item)) or FakeResponse(status_code=204),
        )
        progress_events = []

        updated_movies = operator.emby_movie_translate_genres_and_update_whole_item(progress_callback=progress_events.append)

        assert [movie['Id'] for movie in updated_movies] == ['movie-action']
        assert detail_calls == ['movie-action']
        assert [update[0] for update in updates] == ['movie-action']
        assert len(progress_events) < 10
        assert any('扫描影片流派进度' in event['message'] for event in progress_events)
        scan_finished_event = next(
            event for event in progress_events if event['message'].startswith('扫描影片流派进度: 1001/1001')
        )
        assert scan_finished_event['percent'] == 50
        assert any('开始更新影片流派' in event['message'] for event in progress_events)

    def test_update_genres_scales_movie_and_series_progress(self, monkeypatch):
        from media_server.client import MediaServerClient

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')
        monkeypatch.setattr(operator, 'validate_server_type', lambda: None)

        def fake_update_movies(progress_callback=None):
            progress_callback({'message': '影片阶段完成', 'current': 1, 'total': 1, 'percent': 100})
            return []

        def fake_update_series(progress_callback=None):
            progress_callback({'message': '剧集阶段开始', 'current': 0, 'total': 1, 'percent': 0})
            progress_callback({'message': '剧集阶段完成', 'current': 1, 'total': 1, 'percent': 100})
            return []

        monkeypatch.setattr(operator, 'emby_movie_translate_genres_and_update_whole_item', fake_update_movies)
        monkeypatch.setattr(operator, 'emby_tv_translate_genres_and_update_whole_item', fake_update_series)
        progress_events = []

        thread = operator.update_genres(callback=progress_events.append)
        thread.join(timeout=1)

        assert not thread.is_alive()
        assert next(event for event in progress_events if event['message'] == '影片阶段完成')['percent'] == 50
        assert next(event for event in progress_events if event['message'] == '剧集阶段开始')['percent'] == 50
        assert next(event for event in progress_events if event['message'] == '剧集阶段完成')['percent'] == 100

    def test_movie_genre_update_rescans_stale_candidates(self, monkeypatch):
        from media_server.client import MediaServerClient

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')
        stale_movies = [
            {'Id': f'movie-{index}', 'Name': f'Movie {index}', 'Genres': ['Action'], 'GenreItems': []}
            for index in range(200)
        ]
        fresh_movies = [
            {'Id': f'movie-{index}', 'Name': f'Movie {index}', 'Genres': ['动作'], 'GenreItems': []}
            for index in range(200)
        ]
        request_calls = []

        def fake_request(method, path, params=None, **_kwargs):
            request_calls.append((method, path, params))
            payload = {'Items': stale_movies if len(request_calls) == 1 else fresh_movies}
            return FakeResponse(payload=payload)

        monkeypatch.setattr(operator, '_request', fake_request)
        monkeypatch.setattr(
            operator,
            'get_item_info',
            lambda item_id: {'Id': item_id, 'Name': item_id, 'Genres': ['动作'], 'GenreItems': []},
        )
        updates = []
        monkeypatch.setattr(
            operator,
            '_post_item_update',
            lambda item_id, item: updates.append((item_id, item)) or FakeResponse(status_code=204),
        )

        updated_movies = operator.emby_movie_translate_genres_and_update_whole_item()

        assert updated_movies == []
        assert updates == []
        assert len(request_calls) == 2

    def test_country_translation_normalizes_aliases_and_deduplicates(self):
        from media_server.client import MediaServerClient

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        assert operator._translate_production_locations(
            [
                'Japan',
                'jpn',
                '日本',
                'Hong Kong',
                '中国香港特别行政区',
                'US',
                'usa',
                'Soviet Union',
                ' ',
            ]
        ) == ['日本', '中国香港', '美国', '苏联']

    def test_country_translation_is_case_insensitive_and_preserves_historical_regions(self):
        from media_server.client import MediaServerClient

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        assert operator._translate_production_locations(
            ['USA', 'united kingdom', 'Czechoslovakia', 'West Germany', 'Serbia and Montenegro']
        ) == ['美国', '英国', '捷克斯洛伐克', '西德', '塞尔维亚和黑山']

    def test_movie_country_update_changes_only_production_locations(self, monkeypatch):
        from media_server.client import MediaServerClient

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')
        snapshot = {
            'Id': 'movie1',
            'Name': 'Movie',
            'Genres': ['剧情'],
            'ProductionLocations': ['Japan', 'jpn', '日本', 'usa'],
        }
        monkeypatch.setattr(
            operator,
            '_get_genre_update_items',
            lambda include_item_types, params: [snapshot.copy()],
        )
        monkeypatch.setattr(operator, 'get_item_info', lambda item_id: snapshot.copy())
        updates = []
        monkeypatch.setattr(
            operator,
            '_post_item_update',
            lambda item_id, item: updates.append((item_id, item)) or FakeResponse(status_code=204),
        )

        updated_movies = operator.emby_movie_translate_countries_and_update_whole_item()

        assert [item['Id'] for item in updated_movies] == ['movie1']
        assert updates[0][0] == 'movie1'
        assert updates[0][1]['ProductionLocations'] == ['日本', '美国']
        assert updates[0][1]['Genres'] == ['剧情']

    def test_country_update_uses_jellyfin_library_enumeration(self, monkeypatch):
        from media_server.client import MediaServerClient

        operator = MediaServerClient(
            server_url='http://localhost:8096', api_key='test-api-key', username='wiz', server_type='jellyfin'
        )
        operator.user_id = 'user1'
        item_requests = []

        def fake_request(method, path, params=None, **_kwargs):
            assert method == 'get'
            if path == '/Users/user1/Views':
                return FakeResponse(
                    payload={
                        'Items': [
                            {'Id': 'movies1', 'Name': 'Movies', 'CollectionType': 'movies'},
                            {'Id': 'series1', 'Name': 'Series', 'CollectionType': 'tvshows'},
                        ]
                    }
                )
            assert path == '/Users/user1/Items'
            item_requests.append(params.copy())
            return FakeResponse(
                payload={
                    'Items': [
                        {'Id': 'movie1', 'Name': 'Movie', 'ProductionLocations': ['Japan']},
                    ]
                }
            )

        monkeypatch.setattr(operator, '_request', fake_request)
        monkeypatch.setattr(
            operator,
            'get_item_info',
            lambda item_id: {'Id': item_id, 'Name': 'Movie', 'ProductionLocations': ['Japan']},
        )
        updates = []
        monkeypatch.setattr(
            operator,
            '_post_item_update',
            lambda item_id, item: updates.append((item_id, item)) or FakeResponse(status_code=204),
        )

        updated_movies = operator.emby_movie_translate_countries_and_update_whole_item()

        assert [params['ParentId'] for params in item_requests] == ['movies1']
        assert [item['Id'] for item in updated_movies] == ['movie1']
        assert updates[0][1]['ProductionLocations'] == ['日本']

    def test_jellyfin_library_listing_retries_read_timeout(self, monkeypatch):
        from media_server.client import MediaServerClient

        operator = MediaServerClient(
            server_url='http://localhost:8096', api_key='test-api-key', username='wiz', server_type='jellyfin'
        )
        operator.user_id = 'user1'
        item_attempts = []

        def fake_request(method, path, params=None, timeout=None, **_kwargs):
            assert method == 'get'
            if path == '/Users/user1/Views':
                return FakeResponse(
                    payload={
                        'Items': [
                            {'Id': 'movies1', 'Name': 'Large Movies', 'CollectionType': 'movies'},
                        ]
                    }
                )

            assert path == '/Users/user1/Items'
            item_attempts.append(timeout)
            if len(item_attempts) == 1:
                raise requests.exceptions.ReadTimeout('slow library')
            return FakeResponse(
                payload={
                    'Items': [
                        {'Id': 'movie1', 'Name': 'Movie', 'ProductionLocations': ['Japan']},
                    ]
                }
            )

        monkeypatch.setattr(operator, '_request', fake_request)
        monkeypatch.setattr('media_server.client.time.sleep', lambda _seconds: None)

        items = operator._get_genre_update_items(
            'Movie',
            {
                'Recursive': 'true',
                'IncludeItemTypes': 'Movie',
                'Fields': 'ProductionLocations',
                'Limit': '1000000',
            },
        )

        assert [item['Id'] for item in items] == ['movie1']
        assert item_attempts == [(5, 120), (5, 120)]

    def test_update_countries_scales_movie_and_series_progress(self, monkeypatch):
        from media_server.client import MediaServerClient

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')
        monkeypatch.setattr(operator, 'validate_server_type', lambda: None)

        def fake_update_movies(progress_callback=None):
            progress_callback({'message': '影片地区完成', 'current': 1, 'total': 1, 'percent': 100})
            return []

        def fake_update_series(progress_callback=None):
            progress_callback({'message': '剧集地区开始', 'current': 0, 'total': 1, 'percent': 0})
            progress_callback({'message': '剧集地区完成', 'current': 1, 'total': 1, 'percent': 100})
            return []

        monkeypatch.setattr(operator, 'emby_movie_translate_countries_and_update_whole_item', fake_update_movies)
        monkeypatch.setattr(operator, 'emby_tv_translate_countries_and_update_whole_item', fake_update_series)
        progress_events = []

        thread = operator.update_countries(callback=progress_events.append)
        thread.join(timeout=1)

        assert not thread.is_alive()
        assert next(event for event in progress_events if event['message'] == '影片地区完成')['percent'] == 50
        assert next(event for event in progress_events if event['message'] == '剧集地区开始')['percent'] == 50
        assert next(event for event in progress_events if event['message'] == '剧集地区完成')['percent'] == 100


class TestMediaServerClientExtractTmdbid:
    """测试 extract_tmdbid_from_nfo 方法"""

    def test_extract_tmdbid_valid_nfo(self, temp_dir):
        """测试从有效的 NFO 文件提取 TMDB ID"""
        from media_server.client import MediaServerClient

        nfo_content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
    <title>Test Movie</title>
    <tmdbid>12345</tmdbid>
</movie>"""

        nfo_path = os.path.join(temp_dir, 'movie.nfo')
        with open(nfo_path, 'w', encoding='utf-8') as f:
            f.write(nfo_content)

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        result, is_damaged = operator.extract_tmdbid_from_nfo(nfo_path)

        assert result == '12345'
        assert is_damaged == False

    def test_extract_tmdbid_missing_tmdbid(self, temp_dir):
        """测试缺少 tmdbid 的 NFO 文件"""
        from media_server.client import MediaServerClient

        nfo_content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
    <title>Test Movie</title>
</movie>"""

        nfo_path = os.path.join(temp_dir, 'movie.nfo')
        with open(nfo_path, 'w', encoding='utf-8') as f:
            f.write(nfo_content)

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        result, is_damaged = operator.extract_tmdbid_from_nfo(nfo_path)

        assert result is None
        assert is_damaged == False

    def test_extract_tmdbid_damaged_nfo(self, temp_dir):
        """测试损坏的 NFO 文件（强制提取）"""
        from media_server.client import MediaServerClient

        # 不完整的 XML，但有 tmdbid 行
        nfo_content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
    <title>Test Movie</title>
  <tmdbid>67890</tmdbid>
"""

        nfo_path = os.path.join(temp_dir, 'movie.nfo')
        with open(nfo_path, 'w', encoding='utf-8') as f:
            f.write(nfo_content)

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        result, is_damaged = operator.extract_tmdbid_from_nfo(nfo_path)

        assert result == '67890'
        assert is_damaged == True


class TestMediaServerClientQueryMovies:
    """测试 query_movies_by_tmdbid 方法"""

    def test_query_movies_found(self):
        """测试找到匹配的影片"""
        from media_server.client import MediaServerClient

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        movies = [
            {'Name': 'Movie 1', 'ProviderIds': {'Tmdb': '12345'}},
            {'Name': 'Movie 2', 'ProviderIds': {'Tmdb': '67890'}},
        ]

        result = operator.query_movies_by_tmdbid(movies, '12345')

        assert result == True

    def test_query_movies_not_found(self):
        """测试未找到匹配的影片"""
        from media_server.client import MediaServerClient

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        movies = [
            {'Name': 'Movie 1', 'ProviderIds': {'Tmdb': '12345'}},
            {'Name': 'Movie 2', 'ProviderIds': {'Tmdb': '67890'}},
        ]

        result = operator.query_movies_by_tmdbid(movies, '99999')

        assert result == False

    def test_query_movies_empty_list(self):
        """测试空影片列表"""
        from media_server.client import MediaServerClient

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        result = operator.query_movies_by_tmdbid([], '12345')

        assert result == False


class TestMediaServerClientGroupMovies:
    """测试 group_movies_by_tmdbid 方法"""

    def test_group_movies_with_duplicates(self):
        """测试分组有重复的影片"""
        from media_server.client import MediaServerClient

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        movies = [
            {'Id': '1', 'Name': 'Movie A', 'ProviderIds': {'Tmdb': '12345'}, 'Path': '/path/a'},
            {'Id': '2', 'Name': 'Movie A HD', 'ProviderIds': {'Tmdb': '12345'}, 'Path': '/path/b'},
            {'Id': '3', 'Name': 'Movie B', 'ProviderIds': {'Tmdb': '67890'}, 'Path': '/path/c'},
        ]

        result = operator.group_movies_by_tmdbid(movies)

        assert '12345' in result
        assert '67890' in result
        assert len(result['12345']) == 2
        assert len(result['67890']) == 1

    def test_group_movies_no_duplicates(self):
        """测试分组无重复的影片"""
        from media_server.client import MediaServerClient

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        movies = [
            {'Id': '1', 'Name': 'Movie A', 'ProviderIds': {'Tmdb': '12345'}, 'Path': '/path/a'},
            {'Id': '2', 'Name': 'Movie B', 'ProviderIds': {'Tmdb': '67890'}, 'Path': '/path/b'},
        ]

        result = operator.group_movies_by_tmdbid(movies)

        assert len(result) == 2
        assert len(result['12345']) == 1
        assert len(result['67890']) == 1

    def test_group_movies_by_provider_id_matches_key_case_insensitive(self):
        """测试 provider key 大小写不敏感"""
        from media_server.client import MediaServerClient

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        movies = [
            {'Id': '1', 'Name': 'AARM-009', 'ProviderIds': {'num': 'AARM-009'}, 'Path': '/path/a'},
            {'Id': '2', 'Name': 'AARM-009-C', 'ProviderIds': {'Num': 'AARM-009'}, 'Path': '/path/b'},
            {'Id': '3', 'Name': 'Movie A', 'ProviderIds': {'Tmdb': '12345'}, 'Path': '/path/c'},
            {'Id': '4', 'Name': 'No Provider', 'ProviderIds': {}, 'Path': '/path/d'},
        ]

        av_result = operator.group_movies_by_provider_id(movies, 'num')
        tmdb_result = operator.group_movies_by_provider_id(movies, 'tmdb')

        assert list(av_result.keys()) == ['AARM-009']
        assert [movie['Id'] for movie in av_result['AARM-009']] == ['1', '2']
        assert list(tmdb_result.keys()) == ['12345']
        assert [movie['Id'] for movie in tmdb_result['12345']] == ['3']

    def test_group_movies_by_provider_id_normalizes_av_num_value_case(self):
        """测试 AV 番号值大小写不同时仍合并到同一组"""
        from media_server.client import MediaServerClient

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        movies = [
            {'Id': '1', 'Name': 'AARM-009', 'ProviderIds': {'num': 'AARM-009'}, 'Path': '/path/a'},
            {'Id': '2', 'Name': 'aarm-009', 'ProviderIds': {'num': 'aarm-009'}, 'Path': '/path/b'},
        ]

        result = operator.group_movies_by_provider_id(movies, 'num')

        assert list(result.keys()) == ['AARM-009']
        assert [movie['Id'] for movie in result['AARM-009']] == ['1', '2']


class TestMediaServerClientFindRelatedVideos:
    """测试 find_related_videos 方法"""

    def test_find_related_video_exists(self, temp_dir, create_test_file_structure):
        """测试找到相关视频文件"""
        from media_server.client import MediaServerClient

        structure = {
            'movies/Movie.2023.nfo': 'nfo content',
            'movies/Movie.2023.mp4': 'video content',
        }
        create_test_file_structure(structure)

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        nfo_path = os.path.join(temp_dir, 'movies', 'Movie.2023.nfo')
        result = operator.find_related_videos(nfo_path)

        assert result is not None
        assert 'Movie.2023.mp4' in result

    def test_find_related_video_not_exists(self, temp_dir, create_test_file_structure):
        """测试未找到相关视频文件"""
        from media_server.client import MediaServerClient

        structure = {
            'movies/Movie.2023.nfo': 'nfo content',
        }
        create_test_file_structure(structure)

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        nfo_path = os.path.join(temp_dir, 'movies', 'Movie.2023.nfo')
        result = operator.find_related_videos(nfo_path)

        assert result is None

    def test_find_related_video_different_extensions(self, temp_dir, create_test_file_structure):
        """测试不同扩展名的视频文件"""
        from media_server.client import MediaServerClient

        structure = {
            'movies/Movie.2023.nfo': 'nfo content',
            'movies/Movie.2023.mkv': 'video content',
        }
        create_test_file_structure(structure)

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        nfo_path = os.path.join(temp_dir, 'movies', 'Movie.2023.nfo')
        result = operator.find_related_videos(nfo_path)

        assert result is not None
        assert 'Movie.2023.mkv' in result


class TestMediaServerClientCheckNfoFiles:
    """测试 check_nfo_files 方法"""

    def test_check_nfo_files_all_valid(self, temp_dir, create_test_file_structure):
        """测试所有 NFO 都有对应视频"""
        from media_server.client import MediaServerClient

        structure = {
            'movies/Movie1.2023.nfo': 'nfo1',
            'movies/Movie1.2023.mp4': 'video1',
            'movies/Movie2.2022.nfo': 'nfo2',
            'movies/Movie2.2022.mkv': 'video2',
        }
        create_test_file_structure(structure)

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        result = operator.check_nfo_files(temp_dir)

        assert result['total_nfo'] == 2
        assert len(result['no_video_nfo']) == 0
        assert len(result['found_video_nfo']) == 2

    def test_check_nfo_files_some_missing(self, temp_dir, create_test_file_structure):
        """测试部分 NFO 缺少视频"""
        from media_server.client import MediaServerClient

        structure = {
            'movies/Movie1.2023.nfo': 'nfo1',
            'movies/Movie1.2023.mp4': 'video1',
            'movies/Movie2.2022.nfo': 'nfo2',
            # Movie2 没有视频文件
        }
        create_test_file_structure(structure)

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        result = operator.check_nfo_files(temp_dir)

        assert result['total_nfo'] == 2
        assert len(result['no_video_nfo']) == 1
        assert len(result['found_video_nfo']) == 1

    def test_check_nfo_files_skips_tvshow_nfo(self, temp_dir, create_test_file_structure):
        """测试跳过 tvshow.nfo 和 season.nfo"""
        from media_server.client import MediaServerClient

        structure = {
            'tvshow/tvshow.nfo': 'show nfo',
            'tvshow/season.nfo': 'season nfo',
            'tvshow/episode01.nfo': 'ep nfo',
            'tvshow/episode01.mp4': 'ep video',
        }
        create_test_file_structure(structure)

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        result = operator.check_nfo_files(temp_dir)

        # tvshow.nfo 和 season.nfo 应该被跳过
        assert result['total_nfo'] == 1
        assert len(result['found_video_nfo']) == 1


class TestMediaServerClientCheckVideoFiles:
    """测试 check_video_files 方法"""

    def test_check_video_files_all_have_nfo(self, temp_dir, create_test_file_structure):
        """测试所有视频都有 NFO"""
        from media_server.client import MediaServerClient

        structure = {
            'movies/Movie1.2023.mp4': 'video1',
            'movies/Movie1.2023.nfo': 'nfo1',
            'movies/Movie2.2022.mkv': 'video2',
            'movies/Movie2.2022.nfo': 'nfo2',
        }
        create_test_file_structure(structure)

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        result = operator.check_video_files(temp_dir)

        assert result['total_videos'] == 2
        assert len(result['no_nfo_videos']) == 0
        assert len(result['found_nfo_videos']) == 2

    def test_check_video_files_some_missing_nfo(self, temp_dir, create_test_file_structure):
        """测试部分视频缺少 NFO"""
        from media_server.client import MediaServerClient

        structure = {
            'movies/Movie1.2023.mp4': 'video1',
            'movies/Movie1.2023.nfo': 'nfo1',
            'movies/Movie2.2022.mkv': 'video2',
            # Movie2 没有 NFO
        }
        create_test_file_structure(structure)

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        result = operator.check_video_files(temp_dir)

        assert result['total_videos'] == 2
        assert len(result['no_nfo_videos']) == 1
        assert len(result['found_nfo_videos']) == 1


class TestMediaServerClientForceExtractTmdbid:
    """测试 force_extract_tmdbid_from_file 方法"""

    def test_force_extract_valid(self, temp_dir):
        """测试强制提取有效的 tmdbid"""
        from media_server.client import MediaServerClient

        content = """  <tmdbid>12345</tmdbid>
  <title>Test</title>
"""
        file_path = os.path.join(temp_dir, 'test.txt')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        result = operator.force_extract_tmdbid_from_file(file_path)

        assert result == '12345'

    def test_force_extract_not_found(self, temp_dir):
        """测试强制提取未找到 tmdbid"""
        from media_server.client import MediaServerClient

        content = """  <title>Test</title>
"""
        file_path = os.path.join(temp_dir, 'test.txt')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        result = operator.force_extract_tmdbid_from_file(file_path)

        assert result is None


class TestMediaServerClientNfoParsing:
    """测试 NFO 文件解析"""

    def test_extract_tmdb_id_from_nfo(self, temp_dir, sample_nfo_content):
        """测试从 NFO 提取 TMDB ID"""
        # 创建 NFO 文件
        nfo_path = os.path.join(temp_dir, 'movie.nfo')
        with open(nfo_path, 'w', encoding='utf-8') as f:
            f.write(sample_nfo_content)

        # 解析 NFO
        tree = ET.parse(nfo_path)
        root = tree.getroot()

        # 验证 TMDB ID
        uniqueid = root.find('uniqueid[@type="tmdb"]')
        assert uniqueid is not None
        assert uniqueid.text == '12345'

    def test_extract_genres_from_nfo(self, temp_dir, sample_nfo_content):
        """测试从 NFO 提取流派"""
        # 创建 NFO 文件
        nfo_path = os.path.join(temp_dir, 'movie.nfo')
        with open(nfo_path, 'w', encoding='utf-8') as f:
            f.write(sample_nfo_content)

        # 解析 NFO
        tree = ET.parse(nfo_path)
        root = tree.getroot()

        # 验证流派
        genres = root.findall('genre')
        assert len(genres) == 2
        genre_texts = [g.text for g in genres]
        assert 'Action' in genre_texts
        assert 'Adventure' in genre_texts


class TestMediaServerClientClearFiles:
    """测试 clear_files_by_type 方法"""

    def test_clear_video_files(self, temp_dir, create_test_file_structure):
        """测试清除视频文件"""
        from media_server.client import MediaServerClient

        structure = {
            'movies/movie1.mp4': 'video1',
            'movies/movie1.nfo': 'nfo1',
            'movies/movie2.mkv': 'video2',
            'movies/poster.jpg': 'poster',
        }
        create_test_file_structure(structure)

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        messages = []

        def callback(msg):
            messages.append(msg)

        operator.clear_files_by_type(temp_dir, 'VIDEO', callback)

        # 等待线程完成
        time.sleep(0.5)

        # 验证视频文件被删除
        assert not os.path.exists(os.path.join(temp_dir, 'movies', 'movie1.mp4'))
        assert not os.path.exists(os.path.join(temp_dir, 'movies', 'movie2.mkv'))

        # 验证其他文件未被删除
        assert os.path.exists(os.path.join(temp_dir, 'movies', 'movie1.nfo'))
        assert os.path.exists(os.path.join(temp_dir, 'movies', 'poster.jpg'))


class TestMediaServerClientCallback:
    """测试回调功能"""

    def test_check_duplicates_callback(self, temp_dir, sample_nfo_content):
        """测试 check_duplicates 回调"""
        from media_server.client import MediaServerClient

        # 创建 NFO 文件
        nfo_content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
    <title>Test Movie</title>
    <tmdbid>12345</tmdbid>
</movie>"""
        nfo_path = os.path.join(temp_dir, 'movie.nfo')
        with open(nfo_path, 'w', encoding='utf-8') as f:
            f.write(nfo_content)

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        messages = []

        def callback(msg):
            messages.append(msg)

        # 模拟 get_all_media 返回包含该影片的数据（有重复）
        mock_movies = [{'Name': 'Test Movie', 'ProviderIds': {'Tmdb': '12345'}, 'Path': '/path/to/movie'}]
        with patch.object(operator, 'get_all_media', return_value=mock_movies):
            operator.check_duplicates(temp_dir, callback)
            time.sleep(0.5)

        # 验证回调被调用
        assert len(messages) > 0


class TestMediaServerClientGenresMap:
    """测试流派翻译映射"""

    def test_genres_map_exists_in_methods(self):
        """测试流派翻译映射在方法中存在"""
        from media_server.client import MediaServerClient

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')

        # 验证流派翻译方法存在
        assert hasattr(operator, 'emby_tv_translate_genres_and_update_whole_item')
        assert hasattr(operator, 'emby_movie_translate_genres_and_update_whole_item')

    def test_common_genres_translation(self):
        """测试常见流派的翻译映射逻辑"""
        from media_server.genre_maps import MOVIE_GENRE_TRANSLATIONS, TV_GENRE_TRANSLATIONS

        # 验证映射不为空且包含常见流派
        assert len(TV_GENRE_TRANSLATIONS) > 0
        assert len(MOVIE_GENRE_TRANSLATIONS) > 0
        assert TV_GENRE_TRANSLATIONS['Action'] == '动作'
        assert TV_GENRE_TRANSLATIONS['Drama'] == '剧情'
        assert TV_GENRE_TRANSLATIONS['Comedy'] == '喜剧'
        assert MOVIE_GENRE_TRANSLATIONS['Action'] == '动作'
        assert MOVIE_GENRE_TRANSLATIONS['Comedy'] == '喜剧'

    def test_movie_genres_keep_duplicate_key_effective_values(self):
        """测试抽离后保留旧字典重复键的最终生效值"""
        from media_server.genre_maps import MOVIE_GENRE_TRANSLATIONS

        assert MOVIE_GENRE_TRANSLATIONS['エロス'] == '情色'
        assert MOVIE_GENRE_TRANSLATIONS['セクシー'] == '性感'
        assert MOVIE_GENRE_TRANSLATIONS['逆レイプ'] == '逆强奸'

    def test_reviewed_av_genre_suggestions_are_applied_to_movie_map(self):
        """测试 2026-07-14 审核版 AV 流派表已同步到电影流派映射"""
        import csv
        from pathlib import Path

        from media_server.client import MediaServerClient
        from media_server.genre_maps import MOVIE_GENRE_TRANSLATIONS

        operator = MediaServerClient(server_url='http://localhost:8096', api_key='test-api-key')
        review_path = (
            Path(__file__).resolve().parents[3]
            / 'av_genre_translation_suggestions_2026-07-14.csv'
        )

        with review_path.open(encoding='utf-8-sig', newline='') as review_file:
            for row in csv.DictReader(review_file):
                source = row['原始流派名称'].strip()
                expected = row['建议合并后简体流派名称'].strip()

                assert operator._resolve_genre_translation(source, MOVIE_GENRE_TRANSLATIONS) == expected
