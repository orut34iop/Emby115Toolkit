import time

from fastapi.testclient import TestClient

from emby115_v2 import cancellation, windows_admin
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
    assert "metadataDownloadSeasonPosters" in response.text
    assert "metadataMoviesEnabled" in response.text
    assert "metadataTvshowsEnabled" in response.text
    assert "metadataMoviesPath" in response.text
    assert "metadataTvshowsPath" in response.text
    assert "symlinkMoviesEnabled" in response.text
    assert "symlinkTvshowsEnabled" in response.text
    assert "symlinkMoviesSource" in response.text
    assert "symlinkTvshowsTarget" in response.text
    assert "执行完整流程" in response.text
    assert "构建网盘已刮削媒体库" in response.text
    assert "cloudMoviesEnabled" in response.text
    assert "cloudTvshowsEnabled" in response.text
    assert "cloudWaitStrategy" in response.text
    assert "testCloudDrive2Button" in response.text
    assert "需要管理员权限" not in response.text


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
    assert "metadataWorkflowActive" in script
    assert "metadataCancelRequested" in script
    assert "requestMetadataCancel" in script
    assert "已请求取消元数据刮削" in script
    assert "元数据刮削队列已取消" in script
    assert "}元数据" in script
    assert "MEDIA_TYPE_LABELS" in script


def test_webui_cloud_library_card_uses_fixed_checklist_and_probe():
    client = TestClient(create_app())

    html = client.get("/").text
    script = client.get("/static/app.js").text

    assert "构建网盘已刮削媒体库" in html
    assert "cloudMoviesEnabled" in html
    assert "cloudTvshowsEnabled" in html
    assert "cloudMoviesSource" in html
    assert "cloudTvshowsTarget" in html
    assert "cloudWaitStrategy" in html
    assert "clouddrive2_or_fixed" in html
    assert "cloudMetadataOnly" in html
    assert "testCloudDrive2Button" in html
    assert "emby115_v2.webui.cloud.form.v1" in script
    assert "collectCloudLibraries()" in script
    assert "normalizeCloudLibraries" in script
    assert "build_cloud_scraped_library" in script
    assert "test_clouddrive2_upload_wait" in script
    assert "cloud_library_output" in script
    assert "clouddrive2" in script
    assert "requestCloudCancel" in script
    assert "CloudDrive2 上传探测" in script


def test_webui_layout_css_prevents_horizontal_overflow():
    client = TestClient(create_app())

    html = client.get("/").text
    css = client.get("/static/styles.css").text

    assert "responsive-workflow-layout" in html
    assert "overflow-x: hidden" in css
    assert "grid-template-columns: minmax(0, 1fr) minmax(320px, 380px)" in css
    assert "overflow-wrap: anywhere" in css
    assert "@media (max-width: 1280px)" in css
    assert ".run-panel" in css
    assert "position: sticky" in css


def test_webui_uses_background_runs_and_sse():
    client = TestClient(create_app())

    script = client.get("/static/app.js").text

    assert "/v1/runs" in script
    assert "EventSource" in script
    assert "streamRunEvents" in script
    assert "pollRunStatus" in script
    assert "完整流程开始" in script
    assert "构建本地软链接工作区 -> 刮削媒体元数据 -> 构建网盘已刮削媒体库" in script
    assert "library_path: pair.target" in script
    assert "source: pair.target" in script
    assert "cloudLibrariesFromPathPairs" in script
    assert "完整流程开始网盘导入" in script
    assert "网盘已刮削媒体库" in script
    assert "软链接工作区步骤未成功完成，完整流程已停止" in script
    assert "confirmCloudMoveIfNeeded" in script
    assert "window.confirm" in script
    assert "当前 C 盘 symlink 工作区中的链接变成过期链接" in script
    assert "runFullWorkflowPayload" in script
    assert "metadataLibrariesFromPathPairs" in script
    assert "fullWorkflowCancelRequested" in script
    assert "requestFullWorkflowCancel" in script
    assert "取消执行" in script
    assert "/cancel" in script
    assert "canceled" in script
    assert "result-status" in script
    assert "部分成功" in script
    assert "updateLastReportStatus" in script


def test_webui_uses_symlink_capability_check_without_uac_restart():
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "/v1/symlink/capability" in response.text
    assert "needsDeveloperMode" in response.text
    assert "requires_developer_mode" in response.text
    assert "请到系统设置中打开开发者模式" in response.text
    assert "/v1/admin/restart-elevated" not in response.text
    assert "pending_elevated_run" not in response.text
    assert "sessionStorage.setItem" not in response.text


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
    assert "metadata_form_version: 2" in response.text
    assert "test_tmdb_config" in response.text
    assert "test_llm_config" in response.text
    assert "scrape_metadata" in response.text
    assert "auto_rename" in response.text
    assert "download_season_posters" in response.text
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
    assert "build_cloud_scraped_library" in authorized.json()["actions"]
    assert "test_clouddrive2_upload_wait" in authorized.json()["actions"]


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


def test_cancel_background_run_sets_cancel_flag():
    app = create_app()
    client = TestClient(app)
    run_id = "cancel-test-run"
    app.state.runs[run_id] = {"run_id": run_id, "status": "running"}
    cancellation.clear_cancel(run_id)

    response = client.post(f"/v1/runs/{run_id}/cancel")

    assert response.status_code == 200
    assert response.json()["cancel_requested"] is True
    assert cancellation.is_cancelled(run_id) is True
    assert app.state.runs[run_id]["cancel_requested"] is True
    cancellation.clear_cancel(run_id)


def test_symlink_capability_reports_developer_mode_requirement(monkeypatch):
    monkeypatch.setattr(windows_admin, "is_windows", lambda: True)
    monkeypatch.setattr(windows_admin, "is_admin", lambda: False)
    monkeypatch.setattr(windows_admin, "can_create_symlink", lambda: False)
    client = TestClient(create_app())

    response = client.get("/v1/symlink/capability")

    assert response.status_code == 200
    assert response.json() == {
        "is_windows": True,
        "is_admin": False,
        "can_create_symlink": False,
        "requires_developer_mode": True,
    }


def test_non_dry_run_symlink_requires_developer_mode_when_symlink_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(windows_admin, "can_create_symlink", lambda: False)
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
    assert response.json()["requires_developer_mode"] is True
    assert "打开开发者模式" in response.json()["detail"]


def test_background_non_dry_run_symlink_requires_developer_mode_when_symlink_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(windows_admin, "can_create_symlink", lambda: False)
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
    assert response.json()["requires_developer_mode"] is True


def test_run_lock_rejects_concurrent_run():
    app = create_app()
    client = TestClient(app)
    app.state.run_lock.acquire()
    try:
        response = client.post("/v1/run", json={"action": "build_symlink_workspace", "dry_run": True})
    finally:
        app.state.run_lock.release()

    assert response.status_code == 409
