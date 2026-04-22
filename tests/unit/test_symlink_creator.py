"""
autosync/SymlinkCreator.py 单元测试
"""
import os
from unittest.mock import patch, MagicMock

import pytest

from autosync.SymlinkCreator import SymlinkCreator


class TestCreateSymlink:
    def test_creates_symlink_success(self, temp_dir, mock_logger):
        creator = SymlinkCreator(
            source_folders=[temp_dir],
            target_folder=temp_dir,
            allowed_extensions=(".mkv",),
            logger=mock_logger,
        )
        src = os.path.join(temp_dir, "source.mkv")
        dst = os.path.join(temp_dir, "link.mkv")
        with open(src, "w") as f:
            f.write("test")

        with patch("os.symlink") as mock_symlink:
            creator.create_symlink(src, dst, "Thread-1")
            mock_symlink.assert_called_once_with(src, dst)
            assert creator.created_links == 1

    def test_skips_existing_symlink(self, temp_dir, mock_logger):
        creator = SymlinkCreator(
            source_folders=[temp_dir],
            target_folder=temp_dir,
            allowed_extensions=(".mkv",),
            logger=mock_logger,
        )
        src = os.path.join(temp_dir, "source.mkv")
        dst = os.path.join(temp_dir, "link.mkv")
        with open(src, "w") as f:
            f.write("test")

        with patch("os.path.exists", return_value=True):
            creator.create_symlink(src, dst, "Thread-1")

            assert creator.existing_links == 1
            assert creator.created_links == 0

    def test_path_replacement(self, temp_dir, mock_logger):
        creator = SymlinkCreator(
            source_folders=[temp_dir],
            target_folder=temp_dir,
            allowed_extensions=(".mkv",),
            enable_replace_path=True,
            original_path="C:\\mirror",
            replace_path="D:\\real",
            logger=mock_logger,
        )
        src = "C:\\mirror\\movie.mkv"
        dst = os.path.join(temp_dir, "link.mkv")

        with patch("os.path.exists", return_value=False):
            with patch("os.symlink") as mock_symlink:
                creator.create_symlink(src, dst, "Thread-1")
                mock_symlink.assert_called_once()
                # 验证路径被替换
                called_src = mock_symlink.call_args[0][0]
                assert "D:\\real" in called_src

    def test_path_replacement_normalizes_paths(self, temp_dir, mock_logger):
        creator = SymlinkCreator(
            source_folders=[temp_dir],
            target_folder=temp_dir,
            allowed_extensions=(".mkv",),
            enable_replace_path=True,
            original_path="C:/mirror/",
            replace_path="D:/real/",
            logger=mock_logger,
        )
        # 使用 normpath 后的路径形式，因为原始路径会被 normpath
        src = "C:\\mirror\\movie.mkv"
        dst = os.path.join(temp_dir, "link.mkv")

        with patch("os.path.exists", return_value=False):
            with patch("os.symlink") as mock_symlink:
                creator.create_symlink(src, dst, "Thread-1")
                called_src = mock_symlink.call_args[0][0]
                assert "D:\\real" in called_src or "D:/real" in called_src


class TestGetSourceFiles:
    def test_yields_matching_extensions(self, temp_dir, mock_logger):
        # 创建不同扩展名的文件
        for name in ["a.mkv", "b.mp4", "c.txt"]:
            with open(os.path.join(temp_dir, name), "w") as f:
                f.write("x")

        creator = SymlinkCreator(
            source_folders=[temp_dir],
            target_folder=temp_dir,
            allowed_extensions=(".mkv", ".mp4"),
            logger=mock_logger,
        )
        results = list(creator.get_source_files())
        names = [os.path.basename(f) for f, _ in results]
        assert "a.mkv" in names
        assert "b.mp4" in names
        assert "c.txt" not in names

    def test_ignores_directories(self, temp_dir, mock_logger):
        os.makedirs(os.path.join(temp_dir, "subdir"))
        with open(os.path.join(temp_dir, "subdir", "a.mkv"), "w") as f:
            f.write("x")

        creator = SymlinkCreator(
            source_folders=[temp_dir],
            target_folder=temp_dir,
            allowed_extensions=(".mkv",),
            logger=mock_logger,
        )
        results = list(creator.get_source_files())
        names = [os.path.basename(f) for f, _ in results]
        assert "a.mkv" in names


class TestCreateStrmFile:
    def test_cd2_url_format(self, temp_dir, mock_logger):
        """
        cloud_url 只传主机+端口，代码会自动拼接 http:// 前缀。
        """
        creator = SymlinkCreator(
            source_folders=[temp_dir],
            target_folder=temp_dir,
            allowed_extensions=(".mkv",),
            symlink_mode="strm",
            cloud_type="cd2",
            cloud_root_path="/media",
            cloud_url="cd2.local:19798",
            logger=mock_logger,
        )
        src = os.path.join(temp_dir, "movie.mkv")
        with open(src, "w") as f:
            f.write("x")

        creator.create_strm_file(
            source_dir=temp_dir,
            target_dir=temp_dir,
            source_file=src,
            cloud_type="cd2",
            cloud_root_path="/media",
            cloud_url="cd2.local:19798",
            thread_name="T1",
        )

        strm_path = os.path.join(temp_dir, "movie.strm")
        with open(strm_path, "r") as f:
            content = f.read()
        assert content.startswith("http://cd2.local:19798/static/http/cd2.local:19798/False/")

    def test_alist_url_format(self, temp_dir, mock_logger):
        creator = SymlinkCreator(
            source_folders=[temp_dir],
            target_folder=temp_dir,
            allowed_extensions=(".mkv",),
            symlink_mode="strm",
            cloud_type="alist",
            cloud_root_path="/media",
            cloud_url="alist.local:5244",
            logger=mock_logger,
        )
        src = os.path.join(temp_dir, "movie.mkv")
        with open(src, "w") as f:
            f.write("x")
        dst = os.path.join(temp_dir, "movie.strm")

        creator.create_strm_file(
            source_dir=temp_dir,
            target_dir=temp_dir,
            source_file=src,
            cloud_type="alist",
            cloud_root_path="/media",
            cloud_url="alist.local:5244",
            thread_name="T1",
        )

        with open(dst, "r") as f:
            content = f.read()
        assert content.startswith("http://alist.local:5244/d/")

    def test_invalid_cloud_type_logs_error(self, temp_dir, mock_logger):
        creator = SymlinkCreator(
            source_folders=[temp_dir],
            target_folder=temp_dir,
            allowed_extensions=(".mkv",),
            symlink_mode="strm",
            logger=mock_logger,
        )
        src = os.path.join(temp_dir, "movie.mkv")
        with open(src, "w") as f:
            f.write("x")

        creator.create_strm_file(
            source_dir=temp_dir,
            target_dir=temp_dir,
            source_file=src,
            cloud_type="unknown",
            cloud_root_path="/media",
            cloud_url="test",
            thread_name="T1",
        )

        assert any("错误" in r.getMessage() for r in mock_logger.handlers[0].records)
