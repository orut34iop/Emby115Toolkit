from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from emby115_v2.context import AppContext
from emby115_v2.reports.writer import OperationRecord, StepResult


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


class MetadataScraperService:
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

        records = []
        extensions = set(context.symlink.video_extensions)
        for video_path in iter_video_files(library_path, extensions):
            records.append(
                OperationRecord(
                    action="scrape_metadata",
                    status="planned" if context.dry_run else "manual_review",
                    source_path=str(video_path),
                    target_path=str(video_path.with_suffix(".nfo")),
                    media_type=context.metadata_output.media_type,
                    title=video_path.stem,
                    reason="元数据刮削骨架已扫描到媒体文件；TMDB 匹配将在下一轮实现",
                    extra={
                        "write_nfo": context.metadata_output.write_nfo,
                        "download_images": context.metadata_output.download_images,
                        "overwrite_existing": context.metadata_output.overwrite_existing,
                    },
                )
            )

        logger.info("元数据刮削骨架扫描完成 library=%s planned=%s", library_path, len(records))
        return StepResult(
            step_id="scrape_metadata",
            status="planned" if context.dry_run else "manual_review",
            summary={
                "media_type": context.metadata_output.media_type,
                "library_path": str(library_path),
                "dry_run": context.dry_run,
                "planned": len(records),
                "tmdb_language": context.tmdb.language,
                "tmdb_fallback_language": context.tmdb.fallback_language,
                "llm_enabled": context.llm.enabled,
            },
            records=records,
        )


def iter_video_files(root: Path, extensions: set[str]):
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in extensions:
            yield path
