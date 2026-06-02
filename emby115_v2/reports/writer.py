from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from emby115_v2.context import AppContext


@dataclass
class OperationRecord:
    action: str
    status: str
    source_path: str = ""
    target_path: str = ""
    media_type: str = ""
    title: str = ""
    year: str = ""
    season: str = ""
    episode: str = ""
    confidence: str = ""
    reason: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    step_id: str
    status: str
    summary: dict[str, Any]
    records: list[OperationRecord] = field(default_factory=list)


class RunReport:
    def __init__(self, context: AppContext):
        self.context = context
        self.records: list[OperationRecord] = []
        self.steps: list[StepResult] = []

    def add_record(self, record: OperationRecord) -> None:
        self.records.append(record)

    def add_step(self, result: StepResult) -> None:
        self.steps.append(result)
        self.records.extend(result.records)

    def write(self) -> dict[str, str]:
        run_dir = self.context.report.output_dir / self.context.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        json_path = run_dir / "report.json"
        html_path = run_dir / "report.html"

        payload = {
            "run_id": self.context.run_id,
            "workflow_id": self.context.workflow_id,
            "action": self.context.action,
            "dry_run": self.context.dry_run,
            "context": self.context.to_dict(),
            "steps": [
                {
                    "step_id": step.step_id,
                    "status": step.status,
                    "summary": step.summary,
                    "records": [asdict(record) for record in step.records],
                }
                for step in self.steps
            ],
            "records": [asdict(record) for record in self.records],
        }

        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        html_path.write_text(self._render_html(payload), encoding="utf-8")
        return {"json": str(json_path), "html": str(html_path)}

    def _render_html(self, payload: dict[str, Any]) -> str:
        rows = []
        for record in payload["records"]:
            rows.append(
                "<tr>"
                f"<td>{html.escape(record['action'])}</td>"
                f"<td>{html.escape(record['status'])}</td>"
                f"<td>{html.escape(record['source_path'])}</td>"
                f"<td>{html.escape(record['target_path'])}</td>"
                f"<td>{html.escape(record['media_type'])}</td>"
                f"<td>{html.escape(record['title'])}</td>"
                f"<td>{html.escape(record['year'])}</td>"
                f"<td>{html.escape(record['season'])}</td>"
                f"<td>{html.escape(record['episode'])}</td>"
                f"<td>{html.escape(record['confidence'])}</td>"
                f"<td>{html.escape(record['reason'])}</td>"
                "</tr>"
            )
        summary_rows = []
        for step in payload["steps"]:
            summary_rows.append(
                "<tr>"
                f"<td>{html.escape(step['step_id'])}</td>"
                f"<td>{html.escape(step['status'])}</td>"
                f"<td><pre>{html.escape(json.dumps(step['summary'], ensure_ascii=False, indent=2))}</pre></td>"
                "</tr>"
            )

        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Emby115Toolkit V2 Report {html.escape(payload['run_id'])}</title>
  <style>
    body {{ font-family: Segoe UI, Microsoft YaHei, sans-serif; margin: 24px; color: #1f2937; }}
    h1, h2 {{ margin-bottom: 8px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 28px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; vertical-align: top; font-size: 13px; }}
    th {{ background: #f3f4f6; text-align: left; }}
    pre {{ white-space: pre-wrap; margin: 0; }}
  </style>
</head>
<body>
  <h1>Emby115Toolkit V2 执行报告</h1>
  <p>Run ID: {html.escape(payload['run_id'])}</p>
  <p>Action: {html.escape(payload['action'])}</p>
  <p>Dry Run: {str(payload['dry_run']).lower()}</p>
  <h2>步骤摘要</h2>
  <table>
    <thead><tr><th>步骤</th><th>状态</th><th>摘要</th></tr></thead>
    <tbody>{''.join(summary_rows)}</tbody>
  </table>
  <h2>操作记录</h2>
  <table>
    <thead><tr><th>动作</th><th>状态</th><th>原路径</th><th>目标路径</th><th>类型</th><th>标题</th><th>年份</th><th>季</th><th>集</th><th>置信度</th><th>原因</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</body>
</html>
"""
