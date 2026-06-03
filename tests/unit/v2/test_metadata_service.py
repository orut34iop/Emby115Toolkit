from emby115_v2.context import AppContext
from emby115_v2.logging_setup import setup_run_logger
import urllib.error

from emby115_v2.services.metadata_service import (
    LlmConfigTestService,
    MetadataScraperService,
    TmdbClient,
    TmdbConfigTestService,
)


class FakeHttpResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.payload


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
        cast = [
            {
                "name": f"Actor {index:02d}",
                "character": f"Role {index:02d}",
                "order": index,
                "profile_path": f"/actor-{index:02d}.jpg",
            }
            for index in range(25)
        ]
        cast[0] = {
            "name": "Maggie Cheung",
            "character": "Ellen",
            "order": 0,
            "profile_path": "/maggie.jpg",
        }
        if language == "zh-CN":
            return {
                "id": tmdb_id,
                "title": "一见钟情",
                "original_title": "Sausalito",
                "release_date": "2000-04-20",
                "overview": "",
                "runtime": 98,
                "genres": [{"name": "爱情"}],
                "original_language": "en",
                "vote_average": 7.6,
                "belongs_to_collection": {"id": 100, "name": "Sausalito Collection"},
                "production_companies": [{"name": "Film Workshop"}],
                "production_countries": [{"name": "Hong Kong", "iso_3166_1": "HK"}],
                "spoken_languages": [{"english_name": "English", "iso_639_1": "en"}],
                "external_ids": {
                    "imdb_id": "tt0184030",
                    "tvdb_id": "12345",
                    "wikidata_id": "Q123",
                },
                "release_dates": {
                    "results": [
                        {
                            "iso_3166_1": "US",
                            "release_dates": [{"certification": "PG-13"}],
                        }
                    ]
                },
                "credits": {
                    "cast": cast,
                    "crew": [
                        {"name": "Andrew Lau", "job": "Director", "department": "Directing"},
                        {"name": "Writer A", "job": "Screenplay", "department": "Writing"},
                        {"name": "Producer A", "job": "Producer", "department": "Production"},
                    ],
                },
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
                "original_language": "en",
                "vote_average": 7.6,
                "belongs_to_collection": {"id": 100, "name": "Sausalito Collection"},
                "production_companies": [{"name": "Film Workshop"}],
                "production_countries": [{"name": "Hong Kong", "iso_3166_1": "HK"}],
                "spoken_languages": [{"english_name": "English", "iso_639_1": "en"}],
                "external_ids": {
                    "imdb_id": "tt0184030",
                    "tvdb_id": "12345",
                    "wikidata_id": "Q123",
                },
                "release_dates": {
                    "results": [
                        {
                            "iso_3166_1": "US",
                            "release_dates": [{"certification": "PG-13"}],
                        }
                    ]
                },
                "credits": {
                    "cast": cast,
                    "crew": [
                        {"name": "Andrew Lau", "job": "Director", "department": "Directing"},
                        {"name": "Writer A", "job": "Screenplay", "department": "Writing"},
                        {"name": "Producer A", "job": "Producer", "department": "Production"},
                    ],
                },
                "poster_path": "/poster.jpg",
                "backdrop_path": "/fanart.jpg",
            }

    def search_tv(self, query, language):
        self.search_calls.append((query, language))
        return [
            {
                "id": 9001,
                "name": "9号秘事",
                "original_name": "Inside No. 9",
                "first_air_date": "2014-02-05",
            }
        ]

    def tv_details(self, tmdb_id, language):
        self.detail_calls.append((tmdb_id, language))
        if language == "zh-CN":
            return {
                "id": tmdb_id,
                "name": "9号秘事",
                "original_name": "Inside No. 9",
                "first_air_date": "2014-02-05",
                "overview": "",
                "genres": [{"name": "喜剧"}, {"name": "悬疑"}],
                "original_language": "en",
                "vote_average": 8.5,
                "content_ratings": {"results": [{"iso_3166_1": "US", "rating": "TV-MA"}]},
                "production_companies": [{"name": "BBC"}],
                "production_countries": [{"name": "United Kingdom", "iso_3166_1": "GB"}],
                "spoken_languages": [{"english_name": "English", "iso_639_1": "en"}],
                "external_ids": {
                    "imdb_id": "tt2674806",
                    "tvdb_id": "278260",
                    "wikidata_id": "Q16906266",
                },
                "aggregate_credits": {
                    "cast": [
                        {
                            "name": "Reece Shearsmith",
                            "roles": [{"character": "Stuart"}, {"character": "A Stranger"}],
                            "order": 0,
                            "profile_path": "/reece.jpg",
                        }
                    ],
                    "crew": [
                        {
                            "name": "Director B",
                            "jobs": [{"job": "Director"}],
                            "department": "Directing",
                        },
                        {
                            "name": "Writer B",
                            "jobs": [{"job": "Writer"}],
                            "department": "Writing",
                        },
                        {
                            "name": "Producer B",
                            "jobs": [{"job": "Producer"}],
                            "department": "Production",
                        },
                    ],
                },
                "poster_path": "/tv-poster.jpg",
                "backdrop_path": "/tv-fanart.jpg",
            }
        return {
            "id": tmdb_id,
            "name": "Inside No. 9",
            "original_name": "Inside No. 9",
            "first_air_date": "2014-02-05",
                "overview": "Fallback show overview",
                "genres": [{"name": "Comedy"}],
                "original_language": "en",
                "vote_average": 8.5,
                "content_ratings": {"results": [{"iso_3166_1": "US", "rating": "TV-MA"}]},
                "production_companies": [{"name": "BBC"}],
                "production_countries": [{"name": "United Kingdom", "iso_3166_1": "GB"}],
                "spoken_languages": [{"english_name": "English", "iso_639_1": "en"}],
                "external_ids": {
                    "imdb_id": "tt2674806",
                    "tvdb_id": "278260",
                    "wikidata_id": "Q16906266",
                },
                "aggregate_credits": {
                    "cast": [
                        {
                            "name": "Reece Shearsmith",
                            "roles": [{"character": "Stuart"}, {"character": "A Stranger"}],
                            "order": 0,
                            "profile_path": "/reece.jpg",
                        }
                    ],
                    "crew": [
                        {
                            "name": "Director B",
                            "jobs": [{"job": "Director"}],
                            "department": "Directing",
                        },
                        {
                            "name": "Writer B",
                            "jobs": [{"job": "Writer"}],
                            "department": "Writing",
                        },
                        {
                            "name": "Producer B",
                            "jobs": [{"job": "Producer"}],
                            "department": "Production",
                        },
                    ],
                },
                "poster_path": "/tv-poster.jpg",
                "backdrop_path": "/tv-fanart.jpg",
            }

    def tv_episode_details(self, tmdb_id, season, episode, language):
        self.detail_calls.append((tmdb_id, season, episode, language))
        if language == "zh-CN":
            return {
                "name": "沙丁鱼",
                "overview": "",
                "air_date": "2014-02-05",
                "vote_average": 8.7,
                "still_path": "/episode-thumb.jpg",
            }
        return {
            "name": "Sardines",
            "overview": "Fallback episode overview",
            "air_date": "2014-02-05",
            "vote_average": 8.7,
            "still_path": "/episode-thumb.jpg",
        }

    def download_image(self, image_path, target_path, overwrite):
        self.download_calls.append((image_path, target_path, overwrite))
        target_path.write_text("image", encoding="utf-8")
        return "downloaded"


