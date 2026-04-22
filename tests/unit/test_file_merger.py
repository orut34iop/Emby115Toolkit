"""
autosync/FileMerger.py 单元测试
"""
import os

import pytest

from autosync.FileMerger import FileMerger


class TestInit:
    def test_raises_on_missing_metadata_folder(self, temp_dir, mock_logger):
        with pytest.raises(FileNotFoundError):
            FileMerger("/nonexistent/metadata", temp_dir, logger=mock_logger)

    def test_raises_on_missing_video_folder(self, temp_dir, mock_logger):
        with pytest.raises(FileNotFoundError):
            FileMerger(temp_dir, "/nonexistent/video", logger=mock_logger)


class TestFindMatchingVideo:
    def test_matches_by_nfo_name(self, temp_dir, mock_logger):
        merger = FileMerger(temp_dir, temp_dir, logger=mock_logger)
        # 模拟已加载的视频文件列表
        merger.video_files = [
            os.path.join(temp_dir, "movie.mkv"),
            os.path.join(temp_dir, "other.mp4"),
        ]
        nfo = os.path.join(temp_dir, "movie.nfo")
        result = merger.find_matching_video(nfo)
        assert result == os.path.join(temp_dir, "movie.mkv")

    def test_no_match_returns_empty(self, temp_dir, mock_logger):
        merger = FileMerger(temp_dir, temp_dir, logger=mock_logger)
        merger.video_files = [
            os.path.join(temp_dir, "other.mp4"),
        ]
        nfo = os.path.join(temp_dir, "movie.nfo")
        result = merger.find_matching_video(nfo)
        assert result == ""

    def test_skips_tvshow_nfo(self, temp_dir, mock_logger):
        merger = FileMerger(temp_dir, temp_dir, logger=mock_logger)
        merger.video_files = [
            os.path.join(temp_dir, "tvshow.mkv"),
        ]
        nfo = os.path.join(temp_dir, "tvshow.nfo")
        # 注意：实际代码在 find_matching_video 中不跳过 tvshow.nfo
        # 跳过逻辑在主循环中，所以这里会返回匹配
        result = merger.find_matching_video(nfo)
        assert result == os.path.join(temp_dir, "tvshow.mkv")

    def test_video_extension_whitelist(self, temp_dir, mock_logger):
        merger = FileMerger(temp_dir, temp_dir, logger=mock_logger)
        merger.video_files = [
            os.path.join(temp_dir, "movie.exe"),  # 不在白名单中
            os.path.join(temp_dir, "movie.mkv"),  # 在白名单中
        ]
        nfo = os.path.join(temp_dir, "movie.nfo")
        result = merger.find_matching_video(nfo)
        assert result == os.path.join(temp_dir, "movie.mkv")


class TestMoveVideoFile:
    def test_moves_file_success(self, temp_dir, mock_logger):
        merger = FileMerger(temp_dir, temp_dir, logger=mock_logger)
        src = os.path.join(temp_dir, "video.mkv")
        with open(src, "w") as f:
            f.write("video")
        nfo_dir = os.path.join(temp_dir, "Movie (2024)")
        os.makedirs(nfo_dir)
        nfo = os.path.join(nfo_dir, "Movie (2024).nfo")

        result = merger.move_video_file(src, nfo)

        assert result is True
        assert not os.path.exists(src)
        assert os.path.exists(os.path.join(nfo_dir, "video.mkv"))

    def test_missing_source_returns_false(self, temp_dir, mock_logger):
        merger = FileMerger(temp_dir, temp_dir, logger=mock_logger)
        src = os.path.join(temp_dir, "nonexistent.mkv")
        nfo_dir = os.path.join(temp_dir, "Movie (2024)")
        os.makedirs(nfo_dir)
        nfo = os.path.join(nfo_dir, "Movie (2024).nfo")

        result = merger.move_video_file(src, nfo)

        assert result is False
