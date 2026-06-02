from emby115_v2.context import AppContext
from emby115_v2.logging_setup import setup_run_logger
from emby115_v2.services.metadata_service import LlmConfigTestService, MetadataScraperService, TmdbConfigTestService


class FakeTmdbClient:
    def __init__(self):
        self.search_calls = []
        self.detail_calls = []
        self.download_calls = []

    def search_movie(self, query, language):
        self.search_calls.append((query, language))
        if language == "zh-CN":
            return [
                {
                    "id": 42,
                    "title": "一见钟情",
                    "original_title": "Sausalito",
                    "release_date": "2000-04-20",
                }
            ]
        return []

    def movie_details(self, tmdb_id, language):
        self.detail_calls.append((tmdb_id, language))
        if language == "zh-CN":
            return {
                "id": tmdb_id,
                "title": "一见钟情",
                "original_title": "Sausalito",
                "release_date": "2000-04-20",
                "overview": "",
                "runtime": 98,
                "genres": [{"name": "爱情"}],
                "poster_path": "/poster.jpg",
                "backdrop_path": "/fanart.jpg",
            }
        return {
            "id": tmdb_id,
            "title": "Sausalito",
            "original_title": "Sausalito",
            "release_date": "2000-04-20",
            "overview": "Fallback overview",
            "runtime": 98,
            "genres": [{"name": "Romance"}],
            "poster_path": "/poster.jpg",
            "backdrop_path": "/fanart.jpg",
        }

    def download_image(self, image_path, target_path, overwrite):
        self.download_calls.append((image_path, target_path, overwrite))
        target_path.write_text("image", encoding="utf-8")
        return "downloaded"


def test_tmdb_config_test_reports_missing_api_key(tmp_path):
    context = AppContext.from_dict(
        {
            "action": "test_tmdb_config",
            "report": {"output_dir": str(tmp_path / "reports")},
            "logging": {"log_dir": str(tmp_path / "logs")},
        }
    )
    logger = setup_run_logger("test_tmdb_config", context.logging.log_dir, context.run_id)

    result = TmdbConfigTestService().run(context, logger)

    assert result.status == "failed"
    assert result.summary["ok"] is False
    assert "API Key" in result.summary["reason"]


def test_llm_config_test_reports_missing_required_fields(tmp_path):
    context = AppContext.from_dict(
        {
            "action": "test_llm_config",
            "llm": {"enabled": True},
            "report": {"output_dir": str(tmp_path / "reports")},
            "logging": {"log_dir": str(tmp_path / "logs")},
        }
    )
    logger = setup_run_logger("test_llm_config", context.logging.log_dir, context.run_id)

    result = LlmConfigTestService().run(context, logger)

    assert result.status == "failed"
    assert "base_url" in result.summary["reason"]
    assert "api_key" in result.summary["reason"]
    assert "model" in result.summary["reason"]


def test_metadata_scraper_dry_run_scans_library_without_writing(tmp_path):
    library = tmp_path / "movies"
    library.mkdir()
    (library / "Movie.Title.2026.mkv").write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "scrape_metadata",
            "dry_run": True,
            "metadata_output": {"media_type": "movies", "library_path": str(library)},
            "tmdb": {"api_key": "key"},
            "symlink": {"video_extensions": [".mkv"]},
            "report": {"output_dir": str(tmp_path / "reports")},
            "logging": {"log_dir": str(tmp_path / "logs")},
        }
    )
    logger = setup_run_logger("test_metadata_scraper", context.logging.log_dir, context.run_id)

    fake_tmdb = FakeTmdbClient()
    result = MetadataScraperService(tmdb_client=fake_tmdb).run(context, logger)

    assert result.status == "success"
    assert result.summary["matched"] == 1
    assert result.records[0].source_path.endswith("Movie.Title.2026.mkv")
    assert result.records[0].target_path.endswith("Movie.Title.2026.nfo")
    assert result.records[0].status == "planned"
    assert not (library / "Movie.Title.2026.nfo").exists()


def test_movie_metadata_writes_video_stem_nfo_and_uses_fallback_details(tmp_path):
    library = tmp_path / "movies"
    movie_dir = library / "一见钟情 (2000)"
    movie_dir.mkdir(parents=True)
    video = movie_dir / "一见钟情.Sausalito.2000.BD1080P.mkv"
    video.write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "scrape_metadata",
            "dry_run": False,
            "metadata_output": {
                "media_type": "movies",
                "library_path": str(library),
                "download_images": True,
            },
            "tmdb": {"api_key": "key", "language": "zh-CN", "fallback_language": "en-US"},
            "symlink": {"video_extensions": [".mkv"]},
            "report": {"output_dir": str(tmp_path / "reports")},
            "logging": {"log_dir": str(tmp_path / "logs")},
        }
    )
    logger = setup_run_logger("test_metadata_writer", context.logging.log_dir, context.run_id)
    fake_tmdb = FakeTmdbClient()

    result = MetadataScraperService(tmdb_client=fake_tmdb).run(context, logger)

    nfo = movie_dir / "一见钟情.Sausalito.2000.BD1080P.nfo"
    assert result.status == "success"
    assert result.records[0].status == "written"
    assert result.records[0].extra["tmdb_id"] == 42
    assert result.records[0].extra["fallback_used"] is True
    assert nfo.exists()
    assert "<title>一见钟情</title>" in nfo.read_text(encoding="utf-8")
    assert "<plot>Fallback overview</plot>" in nfo.read_text(encoding="utf-8")
    assert (movie_dir / "一见钟情.Sausalito.2000.BD1080P-poster.jpg").exists()


