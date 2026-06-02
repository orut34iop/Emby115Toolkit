from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from emby115_v2.context import AppContext
from emby115_v2.reports.writer import OperationRecord, StepResult


TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/original"
TMDB_REQUEST_RETRIES = 3
INVALID_WINDOWS_NAME_CHARS = r'<>:"/\|?*'


@dataclass(frozen=True)
class MovieQuery:
    title: str
    year: str = ""


@dataclass(frozen=True)
class TvShowQuery:
    title: str
    year: str = ""


@dataclass(frozen=True)
class LlmTvShowCandidate:
    title: str
    year: str = ""
    confidence: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class LlmMovieCandidate:
    title: str
    year: str = ""
    confidence: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class ActorMetadata:
    name: str
    role: str = ""
    order: int = 0
    profile_path: str = ""


@dataclass(frozen=True)
class MovieMetadata:
    tmdb_id: int
    title: str
    original_title: str = ""
    year: str = ""
    overview: str = ""
    runtime: int = 0
    genres: tuple[str, ...] = ()
    rating: float = 0.0
    certification: str = ""
    actors: tuple[ActorMetadata, ...] = ()
    poster_path: str = ""
    backdrop_path: str = ""
    language: str = ""
    fallback_used: bool = False


@dataclass(frozen=True)
class TvShowMetadata:
    tmdb_id: int
    title: str
    original_title: str = ""
    year: str = ""
    overview: str = ""
    genres: tuple[str, ...] = ()
    rating: float = 0.0
    certification: str = ""
    actors: tuple[ActorMetadata, ...] = ()
    poster_path: str = ""
    backdrop_path: str = ""
    language: str = ""
    fallback_used: bool = False


@dataclass(frozen=True)
class EpisodeMetadata:
    title: str
    season: int
    episode: int
    overview: str = ""
    air_date: str = ""
    rating: float = 0.0
    still_path: str = ""
    fallback_used: bool = False


