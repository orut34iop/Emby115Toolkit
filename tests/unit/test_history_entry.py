"""
utils/history_entry.py 单元测试

测试纯逻辑方法，不涉及真实 tkinter GUI。
"""
import os
from unittest.mock import MagicMock, patch

import pytest

from utils.history_entry import HistoryEntry


class TestParsePaths:
    def test_brace_delimited(self):
        with patch("utils.history_entry.ttk"):
            entry = HistoryEntry(MagicMock(), MagicMock(), "sec", "key")
            result = entry._parse_paths("{C:\\path\\a} {C:\\path\\b}")
            assert result == ["C:\\path\\a", "C:\\path\\b"]

    def test_space_delimited(self):
        with patch("utils.history_entry.ttk"):
            entry = HistoryEntry(MagicMock(), MagicMock(), "sec", "key")
            result = entry._parse_paths("C:\\path\\a C:\\path\\b")
            assert result == ["C:\\path\\a", "C:\\path\\b"]

    def test_mixed_format(self):
        with patch("utils.history_entry.ttk"):
            entry = HistoryEntry(MagicMock(), MagicMock(), "sec", "key")
            result = entry._parse_paths("{C:\\path\\a} C:\\path\\b")
            assert result == ["C:\\path\\a", "C:\\path\\b"]

    def test_empty_input(self):
        with patch("utils.history_entry.ttk"):
            entry = HistoryEntry(MagicMock(), MagicMock(), "sec", "key")
            result = entry._parse_paths("")
            assert result == []


class TestSaveHistory:
    def test_deduplicates(self):
        mock_config = MagicMock()
        mock_config.get.return_value = ["C:\\old1", "C:\\old2"]
        with patch("utils.history_entry.ttk"):
            entry = HistoryEntry(MagicMock(), mock_config, "sec", "key")
            entry._save_history("C:\\old1")  # 已存在的路径

        saved = mock_config.set.call_args_list
        # 路径被移到列表开头
        assert saved[0][0] == ("sec", "key_history", ["C:\\old1", "C:\\old2"])

    def test_limits_to_five(self):
        mock_config = MagicMock()
        mock_config.get.return_value = [f"C:\\path{i}" for i in range(5)]
        with patch("utils.history_entry.ttk"):
            entry = HistoryEntry(MagicMock(), mock_config, "sec", "key")
            entry._save_history("C:\\new")

        saved_history = mock_config.set.call_args_list[0][0][2]
        assert len(saved_history) == 5
        assert saved_history[0] == "C:\\new"

    def test_normalizes_paths(self):
        mock_config = MagicMock()
        mock_config.get.return_value = []
        with patch("utils.history_entry.ttk"):
            entry = HistoryEntry(MagicMock(), mock_config, "sec", "key")
            entry._save_history("C:/path/to/folder/")

        saved_path = mock_config.set.call_args_list[1][0][2]
        assert saved_path == os.path.normpath("C:/path/to/folder/")

    def test_ignores_empty_path(self):
        mock_config = MagicMock()
        mock_config.get.return_value = []
        with patch("utils.history_entry.ttk"):
            entry = HistoryEntry(MagicMock(), mock_config, "sec", "key")
            entry._save_history("")

        mock_config.set.assert_not_called()


class TestGetHistoryKey:
    def test_format(self):
        with patch("utils.history_entry.ttk"):
            entry = HistoryEntry(MagicMock(), MagicMock(), "sec", "target_folder")
            assert entry._get_history_key() == "target_folder_history"
