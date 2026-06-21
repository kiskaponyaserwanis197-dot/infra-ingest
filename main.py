#!/usr/bin/env python3
"""Command-line entry point for infra-ingest."""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if SRC_DIR.is_dir():
    sys.path.insert(0, str(SRC_DIR))

from infra_ingest.cli import main


if __name__ == "__main__":
    sys.exit(main())