def test_movie_metadata_auto_renames_first_level_folder_from_nfo(tmp_path):
    library = tmp_path / "movies"
    movie_dir = library / "The Devil Wears Prada 2 (2026)"
    movie_dir.mkdir(parents=True)
    video = movie_dir / "The Devil Wears Prada 2.2026.1080p.mkv"
    video.write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "scrape_metadata",
            "dry_run": False,
            "metadata_output": {
                "media_type": "movies",
                "library_path": str(library),
                "download_images": False,
                "auto_rename": True,
            },
            "tmdb": {"api_key": "key", "language": "zh-CN", "fallback_language": "en-US"},
            "symlink": {"video_extensions": [".mkv"]},
            "report": {"output_dir": str(tmp_path / "reports")},
            "logging": {"log_dir": str(tmp_path / "logs")},
        }
    )
    logger = setup_run_logger("test_metadata_auto_rename", context.logging.log_dir, context.run_id)
    fake_tmdb = FakeTmdbClient()

    result = MetadataScraperService(tmdb_client=fake_tmdb).run(context, logger)

    renamed = library / "一见钟情 (2000)"
    assert result.summary["auto_rename"]["renamed"] == 1
    assert renamed.exists()
    assert not movie_dir.exists()
    assert (renamed / "The Devil Wears Prada 2.2026.1080p.nfo").exists()
    assert result.records[0].extra["auto_rename"]["target_path"] == str(renamed)


def test_movie_auto_rename_merges_when_target_folder_exists(tmp_path):
    library = tmp_path / "movies"
    wrong_dir = library / "[恶灵空间2 (2007)"
    right_dir = library / "恶灵空间2 (2007)"
    wrong_dir.mkdir(parents=True)
    right_dir.mkdir(parents=True)
    (wrong_dir / "[恶灵空间2 2007][22.18G].nfo").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<movie>
  <title>恶灵空间2</title>
  <year>2007</year>
</movie>
""",
        encoding="utf-8",
    )
    (wrong_dir / "[恶灵空间2 2007][22.18G].iso").write_text("x", encoding="utf-8")
    (right_dir / "Boogeyman 2.2007.1080p.mkv").write_text("y", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "scrape_metadata",
            "dry_run": False,
            "metadata_output": {
                "media_type": "movies",
                "library_path": str(library),
                "auto_rename": True,
            },
            "report": {"output_dir": str(tmp_path / "reports")},
            "logging": {"log_dir": str(tmp_path / "logs")},
        }
    )
    logger = setup_run_logger("test_movie_auto_rename_merge", context.logging.log_dir, context.run_id)

    from emby115_v2.services.metadata_service import auto_rename_folder_from_nfo

    result = auto_rename_folder_from_nfo(
        wrong_dir,
        wrong_dir / "[恶灵空间2 2007][22.18G].nfo",
        "movie",
        context.dry_run,
        logger,
    )

    assert result["status"] == "merged"
    assert not wrong_dir.exists()
    assert (right_dir / "[恶灵空间2 2007][22.18G].nfo").exists()
    assert (right_dir / "[恶灵空间2 2007][22.18G].iso").exists()
    assert (right_dir / "Boogeyman 2.2007.1080p.mkv").exists()


def test_tvshow_auto_renames_first_level_folder_from_tvshow_nfo(tmp_path):
    library = tmp_path / "tvshows"
    show_dir = library / "Inside.No.9"
    show_dir.mkdir(parents=True)
    (show_dir / "tvshow.nfo").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<tvshow>
  <title>9号秘事</title>
  <year>2014</year>
</tvshow>
""",
        encoding="utf-8",
    )
    (show_dir / "S01E01.mkv").write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "scrape_metadata",
            "dry_run": False,
            "metadata_output": {
                "media_type": "tvshows",
                "library_path": str(library),
                "auto_rename": True,
            },
            "symlink": {"video_extensions": [".mkv"]},
            "report": {"output_dir": str(tmp_path / "reports")},
            "logging": {"log_dir": str(tmp_path / "logs")},
        }
    )
    logger = setup_run_logger("test_tvshow_auto_rename", context.logging.log_dir, context.run_id)

    result = MetadataScraperService().run(context, logger)

    renamed = library / "9号秘事 (2014)"
    assert result.summary["auto_rename"]["renamed"] == 1
    assert renamed.exists()
    assert not show_dir.exists()
    assert any(record.action == "auto_rename" and record.target_path == str(renamed) for record in result.records)
