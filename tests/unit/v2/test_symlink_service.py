import os
from unittest.mock import patch

from emby115_v2 import cancellation
from emby115_v2.context import AppContext
from emby115_v2.services.symlink_service import ScanAndLinkService


def _context(tmp_path, dry_run=False, auto_clear_workspace=True):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    (source / "Movie").mkdir()
    (source / "Movie" / "movie.mkv").write_text("x", encoding="utf-8")
    (source / "Movie" / "ignore.txt").write_text("x", encoding="utf-8")
    return AppContext.from_dict(
        {
            "action": "build_symlink_workspace",
            "dry_run": dry_run,
            "path_pairs": [{"name": "movies", "source": str(source), "target": str(target)}],
            "symlink": {
                "video_extensions": [".mkv"],
                "thread_count": 1,
                "auto_clear_workspace": auto_clear_workspace,
            },
        }
    )


def test_dry_run_plans_without_creating_links(tmp_path, mock_logger):
    context = _context(tmp_path, dry_run=True)

    result = ScanAndLinkService().run(context, mock_logger)

    assert result.status == "success"
    assert result.summary["planned"] == 1
    assert result.records[-1].status == "planned"
    assert not (tmp_path / "target").exists()
    assert not (tmp_path / "target" / "Movie" / "movie.mkv").exists()


def test_symlink_workspace_stops_when_cancel_requested(tmp_path, mock_logger):
    context = _context(tmp_path, dry_run=True)
    cancellation.request_cancel(context.run_id)
    try:
        result = ScanAndLinkService().run(context, mock_logger)
    finally:
        cancellation.clear_cancel(context.run_id)

    assert result.status == "canceled"
    assert result.summary["canceled"] is True
    assert result.records[-1].status == "canceled"


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


def test_run_allows_existing_empty_target_workspace(tmp_path, mock_logger):
    context = _context(tmp_path)
    (tmp_path / "target").mkdir()

    with patch("os.symlink") as mock_symlink:
        result = ScanAndLinkService().run(context, mock_logger)

    assert result.status == "success"
    assert result.summary["created"] == 1
    assert result.summary["workspace_precheck_failed"] == 0
    mock_symlink.assert_called_once()


def test_non_empty_target_workspace_fails_before_scan_plan_when_auto_clear_disabled(tmp_path, mock_logger):
    context = _context(tmp_path, auto_clear_workspace=False)
    existing = tmp_path / "target" / "Movie"
    existing.mkdir(parents=True)
    (existing / "movie.mkv").write_text("already here", encoding="utf-8")

    result = ScanAndLinkService().run(context, mock_logger)

    assert result.status == "failed"
    assert result.summary["workspace_precheck_failed"] == 1
    assert result.summary["failed"] == 1
    assert result.summary["planned"] == 0
    assert result.summary["created"] == 0
    assert result.records[0].action == "validate_target_workspace"
    assert result.records[0].status == "failed"
    assert "必须是空文件夹" in result.records[0].reason


def test_auto_clear_workspace_removes_existing_contents_before_creating_links(tmp_path, mock_logger):
    context = _context(tmp_path)
    stale_folder = tmp_path / "target" / "old"
    stale_folder.mkdir(parents=True)
    (stale_folder / "old.nfo").write_text("stale", encoding="utf-8")
    (tmp_path / "target" / "old.txt").write_text("stale", encoding="utf-8")

    with patch("os.symlink") as mock_symlink:
        result = ScanAndLinkService().run(context, mock_logger)

    assert result.status == "success"
    assert result.summary["workspace_cleared"] == 1
    assert result.summary["workspace_precheck_failed"] == 0
    assert not stale_folder.exists()
    assert not (tmp_path / "target" / "old.txt").exists()
    assert any(record.action == "clear_target_workspace" and record.status == "cleared" for record in result.records)
    mock_symlink.assert_called_once()


def test_auto_clear_workspace_dry_run_only_plans_clear(tmp_path, mock_logger):
    context = _context(tmp_path, dry_run=True)
    stale = tmp_path / "target" / "old.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text("stale", encoding="utf-8")

    result = ScanAndLinkService().run(context, mock_logger)

    assert result.status == "success"
    assert result.summary["workspace_clear_planned"] == 1
    assert result.summary["planned"] == 1
    assert stale.exists()
    assert result.records[0].action == "clear_target_workspace"
    assert result.records[0].status == "planned"


