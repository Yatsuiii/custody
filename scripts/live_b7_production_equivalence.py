#!/usr/bin/env python3
"""Command-line entry point for the P7 live production B7 proof."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from live.b7_production_equivalence import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
