"""Exercise real HTTP serialization against snapshots of both official OpenAPI specs.

The HTTP server is a test double, not a running Jellyfin installation.
"""

import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import pytest

from media_server.client import MediaServerClient

pytestmark = pytest.mark.integration

USER_ID = UUID(int=1).hex
MOVIE_LIBRARY = UUID(int=2).hex
TV_LIBRARY = UUID(int=3).hex


@pytest.fixture(params=['10.11.11', '12.0'])
def jellyfin_contract_server(request):
    path = Path(__file__).parents[1] / 'fixtures' / 'jellyfin' / f'{request.param}.json'
    contract = json.loads(path.read_text())
    items = {}
    for number, item_type in [(10, 'Movie'), (11, 'Movie'), (12, 'Series')]:
        item_id = UUID(int=number).hex
        items[item_id] = {
            'Id': item_id,
            'Name': f'Test {number}',
            'Type': item_type,
            'Path': f'/media/Test {number}.mkv',
            'ProviderIds': {'Tmdb': '123'},
            'MediaSourceCount': 1,
            'Genres': ['Action'],
            'ProductionLocations': ['Japan'],
            'GenreItems': [{'Id': UUID(int=20).hex, 'Name': 'Action'}],
            'Overview': 'Keep this overview',
            'Tags': ['Keep this tag'],
            'LockedFields': ['Name'],
        }
        if 'OriginalLanguage' in contract['item_properties']:
            items[item_id]['OriginalLanguage'] = 'ja'
    state = SimpleNamespace(contract=contract, items=items, errors=[], requests=[], merges=[], hidden=set())

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            self.handle_api_request()

        def do_POST(self):
            self.handle_api_request()

        def handle_api_request(self):
            try:
                status, payload = self.dispatch()
            except Exception as exc:
                state.errors.append(str(exc))
                status, payload = 400, {'Error': str(exc)}
            raw = json.dumps(payload).encode() if status != 204 else b''
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def dispatch(self):
            url = urlsplit(self.path)
            assert url.path.startswith('/jellyfin/'), 'Reverse proxy base path was lost'
            route = url.path[len('/jellyfin') :]
            query = {key.lower(): values[0] for key, values in parse_qs(url.query).items()}
            operation_path = '/Items/{itemId}' if route.startswith('/Items/') else route
            operation = contract['operations'][f'{self.command} {operation_path}']
            assert not operation['deprecated']
            assert set(query) <= {name.lower() for name in operation['query']}
            state.requests.append((self.command, route, query))
            if route == '/System/Info/Public':
                return 200, {'Id': UUID(int=99).hex, 'ProductName': 'Jellyfin Server', 'Version': contract['server_version']}

            assert self.headers[contract['security']['name']] == 'MediaBrowser Token="contract-test-key"'
            assert 'X-Emby-Token' not in self.headers
            assert 'X-MediaBrowser-Token' not in self.headers
            assert 'api_key' not in query and 'apikey' not in query

            if route == '/Users':
                return 200, [{'Name': 'Admin', 'Id': USER_ID}]
            if route == '/UserViews':
                assert query['userid'] == USER_ID
                return 200, {
                    'Items': [
                        {'Id': MOVIE_LIBRARY, 'Name': 'Movies', 'CollectionType': 'movies'},
                        {'Id': TV_LIBRARY, 'Name': 'TV', 'CollectionType': 'tvshows'},
                        {'Id': UUID(int=4).hex, 'Name': 'Music', 'CollectionType': 'music'},
                    ]
                }
            if route == '/Items':
                assert query['recursive'].lower() == 'true'
                assert 'mindatelastsaved' not in query
                assert set(query['fields'].split(',')) <= set(contract['item_fields'])
                assert query['sortby'] in contract['item_sort_by']
                selected = [item for item in items.values() if item['Type'] in query['includeitemtypes'].split(',')]
                selected = [item for item in selected if item['Id'] not in state.hidden]
                if 'parentid' in query:
                    assert query['userid'] == USER_ID
                    expected_type = {MOVIE_LIBRARY: 'Movie', TV_LIBRARY: 'Series'}[query['parentid']]
                    selected = [item for item in selected if item['Type'] == expected_type]
                start = int(query['startindex'])
                # Deliberately return less than Limit to exercise TotalRecordCount.
                return 200, {'Items': selected[start : start + 1], 'TotalRecordCount': len(selected)}
            if operation_path == '/Items/{itemId}':
                item_id = route.rsplit('/', 1)[1]
                UUID(item_id)
                if self.command == 'GET':
                    assert query['userid'] == USER_ID
                    return 200, items[item_id]
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                assert set(payload) <= set(contract['item_properties'])
                assert 'GenreItems' not in payload
                for key, value in items[item_id].items():
                    if key not in {'Genres', 'ProductionLocations', 'GenreItems', 'LockedFields'}:
                        assert payload[key] == value, f'Metadata field lost: {key}'
                changed = {
                    key for key in ('Genres', 'ProductionLocations')
                    if payload[key] != items[item_id][key]
                }
                assert set(items[item_id]['LockedFields']).issubset(payload['LockedFields'])
                assert changed.issubset(payload['LockedFields'])
                assert set(payload['LockedFields']) - set(items[item_id]['LockedFields']) <= {'Genres', 'ProductionLocations'}
                items[item_id].update(payload)
                assert 204 in operation['success']
                return 204, None
            if route == '/Videos/MergeVersions':
                ids = query['ids'].split(',')
                assert len(ids) >= 2 and all(items[item_id]['Type'] == 'Movie' for item_id in ids)
                state.merges.append(ids)
                assert 204 in operation['success']
                return 204, None
            raise AssertionError(f'Unexpected route {route}')

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state.client = MediaServerClient(
        server_url=f'http://127.0.0.1:{server.server_port}/jellyfin/',
        api_key='contract-test-key',
        username='admin',
        server_type='jellyfin',
    )
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not state.errors, '\n'.join(state.errors)