def test_auto_clear_workspace_refuses_to_clear_source_path(tmp_path, mock_logger):
    source = tmp_path / "source"
    source.mkdir()
    (source / "movie.mkv").write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "build_symlink_workspace",
            "path_pairs": [{"name": "movies", "source": str(source), "target": str(source)}],
            "symlink": {"video_extensions": [".mkv"], "thread_count": 1, "auto_clear_workspace": True},
        }
    )

    result = ScanAndLinkService().run(context, mock_logger)

    assert result.status == "failed"
    assert result.summary["workspace_clear_failed"] == 1
    assert result.summary["created"] == 0
    assert (source / "movie.mkv").exists()
    assert result.records[0].action == "clear_target_workspace"
    assert "拒绝自动清空" in result.records[0].reason


def test_auto_clear_workspace_does_not_resolve_virtual_drive_source(tmp_path, mock_logger, monkeypatch):
    context = _context(tmp_path)
    stale = tmp_path / "target" / "old.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text("stale", encoding="utf-8")

    def fail_resolve(self, strict=False):
        raise OSError("virtual drive resolve failed")

    monkeypatch.setattr("emby115_v2.services.symlink_service.Path.resolve", fail_resolve)

    with patch("os.symlink") as mock_symlink:
        result = ScanAndLinkService().run(context, mock_logger)

    assert result.status == "success"
    assert result.summary["workspace_cleared"] == 1
    assert not stale.exists()
    mock_symlink.assert_called_once()


def test_target_workspace_file_path_fails_precheck(tmp_path, mock_logger):
    context = _context(tmp_path)
    (tmp_path / "target").write_text("not a directory", encoding="utf-8")

    result = ScanAndLinkService().run(context, mock_logger)

    assert result.status == "failed"
    assert result.summary["workspace_precheck_failed"] == 1
    assert result.summary["created"] == 0
    assert result.records[0].action == "validate_target_workspace"
    assert "不是目录" in result.records[0].reason


def test_movie_standardizes_to_title_year_folder(tmp_path, mock_logger):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    (source / "mixed").mkdir()
    video = source / "mixed" / "一见钟情.Sausalito.2000.BD1080P.x265.mkv"
    video.write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "build_symlink_workspace",
            "dry_run": True,
            "path_pairs": [{"name": "movies", "source": str(source), "target": str(target)}],
            "symlink": {"video_extensions": [".mkv"], "thread_count": 1},
        }
    )

    result = ScanAndLinkService().run(context, mock_logger)

    record = result.records[-1]
    assert record.target_path.endswith(os.path.join("target", "一见钟情.Sausalito (2000)", video.name))
    assert record.title == "一见钟情.Sausalito"
    assert record.year == "2000"


def test_movie_standardization_strips_leading_bracket_before_year(tmp_path, mock_logger):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    video = source / "[恶灵空间2 2007][西班牙限量版蓝光原盘 DIY简中][22.18G].iso"
    video.write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "build_symlink_workspace",
            "dry_run": True,
            "path_pairs": [{"name": "movies", "source": str(source), "target": str(target)}],
            "symlink": {"video_extensions": [".iso"], "thread_count": 1},
        }
    )

    result = ScanAndLinkService().run(context, mock_logger)

    record = result.records[-1]
    assert record.target_path.endswith(os.path.join("target", "恶灵空间2 (2007)", video.name))
    assert record.title == "恶灵空间2"
    assert record.year == "2007"


def test_movie_prefers_parent_title_year_over_short_release_filename(tmp_path, mock_logger):
    source = tmp_path / "source"
    target = tmp_path / "target"
    release = source / "东方男孩Eastern.Boys.2013.1080p.BluRay.x264-FAPCAVE"
    release.mkdir(parents=True)
    video = release / "eb-1080p-fap.mkv"
    video.write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "build_symlink_workspace",
            "dry_run": True,
            "path_pairs": [{"name": "movies", "source": str(source), "target": str(target)}],
            "symlink": {"video_extensions": [".mkv"], "thread_count": 1},
        }
    )

    result = ScanAndLinkService().run(context, mock_logger)

    record = result.records[-1]
    assert record.target_path.endswith(os.path.join("target", "东方男孩Eastern.Boys (2013)", video.name))
    assert record.title == "东方男孩Eastern.Boys"
    assert record.year == "2013"


def test_movie_combines_chinese_parent_title_with_english_filename_title(tmp_path, mock_logger):
    source = tmp_path / "source"
    target = tmp_path / "target"
    release = source / "惊蛰无声 (2026)"
    release.mkdir(parents=True)
    video = release / "Scare Out.2026.2160p.SDR.50fps.WEB-DL.H265.Dolby Atmos 5.1.mkv"
    video.write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "build_symlink_workspace",
            "dry_run": True,
            "path_pairs": [{"name": "movies", "source": str(source), "target": str(target)}],
            "symlink": {"video_extensions": [".mkv"], "thread_count": 1},
        }
    )

    result = ScanAndLinkService().run(context, mock_logger)

    record = result.records[-1]
    assert record.target_path.endswith(os.path.join("target", "惊蛰无声.Scare Out (2026)", video.name))
    assert record.title == "惊蛰无声.Scare Out"
    assert record.year == "2026"


