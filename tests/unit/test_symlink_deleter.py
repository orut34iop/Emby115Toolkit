"""
autosync/SymlinkDeleter.py 单元测试
"""
import os

import pytest

from autosync.SymlinkDeleter import SymlinkDeleter


class TestSymlinkDeleter:
    def test_run_deletes_symlinks(self, temp_dir, mock_logger):
        """验证只删除符号链接，保留普通文件"""
        # 创建普通文件
        regular = os.path.join(temp_dir, "regular.txt")
        with open(regular, "w") as f:
            f.write("regular")

        # 创建符号链接（Windows 需要管理员权限，跳过若失败）
        link = os.path.join(temp_dir, "link.txt")
        try:
            os.symlink(regular, link)
        except (OSError, NotImplementedError):
            pytest.skip("当前环境不支持创建符号链接")

        deleter = SymlinkDeleter(temp_dir, logger=mock_logger)
        total_time, message = deleter.run()

        # 符号链接应被删除
        assert not os.path.exists(link)
        # 普通文件应保留
        assert os.path.exists(regular)

    def test_run_skips_regular_files(self, temp_dir, mock_logger):
        """验证普通文件不被删除"""
        regular = os.path.join(temp_dir, "regular.txt")
        with open(regular, "w") as f:
            f.write("regular")

        deleter = SymlinkDeleter(temp_dir, logger=mock_logger)
        total_time, message = deleter.run()

        assert os.path.exists(regular)
        # 计数应为 0（没有符号链接）
        assert "共处理软链接数：0" in message

    def test_run_counts_correctly(self, temp_dir, mock_logger):
        """验证计数准确"""
        regular = os.path.join(temp_dir, "regular.txt")
        with open(regular, "w") as f:
            f.write("regular")

        link1 = os.path.join(temp_dir, "link1.txt")
        link2 = os.path.join(temp_dir, "link2.txt")
        try:
            os.symlink(regular, link1)
            os.symlink(regular, link2)
        except (OSError, NotImplementedError):
            pytest.skip("当前环境不支持创建符号链接")

        deleter = SymlinkDeleter(temp_dir, logger=mock_logger)
        total_time, message = deleter.run()

        # 处理了 2 个符号链接，删除了 2 个，跳过 0 个
        assert "共处理软链接数：2" in message
        assert "共删除软链接数：2" in message
        assert "共跳过软链接数：0" in message

    def test_run_on_empty_dir(self, temp_dir, mock_logger):
        """空目录不报错"""
        deleter = SymlinkDeleter(temp_dir, logger=mock_logger)
        total_time, message = deleter.run()
        assert "共处理软链接数：0" in message
