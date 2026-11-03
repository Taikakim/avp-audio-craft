# Owner: THE-FINN (created 2026-11-03)
"""Find a run after the __theme sorting, for code that builds a path from a name at run time.

    from run_paths import find_run
    d = find_run(RUNS, name)   # RUNS / name if it exists there, else RUNS / <theme> / name from __MOVED_MAP.json

A literal path can be rewritten in the source; `RUNS / name` in a loop cannot, so those call this.
"""
import json
from pathlib import Path


def find_run(root, name):
    root = Path(root); first, *rest = Path(str(name)).parts
    direct = root / first
    if direct.exists():
        return direct.joinpath(*rest)
    try:
        theme = json.loads((root / "__MOVED_MAP.json").read_text()).get(first)
    except (OSError, ValueError):
        theme = None
    return (root / theme / first if theme else direct).joinpath(*rest)   # unknown name: the plain path, so the caller's own error names it