class TmdbConfigTestService:
    def run(self, context: AppContext, logger: logging.Logger) -> StepResult:
        started = time.perf_counter()
        if not context.tmdb.api_key:
            return StepResult(
                step_id="test_tmdb_config",
                status="failed",
                summary={"ok": False, "reason": "TMDB API Key 未配置"},
                records=[
                    OperationRecord(
                        action="test_tmdb_config",
                        status="failed",
                        reason="TMDB API Key 未配置",
                    )
                ],
            )

        params = urllib.parse.urlencode({"api_key": context.tmdb.api_key})
        url = f"https://api.themoviedb.org/3/configuration?{params}"
        try:
            with urllib.request.urlopen(url, timeout=context.tmdb.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            logger.info("TMDB 配置测试成功 elapsed_ms=%s", elapsed_ms)
            return StepResult(
                step_id="test_tmdb_config",
                status="success",
                summary={
                    "ok": True,
                    "elapsed_ms": elapsed_ms,
                    "language": context.tmdb.language,
                    "fallback_language": context.tmdb.fallback_language,
                    "secure_base_url": data.get("images", {}).get("secure_base_url", ""),
                },
                records=[
                    OperationRecord(
                        action="test_tmdb_config",
                        status="success",
                        reason=f"TMDB 配置可用，耗时 {elapsed_ms}ms",
                    )
                ],
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            logger.warning("TMDB 配置测试失败: %s", exc)
            return StepResult(
                step_id="test_tmdb_config",
                status="failed",
                summary={"ok": False, "elapsed_ms": elapsed_ms, "reason": str(exc)},
                records=[
                    OperationRecord(
                        action="test_tmdb_config",
                        status="failed",
                        reason=str(exc),
                    )
                ],
            )


class LlmConfigTestService:
    def run(self, context: AppContext, logger: logging.Logger) -> StepResult:
        started = time.perf_counter()
        if not context.llm.enabled:
            return StepResult(
                step_id="test_llm_config",
                status="skipped",
                summary={"ok": False, "reason": "LLM 未启用"},
                records=[OperationRecord(action="test_llm_config", status="skipped", reason="LLM 未启用")],
            )
        missing = [
            name
            for name, value in {
                "base_url": context.llm.base_url,
                "api_key": context.llm.api_key,
                "model": context.llm.model,
            }.items()
            if not value
        ]
        if missing:
            reason = f"LLM 配置缺失: {', '.join(missing)}"
            return StepResult(
                step_id="test_llm_config",
                status="failed",
                summary={"ok": False, "reason": reason},
                records=[OperationRecord(action="test_llm_config", status="failed", reason=reason)],
            )

        url = context.llm.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": context.llm.model,
            "temperature": context.llm.temperature,
            "messages": [
                {
                    "role": "system",
                    "content": "Return compact JSON only.",
                },
                {
                    "role": "user",
                    "content": (
                        'Choose candidate 1 and return {"selected_index":1,'
                        '"confidence":0.99,"reason":"config test"}'
                    ),
                },
            ],
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {context.llm.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=context.llm.timeout) as response:
                raw = response.read().decode("utf-8")
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            logger.info("LLM 配置测试成功 elapsed_ms=%s", elapsed_ms)
            return StepResult(
                step_id="test_llm_config",
                status="success",
                summary={
                    "ok": True,
                    "elapsed_ms": elapsed_ms,
                    "provider": context.llm.provider,
                    "model": context.llm.model,
                    "response_preview": raw[:500],
                },
                records=[
                    OperationRecord(
                        action="test_llm_config",
                        status="success",
                        reason=f"LLM 配置可用，耗时 {elapsed_ms}ms",
                    )
                ],
            )
        except (urllib.error.URLError, TimeoutError) as exc:
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            logger.warning("LLM 配置测试失败: %s", exc)
            return StepResult(
                step_id="test_llm_config",
                status="failed",
                summary={"ok": False, "elapsed_ms": elapsed_ms, "reason": str(exc)},
                records=[OperationRecord(action="test_llm_config", status="failed", reason=str(exc))],
            )


class TmdbClient:
    def __init__(self, api_key: str, timeout: float = 10.0, retries: int = TMDB_REQUEST_RETRIES):
        self.api_key = api_key
        self.timeout = timeout
        self.retries = max(1, retries)

    def search_movie(self, query: MovieQuery, language: str) -> list[dict[str, Any]]:
        params = {
            "api_key": self.api_key,
            "language": language,
            "query": query.title,
            "include_adult": "false",
        }
        if query.year:
            params["year"] = query.year
        data = self._get("/search/movie", params)
        return list(data.get("results", []))

    def movie_details(self, tmdb_id: int, language: str) -> dict[str, Any]:
        return self._get(
            f"/movie/{tmdb_id}",
            {
                "api_key": self.api_key,
                "language": language,
                "append_to_response": "credits,release_dates",
            },
        )

    def search_tv(self, query: TvShowQuery, language: str) -> list[dict[str, Any]]:
        params = {
            "api_key": self.api_key,
            "language": language,
            "query": query.title,
            "include_adult": "false",
        }
        if query.year:
            params["first_air_date_year"] = query.year
        data = self._get("/search/tv", params)
        return list(data.get("results", []))

    def tv_details(self, tmdb_id: int, language: str) -> dict[str, Any]:
        return self._get(
            f"/tv/{tmdb_id}",
            {
                "api_key": self.api_key,
                "language": language,
                "append_to_response": "credits,content_ratings",
            },
        )

    def tv_episode_details(self, tmdb_id: int, season: int, episode: int, language: str) -> dict[str, Any]:
        return self._get(
            f"/tv/{tmdb_id}/season/{season}/episode/{episode}",
            {"api_key": self.api_key, "language": language},
        )

    def download_image(self, image_path: str, target_path: Path, overwrite: bool) -> str:
        if not image_path:
            return "missing"
        if target_path.exists() and not overwrite:
            return "skipped_existing"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(self._urlopen_with_retry(TMDB_IMAGE_BASE + image_path))
        return "downloaded"

    def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        url = TMDB_API_BASE + endpoint + "?" + urllib.parse.urlencode(params)
        return json.loads(self._urlopen_with_retry(url).decode("utf-8"))

    def _urlopen_with_retry(self, url: str) -> bytes:
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                with urllib.request.urlopen(url, timeout=self.timeout) as response:
                    return response.read()
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in {408, 429, 500, 502, 503, 504} or attempt == self.retries:
                    raise
            except (TimeoutError, urllib.error.URLError) as exc:
                last_error = exc
                if attempt == self.retries:
                    raise
            time.sleep(min(0.2 * attempt, 1.0))
        if last_error:
            raise last_error
        raise RuntimeError("TMDB 请求失败")


class OpenAICompatibleLlmClient:
    def suggest_movie_queries(
        self,
        context: AppContext,
        video_path: Path,
        query: MovieQuery,
    ) -> list[LlmMovieCandidate]:
        url = context.llm.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": context.llm.model,
            "temperature": context.llm.temperature,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You identify movie titles for TMDB search. "
                        "Return compact JSON only, no markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": "TMDB movie search returned no result. Infer alternative titles.",
                            "expected_schema": {
                                "candidates": [
                                    {
                                        "title": "string, original/localized/English title for TMDB search",
                                        "year": "optional 4 digit release year",
                                        "confidence": "0.0-1.0",
                                        "reason": "short audit reason",
                                    }
                                ]
                            },
                            "folder_name": video_path.parent.name,
                            "video_name": video_path.name,
                            "parsed_query": query.__dict__,
                            "rules": [
                                "Prefer official original titles when the folder title may be localized.",
                                "Keep the provided year when it is likely correct.",
                                "Return at most five candidates.",
                            ],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {context.llm.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=context.llm.timeout) as response:
            raw = response.read().decode("utf-8")
        data = json.loads(raw)
        content = str(data.get("choices", [{}])[0].get("message", {}).get("content", ""))
        return parse_llm_movie_candidates(content, fallback_year=query.year)

    def suggest_tvshow_queries(
        self,
        context: AppContext,
        show_dir: Path,
        query: TvShowQuery,
        video_names: list[str],
    ) -> list[LlmTvShowCandidate]:
        url = context.llm.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": context.llm.model,
            "temperature": context.llm.temperature,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You identify TV show titles for TMDB search. "
                        "Return compact JSON only, no markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": "TMDB TV search returned no result. Infer alternative titles.",
                            "expected_schema": {
                                "candidates": [
                                    {
                                        "title": "string, original/localized/English title for TMDB search",
                                        "year": "optional 4 digit first air year",
                                        "confidence": "0.0-1.0",
                                        "reason": "short audit reason",
                                    }
                                ]
                            },
                            "folder_name": show_dir.name,
                            "parsed_query": query.__dict__,
                            "sample_video_names": video_names[:20],
                            "rules": [
                                "Prefer official original titles when the folder title may be localized.",
                                "Keep the provided year when it is likely correct.",
                                "Return at most five candidates.",
                            ],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {context.llm.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=context.llm.timeout) as response:
            raw = response.read().decode("utf-8")
        data = json.loads(raw)
        content = str(data.get("choices", [{}])[0].get("message", {}).get("content", ""))
        return parse_llm_tvshow_candidates(content, fallback_year=query.year)


class MetadataScraperService:
    def __init__(self, tmdb_client: TmdbClient | None = None, llm_client: OpenAICompatibleLlmClient | None = None):
        self.tmdb_client = tmdb_client
        self.llm_client = llm_client

    def run(self, context: AppContext, logger: logging.Logger) -> StepResult:
        library_path = context.metadata_output.library_path
        configured_library = str(context.raw.get("metadata_output", {}).get("library_path", "")).strip()
        if not configured_library:
            return StepResult(
                step_id="scrape_metadata",
                status="failed",
                summary={"planned": 0, "reason": "媒体库目录未配置"},
                records=[
                    OperationRecord(
                        action="scrape_metadata",
                        status="failed",
                        media_type=context.metadata_output.media_type,
                        reason="媒体库目录未配置",
                    )
                ],
            )
        if not library_path.exists():
            return StepResult(
                step_id="scrape_metadata",
                status="failed",
                summary={"planned": 0, "library_path": str(library_path), "reason": "媒体库目录不存在"},
                records=[
                    OperationRecord(
                        action="scrape_metadata",
                        status="failed",
                        source_path=str(library_path),
                        media_type=context.metadata_output.media_type,
                        reason="媒体库目录不存在",
                    )
                ],
            )

        if context.metadata_output.media_type == "tvshows":
            return self._run_tvshows_skeleton(context, logger, library_path)
        return self._run_movies(context, logger, library_path)

    def _run_movies(self, context: AppContext, logger: logging.Logger, library_path: Path) -> StepResult:
        records = []
        extensions = set(context.symlink.video_extensions)
        for video_path in iter_video_files(library_path, extensions):
            records.append(self._process_movie(context, video_path, logger))
        rename_summary = auto_rename_from_movie_records(context, records, logger)

        matched = sum(1 for record in records if record.status in {"planned", "written", "skipped_existing"})
        manual_review = sum(1 for record in records if record.status == "manual_review")
        failed = sum(1 for record in records if record.status == "failed") + rename_summary.get("failed", 0)
        logger.info("电影元数据刮削完成 library=%s matched=%s manual_review=%s", library_path, matched, manual_review)
        return StepResult(
            step_id="scrape_metadata",
            status="success" if failed == 0 else "partial",
            summary={
                "media_type": "movies",
                "library_path": str(library_path),
                "dry_run": context.dry_run,
                "scanned": len(records),
                "matched": matched,
                "manual_review": manual_review,
                "failed": failed,
                "tmdb_language": context.tmdb.language,
                "tmdb_fallback_language": context.tmdb.fallback_language,
                "llm_enabled": context.llm.enabled,
                "auto_rename": rename_summary,
            },
            records=records,
        )

    def _run_tvshows_skeleton(self, context: AppContext, logger: logging.Logger, library_path: Path) -> StepResult:
        records = []
        for show_dir in direct_child_dirs(library_path):
            records.extend(self._process_tvshow(context, show_dir, logger))
        rename_summary = auto_rename_tvshow_folders(context, library_path, records, logger)
        matched = sum(1 for record in records if record.status in {"planned", "written", "skipped_existing"})
        manual_review = sum(1 for record in records if record.status == "manual_review")
        failed = sum(1 for record in records if record.status == "failed") + rename_summary.get("failed", 0)
        logger.info("电视剧元数据刮削完成 library=%s matched=%s manual_review=%s", library_path, matched, manual_review)
        return StepResult(
            step_id="scrape_metadata",
            status="success" if failed == 0 else "partial",
            summary={
                "media_type": "tvshows",
                "library_path": str(library_path),
                "dry_run": context.dry_run,
                "scanned": len(records),
                "matched": matched,
                "manual_review": manual_review,
                "failed": failed,
                "tmdb_language": context.tmdb.language,
                "tmdb_fallback_language": context.tmdb.fallback_language,
                "llm_enabled": context.llm.enabled,
                "auto_rename": rename_summary,
            },
            records=records,
        )

    def _process_tvshow(self, context: AppContext, show_dir: Path, logger: logging.Logger) -> list[OperationRecord]:
        query = infer_tvshow_query(show_dir)
        tvshow_nfo = show_dir / "tvshow.nfo"
        if not context.tmdb.api_key and self.tmdb_client is None:
            return [
                OperationRecord(
                    action="scrape_metadata",
                    status="manual_review",
                    source_path=str(show_dir),
                    target_path=str(tvshow_nfo),
                    media_type="tvshows",
                    title=query.title,
                    year=query.year,
                    reason="TMDB API Key 未配置，无法执行电视剧元数据匹配",
                )
            ]

        try:
            client = self.tmdb_client or TmdbClient(context.tmdb.api_key, context.tmdb.timeout)
            show_metadata, candidates = fetch_tvshow_metadata(
                client,
                query,
                context.tmdb.language,
                context.tmdb.fallback_language,
            )
            if show_metadata is None:
                llm_resolution = infer_tvshow_queries_with_llm(context, self.llm_client, show_dir, query, logger)
                for llm_query in llm_resolution.get("queries", []):
                    show_metadata, candidates = fetch_tvshow_metadata(
                        client,
                        llm_query,
                        context.tmdb.language,
                        context.tmdb.fallback_language,
                    )
                    llm_resolution.setdefault("tmdb_retry_queries", []).append(llm_query.__dict__)
                    if show_metadata is not None:
                        query = llm_query
                        break

            if show_metadata is None:
                return [
                    OperationRecord(
                        action="scrape_metadata",
                        status="manual_review",
                        source_path=str(show_dir),
                        target_path=str(tvshow_nfo),
                        media_type="tvshows",
                        title=query.title,
                        year=query.year,
                        reason="TMDB 未返回可用电视剧候选",
                        extra={
                            "query": query.__dict__,
                            "candidates": candidates,
                            "llm_resolution": llm_resolution_for_report(locals().get("llm_resolution", {})),
                        },
                    )
                ]

            records = [
                self._write_tvshow_metadata_record(
                    context,
                    client,
                    show_dir,
                    tvshow_nfo,
                    show_metadata,
                    query,
                    candidates,
                    locals().get("llm_resolution", {}),
                )
            ]
            extensions = set(context.symlink.video_extensions)
            for video_path in iter_video_files(show_dir, extensions):
                records.append(self._process_episode(context, client, video_path, show_metadata, logger))
            return records
        except Exception as exc:
            logger.warning("电视剧元数据处理失败 show=%s error=%s", show_dir, exc)
            return [
                OperationRecord(
                    action="scrape_metadata",
                    status="failed",
                    source_path=str(show_dir),
                    target_path=str(tvshow_nfo),
                    media_type="tvshows",
                    title=query.title,
                    year=query.year,
                    reason=str(exc),
                )
            ]

    def _write_tvshow_metadata_record(
        self,
        context: AppContext,
        client: TmdbClient,
        show_dir: Path,
        tvshow_nfo: Path,
        metadata: TvShowMetadata,
        query: TvShowQuery,
        candidates: list[dict[str, Any]],
        llm_resolution: dict[str, Any] | None = None,
    ) -> OperationRecord:
        nfo_status = plan_or_write_tvshow_nfo(context, tvshow_nfo, metadata)
        poster_status = "not_requested"
        fanart_status = "not_requested"
        if context.metadata_output.download_images:
            if context.dry_run:
                poster_status = "planned" if metadata.poster_path else "missing"
                fanart_status = "planned" if metadata.backdrop_path else "missing"
            else:
                poster_status = client.download_image(
                    metadata.poster_path,
                    show_dir / "poster.jpg",
                    context.metadata_output.overwrite_existing,
                )
                fanart_status = client.download_image(
                    metadata.backdrop_path,
                    show_dir / "fanart.jpg",
                    context.metadata_output.overwrite_existing,
                )
        return OperationRecord(
            action="scrape_metadata",
            status=nfo_status,
            source_path=str(show_dir),
            target_path=str(tvshow_nfo),
            media_type="tvshows",
            title=metadata.title,
            year=metadata.year,
            confidence="0.90",
            reason="TMDB 电视剧自动匹配成功",
            extra={
                "query": query.__dict__,
                "tmdb_id": metadata.tmdb_id,
                "tmdb_language": metadata.language,
                "fallback_used": metadata.fallback_used,
                "rating": metadata.rating,
                "certification": metadata.certification,
                "actor_count": len(metadata.actors),
                "candidates": candidates,
                "poster_path": str(show_dir / "poster.jpg"),
                "fanart_path": str(show_dir / "fanart.jpg"),
                "poster_status": poster_status,
                "fanart_status": fanart_status,
                "llm_resolution": llm_resolution_for_report(llm_resolution or {}),
            },
        )

    def _process_episode(
        self,
        context: AppContext,
        client: TmdbClient,
        video_path: Path,
        show_metadata: TvShowMetadata,
        logger: logging.Logger,
    ) -> OperationRecord:
        parsed = parse_episode_from_filename(video_path.stem)
        nfo_path = video_path.with_suffix(".nfo")
        if not parsed:
            return OperationRecord(
                action="scrape_metadata",
                status="manual_review",
                source_path=str(video_path),
                target_path=str(nfo_path),
                media_type="tvshows",
                title=show_metadata.title,
                reason="无法从文件名解析 SxxEyy，跳过单集元数据生成",
                extra={"tmdb_id": show_metadata.tmdb_id},
            )

        season, episode = parsed
        try:
            episode_metadata = fetch_episode_metadata(
                client,
                show_metadata.tmdb_id,
                season,
                episode,
                context.tmdb.language,
                context.tmdb.fallback_language,
            )
            nfo_status = plan_or_write_episode_nfo(context, nfo_path, show_metadata, episode_metadata)
            thumb_path = video_path.with_name(f"{video_path.stem}-thumb.jpg")
            thumb_status = "not_requested"
            if context.metadata_output.download_episode_thumbs:
                if context.dry_run:
                    thumb_status = "planned" if episode_metadata.still_path else "missing"
                else:
                    thumb_status = client.download_image(
                        episode_metadata.still_path,
                        thumb_path,
                        context.metadata_output.overwrite_existing,
                    )
            return OperationRecord(
                action="scrape_metadata",
                status=nfo_status,
                source_path=str(video_path),
                target_path=str(nfo_path),
                media_type="tvshows",
                title=episode_metadata.title,
                year=show_metadata.year,
                season=f"{season:02d}",
                episode=f"{episode:02d}",
                confidence="0.90",
                reason="TMDB 单集自动匹配成功",
                extra={
                    "tmdb_id": show_metadata.tmdb_id,
                    "fallback_used": episode_metadata.fallback_used,
                    "rating": episode_metadata.rating,
                    "actor_count": len(show_metadata.actors),
                    "thumb_path": str(thumb_path),
                    "thumb_status": thumb_status,
                },
            )
        except Exception as exc:
            logger.warning("单集元数据处理失败 video=%s error=%s", video_path, exc)
            return OperationRecord(
                action="scrape_metadata",
                status="failed",
                source_path=str(video_path),
                target_path=str(nfo_path),
                media_type="tvshows",
                title=show_metadata.title,
                year=show_metadata.year,
                season=f"{season:02d}",
                episode=f"{episode:02d}",
                reason=str(exc),
                extra={"tmdb_id": show_metadata.tmdb_id},
            )

    def _process_movie(self, context: AppContext, video_path: Path, logger: logging.Logger) -> OperationRecord:
        query = infer_movie_query(video_path, context.metadata_output.library_path)
        nfo_path = video_path.with_suffix(".nfo")
        poster_path = video_path.with_name(f"{video_path.stem}-poster.jpg")
        fanart_path = video_path.with_name(f"{video_path.stem}-fanart.jpg")
        if not context.tmdb.api_key and self.tmdb_client is None:
            return OperationRecord(
                action="scrape_metadata",
                status="manual_review",
                source_path=str(video_path),
                target_path=str(nfo_path),
                media_type="movies",
                title=query.title,
                year=query.year,
                reason="TMDB API Key 未配置，无法执行元数据匹配",
            )

        try:
            client = self.tmdb_client or TmdbClient(context.tmdb.api_key, context.tmdb.timeout)
            metadata, candidates = fetch_movie_metadata(client, query, context.tmdb.language, context.tmdb.fallback_language)
            if metadata is None:
                llm_resolution = infer_movie_queries_with_llm(context, self.llm_client, video_path, query, logger)
                for llm_query in llm_resolution.get("queries", []):
                    metadata, candidates = fetch_movie_metadata(
                        client,
                        llm_query,
                        context.tmdb.language,
                        context.tmdb.fallback_language,
                    )
                    llm_resolution.setdefault("tmdb_retry_queries", []).append(llm_query.__dict__)
                    if metadata is not None:
                        query = llm_query
                        break

            if metadata is None:
                return OperationRecord(
                    action="scrape_metadata",
                    status="manual_review",
                    source_path=str(video_path),
                    target_path=str(nfo_path),
                    media_type="movies",
                    title=query.title,
                    year=query.year,
                    reason="TMDB 未返回可用候选",
                    extra={
                        "query": query.__dict__,
                        "candidates": candidates,
                        "llm_resolution": llm_resolution_for_report(locals().get("llm_resolution", {})),
                    },
                )

            nfo_status = plan_or_write_movie_nfo(context, nfo_path, metadata)
            poster_status = "not_requested"
            fanart_status = "not_requested"
            if context.metadata_output.download_images:
                if context.dry_run:
                    poster_status = "planned" if metadata.poster_path else "missing"
                    fanart_status = "planned" if metadata.backdrop_path else "missing"
                else:
                    poster_status = client.download_image(
                        metadata.poster_path,
                        poster_path,
                        context.metadata_output.overwrite_existing,
                    )
                    fanart_status = client.download_image(
                        metadata.backdrop_path,
                        fanart_path,
                        context.metadata_output.overwrite_existing,
                    )

            return OperationRecord(
                action="scrape_metadata",
                status=nfo_status,
                source_path=str(video_path),
                target_path=str(nfo_path),
                media_type="movies",
                title=metadata.title,
                year=metadata.year,
                confidence="0.90",
                reason="TMDB 自动匹配成功",
                extra={
                    "query": query.__dict__,
                    "tmdb_id": metadata.tmdb_id,
                    "tmdb_language": metadata.language,
                    "fallback_used": metadata.fallback_used,
                    "rating": metadata.rating,
                    "certification": metadata.certification,
                    "actor_count": len(metadata.actors),
                    "candidates": candidates,
                    "poster_path": str(poster_path),
                    "fanart_path": str(fanart_path),
                    "poster_status": poster_status,
                    "fanart_status": fanart_status,
                    "llm_resolution": llm_resolution_for_report(locals().get("llm_resolution", {})),
                },
            )
        except Exception as exc:
            logger.warning("电影元数据处理失败 video=%s error=%s", video_path, exc)
            return OperationRecord(
                action="scrape_metadata",
                status="failed",
                source_path=str(video_path),
                target_path=str(nfo_path),
                media_type="movies",
                title=query.title,
                year=query.year,
                reason=str(exc),
            )


def iter_video_files(root: Path, extensions: set[str]):
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in extensions:
            yield path


def infer_movie_query(video_path: Path, library_path: Path) -> MovieQuery:
    parent = video_path.parent
    raw_title = parent.name if parent != library_path else video_path.stem
    match = re.search(r"\((\d{4})\)", raw_title)
    year = match.group(1) if match else extract_year(video_path.stem)
    title = re.sub(r"\(\d{4}\)", "", raw_title).strip()
    if not title or title == video_path.stem:
        title = clean_release_title(video_path.stem)
    return MovieQuery(title=title.strip(" ._-"), year=year)


def infer_tvshow_query(show_dir: Path) -> TvShowQuery:
    raw_title = show_dir.name
    match = re.search(r"\((\d{4})\)", raw_title)
    year = match.group(1) if match else extract_year(raw_title)
    title = re.sub(r"\(\d{4}\)", "", raw_title).strip(" ._-")
    if year and title == raw_title:
        title = raw_title.split(year, 1)[0]
    return TvShowQuery(title=title.strip(" ._-"), year=year)


def parse_episode_from_filename(stem: str) -> tuple[int, int] | None:
    match = re.search(r"(?i)\bS(?P<season>\d{1,2})E(?P<episode>\d{1,3})\b", stem)
    if not match:
        return None
    return int(match.group("season")), int(match.group("episode"))


def extract_year(value: str) -> str:
    match = re.search(r"(?:^|[ ._\-])((?:19|20)\d{2})(?:[ ._\-]|$)", value)
    return match.group(1) if match else ""


def clean_release_title(value: str) -> str:
    year = extract_year(value)
    if year:
        value = value.split(year, 1)[0]
    return re.sub(r"[._]+", " ", value).strip()


def llm_config_ready(context: AppContext) -> bool:
    return bool(context.llm.enabled and context.llm.base_url and context.llm.api_key and context.llm.model)


def infer_movie_queries_with_llm(
    context: AppContext,
    llm_client: OpenAICompatibleLlmClient | None,
    video_path: Path,
    query: MovieQuery,
    logger: logging.Logger,
) -> dict[str, Any]:
    if not llm_config_ready(context) and llm_client is None:
        return {"status": "skipped", "reason": "LLM 未启用或配置不完整", "queries": []}

    try:
        client = llm_client or OpenAICompatibleLlmClient()
        candidates = client.suggest_movie_queries(context, video_path, query)
        queries = unique_llm_movie_queries(candidates, original=query)
        logger.info("LLM 电影候选扩展 video=%s candidates=%s", video_path, len(queries))
        return {
            "status": "suggested" if queries else "empty",
            "reason": "LLM 已生成 TMDB 二次搜索候选" if queries else "LLM 未返回有效候选",
            "candidates": [candidate.__dict__ for candidate in candidates],
            "query_candidates": [item.__dict__ for item in queries],
            "queries": queries,
        }
    except Exception as exc:
        logger.warning("LLM 电影候选扩展失败 video=%s error=%s", video_path, exc)
        return {"status": "failed", "reason": str(exc), "queries": []}


def infer_tvshow_queries_with_llm(
    context: AppContext,
    llm_client: OpenAICompatibleLlmClient | None,
    show_dir: Path,
    query: TvShowQuery,
    logger: logging.Logger,
) -> dict[str, Any]:
    if not llm_config_ready(context) and llm_client is None:
        return {"status": "skipped", "reason": "LLM 未启用或配置不完整", "queries": []}

    try:
        client = llm_client or OpenAICompatibleLlmClient()
        video_names = [path.name for path in iter_video_files(show_dir, set(context.symlink.video_extensions))]
        candidates = client.suggest_tvshow_queries(context, show_dir, query, video_names)
        queries = unique_llm_tvshow_queries(candidates, original=query)
        logger.info("LLM 电视剧候选扩展 show=%s candidates=%s", show_dir, len(queries))
        return {
            "status": "suggested" if queries else "empty",
            "reason": "LLM 已生成 TMDB 二次搜索候选" if queries else "LLM 未返回有效候选",
            "candidates": [candidate.__dict__ for candidate in candidates],
            "query_candidates": [item.__dict__ for item in queries],
            "queries": queries,
        }
    except Exception as exc:
        logger.warning("LLM 电视剧候选扩展失败 show=%s error=%s", show_dir, exc)
        return {"status": "failed", "reason": str(exc), "queries": []}


def llm_resolution_for_report(resolution: dict[str, Any]) -> dict[str, Any]:
    if not resolution:
        return {}
    result = dict(resolution)
    result.pop("queries", None)
    return result


def unique_llm_movie_queries(candidates: list[LlmMovieCandidate], original: MovieQuery) -> list[MovieQuery]:
    queries: list[MovieQuery] = []
    seen = {(original.title.casefold(), original.year)}
    for candidate in sorted(candidates, key=lambda item: item.confidence, reverse=True):
        title = candidate.title.strip()
        year = normalize_year(candidate.year) or original.year
        key = (title.casefold(), year)
        if not title or key in seen:
            continue
        seen.add(key)
        queries.append(MovieQuery(title=title, year=year))
        if len(queries) >= 5:
            break
    return queries


def unique_llm_tvshow_queries(candidates: list[LlmTvShowCandidate], original: TvShowQuery) -> list[TvShowQuery]:
    queries: list[TvShowQuery] = []
    seen = {(original.title.casefold(), original.year)}
    for candidate in sorted(candidates, key=lambda item: item.confidence, reverse=True):
        title = candidate.title.strip()
        year = normalize_year(candidate.year) or original.year
        key = (title.casefold(), year)
        if not title or key in seen:
            continue
        seen.add(key)
        queries.append(TvShowQuery(title=title, year=year))
        if len(queries) >= 5:
            break
    return queries


def parse_llm_movie_candidates(content: str, fallback_year: str = "") -> list[LlmMovieCandidate]:
    payload = parse_json_object_from_text(content)
    raw_candidates = payload.get("candidates", []) if isinstance(payload, dict) else []
    if not isinstance(raw_candidates, list):
        return []

    candidates = []
    for item in raw_candidates:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        candidates.append(
            LlmMovieCandidate(
                title=title,
                year=normalize_year(str(item.get("year") or "")) or fallback_year,
                confidence=normalize_confidence(item.get("confidence")),
                reason=str(item.get("reason") or "").strip(),
            )
        )
    return candidates


def parse_llm_tvshow_candidates(content: str, fallback_year: str = "") -> list[LlmTvShowCandidate]:
    payload = parse_json_object_from_text(content)
    raw_candidates = payload.get("candidates", []) if isinstance(payload, dict) else []
    if not isinstance(raw_candidates, list):
        return []

    candidates = []
    for item in raw_candidates:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        candidates.append(
            LlmTvShowCandidate(
                title=title,
                year=normalize_year(str(item.get("year") or "")) or fallback_year,
                confidence=normalize_confidence(item.get("confidence")),
                reason=str(item.get("reason") or "").strip(),
            )
        )
    return candidates


def parse_json_object_from_text(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return data if isinstance(data, dict) else {}


def normalize_year(value: str) -> str:
    match = re.search(r"\b((?:19|20)\d{2})\b", value)
    return match.group(1) if match else ""


def normalize_confidence(value: Any) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return 0.0


def fetch_movie_metadata(
    client: TmdbClient,
    query: MovieQuery,
    language: str,
    fallback_language: str,
) -> tuple[MovieMetadata | None, list[dict[str, Any]]]:
    candidates = client.search_movie(query, language)
    used_language = language
    fallback_used = False
    if not candidates and fallback_language != language:
        candidates = client.search_movie(query, fallback_language)
        used_language = fallback_language
        fallback_used = True
    if not candidates:
        return None, []

    selected = candidates[0]
    tmdb_id = int(selected["id"])
    details = client.movie_details(tmdb_id, used_language)
    fallback_details = {}
    if fallback_language != used_language and missing_core_fields(details):
        fallback_details = client.movie_details(tmdb_id, fallback_language)
        fallback_used = True
    metadata = movie_metadata_from_details(details, fallback_details, used_language, fallback_used)
    return metadata, summarize_candidates(candidates)


def fetch_tvshow_metadata(
    client: TmdbClient,
    query: TvShowQuery,
    language: str,
    fallback_language: str,
) -> tuple[TvShowMetadata | None, list[dict[str, Any]]]:
    candidates = client.search_tv(query, language)
    used_language = language
    fallback_used = False
    if not candidates and fallback_language != language:
        candidates = client.search_tv(query, fallback_language)
        used_language = fallback_language
        fallback_used = True
    if not candidates:
        return None, []

    selected = candidates[0]
    tmdb_id = int(selected["id"])
    details = client.tv_details(tmdb_id, used_language)
    fallback_details = {}
    if fallback_language != used_language and missing_tv_core_fields(details):
        fallback_details = client.tv_details(tmdb_id, fallback_language)
        fallback_used = True
    metadata = tvshow_metadata_from_details(details, fallback_details, used_language, fallback_used)
    return metadata, summarize_tv_candidates(candidates)


def fetch_episode_metadata(
    client: TmdbClient,
    tmdb_id: int,
    season: int,
    episode: int,
    language: str,
    fallback_language: str,
) -> EpisodeMetadata:
    details = client.tv_episode_details(tmdb_id, season, episode, language)
    fallback_details = {}
    fallback_used = False
    if fallback_language != language and missing_episode_core_fields(details):
        fallback_details = client.tv_episode_details(tmdb_id, season, episode, fallback_language)
        fallback_used = True
    return episode_metadata_from_details(details, fallback_details, season, episode, fallback_used)


def missing_core_fields(details: dict[str, Any]) -> bool:
    return not details.get("overview") or not details.get("title")


def missing_tv_core_fields(details: dict[str, Any]) -> bool:
    return not details.get("overview") or not details.get("name")


def missing_episode_core_fields(details: dict[str, Any]) -> bool:
    return not details.get("overview") or not details.get("name")


def normalize_rating(value: Any) -> float:
    try:
        return round(max(0.0, min(float(value), 10.0)), 1)
    except (TypeError, ValueError):
        return 0.0


def extract_actors(details: dict[str, Any], fallback: dict[str, Any], limit: int = 20) -> tuple[ActorMetadata, ...]:
    cast = (details.get("credits") or {}).get("cast") or (fallback.get("credits") or {}).get("cast") or []
    actors: list[ActorMetadata] = []
    for item in cast:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        actors.append(
            ActorMetadata(
                name=name,
                role=str(item.get("character") or "").strip(),
                order=int(item.get("order") or len(actors)),
                profile_path=str(item.get("profile_path") or "").strip(),
            )
        )
        if len(actors) >= limit:
            break
    return tuple(actors)


def extract_movie_certification(details: dict[str, Any], fallback: dict[str, Any]) -> str:
    release_dates = (details.get("release_dates") or {}).get("results") or (
        fallback.get("release_dates") or {}
    ).get("results") or []
    by_country = {str(item.get("iso_3166_1") or "").upper(): item for item in release_dates}
    for country in ("CN", "US", "HK", "TW", "JP", "KR", "GB"):
        certification = first_movie_certification(by_country.get(country, {}))
        if certification:
            return certification
    for item in release_dates:
        certification = first_movie_certification(item)
        if certification:
            return certification
    return ""


def first_movie_certification(country_release: dict[str, Any]) -> str:
    for release in country_release.get("release_dates") or []:
        certification = str(release.get("certification") or "").strip()
        if certification:
            return certification
    return ""


def extract_tv_certification(details: dict[str, Any], fallback: dict[str, Any]) -> str:
    ratings = (details.get("content_ratings") or {}).get("results") or (
        fallback.get("content_ratings") or {}
    ).get("results") or []
    by_country = {str(item.get("iso_3166_1") or "").upper(): item for item in ratings}
    for country in ("CN", "US", "HK", "TW", "JP", "KR", "GB"):
        rating = str((by_country.get(country) or {}).get("rating") or "").strip()
        if rating:
            return rating
    for item in ratings:
        rating = str(item.get("rating") or "").strip()
        if rating:
            return rating
    return ""


def movie_metadata_from_details(
    details: dict[str, Any],
    fallback: dict[str, Any],
    language: str,
    fallback_used: bool,
) -> MovieMetadata:
    release_date = str(details.get("release_date") or fallback.get("release_date") or "")
    return MovieMetadata(
        tmdb_id=int(details.get("id") or fallback.get("id")),
        title=str(details.get("title") or fallback.get("title") or ""),
        original_title=str(details.get("original_title") or fallback.get("original_title") or ""),
        year=release_date[:4],
        overview=str(details.get("overview") or fallback.get("overview") or ""),
        runtime=int(details.get("runtime") or fallback.get("runtime") or 0),
        genres=tuple(str(item.get("name")) for item in details.get("genres") or fallback.get("genres") or []),
        rating=normalize_rating(details.get("vote_average") or fallback.get("vote_average")),
        certification=extract_movie_certification(details, fallback),
        actors=extract_actors(details, fallback),
        poster_path=str(details.get("poster_path") or fallback.get("poster_path") or ""),
        backdrop_path=str(details.get("backdrop_path") or fallback.get("backdrop_path") or ""),
        language=language,
        fallback_used=fallback_used,
    )


def tvshow_metadata_from_details(
    details: dict[str, Any],
    fallback: dict[str, Any],
    language: str,
    fallback_used: bool,
) -> TvShowMetadata:
    first_air_date = str(details.get("first_air_date") or fallback.get("first_air_date") or "")
    return TvShowMetadata(
        tmdb_id=int(details.get("id") or fallback.get("id")),
        title=str(details.get("name") or fallback.get("name") or ""),
        original_title=str(details.get("original_name") or fallback.get("original_name") or ""),
        year=first_air_date[:4],
        overview=str(details.get("overview") or fallback.get("overview") or ""),
        genres=tuple(str(item.get("name")) for item in details.get("genres") or fallback.get("genres") or []),
        rating=normalize_rating(details.get("vote_average") or fallback.get("vote_average")),
        certification=extract_tv_certification(details, fallback),
        actors=extract_actors(details, fallback),
        poster_path=str(details.get("poster_path") or fallback.get("poster_path") or ""),
        backdrop_path=str(details.get("backdrop_path") or fallback.get("backdrop_path") or ""),
        language=language,
        fallback_used=fallback_used,
    )


def episode_metadata_from_details(
    details: dict[str, Any],
    fallback: dict[str, Any],
    season: int,
    episode: int,
    fallback_used: bool,
) -> EpisodeMetadata:
    return EpisodeMetadata(
        title=str(details.get("name") or fallback.get("name") or f"S{season:02d}E{episode:02d}"),
        season=season,
        episode=episode,
        overview=str(details.get("overview") or fallback.get("overview") or ""),
        air_date=str(details.get("air_date") or fallback.get("air_date") or ""),
        rating=normalize_rating(details.get("vote_average") or fallback.get("vote_average")),
        still_path=str(details.get("still_path") or fallback.get("still_path") or ""),
        fallback_used=fallback_used,
    )


def summarize_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "original_title": item.get("original_title"),
            "release_date": item.get("release_date"),
        }
        for item in candidates[:5]
    ]


def summarize_tv_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "original_name": item.get("original_name"),
            "first_air_date": item.get("first_air_date"),
        }
        for item in candidates[:5]
    ]


