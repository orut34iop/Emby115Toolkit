from pathlib import Path

from emby115_v2.context import AppContext
from emby115_v2.reports.writer import OperationRecord, RunReport, StepResult


def test_html_report_includes_filter_controls_and_record_metadata(tmp_path):
    context = AppContext.from_dict(
        {
            "action": "scrape_metadata",
            "run_id": "filter-report",
            "dry_run": True,
            "report": {"output_dir": str(tmp_path / "reports")},
        }
    )
    report = RunReport(context)
    report.add_step(
        StepResult(
            "metadata",
            "partial",
            {"manual_review": 1, "failed": 1},
            [
                OperationRecord(
                    action="scrape_metadata",
                    status="manual_review",
                    source_path=r"C:\working-emby\movies\unknown.mkv",
                    target_path=r"C:\working-emby\movies\unknown.nfo",
                    media_type="movies",
                    title="待确认影片",
                    year="",
                    confidence="low",
                    reason="TMDB 未返回可用候选",
                ),
                OperationRecord(
                    action="download_image",
                    status="failed",
                    source_path="https://image.tmdb.org/poster.jpg",
                    target_path=r"C:\working-emby\movies\poster.jpg",
                    media_type="movies",
                    title="失败影片",
                    year="2026",
                    confidence="",
                    reason="urlopen error timed out",
                ),
            ],
        )
    )

    paths = report.write()
    html_text = Path(paths["html"]).read_text(encoding="utf-8")

    assert 'aria-label="操作记录筛选"' in html_text
    assert 'id="statusFilter"' in html_text
    assert 'id="actionFilter"' in html_text
    assert 'id="mediaTypeFilter"' in html_text
    assert 'id="textFilter"' in html_text
    assert 'data-quick="manual_review"' in html_text
    assert 'data-quick="failed"' in html_text
    assert 'id="filterCount"' in html_text
    assert 'id="recordsTable"' in html_text
    assert 'data-status="manual_review"' in html_text
    assert 'data-status="failed"' in html_text
    assert 'data-action="scrape_metadata"' in html_text
    assert 'data-media-type="movies"' in html_text
    assert "TMDB 未返回可用候选" in html_text
    assert "urlopen error timed out" in html_text
    assert "显示 ${visible} / ${rows.length} 条" in html_text