class FakeTmdbClientWithLlmRetry:
    def __init__(self):
        self.search_calls = []
        self.detail_calls = []

    def search_movie(self, query, language):
        return []

    def movie_details(self, tmdb_id, language):
        return {}

    def search_tv(self, query, language):
        self.search_calls.append((query, language))
        if query.title == "黒革の手帖":
            return [
                {
                    "id": 71151,
                    "name": "黑皮记事本",
                    "original_name": "黒革の手帖",
                    "first_air_date": "2017-07-20",
                }
            ]
        return []

    def tv_details(self, tmdb_id, language):
        self.detail_calls.append((tmdb_id, language))
        return {
            "id": tmdb_id,
            "name": "黑皮记事本",
            "original_name": "黒革の手帖",
            "first_air_date": "2017-07-20",
            "overview": "银行职员利用假账户购买银座俱乐部。",
            "genres": [{"name": "剧情"}],
            "poster_path": "",
            "backdrop_path": "",
        }

    def tv_episode_details(self, tmdb_id, season, episode, language):
        return {
            "name": "第一集",
            "overview": "第一集剧情。",
            "air_date": "2017-07-20",
            "still_path": "",
        }

    def download_image(self, image_path, target_path, overwrite):
        return "missing"


class FakeTmdbMovieClientWithLlmRetry:
    def __init__(self):
        self.search_calls = []
        self.detail_calls = []

    def search_movie(self, query, language):
        self.search_calls.append((query, language))
        if query.title == "The Devil Wears Prada 2":
            return [
                {
                    "id": 12345,
                    "title": "穿普拉达的女王2",
                    "original_title": "The Devil Wears Prada 2",
                    "release_date": "2026-05-01",
                }
            ]
        return []

    def movie_details(self, tmdb_id, language):
        self.detail_calls.append((tmdb_id, language))
        return {
            "id": tmdb_id,
            "title": "穿普拉达的女王2",
            "original_title": "The Devil Wears Prada 2",
            "release_date": "2026-05-01",
            "overview": "时尚杂志故事续篇。",
            "runtime": 110,
            "genres": [{"name": "喜剧"}],
            "poster_path": "",
            "backdrop_path": "",
        }

    def search_tv(self, query, language):
        return []

    def tv_details(self, tmdb_id, language):
        return {}

    def tv_episode_details(self, tmdb_id, season, episode, language):
        return {}

    def download_image(self, image_path, target_path, overwrite):
        return "missing"


