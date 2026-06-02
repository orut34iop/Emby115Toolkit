import json

from emby115_v2.cli import run_cli


def test_cli_runs_build_symlink_workspace_dry_run_from_config(tmp_path, capsys):
    source = tmp_path / "source"
    target = tmp_path / "target"
    report_dir = tmp_path / "reports"
    log_dir = tmp_path / "logs"
    source.mkdir()
    (source / "movie.mkv").write_text("x", encoding="utf-8")

    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "action": "build_symlink_workspace",
                "path_pairs": [{"name": "movies", "source": str(source), "target": str(target)}],
                "report": {"output_dir": str(report_dir)},
                "logging": {"log_dir": str(log_dir)},
                "symlink": {"video_extensions": [".mkv"], "thread_count": 1},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    code = run_cli(["--config", str(config), "--dry-run", "--json"])
    output = json.loads(capsys.readouterr().out)

    assert code == 0
    assert output["action"] == "build_symlink_workspace"
    assert output["dry_run"] is True
    assert (report_dir / output["run_id"] / "report.json").exists()
    assert (report_dir / output["run_id"] / "report.html").exists()
    assert (log_dir / f"{output['run_id']}.log").exists()


def test_cli_keeps_scan_and_link_alias(tmp_path, capsys):
    source = tmp_path / "source"
    target = tmp_path / "target"
    report_dir = tmp_path / "reports"
    source.mkdir()
    (source / "movie.mkv").write_text("x", encoding="utf-8")

    code = run_cli(
        [
            "--action",
            "scan_and_link",
            "--source",
            str(source),
            "--target",
            str(target),
            "--report-dir",
            str(report_dir),
            "--dry-run",
            "--json",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert code == 0
    assert output["action"] == "scan_and_link"
    assert (report_dir / output["run_id"] / "report.json").exists()