def test_movie_preserves_parent_title_when_it_already_contains_english_filename_title(tmp_path, mock_logger):
    source = tmp_path / "source"
    target = tmp_path / "target"
    release = (
        source
        / "莎拉·丝沃曼：生离笑别[简繁英字幕].Sarah.Silverman.PostMortem.2025.2160p.NF.WEB-DL"
    )
    release.mkdir(parents=True)
    video = release / "Sarah.Silverman.PostMortem.2025.2160p.NF.WEB-DL.mkv"
    video.write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "build_symlink_workspace",
            "dry_run": True,
            "path_pairs": [{"name": "movies", "source": str(source), "target": str(target)}],
            "symlink": {"video_extensions": [".mkv"], "thread_count": 1},
        }
    )

    result = ScanAndLinkService().run(context, mock_logger)

    record = result.records[-1]
    assert record.target_path.endswith(
        os.path.join("target", "莎拉·丝沃曼：生离笑别.Sarah.Silverman.PostMortem (2025)", video.name)
    )
    assert record.title == "莎拉·丝沃曼：生离笑别.Sarah.Silverman.PostMortem"
    assert record.year == "2025"


def test_tvshow_standardizes_under_series_and_season(tmp_path, mock_logger):
    source = tmp_path / "source"
    target = tmp_path / "target"
    series = source / "tvshow" / "低智商犯罪 (2026)"
    series.mkdir(parents=True)
    video = series / "低智商犯罪 (2026)S01E02.mp4"
    video.write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "build_symlink_workspace",
            "dry_run": True,
            "path_pairs": [{"name": "tvshows", "source": str(source), "target": str(target)}],
            "symlink": {"video_extensions": [".mp4"], "thread_count": 1},
        }
    )

    result = ScanAndLinkService().run(context, mock_logger)

    record = result.records[-1]
    assert record.target_path.endswith(os.path.join("target", "低智商犯罪 (2026)", "Season 01", video.name))
    assert record.title == "低智商犯罪"
    assert record.year == "2026"
    assert record.season == "01"
    assert record.episode == "02"


def test_tvshow_derives_season_folder_from_episode_filename(tmp_path, mock_logger):
    source = tmp_path / "source"
    target = tmp_path / "target"
    series = source / "tvshow" / "Girigo：夺命许愿 (2026)(1)"
    series.mkdir(parents=True)
    video = series / "If Wishes Could Kill.S01E01.2160p.DV.H.265.DDP 5.1 Atmos.mkv"
    video.write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "build_symlink_workspace",
            "dry_run": True,
            "path_pairs": [{"name": "tvshows", "source": str(source), "target": str(target)}],
            "symlink": {"video_extensions": [".mkv"], "thread_count": 1},
        }
    )

    result = ScanAndLinkService().run(context, mock_logger)

    assert result.records[-1].target_path.endswith(
        os.path.join(
            "target",
            "Girigo：夺命许愿 (2026)",
            "If Wishes Could Kill.S01.2160p.DV.H.265.DDP 5.1 Atmos",
            video.name,
        )
    )


def test_tvshow_simple_episode_filename_falls_back_to_season_folder(tmp_path, mock_logger):
    source = tmp_path / "source"
    target = tmp_path / "target"
    series = source / "tvshow" / "低智商犯罪 (2026)"
    series.mkdir(parents=True)
    video = series / "低智商犯罪.S01E01.mkv"
    video.write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "build_symlink_workspace",
            "dry_run": True,
            "path_pairs": [{"name": "tvshows", "source": str(source), "target": str(target)}],
            "symlink": {"video_extensions": [".mkv"], "thread_count": 1},
        }
    )

    result = ScanAndLinkService().run(context, mock_logger)

    assert result.records[-1].target_path.endswith(os.path.join("target", "低智商犯罪 (2026)", "Season 01", video.name))


def test_tvshow_drops_episode_title_when_deriving_release_folder(tmp_path, mock_logger):
    source = tmp_path / "source"
    target = tmp_path / "target"
    series = source / "tvshow" / "Inside No. 9 (2014)"
    series.mkdir(parents=True)
    video = series / "Inside.No.9.S01E01.Sardines.1080i.BluRay.REMUX.AVC.mkv"
    video.write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "build_symlink_workspace",
            "dry_run": True,
            "path_pairs": [{"name": "tvshows", "source": str(source), "target": str(target)}],
            "symlink": {"video_extensions": [".mkv"], "thread_count": 1},
        }
    )

    result = ScanAndLinkService().run(context, mock_logger)

    assert result.records[-1].target_path.endswith(
        os.path.join("target", "Inside No. 9 (2014)", "Inside.No.9.S01.1080i.BluRay.REMUX.AVC", video.name)
    )


