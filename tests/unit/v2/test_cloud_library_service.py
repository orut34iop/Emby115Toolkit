import os

import pytest

from emby115_v2.context import AppContext
from emby115_v2.context import PathPair
from emby115_v2.services.cloud_library_service import CloudScrapedLibraryService
from emby115_v2.services.clouddrive2 import CloudDrive2WaitResult


def _make_symlink(link_path, target_path):
    try:
        os.symlink(target_path, link_path)
    except OSError as exc:
        pytest.skip(f"当前环境无法创建 symlink: {exc}")


def _context(
    workspace,
    target,
    dry_run=False,
    wait_minutes=0,
    upload_wait_strategy="fixed",
    move_videos_after_wait=True,
):
    return AppContext.from_dict(
        {
            "action": "build_cloud_scraped_library",
            "dry_run": dry_run,
            "path_pairs": [{"name": "movies", "source": str(workspace), "target": str(target)}],
            "symlink": {"video_extensions": [".mkv"]},
            "cloud_library_output": {
                "wait_minutes": wait_minutes,
                "upload_wait_strategy": upload_wait_strategy,
                "move_videos_after_wait": move_videos_after_wait,
            },
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


def test_cloud_library_ignores_legacy_config_that_disabled_video_move(tmp_path, mock_logger):
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

    result = CloudScrapedLibraryService().run(
        _context(workspace, target, move_videos_after_wait=False),
        mock_logger,
    )

    assert result.status == "success"
    assert (target / "Movie (2026)" / "movie.mkv").read_text(encoding="utf-8") == "video"
    assert not real_video.exists()
    assert result.summary["move_videos_after_wait"] is True
    assert result.summary["videos_moved"] == 1


def test_cloud_library_uses_readlink_when_resolve_fails_on_virtual_drive(tmp_path, mock_logger, monkeypatch):
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

    original_readlink = os.readlink
    raw_target = "\\\\?\\" + str(real_video)

    def fake_readlink(path):
        if os.fspath(path) == os.fspath(link):
            return raw_target
        return original_readlink(path)

    def fake_resolve(self, strict=False):
        if os.fspath(self) == os.fspath(link):
            exc = OSError("The volume does not contain a recognized file system")
            exc.winerror = 1005
            raise exc
        return self

    monkeypatch.setattr("emby115_v2.services.cloud_library_service.os.readlink", fake_readlink)
    monkeypatch.setattr("emby115_v2.services.cloud_library_service.Path.resolve", fake_resolve)

    result = CloudScrapedLibraryService().run(_context(workspace, target), mock_logger)

    assert result.status == "success"
    assert (target / "Movie (2026)" / "movie.mkv").read_text(encoding="utf-8") == "video"
    assert not real_video.exists()
    assert result.summary["videos_moved"] == 1
    assert any(
        record.action == "skip_symlink_copy"
        and "os.readlink" in record.extra.get("real_video_resolve_reason", "")
        for record in result.records
    )


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
    (movie_dir / "movie.nfo").write_text("nfo", encoding="utf-8")
    existing_target = target / "Movie (2026)" / "movie.mkv"
    existing_target.parent.mkdir(parents=True)
    existing_target.write_text("existing", encoding="utf-8")

    result = CloudScrapedLibraryService().run(_context(workspace, target), mock_logger)

    assert result.status == "success"
    assert existing_target.read_text(encoding="utf-8") == "existing"
    assert real_video.exists()
    assert result.summary["videos_skipped_existing"] == 1


@pytest.mark.parametrize("move_videos_after_wait", [True, False])
def test_cloud_library_does_not_plan_real_video_move_without_same_stem_nfo(
    tmp_path,
    mock_logger,
    move_videos_after_wait,
):
    workspace = tmp_path / f"workspace-{move_videos_after_wait}"
    target = tmp_path / f"organized-{move_videos_after_wait}"
    origin = tmp_path / f"origin-{move_videos_after_wait}"
    movie_dir = workspace / "Movie (2026)"
    origin.mkdir()
    movie_dir.mkdir(parents=True)
    real_video = origin / "movie.mkv"
    real_video.write_text("video", encoding="utf-8")
    link = movie_dir / "movie.mkv"
    _make_symlink(link, real_video)
    (movie_dir / "other.nfo").write_text("unrelated", encoding="utf-8")

    result = CloudScrapedLibraryService().run(
        _context(workspace, target, move_videos_after_wait=move_videos_after_wait),
        mock_logger,
    )

    assert result.status == "partial"
    assert result.summary["videos_planned"] == 0
    assert result.summary["videos_moved"] == 0
    assert result.summary["videos_skipped_missing_nfo"] == 1
    assert real_video.exists()
    assert not (target / "Movie (2026)" / "movie.mkv").exists()
    assert not any(record.action == "move_real_video" for record in result.records)
    assert any(
        record.action == "skip_symlink_copy"
        and record.status == "skipped"
        and "同目录缺少同名 NFO" in record.reason
        and record.extra.get("required_nfo_path", "").endswith("movie.nfo")
        for record in result.records
    )


def test_cloud_library_clouddrive2_or_fixed_treats_not_observed_as_settled(
    tmp_path,
    mock_logger,
    monkeypatch,
):
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

    class FakeWaiter:
        def wait_for_paths(self, paths, run_id, logger):
            return CloudDrive2WaitResult(
                "not_observed",
                "测试未观测到上传任务",
                watched_roots=("d:/organized",),
            )

    monkeypatch.setattr(
        "emby115_v2.services.cloud_library_service.CloudDrive2UploadWaiter.from_context",
        lambda _context: FakeWaiter(),
    )

    result = CloudScrapedLibraryService().run(
        _context(workspace, target, wait_minutes=0, upload_wait_strategy="clouddrive2_or_fixed"),
        mock_logger,
    )

    assert result.status == "success"
    assert (target / "Movie (2026)" / "movie.mkv").exists()
    assert any(
        record.action == "wait_for_cloud_upload"
        and record.status == "success"
        and record.extra.get("raw_status") == "not_observed"
        for record in result.records
    )
    assert not any(record.action == "wait_for_cloud_upload" and record.status == "fallback" for record in result.records)


def test_cloud_library_clouddrive2_strict_treats_not_observed_as_settled(
    tmp_path,
    mock_logger,
    monkeypatch,
):
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

    class FakeWaiter:
        def wait_for_paths(self, paths, run_id, logger):
            return CloudDrive2WaitResult("not_observed", "测试未观测到上传任务")

    monkeypatch.setattr(
        "emby115_v2.services.cloud_library_service.CloudDrive2UploadWaiter.from_context",
        lambda _context: FakeWaiter(),
    )

    result = CloudScrapedLibraryService().run(
        _context(workspace, target, wait_minutes=0, upload_wait_strategy="clouddrive2"),
        mock_logger,
    )

    assert result.status == "success"
    assert not real_video.exists()
    assert (target / "Movie (2026)" / "movie.mkv").exists()
    assert (target / "Movie (2026)" / "movie.nfo").exists()
    assert any(record.action == "move_real_video" and record.status == "moved" for record in result.records)


def test_cloud_library_clouddrive2_strict_marks_partial_when_timeout(
    tmp_path,
    mock_logger,
    monkeypatch,
):
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

    class FakeWaiter:
        def wait_for_paths(self, paths, run_id, logger):
            return CloudDrive2WaitResult("timeout", "测试等待上传任务超时", observed=True)

    monkeypatch.setattr(
        "emby115_v2.services.cloud_library_service.CloudDrive2UploadWaiter.from_context",
        lambda _context: FakeWaiter(),
    )

    result = CloudScrapedLibraryService().run(
        _context(workspace, target, wait_minutes=0, upload_wait_strategy="clouddrive2"),
        mock_logger,
    )

    assert result.status == "partial"
    assert result.summary["cloud_upload_wait_unconfirmed"] is True
    assert result.summary["videos_skipped_wait_unconfirmed"] == 1
    assert real_video.exists()
    assert not (target / "Movie (2026)" / "movie.mkv").exists()
    assert (target / "Movie (2026)" / "movie.nfo").exists()
    assert any(record.action == "move_real_video" and record.status == "skipped" for record in result.records)


def test_cloud_library_clouddrive2_strict_fails_when_upload_task_failed(
    tmp_path,
    mock_logger,
    monkeypatch,
):
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

    class FakeWaiter:
        def wait_for_paths(self, paths, run_id, logger):
            return CloudDrive2WaitResult("failed", "测试上传任务失败")

    monkeypatch.setattr(
        "emby115_v2.services.cloud_library_service.CloudDrive2UploadWaiter.from_context",
        lambda _context: FakeWaiter(),
    )

    result = CloudScrapedLibraryService().run(
        _context(workspace, target, wait_minutes=0, upload_wait_strategy="clouddrive2"),
        mock_logger,
    )

    assert result.status == "failed"
    assert result.summary["failed_before_video_move"] is True
    assert real_video.exists()
    assert not (target / "Movie (2026)" / "movie.mkv").exists()


def test_cloud_library_directory_creation_retries_virtual_drive_winerror_50(mock_logger, monkeypatch):
    service = CloudScrapedLibraryService()
    attempts = {}

    def fake_mkdir(path):
        key = str(path)
        attempts[key] = attempts.get(key, 0) + 1
        if key.endswith("Season 01") and attempts[key] == 1:
            exc = OSError("The request is not supported")
            exc.winerror = 50
            raise exc

    monkeypatch.setattr("emby115_v2.services.cloud_library_service.os.mkdir", fake_mkdir)
    monkeypatch.setattr("emby115_v2.services.cloud_library_service.time.sleep", lambda _seconds: None)
    monkeypatch.setattr(service, "_directory_name_visible", lambda _path: False)

    error = service._ensure_directory(PathPair.from_dict({
        "name": "tvshows",
        "source": "C:\\working-emby\\tvshows",
        "target": "D:\\115open\\tmp\\organized\\tvshows\\证词 (2026)\\Season 01",
    }).target, mock_logger)

    assert error == ""
    assert attempts["D:\\115open\\tmp\\organized\\tvshows\\证词 (2026)\\Season 01"] == 2


def test_cloud_library_records_directory_creation_failure_without_crashing(tmp_path, mock_logger, monkeypatch):
    workspace = tmp_path / "workspace"
    target = tmp_path / "organized"
    show_dir = workspace / "证词 (2026)" / "Season 01"
    show_dir.mkdir(parents=True)
    (show_dir / "episode.nfo").write_text("nfo", encoding="utf-8")

    def fake_ensure_directory(path, logger=None):
        if str(path).endswith("Season 01"):
            return "创建目标目录失败: [WinError 50] The request is not supported"
        path.mkdir(parents=True, exist_ok=True)
        return ""

    service = CloudScrapedLibraryService()
    monkeypatch.setattr(service, "_ensure_directory", fake_ensure_directory)

    result = service.run(
        AppContext.from_dict(
            {
                "action": "build_cloud_scraped_library",
                "path_pairs": [{"name": "tvshows", "source": str(workspace), "target": str(target)}],
                "cloud_library_output": {"wait_minutes": 0},
            }
        ),
        mock_logger,
    )

    assert result.status == "failed"
    assert any(record.action == "create_directory" and record.status == "failed" for record in result.records)
