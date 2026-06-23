import logging
import sys
from pathlib import Path

import pytest


PACKAGE_PARENT = Path(__file__).resolve().parents[2]
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))


class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture
def mock_logger():
    logger = logging.getLogger("test_logger")
    logger.handlers = []
    logger.setLevel(logging.DEBUG)
    handler = ListHandler()
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    yield logger

    logger.handlers = []
