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


@dataclass(frozen=True)
class MovieQuery:
    title: str
    year: str = ""


@dataclass(frozen=True)
class MovieMetadata:
    tmdb_id: int
    title: str
    original_title: str = ""
    year: str = ""
    overview: str = ""
    runtime: int = 0
    genres: tuple[str, ...] = ()
    poster_path: str = ""
    backdrop_path: str = ""
    language: str = ""
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
    def __init__(self, api_key: str, timeout: float = 10.0):
        self.api_key = api_key
        self.timeout = timeout

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
        return self._get(f"/movie/{tmdb_id}", {"api_key": self.api_key, "language": language})

    def download_image(self, image_path: str, target_path: Path, overwrite: bool) -> str:
        if not image_path:
            return "missing"
        if target_path.exists() and not overwrite:
            return "skipped_existing"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(TMDB_IMAGE_BASE + image_path, timeout=self.timeout) as response:
            target_path.write_bytes(response.read())
        return "downloaded"

    def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        url = TMDB_API_BASE + endpoint + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))


class MetadataScraperService:
    def __init__(self, tmdb_client: TmdbClient | None = None):
        self.tmdb_client = tmdb_client

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

        matched = sum(1 for record in records if record.status in {"planned", "written", "skipped_existing"})
        manual_review = sum(1 for record in records if record.status == "manual_review")
        failed = sum(1 for record in records if record.status == "failed")
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
            },
            records=records,
        )

    def _run_tvshows_skeleton(self, context: AppContext, logger: logging.Logger, library_path: Path) -> StepResult:
        records = []
        extensions = set(context.symlink.video_extensions)
        for video_path in iter_video_files(library_path, extensions):
            records.append(
                OperationRecord(
                    action="scrape_metadata",
                    status="planned" if context.dry_run else "manual_review",
                    source_path=str(video_path),
                    target_path=str(video_path.with_suffix(".nfo")),
                    media_type="tvshows",
                    title=video_path.stem,
                    reason="电视剧 TMDB 匹配、tvshow.nfo 和单集 NFO 将在电影链路稳定后实现",
                )
            )
        logger.info("电视剧元数据刮削骨架扫描完成 library=%s planned=%s", library_path, len(records))
        return StepResult(
            step_id="scrape_metadata",
            status="planned" if context.dry_run else "manual_review",
            summary={
                "media_type": "tvshows",
                "library_path": str(library_path),
                "dry_run": context.dry_run,
                "planned": len(records),
                "tmdb_language": context.tmdb.language,
                "tmdb_fallback_language": context.tmdb.fallback_language,
                "llm_enabled": context.llm.enabled,
            },
            records=records,
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
                return OperationRecord(
                    action="scrape_metadata",
                    status="manual_review",
                    source_path=str(video_path),
                    target_path=str(nfo_path),
                    media_type="movies",
                    title=query.title,
                    year=query.year,
                    reason="TMDB 未返回可用候选",
                    extra={"query": query.__dict__, "candidates": candidates},
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
                    "candidates": candidates,
                    "poster_path": str(poster_path),
                    "fanart_path": str(fanart_path),
                    "poster_status": poster_status,
                    "fanart_status": fanart_status,
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


def extract_year(value: str) -> str:
    match = re.search(r"(?:^|[ ._\-])((?:19|20)\d{2})(?:[ ._\-]|$)", value)
    return match.group(1) if match else ""


def clean_release_title(value: str) -> str:
    year = extract_year(value)
    if year:
        value = value.split(year, 1)[0]
    return re.sub(r"[._]+", " ", value).strip()


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


def missing_core_fields(details: dict[str, Any]) -> bool:
    return not details.get("overview") or not details.get("title")


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
        poster_path=str(details.get("poster_path") or fallback.get("poster_path") or ""),
        backdrop_path=str(details.get("backdrop_path") or fallback.get("backdrop_path") or ""),
        language=language,
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


def plan_or_write_movie_nfo(context: AppContext, nfo_path: Path, metadata: MovieMetadata) -> str:
    if nfo_path.exists() and not context.metadata_output.overwrite_existing:
        return "skipped_existing"
    if context.dry_run or not context.metadata_output.write_nfo:
        return "planned"
    nfo_path.parent.mkdir(parents=True, exist_ok=True)
    nfo_path.write_text(render_movie_nfo(metadata), encoding="utf-8")
    return "written"


def render_movie_nfo(metadata: MovieMetadata) -> str:
    movie = ET.Element("movie")
    fields = {
        "title": metadata.title,
        "originaltitle": metadata.original_title,
        "year": metadata.year,
        "plot": metadata.overview,
        "runtime": str(metadata.runtime) if metadata.runtime else "",
        "tmdbid": str(metadata.tmdb_id),
    }
    for key, value in fields.items():
        child = ET.SubElement(movie, key)
        child.text = value
    for genre in metadata.genres:
        child = ET.SubElement(movie, "genre")
        child.text = genre
    ET.indent(movie, space="  ")
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n' + ET.tostring(
        movie,
        encoding="unicode",
    )
