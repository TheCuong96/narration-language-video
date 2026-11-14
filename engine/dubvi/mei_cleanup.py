"""Remove orphan PyInstaller onefile extract dirs (%TEMP%\\_MEI*).

Onefile builds unpack into a fresh _MEI* folder each run. Force-kill
(taskkill /F), crashes, or abrupt exit skip the bootloader cleanup and
leave ~1GB folders behind. Safe to delete any _MEI* that is not the
currently running extract (_MEIPASS).
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path


def cleanup_orphan_mei_dirs(*, ignore_meipass: bool = True) -> int:
    """Delete orphan ``_MEI*`` dirs under the system temp folder.

    Returns the number of directories removed (best-effort).
    """
    temp = Path(tempfile.gettempdir())
    if not temp.is_dir():
        return 0

    keep: Path | None = None
    if ignore_meipass:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            try:
                keep = Path(meipass).resolve()
            except OSError:
                keep = None

    removed = 0
    try:
        entries = list(temp.iterdir())
    except OSError:
        return 0

    for path in entries:
        name = path.name
        if not name.startswith("_MEI"):
            continue
        if not path.is_dir():
            continue
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if keep is not None and resolved == keep:
            continue
        try:
            shutil.rmtree(path, ignore_errors=True)
            if not path.exists():
                removed += 1
        except OSError:
            pass
    return removed
