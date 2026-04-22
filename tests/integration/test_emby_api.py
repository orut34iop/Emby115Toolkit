"""
Emby API 集成测试

使用 responses mock HTTP 请求，验证 EmbyOperator 的完整工作流。
"""
import pytest
import responses

from emby.EmbyOperator import EmbyOperator


class TestEmbyApiWorkflow:
    @responses.activate
    def test_full_duplicate_check_flow(self, mock_logger):
        """模拟完整查重流程"""
        server_url = "http://localhost:8096"
        api_key = "test-key"

        responses.get(
            f"{server_url}/emby/Items",
            json={
                "Items": [
                    {"Id": "1", "Name": "Existing Movie", "ProviderIds": {"Tmdb": "12345"}},
                ]
            },
            status=200,
        )

        op = EmbyOperator(server_url=server_url, api_key=api_key, logger=mock_logger)
        movies = op.get_all_media()

        assert len(movies) == 1
        assert op.query_movies_by_tmdbid(movies, "12345") is True
        assert op.query_movies_by_tmdbid(movies, "99999") is False

    @responses.activate
    def test_merge_versions_flow(self, mock_logger):
        """模拟版本合并流程"""
        server_url = "http://localhost:8096"
        api_key = "test-key"

        responses.get(
            f"{server_url}/emby/Items",
            json={
                "Items": [
                    {"Id": "1", "Name": "Movie", "ProviderIds": {"Tmdb": "123"}},
                    {"Id": "2", "Name": "Movie", "ProviderIds": {"Tmdb": "123"}},
                ]
            },
            status=200,
        )
        responses.post(
            f"{server_url}/emby/Videos/MergeVersions",
            status=204,
        )

        op = EmbyOperator(server_url=server_url, api_key=api_key, logger=mock_logger)
        movies = op.get_movie_media()
        grouped = op.group_movies_by_tmdbid(movies)
        merged = op.merge_movie_versions(grouped)

        assert len(merged) == 1
        assert len(responses.calls) == 2  # 1 GET + 1 POST

    @responses.activate
    def test_get_user_id_flow(self, mock_logger):
        """模拟获取用户 ID 流程"""
        server_url = "http://localhost:8096"
        api_key = "test-key"

        responses.get(
            f"{server_url}/Users/Public?api_key={api_key}",
            json=[
                {"Name": "admin", "Id": "u1"},
                {"Name": "test", "Id": "u2"},
            ],
            status=200,
        )

        op = EmbyOperator(
            server_url=server_url, api_key=api_key,
            user_name="test", logger=mock_logger,
        )
        user_id = op.emby_get_user_id()
        assert user_id == "u2"
