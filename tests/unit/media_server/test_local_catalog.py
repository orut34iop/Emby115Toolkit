"""Real SQLite snapshots: version closure, scope, freshness and read-only access."""

import json
import sqlite3
import threading
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from media_server.local_catalog import ITEM_TYPES, CatalogUnavailable, LocalCatalog, db_guid


def uid(number):
    return UUID(int=number).hex


@pytest.fixture
def catalog(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    database = data / 'jellyfin.db'
    device = data / 'device.txt'
    device.write_text('\ufeff' + uid(900))
    with sqlite3.connect(database) as db:
        db.executescript("""
            CREATE TABLE BaseItems (
                Id TEXT PRIMARY KEY, Name TEXT, Path TEXT, Type TEXT, TopParentId TEXT,
                PrimaryVersionId TEXT, OwnerId TEXT, ExtraType INTEGER, Genres TEXT,
                ProductionLocations TEXT, PresentationUniqueKey TEXT, Data TEXT,
                SortName TEXT, IsFolder INTEGER);
            CREATE TABLE BaseItemProviders (ItemId TEXT, ProviderId TEXT, ProviderValue TEXT);
            CREATE TABLE BaseItemMetadataFields (Id INTEGER, ItemId TEXT);
        """)
        for root in (100, 200):
            db.execute(
                'INSERT INTO BaseItems(Id,Path,TopParentId,IsFolder) VALUES(?,?,?,1)',
                (db_guid(uid(root)), f'/library/{root}', db_guid(uid(root))),
            )
        for number, root, primary in [(1, 100, None), (2, 100, 1), (3, 200, None), (4, 100, None)]:
            db.execute(
                """INSERT INTO BaseItems
                   (Id,Name,Path,Type,TopParentId,PrimaryVersionId,Genres,ProductionLocations,
                    PresentationUniqueKey,Data,SortName,IsFolder)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,0)""",
                (db_guid(uid(number)), f'Movie {number}', f'/library/{root}/{number}.mkv',
                 ITEM_TYPES['Movie'], db_guid(uid(root)), db_guid(uid(primary)) if primary else None,
                 'Action|Drama', 'United States', str(number), '{}', str(number)),
            )
            db.execute('INSERT INTO BaseItemProviders VALUES(?,?,?)', (db_guid(uid(number)), 'Tmdb', '10'))
        db.execute(
            'UPDATE BaseItems SET Data=? WHERE Id=?',
            (json.dumps({'LinkedAlternateVersions': [{'ItemId': uid(2)}],
                         'LocalAlternateVersions': ['/library/100/2.mkv']}), db_guid(uid(1))),
        )
    result = LocalCatalog(database, device, uid(900),
                          [{'ItemId': uid(10), 'Locations': ['/library/100']}], threading.Event())
    yield result
    result.close()


def change(catalog, sql, params=()):
    with sqlite3.connect(catalog.database) as db:
        db.execute(sql, params)


def snapshot(catalog, expand=True):
    return catalog.snapshot([{'Id': uid(10)}, {'Id': uid(11)}], 'Movie', expand)


def test_snapshot_covers_only_mapped_views_and_expands_hidden_members(catalog):
    items, covered = snapshot(catalog)
    assert {item['Id'] for item in items} == {uid(1), uid(2), uid(4)}
    assert covered == {uid(10)}
    visible, _ = snapshot(catalog, False)
    assert [item['Id'] for item in visible] == [uid(1), uid(4)]
    assert [item['MediaSourceCount'] for item in visible] == [2, 1]
    assert visible[0]['ProviderIds'] == {'Tmdb': '10'}
    assert items[0]['Genres'] == ['Action', 'Drama']
    assert items[0]['ProductionLocations'] == ['United States']
    with catalog.read() as db:
        with pytest.raises(sqlite3.OperationalError, match='readonly'):
            db.execute('DELETE FROM BaseItems')


def test_visible_linked_version_is_followed_even_without_primary_pointer(catalog):
    change(catalog, 'UPDATE BaseItems SET PrimaryVersionId=NULL WHERE Id=?', (db_guid(uid(2)),))
    visible, _ = snapshot(catalog, False)
    assert len(visible) == 3
    assert visible[0]['MediaSourceCount'] == 2
    assert len(snapshot(catalog)[0]) == 3


@pytest.mark.parametrize('corruption', ['missing_link', 'missing_local', 'cycle', 'missing_primary', 'presentation'])
def test_incomplete_graph_never_yields_partial_snapshot(catalog, corruption):
    if corruption == 'missing_link':
        change(catalog, 'UPDATE BaseItems SET Data=? WHERE Id=?',
               (json.dumps({'LinkedAlternateVersions': [{'ItemId': uid(99)}]}), db_guid(uid(1))))
    elif corruption == 'missing_local':
        change(catalog, 'UPDATE BaseItems SET Data=? WHERE Id=?',
               (json.dumps({'LocalAlternateVersions': ['/missing']}), db_guid(uid(1))))
    elif corruption == 'cycle':
        change(catalog, 'UPDATE BaseItems SET PrimaryVersionId=? WHERE Id=?', (db_guid(uid(2)), db_guid(uid(1))))
    elif corruption == 'missing_primary':
        change(catalog, 'UPDATE BaseItems SET PrimaryVersionId=? WHERE Id=?', (db_guid(uid(99)), db_guid(uid(2))))
    else:
        change(catalog, 'UPDATE BaseItems SET PresentationUniqueKey=? WHERE Id=?', ('1', db_guid(uid(4))))
    with pytest.raises(CatalogUnavailable):
        snapshot(catalog)


def test_verify_reads_new_committed_values_and_all_existing_locks(catalog):
    expected = {'Genres': ['动作'], 'LockedFields': ['Genres', 'Overview']}
    assert not catalog.verify(uid(1), expected, ('Genres',))
    change(catalog, 'UPDATE BaseItems SET Genres=? WHERE Id=?', ('动作', db_guid(uid(1))))
    change(catalog, 'INSERT INTO BaseItemMetadataFields VALUES(?,?)', (1, db_guid(uid(1))))
    assert not catalog.verify(uid(1), expected, ('Genres',))
    change(catalog, 'INSERT INTO BaseItemMetadataFields VALUES(?,?)', (6, db_guid(uid(1))))
    assert catalog.verify(uid(1), expected, ('Genres',))
    # A stop prevents new work, but must still confirm a write already sent.
    catalog.stop_flag.set()
    assert catalog.verify(uid(1), expected, ('Genres',))
    change(catalog, 'UPDATE BaseItems SET Genres=? WHERE Id=?', ('Drama', db_guid(uid(1))))
    assert not catalog.verify(uid(1), expected, ('Genres',))


@pytest.mark.parametrize('reason', ['device', 'database', 'stop'])
def test_reader_rejects_server_replacement_and_cancel(catalog, reason):
    snapshot(catalog)
    if reason == 'device':
        catalog.device_file.write_text(uid(901))
    elif reason == 'database':
        catalog.database.rename(catalog.database.with_suffix('.old'))
        catalog.database.touch()
    else:
        catalog.stop_flag.set()
    with pytest.raises((CatalogUnavailable, InterruptedError)):
        snapshot(catalog)


def test_merge_revalidates_identity_and_new_version_members(catalog):
    items, _ = snapshot(catalog, False)
    assert catalog.merge_is_current(items)
    change(catalog, 'UPDATE BaseItemProviders SET ProviderValue=? WHERE ItemId=?', ('20', db_guid(uid(4))))
    assert not catalog.merge_is_current(items)
    change(catalog, 'UPDATE BaseItemProviders SET ProviderValue=? WHERE ItemId=?', ('10', db_guid(uid(4))))
    change(catalog, 'UPDATE BaseItems SET PrimaryVersionId=? WHERE Id=?', (db_guid(uid(4)), db_guid(uid(3))))
    assert not catalog.merge_is_current(items)


def discovery_client(catalog, **policy):
    user_policy = dict(IsAdministrator=True, EnableAllFolders=True)
    user_policy.update(policy)
    payloads = {
        '/System/Info': {'Id': uid(900), 'Version': '12.0', 'ProgramDataPath': str(catalog.database.parent.parent)},
        '/Users/' + uid(800): {'Id': uid(800), 'Policy': user_policy},
        '/Library/VirtualFolders': catalog.libraries,
    }
    def request(method, path, **kwargs):
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payloads[path])
    return SimpleNamespace(server_type='jellyfin', server_version='12.0', server_url='http://localhost:8096',
                           user_id=uid(800), stop_flag=threading.Event(), _request=Mock(side_effect=request))


def test_discovery_bom_identity_and_unrestricted_admin(catalog):
    found = LocalCatalog.discover(discovery_client(catalog))
    assert found.server_id == uid(900)
    found.close()


@pytest.mark.parametrize('policy', [
    {'IsAdministrator': False}, {'EnableAllFolders': False}, {'BlockedTags': ['private']},
    {'AllowedTags': ['public']}, {'MaxParentalRating': 12}, {'MaxParentalRating': 0},
    {'BlockUnratedItems': ['Movie']},
])
def test_restricted_users_use_api(catalog, policy):
    with pytest.raises(CatalogUnavailable):
        LocalCatalog.discover(discovery_client(catalog, **policy))


@pytest.mark.parametrize('attribute,value', [
    ('server_url', 'http://remote:8096'), ('server_url', 'http://localhost:8096/proxy'),
    ('server_version', '10.11.11'), ('server_type', 'emby'),
])
def test_unsupported_servers_do_not_probe_local_files(catalog, attribute, value):
    client = discovery_client(catalog)
    setattr(client, attribute, value)
    assert LocalCatalog.discover(client) is None
    client._request.assert_not_called()
