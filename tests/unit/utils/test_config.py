"""
utils.config 模块单元测试
"""
import pytest
import os
import yaml
import sys


@pytest.fixture
def isolated_config(temp_dir, monkeypatch):
    """提供在临时目录中隔离运行的 Config 实例"""
    import utils.config
    fake_path = os.path.join(temp_dir, 'utils', 'config.py')
    os.makedirs(os.path.dirname(fake_path), exist_ok=True)
    monkeypatch.setattr(utils.config, '__file__', fake_path)

    from utils.config import Config
    Config._instance = None
    Config._config = None
    return Config


class TestConfigSingleton:
    """测试 Config 单例模式"""

    def test_singleton_instance(self, isolated_config):
        """测试单例模式确保只有一个实例"""
        config1 = isolated_config()
        config2 = isolated_config()

        assert config1 is config2
        assert isolated_config._instance is config1

    def test_config_file_creation(self, isolated_config, temp_dir):
        """测试配置文件自动创建"""
        config = isolated_config()

        assert os.path.exists(os.path.join(temp_dir, 'config.yaml'))
        assert config._config is not None
        assert 'export_symlink' in config._config

    def test_config_default_values(self, isolated_config):
        """测试默认配置值"""
        config = isolated_config()

        # 检查默认值
        assert config.get('export_symlink', 'thread_count') == 4
        assert config.get('export_symlink', 'enable_replace_path') == False
        assert config.get('delete_symlink', 'target_folder') == ''
        assert config.get('merge_version', 'emby_url') == ''


class TestConfigGetSet:
    """测试配置读写操作"""

    def test_get_existing_value(self, isolated_config):
        """测试获取已存在的配置值"""
        config = isolated_config()

        # 设置一个值
        config.set('export_symlink', 'target_folder', '/test/path')

        # 获取值
        value = config.get('export_symlink', 'target_folder')
        assert value == '/test/path'

    def test_get_default_value(self, isolated_config):
        """测试获取不存在的键时返回默认值"""
        config = isolated_config()

        # 获取不存在的键
        value = config.get('nonexistent_section', 'nonexistent_key', default='default_value')
        assert value == 'default_value'

    def test_get_nested_dict(self, isolated_config):
        """测试获取嵌套字典"""
        config = isolated_config()

        # 获取整个 export_symlink 配置
        export_config = config.get('export_symlink')
        assert isinstance(export_config, dict)
        assert 'link_suffixes' in export_config
        assert 'meta_suffixes' in export_config

    def test_set_and_save(self, isolated_config, temp_dir):
        """测试设置值并保存到文件"""
        config = isolated_config()

        # 设置值
        config.set('export_symlink', 'target_folder', '/new/target')
        config.save()

        # 重新读取文件验证
        config_path = os.path.join(temp_dir, 'config.yaml')
        with open(config_path, 'r', encoding='utf-8') as f:
            saved_config = yaml.safe_load(f)

        assert saved_config['export_symlink']['target_folder'] == '/new/target'

    def test_set_list_value(self, isolated_config):
        """测试设置列表值"""
        config = isolated_config()

        # 设置列表值
        folders = ['/path/one', '/path/two']
        config.set('export_symlink', 'link_folders', folders)
        config.save()

        # 验证
        value = config.get('export_symlink', 'link_folders')
        assert value == folders

    def test_set_boolean_value(self, isolated_config):
        """测试设置布尔值"""
        config = isolated_config()

        # 设置布尔值
        config.set('export_symlink', 'enable_replace_path', True)
        config.save()

        # 验证
        value = config.get('export_symlink', 'enable_replace_path')
        assert value == True


class TestConfigMerge:
    """测试配置合并功能"""

    def test_merge_new_keys(self, isolated_config, temp_dir):
        """测试新键自动合并"""
        # 创建旧版配置文件（缺少一些键）
        old_config = {
            'export_symlink': {
                'link_suffixes': ['.mp4'],
                'meta_suffixes': ['.nfo']
            }
        }

        config_path = os.path.join(temp_dir, 'config.yaml')
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(old_config, f, allow_unicode=True)

        config = isolated_config()

        # 验证新键被合并
        assert config.get('export_symlink', 'thread_count') == 4
        assert config.get('export_symlink', 'enable_replace_path') == False

    def test_merge_preserves_existing_values(self, isolated_config, temp_dir):
        """测试合并时保留现有值"""
        # 创建包含自定义值的配置文件
        custom_config = {
            'export_symlink': {
                'link_suffixes': ['.custom'],
                'meta_suffixes': ['.nfo'],
                'thread_count': 8,
                'target_folder': '/custom/path'
            }
        }

        config_path = os.path.join(temp_dir, 'config.yaml')
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(custom_config, f, allow_unicode=True)

        config = isolated_config()

        # 验证自定义值被保留
        assert config.get('export_symlink', 'thread_count') == 8
        assert config.get('export_symlink', 'target_folder') == '/custom/path'
        assert config.get('export_symlink', 'link_suffixes') == ['.custom']


class TestConfigFrozen:
    """测试打包为 EXE 后的路径处理"""

    def test_frozen_path(self, temp_dir, monkeypatch):
        """测试打包后的路径解析"""
        import utils.config
        fake_path = os.path.join(temp_dir, 'utils', 'config.py')
        os.makedirs(os.path.dirname(fake_path), exist_ok=True)
        monkeypatch.setattr(utils.config, '__file__', fake_path)

        # 模拟打包环境
        monkeypatch.setattr('sys.frozen', True, raising=False)
        monkeypatch.setattr('sys.executable', os.path.join(temp_dir, 'app.exe'), raising=False)

        from utils.config import Config
        Config._instance = None
        Config._config = None

        config = Config()

        # 验证配置文件在 exe 所在目录创建
        assert os.path.exists(os.path.join(temp_dir, 'config.yaml'))

    def test_non_frozen_path(self, isolated_config, temp_dir):
        """测试非打包环境的路径"""
        config = isolated_config()

        # 验证配置文件在正确的位置创建
        assert os.path.exists(os.path.join(temp_dir, 'config.yaml'))