def plan_or_write_movie_nfo(context: AppContext, nfo_path: Path, metadata: MovieMetadata) -> str:
    if nfo_path.exists() and not context.metadata_output.overwrite_existing:
        return "skipped_existing"
    if context.dry_run or not context.metadata_output.write_nfo:
        return "planned"
    nfo_path.parent.mkdir(parents=True, exist_ok=True)
    nfo_path.write_text(render_movie_nfo(metadata), encoding="utf-8")
    return "written"


def plan_or_write_tvshow_nfo(context: AppContext, nfo_path: Path, metadata: TvShowMetadata) -> str:
    if nfo_path.exists() and not context.metadata_output.overwrite_existing:
        return "skipped_existing"
    if context.dry_run or not context.metadata_output.write_nfo:
        return "planned"
    nfo_path.parent.mkdir(parents=True, exist_ok=True)
    nfo_path.write_text(render_tvshow_nfo(metadata), encoding="utf-8")
    return "written"


def plan_or_write_episode_nfo(
    context: AppContext,
    nfo_path: Path,
    show_metadata: TvShowMetadata,
    episode_metadata: EpisodeMetadata,
) -> str:
    if nfo_path.exists() and not context.metadata_output.overwrite_existing:
        return "skipped_existing"
    if context.dry_run or not context.metadata_output.write_nfo:
        return "planned"
    nfo_path.parent.mkdir(parents=True, exist_ok=True)
    nfo_path.write_text(render_episode_nfo(show_metadata, episode_metadata), encoding="utf-8")
    return "written"


