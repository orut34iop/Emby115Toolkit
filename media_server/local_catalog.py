"""Read-only acceleration for a verified, local Jellyfin 12 database.

The database is never used to write metadata. Unknown layouts, restricted users,
unmapped views and incomplete version relationships retain the HTTP fallback.
"""

import json
import sqlite3
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

LOCK_NAMES = ('Cast', 'Genres', 'ProductionLocations', 'Studios', 'Tags',
              'Name', 'Overview', 'Runtime', 'OfficialRating')
ITEM_TYPES = {'Movie': 'MediaBrowser.Controller.Entities.Movies.Movie',
              'Series': 'MediaBrowser.Controller.Entities.TV.Series'}


class CatalogUnavailable(ValueError):
    """The local catalog cannot establish a complete, compatible snapshot."""


def guid(value):
    return UUID(str(value)).hex


def db_guid(value):
    return str(UUID(str(value))).upper()


def values(value):
    if value is None or value == '':
        return []
    if not isinstance(value, str):
        raise CatalogUnavailable('字段格式不兼容')
    return value.split('|')


class LocalCatalog:
    def __init__(self, database, device_file, server_id, libraries, stop_flag):
        self.database = Path(database)
        self.device_file = Path(device_file)
        self.server_id = guid(server_id)
        self.libraries = libraries
        self.stop_flag = stop_flag
        stat = self.database.stat()
        self.identity = (stat.st_dev, stat.st_ino)
        self._local = threading.local()
        self._connections = []
        self._lock = threading.Lock()

    @classmethod
    def discover(cls, client):
        url = urlsplit(client.server_url)
        if (client.server_type != 'jellyfin' or not str(client.server_version or '').startswith('12.')
                or url.hostname not in ('127.0.0.1', '::1', 'localhost')
                or url.path not in ('', '/') or not client.user_id):
            return None

        def get(path):
            response = client._request('get', path, timeout=(3, 10))
            response.raise_for_status()
            return response.json()

        info = get('/System/Info')
        if not str(info.get('Version', '')).startswith('12.') or not info.get('ProgramDataPath'):
            raise CatalogUnavailable('服务端没有提供可验证的数据目录')
        root = Path(info['ProgramDataPath'])
        if not root.is_absolute():
            raise CatalogUnavailable('数据目录不是绝对路径')
        device = root / 'data' / 'device.txt'
        if guid(device.read_text(encoding='utf-8-sig').strip()) != guid(info.get('Id')):
            raise CatalogUnavailable('本机数据库与当前服务器身份不一致')
        user = get('/Users/' + client.user_id)
        policy = user.get('Policy', {})
        if (guid(user.get('Id')) != guid(client.user_id)
                or policy.get('IsAdministrator') is not True
                or policy.get('EnableAllFolders') is not True
                or policy.get('IsDisabled', False)
                or any(policy.get(key) is not None for key in ('MaxParentalRating', 'MaxParentalSubRating'))
                or any(policy.get(key) for key in (
                    'BlockedTags', 'AllowedTags', 'BlockedMediaFolders', 'AccessSchedules',
                    'BlockUnratedItems',
                ))):
            raise CatalogUnavailable('当前用户需要逐项访问控制，使用 API')
        libraries = get('/Library/VirtualFolders')
        if not isinstance(libraries, list):
            raise CatalogUnavailable('媒体库映射格式无效')
        return cls(root / 'data' / 'jellyfin.db', device, info['Id'], libraries, client.stop_flag)

    def close(self):
        with self._lock:
            for connection in self._connections:
                connection.close()
            self._connections.clear()
        self._local = threading.local()

    @contextmanager
    def read(self):
        if self.stop_flag.is_set():
            raise InterruptedError('已停止本机快照读取')
        stat = self.database.stat()
        if ((stat.st_dev, stat.st_ino) != self.identity
                or guid(self.device_file.read_text(encoding='utf-8-sig').strip()) != self.server_id):
            raise CatalogUnavailable('本机服务器或数据库已替换')
        connection = getattr(self._local, 'connection', None)
        if connection is None:
            connection = sqlite3.connect(self.database.as_uri() + '?mode=ro', uri=True, timeout=1,
                                         check_same_thread=False, isolation_level=None)
            connection.execute('PRAGMA query_only=ON')
            connection.row_factory = sqlite3.Row
            self._local.connection = connection
            with self._lock:
                self._connections.append(connection)
        start = time.monotonic()
        connection.set_progress_handler(
            lambda: int(self.stop_flag.is_set() or time.monotonic() - start > 20), 10000,
        )
        connection.execute('BEGIN')
        try:
            yield connection
        finally:
            connection.execute('ROLLBACK')

    def snapshot(self, views, kind, expand_members):
        if kind not in ITEM_TYPES:
            raise CatalogUnavailable('条目类型不支持本机快照')
        libraries = {guid(v['ItemId']): v for v in self.libraries if v.get('ItemId')}
        covered, roots = set(), set()
        with self.read() as db:
            for view in views:
                library = libraries.get(guid(view['Id']))
                if library is None or not library.get('Locations'):
                    continue
                found_roots = set()
                for location in library['Locations']:
                    found = db.execute(
                        'SELECT Id FROM BaseItems WHERE Path=? AND IsFolder=1 AND Id=TopParentId',
                        (location,),
                    ).fetchall()
                    if len(found) != 1:
                        raise CatalogUnavailable('媒体库路径不能唯一映射到数据库根目录')
                    found_roots.add(guid(found[0]['Id']))
                roots.update(found_roots)
                covered.add(guid(view['Id']))
            if not covered:
                return [], covered
            rows = db.execute(
                """SELECT Id, Name, Path, TopParentId, PrimaryVersionId, OwnerId, ExtraType,
                          Genres, ProductionLocations, PresentationUniqueKey,
                          json_extract(Data, '$.LocalAlternateVersions') AS LocalVersions,
                          json_extract(Data, '$.LinkedAlternateVersions') AS LinkedVersions
                   FROM BaseItems WHERE Type=? ORDER BY SortName, Id""", (ITEM_TYPES[kind],),
            ).fetchall()
            by_id = {guid(row['Id']): row for row in rows}
            by_path = defaultdict(list)
            for identifier, row in by_id.items():
                by_path[row['Path']].append(identifier)
            primary = {}

            def root_for(identifier):
                chain, seen = [], set()
                while identifier not in primary:
                    if identifier in seen or identifier not in by_id:
                        raise CatalogUnavailable('版本关系存在循环或缺失成员')
                    seen.add(identifier)
                    chain.append(identifier)
                    parent = by_id[identifier]['PrimaryVersionId']
                    if not parent:
                        primary[identifier] = identifier
                        break
                    identifier = guid(parent)
                result = primary[identifier]
                for member in chain:
                    primary[member] = result
                return result

            groups = defaultdict(list)
            for identifier in by_id:
                groups[root_for(identifier)].append(identifier)
            seeds = []
            presentation_keys = set()
            for identifier, row in by_id.items():
                if (row['PrimaryVersionId'] or not row['TopParentId'] or guid(row['TopParentId']) not in roots
                        or (row['OwnerId'] and row['ExtraType'] is None)):
                    continue
                key = row['PresentationUniqueKey']
                # Ambiguous presentation grouping must use the server's selection rules.
                if key and key in presentation_keys:
                    raise CatalogUnavailable('媒体库含额外的展示分组，使用服务器列表')
                if key:
                    presentation_keys.add(key)
                seeds.append(identifier)
            selected, source_counts = set(), {}
            for identifier in seeds:
                group, pending = set(), list(groups[identifier])
                # Linked versions can remain visible after a partial historical merge.
                # Follow advertised relationships, not just PrimaryVersionId.
                while pending:
                    member = pending.pop()
                    if member in group:
                        continue
                    group.add(member)
                    row = by_id[member]
                    linked = []
                    for path in json.loads(row['LocalVersions'] or '[]'):
                        matches = by_path[path]
                        if len(matches) != 1:
                            raise CatalogUnavailable('本地版本路径缺少完整成员')
                        linked.append(matches[0])
                    for link in json.loads(row['LinkedVersions'] or '[]'):
                        target = guid(link['ItemId'])
                        if target not in by_id:
                            raise CatalogUnavailable('链接版本缺少完整成员')
                        linked.append(target)
                    for target in linked:
                        pending.extend(m for m in groups[primary[target]] if m not in group)
                source_counts[identifier] = len(group)
                selected.update(group if expand_members else [identifier])
            providers = defaultdict(dict)
            if not expand_members:
                for row in db.execute(
                    """SELECT p.ItemId, p.ProviderId, p.ProviderValue FROM BaseItemProviders p
                       JOIN BaseItems b ON b.Id=p.ItemId WHERE b.Type=?""", (ITEM_TYPES[kind],),
                ):
                    identifier = guid(row['ItemId'])
                    if identifier in selected:
                        providers[identifier][row['ProviderId']] = row['ProviderValue']
            result = []
            for identifier, row in by_id.items():
                if identifier not in selected:
                    continue
                result.append({
                    'Id': identifier, 'Name': row['Name'], 'Path': row['Path'], 'Type': kind,
                    'Genres': values(row['Genres']), 'ProductionLocations': values(row['ProductionLocations']),
                    'ProviderIds': providers.get(identifier, {}),
                    'MediaSourceCount': source_counts.get(identifier, len(groups[primary[identifier]])),
                    '_local_snapshot': True,
                })
            return result, covered

    def verify(self, identifier, expected, fields):
        """Fresh committed values and existing locks, without constructing a playback DTO."""
        with self.read() as db:
            row = db.execute(
                'SELECT Genres, ProductionLocations FROM BaseItems WHERE Id=?', (db_guid(identifier),),
            ).fetchone()
            if row is None:
                return False
            locks = [r[0] for r in db.execute(
                'SELECT Id FROM BaseItemMetadataFields WHERE ItemId=?', (db_guid(identifier),),
            )]
            if any(type(lock) is not int or lock < 0 or lock >= len(LOCK_NAMES) for lock in locks):
                raise CatalogUnavailable('字段锁枚举不兼容')
            return (set(expected['LockedFields']).issubset({LOCK_NAMES[lock] for lock in locks})
                    and all(values(row[field]) == expected[field] for field in fields))

    def merge_is_current(self, movies):
        """Reject stale snapshot identities before asking the server to merge."""
        with self.read() as db:
            for movie in movies:
                if not movie.get('_local_snapshot'):
                    continue
                identifier = db_guid(movie['Id'])
                row = db.execute(
                    """SELECT Path, Type, PrimaryVersionId,
                              json_array_length(json_extract(Data, '$.LinkedAlternateVersions')),
                              json_array_length(json_extract(Data, '$.LocalAlternateVersions'))
                       FROM BaseItems WHERE Id=?""", (identifier,),
                ).fetchone()
                if (row is None or row[0] != movie['Path'] or row[1] != ITEM_TYPES['Movie'] or row[2]):
                    return False
                providers = dict(db.execute(
                    'SELECT ProviderId, ProviderValue FROM BaseItemProviders WHERE ItemId=?', (identifier,),
                ))
                if providers != movie['ProviderIds']:
                    return False
                if movie['MediaSourceCount'] <= 1 and (
                    row[3] or row[4] or db.execute(
                        'SELECT 1 FROM BaseItems WHERE PrimaryVersionId=? LIMIT 1', (identifier,),
                    ).fetchone()
                ):
                    return False
            return True
