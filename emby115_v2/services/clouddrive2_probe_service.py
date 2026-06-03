from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from emby115_v2.context import AppContext
from emby115_v2.reports.writer import OperationRecord, StepResult
from emby115_v2.services.clouddrive2 import CloudDrive2UploadWaiter


class CloudDrive2UploadProbeService:
    """Verify whether mounted-disk writes can be observed as CloudDrive2 uploads."""

    step_id = "test_clouddrive2_upload_wait"

    def run(self, context: AppContext, logger: logging.Logger) -> StepResult:
        if not context.path_pairs:
            raise ValueError("test_clouddrive2_upload_wait 需要至少一个 path_pairs，target 为探测文件写入目录")

        target_dir = context.path_pairs[0].target / ".emby115_cd2_probe"
        probe_file = target_dir / f"{context.run_id}.nfo"
        summary: dict[str, Any] = {
            "target_dir": str(target_dir),
            "probe_file": str(probe_file),
            "endpoint": context.clouddrive2.endpoint,
            "dry_run": context.dry_run,
            "observed": False,
            "wait_status": "",
        }
        records: list[OperationRecord] = []

        if context.dry_run:
            records.append(
                OperationRecord(
                    action="cloud_upload_probe",
                    status="planned",
                    target_path=str(probe_file),
                    reason="dry-run 仅生成 CloudDrive2 挂载上传探测计划",
                )
            )
            return StepResult(self.step_id, "success", summary, records)

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            probe_file.write_text(
                f"Emby115Toolkit CloudDrive2 upload probe\nrun_id={context.run_id}\n",
                encoding="utf-8",
            )
        except Exception as exc:
            records.append(
                OperationRecord(
                    action="cloud_upload_probe",
                    status="failed",
                    target_path=str(probe_file),
                    reason=f"写入 CloudDrive2 探测文件失败: {exc}",
                )
            )
            summary["wait_status"] = "failed"
            return StepResult(self.step_id, "failed", summary, records)

        records.append(
            OperationRecord(
                action="cloud_upload_probe",
                status="created",
                target_path=str(probe_file),
                reason="已写入 CloudDrive2 探测文件，开始观察挂载上传任务",
            )
        )
        logger.info("CloudDrive2 上传探测文件已写入: %s", probe_file)

        try:
            wait_result = CloudDrive2UploadWaiter.from_context(context).wait_for_paths(
                [probe_file],
                context.run_id,
                logger,
            )
        except Exception as exc:
            wait_result = None
            records.append(
                OperationRecord(
                    action="cloud_upload_probe",
                    status="failed",
                    target_path=str(probe_file),
                    reason=f"CloudDrive2 上传任务探测失败: {exc}",
                )
            )
            summary["wait_status"] = "failed"
            return StepResult(self.step_id, "failed", summary, records)

        summary.update(
            {
                "observed": wait_result.observed,
                "wait_status": wait_result.status,
                "waited_seconds": round(wait_result.waited_seconds, 2),
                "watched_roots": list(wait_result.watched_roots),
                "matched_count": wait_result.matched_count,
                "active_count": wait_result.active_count,
                "error_count": wait_result.error_count,
            }
        )
        records.append(
            OperationRecord(
                action="cloud_upload_probe",
                status=wait_result.status,
                target_path=str(probe_file),
                reason=wait_result.reason,
                extra={
                    "observed": wait_result.observed,
                    "waited_seconds": round(wait_result.waited_seconds, 2),
                    "watched_roots": list(wait_result.watched_roots),
                    "matched_count": wait_result.matched_count,
                    "active_count": wait_result.active_count,
                    "error_count": wait_result.error_count,
                },
            )
        )

        if wait_result.status == "success":
            self._cleanup_probe_file(probe_file, logger, records)
            return StepResult(self.step_id, "success", summary, records)
        if wait_result.status == "not_observed":
            return StepResult(self.step_id, "partial", summary, records)
        if wait_result.status == "canceled":
            return StepResult(self.step_id, "canceled", summary, records)
        return StepResult(self.step_id, "failed", summary, records)

    def _cleanup_probe_file(self, probe_file: Path, logger: logging.Logger, records: list[OperationRecord]) -> None:
        try:
            probe_file.unlink(missing_ok=True)
            records.append(
                OperationRecord(
                    action="cloud_upload_probe_cleanup",
                    status="deleted",
                    target_path=str(probe_file),
                    reason="探测成功后已删除本地探测文件",
                )
            )
        except Exception as exc:
            logger.warning("删除 CloudDrive2 探测文件失败: %s", exc)
            records.append(
                OperationRecord(
                    action="cloud_upload_probe_cleanup",
                    status="failed",
                    target_path=str(probe_file),
                    reason=f"删除探测文件失败: {exc}",
                )
            )
