"""
autosync.AutoUploader 模块单元测试
"""
import pytest
import os
import yaml


class TestAutoUploaderInit:
    """测试 AutoUploader 初始化"""

    def test_init_with_default_config_path(self):
        """测试使用默认配置路径初始化"""
        from autosync.AutoUploader import AutoUploader

        uploader = AutoUploader()

        assert uploader.config_path == './config/config.yaml'
        assert uploader.metadata_ext == (".nfo", ".jpg", ".png", ".svg", ".ass", ".srt", ".sup")

    def test_init_with_custom_config_path(self):
        """测试使用自定义配置路径初始化"""
        from autosync.AutoUploader import AutoUploader

        uploader = AutoUploader(config_path='/custom/config.yaml')

        assert uploader.config_path == '/custom/config.yaml'


class TestAutoUploaderReadConfig:
    """测试 read_config 方法"""

    def test_read_valid_config(self, temp_dir):
        """测试读取有效的配置文件"""
        from autosync.AutoUploader import AutoUploader

        config_path = os.path.join(temp_dir, 'config.yaml')
        config_data = {
            'upload_enabled': True,
            'upload_scheduled': False,
            'num_threads': 4,
            'upload_list': []
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, allow_unicode=True)

        uploader = AutoUploader(config_path=config_path)
        result = uploader.read_config()

        assert result is not None
        assert result['upload_enabled'] == True
        assert result['num_threads'] == 4

    def test_read_nonexistent_config(self, temp_dir):
        """测试读取不存在的配置文件"""
        from autosync.AutoUploader import AutoUploader

        uploader = AutoUploader(config_path=os.path.join(temp_dir, 'nonexistent.yaml'))
        result = uploader.read_config()

        assert result is None

    def test_read_invalid_yaml(self, temp_dir):
        """测试读取无效的 YAML 文件"""
        from autosync.AutoUploader import AutoUploader

        config_path = os.path.join(temp_dir, 'invalid.yaml')
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write('invalid: yaml: content: [')

        uploader = AutoUploader(config_path=config_path)
        result = uploader.read_config()

        assert result is None


class TestAutoUploaderCaculateTime:
    """测试 caculate_time 方法"""

    def test_caculate_time_with_integer(self):
        """测试纯数字字符串"""
        from autosync.AutoUploader import AutoUploader

        uploader = AutoUploader()
        result = uploader.caculate_time('3600')

        assert result == 3600

    def test_caculate_time_with_multiplication(self):
        """测试乘法表达式"""
        from autosync.AutoUploader import AutoUploader

        uploader = AutoUploader()
        result = uploader.caculate_time('2*3600')

        assert result == 7200

    def test_caculate_time_with_invalid_input(self):
        """测试无效输入返回默认值"""
        from autosync.AutoUploader import AutoUploader

        uploader = AutoUploader()
        result = uploader.caculate_time('not_a_number')

        assert result == 86400

    def test_caculate_time_with_complex_expression(self):
        """测试复杂乘法表达式"""
        from autosync.AutoUploader import AutoUploader

        uploader = AutoUploader()
        result = uploader.caculate_time('60*60*24')

        assert result == 86400


class TestAutoUploaderParseExtensions:
    """测试 parse_extensions 方法"""

    def test_parse_single_extension(self):
        """测试单个扩展名"""
        from autosync.AutoUploader import AutoUploader

        uploader = AutoUploader()
        result = uploader.parse_extensions('.nfo')

        assert result == ('.nfo',)

    def test_parse_multiple_extensions(self):
        """测试多个扩展名"""
        from autosync.AutoUploader import AutoUploader

        uploader = AutoUploader()
        result = uploader.parse_extensions('.nfo;.jpg;.png')

        assert result == ('.nfo', '.jpg', '.png')

    def test_parse_with_whitespace(self):
        """测试带空格的扩展名字符串"""
        from autosync.AutoUploader import AutoUploader

        uploader = AutoUploader()
        result = uploader.parse_extensions(' .nfo ; .jpg ; .png ')

        assert result == ('.nfo', '.jpg', '.png')

    def test_parse_with_empty_elements(self):
        """测试包含空元素的扩展名字符串"""
        from autosync.AutoUploader import AutoUploader

        uploader = AutoUploader()
        result = uploader.parse_extensions('.nfo;;.jpg;')

        assert result == ('.nfo', '.jpg')


