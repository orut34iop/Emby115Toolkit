import os
import sys

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

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialize()
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
            'version_merge': {'server_url': '', 'api_key': '', 'server_type': 'emby'},
            'genre_update': {'server_url': '', 'api_key': '', 'username': '', 'server_type': 'emby'},
            'country_update': {'server_url': '', 'api_key': '', 'username': '', 'server_type': 'emby'},
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

    def _create_default_config(self):
        """创建默认配置文件"""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.safe_dump(self._get_default_config(), f, allow_unicode=True, sort_keys=False)

    def _load_config(self):
        """加载配置文件"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                loaded_config = yaml.safe_load(f)

            # 获取默认配置
            default_config = self._get_default_config()

            # 确保配置不为空
            if not loaded_config:
                loaded_config = {}
            loaded_config = self._migrate_config(loaded_config)

            # 递归合并配置，确保所有默认值都存在
            def merge_config(default, loaded):
                if not isinstance(default, dict):
                    return loaded if loaded is not None else default

                result = loaded.copy() if loaded else {}
                for key, value in default.items():
                    if key not in result:
                        result[key] = value
                    else:
                        result[key] = merge_config(value, result.get(key))
                return result

            self._config = merge_config(default_config, loaded_config)

            # 保存合并后的配置
            self.save()

        except Exception as e:
            print(f"加载配置文件失败: {e}")
            self._config = self._get_default_config()
            self._create_default_config()

    def save(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(self._config, f, allow_unicode=True, sort_keys=False)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False

    def get(self, section, key=None, default=None):
        """获取配置值

        Args:
            section: 配置区段名
            key: 配置键名，如果为None则返回整个区段
            default: 默认值，当配置不存在时返回
        """
        if section not in self._config:
            return default

        if key is None:
            return self._config[section]

        return self._config[section].get(key, default)

    def set(self, section, key, value):
        """设置配置值

        Args:
            section: 配置区段名
            key: 配置键名
            value: 配置值
        """
        if section not in self._config:
            self._config[section] = {}

        self._config[section][key] = value
