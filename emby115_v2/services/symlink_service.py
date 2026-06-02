from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from emby115_v2.context import AppContext, PathPair
from emby115_v2.reports.writer import OperationRecord, StepResult


@dataclass(frozen=True)
class LinkPlan:
    pair_name: str
    source_path: Path
    target_path: Path


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
            "dry_run": context.dry_run,
        }

        plans: list[LinkPlan] = []
        for pair in context.path_pairs:
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
        if context.dry_run:
            for plan in plans:
                records.append(self._record_plan(plan, status="planned", reason="dry-run 仅生成计划"))
            return StepResult(self.step_id, "success", summary, records)

        with ThreadPoolExecutor(max_workers=context.symlink.thread_count) as executor:
            futures = [executor.submit(self._create_link, plan) for plan in plans]
            for future in as_completed(futures):
                record = future.result()
                records.append(record)
                if record.status == "created":
                    summary["created"] += 1
                elif record.status == "skipped":
                    summary["skipped_existing"] += 1
                elif record.status == "failed":
                    summary["failed"] += 1

        status = "failed" if summary["failed"] else "success"
        return StepResult(self.step_id, status, summary, records)

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

        pair.target.mkdir(parents=True, exist_ok=True)
        extensions = context.symlink.video_extensions
        for root, _, files in os.walk(pair.source):
            root_path = Path(root)
            for filename in files:
                source_path = root_path / filename
                if source_path.suffix.lower() not in extensions:
                    continue
                relative_path = source_path.relative_to(pair.source)
                target_path = pair.target / relative_path
                plans.append(LinkPlan(pair.name, source_path, target_path))

        return plans, records

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
            media_type="video",
            confidence="high",
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
