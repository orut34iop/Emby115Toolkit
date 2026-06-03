from __future__ import annotations

import logging
import json
import threading
import time
import traceback
from pathlib import Path
from typing import Any

from emby115_v2 import cancellation, windows_admin
from emby115_v2.app import run_context
from emby115_v2.config_store import default_config_path, load_metadata_config, save_metadata_config
from emby115_v2.context import AppContext
from emby115_v2.logging_setup import setup_run_logger


SYMLINK_ACTIONS = {"build_symlink_workspace", "scan_and_link"}
V2_ACTIONS = [
    "build_symlink_workspace",
    "scan_and_link",
    "test_tmdb_config",
    "test_llm_config",
    "scrape_metadata",
    "build_cloud_scraped_library",
    "test_clouddrive2_upload_wait",
]


def create_app(access_token: str = "", host: str = "127.0.0.1", port: int = 8765):
    from fastapi import Depends, FastAPI, Header, HTTPException, Query
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles

    static_dir = Path(__file__).resolve().parent / "static"
    app = FastAPI(title="Emby115Toolkit V2 API")
    app.state.access_token = access_token
    app.state.host = host
    app.state.port = port
    app.state.run_lock = threading.Lock()
    app.state.report_dirs = {}
    app.state.runs = {}
    app.state.runs_lock = threading.Lock()
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    def require_token(
        authorization: str | None = Header(default=None),
        x_access_token: str | None = Header(default=None),
        access_token: str | None = Query(default=None),
    ) -> None:
        expected = app.state.access_token
        if not expected:
            return
        bearer = ""
        if authorization and authorization.lower().startswith("bearer "):
            bearer = authorization[7:].strip()
        supplied = x_access_token or bearer or access_token
        if supplied != expected:
            raise HTTPException(status_code=401, detail="无效或缺失的 WebUI access token")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (static_dir / "index.html").read_text(encoding="utf-8")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/actions", dependencies=[Depends(require_token)])
    def actions() -> dict[str, list[str]]:
        return {"actions": V2_ACTIONS}

    @app.get("/v1/config/metadata", dependencies=[Depends(require_token)])
    def get_metadata_config() -> dict[str, Any]:
        path = default_config_path()
        return {
            "path": str(path),
            "config": load_metadata_config(path),
        }

    @app.put("/v1/config/metadata", dependencies=[Depends(require_token)])
    def put_metadata_config(payload: dict[str, Any]) -> dict[str, str]:
        config = payload.get("config", payload)
        if not isinstance(config, dict):
            raise HTTPException(status_code=400, detail="配置必须是 JSON object")
        path = save_metadata_config(config, default_config_path())
        return {"status": "saved", "path": str(path)}

    @app.get("/v1/symlink/capability", dependencies=[Depends(require_token)])
    def symlink_capability() -> dict[str, bool]:
        can_create = windows_admin.can_create_symlink()
        return {
            "is_windows": windows_admin.is_windows(),
            "is_admin": windows_admin.is_admin(),
            "can_create_symlink": can_create,
            "requires_developer_mode": windows_admin.is_windows() and not can_create,
        }

    def _requires_symlink_capability(context: AppContext) -> bool:
        return (
            context.action in SYMLINK_ACTIONS
            and not context.dry_run
            and not windows_admin.can_create_symlink()
        )

    def _symlink_capability_response() -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={
                "detail": "当前 Windows 用户无法创建符号链接。请到系统设置中打开开发者模式后重试。",
                "requires_developer_mode": True,
            },
        )

    def _report_urls(context: AppContext, paths: dict[str, str]) -> dict[str, str]:
        return {
            **paths,
            "html_url": f"/v1/reports/{context.run_id}/report.html",
            "json_url": f"/v1/reports/{context.run_id}/report.json",
        }

    def _status_from_report(report) -> str:
        if not report.steps:
            return "success"
        status = report.steps[-1].status
        return status if status in {"success", "partial", "failed", "canceled"} else "success"

    def _run_state(run_id: str) -> dict[str, Any]:
        with app.state.runs_lock:
            state = app.state.runs.get(run_id)
            return dict(state) if state else {}

    def _update_run_state(run_id: str, **changes: Any) -> None:
        with app.state.runs_lock:
            if run_id not in app.state.runs:
                app.state.runs[run_id] = {"run_id": run_id}
            app.state.runs[run_id].update(changes)

    def _public_run_state(run_id: str) -> dict[str, Any]:
        state = _run_state(run_id)
        if not state:
            raise HTTPException(status_code=404, detail="运行记录不存在或服务已重启")
        report_paths = state.get("reports") or {}
        return {
            "run_id": state["run_id"],
            "action": state.get("action", ""),
            "dry_run": state.get("dry_run", False),
            "status": state.get("status", "queued"),
            "log_path": state.get("log_path", ""),
            "reports": report_paths,
            "error": state.get("error", ""),
        }

    def _execute_context(context: AppContext, logger_name: str = "emby115_v2_web") -> dict[str, Any]:
        logger = setup_run_logger(
            logger_name,
            context.logging.log_dir,
            context.run_id,
            context.logging.log_level,
        )
        report = run_context(context, logger)
        paths = report.write()
        reports = _report_urls(context, paths)
        app.state.report_dirs[context.run_id] = str(context.report.output_dir / context.run_id)
        return {
            "run_id": context.run_id,
            "action": context.action,
            "dry_run": context.dry_run,
            "status": _status_from_report(report),
            "reports": reports,
        }

    def _background_run(context: AppContext) -> None:
        log_path = str(context.logging.log_dir / f"{context.run_id}.log")
        try:
            _update_run_state(context.run_id, status="running")
            result = _execute_context(context, f"emby115_v2_web.{context.run_id}")
            _update_run_state(context.run_id, status=result["status"], reports=result["reports"])
        except Exception as exc:
            logger = logging.getLogger(f"emby115_v2_web.{context.run_id}")
            if logger.handlers:
                logger.exception("Web background run failed")
            else:
                logging.getLogger(__name__).exception("Web background run failed")
            _update_run_state(
                context.run_id,
                status="failed",
                error=str(exc),
                traceback=traceback.format_exc(),
                log_path=log_path,
            )
        finally:
            app.state.run_lock.release()

    def _sse(event: str, data: dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    @app.post("/v1/run", dependencies=[Depends(require_token)])
    def run(payload: dict[str, Any]):
        try:
            context = AppContext.from_dict(payload)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if _requires_symlink_capability(context):
            return _symlink_capability_response()
        if not app.state.run_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="已有工作流正在执行，请等待当前任务完成")
        try:
            return _execute_context(context)
        except Exception as exc:
            logging.getLogger(__name__).exception("Web run failed")
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            app.state.run_lock.release()

    @app.post("/v1/runs", dependencies=[Depends(require_token)])
    def start_run(payload: dict[str, Any]):
        try:
            context = AppContext.from_dict(payload)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if _requires_symlink_capability(context):
            return _symlink_capability_response()
        if not app.state.run_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="已有工作流正在执行，请等待当前任务完成")

        log_path = str(context.logging.log_dir / f"{context.run_id}.log")
        _update_run_state(
            context.run_id,
            action=context.action,
            dry_run=context.dry_run,
            status="queued",
            log_path=log_path,
            reports={},
            error="",
            cancel_requested=False,
        )
        cancellation.clear_cancel(context.run_id)
        thread = threading.Thread(target=_background_run, args=(context,), daemon=True)
        thread.start()
        return {
            "run_id": context.run_id,
            "action": context.action,
            "dry_run": context.dry_run,
            "status": "queued",
            "events_url": f"/v1/runs/{context.run_id}/events",
            "status_url": f"/v1/runs/{context.run_id}",
        }

    @app.get("/v1/runs/{run_id}", dependencies=[Depends(require_token)])
    def get_run(run_id: str) -> dict[str, Any]:
        return _public_run_state(run_id)

    @app.post("/v1/runs/{run_id}/cancel", dependencies=[Depends(require_token)])
    def cancel_run(run_id: str) -> dict[str, Any]:
        state = _run_state(run_id)
        if not state:
            raise HTTPException(status_code=404, detail="运行记录不存在或服务已重启")
        status = state.get("status", "queued")
        if status in {"success", "partial", "failed", "canceled"}:
            return {"run_id": run_id, "status": status, "cancel_requested": False}
        cancellation.request_cancel(run_id)
        _update_run_state(run_id, cancel_requested=True)
        return {"run_id": run_id, "status": status, "cancel_requested": True}

    @app.get("/v1/runs/{run_id}/events", dependencies=[Depends(require_token)])
    def run_events(run_id: str):
        if not _run_state(run_id):
            raise HTTPException(status_code=404, detail="运行记录不存在或服务已重启")

        def generate():
            last_status = None
            offset = 0
            sent_report = False
            sent_error = False
            while True:
                state = _run_state(run_id)
                if not state:
                    yield _sse("error", {"error": "运行记录不存在或服务已重启"})
                    yield _sse("done", {"status": "failed"})
                    return

                status = state.get("status", "queued")
                if status != last_status:
                    yield _sse("status", {"status": status, "run_id": run_id})
                    last_status = status

                log_path = Path(state.get("log_path") or "")
                if log_path.exists():
                    with log_path.open("r", encoding="utf-8", errors="replace") as handle:
                        handle.seek(offset)
                        for line in handle:
                            yield _sse("log", {"line": line.rstrip("\n")})
                        offset = handle.tell()

                if status in {"success", "partial", "failed", "canceled"}:
                    if state.get("reports") and not sent_report:
                        yield _sse("report", {"reports": state["reports"]})
                        sent_report = True
                    if state.get("error") and not sent_error:
                        yield _sse("error", {"error": state["error"]})
                        sent_error = True
                    yield _sse("done", {"status": status, "run_id": run_id})
                    return

                time.sleep(0.25)

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.get("/v1/reports/{run_id}/{filename}", dependencies=[Depends(require_token)])
    def report_file(run_id: str, filename: str):
        if filename not in {"report.html", "report.json"}:
            raise HTTPException(status_code=404, detail="不支持的报告文件")
        report_dir = app.state.report_dirs.get(run_id)
        if not report_dir:
            raise HTTPException(status_code=404, detail="报告不存在或服务已重启")
        path = Path(report_dir) / filename
        if not path.exists():
            raise HTTPException(status_code=404, detail="报告文件不存在")
        return FileResponse(path)

    return app