def render_movie_nfo(metadata: MovieMetadata) -> str:
    movie = ET.Element("movie")
    fields = {
        "title": metadata.title,
        "originaltitle": metadata.original_title,
        "year": metadata.year,
        "plot": metadata.overview,
        "runtime": str(metadata.runtime) if metadata.runtime else "",
        "rating": format_nfo_rating(metadata.rating),
        "mpaa": metadata.certification,
        "tmdbid": str(metadata.tmdb_id),
    }
    for key, value in fields.items():
        child = ET.SubElement(movie, key)
        child.text = value
    for genre in metadata.genres:
        child = ET.SubElement(movie, "genre")
        child.text = genre
    append_actor_elements(movie, metadata.actors)
    ET.indent(movie, space="  ")
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n' + ET.tostring(
        movie,
        encoding="unicode",
    )


def render_tvshow_nfo(metadata: TvShowMetadata) -> str:
    tvshow = ET.Element("tvshow")
    fields = {
        "title": metadata.title,
        "originaltitle": metadata.original_title,
        "year": metadata.year,
        "plot": metadata.overview,
        "rating": format_nfo_rating(metadata.rating),
        "mpaa": metadata.certification,
        "tmdbid": str(metadata.tmdb_id),
    }
    for key, value in fields.items():
        child = ET.SubElement(tvshow, key)
        child.text = value
    for genre in metadata.genres:
        child = ET.SubElement(tvshow, "genre")
        child.text = genre
    append_actor_elements(tvshow, metadata.actors)
    ET.indent(tvshow, space="  ")
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n' + ET.tostring(
        tvshow,
        encoding="unicode",
    )