class FakeLlmClient:
    def suggest_movie_queries(self, context, video_path, query):
        from emby115_v2.services.metadata_service import LlmMovieCandidate

        return [
            LlmMovieCandidate(
                title="The Devil Wears Prada 2",
                year="2026",
                confidence=0.96,
                reason="Chinese title maps to English original title.",
            )
        ]

    def suggest_tvshow_queries(self, context, show_dir, query, video_names):
        from emby115_v2.services.metadata_service import LlmTvShowCandidate

        return [
            LlmTvShowCandidate(
                title="黒革の手帖",
                year="2017",
                confidence=0.95,
                reason="Chinese title maps to Japanese original title.",
            )
        ]


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


def test_tmdb_client_retries_timed_out_json_request(monkeypatch):
    calls = []

    def fake_urlopen(url, timeout):
        calls.append((url, timeout))
        if len(calls) == 1:
            raise urllib.error.URLError("timed out")
        return FakeHttpResponse(b'{"results":[{"id":42}]}')

    monkeypatch.setattr("emby115_v2.services.metadata_service.urllib.request.urlopen", fake_urlopen)

    client = TmdbClient("key", timeout=1, retries=2)
    result = client.search_movie(type("Query", (), {"title": "Movie", "year": ""})(), "zh-CN")

    assert result == [{"id": 42}]
    assert len(calls) == 2


def test_tmdb_client_retries_timed_out_image_download(tmp_path, monkeypatch):
    calls = []

    def fake_urlopen(url, timeout):
        calls.append((url, timeout))
        if len(calls) == 1:
            raise urllib.error.URLError("timed out")
        return FakeHttpResponse(b"image")

    monkeypatch.setattr("emby115_v2.services.metadata_service.urllib.request.urlopen", fake_urlopen)

    target = tmp_path / "poster.jpg"
    client = TmdbClient("key", timeout=1, retries=2)
    status = client.download_image("/poster.jpg", target, overwrite=False)

    assert status == "downloaded"
    assert target.read_bytes() == b"image"
    assert len(calls) == 2


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
    assert result.records[0].extra["rating"] == 7.6
    assert result.records[0].extra["certification"] == "PG-13"
    assert result.records[0].extra["actor_count"] == 25
    assert result.records[0].extra["directors"] == ["Andrew Lau"]
    assert result.records[0].extra["writers"] == ["Writer A"]
    assert result.records[0].extra["producers"] == ["Producer A"]
    assert result.records[0].extra["external_ids"]["imdb_id"] == "tt0184030"
    assert result.records[0].extra["collection"]["name"] == "Sausalito Collection"
    assert result.records[0].extra["production_companies"] == ["Film Workshop"]
    assert result.records[0].extra["production_countries"] == ["Hong Kong"]
    assert result.records[0].extra["spoken_languages"] == ["English"]
    assert result.records[0].extra["original_language"] == "en"
    assert result.records[0].extra["release_date"] == "2000-04-20"
    assert nfo.exists()
    nfo_text = nfo.read_text(encoding="utf-8")
    assert "<title>一见钟情</title>" in nfo_text
    assert "<premiered>2000-04-20</premiered>" in nfo_text
    assert "<releasedate>2000-04-20</releasedate>" in nfo_text
    assert "<plot>Fallback overview</plot>" in nfo_text
    assert "<rating>7.6</rating>" in nfo_text
    assert "<mpaa>PG-13</mpaa>" in nfo_text
    assert '<uniqueid type="imdb" default="false">tt0184030</uniqueid>' in nfo_text
    assert '<uniqueid type="tvdb" default="false">12345</uniqueid>' in nfo_text
    assert '<uniqueid type="wikidata" default="false">Q123</uniqueid>' in nfo_text
    assert "<director>Andrew Lau</director>" in nfo_text
    assert "<credits>Writer A</credits>" in nfo_text
    assert "<producer>Producer A</producer>" in nfo_text
    assert "<name>Sausalito Collection</name>" in nfo_text
    assert "<studio>Film Workshop</studio>" in nfo_text
    assert "<country>Hong Kong</country>" in nfo_text
    assert "<language>English</language>" in nfo_text
    assert "<original_language>en</original_language>" in nfo_text
    assert "<name>Maggie Cheung</name>" in nfo_text
    assert "<role>Ellen</role>" in nfo_text
    assert "<name>Actor 24</name>" in nfo_text
    assert "<role>Role 24</role>" in nfo_text
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


