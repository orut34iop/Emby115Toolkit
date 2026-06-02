from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from emby115_v2.app import run_context
from emby115_v2.context import AppContext
from emby115_v2.logging_setup import setup_run_logger


def create_app(access_token: str = ""):
    from fastapi import Depends, FastAPI, Header, HTTPException, Query
    from fastapi.responses import FileResponse, HTMLResponse
    from fastapi.staticfiles import StaticFiles

    static_dir = Path(__file__).resolve().parent / "static"
    app = FastAPI(title="Emby115Toolkit V2 API")
    app.state.access_token = access_token
    app.state.run_lock = threading.Lock()
    app.state.report_dirs = {}
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
        return {"actions": ["build_symlink_workspace", "scan_and_link"]}

    @app.post("/v1/run", dependencies=[Depends(require_token)])
    def run(payload: dict[str, Any]) -> dict[str, Any]:
        if not app.state.run_lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="已有工作流正在执行，请等待当前任务完成")
        try:
            context = AppContext.from_dict(payload)
            logger = setup_run_logger(
                "emby115_v2_web",
                context.logging.log_dir,
                context.run_id,
                context.logging.log_level,
            )
            report = run_context(context, logger)
            paths = report.write()
            app.state.report_dirs[context.run_id] = str(context.report.output_dir / context.run_id)
            return {
                "run_id": context.run_id,
                "action": context.action,
                "dry_run": context.dry_run,
                "reports": {
                    **paths,
                    "html_url": f"/v1/reports/{context.run_id}/report.html",
                    "json_url": f"/v1/reports/{context.run_id}/report.json",
                },
            }
        except Exception as exc:
            logging.getLogger(__name__).exception("Web run failed")
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            app.state.run_lock.release()

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
