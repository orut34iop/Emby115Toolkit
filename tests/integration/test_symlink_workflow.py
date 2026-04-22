"""
软链接工作流集成测试
"""
import os
from unittest.mock import patch

import pytest

from autosync.SymlinkCreator import SymlinkCreator
from autosync.MetadataCopyer import MetadataCopyer


class TestSymlinkWorkflow:
    def test_creates_symlinks_for_matching_files(self, temp_dir, mock_logger):
        """端到端：创建符号链接"""
        source = os.path.join(temp_dir, "source")
        target = os.path.join(temp_dir, "target")
        os.makedirs(source)
        os.makedirs(target)

        for name in ["a.mkv", "b.mp4", "c.nfo"]:
            with open(os.path.join(source, name), "w") as f:
                f.write("x")

        creator = SymlinkCreator(
            source_folders=[source],
            target_folder=target,
            allowed_extensions=(".mkv", ".mp4"),
            num_threads=1,
            logger=mock_logger,
        )

        with patch("os.symlink") as mock_symlink:
            results = []
            def callback(msg):
                results.append(msg)
            creator.run(callback)
            # 等待线程完成
            import time
            time.sleep(0.5)
            assert mock_symlink.call_count == 2

    def test_metadata_copy_workflow(self, temp_dir, mock_logger):
        """端到端：复制元数据文件"""
        source = os.path.join(temp_dir, "source")
        target = os.path.join(temp_dir, "target")
        os.makedirs(source)

        for name in ["movie.mkv", "movie.nfo", "movie.jpg"]:
            with open(os.path.join(source, name), "w") as f:
                f.write("x")

        copier = MetadataCopyer(
            source_folders=[source],
            target_folder=target,
            allowed_extensions=(".nfo", ".jpg"),
            num_threads=1,
            logger=mock_logger,
        )

        results = []
        def callback(msg):
            results.append(msg)
        copier.run(callback)
        import time
        time.sleep(0.5)

        # MetadataCopyer 保留源文件夹结构，所以路径是 target\source\movie.nfo
        assert os.path.exists(os.path.join(target, "source", "movie.nfo"))
        assert os.path.exists(os.path.join(target, "source", "movie.jpg"))
        assert not os.path.exists(os.path.join(target, "source", "movie.mkv"))
