from pathlib import Path

from emby115_v2.context import AppContext


def test_context_from_dict_builds_typed_objects(tmp_path):
    context = AppContext.from_dict(
        {
            "action": "scan_and_link",
            "dry_run": True,
            "path_pairs": [
                {
                    "name": "movies",
                    "source": str(tmp_path / "source"),
                    "target": str(tmp_path / "target"),
                }
            ],
            "symlink": {"thread_count": 99, "video_extensions": [".mkv"]},
            "report": {"output_dir": str(tmp_path / "reports")},
            "logging": {"log_dir": str(tmp_path / "logs"), "log_level": "debug"},
        }
    )

    assert context.action == "scan_and_link"
    assert context.dry_run is True
    assert context.path_pairs[0].name == "movies"
    assert context.path_pairs[0].source == tmp_path / "source"
    assert context.symlink.thread_count == 32
    assert context.symlink.video_extensions == (".mkv",)
    assert context.report.output_dir == tmp_path / "reports"
    assert context.logging.log_level == "DEBUG"


def test_context_to_dict_serializes_paths(tmp_path):
    context = AppContext.from_dict(
        {
            "action": "scan_and_link",
            "path_pairs": [
                {"name": "tv", "source": str(tmp_path / "s"), "target": str(tmp_path / "t")}
            ],
        }
    )

    data = context.to_dict()

    assert data["path_pairs"][0]["source"] == str(Path(tmp_path / "s"))
    assert data["path_pairs"][0]["target"] == str(Path(tmp_path / "t"))