def render_episode_nfo(show_metadata: TvShowMetadata, episode_metadata: EpisodeMetadata) -> str:
    episode = ET.Element("episodedetails")
    fields = {
        "title": episode_metadata.title,
        "showtitle": show_metadata.title,
        "season": str(episode_metadata.season),
        "episode": str(episode_metadata.episode),
        "plot": episode_metadata.overview,
        "aired": episode_metadata.air_date,
        "rating": format_nfo_rating(episode_metadata.rating),
        "tmdbid": str(show_metadata.tmdb_id),
    }
    for key, value in fields.items():
        child = ET.SubElement(episode, key)
        child.text = value
    append_actor_elements(episode, show_metadata.actors)
    ET.indent(episode, space="  ")
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n' + ET.tostring(
        episode,
        encoding="unicode",
    )


def format_nfo_rating(rating: float) -> str:
    return f"{rating:.1f}" if rating else ""


def append_actor_elements(parent: ET.Element, actors: tuple[ActorMetadata, ...]) -> None:
    for actor in actors:
        actor_node = ET.SubElement(parent, "actor")
        name = ET.SubElement(actor_node, "name")
        name.text = actor.name
        role = ET.SubElement(actor_node, "role")
        role.text = actor.role
        order = ET.SubElement(actor_node, "order")
        order.text = str(actor.order)
        if actor.profile_path:
            thumb = ET.SubElement(actor_node, "thumb")
            thumb.text = TMDB_IMAGE_BASE + actor.profile_path


