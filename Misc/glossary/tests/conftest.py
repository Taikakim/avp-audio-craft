# Owner: WINTERMUTE (created 2026-10-26)
import sys
from pathlib import Path

MISC = str(Path(__file__).resolve().parents[2])      # .../Misc  (parent of the `glossary` package)
if MISC not in sys.path:
    sys.path.insert(0, MISC)
