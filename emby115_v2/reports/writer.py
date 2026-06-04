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
        def text_value(value: Any) -> str:
            if value is None:
                return ""
            return str(value)

        def escape_text(value: Any) -> str:
            return html.escape(text_value(value))

        def escape_attr(value: Any) -> str:
            return html.escape(text_value(value), quote=True)

        def render_options(values: set[str], all_label: str) -> str:
            options = [f'<option value="">{html.escape(all_label)}</option>']
            for value in sorted(item for item in values if item):
                options.append(f'<option value="{escape_attr(value)}">{escape_text(value)}</option>')
            return "".join(options)

        statuses = {text_value(record.get("status")) for record in payload["records"]}
        actions = {text_value(record.get("action")) for record in payload["records"]}
        media_types = {text_value(record.get("media_type")) for record in payload["records"]}
        status_options = render_options(statuses, "全部状态")
        action_options = render_options(actions, "全部动作")
        media_type_options = render_options(media_types, "全部类型")

        rows = []
        for record in payload["records"]:
            searchable = " ".join(
                text_value(record.get(key))
                for key in (
                    "action",
                    "status",
                    "source_path",
                    "target_path",
                    "media_type",
                    "title",
                    "year",
                    "season",
                    "episode",
                    "confidence",
                    "reason",
                )
            )
            rows.append(
                "<tr "
                f'data-status="{escape_attr(record.get("status"))}" '
                f'data-action="{escape_attr(record.get("action"))}" '
                f'data-media-type="{escape_attr(record.get("media_type"))}" '
                f'data-search="{escape_attr(searchable)}">'
                f"<td>{escape_text(record.get('action'))}</td>"
                f"<td>{escape_text(record.get('status'))}</td>"
                f"<td>{escape_text(record.get('source_path'))}</td>"
                f"<td>{escape_text(record.get('target_path'))}</td>"
                f"<td>{escape_text(record.get('media_type'))}</td>"
                f"<td>{escape_text(record.get('title'))}</td>"
                f"<td>{escape_text(record.get('year'))}</td>"
                f"<td>{escape_text(record.get('season'))}</td>"
                f"<td>{escape_text(record.get('episode'))}</td>"
                f"<td>{escape_text(record.get('confidence'))}</td>"
                f"<td>{escape_text(record.get('reason'))}</td>"
                "</tr>"
            )
        summary_rows = []
        for step in payload["steps"]:
            summary_rows.append(
                "<tr>"
                f"<td>{escape_text(step['step_id'])}</td>"
                f"<td>{escape_text(step['status'])}</td>"
                f"<td><pre>{escape_text(json.dumps(step['summary'], ensure_ascii=False, indent=2))}</pre></td>"
                "</tr>"
            )

        styles = """
    :root { color-scheme: light; }
    body { font-family: Segoe UI, Microsoft YaHei, sans-serif; margin: 24px; color: #1f2937; background: #ffffff; }
    h1, h2 { margin-bottom: 8px; }
    .muted { color: #6b7280; }
    .filters { display: grid; gap: 10px; margin: 12px 0 16px; padding: 12px; border: 1px solid #d1d5db; background: #f9fafb; }
    .filter-grid { display: grid; grid-template-columns: repeat(4, minmax(140px, 1fr)); gap: 10px; }
    label { display: grid; gap: 4px; color: #4b5563; font-size: 13px; }
    input, select, button { min-height: 32px; border: 1px solid #cbd5e1; border-radius: 4px; padding: 5px 8px; font: inherit; }
    button { cursor: pointer; background: #ffffff; color: #1f2937; }
    button[aria-pressed="true"] { border-color: #2563eb; background: #dbeafe; color: #1d4ed8; font-weight: 700; }
    .quick-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    #filterCount { margin-left: auto; color: #4b5563; font-size: 13px; }
    table { border-collapse: collapse; width: 100%; margin: 12px 0 28px; }
    th, td { border: 1px solid #d1d5db; padding: 8px; vertical-align: top; font-size: 13px; }
    th { background: #f3f4f6; text-align: left; position: sticky; top: 0; z-index: 1; }
    tr[hidden] { display: none; }
    pre { white-space: pre-wrap; margin: 0; }
    @media (max-width: 960px) { .filter-grid { grid-template-columns: 1fr; } }
"""
        scripts = """
    (() => {
      const rows = Array.from(document.querySelectorAll("#recordsTable tbody tr"));
      const statusFilter = document.querySelector("#statusFilter");
      const actionFilter = document.querySelector("#actionFilter");
      const mediaTypeFilter = document.querySelector("#mediaTypeFilter");
      const textFilter = document.querySelector("#textFilter");
      const filterCount = document.querySelector("#filterCount");
      const quickButtons = Array.from(document.querySelectorAll("[data-quick]"));
      let quickMode = "all";

      function resetDetailedFilters() {
        statusFilter.value = "";
        actionFilter.value = "";
        mediaTypeFilter.value = "";
        textFilter.value = "";
      }

      function rowMatches(row) {
        const status = row.dataset.status || "";
        const action = row.dataset.action || "";
        const mediaType = row.dataset.mediaType || "";
        const search = (row.dataset.search || "").toLowerCase();
        const query = textFilter.value.trim().toLowerCase();

        if (quickMode === "manual_review" && status !== "manual_review") return false;
        if (quickMode === "failed" && status !== "failed") return false;
        if (statusFilter.value && status !== statusFilter.value) return false;
        if (actionFilter.value && action !== actionFilter.value) return false;
        if (mediaTypeFilter.value && mediaType !== mediaTypeFilter.value) return false;
        if (query && !search.includes(query)) return false;
        return true;
      }

      function updateQuickButtons() {
        for (const button of quickButtons) {
          button.setAttribute("aria-pressed", button.dataset.quick === quickMode ? "true" : "false");
        }
      }

      function applyFilters() {
        let visible = 0;
        for (const row of rows) {
          const matched = rowMatches(row);
          row.hidden = !matched;
          if (matched) visible += 1;
        }
        filterCount.textContent = `显示 ${visible} / ${rows.length} 条`;
        updateQuickButtons();
      }

      for (const button of quickButtons) {
        button.addEventListener("click", () => {
          quickMode = button.dataset.quick || "all";
          resetDetailedFilters();
          applyFilters();
        });
      }

      for (const control of [statusFilter, actionFilter, mediaTypeFilter, textFilter]) {
        const eventName = control === textFilter ? "input" : "change";
        control.addEventListener(eventName, () => {
          quickMode = "custom";
          applyFilters();
        });
      }

      applyFilters();
    })();
"""

        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Emby115Toolkit V2 Report {escape_text(payload['run_id'])}</title>
  <style>
{styles}
  </style>
