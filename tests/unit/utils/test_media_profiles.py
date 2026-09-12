"""Profile identity, migration, persistence and concurrent task attribution."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest
import yaml

from utils.config import Config
from utils.media_profiles import get_media_profiles


@pytest.fixture
def config(tmp_path, monkeypatch):
    def initialize(self):
        self.config_dir = str(tmp_path)
        self.config_file = str(tmp_path / 'config.yaml')
        if not (tmp_path / 'config.yaml').exists():
            self._create_default_config()
        self._load_config()

    monkeypatch.setattr(Config, '_initialize', initialize)
    Config._instance = None
    yield Config
    Config._instance = None


def fields(**overrides):
    return dict(
        dict(
            name='主机 · Jellyfin',
            group='主机',
            server_type='jellyfin',
            server_url='http://server:8096/CaseSensitive',
            api_key='secret-a',
            username='media',
        ),
        **overrides,
    )


def test_migrates_exact_backup_distinct_instances_and_removes_scan_states(config, tmp_path):
    shared = {k: v for k, v in fields().items() if k not in ('name', 'group')}
    old = dict(
        genre_update=dict(shared, scan_mode='full', sync_state={'genre': 1}),
        country_update=dict(shared, sync_state={'country': 2}),
        version_merge=dict(shared, server_type='emby', server_url='http://server:8097'),
        symlink_export={'target_folder': '/keep/local'},
        ui_state={'selected_tab_index': 4},
    )
    original = ('# preserve exact original\n' + yaml.safe_dump(old)).encode()
    path = tmp_path / 'config.yaml'
    path.write_bytes(original)
    conf = config()
    store = get_media_profiles(conf)
    assert len(store.profiles) == 2
    assert store.active['server_type'] == 'jellyfin'
    assert store.settings('genre_update') == {}
    assert store.settings('country_update') == {}
    assert conf.get('symlink_export', 'target_folder') == '/keep/local'
    backups = list(tmp_path.glob('*.bak'))
    assert len(backups) == 1 and backups[0].read_bytes() == original
    ids = [p['id'] for p in store.profiles]
    conf._load_config()
    assert [p['id'] for p in store.profiles] == ids
    assert len(list(tmp_path.glob('*.bak'))) == 1


def test_same_host_credentials_type_port_path_are_separate(config):
    store = get_media_profiles(config())
    originals = [
        fields(),
        fields(server_type='emby'),
        fields(server_url='http://server:8097'),
        fields(api_key='secret-b'),
        fields(server_url='http://server:8096/casesensitive'),
    ]
    ids = [store.save_profile(p) for p in originals]
    assert len(set(ids)) == 5
    for profile_id, expected in zip(ids, originals):
        store.select(profile_id)
        assert store.active['api_key'] == expected['api_key']
        assert store.active['server_url'] == expected['server_url']
    store.config._load_config()
    assert store.active['id'] == ids[-1]


def test_existing_profiles_drop_incremental_settings_on_reload(config):
    store = get_media_profiles(config())
    profile_id = store.save_profile(fields())

    def legacy_settings(data):
        data['profiles'][0]['settings'] = {
            'genre_update': {'scan_mode': 'incremental', 'sync_state': {'last_scan_utc': '2026-09-01'}, 'keep': 1},
            'country_update': {'scan_mode': 'full', 'sync_state': {'last_scan_utc': '2026-09-02'}},
        }

    store.config.update_section('media_servers', legacy_settings)
    store.config._load_config()
    assert store.active['id'] == profile_id
    assert store.active['api_key'] == 'secret-a'
    assert store.settings('genre_update') == {'keep': 1}
    assert store.settings('country_update') == {}
    store.config._load_config()
    assert store.settings('genre_update') == {'keep': 1}


def test_snapshots_lock_profiles_while_local_settings_can_save(config):
    store = get_media_profiles(config())
    a = store.save_profile(fields())
    b = store.save_profile(fields(name='备机', server_url='http://second:8096'))
    genre, snapshot = store.begin_task('genre_update')
    with pytest.raises(ValueError):
        store.begin_task('country_update')
    snapshot['profile']['api_key'] = 'mutated snapshot'
    with pytest.raises(ValueError):
        store.select(b)
    with pytest.raises(ValueError):
        store.save_profile(fields(), a)
    with pytest.raises(ValueError):
        store.delete(a)

    def local_save():
        store.config.update_section('symlink_export', lambda data: data.update(target_folder='/local/kept'))

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(local_save)]
        for future in futures:
            future.result()
    store.end_task(genre)
    country, _ = store.begin_task('country_update')
    store.end_task(country)
    assert not store.busy
    assert store.config.get('symlink_export', 'target_folder') == '/local/kept'
    assert store.active['api_key'] == 'secret-a'
    store.select(b)
    assert store.settings('genre_update') == {}
    store.select(a)
    assert store.settings('genre_update') == {}
    assert store.settings('country_update') == {}
    store.config._load_config()
    assert store.settings('genre_update') == {}
    assert store.settings('country_update') == {}


def test_write_failure_keeps_disk_and_memory(config, monkeypatch):
    store = get_media_profiles(config())
    profile_id = store.save_profile(fields())
    old = deepcopy(store.data)
    from pathlib import Path

    original = Path(store.config.config_file).read_bytes()

    def fail(*_args):
        raise OSError('disk full')

    monkeypatch.setattr('utils.config.os.replace', fail)
    with pytest.raises(OSError):
        store.save_profile(fields(name='not saved'), profile_id)
    assert store.data == old
    assert Path(store.config.config_file).read_bytes() == original


def test_invalid_yaml_or_profile_format_never_overwrites(config, tmp_path):
    path = tmp_path / 'config.yaml'
    for original in [b'bad: [', b'[]', b'media_servers: {schema_version: 999}\n']:
        path.write_bytes(original)
        with pytest.raises((ValueError, yaml.YAMLError)):
            config()
        assert path.read_bytes() == original


def test_backup_failure_prevents_migration(config, tmp_path, monkeypatch):
    path = tmp_path / 'config.yaml'
    original = yaml.safe_dump({'genre_update': fields()}).encode()
    path.write_bytes(original)

    def fail(*_args, **_kwargs):
        raise OSError('backup unavailable')

    monkeypatch.setattr('utils.config.tempfile.mkstemp', fail)
    with pytest.raises(OSError):
        config()
    assert path.read_bytes() == original


def test_empty_store_does_not_reimport_legacy_and_selection_errors(config):
    conf = config()
    conf.set('genre_update', 'server_url', 'http://old')
    conf.save()
    conf._load_config()
    store = get_media_profiles(conf)
    assert store.profiles == []
    with pytest.raises(ValueError):
        store.begin_task('genre_update')
    profile_id = store.save_profile(fields())
    with pytest.raises(ValueError):
        store.delete(profile_id)
    with pytest.raises(ValueError):
        store.select('missing')
    assert store.active['id'] == profile_id


@pytest.mark.parametrize(
    'url', ['ftp://server', 'http://server:bad', 'http://user:secret@server', 'http://server?key=x']
)
def test_invalid_endpoints_rejected(config, url):
    store = get_media_profiles(config())
    with pytest.raises(ValueError):
        store.save_profile(fields(server_url=url))
    assert not store.profiles
