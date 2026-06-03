from __future__ import annotations

import logging

from emby115_v2.context import AppContext
from emby115_v2.services.clouddrive2_probe_service import CloudDrive2UploadProbeService
from emby115_v2.reports.writer import RunReport
from emby115_v2.services.cloud_library_service import CloudScrapedLibraryService
from emby115_v2.services.metadata_service import LlmConfigTestService, MetadataScraperService, TmdbConfigTestService
from emby115_v2.services.symlink_service import ScanAndLinkService
from emby115_v2.workflow.runner import WorkflowRunner


def build_runner() -> WorkflowRunner:
    return WorkflowRunner(
        services={
            "build_symlink_workspace": ScanAndLinkService(),
            "scan_and_link": ScanAndLinkService(),
            "test_tmdb_config": TmdbConfigTestService(),
            "test_llm_config": LlmConfigTestService(),
            "scrape_metadata": MetadataScraperService(),
            "build_cloud_scraped_library": CloudScrapedLibraryService(),
            "test_clouddrive2_upload_wait": CloudDrive2UploadProbeService(),
        }
    )


def run_context(context: AppContext, logger: logging.Logger) -> RunReport:
    runner = build_runner()
    return runner.run(context, logger)
