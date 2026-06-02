import time

from fastapi.testclient import TestClient

from emby115_v2 import windows_admin
from emby115_v2.web.api import create_app


def test_webui_serves_index():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Emby115Toolkit V2" in response.text
    assert "媒体类型" in response.text
    assert "刮削媒体元数据" in response.text
    assert "测试 TMDB 配置" in response.text
    assert "测试 LLM 配置" in response.text
    assert "metadataAutoRename" in response.text
    assert "metadataMoviesEnabled" in response.text
    assert "metadataTvshowsEnabled" in response.text
    assert "metadataMoviesPath" in response.text
    assert "metadataTvshowsPath" in response.text
    assert "symlinkMoviesEnabled" in response.text
    assert "symlinkTvshowsEnabled" in response.text
    assert "symlinkMoviesSource" in response.text
    assert "symlinkTvshowsTarget" in response.text
    assert "执行完整流程" in response.text
    assert "需要管理员权限" in response.text


def test_webui_symlink_uses_fixed_library_checklist():
    client = TestClient(create_app())

    html = client.get("/").text
    script = client.get("/static/app.js").text

    assert "symlinkMoviesEnabled" in html
    assert "symlinkTvshowsEnabled" in html
    assert "symlinkMoviesSource" in html
    assert "symlinkTvshowsTarget" in html
    assert "添加路径对" not in html
    assert "移除" not in html
    assert "pair-media-type" not in script
    assert "collectPathPairRows()" in script
    assert "normalizePathPairs" in script
    assert "pair.enabled" in script
    assert "请至少勾选一个源目录和目标目录都有效的媒体库" in script
    assert "addPair(" not in script
    assert "runFullWorkflow" in script
    assert "软链接工作区" in script


def test_webui_metadata_uses_fixed_library_checklist():
    client = TestClient(create_app())

    html = client.get("/").text
    script = client.get("/static/app.js").text

    assert "元数据媒体库列表" in html
    assert "metadataMoviesEnabled" in html
    assert "metadataTvshowsEnabled" in html
    assert "metadataMoviesPath" in html
    assert "metadataTvshowsPath" in html
    assert "name=\"metadataMediaType\"" not in html
    assert "metadata_libraries" in script
    assert "collectMetadataLibraries()" in script
    assert "normalizeMetadataLibraries" in script
    assert "metadata_output: metadataOutput" in script
    assert "不存在已勾选且路径有效的媒体库" in script
    assert "元数据刮削队列完成" in script
    assert "}元数据" in script
    assert "MEDIA_TYPE_LABELS" in script


def test_webui_uses_background_runs_and_sse():
    client = TestClient(create_app())

    script = client.get("/static/app.js").text

    assert "/v1/runs" in script
    assert "EventSource" in script
    assert "streamRunEvents" in script
    assert "pollRunStatus" in script
    assert "完整流程开始" in script
    assert "library_path: pair.target" in script


def test_webui_includes_admin_elevation_flow():
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "/v1/admin/status" in response.text
    assert "/v1/admin/restart-elevated" in response.text
    assert "emby115_v2.webui.pending_elevated_run.v1" in response.text
    assert "savePendingElevatedRun(payload)" in response.text
    assert "waitForElevatedRestart" in response.text
    assert "resumePendingElevatedRun" in response.text
    assert "sessionStorage.setItem" in response.text


def test_webui_persists_form_without_access_token():
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "emby115_v2.webui.form.v1" in response.text
    assert "localStorage.setItem(FORM_STORAGE_KEY" in response.text
    saved_config_block = response.text.split("function currentFormConfig()", 1)[1].split("function saveFormConfig()", 1)[0]
    assert "accessToken" not in saved_config_block


def test_webui_includes_metadata_config_controls():
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "emby115_v2.webui.metadata.form.v1" in response.text
    assert "test_tmdb_config" in response.text
    assert "test_llm_config" in response.text
    assert "scrape_metadata" in response.text
    assert "auto_rename" in response.text
    assert "/v1/config/metadata" in response.text