def auto_rename_from_movie_records(
    context: AppContext,
    records: list[OperationRecord],
    logger: logging.Logger,
) -> dict[str, int]:
    summary = {"planned": 0, "renamed": 0, "merged": 0, "skipped": 0, "failed": 0}
    if not context.metadata_output.auto_rename:
        return summary

    library_path = context.metadata_output.library_path
    folders: dict[Path, OperationRecord] = {}
    for record in records:
        if record.media_type != "movies" or record.status not in {"written", "skipped_existing", "planned"}:
            continue
        nfo_path = Path(record.target_path)
        folder = first_level_folder(library_path, nfo_path)
        if folder and folder not in folders:
            folders[folder] = record

    for folder, record in folders.items():
        nfo_path = Path(record.target_path)
        result = auto_rename_folder_from_nfo(
            folder=folder,
            nfo_path=nfo_path,
            expected_root="movie",
            dry_run=context.dry_run,
            logger=logger,
        )
        summary[result["status"]] = summary.get(result["status"], 0) + 1
        record.extra["auto_rename"] = result
    return summary


def auto_rename_tvshow_folders(
    context: AppContext,
    library_path: Path,
    records: list[OperationRecord],
    logger: logging.Logger,
) -> dict[str, int]:
    summary = {"planned": 0, "renamed": 0, "merged": 0, "skipped": 0, "failed": 0}
    if not context.metadata_output.auto_rename:
        return summary

    for folder in direct_child_dirs(library_path):
        result = auto_rename_folder_from_nfo(
            folder=folder,
            nfo_path=folder / "tvshow.nfo",
            expected_root="tvshow",
            dry_run=context.dry_run,
            logger=logger,
        )
        summary[result["status"]] = summary.get(result["status"], 0) + 1
        records.append(
            OperationRecord(
                action="auto_rename",
                status=result["status"],
                source_path=str(folder),
                target_path=result.get("target_path", ""),
                media_type="tvshows",
                title=result.get("title", ""),
                year=result.get("year", ""),
                reason=result.get("reason", ""),
                extra=result,
            )
        )
    return summary


