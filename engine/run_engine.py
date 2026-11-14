#!/usr/bin/env python3
"""PyInstaller / console entry for DubVIEngine.

Must use absolute imports — packaging ``dubvi/__main__.py`` as a script
breaks relative imports (``ImportError: attempted relative import with no
known parent package``).
"""

from __future__ import annotations

from dubvi.cli import main
from dubvi.events import ensure_utf8_stdio
from dubvi.mei_cleanup import cleanup_orphan_mei_dirs

if __name__ == "__main__":
    ensure_utf8_stdio()
    # Reclaim leftover onefile extracts from prior force-kills / crashes.
    cleanup_orphan_mei_dirs()
    raise SystemExit(main())
