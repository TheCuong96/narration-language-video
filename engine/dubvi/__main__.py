"""Package entry for ``python -m dubvi``.

PyInstaller must use ``engine/run_engine.py`` instead of this file — relative
imports fail when the bootloader runs ``__main__.py`` as a bare script.
"""

from __future__ import annotations


def _run() -> int:
    try:
        from .cli import main
    except ImportError:  # script / frozen entry without package context
        from dubvi.cli import main  # type: ignore[no-redef]

    return main()


raise SystemExit(_run())