class TestAutoUploaderRunOnce:
    """测试 run_once 方法"""

    def test_run_once_with_empty_upload_list(self, temp_dir):
        """测试空上传列表"""
        from autosync.AutoUploader import AutoUploader

        config_path = os.path.join(temp_dir, 'config.yaml')
        config_data = {
            'upload_enabled': True,
            'upload_list': [],
            'num_threads': 4,
            'metadata_ext': '.nfo;.jpg'
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, allow_unicode=True)

        uploader = AutoUploader(config_path=config_path)
        # 空列表不应抛出异常
        uploader.run_once()

    def test_run_once_with_disabled_upload(self, temp_dir):
        """测试禁用的上传项"""
        from unittest.mock import patch
        from autosync.AutoUploader import AutoUploader

        config_path = os.path.join(temp_dir, 'config.yaml')
        config_data = {
            'upload_enabled': True,
            'upload_list': [
                {
                    'source_dir': '/source',
                    'target_dir': '/target',
                    'upload_enabled': False
                }
            ],
            'num_threads': 4,
            'metadata_ext': '.nfo;.jpg'
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, allow_unicode=True)

        uploader = AutoUploader(config_path=config_path)

        # upload_enabled=False 时不应创建 MetadataCopyer
        with patch('autosync.AutoUploader.MetadataCopyer') as MockCopyer:
            uploader.run_once()
            MockCopyer.assert_not_called()

    def test_run_once_with_enabled_upload(self, temp_dir):
        """测试启用的上传项"""
        from unittest.mock import patch, MagicMock
        from autosync.AutoUploader import AutoUploader

        config_path = os.path.join(temp_dir, 'config.yaml')
        config_data = {
            'upload_enabled': True,
            'upload_list': [
                {
                    'source_dir': '/source',
                    'target_dir': '/target',
                    'upload_enabled': True,
                    'metadata_ext': '.nfo;.jpg'
                }
            ],
            'num_threads': 4,
            'metadata_ext': '.nfo;.jpg'
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, allow_unicode=True)

        uploader = AutoUploader(config_path=config_path)

        mock_instance = MagicMock()
        mock_instance.run.return_value = 1.5

        with patch('autosync.AutoUploader.MetadataCopyer', return_value=mock_instance) as MockCopyer:
            uploader.run_once()
            MockCopyer.assert_called_once_with('/source', '/target', ('.nfo', '.jpg'), 4)
            mock_instance.run.assert_called_once()

    def test_run_once_reads_config_metadata_ext(self, temp_dir):
        """测试从配置读取默认 metadata_ext"""
        from unittest.mock import patch, MagicMock
        from autosync.AutoUploader import AutoUploader

        config_path = os.path.join(temp_dir, 'config.yaml')
        config_data = {
            'upload_enabled': True,
            'upload_list': [
                {
                    'source_dir': '/source',
                    'target_dir': '/target',
                    'upload_enabled': True
                }
            ],
            'num_threads': 2,
            'metadata_ext': '.nfo;.srt'
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, allow_unicode=True)

        uploader = AutoUploader(config_path=config_path)

        mock_instance = MagicMock()
        mock_instance.run.return_value = 0.5

        with patch('autosync.AutoUploader.MetadataCopyer', return_value=mock_instance) as MockCopyer:
            uploader.run_once()
            # 当 upload_list 项没有 metadata_ext 时使用全局配置
            MockCopyer.assert_called_once_with('/source', '/target', ('.nfo', '.srt'), 2)


class TestAutoUploaderRun:
    """测试 run 方法"""

    def test_run_when_upload_disabled(self, temp_dir):
        """测试 upload_enabled=False 时直接返回"""
        from unittest.mock import patch
        from autosync.AutoUploader import AutoUploader

        config_path = os.path.join(temp_dir, 'config.yaml')
        config_data = {
            'upload_enabled': False,
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, allow_unicode=True)

        uploader = AutoUploader(config_path=config_path)

        with patch.object(uploader, 'run_once') as mock_run_once:
            uploader.run()
            mock_run_once.assert_not_called()

    def test_run_single_mode(self, temp_dir):
        """测试单次运行模式"""
        from unittest.mock import patch
        from autosync.AutoUploader import AutoUploader

        config_path = os.path.join(temp_dir, 'config.yaml')
        config_data = {
            'upload_enabled': True,
            'upload_scheduled': False,
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, allow_unicode=True)

        uploader = AutoUploader(config_path=config_path)

        with patch.object(uploader, 'run_once') as mock_run_once:
            uploader.run()
            mock_run_once.assert_called_once()

    def test_run_with_no_config(self, temp_dir):
        """测试没有配置文件时直接返回"""
        from autosync.AutoUploader import AutoUploader

        uploader = AutoUploader(config_path=os.path.join(temp_dir, 'nonexistent.yaml'))
        # 不应抛出异常
        uploader.run()
