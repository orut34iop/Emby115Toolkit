"""
全局 fixtures 和配置
"""
import os
import sys
import tempfile
import shutil
import threading
import logging
from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import Config


# ─────────────────────────────────────────────
# Config 单例隔离
# ─────────────────────────────────────────────
@pytest.fixture(autouse=True)
def isolate_config():
    """每个测试前后重置 Config 单例，防止状态泄漏"""
    Config._instance = None
    Config._config = None
    yield
    Config._instance = None
    Config._config = None


@pytest.fixture
def mock_config(tmp_path):
    """提供一个使用临时目录的 Config 实例"""
    Config._instance = None
    Config._config = None
    cfg = Config.__new__(Config)
    cfg.config_dir = str(tmp_path)
    cfg.config_file = os.path.join(str(tmp_path), 'config.yaml')
    cfg._config = cfg._get_default_config()
    cfg._create_default_config()
    Config._instance = cfg
    yield cfg
    Config._instance = None
    Config._config = None


# ─────────────────────────────────────────────
# 临时目录
# ─────────────────────────────────────────────
@pytest.fixture
def temp_dir():
    """提供临时目录并在测试后清理"""
    path = tempfile.mkdtemp()
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def source_media_dir(temp_dir):
    """创建模拟媒体源目录树"""
    root = os.path.join(temp_dir, "source")
    dirs = [
        os.path.join(root, "Movie A"),
        os.path.join(root, "Movie B", "Subfolder"),
        os.path.join(root, "TV Show", "Season 01"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)

    files = [
        os.path.join(root, "Movie A", "movie.mkv"),
        os.path.join(root, "Movie A", "movie.nfo"),
        os.path.join(root, "Movie A", "movie.jpg"),
        os.path.join(root, "Movie B", "movie2.mp4"),
        os.path.join(root, "Movie B", "movie2.nfo"),
        os.path.join(root, "TV Show", "Season 01", "ep01.ts"),
        os.path.join(root, "TV Show", "Season 01", "ep01.ass"),
    ]
    for f in files:
        Path(f).touch()
    return root


@pytest.fixture
def target_dir(temp_dir):
    """空目标目录"""
    path = os.path.join(temp_dir, "target")
    os.makedirs(path, exist_ok=True)
    return path


# ─────────────────────────────────────────────
# Mock logger（纯内存，无 GUI/文件依赖）
# ─────────────────────────────────────────────
class ListHandler(logging.Handler):
    """在内存中收集日志记录"""
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture
def mock_logger():
    """返回带内存 handler 的 logger"""
    logger = logging.getLogger("test_logger")
    logger.handlers = []
    logger.setLevel(logging.DEBUG)
    handler = ListHandler()
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    yield logger

    logger.handlers = []


@pytest.fixture
def capture_logs(mock_logger):
    """便捷访问 ListHandler 的记录"""
    return mock_logger.handlers[0].records


# ─────────────────────────────────────────────
# Mock tkinter Text 控件
# ─────────────────────────────────────────────
@pytest.fixture
def mock_tk_text():
    """返回支持 TextHandler 所需方法的 MagicMock"""
    widget = MagicMock()
    widget.after = MagicMock()
    widget.insert = MagicMock()
    widget.see = MagicMock()
    widget.update_idletasks = MagicMock()
    widget.after_idle = MagicMock()
    widget.tag_config = MagicMock()
    return widget


# ─────────────────────────────────────────────
# 线程辅助
# ─────────────────────────────────────────────
@pytest.fixture
def run_in_thread():
    """
    执行会启动后台线程的可调用对象，然后等待所有新线程完成。
    用法: run_in_thread(lambda: some_obj.run(callback))
    """
    def _runner(callable_fn, *args, **kwargs):
        threads_before = set(threading.enumerate())
        result = callable_fn(*args, **kwargs)
        threads_after = set(threading.enumerate())
        new_threads = threads_after - threads_before
        for t in new_threads:
            t.join(timeout=5.0)
            if t.is_alive():
                raise RuntimeError(f"线程 {t.name} 在超时内未完成")
        return result
    return _runner


# ─────────────────────────────────────────────
# Emby API 基础 fixture
# ─────────────────────────────────────────────
@pytest.fixture
def emby_server_url():
    return "http://localhost:8096"


@pytest.fixture
def emby_api_key():
    return "test-api-key-12345"


@pytest.fixture
def emby_operator(emby_server_url, emby_api_key, mock_logger):
    from emby.EmbyOperator import EmbyOperator
    return EmbyOperator(
        server_url=emby_server_url,
        api_key=emby_api_key,
        user_name="testuser",
        logger=mock_logger,
    )


@pytest.fixture
def mock_emby_all_media():
    """模拟 /emby/Items 返回数据"""
    return {
        "Items": [
            {
                "Id": "1",
                "Name": "Test Movie",
                "ProviderIds": {"Tmdb": "12345"},
                "Path": "/media/movie1.mkv",
            },
            {
                "Id": "2",
                "Name": "Test Movie 2",
                "ProviderIds": {"Tmdb": "67890"},
                "Path": "/media/movie2.mkv",
            },
            {
                "Id": "3",
                "Name": "Duplicate Movie",
                "ProviderIds": {"Tmdb": "12345"},
                "Path": "/media/movie1_alt.mkv",
            },
        ]
    }


@pytest.fixture
def mock_emby_users_public():
    """模拟 /Users/Public 返回数据"""
    return [
        {"Name": "admin", "Id": "user-admin"},
        {"Name": "testuser", "Id": "user-test-456"},
    ]