def test_tvshow_metadata_writes_tvshow_and_episode_nfo_with_thumbs(tmp_path):
    library = tmp_path / "tvshows"
    show_dir = library / "Inside No. 9 (2014)"
    season_dir = show_dir / "Season 01"
    season_dir.mkdir(parents=True)
    video = season_dir / "Inside.No.9.S01E01.Sardines.1080p.mkv"
    video.write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "scrape_metadata",
            "dry_run": False,
            "metadata_output": {
                "media_type": "tvshows",
                "library_path": str(library),
                "download_images": True,
                "download_episode_thumbs": True,
                "auto_rename": True,
            },
            "tmdb": {"api_key": "key", "language": "zh-CN", "fallback_language": "en-US"},
            "symlink": {"video_extensions": [".mkv"]},
            "report": {"output_dir": str(tmp_path / "reports")},
            "logging": {"log_dir": str(tmp_path / "logs")},
        }
    )
    logger = setup_run_logger("test_tvshow_metadata", context.logging.log_dir, context.run_id)
    fake_tmdb = FakeTmdbClient()

    result = MetadataScraperService(tmdb_client=fake_tmdb).run(context, logger)

    renamed = library / "9号秘事 (2014)"
    tvshow_nfo = renamed / "tvshow.nfo"
    episode_nfo = renamed / "Season 01" / "Inside.No.9.S01E01.Sardines.1080p.nfo"
    thumb = renamed / "Season 01" / "Inside.No.9.S01E01.Sardines.1080p-thumb.jpg"
    assert result.status == "success"
    assert result.summary["matched"] == 2
    assert result.summary["auto_rename"]["renamed"] == 1
    assert tvshow_nfo.exists()
    assert episode_nfo.exists()
    assert thumb.exists()
    tvshow_text = tvshow_nfo.read_text(encoding="utf-8")
    episode_text = episode_nfo.read_text(encoding="utf-8")
    assert "<title>9号秘事</title>" in tvshow_text
    assert "<plot>Fallback show overview</plot>" in tvshow_text
    assert "<premiered>2014-02-05</premiered>" in tvshow_text
    assert '<uniqueid type="imdb" default="false">tt2674806</uniqueid>' in tvshow_text
    assert '<uniqueid type="tvdb" default="false">278260</uniqueid>' in tvshow_text
    assert '<uniqueid type="wikidata" default="false">Q16906266</uniqueid>' in tvshow_text
    assert "<director>Director B</director>" in tvshow_text
    assert "<credits>Writer B</credits>" in tvshow_text
    assert "<producer>Producer B</producer>" in tvshow_text
    assert "<studio>BBC</studio>" in tvshow_text
    assert "<country>United Kingdom</country>" in tvshow_text
    assert "<language>English</language>" in tvshow_text
    assert "<original_language>en</original_language>" in tvshow_text
    assert "<rating>8.5</rating>" in tvshow_text
    assert "<mpaa>TV-MA</mpaa>" in tvshow_text
    assert "<name>Reece Shearsmith</name>" in tvshow_text
    assert "<role>Stuart / A Stranger</role>" in tvshow_text
    assert "<title>沙丁鱼</title>" in episode_text
    assert "<plot>Fallback episode overview</plot>" in episode_text
    assert "<rating>8.7</rating>" in episode_text
    assert "<name>Reece Shearsmith</name>" in episode_text
    episode_record = next(record for record in result.records if record.target_path.endswith(episode_nfo.name))
    assert episode_record.extra["rating"] == 8.7
    assert episode_record.extra["actor_count"] == 1
    log_text = (context.logging.log_dir / f"{context.run_id}.log").read_text(encoding="utf-8")
    assert "开始电视剧元数据刮削" in log_text
    assert "正在刮削电视剧元数据 [1/1]" in log_text
    assert "电视剧匹配成功" in log_text
    assert "正在刮削单集元数据" in log_text
    assert "完成电视剧元数据 [1/1]" in log_text


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


