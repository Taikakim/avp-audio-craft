"""Put THIS worktree's eval/ first on sys.path (tests must never import the shared tree)."""
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
if str(EVAL) in sys.path:
    sys.path.remove(str(EVAL))
sys.path.insert(0, str(EVAL))
