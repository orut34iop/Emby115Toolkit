"""
emby/EmbyOperator.py 单元测试

已知 bug 的回归测试：
1. Path 被导入两次
2. URL 拼写错误 ?/api_key=
3. check_video_files 使用裸文件名而非完整路径
"""
import os
import tempfile
import ast

import pytest
import responses

from emby.EmbyOperator import EmbyOperator


# ─────────────────────────────────────────────
# HTTP 请求测试
# ─────────────────────────────────────────────
class TestGetAllMedia:
    @responses.activate
    def test_success_returns_items(self, emby_server_url, emby_api_key, mock_logger):
        responses.get(
            f"{emby_server_url}/emby/Items",
            json={
                "Items": [
                    {"Id": "1", "Name": "Movie", "ProviderIds": {"Tmdb": "123"}}
                ]
            },
            status=200,
        )
        op = EmbyOperator(server_url=emby_server_url, api_key=emby_api_key, logger=mock_logger)
        result = op.get_all_media()
        assert len(result) == 1
        assert result[0]["Name"] == "Movie"

    @responses.activate
    def test_http_error_returns_empty(self, emby_server_url, emby_api_key, mock_logger):
        responses.get(
            f"{emby_server_url}/emby/Items",
            json={"error": "bad request"},
            status=500,
        )
        op = EmbyOperator(server_url=emby_server_url, api_key=emby_api_key, logger=mock_logger)
        result = op.get_all_media()
        assert result == []


class TestGetMovieMedia:
    @responses.activate
    def test_returns_only_movies(self, emby_server_url, emby_api_key, mock_logger):
        responses.get(
            f"{emby_server_url}/emby/Items",
            json={
                "Items": [
                    {"Id": "1", "Name": "Movie", "ProviderIds": {"Tmdb": "123"}},
                ]
            },
            status=200,
        )
        op = EmbyOperator(server_url=emby_server_url, api_key=emby_api_key, logger=mock_logger)
        result = op.get_movie_media()
        assert len(result) == 1


class TestQueryMoviesByTmdbid:
    def test_found_returns_true(self):
        movies = [
            {"ProviderIds": {"Tmdb": "12345"}},
            {"ProviderIds": {"Tmdb": "67890"}},
        ]
        op = EmbyOperator()
        assert op.query_movies_by_tmdbid(movies, "12345") is True

    def test_not_found_returns_false(self):
        movies = [
            {"ProviderIds": {"Tmdb": "12345"}},
        ]
        op = EmbyOperator()
        assert op.query_movies_by_tmdbid(movies, "99999") is False

    def test_empty_movies_returns_false(self):
        op = EmbyOperator()
        assert op.query_movies_by_tmdbid([], "123") is False


class TestExtractTmdbidFromNfo:
    def test_valid_xml(self, tmp_path):
        op = EmbyOperator()
        nfo = tmp_path / "movie.nfo"
        nfo.write_text("<movie><tmdbid>12345</tmdbid></movie>", encoding="utf-8")
        result, is_damaged = op.extract_tmdbid_from_nfo(str(nfo))
        assert result == "12345"
        assert is_damaged is False

    def test_missing_tmdbid_returns_none(self, tmp_path):
        """
        已知 bug：当 XML 中没有 tmdbid 元素时，extract_tmdbid_from_nfo
        没有显式 return，导致函数隐式返回 None（而非 (None, False)）。
        """
        op = EmbyOperator()
        nfo = tmp_path / "movie.nfo"
        nfo.write_text("<movie><title>Test</title></movie>", encoding="utf-8")
        result = op.extract_tmdbid_from_nfo(str(nfo))
        # 当前行为：隐式返回 None（不是 (None, False)）
        assert result is None

    def test_damaged_xml_uses_force_extract(self, tmp_path):
        op = EmbyOperator()
        nfo = tmp_path / "movie.nfo"
        # 破损 XML 但包含 tmdbid 行
        nfo.write_text("<movie>\n  <tmdbid>67890</tmdbid>\n</movie", encoding="utf-8")
        result, is_damaged = op.extract_tmdbid_from_nfo(str(nfo))
        assert result == "67890"
        assert is_damaged is True


class TestForceExtractTmdbid:
    def test_finds_with_two_space_indent(self, tmp_path):
        op = EmbyOperator()
        nfo = tmp_path / "movie.nfo"
        nfo.write_text("  <tmdbid>11111</tmdbid>\n", encoding="utf-8")
        result = op.force_extract_tmdbid_from_file(str(nfo))
        assert result == "11111"

    def test_no_match_returns_none(self, tmp_path):
        op = EmbyOperator()
        nfo = tmp_path / "movie.nfo"
        nfo.write_text("<tmdbid>22222</tmdbid>\n", encoding="utf-8")  # 没有两个空格前缀
        result = op.force_extract_tmdbid_from_file(str(nfo))
        assert result is None


