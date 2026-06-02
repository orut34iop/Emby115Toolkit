import os
from unittest.mock import patch

from emby115_v2.context import AppContext
from emby115_v2.services.symlink_service import ScanAndLinkService


def _context(tmp_path, dry_run=False):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    (source / "Movie").mkdir()
    (source / "Movie" / "movie.mkv").write_text("x", encoding="utf-8")
    (source / "Movie" / "ignore.txt").write_text("x", encoding="utf-8")
    return AppContext.from_dict(
        {
            "action": "scan_and_link",
            "dry_run": dry_run,
            "path_pairs": [{"name": "movies", "source": str(source), "target": str(target)}],
            "symlink": {"video_extensions": [".mkv"], "thread_count": 1},
        }
    )


def test_dry_run_plans_without_creating_links(tmp_path, mock_logger):
    context = _context(tmp_path, dry_run=True)

    result = ScanAndLinkService().run(context, mock_logger)

    assert result.status == "success"
    assert result.summary["planned"] == 1
    assert result.records[-1].status == "planned"
    assert not (tmp_path / "target" / "Movie" / "movie.mkv").exists()


def test_run_creates_symlink_for_video_files(tmp_path, mock_logger):
    context = _context(tmp_path)

    with patch("os.symlink") as mock_symlink:
        result = ScanAndLinkService().run(context, mock_logger)

    assert result.status == "success"
    assert result.summary["created"] == 1
    mock_symlink.assert_called_once()
    called_source, called_target = mock_symlink.call_args.args
    assert called_source.endswith(os.path.join("source", "Movie", "movie.mkv"))
    assert called_target.endswith(os.path.join("target", "Movie", "movie.mkv"))


def test_existing_target_is_skipped(tmp_path, mock_logger):
    context = _context(tmp_path)
    existing = tmp_path / "target" / "Movie"
    existing.mkdir(parents=True)
    (existing / "movie.mkv").write_text("already here", encoding="utf-8")

    result = ScanAndLinkService().run(context, mock_logger)

    assert result.status == "success"
    assert result.summary["skipped_existing"] == 1
    assert result.summary["created"] == 0

