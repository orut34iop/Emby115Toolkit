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
            "videos_failed": 0,
            "wait_minutes": context.cloud_library_output.wait_minutes,
            "move_videos_after_wait": context.cloud_library_output.move_videos_after_wait,
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

        if context.cloud_library_output.move_videos_after_wait and move_plans:
            wait_result = self._wait_before_move(context, logger, records)
            if wait_result:
                return self._canceled_result(summary, records, wait_result)
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
                    reason="配置为不移动真实视频或没有可移动视频计划",
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
            pair.target.mkdir(parents=True, exist_ok=True)

        media_type = self._media_type(pair)
        for root, dirs, files in os.walk(pair.source, followlinks=False):
            if cancellation.is_cancelled(context.run_id):
                break
            root_path = Path(root)
            relative_dir = root_path.relative_to(pair.source)
            target_dir = pair.target / relative_dir

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
                target_dir.mkdir(parents=True, exist_ok=True)

            for filename in files:
                if cancellation.is_cancelled(context.run_id):
                    break
                source_file = root_path / filename
                target_file = target_dir / filename
                if source_file.is_symlink():
                    summary["symlinks_skipped_copy"] += 1
                    move_plan = self._build_video_move_plan(pair, source_file, target_file, media_type, context)
                    if move_plan:
                        move_plans.append(move_plan)
                    records.append(
                        OperationRecord(
                            action="skip_symlink_copy",
                            status="skipped",
                            source_path=str(source_file),
                            target_path=str(target_file),
                            media_type=media_type,
                            reason="阶段 A 排除 symlink 文件；真实视频将在阶段 B 移动",
                            extra={
                                "path_pair": pair.name,
                                "real_video_path": str(move_plan.real_video_path) if move_plan and move_plan.real_video_path else "",
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
            target_file.parent.mkdir(parents=True, exist_ok=True)
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
        try:
            real_video_path = workspace_symlink_path.resolve(strict=True)
            reason = "已解析 symlink 指向的真实视频"
        except OSError as exc:
            real_video_path = None
            reason = f"无法解析 symlink 指向的真实视频: {exc}"
        return VideoMovePlan(pair.name, workspace_symlink_path, real_video_path, target_video_path, media_type, reason)

    def _wait_before_move(
        self,
        context: AppContext,
        logger: logging.Logger,
        records: list[OperationRecord],
    ) -> str:
        wait_seconds = context.cloud_library_output.wait_minutes * 60
        records.append(
            OperationRecord(
                action="wait_for_cloud_upload",
                status="planned" if wait_seconds else "skipped",
                reason=(
                    f"等待 {context.cloud_library_output.wait_minutes} 分钟，给网络硬盘异步上传缓存留时间"
                    if wait_seconds
                    else "等待时间为 0，直接进入真实视频移动阶段"
                ),
            )
        )
        if wait_seconds <= 0:
            return ""

        logger.info("阶段 A 已完成，等待 %s 分钟后开始移动真实视频", context.cloud_library_output.wait_minutes)
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            if cancellation.is_cancelled(context.run_id):
                return "等待上传缓冲期间收到取消请求"
            time.sleep(min(5.0, max(0.1, deadline - time.monotonic())))
        return ""

    def _move_video(self, plan: VideoMovePlan, context: AppContext) -> OperationRecord:
        if not plan.real_video_path:
            return self._record_video_plan(plan, "failed", plan.reason)
        try:
            if not plan.real_video_path.exists():
                return self._record_video_plan(plan, "failed", "symlink 指向的真实视频不存在")
            if plan.target_video_path.exists() and not context.cloud_library_output.overwrite_videos:
                return self._record_video_plan(plan, "skipped", "目标视频已存在，默认跳过")
            plan.target_video_path.parent.mkdir(parents=True, exist_ok=True)
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
            },
        )

    def _canceled_result(self, summary: dict[str, Any], records: list[OperationRecord], reason: str) -> StepResult:
        summary["canceled"] = True
        records.append(OperationRecord(action="cancel", status="canceled", reason=reason))
        return StepResult(self.step_id, "canceled", summary, records)

    def _status(self, summary: dict[str, Any]) -> str:
        failures = int(summary.get("metadata_failed", 0)) + int(summary.get("videos_failed", 0))
        successes = int(summary.get("metadata_copied", 0)) + int(summary.get("videos_moved", 0))
        if failures and successes:
            return "partial"
        if failures:
            return "failed"
        return "success"

    def _media_type(self, pair: PathPair) -> str:
        return "tvshows" if pair.name.lower() in {"tv", "tvshow", "tvshows", "series"} else "movies"