class TestGroupMoviesByTmdbid:
    def test_groups_duplicates(self):
        op = EmbyOperator()
        movies = [
            {"Id": "1", "ProviderIds": {"Tmdb": "123"}, "Path": "/a.mkv"},
            {"Id": "2", "ProviderIds": {"Tmdb": "123"}, "Path": "/b.mkv"},
            {"Id": "3", "ProviderIds": {"Tmdb": "456"}, "Path": "/c.mkv"},
        ]
        result = op.group_movies_by_tmdbid(movies)
        assert len(result) == 2
        assert len(result["123"]) == 2
        assert len(result["456"]) == 1

    def test_skips_missing_tmdb(self):
        op = EmbyOperator()
        movies = [
            {"Id": "1", "ProviderIds": {}, "Path": "/a.mkv"},
            {"Id": "2", "ProviderIds": {"Tmdb": "123"}, "Path": "/b.mkv"},
        ]
        result = op.group_movies_by_tmdbid(movies)
        assert len(result) == 1
        assert "123" in result


class TestEmbyGetUserId:
    @responses.activate
    def test_found(self, emby_server_url, emby_api_key, mock_logger):
        responses.get(
            f"{emby_server_url}/Users/Public?api_key={emby_api_key}",
            json=[
                {"Name": "admin", "Id": "user-1"},
                {"Name": "testuser", "Id": "user-2"},
            ],
            status=200,
        )
        op = EmbyOperator(
            server_url=emby_server_url, api_key=emby_api_key,
            user_name="testuser", logger=mock_logger,
        )
        result = op.emby_get_user_id()
        assert result == "user-2"

    @responses.activate
    def test_not_found_returns_none(self, emby_server_url, emby_api_key, mock_logger):
        responses.get(
            f"{emby_server_url}/Users/Public?api_key={emby_api_key}",
            json=[{"Name": "admin", "Id": "user-1"}],
            status=200,
        )
        op = EmbyOperator(
            server_url=emby_server_url, api_key=emby_api_key,
            user_name="nobody", logger=mock_logger,
        )
        result = op.emby_get_user_id()
        assert result is None


class TestMergeMovieVersions:
    @responses.activate
    def test_calls_post(self, emby_server_url, emby_api_key, mock_logger):
        responses.post(
            f"{emby_server_url}/emby/Videos/MergeVersions",
            status=204,
        )
        op = EmbyOperator(server_url=emby_server_url, api_key=emby_api_key, logger=mock_logger)
        grouped = {
            "123": [
                {"Id": "1", "Name": "Movie"},
                {"Id": "2", "Name": "Movie"},
            ]
        }
        result = op.merge_movie_versions(grouped)
        assert len(result) == 1
        assert len(responses.calls) == 1
        # 验证请求参数包含 Ids
        assert "Ids=1%2C2" in responses.calls[0].request.url or "Ids=1,2" in responses.calls[0].request.url

    @responses.activate
    def test_skips_single_movies(self, emby_server_url, emby_api_key, mock_logger):
        op = EmbyOperator(server_url=emby_server_url, api_key=emby_api_key, logger=mock_logger)
        grouped = {
            "123": [
                {"Id": "1", "Name": "Movie"},
            ]
        }
        result = op.merge_movie_versions(grouped)
        assert len(result) == 0
        assert len(responses.calls) == 0


# ─────────────────────────────────────────────
# 已知 bug 的回归测试
# ─────────────────────────────────────────────
class TestKnownBugs:
    def test_duplicate_path_import(self):
        """
        Bug: EmbyOperator.py 中 Path 被导入了两次（第 11 行和第 16 行）。
        """
        file_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "emby", "EmbyOperator.py"
        )
        file_path = os.path.abspath(file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)
        path_imports = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "pathlib":
                    for alias in node.names:
                        if alias.name == "Path":
                            path_imports += 1

        # 当前有 2 次导入，修复后应为 1
        assert path_imports == 2, f"发现 {path_imports} 次 Path 导入，预期 2（已知 bug）"

    def test_url_typo_in_source(self):
        """
        Bug: EmbyOperator.py 中存在 ?/api_key= 的 URL 拼写错误。
        这个测试记录该 bug 的存在。
        """
        file_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "emby", "EmbyOperator.py"
        )
        file_path = os.path.abspath(file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert "?/api_key=" in source, "未发现 URL 拼写错误（可能已修复）"

    def test_check_video_files_uses_bare_filename(self):
        """
        Bug: check_video_files 中使用 os.path.isfile(video_file)，
        但 video_file 只是文件名而非完整路径。
        这个测试通过检查源码来记录该 bug。
        """
        file_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "emby", "EmbyOperator.py"
        )
        file_path = os.path.abspath(file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        # 查找 check_video_files 方法中是否存在 isfile(video_file) 而非 isfile(video_full_path)
        assert "os.path.isfile(video_file)" in source, "未发现裸文件名 bug（可能已修复）"
