from fastapi.testclient import TestClient

from emby115_v2 import windows_admin
from emby115_v2.web.api import create_app


def test_webui_serves_index():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Emby115Toolkit V2" in response.text
    assert "媒体类型" in response.text
    assert "需要管理员权限" in response.text


def test_webui_media_type_uses_radio_controls():
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert 'type="radio"' in response.text
    assert 'value="movies"' in response.text
    assert 'value="tvshows"' in response.text
    assert "pair-name" not in response.text


def test_webui_includes_admin_elevation_flow():
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "/v1/admin/status" in response.text
    assert "/v1/admin/restart-elevated" in response.text


def test_webui_persists_form_without_access_token():
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "emby115_v2.webui.form.v1" in response.text
    assert "localStorage.setItem(FORM_STORAGE_KEY" in response.text
    saved_config_block = response.text.split("function currentFormConfig()", 1)[1].split("function saveFormConfig()", 1)[0]
    assert "accessToken" not in saved_config_block


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


def test_admin_status_reports_windows_permissions(monkeypatch):
    monkeypatch.setattr(windows_admin, "is_windows", lambda: True)
    monkeypatch.setattr(windows_admin, "is_admin", lambda: False)
    monkeypatch.setattr(windows_admin, "requires_admin_for_symlink", lambda: True)
    client = TestClient(create_app())

    response = client.get("/v1/admin/status")

    assert response.status_code == 200
    assert response.json() == {
        "is_windows": True,
        "is_admin": False,
        "requires_admin_for_symlink": True,
    }


def test_non_dry_run_symlink_requires_admin(tmp_path, monkeypatch):
    monkeypatch.setattr(windows_admin, "is_admin", lambda: False)
    monkeypatch.setattr(windows_admin, "requires_admin_for_symlink", lambda: True)
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    (source / "movie.mkv").write_text("x", encoding="utf-8")
    client = TestClient(create_app())

    response = client.post(
        "/v1/run",
        json={
            "action": "build_symlink_workspace",
            "dry_run": False,
            "path_pairs": [{"name": "movies", "source": str(source), "target": str(target)}],
            "symlink": {"video_extensions": [".mkv"], "thread_count": 1},
        },
    )

    assert response.status_code == 403
    assert response.json()["requires_elevation"] is True


def test_restart_elevated_calls_windows_helper(monkeypatch):
    calls = []
    monkeypatch.setattr(windows_admin, "is_admin", lambda: False)
    monkeypatch.setattr(
        windows_admin,
        "restart_webui_as_admin",
        lambda host, port, access_token, cwd: calls.append((host, port, access_token, cwd)),
    )
    client = TestClient(create_app(access_token="secret", host="127.0.0.1", port=8765, exit_after_elevation=False))

    response = client.post("/v1/admin/restart-elevated", headers={"X-Access-Token": "secret"})

    assert response.status_code == 200
    assert response.json()["status"] == "elevation_requested"
    assert calls


def test_run_lock_rejects_concurrent_run():
    app = create_app()
    client = TestClient(app)
    app.state.run_lock.acquire()
    try:
        response = client.post("/v1/run", json={"action": "build_symlink_workspace", "dry_run": True})
    finally:
        app.state.run_lock.release()

    assert response.status_code == 409
