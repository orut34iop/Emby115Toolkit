"""Shared, GUI-independent media service profiles and task snapshots."""

from copy import deepcopy
from urllib.parse import urlsplit
from uuid import uuid4
from weakref import WeakMethod

CONNECTION_KEYS = ('server_type', 'server_url', 'api_key', 'username')
MEDIA_SECTIONS = ('version_merge', 'genre_update', 'country_update')


def connection(profile):
    return {key: profile.get(key, '') for key in CONNECTION_KEYS}


def migrate_profiles(config):
    """One-time migration. Keep partial legacy entries for repair, never merge by host alone."""
    if 'media_servers' in config:
        validate_store(config['media_servers'])
        changed = False
        for profile in config['media_servers']['profiles']:
            for section in ('genre_update', 'country_update'):
                settings = profile.get('settings', {}).get(section, {})
                for key in ('scan_mode', 'sync_state'):
                    if key in settings:
                        del settings[key]
                        changed = True
        return changed
    profiles, identities, section_ids = [], {}, {}
    labels = {'version_merge': '合并版本', 'genre_update': '更新流派', 'country_update': '更新地区'}
    for section in MEDIA_SECTIONS:
        old = config.get(section, {})
        if not isinstance(old, dict):
            continue
        values = {key: str(old.get(key) or '').strip() for key in CONNECTION_KEYS}
        if not any(values[key] for key in ('server_url', 'api_key', 'username')):
            continue
        values['server_type'] = values['server_type'] or 'emby'
        # The old merge page borrowed the genre username. Only do so for the same endpoint/credential.
        genre = config.get('genre_update', {})
        if section == 'version_merge' and not values['username'] and isinstance(genre, dict):
            if all(
                values[k] == str(genre.get(k) or ('emby' if k == 'server_type' else '')).strip()
                for k in ('server_type', 'server_url', 'api_key')
            ):
                values['username'] = str(genre.get('username') or '').strip()
        identity = tuple(values[k] for k in CONNECTION_KEYS)
        if identity not in identities:
            profile = dict(values, id=uuid4().hex, name=f"原配置 · {labels[section]}", group='', settings={})
            identities[identity] = profile
            profiles.append(profile)
        profile = identities[identity]
        section_ids[section] = profile['id']
    last_section = {3: 'version_merge', 4: 'genre_update', 5: 'country_update'}.get(
        config.get('ui_state', {}).get('selected_tab_index')
    )
    config['media_servers'] = {
        'schema_version': 1,
        'profiles': profiles,
        'active_profile_id': section_ids.get(last_section, profiles[0]['id'] if profiles else ''),
    }
    return True


def validate_store(data):
    if not isinstance(data, dict) or data.get('schema_version') != 1 or not isinstance(data.get('profiles'), list):
        raise ValueError('媒体服务配置格式或版本不受支持，请恢复配置备份')
    ids = set()
    for profile in data['profiles']:
        if not isinstance(profile, dict) or not isinstance(profile.get('id'), str) or not profile['id']:
            raise ValueError('媒体服务配置缺少实例 ID')
        if profile['id'] in ids or not all(
            isinstance(profile.get(k), str) for k in (*CONNECTION_KEYS, 'name', 'group')
        ):
            raise ValueError('媒体服务配置包含重复 ID 或无效字段')
        settings = profile.get('settings', {})
        if not isinstance(settings, dict) or any(not isinstance(v, dict) for v in settings.values()):
            raise ValueError('媒体服务扫描设置格式无效')
        ids.add(profile['id'])
    if data.get('active_profile_id') not in ids and (ids or data.get('active_profile_id') != ''):
        raise ValueError('当前媒体服务配置不存在，请恢复配置备份')


def validate_profile(profile):
    if not profile.get('name', '').strip():
        raise ValueError('请填写配置名称')
    if profile.get('server_type') not in ('emby', 'jellyfin'):
        raise ValueError('请选择 Emby 或 Jellyfin')
    try:
        url = urlsplit(profile.get('server_url', ''))
        valid = url.scheme in ('http', 'https') and url.hostname and not url.username and not url.password
        valid = valid and not url.query and not url.fragment
        _ = url.port
    except ValueError:
        valid = False
    if not valid:
        raise ValueError('请填写完整 HTTP / HTTPS 服务地址，不包含账号、查询参数或片段')
    if not profile.get('api_key', '').strip():
        raise ValueError('请填写 API Key')


