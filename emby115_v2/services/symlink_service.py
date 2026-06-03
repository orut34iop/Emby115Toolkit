from __future__ import annotations

import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from emby115_v2 import cancellation
from emby115_v2.context import AppContext, PathPair
from emby115_v2.reports.writer import OperationRecord, StepResult

YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
SEASON_EPISODE_RE = re.compile(r"(?i)\bS(?P<season>\d{1,2})E(?P<episode>\d{1,3})\b")
SEASON_RE = re.compile(r"(?i)(?:\bS(?P<snum>\d{1,2})\b|Season[\s._-]*(?P<season>\d{1,2})|第(?P<zh>[一二三四五六七八九十\d]+)季)")
BRACKET_RE = re.compile(r"[\[{【].*?[\]}】]")
TMDB_RE = re.compile(r"\{tmdbid=\d+\}", re.IGNORECASE)
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]")
QUALITY_RE = re.compile(
    r"(?i)\b("
    r"2160p|1080p|1080i|720p|4k|8k|blu-?ray|bdrip|web-?dl|webrip|hdtv|remux|"
    r"x26[45]|h\.?26[45]|hevc|avc|dv|hdr|sdr|ddp?|dts|aac|atmos"
    r")\b"
)


@dataclass(frozen=True)
class LinkPlan:
    pair_name: str
    source_path: Path
    target_path: Path
    media_type: str
    title: str = ""
    year: str = ""
    season: str = ""
    episode: str = ""
    confidence: str = "high"
    reason: str = ""


