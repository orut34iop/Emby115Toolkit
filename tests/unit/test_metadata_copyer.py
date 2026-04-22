"""
autosync/MetadataCopyer.py 单元测试
"""
import os

import pytest

from autosync.MetadataCopyer import MetadataCopyer


class TestCopyMetadata:
    def test_copies_file(self, temp_dir, mock_logger):
        copier = MetadataCopyer(
            source_folders=[temp_dir],
            target_folder=temp_dir,
            allowed_extensions=(".nfo", ".jpg"),
            num_threads=1,
            logger=mock_logger,
        )
        src = os.path.join(temp_dir, "source.nfo")
        dst = os.path.join(temp_dir, "target.nfo")
        with open(src, "w") as f:
            f.write("metadata")

        copier.copy_metadata(src, dst, "Thread-1")

        assert os.path.exists(dst)
        with open(dst, "r") as f:
            assert f.read() == "metadata"
        assert copier.copied_metadatas == 1

    def test_skips_existing_file(self, temp_dir, mock_logger):
        copier = MetadataCopyer(
            source_folders=[temp_dir],
            target_folder=temp_dir,
            allowed_extensions=(".nfo",),
            num_threads=1,
            logger=mock_logger,
        )
        src = os.path.join(temp_dir, "source.nfo")
        dst = os.path.join(temp_dir, "target.nfo")
        with open(src, "w") as f:
            f.write("new")
        with open(dst, "w") as f:
            f.write("old")

        copier.copy_metadata(src, dst, "Thread-1")

        assert copier.existing_links == 1
        assert copier.copied_metadatas == 0


class TestGetSourceFiles:
    def test_finds_by_extension(self, temp_dir, mock_logger):
        for name in ["a.nfo", "b.jpg", "c.txt"]:
            with open(os.path.join(temp_dir, name), "w") as f:
                f.write("x")

        copier = MetadataCopyer(
            source_folders=[temp_dir],
            target_folder=temp_dir,
            allowed_extensions=(".nfo", ".jpg"),
            num_threads=1,
            logger=mock_logger,
        )
        results = list(copier.get_source_files())
        names = [os.path.basename(f) for f, _, _ in results]
        assert "a.nfo" in names
        assert "b.jpg" in names
        assert "c.txt" not in names

    def test_only_tvshow_nfo_mode(self, temp_dir, mock_logger):
        subdir = os.path.join(temp_dir, "Show")
        os.makedirs(subdir)
        for name in ["tvshow.nfo", "episode.nfo", "poster.jpg"]:
            with open(os.path.join(subdir, name), "w") as f:
                f.write("x")

        copier = MetadataCopyer(
            source_folders=[temp_dir],
            target_folder=temp_dir,
            allowed_extensions=(".nfo", ".jpg"),
            num_threads=1,
            only_tvshow_nfo=True,
            logger=mock_logger,
        )
        results = list(copier.get_source_files())
        names = [os.path.basename(f) for f, _, _ in results]
        assert "tvshow.nfo" in names
        assert "episode.nfo" not in names
        assert "poster.jpg" not in names

    def test_avoids_symlink_loops(self, temp_dir, mock_logger):
        """验证循环符号链接不会导致无限递归"""
        subdir = os.path.join(temp_dir, "a")
        os.makedirs(subdir)
        # 创建循环符号链接 a/b -> a
        try:
            os.symlink(subdir, os.path.join(subdir, "b"))
        except (OSError, NotImplementedError):
            pytest.skip("当前环境不支持创建符号链接")

        with open(os.path.join(subdir, "file.nfo"), "w") as f:
            f.write("x")

        copier = MetadataCopyer(
            source_folders=[temp_dir],
            target_folder=temp_dir,
            allowed_extensions=(".nfo",),
            num_threads=1,
            logger=mock_logger,
        )
        results = list(copier.get_source_files())
        # 应该只找到 file.nfo，不会因循环而卡住或重复
        names = [os.path.basename(f) for f, _, _ in results]
        assert names.count("file.nfo") == 1