class MediaProfiles:
    """One store per Config instance. UI mutations run on the UI thread."""

    def __init__(self, config):
        self.config = config
        self._lock = config._lock
        self._listeners = []
        self._tasks = {}
        validate_store(self.data)

    @property
    def data(self):
        return self.config.get('media_servers')

    @property
    def profiles(self):
        return self.data['profiles']

    @property
    def busy(self):
        with self._lock:
            return bool(self._tasks)

    @property
    def active(self):
        data = self.data
        return next((p for p in data['profiles'] if p['id'] == data['active_profile_id']), None)

    def subscribe(self, callback):
        ref = WeakMethod(callback)
        self._listeners.append(ref)
        return lambda: self._listeners.remove(ref) if ref in self._listeners else None

    def _notify(self):
        for ref in list(self._listeners):
            callback = ref()
            if callback is None:
                self._listeners.remove(ref)
            else:
                callback()

    def _editable(self):
        if self._tasks:
            raise ValueError('媒体任务仍在运行，请等待完成或停止后再修改配置')

    def _change(self, change):
        with self._lock:
            self._editable()
            self.config.update_section('media_servers', change)
        self._notify()

    def select(self, profile_id):
        def change(data):
            if not any(p['id'] == profile_id for p in data['profiles']):
                raise ValueError('所选配置不存在')
            data['active_profile_id'] = profile_id

        self._change(change)

    def save_profile(self, fields, profile_id=None):
        profile = {k: str(fields.get(k, '')).strip() for k in (*CONNECTION_KEYS, 'name', 'group')}
        validate_profile(profile)
        profile['id'] = profile_id or uuid4().hex

        def change(data):
            previous = next((p for p in data['profiles'] if p['id'] == profile_id), None)
            if profile_id and previous is None:
                raise ValueError('编辑的配置已不存在')
            profile['settings'] = deepcopy(previous.get('settings', {})) if previous else {}
            if previous:
                data['profiles'][data['profiles'].index(previous)] = profile
            else:
                data['profiles'].append(profile)
            if not data['active_profile_id']:
                data['active_profile_id'] = profile['id']

        self._change(change)
        return profile['id']

    def delete(self, profile_id):
        def change(data):
            if len(data['profiles']) <= 1:
                raise ValueError('请至少保留一份服务配置')
            if not any(p['id'] == profile_id for p in data['profiles']):
                raise ValueError('删除的配置不存在')
            data['profiles'] = [p for p in data['profiles'] if p['id'] != profile_id]
            if data['active_profile_id'] == profile_id:
                data['active_profile_id'] = data['profiles'][0]['id']

        self._change(change)

    def settings(self, section):
        profile = self.active
        return deepcopy(profile.get('settings', {}).get(section, {})) if profile else {}

    def begin_task(self, section):
        """Freeze all request parameters before launching a worker; release only after join."""
        with self._lock:
            if section not in MEDIA_SECTIONS:
                raise ValueError('未知媒体操作')
            if self._tasks:
                raise ValueError('已有媒体任务运行中，请等待完成后再执行其他媒体操作')
            profile = self.active
            if not profile:
                raise ValueError('请先打开右上角“服务配置”，新增并选择媒体服务')
            validate_profile(profile)
            if (section != 'version_merge' or profile['server_type'] == 'jellyfin') and not profile['username']:
                raise ValueError('此操作需要用户名，请在服务配置中补充')
            token = uuid4().hex
            task = {'section': section, 'profile': profile}
            self._tasks[token] = deepcopy(task)
        self._notify()
        return token, task

    def end_task(self, token):
        with self._lock:
            self._tasks.pop(token, None)
        self._notify()

def get_media_profiles(config):
    with config._lock:
        if not hasattr(config, '_media_profiles'):
            config._media_profiles = MediaProfiles(config)
        return config._media_profiles
