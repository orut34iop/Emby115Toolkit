from fastapi.testclient import TestClient

from emby115_v2.web.api import create_app


def test_webui_serves_index():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Emby115Toolkit V2" in response.text


def test_actions_require_token_when_configured():
    client = TestClient(create_app(access_token="secret"))

    unauthorized = client.get("/v1/actions")
    authorized = client.get("/v1/actions", headers={"X-Access-Token": "secret"})

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert "build_symlink_workspace" in authorized.json()["actions"]


def test_run_returns_report_links_and_serves_report(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    report_dir = tmp_path / "reports"
    log_dir = tmp_path / "logs"
    source.mkdir()
    (source / "movie.mkv").write_text("x", encoding="utf-8")

    client = TestClient(create_app())
    response = client.post(
        "/v1/run",
        json={
            "action": "build_symlink_workspace",
            "dry_run": True,
            "path_pairs": [{"name": "movies", "source": str(source), "target": str(target)}],
            "report": {"output_dir": str(report_dir)},
            "logging": {"log_dir": str(log_dir)},
            "symlink": {"video_extensions": [".mkv"], "thread_count": 1},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["dry_run"] is True
    assert data["reports"]["html_url"].endswith("/report.html")
    assert data["reports"]["json_url"].endswith("/report.json")

    html_report = client.get(data["reports"]["html_url"])
    json_report = client.get(data["reports"]["json_url"])

    assert html_report.status_code == 200
    assert json_report.status_code == 200
    assert json_report.json()["run_id"] == data["run_id"]


def test_run_lock_rejects_concurrent_run():
    app = create_app()
    client = TestClient(app)
    app.state.run_lock.acquire()
    try:
        response = client.post("/v1/run", json={"action": "build_symlink_workspace"})
    finally:
        app.state.run_lock.release()

    assert response.status_code == 409
