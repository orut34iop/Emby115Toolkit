"""
utils/listdir.py 单元测试

已知 bug：
- list_files 的 docstring 声称返回 3 元组，实际返回 2 元组
"""
import os
import time

import pytest
from freezegun import freeze_time

from utils.listdir import generate_output_filename, list_files, get_file_count


class TestGenerateOutputFilename:
    @freeze_time("2024-01-15 12:30:45")
    def test_includes_folder_name_and_timestamp(self):
        result = generate_output_filename("/path/to/MyFolder")
        assert result.startswith("MyFolder_files_")
        assert result.endswith(".txt")
        # 验证中间是 YYYYMMDD_HHMMSS 格式
        timestamp = result[len("MyFolder_files_"):-len(".txt")]
        assert len(timestamp) == 15  # YYYYMMDD_HHMMSS
        assert timestamp[8] == "_"

    def test_trailing_slash_removed(self):
        result = generate_output_filename("/path/to/MyFolder/")
        assert result.startswith("MyFolder_files_")
        assert result.endswith(".txt")


class TestListFiles:
    def test_returns_count_and_output_path(self, temp_dir):
        """
        验证 list_files 实际返回 2 元组（count, output_path）。
        这是已知 bug：docstring 声称返回 3 元组（count, paths, output_path）。
        """
        result = list_files(temp_dir)
        assert isinstance(result, tuple)
        assert len(result) == 2  # 实际返回 2 个值
        count, output_path = result
        assert isinstance(count, int)
        assert count == 0  # 空目录
        assert output_path == ""  # 空目录返回空字符串

    def test_creates_mergeLog_directory(self, temp_dir):
        """验证创建了 mergeLog 目录"""
        list_files(temp_dir)
        assert os.path.isdir("mergeLog")
        # 清理
        import shutil
        shutil.rmtree("mergeLog", ignore_errors=True)

    def test_writes_absolute_paths(self, temp_dir):
        """验证输出文件中每行是绝对路径"""
        # 创建文件
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("hello")

        count, output_path = list_files(temp_dir)
        assert count == 1
        assert os.path.exists(output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            lines = f.read().strip().split("\n")
        assert len(lines) == 1
        assert os.path.isabs(lines[0])
        assert lines[0].endswith("test.txt")

        # 清理
        import shutil
        shutil.rmtree("mergeLog", ignore_errors=True)

    def test_empty_folder_returns_zero(self, temp_dir):
        """空目录返回 (0, '')"""
        count, output_path = list_files(temp_dir)
        assert count == 0
        assert output_path == ""

    def test_nonexistent_folder_returns_zero(self, mock_logger):
        """不存在的目录返回 (0, '') 并记录错误"""
        count, output_path = list_files("/nonexistent/path/xyz", logger=mock_logger)
        assert count == 0
        assert output_path == ""
        records = mock_logger.handlers[0].records
        assert len(records) >= 1
        # 查找包含 "不存在" 的错误日志（可能在 INFO 记录之后）
        assert any("不存在" in r.getMessage() for r in records)

    def test_overwrites_existing_output(self, temp_dir):
        """验证会删除同名已有文件"""
        test_file = os.path.join(temp_dir, "a.txt")
        with open(test_file, "w") as f:
            f.write("a")

        count1, path1 = list_files(temp_dir)
        assert count1 == 1
        assert os.path.exists(path1)

        # 再创建第二个文件
        test_file2 = os.path.join(temp_dir, "b.txt")
        with open(test_file2, "w") as f:
            f.write("b")

        count2, path2 = list_files(temp_dir)
        assert count2 == 2
        assert path1 == path2  # 同名覆盖
        with open(path2, "r", encoding="utf-8") as f:
            lines = f.read().strip().split("\n")
        assert len(lines) == 2

        # 清理
        import shutil
        shutil.rmtree("mergeLog", ignore_errors=True)


class TestGetFileCount:
    def test_empty_directory(self, temp_dir):
        assert get_file_count(temp_dir) == 0

    def test_nested_files(self, temp_dir):
        os.makedirs(os.path.join(temp_dir, "sub"))
        for name in ["a.txt", "b.txt", "sub/c.txt"]:
            with open(os.path.join(temp_dir, name), "w") as f:
                f.write("x")
        assert get_file_count(temp_dir) == 3

    def test_nonexistent_path(self):
        assert get_file_count("/nonexistent/path") == 0