def test_actions_require_token_when_configured():
    client = TestClient(create_app(access_token="secret"))

    unauthorized = client.get("/v1/actions")
    authorized = client.get("/v1/actions", headers={"X-Access-Token": "secret"})

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert "build_symlink_workspace" in authorized.json()["actions"]
    assert "test_tmdb_config" in authorized.json()["actions"]
    assert "test_llm_config" in authorized.json()["actions"]
    assert "scrape_metadata" in authorized.json()["actions"]


def test_metadata_config_api_loads_and_saves(tmp_path, monkeypatch):
    config_path = tmp_path / "emby115_v2.config.json"
    monkeypatch.setattr("emby115_v2.web.api.default_config_path", lambda: config_path)
    client = TestClient(create_app())

    loaded = client.get("/v1/config/metadata")
    saved = client.put(
        "/v1/config/metadata",
        json={"config": {"tmdb": {"api_key": "abc"}, "metadata_output": {"media_type": "tvshows"}}},
    )

    assert loaded.status_code == 200
    assert loaded.json()["config"]["tmdb"]["language"] == "zh-CN"
    assert loaded.json()["config"]["metadata_libraries"][0]["media_type"] == "movies"
    assert loaded.json()["config"]["metadata_libraries"][1]["media_type"] == "tvshows"
    assert saved.status_code == 200
    assert config_path.exists()
    assert client.get("/v1/config/metadata").json()["config"]["tmdb"]["api_key"] == "abc"


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


def wait_for_run(client: TestClient, run_id: str) -> dict:
    for _ in range(80):
        response = client.get(f"/v1/runs/{run_id}")
        assert response.status_code == 200
        data = response.json()
        if data["status"] in {"success", "partial", "failed"}:
            return data
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} did not finish")


def test_background_run_returns_run_id_status_and_report(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    report_dir = tmp_path / "reports"
    log_dir = tmp_path / "logs"
    source.mkdir()
    (source / "movie.mkv").write_text("x", encoding="utf-8")
    client = TestClient(create_app())

    response = client.post(
        "/v1/runs",
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
    assert data["run_id"]
    assert data["events_url"].endswith("/events")

    done = wait_for_run(client, data["run_id"])

    assert done["status"] in {"success", "partial"}
    assert done["reports"]["html_url"].endswith("/report.html")
    assert client.get(done["reports"]["json_url"]).status_code == 200


def test_background_run_events_stream_status_log_report_and_done(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    report_dir = tmp_path / "reports"
    log_dir = tmp_path / "logs"
    source.mkdir()
    (source / "movie.mkv").write_text("x", encoding="utf-8")
    client = TestClient(create_app())

    started = client.post(
        "/v1/runs",
        json={
            "action": "build_symlink_workspace",
            "dry_run": True,
            "path_pairs": [{"name": "movies", "source": str(source), "target": str(target)}],
            "report": {"output_dir": str(report_dir)},
            "logging": {"log_dir": str(log_dir)},
            "symlink": {"video_extensions": [".mkv"], "thread_count": 1},
        },
    ).json()

    with client.stream("GET", started["events_url"]) as response:
        body = "\n".join(response.iter_lines())

    assert "event: status" in body
    assert "event: log" in body
    assert "event: report" in body
    assert "event: done" in body


def test_background_run_lock_rejects_concurrent_run():
    app = create_app()
    client = TestClient(app)
    app.state.run_lock.acquire()
    try:
        response = client.post("/v1/runs", json={"action": "build_symlink_workspace", "dry_run": True})
    finally:
        app.state.run_lock.release()

    assert response.status_code == 409


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


def test_background_non_dry_run_symlink_requires_admin(tmp_path, monkeypatch):
    monkeypatch.setattr(windows_admin, "is_admin", lambda: False)
    monkeypatch.setattr(windows_admin, "requires_admin_for_symlink", lambda: True)
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    (source / "movie.mkv").write_text("x", encoding="utf-8")
    client = TestClient(create_app())

    response = client.post(
        "/v1/runs",
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
