from __future__ import annotations

import logging

from emby115_v2.context import AppContext
from emby115_v2.reports.writer import RunReport
from emby115_v2.services.symlink_service import ScanAndLinkService
from emby115_v2.workflow.runner import WorkflowRunner


def build_runner() -> WorkflowRunner:
    return WorkflowRunner(
        services={
            "build_symlink_workspace": ScanAndLinkService(),
            "scan_and_link": ScanAndLinkService(),
        }
    )


def run_context(context: AppContext, logger: logging.Logger) -> RunReport:
    runner = build_runner()
    return runner.run(context, logger)