def test_tvshow_preserves_version_season_folder(tmp_path, mock_logger):
    source = tmp_path / "source"
    target = tmp_path / "target"
    version = source / "tvshow" / "柏林：抱银貂的女子 (2026)" / "Season 1"
    version.mkdir(parents=True)
    video = version / "Berlin and the Lady with an Ermine.S01E01.2160p.mkv"
    video.write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "build_symlink_workspace",
            "dry_run": True,
            "path_pairs": [{"name": "tvshows", "source": str(source), "target": str(target)}],
            "symlink": {"video_extensions": [".mkv"], "thread_count": 1},
        }
    )

    result = ScanAndLinkService().run(context, mock_logger)

    assert result.records[-1].target_path.endswith(
        os.path.join("target", "柏林：抱银貂的女子 (2026)", "Season 01", video.name)
    )


def test_tvshow_normalizes_chinese_season_folder_to_english_season(tmp_path, mock_logger):
    source = tmp_path / "source"
    target = tmp_path / "target"
    season_dir = source / "tvshow" / "失踪 (2014)" / "第一季"
    season_dir.mkdir(parents=True)
    video = season_dir / "失踪.S01E07.Return.to.Eden.BluRay.1080i.DTS-HD.MA.2.0.AVC.REMUX-FraMeSToR.mkv"
    video.write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "build_symlink_workspace",
            "dry_run": True,
            "path_pairs": [{"name": "tvshows", "source": str(source), "target": str(target)}],
            "symlink": {"video_extensions": [".mkv"], "thread_count": 1},
        }
    )

    result = ScanAndLinkService().run(context, mock_logger)

    record = result.records[-1]
    assert record.target_path.endswith(os.path.join("target", "失踪 (2014)", "Season 01", video.name))
    assert record.season == "01"
    assert record.episode == "07"


def test_tvshow_episode_filename_does_not_become_series_folder(tmp_path, mock_logger):
    source = tmp_path / "source"
    target = tmp_path / "target"
    season_dir = source / "[小镇疑云 1-3季][1080P蓝光Remux][内封简英双语字幕]" / "S02"
    season_dir.mkdir(parents=True)
    video = season_dir / "小镇疑云.S02E01.Episode.1.1080i.BluRay.REMUX.AVC.DTS.5.1-Gz.mkv"
    video.write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "build_symlink_workspace",
            "dry_run": True,
            "path_pairs": [{"name": "tvshows", "source": str(source), "target": str(target)}],
            "symlink": {"video_extensions": [".mkv"], "thread_count": 1},
        }
    )

    result = ScanAndLinkService().run(context, mock_logger)

    record = result.records[-1]
    assert record.target_path.endswith(os.path.join("target", "小镇疑云", "Season 02", video.name))
    assert record.title == "小镇疑云"
    assert record.season == "02"
    assert record.episode == "01"


def test_tvshow_ignores_quality_only_source_folder_for_second_level(tmp_path, mock_logger):
    source = tmp_path / "source"
    target = tmp_path / "target"
    version = source / "tvshow" / "黑夜告白 (2026)完结" / "4K SDR 60帧 高码率"
    version.mkdir(parents=True)
    video = version / "Light to the Night.S01E10.2160p.SDR.60fps.H265.10bit.DTS 5.1.mkv"
    video.write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "build_symlink_workspace",
            "dry_run": True,
            "path_pairs": [{"name": "tvshows", "source": str(source), "target": str(target)}],
            "symlink": {"video_extensions": [".mkv"], "thread_count": 1},
        }
    )

    result = ScanAndLinkService().run(context, mock_logger)

    assert result.records[-1].target_path.endswith(
        os.path.join(
            "target",
            "黑夜告白 (2026)",
            "Light to the Night.S01.2160p.SDR.60fps.H265.10bit.DTS 5.1",
            video.name,
        )
    )


def test_unrecognized_tvshow_stays_in_original_relative_path_for_review(tmp_path, mock_logger):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    video = source / "unknown-video.mkv"
    video.write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "build_symlink_workspace",
            "dry_run": True,
            "path_pairs": [{"name": "tvshows", "source": str(source), "target": str(target)}],
            "symlink": {"video_extensions": [".mkv"], "thread_count": 1},
        }
    )

    result = ScanAndLinkService().run(context, mock_logger)

    record = result.records[-1]
    assert record.status == "manual_review"
    assert record.target_path.endswith(os.path.join("target", video.name))
    assert result.summary["manual_review"] == 1