def test_tvshow_uses_llm_alias_retry_when_tmdb_returns_no_candidates(tmp_path):
    library = tmp_path / "tvshows"
    show_dir = library / "黑皮记事本 (2017)"
    season_dir = show_dir / "Season 01"
    season_dir.mkdir(parents=True)
    (season_dir / "Kurokawa.no.Techou.S01E01.mkv").write_text("x", encoding="utf-8")
    context = AppContext.from_dict(
        {
            "action": "scrape_metadata",
            "dry_run": False,
            "metadata_output": {
                "media_type": "tvshows",
                "library_path": str(library),
                "download_images": False,
                "download_episode_thumbs": False,
                "auto_rename": True,
            },
            "tmdb": {"api_key": "key", "language": "zh-CN", "fallback_language": "en-US"},
            "llm": {
                "enabled": True,
                "base_url": "http://llm.local/v1",
                "api_key": "llm-key",
                "model": "test-model",
            },
            "symlink": {"video_extensions": [".mkv"]},
            "report": {"output_dir": str(tmp_path / "reports")},
            "logging": {"log_dir": str(tmp_path / "logs")},
        }
    )
    logger = setup_run_logger("test_tvshow_llm_retry", context.logging.log_dir, context.run_id)
    fake_tmdb = FakeTmdbClientWithLlmRetry()

    result = MetadataScraperService(tmdb_client=fake_tmdb, llm_client=FakeLlmClient()).run(context, logger)

    tvshow_nfo = show_dir / "tvshow.nfo"
    assert result.status == "success"
    assert result.summary["matched"] == 2
    assert result.summary["manual_review"] == 0
    assert tvshow_nfo.exists()
    assert "<title>黑皮记事本</title>" in tvshow_nfo.read_text(encoding="utf-8")
    assert [call[0].title for call in fake_tmdb.search_calls] == [
        "黑皮记事本",
        "黑皮记事本",
        "黒革の手帖",
    ]
    show_record = next(record for record in result.records if record.target_path == str(tvshow_nfo))
    assert show_record.extra["query"]["title"] == "黒革の手帖"
    assert show_record.extra["llm_resolution"]["status"] == "suggested"
    assert show_record.extra["llm_resolution"]["query_candidates"][0]["title"] == "黒革の手帖"


def test_movie_uses_llm_alias_retry_when_tmdb_returns_no_candidates(tmp_path):
    library = tmp_path / "movies"
    movie_dir = library / "穿普拉达的女王2 (2026)"
    movie_dir.mkdir(parents=True)
    video = movie_dir / "穿普拉达的女王2.2026.1080p.mkv"
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
            "llm": {
                "enabled": True,
                "base_url": "http://llm.local/v1",
                "api_key": "llm-key",
                "model": "test-model",
            },
            "symlink": {"video_extensions": [".mkv"]},
            "report": {"output_dir": str(tmp_path / "reports")},
            "logging": {"log_dir": str(tmp_path / "logs")},
        }
    )
    logger = setup_run_logger("test_movie_llm_retry", context.logging.log_dir, context.run_id)
    fake_tmdb = FakeTmdbMovieClientWithLlmRetry()

    result = MetadataScraperService(tmdb_client=fake_tmdb, llm_client=FakeLlmClient()).run(context, logger)

    nfo = movie_dir / "穿普拉达的女王2.2026.1080p.nfo"
    assert result.status == "success"
    assert result.summary["matched"] == 1
    assert result.summary["manual_review"] == 0
    assert nfo.exists()
    assert "<title>穿普拉达的女王2</title>" in nfo.read_text(encoding="utf-8")
    assert [call[0].title for call in fake_tmdb.search_calls] == [
        "穿普拉达的女王2",
        "穿普拉达的女王2",
        "The Devil Wears Prada 2",
    ]
    movie_record = next(record for record in result.records if record.target_path == str(nfo))
    assert movie_record.extra["query"]["title"] == "The Devil Wears Prada 2"
    assert movie_record.extra["llm_resolution"]["status"] == "suggested"
    assert movie_record.extra["llm_resolution"]["query_candidates"][0]["title"] == "The Devil Wears Prada 2"