def auto_rename_folder_from_nfo(
    folder: Path,
    nfo_path: Path,
    expected_root: str,
    dry_run: bool,
    logger: logging.Logger,
) -> dict[str, str]:
    parsed = parse_title_year_from_nfo(nfo_path, expected_root)
    if not parsed:
        return {
            "status": "skipped",
            "source_path": str(folder),
            "target_path": "",
            "reason": f"未找到可解析的 {expected_root}.nfo title/year",
        }

    title, year = parsed
    target = folder.with_name(format_media_folder_name(title, year))
    result = {
        "status": "planned" if dry_run else "renamed",
        "source_path": str(folder),
        "target_path": str(target),
        "title": title,
        "year": year,
        "reason": "自动重命名一级目录",
    }
    if folder == target:
        result["status"] = "skipped"
        result["reason"] = "一级目录名称已经符合 title (year)"
        return result
    if target.exists():
        if dry_run:
            result["status"] = "planned"
            result["reason"] = "目标目录已存在，将合并移动当前目录内不冲突的文件"
            return result
        merge_result = merge_folder_contents(folder, target, logger)
        result.update(merge_result)
        return result
    if dry_run:
        return result

    try:
        folder.rename(target)
        logger.info("自动重命名媒体目录 %s -> %s", folder, target)
        return result
    except OSError as exc:
        result["status"] = "failed"
        result["reason"] = str(exc)
        return result


