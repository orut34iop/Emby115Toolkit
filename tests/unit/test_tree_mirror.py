"""
autosync/TreeMirror.py 单元测试
"""
import os
import tempfile
import logging

import pytest

from autosync.TreeMirror import TreeMirror


def _make_mirror():
    """辅助函数：创建一个未完整初始化的 TreeMirror 实例用于测试"""
    mirror = TreeMirror.__new__(TreeMirror)
    mirror.logger = logging.getLogger(__name__)
    mirror.fix_garbled = False
    return mirror


class TestReplaceSpecialChars:
    def test_replaces_asterisk(self):
        mirror = _make_mirror()
        assert mirror.replace_special_chars("path*name") == "pathsname"

    def test_no_asterisk_unchanged(self):
        mirror = _make_mirror()
        assert mirror.replace_special_chars("pathname") == "pathname"


class TestReadFileWithEncodings:
    def test_reads_utf8(self, tmp_path):
        mirror = _make_mirror()
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\n", encoding="utf-8")
        lines = mirror.read_file_with_encodings(str(f))
        assert lines == ["line1\n", "line2\n"]

    def test_reads_gbk_fallback(self, tmp_path):
        mirror = _make_mirror()
        f = tmp_path / "test.txt"
        f.write_bytes("中文\n测试\n".encode("gbk"))
        lines = mirror.read_file_with_encodings(str(f))
        assert lines == ["中文\n", "测试\n"]

    def test_cp1252_always_succeeds(self, tmp_path):
        """
        验证 cp1252（单字节编码）可以解码任何字节序列。
        因此 read_file_with_encodings 实际上永远不会抛出 UnicodeDecodeError。
        """
        mirror = _make_mirror()
        f = tmp_path / "test.bin"
        f.write_bytes(b"\xff\xfe\x00\x01\x80\x81")
        lines = mirror.read_file_with_encodings(str(f))
        # cp1252 会成功解码，返回字符串列表
        assert len(lines) == 1


class TestParseLinesToTuples:
    """
    TreeMirror 使用特定的缩进前缀来识别层级：
    - level 1: "|——" (U+007C + U+2014 + U+2014)
    - level 2: "| |-" (4 chars)
    - level 3: "| | |-" (6 chars)
    - level 4: "| | | |-" (8 chars)
    """

    def test_level_1(self):
        mirror = _make_mirror()
        content = "|——Root\n"
        f = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8")
        f.write(content)
        f.close()
        try:
            result = mirror.parse_lines_to_tuples(f.name)
            assert result == [(1, "Root")]
        finally:
            os.unlink(f.name)

    def test_level_3(self):
        mirror = _make_mirror()
        content = "|——Root\n| |-Sub\n| | |-Deep\n"
        f = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8")
        f.write(content)
        f.close()
        try:
            result = mirror.parse_lines_to_tuples(f.name)
            assert result == [
                (1, "Root"),
                (2, "Sub"),
                (3, "Deep"),
            ]
        finally:
            os.unlink(f.name)

    def test_ignores_blank_lines(self):
        mirror = _make_mirror()
        content = "|——Root\n\n| |-Sub\n"
        f = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8")
        f.write(content)
        f.close()
        try:
            result = mirror.parse_lines_to_tuples(f.name)
            assert result == [(1, "Root"), (2, "Sub")]
        finally:
            os.unlink(f.name)


class TestCreateEmptyFilesFromList:
    def test_creates_directories_and_files(self, tmp_path):
        mirror = _make_mirror()

        # 构建使用正确前缀的层级文本
        content = "|——Root\n| |-SubFolder\n| | |-file.mkv\n"
        f = tmp_path / "items.txt"
        f.write_text(content, encoding="utf-8")

        export = tmp_path / "export"
        export.mkdir()
        mirror.create_empty_files_from_list(str(f), str(export), fix_garbled=False)

        # 验证目录和文件
        assert (export / "Root").is_dir()
        assert (export / "Root" / "SubFolder").is_dir()
        assert (export / "Root" / "SubFolder" / "file.mkv").is_file()
        assert (export / "Root" / "SubFolder" / "file.mkv").stat().st_size == 0

    def test_sanitizes_path_traversal(self, tmp_path):
        mirror = _make_mirror()

        content = "|——..Root\n| |-fi<le>.txt\n"
        f = tmp_path / "items.txt"
        f.write_text(content, encoding="utf-8")

        export = tmp_path / "export"
        export.mkdir()
        mirror.create_empty_files_from_list(str(f), str(export), fix_garbled=False)

        # "..Root" 经过 strip('.') 后变成 "Root"（这是代码的已知行为）
        # "fi<le>.txt" 中 < > 被替换为下划线
        assert (export / "Root").is_dir()
        assert (export / "Root" / "fi_le_.txt").is_file()
