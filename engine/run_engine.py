#!/usr/bin/env python3
"""PyInstaller / console entry for DubVIEngine.

Must use absolute imports — packaging ``dubvi/__main__.py`` as a script
breaks relative imports (``ImportError: attempted relative import with no
known parent package``).
"""

from __future__ import annotations

from dubvi.cli import main
from dubvi.events import ensure_utf8_stdio

if __name__ == "__main__":
    ensure_utf8_stdio()
    raise SystemExit(main())
