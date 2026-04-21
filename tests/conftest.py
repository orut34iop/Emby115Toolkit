"""
测试配置和共享夹具
"""
import pytest
import tempfile
import os
import shutil
import sys
import types
from pathlib import Path

# 确保项目根目录在 sys.path 的最前面
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
else:
    # 如果已存在，确保它在最前面
    sys.path.remove(project_root)
    sys.path.insert(0, project_root)


# Mock utils.shentools if it doesn't exist (needed by SymlinkChecker, SymlinkDirChecker, etc.)
try:
    import utils.shentools
except ImportError:
    mock_shentools = types.ModuleType('utils.shentools')
    mock_shentools.symlink_name_dict = {"symlink": "软链接", "strm": "strm文件"}
    mock_shentools.print_message = lambda msg: None
    sys.modules['utils.shentools'] = mock_shentools
    # Also register under the package path
    import utils
    utils.shentools = mock_shentools


def pytest_runtest_setup(item):
    """每个测试运行前确保项目根目录在 sys.path 最前面"""
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    elif sys.path[0] != project_root:
        # 确保项目根目录在最前面
        sys.path.remove(project_root)
        sys.path.insert(0, project_root)


@pytest.fixture
def temp_dir():
    """创建临时目录，测试结束后自动清理"""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def sample_nfo_content():
    """返回示例 NFO 文件内容"""
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
    <title>Test Movie</title>
    <originaltitle>Original Title</originaltitle>
    <sorttitle>Sort Title</sorttitle>
    <year>2023</year>
    <rating>8.5</rating>
    <votes>1000</votes>
    <plot>这是一个测试电影的剧情简介。</plot>
    <runtime>120</runtime>
    <mpaa>PG-13</mpaa>
    <id>tt1234567</id>
    <uniqueid type="tmdb" default="true">12345</uniqueid>
    <uniqueid type="imdb" default="false">tt1234567</uniqueid>
    <genre>Action</genre>
    <genre>Adventure</genre>
    <country>USA</country>
    <premiered>2023-01-01</premiered>
    <studio>Test Studio</studio>
    <director>Test Director</director>
    <actor>
        <name>Actor One</name>
        <role>Lead</role>
    </actor>
    <actor>
        <name>Actor Two</name>
        <role>Supporting</role>
    </actor>
</movie>"""


@pytest.fixture
def sample_tvshow_nfo_content():
    """返回示例 TV Show NFO 文件内容"""
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<tvshow>
    <title>Test TV Show</title>
    <originaltitle>Original TV Title</originaltitle>
    <sorttitle>Sort TV Title</sorttitle>
    <year>2022</year>
    <rating>9.0</rating>
    <votes>5000</votes>
    <plot>这是一个测试剧集的剧情简介。</plot>
    <runtime>45</runtime>
    <mpaa>TV-14</mpaa>
    <id>tt7654321</id>
    <uniqueid type="tmdb" default="true">67890</uniqueid>
    <uniqueid type="imdb" default="false">tt7654321</uniqueid>
    <genre>Drama</genre>
    <genre>Thriller</genre>
    <country>UK</country>
    <premiered>2022-06-01</premiered>
    <studio>Test TV Studio</studio>
    <director>TV Director</director>
    <actor>
        <name>TV Actor One</name>
        <role>Main Character</role>
    </actor>
</tvshow>"""


@pytest.fixture
def sample_tree_content():
    """返回示例 115 目录树内容"""
    return """我的资源
|——电影
| |- 动作片
| | |- Movie.A.2023.mkv
| | |- Movie.B.2022.mp4
| |- 喜剧片
| | |- Comedy.2021.avi
|——剧集
| |- 美剧
| | |- Season 1
| | | |- Episode.01.mkv
| | | |- Episode.02.mkv
| |- 韩剧
| | |- Drama.2020
| | | |- EP01.mp4
| | | |- EP02.mp4
"""


@pytest.fixture
def mock_emby_response():
    """返回模拟的 Emby API 响应"""
    return {
        "Items": [
            {
                "Id": "item-id-1",
                "Name": "Test Movie 1",
                "ProviderIds": {"Tmdb": "12345"},
                "MediaSources": [
                    {"Id": "source-1", "Path": "/path/to/movie1.mkv"}
                ]
            },
            {
                "Id": "item-id-2",
                "Name": "Test Movie 2",
                "ProviderIds": {"Tmdb": "67890"},
                "MediaSources": [
                    {"Id": "source-2", "Path": "/path/to/movie2.mp4"},
                    {"Id": "source-3", "Path": "/path/to/movie2-alt.mkv"}
                ]
            }
        ],
        "TotalRecordCount": 2
    }


@pytest.fixture
def create_test_file_structure(temp_dir):
    """创建测试用的文件结构"""
    def _create(structure):
        """
        structure: dict，键为路径，值为内容（字符串）或 None（表示目录）
        """
        for path, content in structure.items():
            full_path = os.path.join(temp_dir, path)
            if content is None:
                os.makedirs(full_path, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w', encoding='utf-8') as f:
                    if isinstance(content, str):
                        f.write(content)
                    else:
                        f.write(str(content))
        return temp_dir
    return _create


@pytest.fixture
def mock_config_file(temp_dir):
    """创建模拟的配置文件"""
    config_path = os.path.join(temp_dir, 'config.yaml')
    config_content = """
export_symlink:
  link_suffixes:
    - .mp4
    - .mkv
    - .avi
  meta_suffixes:
    - .nfo
    - .jpg
    - .png
  thread_count: 4
  link_folders: []
  target_folder: ""
  enable_replace_path: false
  original_path: ""
  replace_path: ""
  only_tvshow_nfo: true

delete_symlink:
  target_folder: ""

merge_file:
  scrap_folder: ""
  target_folder: ""

merge_version:
  emby_url: "http://localhost:8096"
  emby_api: "test-api-key"

update_genres:
  emby_url: "http://localhost:8096"
  emby_api: "test-api-key"
  emby_username: "test-user"

mirror_115_tree:
  tree_file: ""
  export_folder: ""
  fix_garbled_text: false

last_tab_index:
  index: 0
"""
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(config_content)
    return config_path