def merge_folder_contents(source: Path, target: Path, logger: logging.Logger) -> dict[str, str]:
    try:
        moved = 0
        skipped = 0
        for child in source.iterdir():
            destination = target / child.name
            if destination.exists() or destination.is_symlink():
                skipped += 1
                continue
            child.rename(destination)
            moved += 1
        try:
            source.rmdir()
        except OSError:
            pass
        logger.info("自动重命名合并媒体目录 %s -> %s moved=%s skipped=%s", source, target, moved, skipped)
        status = "merged" if moved else "skipped"
        reason = f"目标目录已存在，已合并移动 {moved} 个文件，跳过 {skipped} 个冲突项"
        return {"status": status, "reason": reason}
    except OSError as exc:
        return {"status": "failed", "reason": str(exc)}


def parse_title_year_from_nfo(nfo_path: Path, expected_root: str) -> tuple[str, str] | None:
    if not nfo_path.exists():
        return None
    try:
        root = ET.parse(nfo_path).getroot()
    except ET.ParseError:
        return None
    if root.tag != expected_root:
        return None
    title = (root.findtext("title") or "").strip()
    year = (root.findtext("year") or "").strip()
    if not title or not year:
        return None
    return title, year


def format_media_folder_name(title: str, year: str) -> str:
    safe_title = sanitize_windows_name(title).strip()
    return f"{safe_title} ({year})"


def sanitize_windows_name(value: str) -> str:
    sanitized = "".join(" " if char in INVALID_WINDOWS_NAME_CHARS else char for char in value)
    return re.sub(r"\s+", " ", sanitized).strip(" .")


def first_level_folder(library_path: Path, child_path: Path) -> Path | None:
    try:
        relative = child_path.relative_to(library_path)
    except ValueError:
        return None
    if not relative.parts:
        return None
    folder = library_path / relative.parts[0]
    return folder if folder != library_path else None


def direct_child_dirs(library_path: Path):
    if not library_path.exists():
        return []
    return [path for path in library_path.iterdir() if path.is_dir()]