class ScanAndLinkService:
    """Build the local symlink workspace from mounted CD2 source folders."""

    step_id = "build_symlink_workspace"

    def run(self, context: AppContext, logger: logging.Logger) -> StepResult:
        if not context.path_pairs:
            raise ValueError("build_symlink_workspace 需要至少一个 path_pairs 配置")

        records: list[OperationRecord] = []
        summary = {
            "path_pairs": len(context.path_pairs),
            "planned": 0,
            "created": 0,
            "skipped_existing": 0,
            "failed": 0,
            "broken_links": 0,
            "manual_review": 0,
            "dry_run": context.dry_run,
        }

        plans: list[LinkPlan] = []
        for pair in context.path_pairs:
            if cancellation.is_cancelled(context.run_id):
                return self._canceled_result(summary, records, "扫描源目录前收到取消请求")
            logger.info("扫描源目录: %s -> %s", pair.source, pair.target)
            pair_plans, pair_records = self._build_plans(pair, context)
            plans.extend(pair_plans)
            records.extend(pair_records)

            if context.symlink.report_broken_links:
                broken = self._find_broken_links(pair.target)
                summary["broken_links"] += len(broken)
                for path in broken:
                    records.append(
                        OperationRecord(
                            action="report_broken_symlink",
                            status="warning",
                            source_path=str(path),
                            target_path="",
                            confidence="high",
                            reason="目标工作区中存在失效 symlink；默认只报告，不自动删除。",
                        )
                    )

        summary["planned"] = len(plans)
        summary["manual_review"] = len([plan for plan in plans if plan.confidence == "low"])
        if context.dry_run:
            for plan in plans:
                if cancellation.is_cancelled(context.run_id):
                    return self._canceled_result(summary, records, "dry-run 生成计划时收到取消请求")
                status = "manual_review" if plan.confidence == "low" else "planned"
                reason = plan.reason or "dry-run 仅生成计划"
                records.append(self._record_plan(plan, status=status, reason=reason))
            return StepResult(self.step_id, "success", summary, records)

        with ThreadPoolExecutor(max_workers=context.symlink.thread_count) as executor:
            futures = []
            for plan in plans:
                if cancellation.is_cancelled(context.run_id):
                    break
                futures.append(executor.submit(self._create_link, plan))
            for future in as_completed(futures):
                record = future.result()
                records.append(record)
                if record.status == "created":
                    summary["created"] += 1
                elif record.status == "skipped":
                    summary["skipped_existing"] += 1
                elif record.status == "failed":
                    summary["failed"] += 1
                elif record.status == "manual_review":
                    summary["manual_review"] += 1
                if cancellation.is_cancelled(context.run_id):
                    return self._canceled_result(summary, records, "创建 symlink 时收到取消请求")

        status = "canceled" if cancellation.is_cancelled(context.run_id) else "failed" if summary["failed"] else "success"
        return StepResult(self.step_id, status, summary, records)

    def _canceled_result(self, summary: dict[str, int | bool], records: list[OperationRecord], reason: str) -> StepResult:
        summary["canceled"] = True
        records.append(OperationRecord(action="cancel", status="canceled", reason=reason))
        return StepResult(self.step_id, "canceled", summary, records)

    def _build_plans(
        self,
        pair: PathPair,
        context: AppContext,
    ) -> tuple[list[LinkPlan], list[OperationRecord]]:
        records: list[OperationRecord] = []
        plans: list[LinkPlan] = []

        if not pair.source.exists() or not pair.source.is_dir():
            records.append(
                OperationRecord(
                    action="scan_source",
                    status="failed",
                    source_path=str(pair.source),
                    target_path=str(pair.target),
                    confidence="high",
                    reason="源目录不存在或不是目录",
                )
            )
            return plans, records

        if not context.dry_run:
            pair.target.mkdir(parents=True, exist_ok=True)
        extensions = context.symlink.video_extensions
        for root, _, files in os.walk(pair.source):
            if cancellation.is_cancelled(context.run_id):
                break
            root_path = Path(root)
            for filename in files:
                if cancellation.is_cancelled(context.run_id):
                    break
                source_path = root_path / filename
                if source_path.suffix.lower() not in extensions:
                    continue
                plans.append(self._build_plan(pair, source_path))

        return plans, records

    def _build_plan(self, pair: PathPair, source_path: Path) -> LinkPlan:
        media_type = self._media_type(pair)
        if media_type == "tvshows":
            return self._build_tvshow_plan(pair, source_path)
        return self._build_movie_plan(pair, source_path)

    def _build_movie_plan(self, pair: PathPair, source_path: Path) -> LinkPlan:
        title, year = self._movie_title_year(source_path)
        if not title:
            relative_path = source_path.relative_to(pair.source)
            return LinkPlan(
                pair.name,
                source_path,
                pair.target / relative_path,
                "movies",
                confidence="low",
                reason="无法可靠识别电影名，保持原目录不动，待人工确认。",
            )
        folder_name = self._title_folder(title, year)
        return LinkPlan(
            pair.name,
            source_path,
            pair.target / folder_name / source_path.name,
            "movies",
            title=title,
            year=year,
            reason="按电影一级目录标准化",
        )

    def _build_tvshow_plan(self, pair: PathPair, source_path: Path) -> LinkPlan:
        relative_path = source_path.relative_to(pair.source)
        season_episode = SEASON_EPISODE_RE.search(source_path.stem)
        season = self._format_season(season_episode.group("season")) if season_episode else self._season_from_path(relative_path)
        episode = season_episode.group("episode") if season_episode else ""

        series_source = self._series_source_path(relative_path, source_path)
        title, year = self._tv_title_year(series_source.name, source_path.stem)
        if not title or not season:
            return LinkPlan(
                pair.name,
                source_path,
                pair.target / relative_path,
                "tvshows",
                title=title,
                year=year,
                season=season,
                episode=episode,
                confidence="low",
                reason="无法可靠识别剧名或季集信息，保持原目录不动，待人工确认。",
            )

        series_folder = self._title_folder(title, year)
        second_level = self._tv_second_level(relative_path, season, source_path)
        return LinkPlan(
            pair.name,
            source_path,
            pair.target / series_folder / second_level / source_path.name,
            "tvshows",
            title=title,
            year=year,
            season=season,
            episode=episode,
            reason="按电视剧一级剧名目录和二级季目录标准化",
        )

    def _create_link(self, plan: LinkPlan) -> OperationRecord:
        try:
            if plan.target_path.exists() or plan.target_path.is_symlink():
                return self._record_plan(plan, status="skipped", reason="目标 symlink 或文件已存在，增量同步跳过")

            plan.target_path.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(str(plan.source_path), str(plan.target_path))
            return self._record_plan(plan, status="created", reason="已创建 symlink")
        except Exception as exc:
            return self._record_plan(plan, status="failed", reason=f"创建 symlink 失败: {exc}")

    def _record_plan(self, plan: LinkPlan, status: str, reason: str) -> OperationRecord:
        return OperationRecord(
            action="create_symlink",
            status=status,
            source_path=str(plan.source_path),
            target_path=str(plan.target_path),
            media_type=plan.media_type,
            title=plan.title,
            year=plan.year,
            season=plan.season,
            episode=plan.episode,
            confidence=plan.confidence,
            reason=reason,
            extra={"path_pair": plan.pair_name},
        )

    def _find_broken_links(self, folder: Path) -> list[Path]:
        if not folder.exists():
            return []
        broken: list[Path] = []
        for root, _, files in os.walk(folder):
            for filename in files:
                path = Path(root) / filename
                if path.is_symlink() and not path.exists():
                    broken.append(path)
        return broken

    def _media_type(self, pair: PathPair) -> str:
        return "tvshows" if pair.name.lower() in {"tv", "tvshow", "tvshows", "series"} else "movies"

    def _movie_title_year(self, source_path: Path) -> tuple[str, str]:
        parent_title, parent_year = self._title_year_from_text(source_path.parent.name)
        stem_title, stem_year = self._title_year_from_text(source_path.stem)
        if stem_title and stem_year:
            combined_title = self._combined_movie_title(parent_title, parent_year, stem_title, stem_year)
            if combined_title:
                return combined_title, stem_year
            return stem_title, stem_year or parent_year
        if parent_title and parent_year:
            return parent_title, parent_year
        if parent_title and not self._looks_like_release_folder(source_path.parent.name):
            return parent_title, parent_year
        if stem_title:
            return stem_title, stem_year or parent_year
        return parent_title, parent_year

    def _combined_movie_title(self, parent_title: str, parent_year: str, stem_title: str, stem_year: str) -> str:
        if not parent_title or not parent_year or parent_year != stem_year:
            return ""
        if not CJK_RE.search(parent_title) or not LATIN_RE.search(stem_title):
            return ""
        if self._normalized_title_token(stem_title) in self._normalized_title_token(parent_title):
            return ""
        return f"{parent_title}.{stem_title}"

    def _normalized_title_token(self, title: str) -> str:
        return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", title).lower()

    def _tv_title_year(self, folder_name: str, filename_stem: str) -> tuple[str, str]:
        folder_title, folder_year = self._title_year_from_text(folder_name, stop_at_season=True)
        file_title, file_year = self._title_year_from_text(filename_stem, stop_at_season=True)
        return folder_title or file_title, folder_year or file_year

    def _title_year_from_text(self, text: str, stop_at_season: bool = False) -> tuple[str, str]:
        cleaned = TMDB_RE.sub("", text)
        year_match = YEAR_RE.search(cleaned)
        year = year_match.group(1) if year_match else ""
        title_part = cleaned[: year_match.start()] if year_match else cleaned

        if stop_at_season:
            season_match = SEASON_EPISODE_RE.search(title_part) or SEASON_RE.search(title_part)
            if season_match:
                title_part = title_part[: season_match.start()]

        title_part = BRACKET_RE.sub("", title_part)
        title_part = QUALITY_RE.split(title_part, maxsplit=1)[0]
        title_part = SEASON_RE.split(title_part, maxsplit=1)[0]
        title = self._clean_title(title_part)
        return title, year

    def _clean_title(self, value: str) -> str:
        value = re.sub(r"(?i)\{tmdbid=\d+\}", "", value)
        value = value.replace("_", " ").strip()
        value = re.sub(r"[\s.·・_-]+$", "", value)
        value = re.sub(r"[\s(（\[]+$", "", value)
        value = re.sub(r"^[\s.·・_\-\[\]【】{}()（）]+", "", value)
        value = re.sub(r"\s+", " ", value)
        value = re.sub(r"(完结|全集)$", "", value).strip()
        return value

    def _title_folder(self, title: str, year: str) -> str:
        return f"{title} ({year})" if year else title

    def _looks_like_release_folder(self, folder_name: str) -> bool:
        return bool(QUALITY_RE.search(folder_name) or SEASON_RE.search(folder_name))

    def _series_source_path(self, relative_path: Path, source_path: Path) -> Path:
        parts = relative_path.parts[:-1]
        if not parts:
            return source_path.parent
        first = parts[0].lower()
        if first in {"tv", "tvshow", "tvshows", "series", "电视剧"} and len(parts) >= 2:
            return Path(parts[1])
        return Path(parts[0])

    def _tv_second_level(self, relative_path: Path, season: str, source_path: Path) -> str:
        parts = relative_path.parts[:-1]
        if len(parts) >= 2:
            first = parts[0].lower()
            if first in {"tv", "tvshow", "tvshows", "series", "电视剧"}:
                remaining = parts[2:]
            else:
                remaining = parts[1:]
            if remaining and self._path_has_season_marker(remaining):
                return str(Path(*remaining))
        release_folder = self._season_release_folder_from_filename(source_path.stem, season)
        if release_folder:
            return release_folder
        return f"Season {season}"

    def _path_has_season_marker(self, parts: tuple[str, ...]) -> bool:
        return any(SEASON_RE.search(part) for part in parts)

    def _season_release_folder_from_filename(self, stem: str, season: str) -> str:
        season_episode = SEASON_EPISODE_RE.search(stem)
        if not season_episode:
            return ""

        suffix = stem[season_episode.end() :]
        quality_match = QUALITY_RE.search(suffix)
        if not quality_match:
            return ""

        prefix = stem[: season_episode.start()].rstrip(" ._-")
        release_suffix = suffix[quality_match.start() :].lstrip(" ._-")
        if not prefix or not release_suffix:
            return ""

        season_token = f"S{season}"
        return f"{prefix}.{season_token}.{release_suffix}".strip(" ._-")

    def _season_from_path(self, relative_path: Path) -> str:
        for part in relative_path.parts[:-1]:
            match = SEASON_RE.search(part)
            if match:
                value = match.group("snum") or match.group("season") or match.group("zh") or ""
                return self._format_season(value)
        return ""

    def _format_season(self, value: str) -> str:
        try:
            number = int(value)
        except ValueError:
            number = self._zh_number(value)
        return f"{number:02d}" if number else ""

    def _zh_number(self, value: str) -> int:
        if value.isdigit():
            return int(value)
        digits = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
        if value == "十":
            return 10
        if value.startswith("十"):
            return 10 + digits.get(value[1:], 0)
        if "十" in value:
            left, right = value.split("十", 1)
            return digits.get(left, 0) * 10 + digits.get(right, 0)
        return digits.get(value, 0)
