"""
utils/config.py 单元测试
"""
import os

import pytest
from unittest.mock import patch

from utils.config import Config


class TestSingleton:
    def test_same_instance(self):
        """两次 Config() 返回同一对象"""
        c1 = Config()
        c2 = Config()
        assert c1 is c2

    def test_singleton_after_reset(self):
        """重置后创建新实例"""
        c1 = Config()
        Config._instance = None
        c2 = Config()
        assert c1 is not c2


class TestDefaultConfig:
    def test_default_sections_exist(self, mock_config):
        """默认配置包含所有预期 section"""
        for section in [
            "export_symlink",
            "delete_symlink",
            "merge_file",
            "merge_version",
            "update_genres",
            "mirror_115_tree",
        ]:
            assert mock_config.get(section) is not None

    def test_export_symlink_defaults(self, mock_config):
        cfg = mock_config.get("export_symlink")
        assert "link_suffixes" in cfg
        assert ".mkv" in cfg["link_suffixes"]
        assert "meta_suffixes" in cfg
        assert "thread_count" in cfg
        assert cfg["thread_count"] == 4


class TestGet:
    def test_get_existing_key(self, mock_config):
        val = mock_config.get("export_symlink", "thread_count")
        assert val == 4

    def test_get_missing_key_returns_default(self, mock_config):
        val = mock_config.get("export_symlink", "nonexistent", default="fallback")
        assert val == "fallback"

    def test_get_section_as_dict(self, mock_config):
        section = mock_config.get("export_symlink")
        assert isinstance(section, dict)
        assert "link_suffixes" in section


class TestSet:
    def test_set_updates_value(self, mock_config):
        mock_config.set("export_symlink", "thread_count", 16)
        assert mock_config.get("export_symlink", "thread_count") == 16

    def test_set_creates_new_section(self, mock_config):
        mock_config.set("new_section", "key", "value")
        assert mock_config.get("new_section", "key") == "value"


class TestSave:
    def test_save_creates_yaml_file(self, mock_config):
        assert os.path.exists(mock_config.config_file)
        mock_config.set("test", "val", 42)
        mock_config.save()
        # 验证文件可读
        import yaml
        with open(mock_config.config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data["test"]["val"] == 42


class TestLoadMerge:
    def test_load_merges_missing_defaults(self, mock_config, tmp_path):
        """加载部分配置时，缺失的默认键被回填"""
        # 写一个只有部分键的配置
        partial = {"export_symlink": {"thread_count": 99}}
        import yaml
        with open(mock_config.config_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(partial, f)

        # 重新加载
        mock_config._load_config()

        # 自定义值保留
        assert mock_config.get("export_symlink", "thread_count") == 99
        # 缺失默认值被回填
        assert "link_suffixes" in mock_config.get("export_symlink")
        assert ".mkv" in mock_config.get("export_symlink", "link_suffixes")
