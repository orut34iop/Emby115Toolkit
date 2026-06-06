from __future__ import annotations

import logging
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from emby115_v2 import cancellation
from emby115_v2.context import AppContext, PathPair
from emby115_v2.reports.writer import OperationRecord, StepResult
from emby115_v2.services.clouddrive2 import CloudDrive2UploadWaiter


VIRTUAL_DRIVE_MKDIR_RETRIES = 8
VIRTUAL_DRIVE_MKDIR_RETRY_SECONDS = 0.75


@dataclass(frozen=True)
class VideoMovePlan:
    pair_name: str
    workspace_symlink_path: Path
    real_video_path: Path | None
    target_video_path: Path
    media_type: str
    reason: str = ""


class CloudScrapedLibraryService:
    """Build a cloud-side scraped library from a local symlink workspace."""

    step_id = "build_cloud_scraped_library"

    def run(self, context: AppContext, logger: logging.Logger) -> StepResult:
        if not context.path_pairs:
            raise ValueError("build_cloud_scraped_library 需要至少一个 path_pairs 配置")

        summary: dict[str, Any] = {
            "path_pairs": len(context.path_pairs),
            "metadata_planned": 0,
            "metadata_copied": 0,
            "metadata_skipped_existing": 0,
            "metadata_failed": 0,
            "symlinks_skipped_copy": 0,
            "videos_planned": 0,
            "videos_moved": 0,
            "videos_skipped_existing": 0,
            "videos_skipped_missing_nfo": 0,
            "tvshows_skipped_missing_tvshow_nfo": 0,
            "videos_skipped_wait_unconfirmed": 0,
            "videos_failed": 0,
            "cloud_upload_wait_unconfirmed": False,
            "wait_minutes": context.cloud_library_output.wait_minutes,
            "move_videos_after_wait": True,
            "upload_wait_strategy": context.cloud_library_output.upload_wait_strategy,
            "dry_run": context.dry_run,
        }
        records: list[OperationRecord] = []
        move_plans: list[VideoMovePlan] = []

        for pair in context.path_pairs:
            if cancellation.is_cancelled(context.run_id):
                return self._canceled_result(summary, records, "扫描工作区前收到取消请求")
            logger.info("扫描本地 symlink 工作区: %s -> %s", pair.source, pair.target)
            plans, pair_records = self._copy_workspace_without_symlinks(pair, context, logger, summary)
            move_plans.extend(plans)
            records.extend(pair_records)

        summary["videos_planned"] = len(move_plans)
        if context.dry_run:
            for plan in move_plans:
                records.append(self._record_video_plan(plan, "planned", "dry-run 仅生成真实视频移动计划"))
            return StepResult(self.step_id, self._status(summary), summary, records)

        if move_plans:
            wait_result = self._wait_before_move(context, logger, records)
            if wait_result:
                wait_status, wait_reason = wait_result
                if wait_status == "canceled":
                    return self._canceled_result(summary, records, wait_reason)
                if wait_status == "unconfirmed":
                    return self._upload_wait_unconfirmed_result(summary, records, move_plans, wait_reason)
                return self._failed_result(summary, records, wait_reason)
            for plan in move_plans:
                if cancellation.is_cancelled(context.run_id):
                    return self._canceled_result(summary, records, "移动真实视频前收到取消请求")
                record = self._move_video(plan, context)
                records.append(record)
                if record.status == "moved":
                    summary["videos_moved"] += 1
                elif record.status == "skipped":
                    summary["videos_skipped_existing"] += 1
                elif record.status == "failed":
                    summary["videos_failed"] += 1
        else:
            records.append(
                OperationRecord(
                    action="move_videos",
                    status="skipped",
                    reason="没有可移动视频计划",
                )
            )

        return StepResult(self.step_id, self._status(summary), summary, records)

    def _copy_workspace_without_symlinks(
        self,
        pair: PathPair,
        context: AppContext,
        logger: logging.Logger,
        summary: dict[str, Any],
    ) -> tuple[list[VideoMovePlan], list[OperationRecord]]:
        records: list[OperationRecord] = []
        move_plans: list[VideoMovePlan] = []

        if not pair.source.exists() or not pair.source.is_dir():
            summary["metadata_failed"] += 1
            records.append(
                OperationRecord(
                    action="scan_workspace",
                    status="failed",
                    source_path=str(pair.source),
                    target_path=str(pair.target),
                    confidence="high",
                    reason="本地 symlink 工作区不存在或不是目录",
                )
            )
            return move_plans, records

        if not context.dry_run:
            create_error = self._ensure_directory(pair.target, logger)
            if create_error:
                summary["metadata_failed"] += 1
                records.append(
                    OperationRecord(
                        action="create_directory",
                        status="failed",
                        target_path=str(pair.target),
                        media_type=self._media_type(pair),
                        reason=create_error,
                        extra={"path_pair": pair.name},
                    )
                )
                return move_plans, records

        media_type = self._media_type(pair)
        for root, dirs, files in os.walk(pair.source, followlinks=False):
            if cancellation.is_cancelled(context.run_id):
                break
            root_path = Path(root)
            relative_dir = root_path.relative_to(pair.source)
            target_dir = pair.target / relative_dir

            if media_type == "tvshows" and root_path == pair.source:
                for dirname in list(dirs):
                    show_dir = root_path / dirname
                    if show_dir.is_symlink():
                        continue
                    missing_requirements = self._missing_tvshow_requirements(show_dir, context)
                    if missing_requirements:
                        dirs.remove(dirname)
                        summary["metadata_failed"] += 1
                        if any(item.lower().endswith("tvshow.nfo") for item in missing_requirements):
                            summary["tvshows_skipped_missing_tvshow_nfo"] += 1
                        summary["videos_skipped_missing_nfo"] += sum(
                            1
                            for item in missing_requirements
                            if item.lower().endswith(".nfo") and not item.lower().endswith("tvshow.nfo")
                        )
                        records.append(
                            OperationRecord(
                                action="validate_media_folder",
                                status="failed",
                                source_path=str(show_dir),
                                target_path=str(target_dir / dirname),
                                media_type=media_type,
                                title=dirname,
                                confidence="high",
                                reason="电视剧一级目录元数据不完整，未上传该目录到网盘",
                                extra={
                                    "path_pair": pair.name,
                                    "missing_requirements": missing_requirements,
                                },
                            )
                        )
                        logger.info("跳过元数据不完整的电视剧目录: %s missing=%s", show_dir, missing_requirements)
            elif media_type == "movies" and root_path == pair.source:
                for dirname in list(dirs):
                    movie_dir = root_path / dirname
                    if movie_dir.is_symlink():
                        continue
                    missing_requirements = self._missing_movie_requirements(movie_dir, context)
                    if missing_requirements:
                        dirs.remove(dirname)
                        summary["metadata_failed"] += 1
                        summary["videos_skipped_missing_nfo"] += len(missing_requirements)
                        records.append(
                            OperationRecord(
                                action="validate_media_folder",
                                status="failed",
                                source_path=str(movie_dir),
                                target_path=str(target_dir / dirname),
                                media_type=media_type,
                                title=dirname,
                                confidence="high",
                                reason="电影一级目录元数据不完整，未上传该目录到网盘",
                                extra={
                                    "path_pair": pair.name,
                                    "missing_requirements": missing_requirements,
                                },
                            )
                        )
                        logger.info("跳过元数据不完整的电影目录: %s missing=%s", movie_dir, missing_requirements)

            for dirname in list(dirs):
                dir_path = root_path / dirname
                if dir_path.is_symlink():
                    dirs.remove(dirname)
                    summary["symlinks_skipped_copy"] += 1
                    records.append(
                        OperationRecord(
                            action="skip_symlink_copy",
                            status="skipped",
                            source_path=str(dir_path),
                            target_path=str(target_dir / dirname),
                            media_type=media_type,
                            reason="阶段 A 排除 symlink 目录",
                            extra={"path_pair": pair.name},
                        )
                    )

            if not context.dry_run:
                create_error = self._ensure_directory(target_dir, logger)
                if create_error:
                    summary["metadata_failed"] += 1
                    records.append(
                        OperationRecord(
                            action="create_directory",
                            status="failed",
                            source_path=str(root_path),
                            target_path=str(target_dir),
                            media_type=media_type,
                            reason=create_error,
                            extra={"path_pair": pair.name},
                        )
                    )
                    dirs.clear()
                    continue

            for filename in files:
                if cancellation.is_cancelled(context.run_id):
                    break
                source_file = root_path / filename
                target_file = target_dir / filename
                if source_file.is_symlink():
                    summary["symlinks_skipped_copy"] += 1
                    move_plan = None
                    missing_nfo_path = None
                    if source_file.suffix.lower() in context.symlink.video_extensions:
                        required_nfo = self._matching_nfo_path(source_file)
                        if required_nfo.exists():
                            move_plan = self._build_video_move_plan(pair, source_file, target_file, media_type, context)
                        else:
                            missing_nfo_path = required_nfo
                            summary["videos_skipped_missing_nfo"] += 1
                    if move_plan:
                        move_plans.append(move_plan)
                    if not move_plan:
                        reason = (
                            "阶段 A 排除 symlink 文件；同目录缺少同名 NFO，未创建真实视频移动计划"
                            if missing_nfo_path
                            else "阶段 A 排除 symlink 文件；不是配置的视频后缀"
                        )
                        records.append(
                            OperationRecord(
                                action="skip_symlink_copy",
                                status="skipped",
                                source_path=str(source_file),
                                target_path=str(target_file),
                                media_type=media_type,
                                reason=reason,
                                extra={
                                    "path_pair": pair.name,
                                    "required_nfo_path": str(missing_nfo_path) if missing_nfo_path else "",
                                },
                            )
                        )
                    continue

                summary["metadata_planned"] += 1
                record = self._copy_metadata_file(source_file, target_file, context, media_type, pair.name)
                records.append(record)
                if record.status == "copied":
                    summary["metadata_copied"] += 1
                elif record.status == "skipped":
                    summary["metadata_skipped_existing"] += 1
                elif record.status == "failed":
                    summary["metadata_failed"] += 1

        logger.info(
            "阶段 A 完成 path_pair=%s metadata_planned=%s copied=%s skipped=%s failed=%s symlinks=%s",
            pair.name,
            summary["metadata_planned"],
            summary["metadata_copied"],
            summary["metadata_skipped_existing"],
            summary["metadata_failed"],
            summary["symlinks_skipped_copy"],
        )
        return move_plans, records

    def _copy_metadata_file(
        self,
        source_file: Path,
        target_file: Path,
        context: AppContext,
        media_type: str,
        pair_name: str,
    ) -> OperationRecord:
        if context.dry_run:
            return OperationRecord(
                action="copy_metadata",
                status="planned",
                source_path=str(source_file),
                target_path=str(target_file),
                media_type=media_type,
                reason="dry-run 仅生成非 symlink 文件复制计划",
                extra={"path_pair": pair_name},
            )
        try:
            if target_file.exists() and not context.cloud_library_output.overwrite_metadata:
                return OperationRecord(
                    action="copy_metadata",
                    status="skipped",
                    source_path=str(source_file),
                    target_path=str(target_file),
                    media_type=media_type,
                    reason="目标元数据已存在，默认跳过",
                    extra={"path_pair": pair_name},
                )
            create_error = self._ensure_directory(target_file.parent)
            if create_error:
                raise OSError(create_error)
            shutil.copy2(source_file, target_file)
            return OperationRecord(
                action="copy_metadata",
                status="copied",
                source_path=str(source_file),
                target_path=str(target_file),
                media_type=media_type,
                reason="阶段 A 已复制非 symlink 文件",
                extra={"path_pair": pair_name},
            )
        except Exception as exc:
            return OperationRecord(
                action="copy_metadata",
                status="failed",
                source_path=str(source_file),
                target_path=str(target_file),
                media_type=media_type,
                reason=f"复制非 symlink 文件失败: {exc}",
                extra={"path_pair": pair_name},
            )

    def _build_video_move_plan(
        self,
        pair: PathPair,
        workspace_symlink_path: Path,
        target_video_path: Path,
        media_type: str,
        context: AppContext,
    ) -> VideoMovePlan | None:
        if workspace_symlink_path.suffix.lower() not in context.symlink.video_extensions:
            return None
        real_video_path, reason = self._resolve_symlink_target(workspace_symlink_path)
        return VideoMovePlan(pair.name, workspace_symlink_path, real_video_path, target_video_path, media_type, reason)

    def _matching_nfo_path(self, workspace_symlink_path: Path) -> Path:
        expected_nfo = workspace_symlink_path.with_suffix(".nfo")
        if expected_nfo.exists():
            return expected_nfo
        try:
            expected_stem = workspace_symlink_path.stem.casefold()
            for candidate in workspace_symlink_path.parent.iterdir():
                if candidate.stem.casefold() == expected_stem and candidate.suffix.casefold() == ".nfo":
                    return candidate
        except OSError:
            pass
        return expected_nfo

    def _missing_movie_requirements(self, movie_dir: Path, context: AppContext) -> list[str]:
        missing: list[str] = []
        for video_path in self._iter_workspace_video_symlinks(movie_dir, context):
            required_nfo = self._matching_nfo_path(video_path)
            if not required_nfo.exists():
                missing.append(str(required_nfo))
        return missing

    def _missing_tvshow_requirements(self, show_dir: Path, context: AppContext) -> list[str]:
        missing: list[str] = []
        tvshow_nfo = show_dir / "tvshow.nfo"
        if not tvshow_nfo.exists():
            missing.append(str(tvshow_nfo))
        if not self._has_poster_image(show_dir):
            missing.append(str(show_dir / "poster.jpg"))
        for video_path in self._iter_workspace_video_symlinks(show_dir, context):
            required_nfo = self._matching_nfo_path(video_path)
            if not required_nfo.exists():
                missing.append(str(required_nfo))
        return missing

    def _iter_workspace_video_symlinks(self, media_dir: Path, context: AppContext):
        for root, _dirs, files in os.walk(media_dir, followlinks=False):
            for filename in files:
                path = Path(root) / filename
                if path.is_symlink() and path.suffix.lower() in context.symlink.video_extensions:
                    yield path

    def _has_poster_image(self, show_dir: Path) -> bool:
        for suffix in (".jpg", ".jpeg", ".png", ".webp"):
            poster = show_dir / f"poster{suffix}"
            if poster.exists() and not poster.is_symlink():
                return True
        return False

    def _resolve_symlink_target(self, workspace_symlink_path: Path) -> tuple[Path | None, str]:
        try:
            raw_target = os.readlink(workspace_symlink_path)
            real_video_path = self._normalize_readlink_target(raw_target, workspace_symlink_path)
        except OSError as readlink_exc:
            try:
                real_video_path = workspace_symlink_path.resolve(strict=True)
            except OSError as resolve_exc:
                return None, f"无法解析 symlink 指向的真实视频: readlink={readlink_exc}; resolve={resolve_exc}"
            return real_video_path, "已通过 Path.resolve 解析 symlink 指向的真实视频"

        try:
            real_video_path.stat()
        except OSError as exc:
            return None, f"symlink 指向的真实视频不可访问: {real_video_path}: {exc}"
        return real_video_path, "已通过 os.readlink 解析 symlink 指向的真实视频"

    def _normalize_readlink_target(self, raw_target: str, workspace_symlink_path: Path) -> Path:
        target = raw_target
        if target.startswith("\\\\?\\UNC\\"):
            target = "\\\\" + target[8:]
        elif target.startswith("\\\\?\\") or target.startswith("\\??\\"):
            target = target[4:]
        target_path = Path(target)
        if not target_path.is_absolute():
            target_path = workspace_symlink_path.parent / target_path
        return target_path

    def _wait_before_move(
        self,
        context: AppContext,
        logger: logging.Logger,
        records: list[OperationRecord],
    ) -> tuple[str, str] | None:
        strategy = context.cloud_library_output.upload_wait_strategy
        if strategy in {"clouddrive2", "clouddrive2_or_fixed"}:
            cd2_result = self._wait_with_clouddrive2(context, logger, records)
            if cd2_result == "success":
                return None
            if cd2_result == "canceled":
                return ("canceled", "等待 CloudDrive2 上传任务期间收到取消请求")
            if strategy == "clouddrive2":
                if cd2_result == "timeout":
                    return (
                        "unconfirmed",
                        "CloudDrive2 上传任务探测未能确认元数据上传完成，已跳过真实视频移动",
                    )
                return ("failed", "CloudDrive2 上传任务探测未能确认元数据上传完成")
            records.append(
                OperationRecord(
                    action="wait_for_cloud_upload",
                    status="fallback",
                    reason="CloudDrive2 上传任务探测未确认完成，回退到固定等待",
                    extra={"strategy": strategy},
                )
            )
            logger.warning("CloudDrive2 上传任务探测未确认完成，回退到固定等待")
        return self._fixed_wait_before_move(context, logger, records)

    def _wait_with_clouddrive2(
        self,
        context: AppContext,
        logger: logging.Logger,
        records: list[OperationRecord],
    ) -> str:
        target_roots = [pair.target for pair in context.path_pairs]
        try:
            result = CloudDrive2UploadWaiter.from_context(context).wait_for_paths(target_roots, context.run_id, logger)
        except Exception as exc:
            result = None
            records.append(
                OperationRecord(
                    action="wait_for_cloud_upload",
                    status="failed",
                    reason=f"CloudDrive2 上传任务探测初始化失败: {exc}",
                    extra={"strategy": context.cloud_library_output.upload_wait_strategy},
                )
            )
            logger.error("CloudDrive2 上传任务探测初始化失败: %s", exc)
            return "failed"

        record_status = result.status
        record_reason = result.reason
        if result.status == "not_observed":
            record_status = "success"
            record_reason = "静默窗口内没有匹配上传任务，视为 CloudDrive2 上传队列已静默"
        records.append(
            OperationRecord(
                action="wait_for_cloud_upload",
                status=record_status,
                reason=record_reason,
                extra={
                    "strategy": context.cloud_library_output.upload_wait_strategy,
                    "raw_status": result.status,
                    "observed": result.observed,
                    "waited_seconds": round(result.waited_seconds, 2),
                    "watched_roots": list(result.watched_roots),
                    "active_count": result.active_count,
                    "error_count": result.error_count,
                    "matched_count": result.matched_count,
                },
            )
        )
        if result.status == "success":
            logger.info("CloudDrive2 上传任务已确认完成，进入真实视频移动阶段")
            return "success"
        if result.status == "not_observed":
            logger.info("CloudDrive2 上传任务列表在静默窗口内无匹配任务，视为上传队列已静默，进入真实视频移动阶段")
            return "success"
        logger.warning("CloudDrive2 上传任务探测结果: %s %s", result.status, result.reason)
        return result.status

    def _fixed_wait_before_move(
        self,
        context: AppContext,
        logger: logging.Logger,
        records: list[OperationRecord],
    ) -> tuple[str, str] | None:
        wait_seconds = context.cloud_library_output.wait_minutes * 60
        records.append(
            OperationRecord(
                action="wait_for_cloud_upload",
                status="planned" if wait_seconds else "skipped",
                reason=(
                    f"固定等待 {context.cloud_library_output.wait_minutes} 分钟，给网络硬盘异步上传缓存留时间"
                    if wait_seconds
                    else "等待时间为 0，直接进入真实视频移动阶段"
                ),
                extra={"strategy": "fixed"},
            )
        )
        if wait_seconds <= 0:
            return None

        logger.info("阶段 A 已完成，等待 %s 分钟后开始移动真实视频", context.cloud_library_output.wait_minutes)
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            if cancellation.is_cancelled(context.run_id):
                return ("canceled", "等待上传缓冲期间收到取消请求")
            time.sleep(min(5.0, max(0.1, deadline - time.monotonic())))
        return None

    def _move_video(self, plan: VideoMovePlan, context: AppContext) -> OperationRecord:
        if not plan.real_video_path:
            return self._record_video_plan(plan, "failed", plan.reason)
        try:
            if not plan.real_video_path.exists():
                return self._record_video_plan(plan, "failed", "symlink 指向的真实视频不存在")
            if plan.target_video_path.exists() and not context.cloud_library_output.overwrite_videos:
                return self._record_video_plan(plan, "skipped", "目标视频已存在，默认跳过")
            create_error = self._ensure_directory(plan.target_video_path.parent)
            if create_error:
                return self._record_video_plan(plan, "failed", create_error)
            if plan.target_video_path.exists() and context.cloud_library_output.overwrite_videos:
                plan.target_video_path.unlink()
            shutil.move(str(plan.real_video_path), str(plan.target_video_path))
            return self._record_video_plan(plan, "moved", "阶段 B 已移动 symlink 指向的真实视频")
        except Exception as exc:
            return self._record_video_plan(plan, "failed", f"移动真实视频失败: {exc}")

    def _record_video_plan(self, plan: VideoMovePlan, status: str, reason: str) -> OperationRecord:
        return OperationRecord(
            action="move_real_video",
            status=status,
            source_path=str(plan.workspace_symlink_path),
            target_path=str(plan.target_video_path),
            media_type=plan.media_type,
            reason=reason,
            extra={
                "path_pair": plan.pair_name,
                "real_video_path": str(plan.real_video_path) if plan.real_video_path else "",
                "real_video_resolve_reason": plan.reason,
            },
        )

    def _canceled_result(self, summary: dict[str, Any], records: list[OperationRecord], reason: str) -> StepResult:
        summary["canceled"] = True
        records.append(OperationRecord(action="cancel", status="canceled", reason=reason))
        return StepResult(self.step_id, "canceled", summary, records)

    def _failed_result(self, summary: dict[str, Any], records: list[OperationRecord], reason: str) -> StepResult:
        summary["failed_before_video_move"] = True
        records.append(OperationRecord(action="wait_for_cloud_upload", status="failed", reason=reason))
        return StepResult(self.step_id, "failed", summary, records)

    def _upload_wait_unconfirmed_result(
        self,
        summary: dict[str, Any],
        records: list[OperationRecord],
        move_plans: list[VideoMovePlan],
        reason: str,
    ) -> StepResult:
        summary["cloud_upload_wait_unconfirmed"] = True
        summary["videos_skipped_wait_unconfirmed"] = len(move_plans)
        for plan in move_plans:
            records.append(
                self._record_video_plan(
                    plan,
                    "skipped",
                    "CloudDrive2 未确认元数据上传完成，已跳过真实视频移动",
                )
            )
        records.append(
            OperationRecord(
                action="move_videos",
                status="skipped",
                reason=reason,
                extra={"skipped_count": len(move_plans)},
            )
        )
        stage_a_had_effect = any(
            int(summary.get(key, 0))
            for key in (
                "metadata_copied",
                "metadata_skipped_existing",
                "symlinks_skipped_copy",
                "videos_planned",
            )
        )
        return StepResult(self.step_id, "partial" if stage_a_had_effect else "failed", summary, records)

    def _status(self, summary: dict[str, Any]) -> str:
        failures = int(summary.get("metadata_failed", 0)) + int(summary.get("videos_failed", 0))
        successes = int(summary.get("metadata_copied", 0)) + int(summary.get("videos_moved", 0))
        missing_nfo = int(summary.get("videos_skipped_missing_nfo", 0))
        skipped_tvshows = int(summary.get("tvshows_skipped_missing_tvshow_nfo", 0))
        if failures and successes:
            return "partial"
        if failures:
            return "failed"
        if missing_nfo or skipped_tvshows:
            return "partial"
        return "success"

    def _media_type(self, pair: PathPair) -> str:
        return "tvshows" if pair.name.lower() in {"tv", "tvshow", "tvshows", "series"} else "movies"

    def _ensure_directory(self, path: Path, logger: logging.Logger | None = None) -> str:
        try:
            parts = path.parts
            if not parts:
                return ""
            current = Path(parts[0])
            for part in parts[1:]:
                current = current / part
                error = self._create_single_directory_with_retry(current, logger)
                if error:
                    return error
            return ""
        except Exception as exc:
            return f"创建目标目录失败: {exc}"

    def _create_single_directory_with_retry(self, path: Path, logger: logging.Logger | None = None) -> str:
        for attempt in range(VIRTUAL_DRIVE_MKDIR_RETRIES):
            try:
                os.mkdir(path)
                return ""
            except FileExistsError:
                return ""
            except OSError as exc:
                if self._directory_name_visible(path):
                    return ""
                if attempt + 1 < VIRTUAL_DRIVE_MKDIR_RETRIES and self._should_retry_directory_error(exc):
                    if logger:
                        logger.warning(
                            "创建目录暂时失败，准备重试 attempt=%s path=%s error=%s",
                            attempt + 1,
                            path,
                            exc,
                        )
                    time.sleep(VIRTUAL_DRIVE_MKDIR_RETRY_SECONDS)
                    continue
                return f"创建目标目录失败: {exc}"
        return f"创建目标目录失败: 超过重试次数 path={path}"

    def _directory_name_visible(self, path: Path) -> bool:
        try:
            parent = path.parent
            name = path.name.casefold()
            return any(child.casefold() == name for child in os.listdir(parent))
        except OSError:
            return False

    def _should_retry_directory_error(self, exc: OSError) -> bool:
        winerror = getattr(exc, "winerror", None)
        if winerror in {50, 53, 64, 87, 123, 183}:
            return True
        return isinstance(exc, (FileNotFoundError, PermissionError))
