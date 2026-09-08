import os
import sys
import tempfile
import threading
from copy import deepcopy

import yaml

SECTION_RENAMES = {
    'export_symlink': 'symlink_export',
    'delete_symlink': 'symlink_delete',
    'manipulate_folder': 'folder_tools',
    'check_duplicate': 'duplicate_check',
    'merge_file': 'file_merge',
    'merge_version': 'version_merge',
    'update_genres': 'genre_update',
    'mirror_115_tree': 'tree_mirror',
    'last_tab_index': 'ui_state',
}

KEY_RENAMES = {
    'duplicate_check': {
        'emby_url': 'server_url',
        'emby_api': 'api_key',
    },
    'version_merge': {
        'emby_url': 'server_url',
        'emby_api': 'api_key',
    },
    'genre_update': {
        'emby_url': 'server_url',
        'emby_api': 'api_key',
        'emby_username': 'username',
    },
    'file_merge': {
        'scrap_folder': 'metadata_folder',
    },
    'ui_state': {
        'index': 'selected_tab_index',
    },
}


class Config:
    _instance = None
    _config = None
    _lock = threading.RLock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                instance = super(Config, cls).__new__(cls)
                instance._initialize()
                cls._instance = instance
            return cls._instance

    def _initialize(self):
        """初始化配置"""
        # 获取程序根目录
        """
        根据当前是否为打包后的EXE文件来决定配置文件的保存位置。
        如果是EXE，则返回EXE所在的目录；如果是Python脚本，则返回脚本所在的目录。
        """
        if getattr(sys, 'frozen', False):
            # 打包成EXE的情况
            self.config_dir = os.path.dirname(sys.executable)
        else:
            # Python脚本的情况
            self.config_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.config_file = os.path.join(self.config_dir, 'config.yaml')

        # 确保配置文件存在
        if not os.path.exists(self.config_file):
            self._create_default_config()

        # 加载配置
        self._load_config()

    def _get_default_config(self):
        """获取默认配置"""
        return {
            'media_servers': {'schema_version': 1, 'profiles': [], 'active_profile_id': ''},
            'symlink_export': {
                'link_suffixes': [
                    '.mkv',
                    '.iso',
                    '.ts',
                    '.mp4',
                    '.avi',
                    '.rmvb',
                    '.wmv',
                    '.m2ts',
                    '.mpg',
                    '.flv',
                    '.rm',
                    '.m4v',
                ],
                'meta_suffixes': ['.nfo', '.jpg', '.png', '.ass', '.srt'],
                'thread_count': 4,
                'link_folders': [],
                'target_folder': '',
                'enable_replace_path': False,
                'original_path': '',
                'replace_path': '',
                'only_tvshow_nfo': True,
                'overwrite_metadata': False,
            },
            'symlink_delete': {'target_folder': ''},
            'folder_tools': {'target_folder': ''},
            'duplicate_check': {
                'target_folder': '',
                'server_url': '',
                'api_key': '',
                'delete_nfo': False,
                'delete_nfo_folder': False,
            },
            'file_merge': {
                'metadata_folder': '',
                'target_folder': '',
            },
            'version_merge': {'server_url': '', 'api_key': '', 'username': '', 'server_type': 'emby'},
            'genre_update': {
                'server_url': '',
                'api_key': '',
                'username': '',
                'server_type': 'emby',
                'scan_mode': 'incremental',
                'sync_state': {},
            },
            'country_update': {
                'server_url': '',
                'api_key': '',
                'username': '',
                'server_type': 'emby',
                'scan_mode': 'incremental',
                'sync_state': {},
            },
            'tree_mirror': {'tree_file': '', 'export_folder': '', 'fix_garbled_text': False},
            'ui_state': {'selected_tab_index': 0},
        }

    def _migrate_config(self, loaded_config):
        """将旧版配置字段迁移到当前命名规范。"""
        if not isinstance(loaded_config, dict):
            return {}

        migrated_config = {}
        for section, values in loaded_config.items():
            new_section = SECTION_RENAMES.get(section, section)
            is_legacy_section = section != new_section
            if not isinstance(values, dict):
                if is_legacy_section:
                    migrated_config.setdefault(new_section, values)
                else:
                    migrated_config[new_section] = values
                continue

            section_config = migrated_config.setdefault(new_section, {})
            if not isinstance(section_config, dict):
                section_config = {}
                migrated_config[new_section] = section_config

            section_key_renames = KEY_RENAMES.get(new_section, {})
            for key, value in values.items():
                new_key = section_key_renames.get(key, key)
                if is_legacy_section or key != new_key:
                    section_config.setdefault(new_key, value)
                else:
                    section_config[new_key] = value

        return migrated_config

    def _write_config(self, data):
        """Replace the whole file atomically; a failed write leaves the previous file intact."""
        directory = os.path.dirname(self.config_file)
        os.makedirs(directory, exist_ok=True)
        fd, path = tempfile.mkstemp(prefix='.config-', suffix='.tmp', dir=directory)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                yaml.safe_dump(data, stream, allow_unicode=True, sort_keys=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(path, self.config_file)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def _create_default_config(self):
        self._write_config(self._get_default_config())

    def _load_config(self):
        from utils.media_profiles import migrate_profiles

        with self._lock:
            with open(self.config_file, 'rb') as stream:
                original = stream.read()
            loaded = yaml.safe_load(original)
            if loaded is None:
                loaded = {}
            if not isinstance(loaded, dict):
                raise ValueError('配置文件必须是 YAML 字典；原文件已保留，请修复或恢复备份')
            # Preserve exact bytes before either legacy-key or service-profile migration.
            if loaded and 'media_servers' not in loaded:
                fd, backup = tempfile.mkstemp(
                    prefix='config.yaml.pre-media-profiles-', suffix='.bak', dir=self.config_dir
                )
                try:
                    with os.fdopen(fd, 'wb') as stream:
                        stream.write(original)
                        stream.flush()
                        os.fsync(stream.fileno())
                except Exception:
                    os.unlink(backup)
                    raise
            loaded = self._migrate_config(loaded)
            migrate_profiles(loaded)

            def merge_config(default, values):
                if not isinstance(default, dict):
                    return values if values is not None else default
                result = values.copy() if isinstance(values, dict) else {}
                for key, value in default.items():
                    result[key] = merge_config(value, result[key]) if key in result else deepcopy(value)
                return result

            candidate = merge_config(self._get_default_config(), loaded)
            self._write_config(candidate)
            self._config = candidate

    def save(self):
        with self._lock:
            try:
                self._write_config(self._config)
                return True
            except Exception:
                print('保存配置文件失败，请检查配置目录的权限和可用空间')
                return False

    def update_section(self, section, update):
        """Transactional mutation for concurrent service-state callbacks and profile edits."""
        with self._lock:
            candidate = deepcopy(self._config)
            update(candidate[section])
            self._write_config(candidate)
            self._config = candidate

    def get(self, section, key=None, default=None):
        with self._lock:
            values = self._config.get(section, default)
            if key is not None:
                values = values.get(key, default) if isinstance(values, dict) else default
            return deepcopy(values)

    def set(self, section, key, value):
        with self._lock:
            self._config.setdefault(section, {})[key] = deepcopy(value)