def test_duplicate_lookup_and_version_merge_contract(jellyfin_contract_server):
    state = jellyfin_contract_server
    client = state.client
    assert client.validate_server_type()
    assert client.server_version == state.contract['server_version']
    assert len(client.get_all_media()) == 3
    movies = client.get_movie_media()
    assert len(movies) == 2
    assert client.query_movies_by_tmdbid(movies, '123') is True
    groups = client.group_movies_by_tmdbid(movies)
    assert len(client.merge_movie_versions(groups)) == 1
    assert state.merges == [[movie['Id'] for movie in movies]]
    assert any(query.get('startindex') == '1' for _, _, query in state.requests)
    assert not state.errors


@pytest.mark.parametrize(
    'operation, field, expected',
    [
        ('update_genres', 'Genres', ['动作']),
        ('update_countries', 'ProductionLocations', ['日本']),
    ],
)
def test_metadata_workflow_contract(jellyfin_contract_server, operation, field, expected):
    state = jellyfin_contract_server
    original = copy.deepcopy(state.items)
    task = getattr(state.client, operation)()
    task.join(timeout=10)
    assert not task.is_alive()
    assert not state.errors
    assert not state.client._metadata_had_errors
    for item_id, item in state.items.items():
        assert item[field] == expected
        assert set(item['LockedFields']) == set(original[item_id]['LockedFields']) | {field}
        for key in original[item_id]:
            if key not in {field, 'LockedFields'}:
                assert item[key] == original[item_id][key]
    reads = [query for method, route, query in state.requests if method == 'GET' and route == '/Items']
    assert {query['parentid'] for query in reads} == {MOVIE_LIBRARY, TV_LIBRARY}
    assert all(query['userid'] == USER_ID for query in reads)


