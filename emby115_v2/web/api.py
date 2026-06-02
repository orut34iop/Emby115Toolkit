from __future__ import annotations

import logging
from typing import Any

from emby115_v2.app import run_context
from emby115_v2.context import AppContext
from emby115_v2.logging_setup import setup_run_logger


def create_app():
    from fastapi import FastAPI, HTTPException

    app = FastAPI(title="Emby115Toolkit V2 API")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/actions")
    def actions() -> dict[str, list[str]]:
        return {"actions": ["scan_and_link"]}

    @app.post("/v1/run")
    def run(payload: dict[str, Any]) -> dict[str, Any]:
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
            return {"run_id": context.run_id, "action": context.action, "reports": paths}
        except Exception as exc:
            logging.getLogger(__name__).exception("Web run failed")
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app

