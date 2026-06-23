#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


VERSION_ROOT = Path(__file__).resolve().parent
PACKAGE_PARENT = VERSION_ROOT.parent
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

from emby115_v2.cli import main


if __name__ == "__main__":
    main()