def test_sequential_curation_preserves_locks_and_merge_preserves_member_values(jellyfin_contract_server):
    state = jellyfin_contract_server
    state.items[UUID(int=11).hex]['Genres'] = ['Comedy']
    for operation in ['update_genres', 'update_countries']:
        task = getattr(state.client, operation)()
        task.join(timeout=10)
        assert not task.is_alive()
        assert not state.client._metadata_had_errors
    for value in state.items.values():
        assert set(value['LockedFields']) == {'Name', 'Genres', 'ProductionLocations'}
    before_merge = copy.deepcopy(state.items)
    movies = state.client.get_movie_media()
    assert len(state.client.merge_movie_versions(state.client.group_movies_by_tmdbid(movies))) == 1
    assert state.items == before_merge
    assert state.items[UUID(int=10).hex]['Genres'] != state.items[UUID(int=11).hex]['Genres']
    posts_before = sum(method == 'POST' for method, _, _ in state.requests)
    for operation in ['update_genres', 'update_countries']:
        task = getattr(state.client, operation)()
        task.join(timeout=10)
        assert not task.is_alive()
    assert sum(method == 'POST' for method, _, _ in state.requests) == posts_before


@pytest.mark.parametrize(
    'operation,field,localized',
    [('update_genres', 'Genres', ['动作']), ('update_countries', 'ProductionLocations', ['日本'])],
)
@pytest.mark.parametrize('empty_cleanup', [False, True])
def test_only_actual_curation_adds_protection(jellyfin_contract_server, operation, field, localized, empty_cleanup):
    state = jellyfin_contract_server
    target = state.items[UUID(int=10).hex]
    target[field] = [' '] if empty_cleanup else localized
    task = getattr(state.client, operation)()
    task.join(timeout=10)
    assert not task.is_alive()
    assert not state.client._metadata_had_errors
    assert target[field] == ([] if empty_cleanup else localized)
    assert set(target['LockedFields']) == ({'Name', field} if empty_cleanup else {'Name'})


def test_hidden_versions_translation_and_historical_protection(jellyfin_contract_server, tmp_path):
    from media_server.metadata_protection import apply_plan, create_plan

    state = jellyfin_contract_server
    primary, alternate = UUID(int=10).hex, UUID(int=11).hex
    for identifier in (primary, alternate):
        state.items[identifier]['MediaSourceCount'] = 2
        state.items[identifier]['MediaSources'] = [{'Id': primary}, {'Id': alternate}]
    state.hidden.add(alternate)
    state.items[primary]['Genres'] = ['动作']
    state.items[alternate]['Genres'] = ['Comedy']
    task = state.client.update_genres()
    task.join(timeout=10)
    assert not task.is_alive()
    assert not state.client._metadata_had_errors
    assert state.items[primary]['Genres'] == ['动作']
    assert state.items[primary]['LockedFields'] == ['Name']
    assert state.items[alternate]['Genres'] == ['喜剧']
    assert set(state.items[alternate]['LockedFields']) == {'Name', 'Genres'}
    before = copy.deepcopy(state.items)
    posts = sum(method == 'POST' for method, _, _ in state.requests)
    plan, report = tmp_path / 'plan.json', tmp_path / 'report.json'
    preview = create_plan(state.client, plan, ['Genres', 'ProductionLocations'], libraries=[MOVIE_LIBRARY])
    assert {row['id'] for row in preview['items']} == {primary, alternate}
    assert sum(method == 'POST' for method, _, _ in state.requests) == posts
    assert apply_plan(state.client, plan, report)['summary']['confirmed'] == 2
    for identifier in (primary, alternate):
        for field in ('Genres', 'ProductionLocations', 'MediaSources'):
            assert state.items[identifier][field] == before[identifier][field]
        assert set(state.items[identifier]['LockedFields']) == {'Name', 'Genres', 'ProductionLocations'}
    assert state.items[UUID(int=12).hex] == before[UUID(int=12).hex]
