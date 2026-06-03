from pathlib import Path

from emby115_v2.context import AppContext


def test_context_from_dict_builds_typed_objects(tmp_path):
    context = AppContext.from_dict(
        {
            "action": "build_symlink_workspace",
            "dry_run": True,
            "path_pairs": [
                {
                    "name": "movies",
                    "source": str(tmp_path / "source"),
                    "target": str(tmp_path / "target"),
                }
            ],
            "symlink": {"thread_count": 99, "video_extensions": [".mkv"]},
            "tmdb": {"api_key": "tmdb-key", "language": "zh-CN", "fallback_language": "en-US"},
            "llm": {
                "provider": "deepseek",
                "base_url": "https://api.deepseek.com/v1",
                "api_key": "llm-key",
                "model": "deepseek-chat",
            },
            "metadata_output": {
                "media_type": "tvshows",
                "library_path": str(tmp_path / "library"),
                "download_season_posters": True,
                "auto_rename": True,
            },
            "cloud_library_output": {
                "wait_minutes": 0,
                "move_videos_after_wait": False,
                "overwrite_metadata": True,
                "overwrite_videos": False,
                "upload_wait_strategy": "clouddrive2_or_fixed",
            },
            "clouddrive2": {
                "endpoint": "127.0.0.1:19798",
                "api_token": "cd2-token",
                "poll_interval_seconds": 1,
                "settle_seconds": 2,
                "max_wait_minutes": 3,
            },
            "report": {"output_dir": str(tmp_path / "reports")},
            "logging": {"log_dir": str(tmp_path / "logs"), "log_level": "debug"},
        }
    )

    assert context.action == "build_symlink_workspace"
    assert context.dry_run is True
    assert context.path_pairs[0].name == "movies"
    assert context.path_pairs[0].source == tmp_path / "source"
    assert context.symlink.thread_count == 32
    assert context.symlink.video_extensions == (".mkv",)
    assert context.tmdb.language == "zh-CN"
    assert context.tmdb.fallback_language == "en-US"
    assert context.llm.provider == "deepseek"
    assert context.metadata_output.media_type == "tvshows"
    assert context.metadata_output.library_path == tmp_path / "library"
    assert context.metadata_output.download_season_posters is True
    assert context.metadata_output.auto_rename is True
    assert context.cloud_library_output.wait_minutes == 0
    assert context.cloud_library_output.move_videos_after_wait is False
    assert context.cloud_library_output.overwrite_metadata is True
    assert context.cloud_library_output.overwrite_videos is False
    assert context.cloud_library_output.upload_wait_strategy == "clouddrive2_or_fixed"
    assert context.clouddrive2.api_token == "cd2-token"
    assert context.clouddrive2.poll_interval_seconds == 1
    assert context.clouddrive2.settle_seconds == 2
    assert context.clouddrive2.max_wait_minutes == 3
    assert context.report.output_dir == tmp_path / "reports"
    assert context.logging.log_level == "DEBUG"


def test_context_to_dict_serializes_paths(tmp_path):
    context = AppContext.from_dict(
        {
            "action": "build_symlink_workspace",
            "path_pairs": [
                {"name": "tv", "source": str(tmp_path / "s"), "target": str(tmp_path / "t")}
            ],
        }
    )

    data = context.to_dict()

    assert data["path_pairs"][0]["source"] == str(Path(tmp_path / "s"))
    assert data["path_pairs"][0]["target"] == str(Path(tmp_path / "t"))
    assert data["metadata_output"]["library_path"] == "."
    assert data["metadata_output"]["auto_rename"] is True
    assert data["cloud_library_output"]["wait_minutes"] == 60
    assert data["cloud_library_output"]["upload_wait_strategy"] == "fixed"
    assert data["clouddrive2"]["endpoint"] == "127.0.0.1:19798"
