from emby115_v2.context import AppContext
from emby115_v2.logging_setup import setup_run_logger
from emby115_v2.services.metadata_service import LlmConfigTestService, MetadataScraperService, TmdbConfigTestService


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
            "symlink": {"video_extensions": [".mkv"]},
            "report": {"output_dir": str(tmp_path / "reports")},
            "logging": {"log_dir": str(tmp_path / "logs")},
        }
    )
    logger = setup_run_logger("test_metadata_scraper", context.logging.log_dir, context.run_id)

    result = MetadataScraperService().run(context, logger)

    assert result.status == "planned"
    assert result.summary["planned"] == 1
    assert result.records[0].source_path.endswith("Movie.Title.2026.mkv")
    assert result.records[0].target_path.endswith("Movie.Title.2026.nfo")
