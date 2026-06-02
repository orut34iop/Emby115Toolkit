from __future__ import annotations

import logging
from typing import Protocol

from emby115_v2.context import AppContext
from emby115_v2.reports.writer import RunReport, StepResult


class Service(Protocol):
    def run(self, context: AppContext, logger: logging.Logger) -> StepResult:
        ...


class WorkflowRunner:
    def __init__(self, services: dict[str, Service]):
        self.services = services

    def run(self, context: AppContext, logger: logging.Logger) -> RunReport:
        if context.action not in self.services:
            raise ValueError(f"不支持的 action: {context.action}")

        report = RunReport(context)
        logger.info("开始执行 action=%s run_id=%s", context.action, context.run_id)
        step = self.services[context.action].run(context, logger)
        report.add_step(step)
        logger.info("完成执行 action=%s status=%s", context.action, step.status)
        return report