</head>
<body>
  <h1>Emby115Toolkit V2 执行报告</h1>
  <p>Run ID: {escape_text(payload['run_id'])}</p>
  <p>Action: {escape_text(payload['action'])}</p>
  <p>Dry Run: {str(payload['dry_run']).lower()}</p>
  <h2>步骤摘要</h2>
  <table>
    <thead><tr><th>步骤</th><th>状态</th><th>摘要</th></tr></thead>
    <tbody>{''.join(summary_rows)}</tbody>
  </table>
  <h2>操作记录</h2>
  <section class="filters" aria-label="操作记录筛选">
    <div class="filter-grid">
      <label>状态
        <select id="statusFilter">{status_options}</select>
      </label>
      <label>动作
        <select id="actionFilter">{action_options}</select>
      </label>
      <label>媒体类型
        <select id="mediaTypeFilter">{media_type_options}</select>
      </label>
      <label>关键词
        <input id="textFilter" placeholder="搜索路径、标题、原因">
      </label>
    </div>
    <div class="quick-row">
      <button type="button" data-quick="all" aria-pressed="true">全部</button>
      <button type="button" data-quick="manual_review" aria-pressed="false">待人工 review</button>
      <button type="button" data-quick="failed" aria-pressed="false">失败</button>
      <span id="filterCount" aria-live="polite"></span>
    </div>
    <div class="muted">可组合下拉条件和关键词搜索；快速按钮会重置其它筛选条件。</div>
  </section>
  <table id="recordsTable">
    <thead><tr><th>动作</th><th>状态</th><th>原路径</th><th>目标路径</th><th>类型</th><th>标题</th><th>年份</th><th>季</th><th>集</th><th>置信度</th><th>原因</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <script>
{scripts}
  </script>
</body>
</html>
"""
