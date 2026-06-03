import os

import pytest

from emby115_v2.context import AppContext
from emby115_v2.services.cloud_library_service import CloudScrapedLibraryService


def _make_symlink(link_path, target_path):
    try:
        os.symlink(target_path, link_path)
    except OSError as exc:
        pytest.skip(f"当前环境无法创建 symlink: {exc}")


def _context(workspace, target, dry_run=False, wait_minutes=0):
    return AppContext.from_dict(
        {
            "action": "build_cloud_scraped_library",
            "dry_run": dry_run,
            "path_pairs": [{"name": "movies", "source": str(workspace), "target": str(target)}],
            "symlink": {"video_extensions": [".mkv"]},
            "cloud_library_output": {"wait_minutes": wait_minutes},
        }
    )


def test_cloud_library_dry_run_plans_copy_and_video_move_without_writing(tmp_path, mock_logger):
    workspace = tmp_path / "workspace"
    target = tmp_path / "organized"
    origin = tmp_path / "origin"
    movie_dir = workspace / "Movie (2026)"
    origin.mkdir()
    movie_dir.mkdir(parents=True)
    real_video = origin / "movie.mkv"
    real_video.write_text("video", encoding="utf-8")
    link = movie_dir / "movie.mkv"
    _make_symlink(link, real_video)
    (movie_dir / "movie.nfo").write_text("nfo", encoding="utf-8")

    result = CloudScrapedLibraryService().run(_context(workspace, target, dry_run=True), mock_logger)

    assert result.status == "success"
    assert result.summary["metadata_planned"] == 1
    assert result.summary["videos_planned"] == 1
    assert not target.exists()
    assert real_video.exists()
    assert any(record.action == "copy_metadata" and record.status == "planned" for record in result.records)
    assert any(record.action == "move_real_video" and record.status == "planned" for record in result.records)


def test_cloud_library_copies_non_symlink_files_and_moves_real_video(tmp_path, mock_logger):
    workspace = tmp_path / "workspace"
    target = tmp_path / "organized"
    origin = tmp_path / "origin"
    movie_dir = workspace / "Movie (2026)"
    origin.mkdir()
    movie_dir.mkdir(parents=True)
    real_video = origin / "movie.mkv"
    real_video.write_text("video", encoding="utf-8")
    link = movie_dir / "movie.mkv"
    _make_symlink(link, real_video)
    (movie_dir / "movie.nfo").write_text("nfo", encoding="utf-8")
    (movie_dir / "movie-poster.jpg").write_text("poster", encoding="utf-8")

    result = CloudScrapedLibraryService().run(_context(workspace, target), mock_logger)

    assert result.status == "success"
    assert (target / "Movie (2026)" / "movie.nfo").read_text(encoding="utf-8") == "nfo"
    assert (target / "Movie (2026)" / "movie-poster.jpg").read_text(encoding="utf-8") == "poster"
    assert (target / "Movie (2026)" / "movie.mkv").read_text(encoding="utf-8") == "video"
    assert not real_video.exists()
    assert not (target / "Movie (2026)" / "movie.mkv").is_symlink()
    assert result.summary["metadata_copied"] == 2
    assert result.summary["videos_moved"] == 1


def test_cloud_library_skips_existing_video_by_default(tmp_path, mock_logger):
    workspace = tmp_path / "workspace"
    target = tmp_path / "organized"
    origin = tmp_path / "origin"
    movie_dir = workspace / "Movie (2026)"
    origin.mkdir()
    movie_dir.mkdir(parents=True)
    real_video = origin / "movie.mkv"
    real_video.write_text("video", encoding="utf-8")
    link = movie_dir / "movie.mkv"
    _make_symlink(link, real_video)
    existing_target = target / "Movie (2026)" / "movie.mkv"
    existing_target.parent.mkdir(parents=True)
    existing_target.write_text("existing", encoding="utf-8")

    result = CloudScrapedLibraryService().run(_context(workspace, target), mock_logger)

    assert result.status == "success"
    assert existing_target.read_text(encoding="utf-8") == "existing"
    assert real_video.exists()
    assert result.summary["videos_skipped_existing"] == 1
