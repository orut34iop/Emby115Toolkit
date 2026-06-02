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
            "action": "build_symlink_workspace",
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
    assert not (tmp_path / "target").exists()
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
        os.path.join("target", "柏林：抱银貂的女子 (2026)", "Season 1", video.name)
    )


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
