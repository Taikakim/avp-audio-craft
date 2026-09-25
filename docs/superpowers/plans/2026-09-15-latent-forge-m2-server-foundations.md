# Latent Forge M2 — Server forge foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the render server a `/forge/*` API — async jobs with progress, a sequenced log, uploads, file library, audio refs, sessions, presets, beat analysis, Bungee stretch, SAME chroma, statistics, backbone switching — plus recorded contract fixtures, so every later milestone (server and client) has a foundation.

**Architecture:** `eval/explorer_render_server.py` gains only: a self-locating `sys.path`, two one-line hooks (log → sequenced log, step callback → progress), two extra response keys, and `forge_api.bind(...)` + `include_router`. All routes live in `eval/forge_api.py`; all logic in the pure package `eval/forge/` (no FastAPI imports), unit-tested on CPU. GPU work stays in the resident process under the existing `GPU_LOCK`.

**Tech Stack:** Python 3.13 (`SAO/.venv`), FastAPI/Starlette, numpy, soundfile, librosa, torch (resident model only), `harmonic.same_chroma` (mir-same-chroma checkout), Bungee via subprocess in `mir/.venv`, pytest 9.

**Spec:** `docs/superpowers/specs/2026-09-15-latent-forge-design.md` (§2, §3, §6).

## Global Constraints

- Work ONLY in the worktree `/home/kim/Projects/sa3-studio-review`, branch `latent-forge`. Never check out, reset or commit in the shared tree `/home/kim/Projects/SAO` (its local `sa3-style-adapter` branch holds other instances' uncommitted work).
- Commit with `Misc/agent_commit.sh WINTERMUTE -m "<msg>"`; `git add` explicit paths only, never `-A`/`-u`. End every commit message with the two attribution lines from the session's system reminder.
- Interpreter: `PY=/home/kim/Projects/SAO/.venv/bin/python`. Run tests from the worktree root: `cd /home/kim/Projects/sa3-studio-review && $PY -m pytest <file> -q`.
- Bungee interpreter: `/home/kim/Projects/mir/.venv/bin/python` (`bungee_python 0.2.1`).
- Routes are under `/forge/`. Errors: `{"ok": false, "error": "<message>"}` with 400/404/409, or 500 plus `"traceback"`.
- Forge pass length cap: **184.0 s**, error text exactly `forge passes are capped at 184 s locally (T<2048)`.
- Job queue: at most **4** queued-or-running jobs; the 5th submit returns 409 `job queue full`.
- Storage root: `OUT_DIR/_forge/` with `uploads/`, `sessions/`, `presets/<level>/`, `cache/<kind>/`.
- Preset levels exactly: `prompt, render, latch, film, lora, bungee, master`. Names match `^[A-Za-z0-9._-]{1,80}$` and are not `.`/`..`.
- Upload extensions exactly: `wav flac mp3 m4a ogg aif aiff`; size ≤ 512 MiB.
- `SR = 44100`, `HOP = 4096`, `FPS = 44100/4096 = 10.7666015625`.
- No second model process, ever. GPU work takes `srv.GPU_LOCK`.
- Public-surface rules: no passwords, tunnel URLs or hostnames in commits, WORKLOG or dialogue.

## File Structure

| File | Responsibility |
|---|---|
| `eval/explorer_render_server.py` (modify) | self-locating import path; log/progress hooks; `/status.progress`; `/info.objective`; `_run` maps `ForgeError`; router bind |
| `eval/forge/__init__.py` | package marker |
| `eval/forge/contract.py` | constants, `ForgeError`, cap/name/level validation |
| `eval/forge/paths.py` | `ForgePaths` storage layout |
| `eval/forge/envelope.py` | `validate_envelope`, `sample_envelope` (spec §5.2) |
| `eval/forge/write_vectors.py` | writes shared TS/Python test vectors |
| `eval/forge/logseq.py` | sequenced copy of the log ring |
| `eval/forge/progress.py` | job progress state for `/status` and `/forge/jobs` |
| `eval/forge/jobs.py` | `JobQueue` (FIFO worker thread) |
| `eval/forge/store.py` | `JsonStore` for sessions and presets |
| `eval/forge/uploads.py` | `UploadWriter`, `probe_audio` |
| `eval/forge/hashing.py` | memoised file sha256 |
| `eval/forge/refs.py` | `RefContext`, `resolve_audio` |
| `eval/forge/library.py` | `list_files` for the FILES module |
| `eval/forge/analysis.py` | `analyze_audio` (tempo, beats, downbeats) |
| `eval/forge/stretch.py` | Bungee subprocess stretch + cache key |
| `eval/forge/chroma.py` | `chroma_payload` (SAME 3×128 + 12-class fold) |
| `eval/forge/stats.py` | xcorr, feature timeseries, dataset scalar index |
| `eval/forge/backbone.py` | backbone ids, objectives, HF-cache presence |
| `eval/forge/services.py` | GPU-touching helpers bound to the server (crop decode, encode cache) |
| `eval/forge/record_fixtures.py` | records redacted golden responses from the live server |
| `eval/forge/dev_server.sh` | start/stop/status of the worktree server on :8056 |
| `eval/forge_api.py` | all `/forge/*` routes |
| `eval/tests/forge_testutil.py` | sys.path helper for tests |
| `eval/tests/test_forge_*.py` | one test file per module/route group |
| `docs/latent-forge/contract/vectors/envelope.json` | shared vectors |
| `docs/latent-forge/contract/fixtures/*.json` | recorded responses |

---

### Task 1: Self-locating server, forge package, dev server script

**Files:**
- Modify: `eval/explorer_render_server.py:50`
- Create: `eval/forge/__init__.py`, `eval/forge/dev_server.sh`, `eval/tests/forge_testutil.py`, `eval/tests/test_forge_boot.py`

**Interfaces:**
- Produces: `forge_testutil.EVAL` (Path of the worktree `eval/`), importing it puts `EVAL` first on `sys.path`. `eval/forge/dev_server.sh start|stop|status`.

- [ ] **Step 1: Write the failing test**

`eval/tests/forge_testutil.py`:
```python
"""Put THIS worktree's eval/ first on sys.path (tests must never import the shared tree)."""
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parents[1]
if str(EVAL) in sys.path:
    sys.path.remove(str(EVAL))
sys.path.insert(0, str(EVAL))
```

`eval/tests/test_forge_boot.py`:
```python
from pathlib import Path

import forge_testutil  # noqa: F401
from forge_testutil import EVAL


def test_server_imports_its_own_eval_dir():
    import explorer_render_server as srv
    assert Path(srv.__file__).resolve().parent == EVAL
    # the helper modules must come from the same checkout as the server
    assert Path(srv.cmt.__file__).resolve().parent == EVAL
    assert Path(srv.presets.__file__).resolve().parent == EVAL


def test_forge_package_importable():
    import forge
    assert Path(forge.__file__).resolve().parent == EVAL / "forge"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/kim/Projects/sa3-studio-review && /home/kim/Projects/SAO/.venv/bin/python -m pytest eval/tests/test_forge_boot.py -q`
Expected: FAIL — `cmt.__file__` resolves to `/home/kim/Projects/SAO/eval` and `No module named 'forge'`.

- [ ] **Step 3: Implement**

In `eval/explorer_render_server.py` replace line 50:
```python
sys.path.insert(0, "/home/kim/Projects/SAO/eval")
```
with:
```python
# Self-locating: a worktree copy of this server must import ITS OWN eval/ helpers,
# not the shared checkout's (Latent Forge dev runs from a worktree).
sys.path.insert(0, str(Path(__file__).resolve().parent))
```

Create `eval/forge/__init__.py`:
```python
"""Latent Forge server package: pure logic behind the /forge/* routes (spec 2026-09-15)."""
```

Create `eval/forge/dev_server.sh` (then `chmod +x`):
```bash
#!/usr/bin/env bash
# Start / stop / inspect the Latent Forge dev render server (this worktree) on :8056.
# The server is the ONLY model process; it announces itself on the GPU lock as KIND=server.
set -euo pipefail
WT="$(cd "$(dirname "$0")/../.." && pwd)"
SAO=/home/kim/Projects/SAO
PY=$SAO/.venv/bin/python
FORK=/home/kim/Projects/sa3-fork-forge
PORT=8056
LOG="${FORGE_SERVER_LOG:-$HOME/.cache/latent-forge/server.log}"
mkdir -p "$(dirname "$LOG")"

pids() { pgrep -f "eval/explorer_render_server.py --port $PORT" || true; }

case "${1:-status}" in
  status)
    p="$(pids)"
    echo "pids: ${p:-none}"
    for x in $p; do echo "  $x cwd=$(readlink /proc/"$x"/cwd)"; done
    if curl -sf "localhost:$PORT/status" >/dev/null; then echo "http: up"; else echo "http: down"; fi
    ;;
  stop)
    for x in $(pids); do kill "$x"; done
    for _ in $(seq 1 60); do [ -z "$(pids)" ] && break; sleep 0.5; done
    if [ -n "$(pids)" ]; then echo "still running: $(pids)"; exit 1; fi
    (cd "$SAO" && Misc/gpu_guard.sh release WINTERMUTE) || true
    echo "stopped"
    ;;
  start)
    if [ -n "$(pids)" ]; then echo "already running: $(pids) — run '$0 stop' first"; exit 1; fi
    if ! (cd "$SAO" && python3 Misc/filelock.py check "$SAO/.gpu.lock") | grep -q "unlocked"; then
      echo "GPU lock is held — run: (cd $SAO && Misc/gpu_guard.sh who WINTERMUTE)"; exit 1
    fi
    envs=(FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE PYTORCH_TUNABLEOP_ENABLED=0 MIOPEN_FIND_MODE=2)
    if [ -d "$FORK" ]; then envs+=("PYTHONPATH=$FORK"); fi
    cd "$WT"
    setsid nohup env "${envs[@]}" "$PY" eval/explorer_render_server.py --port "$PORT" </dev/null >"$LOG" 2>&1 &
    spid=$!
    disown
    for _ in $(seq 1 240); do curl -sf "localhost:$PORT/status" >/dev/null && break; sleep 1; done
    if ! curl -sf "localhost:$PORT/status" >/dev/null; then echo "did not come up — last log lines:"; tail -20 "$LOG"; exit 1; fi
    (cd "$SAO" && KIND=server NOTE="latent-forge dev server :$PORT from $WT — ask to yield" Misc/gpu_guard.sh acquire WINTERMUTE "$spid")
    echo "up pid=$spid log=$LOG"
    ;;
  *) echo "usage: $0 start|stop|status"; exit 2 ;;
esac
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$PY -m pytest eval/tests/test_forge_boot.py -q`
Expected: 2 passed.

- [ ] **Step 5: Boot check of the worktree server (GPU; skip if the lock is held and note it)**

Run:
```bash
cd /home/kim/Projects/SAO && Misc/gpu_guard.sh who WINTERMUTE
cd /home/kim/Projects/sa3-studio-review && eval/forge/dev_server.sh status
```
If the shared-tree server is running and the lock is free, stop it with `eval/forge/dev_server.sh stop` (the pgrep pattern matches both copies). If another instance holds the lock, DM it (`python3 Misc/agent_dialogue.py dm-say --handle WINTERMUTE --to <HOLDER> --text "..."`) and defer Steps 5's live part to Task 15.
Then:
```bash
eval/forge/dev_server.sh start
curl -s localhost:8056/info | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['model'], len(d['latch_heads']))"
curl -s "localhost:8056/models?loadable=1" | python3 -c "import json,sys; print(json.load(sys.stdin)['count'])"
```
Expected: `medium-base 17` (16 if the eval drive is unmounted) and a model count > 1000. If boot fails with `ModuleNotFoundError`/`FileNotFoundError` for a file that exists in the shared tree but not in the worktree, STOP and report BLOCKED with the missing path — do not copy untracked files across.

- [ ] **Step 6: Commit**

```bash
git add eval/explorer_render_server.py eval/forge/__init__.py eval/forge/dev_server.sh eval/tests/forge_testutil.py eval/tests/test_forge_boot.py
Misc/agent_commit.sh WINTERMUTE -m "forge: self-locating server imports, forge package, dev server script"
```

---

### Task 2: Contract constants and storage paths

**Files:**
- Create: `eval/forge/contract.py`, `eval/forge/paths.py`, `eval/tests/test_forge_contract.py`

**Interfaces:**
- Produces: `contract.SR, HOP, FPS, CAP_SEC, AUDIO_EXTS, PRESET_LEVELS, MAX_PENDING_JOBS, PRESET_MAX_BYTES, SESSION_MAX_BYTES, UPLOAD_MAX_BYTES, SPLICE_XFADE_FRAMES`; `ForgeError(status:int, message:str)`; `check_cap(duration_sec, what="request") -> float`; `check_name(name) -> str`; `check_level(level) -> str`; `latent_frames(duration_sec) -> int`. `paths.ForgePaths(out_dir)` with `.root .uploads .sessions .presets .cache`, `.ensure() -> ForgePaths`, `.cache_dir(kind) -> Path`, `.preset_dir(level) -> Path`.

- [ ] **Step 1: Write the failing test**

```python
import pytest

import forge_testutil  # noqa: F401
from forge import contract
from forge.contract import ForgeError
from forge.paths import ForgePaths


def test_constants():
    assert contract.FPS == 44100 / 4096
    assert contract.CAP_SEC == 184.0
    assert contract.PRESET_LEVELS == ("prompt", "render", "latch", "film", "lora", "bungee", "master")
    assert contract.AUDIO_EXTS == {".wav", ".flac", ".mp3", ".m4a", ".ogg", ".aif", ".aiff"}
    assert contract.MAX_PENDING_JOBS == 4
    assert contract.SPLICE_XFADE_FRAMES == 2


def test_cap():
    assert contract.check_cap(184.0) == 184.0
    with pytest.raises(ForgeError) as e:
        contract.check_cap(184.01)
    assert e.value.status == 400
    assert e.value.message == "forge passes are capped at 184 s locally (T<2048)"
    with pytest.raises(ForgeError):
        contract.check_cap(0)
    with pytest.raises(ForgeError):
        contract.check_cap(float("nan"))


@pytest.mark.parametrize("name", ["a", "Club_mix-v1.2", "x" * 80])
def test_names_ok(name):
    assert contract.check_name(name) == name


@pytest.mark.parametrize("name", ["", ".", "..", "a/b", "x" * 81, "sp ace", None, 3])
def test_names_bad(name):
    with pytest.raises(ForgeError) as e:
        contract.check_name(name)
    assert e.value.status == 400


def test_levels():
    assert contract.check_level("render") == "render"
    with pytest.raises(ForgeError):
        contract.check_level("sampling")


def test_latent_frames():
    assert contract.latent_frames(184.0) == 1982
    assert contract.latent_frames(1.0) == 11


def test_paths(tmp_path):
    p = ForgePaths(tmp_path).ensure()
    assert p.root == tmp_path / "_forge"
    for d in (p.uploads, p.sessions, p.presets, p.cache):
        assert d.is_dir()
    assert p.cache_dir("chroma") == tmp_path / "_forge" / "cache" / "chroma"
    assert p.cache_dir("chroma").is_dir()
    assert p.preset_dir("render") == tmp_path / "_forge" / "presets" / "render"
    with pytest.raises(ForgeError):
        p.preset_dir("nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest eval/tests/test_forge_contract.py -q`
Expected: FAIL — `No module named 'forge.contract'`.

- [ ] **Step 3: Implement**

`eval/forge/contract.py`:
```python
"""Constants and validation shared by every /forge route (spec §2, §6)."""
import math
import re

SR = 44100
HOP = 4096
FPS = SR / HOP
CAP_SEC = 184.0
AUDIO_EXTS = {".wav", ".flac", ".mp3", ".m4a", ".ogg", ".aif", ".aiff"}
PRESET_LEVELS = ("prompt", "render", "latch", "film", "lora", "bungee", "master")
MAX_PENDING_JOBS = 4
PRESET_MAX_BYTES = 1 << 20
SESSION_MAX_BYTES = 16 << 20
UPLOAD_MAX_BYTES = 512 << 20
SPLICE_XFADE_FRAMES = 2

_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


class ForgeError(Exception):
    """A client-facing error with an HTTP status. Routes turn it into {"ok": false, "error"}."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = int(status)
        self.message = str(message)


def check_cap(duration_sec, what="request") -> float:
    try:
        d = float(duration_sec)
    except (TypeError, ValueError):
        raise ForgeError(400, f"{what}: duration must be a number")
    if not math.isfinite(d) or d <= 0:
        raise ForgeError(400, f"{what}: duration must be a positive number")
    if d > CAP_SEC:
        raise ForgeError(400, "forge passes are capped at 184 s locally (T<2048)")
    return d


def check_name(name) -> str:
    if not isinstance(name, str) or name in (".", "..") or not _NAME_RE.match(name):
        raise ForgeError(400, f"invalid name {name!r} (allowed: A-Z a-z 0-9 . _ -, 1-80 chars)")
    return name


def check_level(level) -> str:
    if level not in PRESET_LEVELS:
        raise ForgeError(400, f"unknown preset level {level!r} (have {', '.join(PRESET_LEVELS)})")
    return level


def latent_frames(duration_sec) -> int:
    return int(math.ceil(float(duration_sec) * SR / HOP))
```

`eval/forge/paths.py`:
```python
"""Storage layout under OUT_DIR/_forge (spec §6.3)."""
from pathlib import Path

from .contract import check_level


class ForgePaths:
    def __init__(self, out_dir):
        self.root = Path(out_dir) / "_forge"
        self.uploads = self.root / "uploads"
        self.sessions = self.root / "sessions"
        self.presets = self.root / "presets"
        self.cache = self.root / "cache"

    def ensure(self) -> "ForgePaths":
        for d in (self.uploads, self.sessions, self.presets, self.cache):
            d.mkdir(parents=True, exist_ok=True)
        return self

    def cache_dir(self, kind: str) -> Path:
        d = self.cache / kind
        d.mkdir(parents=True, exist_ok=True)
        return d

    def preset_dir(self, level: str) -> Path:
        d = self.presets / check_level(level)
        d.mkdir(parents=True, exist_ok=True)
        return d
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$PY -m pytest eval/tests/test_forge_contract.py -q`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add eval/forge/contract.py eval/forge/paths.py eval/tests/test_forge_contract.py
Misc/agent_commit.sh WINTERMUTE -m "forge: contract constants, validation and storage layout"
```

---

### Task 3: Envelope sampling and shared vectors

**Files:**
- Create: `eval/forge/envelope.py`, `eval/forge/write_vectors.py`, `eval/tests/test_forge_envelope.py`, `docs/latent-forge/contract/vectors/envelope.json` (generated)

**Interfaces:**
- Produces: `envelope.validate_envelope(env) -> dict` (normalised `{"points": [4 floats], "curves": [3 floats]}`), `envelope.sample_envelope(env, n) -> np.ndarray float32 (n,)`. `write_vectors.envelope_vectors() -> list[dict]`, `write_vectors.VECTOR_DIR`. Consumed by M8 (lanes, passes) and the client (M5) via `envelope.json`.

- [ ] **Step 1: Write the failing test**

```python
import json

import numpy as np
import pytest

import forge_testutil  # noqa: F401
from forge.contract import ForgeError
from forge.envelope import sample_envelope, validate_envelope


def test_flat():
    v = sample_envelope({"points": [0.4] * 4, "curves": [0, 0, 0]}, 5)
    assert v.dtype == np.float32
    np.testing.assert_allclose(v, [0.4] * 5, atol=1e-6)


def test_linear_points_with_zero_curves_are_linear():
    v = sample_envelope({"points": [0, 1 / 3, 2 / 3, 1], "curves": [0, 0, 0]}, 7)
    np.testing.assert_allclose(v, np.arange(7) / 6, atol=1e-6)


def test_bent_segment_hand_computed():
    v = sample_envelope({"points": [0, 0, 0, 0], "curves": [0.5, 0, 0]}, 7)
    # k=1: x=1/6, segment 0, s=0.5 -> y = .25*90 + .5*(90-30) + .25*90 = 75 -> v = 15/80
    assert v[1] == pytest.approx(0.1875, abs=1e-6)
    assert v[0] == pytest.approx(0.0, abs=1e-6)
    assert v[2] == pytest.approx(0.0, abs=1e-6)


def test_endpoints_and_single():
    env = {"points": [0.2, 0.9, 0.1, 0.6], "curves": [-1, 1, 0.25]}
    v = sample_envelope(env, 13)
    assert v[0] == pytest.approx(0.2, abs=1e-6)
    assert v[-1] == pytest.approx(0.6, abs=1e-6)
    assert sample_envelope(env, 1)[0] == pytest.approx(0.2, abs=1e-6)
    assert sample_envelope(env, 0).shape == (0,)
    assert v.min() >= 0.0 and v.max() <= 1.0


@pytest.mark.parametrize("env", [
    None, {"points": [0, 0, 0], "curves": [0, 0, 0]}, {"points": [0, 0, 0, 1.2], "curves": [0, 0, 0]},
    {"points": [0, 0, 0, 0], "curves": [0, 2, 0]}, {"points": [0, 0, 0, "x"], "curves": [0, 0, 0]},
])
def test_validate_rejects(env):
    with pytest.raises(ForgeError):
        validate_envelope(env)


def test_vectors_file_matches_code():
    from forge.write_vectors import VECTOR_DIR, envelope_vectors
    path = VECTOR_DIR / "envelope.json"
    assert path.exists(), "run: $PY eval/forge/write_vectors.py"
    assert json.loads(path.read_text()) == envelope_vectors()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest eval/tests/test_forge_envelope.py -q`
Expected: FAIL — `No module named 'forge.envelope'`.

- [ ] **Step 3: Implement**

`eval/forge/envelope.py`:
```python
"""Envelope geometry shared with the client (spec §5.2).

SVG viewBox 400x100: node x = 0, 133.33, 266.67, 400; y(v) = 90 - 80 v. Segment i is a
quadratic Bezier with control point at the chord midpoint lifted by 60*c_i, so x(s) is
linear in s and y can be evaluated directly at s = 3x - i.
"""
import math

import numpy as np

from .contract import ForgeError


def _num(v, lo, hi, what):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
        raise ForgeError(400, f"{what}={v!r} must be a number in {lo}..{hi}")
    return float(v)


def validate_envelope(env) -> dict:
    if not isinstance(env, dict):
        raise ForgeError(400, "envelope must be an object with points[4] and curves[3]")
    pts, cs = env.get("points"), env.get("curves")
    if not isinstance(pts, list) or len(pts) != 4 or not isinstance(cs, list) or len(cs) != 3:
        raise ForgeError(400, "envelope must have exactly 4 points and 3 curves")
    return {"points": [_num(p, 0.0, 1.0, "envelope.points") for p in pts],
            "curves": [_num(c, -1.0, 1.0, "envelope.curves") for c in cs]}


def sample_envelope(env, n: int) -> np.ndarray:
    env = validate_envelope(env)
    n = int(n)
    if n <= 0:
        return np.zeros(0, dtype=np.float32)
    x = np.zeros(1) if n == 1 else np.arange(n, dtype=np.float64) / (n - 1)
    i = np.minimum(2, np.floor(3.0 * x).astype(np.int64))
    s = 3.0 * x - i
    ys = 90.0 - 80.0 * np.asarray(env["points"], dtype=np.float64)
    ya, yb = ys[i], ys[i + 1]
    yc = (ya + yb) / 2.0 - 60.0 * np.asarray(env["curves"], dtype=np.float64)[i]
    y = (1 - s) ** 2 * ya + 2 * s * (1 - s) * yc + s ** 2 * yb
    return np.clip((90.0 - y) / 80.0, 0.0, 1.0).astype(np.float32)
```

`eval/forge/write_vectors.py`:
```python
"""Write shared test vectors so the TypeScript client and this server agree by construction.

Run: /home/kim/Projects/SAO/.venv/bin/python eval/forge/write_vectors.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from forge.envelope import sample_envelope  # noqa: E402

VECTOR_DIR = Path(__file__).resolve().parents[2] / "docs" / "latent-forge" / "contract" / "vectors"

ENVELOPE_CASES = [
    {"name": "flat", "env": {"points": [0.4, 0.4, 0.4, 0.4], "curves": [0, 0, 0]}, "n": 5},
    {"name": "linear", "env": {"points": [0, 0.333333, 0.666667, 1], "curves": [0, 0, 0]}, "n": 7},
    {"name": "bent", "env": {"points": [0, 0, 0, 0], "curves": [0.5, 0, 0]}, "n": 7},
    {"name": "single", "env": {"points": [0.2, 0.9, 0.1, 0.6], "curves": [-1, 1, 0.25]}, "n": 1},
    {"name": "mixed", "env": {"points": [0.2, 0.9, 0.1, 0.6], "curves": [-1, 1, 0.25]}, "n": 13},
]


def envelope_vectors():
    return [{**c, "values": [round(float(v), 6) for v in sample_envelope(c["env"], c["n"])]}
            for c in ENVELOPE_CASES]


def main():
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    (VECTOR_DIR / "envelope.json").write_text(json.dumps(envelope_vectors(), indent=2) + "\n")
    print(f"wrote {VECTOR_DIR / 'envelope.json'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Generate vectors and run tests**

Run:
```bash
$PY eval/forge/write_vectors.py
$PY -m pytest eval/tests/test_forge_envelope.py -q
```
Expected: `wrote .../envelope.json`, then all passed.

- [ ] **Step 5: Commit**

```bash
git add eval/forge/envelope.py eval/forge/write_vectors.py eval/tests/test_forge_envelope.py docs/latent-forge/contract/vectors/envelope.json
Misc/agent_commit.sh WINTERMUTE -m "forge: envelope sampling + shared test vectors"
```

---

### Task 4: Sequenced log and progress state

**Files:**
- Create: `eval/forge/logseq.py`, `eval/forge/progress.py`, `eval/tests/test_forge_progress.py`

**Interfaces:**
- Produces: `logseq.append(text)`, `logseq.since(seq) -> (last_seq:int, lines:list[{"seq","text"}])`, `logseq.reset()`. `progress.begin(job_id, op, steps_total, stage_labels=())`, `progress.stage(index:int, label:str)`, `progress.on_step(i:int, steps:int)`, `progress.end()`, `progress.snapshot() -> dict|None` with exactly the §6.1 `Progress` keys.

- [ ] **Step 1: Write the failing test**

```python
import forge_testutil  # noqa: F401
from forge import logseq, progress


def test_logseq_since():
    logseq.reset()
    logseq.append("a")
    logseq.append("b")
    last, lines = logseq.since(0)
    assert last == 2
    assert lines == [{"seq": 1, "text": "a"}, {"seq": 2, "text": "b"}]
    assert logseq.since(1)[1] == [{"seq": 2, "text": "b"}]
    assert logseq.since(2) == (2, [])


def test_logseq_ring_is_bounded():
    logseq.reset()
    for i in range(450):
        logseq.append(str(i))
    last, lines = logseq.since(0)
    assert last == 450 and len(lines) == 400 and lines[0]["seq"] == 51


def test_progress_lifecycle():
    progress.end()
    assert progress.snapshot() is None
    progress.on_step(1, 8)                       # no job: ignored
    assert progress.snapshot() is None
    progress.begin("j1", "commit", 16, ["S1", "S2"])
    s = progress.snapshot()
    assert s == {"job_id": "j1", "op": "commit", "stage": "", "stage_index": 0, "stage_count": 2,
                 "step": 0, "steps": 0, "steps_left_total": 16, "steps_total": 16}
    progress.stage(1, "S1")
    progress.on_step(1, 8)
    progress.on_step(2, 8)
    s = progress.snapshot()
    assert (s["stage"], s["stage_index"], s["step"], s["steps"], s["steps_left_total"]) == ("S1", 1, 2, 8, 14)
    progress.stage(2, "S2")
    assert progress.snapshot()["step"] == 0
    for i in range(1, 30):
        progress.on_step(i, 8)
    assert progress.snapshot()["steps_left_total"] == 0      # never negative
    progress.end()
    assert progress.snapshot() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest eval/tests/test_forge_progress.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`eval/forge/logseq.py`:
```python
"""A sequence-numbered copy of the server log ring, so the TERMINAL tab can fetch only new lines."""
import threading
from collections import deque

_lock = threading.Lock()
_ring = deque(maxlen=400)
_seq = 0


def append(text) -> None:
    global _seq
    with _lock:
        _seq += 1
        _ring.append((_seq, str(text)))


def since(seq):
    seq = int(seq)
    with _lock:
        return _seq, [{"seq": s, "text": t} for s, t in _ring if s > seq]


def reset() -> None:
    global _seq
    with _lock:
        _ring.clear()
        _seq = 0
```

`eval/forge/progress.py`:
```python
"""Progress of the running forge job (spec §6.1 Progress). One job runs at a time."""
import threading

_lock = threading.Lock()
_state = None


def begin(job_id, op, steps_total, stage_labels=()) -> None:
    global _state
    with _lock:
        _state = {"job_id": str(job_id), "op": str(op), "stage": "", "stage_index": 0,
                  "stage_count": len(stage_labels), "step": 0, "steps": 0,
                  "steps_left_total": max(0, int(steps_total)), "steps_total": max(0, int(steps_total)),
                  "_done": 0}


def stage(index, label) -> None:
    with _lock:
        if _state is not None:
            _state.update(stage=str(label), stage_index=int(index), step=0, steps=0)


def on_step(i, steps) -> None:
    with _lock:
        if _state is None:
            return
        _state["_done"] += 1
        _state["step"] = int(i)
        _state["steps"] = int(steps)
        _state["steps_left_total"] = max(0, _state["steps_total"] - _state["_done"])


def end() -> None:
    global _state
    with _lock:
        _state = None


def snapshot():
    with _lock:
        if _state is None:
            return None
        return {k: v for k, v in _state.items() if not k.startswith("_")}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$PY -m pytest eval/tests/test_forge_progress.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add eval/forge/logseq.py eval/forge/progress.py eval/tests/test_forge_progress.py
Misc/agent_commit.sh WINTERMUTE -m "forge: sequenced log ring and job progress state"
```

---

### Task 5: Job queue

**Files:**
- Create: `eval/forge/jobs.py`, `eval/tests/test_forge_jobs.py`

**Interfaces:**
- Produces: `jobs.QueueFull`, `jobs.UnknownOp`, `jobs.CannotCancel`; `JobQueue(runners: dict[str, Callable[[str, dict], dict]], max_pending=4, history=200, log=None)`; `.submit(op, payload) -> (job_id, ahead:int)`; `.get(job_id) -> dict|None` (`job_id, op, payload, state, position, result, error, created, started, finished`); `.cancel(job_id) -> dict`; `.list(limit=50) -> list[dict]` (no payload/result); `.stop()`. Job ids `forge-YYYYmmdd-HHMMSS-<n>`.

- [ ] **Step 1: Write the failing test**

```python
import threading
import time

import pytest

import forge_testutil  # noqa: F401
from forge.jobs import CannotCancel, JobQueue, QueueFull, UnknownOp


def wait_state(q, jid, states, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        rec = q.get(jid)
        if rec and rec["state"] in states:
            return rec
        time.sleep(0.01)
    raise AssertionError(f"{jid} never reached {states}: {q.get(jid)}")


def test_runs_and_returns_result():
    q = JobQueue({"echo": lambda jid, p: {"job_id": jid, "x": p["x"]}})
    jid, ahead = q.submit("echo", {"x": 3})
    assert jid.startswith("forge-") and ahead == 0
    rec = wait_state(q, jid, {"done"})
    assert rec["result"] == {"job_id": jid, "x": 3}
    assert rec["error"] is None and rec["started"] and rec["finished"] and rec["position"] is None
    assert rec["payload"] == {"x": 3}
    q.stop()


def test_error_state():
    def boom(jid, p):
        raise ValueError("nope")
    logged = []
    q = JobQueue({"boom": boom}, log=logged.append)
    jid, _ = q.submit("boom", {})
    rec = wait_state(q, jid, {"error"})
    assert rec["error"] == "nope" and rec["result"] is None
    assert any("nope" in line for line in logged)
    q.stop()


def test_unknown_op():
    q = JobQueue({})
    with pytest.raises(UnknownOp):
        q.submit("x", {})
    q.stop()


def test_queue_full_positions_and_cancel():
    gate = threading.Event()
    q = JobQueue({"slow": lambda jid, p: (gate.wait(5), {"ok": True})[1]}, max_pending=4)
    first, _ = q.submit("slow", {})
    wait_state(q, first, {"running"})
    queued = [q.submit("slow", {"n": i}) for i in range(3)]
    assert [ahead for _, ahead in queued] == [1, 2, 3]
    assert q.get(queued[2][0])["position"] == 3
    with pytest.raises(QueueFull):
        q.submit("slow", {})
    with pytest.raises(CannotCancel):
        q.cancel(first)
    rec = q.cancel(queued[0][0])
    assert rec["state"] == "cancelled"
    assert q.get(queued[2][0])["position"] == 2
    gate.set()
    wait_state(q, queued[2][0], {"done"})
    assert q.get(queued[0][0])["state"] == "cancelled"
    listed = q.list(10)
    assert listed[0]["job_id"] == queued[2][0]            # newest first
    assert "payload" not in listed[0] and "result" not in listed[0]
    q.stop()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest eval/tests/test_forge_jobs.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`eval/forge/jobs.py`:
```python
"""FIFO job queue with one worker thread (spec §6.2). Runners take the GPU lock themselves."""
import itertools
import threading
import time
import traceback
from collections import deque


class QueueFull(Exception):
    pass


class UnknownOp(Exception):
    pass


class CannotCancel(Exception):
    pass


_TERMINAL = ("done", "error", "cancelled")


class JobQueue:
    def __init__(self, runners, max_pending=4, history=200, log=None):
        self._runners = dict(runners)
        self._max = int(max_pending)
        self._history = int(history)
        self._log = log or (lambda msg: None)
        self._jobs = {}
        self._order = []
        self._queue = deque()
        self._running = None
        self._cv = threading.Condition()
        self._counter = itertools.count(1)
        self._stop = False
        self._thread = threading.Thread(target=self._loop, name="forge-jobs", daemon=True)
        self._thread.start()

    def set_runner(self, op, fn):
        with self._cv:
            self._runners[op] = fn

    def ops(self):
        with self._cv:
            return sorted(self._runners)

    def submit(self, op, payload):
        with self._cv:
            if op not in self._runners:
                raise UnknownOp(op)
            ahead = len(self._queue) + (1 if self._running else 0)
            if ahead >= self._max:
                raise QueueFull()
            jid = f"forge-{time.strftime('%Y%m%d-%H%M%S')}-{next(self._counter)}"
            self._jobs[jid] = {"job_id": jid, "op": op, "payload": payload, "state": "queued",
                               "result": None, "error": None, "created": time.time(),
                               "started": None, "finished": None}
            self._order.append(jid)
            self._queue.append(jid)
            self._trim()
            self._cv.notify_all()
            return jid, ahead

    def _position(self, jid):
        if jid in self._queue:
            return list(self._queue).index(jid) + (1 if self._running else 0)
        return None

    def get(self, jid):
        with self._cv:
            rec = self._jobs.get(jid)
            if rec is None:
                return None
            return {**rec, "position": self._position(jid)}

    def cancel(self, jid):
        with self._cv:
            rec = self._jobs.get(jid)
            if rec is None:
                raise KeyError(jid)
            if rec["state"] == "running":
                raise CannotCancel(jid)
            if rec["state"] == "queued":
                self._queue.remove(jid)
                rec.update(state="cancelled", finished=time.time())
            return {**rec, "position": None}

    def list(self, limit=50):
        with self._cv:
            ids = list(reversed(self._order))[: int(limit)]
            return [{k: self._jobs[j][k] for k in ("job_id", "op", "state", "created", "started", "finished")}
                    for j in ids]

    def stop(self):
        with self._cv:
            self._stop = True
            self._cv.notify_all()
        self._thread.join(timeout=5)

    def _trim(self):
        done = [j for j in self._order if self._jobs[j]["state"] in _TERMINAL]
        for j in done[: max(0, len(self._order) - self._history)]:
            self._order.remove(j)
            del self._jobs[j]

    def _loop(self):
        while True:
            with self._cv:
                while not self._queue and not self._stop:
                    self._cv.wait()
                if self._stop:
                    return
                jid = self._queue.popleft()
                rec = self._jobs[jid]
                rec.update(state="running", started=time.time())
                self._running = jid
                fn = self._runners[rec["op"]]
                payload = rec["payload"]
            try:
                result = fn(jid, payload)
                with self._cv:
                    rec.update(state="done", result=result, finished=time.time())
            except Exception as e:  # noqa: BLE001 — a job failure must never kill the worker
                self._log(f"[forge] job {jid} ({rec['op']}) failed: {e}\n{traceback.format_exc()}")
                with self._cv:
                    rec.update(state="error", error=str(e), finished=time.time())
            finally:
                with self._cv:
                    self._running = None
                    self._cv.notify_all()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$PY -m pytest eval/tests/test_forge_jobs.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add eval/forge/jobs.py eval/tests/test_forge_jobs.py
Misc/agent_commit.sh WINTERMUTE -m "forge: FIFO job queue with positions, cancel and bounded history"
```

---

### Task 6: JSON store, uploads, file hashing

**Files:**
- Create: `eval/forge/store.py`, `eval/forge/uploads.py`, `eval/forge/hashing.py`, `eval/tests/test_forge_store.py`

**Interfaces:**
- Produces: `store.JsonStore(root, max_bytes)` with `.names() -> list[str]`, `.listing() -> list[{"name","updated"}]`, `.get(name) -> dict`, `.put(name, obj) -> None`, `.delete(name) -> None`. `uploads.UploadWriter(filename, uploads_dir, max_bytes)` with `.feed(bytes)`, `.finish() -> (path, sha256, nbytes)`, `.abort()`; `uploads.probe_audio(path) -> {"duration_sec","sample_rate","channels"}`. `hashing.file_sha256(path) -> str` (memoised on path+size+mtime).

- [ ] **Step 1: Write the failing test**

```python
import hashlib

import numpy as np
import pytest
import soundfile as sf

import forge_testutil  # noqa: F401
from forge.contract import ForgeError
from forge.hashing import file_sha256
from forge.store import JsonStore
from forge.uploads import UploadWriter, probe_audio


def test_store_crud(tmp_path):
    s = JsonStore(tmp_path / "presets" / "render", max_bytes=200)
    assert s.names() == []
    s.put("warm", {"prompt": "x"})
    assert s.names() == ["warm"] and s.get("warm") == {"prompt": "x"}
    assert s.listing()[0]["name"] == "warm" and s.listing()[0]["updated"] > 0
    with pytest.raises(ForgeError) as e:
        s.put("big", {"p": "x" * 500})
    assert e.value.status == 400
    with pytest.raises(ForgeError) as e:
        s.put("list", [1, 2])
    assert e.value.status == 400
    with pytest.raises(ForgeError):
        s.put("../evil", {})
    s.delete("warm")
    with pytest.raises(ForgeError) as e:
        s.get("warm")
    assert e.value.status == 404
    with pytest.raises(ForgeError) as e:
        s.delete("warm")
    assert e.value.status == 404


def test_upload_writer_hash_and_idempotence(tmp_path):
    data = b"RIFF" + bytes(range(256)) * 10
    w = UploadWriter("take.WAV", tmp_path, max_bytes=10_000)
    for i in range(0, len(data), 100):
        w.feed(data[i:i + 100])
    path, sha, n = w.finish()
    assert sha == hashlib.sha256(data).hexdigest() and n == len(data)
    assert path == tmp_path / f"{sha}.wav" and path.read_bytes() == data
    w2 = UploadWriter("again.wav", tmp_path, max_bytes=10_000)
    w2.feed(data)
    assert w2.finish()[0] == path
    assert sorted(p.name for p in tmp_path.iterdir()) == [f"{sha}.wav"]      # no .part leftovers


def test_upload_writer_rejects(tmp_path):
    with pytest.raises(ForgeError):
        UploadWriter("notes.txt", tmp_path, max_bytes=10)
    w = UploadWriter("a.wav", tmp_path, max_bytes=10)
    with pytest.raises(ForgeError):
        w.feed(b"x" * 11)
    w.abort()
    w = UploadWriter("a.wav", tmp_path, max_bytes=10)
    with pytest.raises(ForgeError):
        w.finish()                                                            # empty
    assert list(tmp_path.iterdir()) == []


def test_probe_audio(tmp_path):
    p = tmp_path / "t.wav"
    sf.write(p, np.zeros((22050, 2), dtype=np.float32), 44100)
    info = probe_audio(p)
    assert info == {"duration_sec": 0.5, "sample_rate": 44100, "channels": 2}
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not audio")
    with pytest.raises(ForgeError):
        probe_audio(bad)


def test_file_sha256(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"abc")
    assert file_sha256(p) == hashlib.sha256(b"abc").hexdigest()
    p.write_bytes(b"abcd")
    assert file_sha256(p) == hashlib.sha256(b"abcd").hexdigest()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest eval/tests/test_forge_store.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`eval/forge/store.py`:
```python
"""Named JSON documents on disk: sessions and presets (spec §6.3)."""
import json
import os
import tempfile
from pathlib import Path

from .contract import ForgeError, check_name


class JsonStore:
    def __init__(self, root, max_bytes):
        self.root = Path(root)
        self.max_bytes = int(max_bytes)

    def _path(self, name) -> Path:
        return self.root / f"{check_name(name)}.json"

    def names(self):
        if not self.root.is_dir():
            return []
        return sorted(p.stem for p in self.root.glob("*.json"))

    def listing(self):
        return [{"name": n, "updated": self._path(n).stat().st_mtime} for n in self.names()]

    def get(self, name) -> dict:
        p = self._path(name)
        if not p.is_file():
            raise ForgeError(404, f"no such entry {name!r}")
        return json.loads(p.read_text())

    def put(self, name, obj) -> None:
        p = self._path(name)
        if not isinstance(obj, dict):
            raise ForgeError(400, "payload must be a JSON object")
        data = json.dumps(obj, indent=2).encode()
        if len(data) > self.max_bytes:
            raise ForgeError(400, f"payload too large ({len(data)} > {self.max_bytes} bytes)")
        self.root.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.root, suffix=".part")
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, p)

    def delete(self, name) -> None:
        p = self._path(name)
        if not p.is_file():
            raise ForgeError(404, f"no such entry {name!r}")
        p.unlink()
```

`eval/forge/uploads.py`:
```python
"""Streaming, content-addressed uploads (spec §6.3 PUT /forge/upload)."""
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from .contract import AUDIO_EXTS, ForgeError


class UploadWriter:
    def __init__(self, filename, uploads_dir, max_bytes):
        self.ext = Path(filename or "").suffix.lower()
        if self.ext not in AUDIO_EXTS:
            raise ForgeError(400, f"unsupported extension {self.ext or '(none)'} "
                                  f"(allowed: {' '.join(sorted(e[1:] for e in AUDIO_EXTS))})")
        self.dir = Path(uploads_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.max_bytes = int(max_bytes)
        self._hash = hashlib.sha256()
        self._n = 0
        fd, self._tmp = tempfile.mkstemp(dir=self.dir, suffix=".part")
        self._f = os.fdopen(fd, "wb")

    def feed(self, chunk: bytes) -> None:
        self._n += len(chunk)
        if self._n > self.max_bytes:
            self.abort()
            raise ForgeError(400, f"upload exceeds {self.max_bytes // (1 << 20)} MiB")
        self._hash.update(chunk)
        self._f.write(chunk)

    def finish(self):
        self._f.close()
        if self._n == 0:
            self.abort()
            raise ForgeError(400, "empty upload")
        sha = self._hash.hexdigest()
        dst = self.dir / f"{sha}{self.ext}"
        if dst.exists():
            os.unlink(self._tmp)
        else:
            os.replace(self._tmp, dst)
        return dst, sha, self._n

    def abort(self) -> None:
        try:
            self._f.close()
        except Exception:  # noqa: BLE001
            pass
        if os.path.exists(self._tmp):
            os.unlink(self._tmp)


def probe_audio(path) -> dict:
    cmd = ["ffprobe", "-v", "error", "-select_streams", "a:0",
           "-show_entries", "stream=sample_rate,channels:format=duration", "-of", "json", str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise ForgeError(400, f"not a readable audio file: {r.stderr.strip()[:200]}")
    d = json.loads(r.stdout or "{}")
    streams = d.get("streams") or []
    if not streams or "duration" not in (d.get("format") or {}):
        raise ForgeError(400, "no audio stream found")
    return {"duration_sec": round(float(d["format"]["duration"]), 3),
            "sample_rate": int(streams[0]["sample_rate"]), "channels": int(streams[0]["channels"])}
```

`eval/forge/hashing.py`:
```python
"""sha256 of a file, memoised on (path, size, mtime_ns) — cache keys for chroma/stretch/encode."""
import hashlib
import threading
from pathlib import Path

_lock = threading.Lock()
_memo = {}


def file_sha256(path) -> str:
    p = Path(path)
    st = p.stat()
    key = (str(p.resolve()), st.st_size, st.st_mtime_ns)
    with _lock:
        if key in _memo:
            return _memo[key]
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    digest = h.hexdigest()
    with _lock:
        _memo[key] = digest
    return digest
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$PY -m pytest eval/tests/test_forge_store.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add eval/forge/store.py eval/forge/uploads.py eval/forge/hashing.py eval/tests/test_forge_store.py
Misc/agent_commit.sh WINTERMUTE -m "forge: JSON store, streaming content-addressed uploads, file hashing"
```

---

### Task 7: Audio ref resolution and file library

**Files:**
- Create: `eval/forge/refs.py`, `eval/forge/library.py`, `eval/tests/test_forge_refs.py`

**Interfaces:**
- Consumes: `contract.AUDIO_EXTS`, `ForgeError`.
- Produces: `refs.RefContext(out_dir: Path, uploads: Path, latent_dir: Path|None, decode_crop: Callable[[str], Path], roots: dict[str, Path])`; `refs.resolve_audio(ref, ctx) -> Path`; `refs.check_crop_id(crop_id) -> str`. `library.ROOT_ORDER = ("crops", "renders", "uploads")`; `library.list_files(roots: dict[str, Path|None], root_id: str, q: str, limit: int) -> {"roots": [...], "files": [...]}`.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import pytest

import forge_testutil  # noqa: F401
from forge.contract import ForgeError
from forge.library import list_files
from forge.refs import RefContext, resolve_audio

SHA = "a" * 64


@pytest.fixture
def ctx(tmp_path):
    out, up, lat = tmp_path / "out", tmp_path / "out" / "_forge" / "uploads", tmp_path / "lat"
    for d in (out / "job1", up, lat):
        d.mkdir(parents=True)
    (out / "job1" / "out_00.wav").write_bytes(b"x")
    (up / f"{SHA}.flac").write_bytes(b"x")
    (lat / "000001.npy").write_bytes(b"x")
    decoded = tmp_path / "dec.wav"
    decoded.write_bytes(b"x")
    return RefContext(out_dir=out, uploads=up, latent_dir=lat, decode_crop=lambda cid: decoded,
                      roots={"crops": lat, "renders": out, "uploads": up})


def test_resolve_each_kind(ctx, tmp_path):
    assert resolve_audio({"kind": "upload", "sha256": SHA}, ctx) == ctx.uploads / f"{SHA}.flac"
    assert resolve_audio({"kind": "render", "job_id": "job1", "file": "out_00.wav"}, ctx) == ctx.out_dir / "job1" / "out_00.wav"
    assert resolve_audio({"kind": "crop", "crop_id": "000001"}, ctx) == tmp_path / "dec.wav"
    assert resolve_audio({"kind": "file", "root": "renders", "rel": "job1/out_00.wav"}, ctx) == ctx.out_dir / "job1" / "out_00.wav"
    p = ctx.out_dir / "job1" / "out_00.wav"
    assert resolve_audio({"kind": "path", "path": str(p)}, ctx) == p


@pytest.mark.parametrize("ref,status", [
    (None, 400), ({"kind": "nope"}, 400),
    ({"kind": "upload", "sha256": "xyz"}, 400), ({"kind": "upload", "sha256": "b" * 64}, 404),
    ({"kind": "render", "job_id": "../job1", "file": "out_00.wav"}, 400),
    ({"kind": "render", "job_id": "job1", "file": "missing.wav"}, 404),
    ({"kind": "crop", "crop_id": "../x"}, 400), ({"kind": "crop", "crop_id": "999999"}, 404),
    ({"kind": "file", "root": "etc", "rel": "x.wav"}, 400),
    ({"kind": "file", "root": "renders", "rel": "../../x.wav"}, 400),
    ({"kind": "path", "path": "relative.wav"}, 400), ({"kind": "path", "path": "/nonexistent/a.wav"}, 404),
])
def test_resolve_errors(ctx, ref, status):
    with pytest.raises(ForgeError) as e:
        resolve_audio(ref, ctx)
    assert e.value.status == status


def test_non_audio_extension(ctx):
    bad = ctx.out_dir / "job1" / "notes.txt"
    bad.write_text("x")
    with pytest.raises(ForgeError) as e:
        resolve_audio({"kind": "path", "path": str(bad)}, ctx)
    assert e.value.status == 400


def test_list_files(ctx):
    roots = {"crops": ctx.latent_dir, "renders": ctx.out_dir, "uploads": ctx.uploads}
    r = list_files(roots, "crops", "", 10)
    assert [x["id"] for x in r["roots"]] == ["crops", "renders", "uploads"]
    assert r["files"] == [{"root": "crops", "rel": "000001.npy", "kind": "latent", "size": 1,
                           "mtime": r["files"][0]["mtime"], "ref": {"kind": "crop", "crop_id": "000001"}}]
    rr = list_files(roots, "renders", "", 10)["files"]
    assert [f["rel"] for f in rr] == ["job1/out_00.wav"]            # _forge/ is never listed
    assert rr[0]["ref"] == {"kind": "render", "job_id": "job1", "file": "out_00.wav"}
    uu = list_files(roots, "uploads", "", 10)["files"]
    assert uu[0]["ref"] == {"kind": "upload", "sha256": SHA}
    assert list_files(roots, "crops", "zzz", 10)["files"] == []
    gone = {**roots, "crops": Path("/nonexistent")}
    g = list_files(gone, "crops", "", 10)
    assert g["files"] == [] and g["roots"][0]["available"] is False
    with pytest.raises(ForgeError):
        list_files(roots, "etc", "", 10)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest eval/tests/test_forge_refs.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`eval/forge/refs.py`:
```python
"""AudioRef -> server file path (spec §6.1). Every path a client names is validated here."""
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable, Optional

from .contract import AUDIO_EXTS, ForgeError

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")


@dataclass
class RefContext:
    out_dir: Path
    uploads: Path
    latent_dir: Optional[Path]
    decode_crop: Callable[[str], Path]
    roots: dict = field(default_factory=dict)


def _hint(p: Path) -> str:
    return " — is the drive mounted?" if str(p).startswith("/run/media/") else ""


def _audio_file(p: Path) -> Path:
    if p.suffix.lower() not in AUDIO_EXTS:
        raise ForgeError(400, f"not an audio file: {p.name}")
    if not p.is_file():
        raise ForgeError(404, f"no such file: {p}{_hint(p)}")
    return p


def _segment(value, what) -> str:
    if not isinstance(value, str) or value in (".", "..") or not _ID_RE.match(value):
        raise ForgeError(400, f"invalid {what}: {value!r}")
    return value


def check_crop_id(crop_id) -> str:
    return _segment(crop_id, "crop_id")


def resolve_audio(ref, ctx: RefContext) -> Path:
    if not isinstance(ref, dict):
        raise ForgeError(400, "audio ref must be an object with a 'kind'")
    kind = ref.get("kind")
    if kind == "upload":
        sha = ref.get("sha256")
        if not isinstance(sha, str) or not _SHA_RE.match(sha):
            raise ForgeError(400, "upload ref needs a 64-hex sha256")
        hits = [p for p in sorted(Path(ctx.uploads).glob(f"{sha}.*")) if p.suffix.lower() in AUDIO_EXTS]
        if not hits:
            raise ForgeError(404, f"no upload {sha}")
        return hits[0]
    if kind == "render":
        job = _segment(ref.get("job_id"), "job_id")
        name = _segment(ref.get("file"), "file")
        return _audio_file(Path(ctx.out_dir) / job / name)
    if kind == "crop":
        cid = check_crop_id(ref.get("crop_id"))
        if ctx.latent_dir is None:
            raise ForgeError(404, "latent_dir not configured on the server")
        npy = Path(ctx.latent_dir) / f"{cid}.npy"
        if not npy.is_file():
            raise ForgeError(404, f"no crop {cid}{_hint(npy)}")
        return ctx.decode_crop(cid)
    if kind == "file":
        root_id = ref.get("root")
        if root_id not in ctx.roots:
            raise ForgeError(400, f"unknown root {root_id!r}")
        rel = ref.get("rel")
        parts = PurePosixPath(rel).parts if isinstance(rel, str) else ()
        if not rel or PurePosixPath(rel).is_absolute() or ".." in parts:
            raise ForgeError(400, f"invalid rel path {rel!r}")
        base = Path(ctx.roots[root_id]).resolve()
        p = (base / rel).resolve()
        if not p.is_relative_to(base):
            raise ForgeError(400, f"invalid rel path {rel!r}")
        return _audio_file(p)
    if kind == "path":
        raw = ref.get("path")
        if not isinstance(raw, str) or not raw.startswith("/"):
            raise ForgeError(400, "path ref needs an absolute server path")
        return _audio_file(Path(raw))
    raise ForgeError(400, f"unknown audio ref kind {kind!r}")
```

`eval/forge/library.py`:
```python
"""FILES module listing (spec §6.3 GET /forge/files)."""
from pathlib import Path

from .contract import AUDIO_EXTS, ForgeError

ROOT_ORDER = ("crops", "renders", "uploads")
ROOT_LABELS = {"crops": "latent crops", "renders": "renders", "uploads": "uploads"}


def _row(root_id, rel, kind, p: Path, ref):
    st = p.stat()
    return {"root": root_id, "rel": rel, "kind": kind, "size": st.st_size, "mtime": st.st_mtime, "ref": ref}


def list_files(roots, root_id, q, limit):
    listing = [{"id": rid, "label": ROOT_LABELS[rid],
                "available": bool(roots.get(rid) and Path(roots[rid]).is_dir())} for rid in ROOT_ORDER]
    if root_id not in ROOT_ORDER:
        raise ForgeError(400, f"unknown root {root_id!r} (have {', '.join(ROOT_ORDER)})")
    base = roots.get(root_id)
    files = []
    ql = (q or "").lower()
    limit = max(1, min(int(limit), 5000))
    if base and Path(base).is_dir():
        base = Path(base)
        if root_id == "crops":
            for p in sorted(base.glob("*.npy")):
                if ql in p.stem.lower():
                    files.append(_row("crops", p.name, "latent", p, {"kind": "crop", "crop_id": p.stem}))
                if len(files) >= limit:
                    break
        elif root_id == "renders":
            wavs = [p for p in base.glob("*/out_*.wav") if not p.parent.name.startswith("_")]
            for p in sorted(wavs, key=lambda x: x.stat().st_mtime, reverse=True):
                rel = f"{p.parent.name}/{p.name}"
                if ql in rel.lower():
                    files.append(_row("renders", rel, "audio", p,
                                      {"kind": "render", "job_id": p.parent.name, "file": p.name}))
                if len(files) >= limit:
                    break
        else:
            for p in sorted(base.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if p.suffix.lower() in AUDIO_EXTS and ql in p.name.lower():
                    files.append(_row("uploads", p.name, "audio", p, {"kind": "upload", "sha256": p.stem}))
                if len(files) >= limit:
                    break
    return {"roots": listing, "files": files}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$PY -m pytest eval/tests/test_forge_refs.py -q`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add eval/forge/refs.py eval/forge/library.py eval/tests/test_forge_refs.py
Misc/agent_commit.sh WINTERMUTE -m "forge: audio ref resolution with path validation, file library listing"
```

---

### Task 8: Router, jobs routes, log route, server hooks

**Files:**
- Create: `eval/forge_api.py`, `eval/forge/services.py`, `eval/tests/test_forge_api_jobs.py`
- Modify: `eval/explorer_render_server.py` (`log`, `make_log_cb`, `/status`, `/info`, `_run`, end of module)

**Interfaces:**
- Consumes: Tasks 2–7.
- Produces: `forge_api.router`, `forge_api.bind(srv_module)`, `forge_api.register_runner(op, fn, validator=None)`, `forge_api.reset_queue()` (tests), `forge_api.paths() -> ForgePaths`, `forge_api.services() -> Services`, `forge_api.forge_route` decorator. `services.Services(srv, paths_fn)` with `.ref_context() -> RefContext`, `.decode_crop(crop_id) -> Path`, `.resolve_audio(ref) -> Path`, `.load_audio(path) -> np.ndarray (2,N)`, `.encode_cached(audio_np) -> torch.Tensor (1,256,T) cpu float32`. Routes: `POST /forge/jobs`, `GET /forge/jobs`, `GET /forge/jobs/{job_id}`, `DELETE /forge/jobs/{job_id}`, `GET /forge/log`. Server: `/status` has `progress`; `/info` has `objective`.

- [ ] **Step 1: Write the failing test**

```python
import time

import pytest

import forge_testutil  # noqa: F401

fastapi_testclient = pytest.importorskip("fastapi.testclient")


@pytest.fixture(scope="module")
def srv():
    import explorer_render_server as srv
    return srv


@pytest.fixture
def client(srv, monkeypatch, tmp_path):
    import forge_api
    monkeypatch.setattr(srv, "OUT_DIR", tmp_path)
    forge_api.reset_queue()
    return fastapi_testclient.TestClient(srv.app)


def poll(client, jid, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        body = client.get(f"/forge/jobs/{jid}").json()
        if body["state"] in ("done", "error", "cancelled"):
            return body
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_generate_job_roundtrip(srv, client, monkeypatch):
    seen = {}

    def fake_generate(req):
        seen.update(req)
        srv.make_log_cb(req["steps"])({"t": [0.5]})
        return {"status": "ok", "job_id": "j", "files": [], "latents": [], "urls": [], "seed": 1,
                "timings": {"total_sec": 0.0, "per_stage": {}}, "warnings": [], "meta": {}}

    monkeypatch.setattr(srv, "_generate_impl", fake_generate)
    r = client.post("/forge/jobs", json={"op": "generate", "payload": {"prompt": "x", "duration": 8, "steps": 4}})
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["ok"] is True and body["job_id"].startswith("forge-") and body["position"] == 0
    done = poll(client, body["job_id"])
    assert done["state"] == "done" and done["result"]["seed"] == 1
    assert done["payload"] == {"prompt": "x", "duration": 8, "steps": 4}
    assert seen["prompt"] == "x"
    listed = client.get("/forge/jobs?limit=5").json()
    assert listed["ok"] and listed["jobs"][0]["job_id"] == body["job_id"]


@pytest.mark.parametrize("body,status,needle", [
    ({"op": "generate", "payload": {"prompt": "x", "duration": 200}}, 400, "capped at 184 s"),
    ({"op": "nope", "payload": {}}, 400, "unknown op"),
    ({"op": "generate", "payload": [1]}, 400, "payload"),
    ({"payload": {}}, 400, "op"),
])
def test_submit_validation(client, body, status, needle):
    r = client.post("/forge/jobs", json=body)
    assert r.status_code == status
    assert r.json()["ok"] is False and needle in r.json()["error"]


def test_unknown_job_404(client):
    assert client.get("/forge/jobs/forge-x").status_code == 404
    assert client.delete("/forge/jobs/forge-x").status_code == 404


def test_error_job(srv, client, monkeypatch):
    def boom(req):
        raise RuntimeError("kaput")
    monkeypatch.setattr(srv, "_decode_impl", boom)
    jid = client.post("/forge/jobs", json={"op": "decode", "payload": {"crop_id": "1"}}).json()["job_id"]
    done = poll(client, jid)
    assert done["state"] == "error" and done["error"] == "kaput"


def test_log_and_status_progress(srv, client):
    srv.log("forge-log-probe")
    body = client.get("/forge/log?since=0").json()
    assert body["ok"] and any(line["text"].endswith("forge-log-probe") for line in body["lines"])
    last = body["seq"]
    assert client.get(f"/forge/log?since={last}").json()["lines"] == []
    st = client.get("/status").json()
    assert "progress" in st
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest eval/tests/test_forge_api_jobs.py -q`
Expected: FAIL — 404 on `/forge/jobs` (router not mounted).

- [ ] **Step 3: Implement `eval/forge/services.py`**

```python
"""Server-bound helpers that touch the resident model or its config. Kept out of the pure modules."""
import hashlib
import os
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from . import refs
from .contract import HOP


class Services:
    def __init__(self, srv, paths_fn):
        self.srv = srv
        self._paths = paths_fn

    def latent_dir(self):
        d = (self.srv.PLAYER_CFG or {}).get("latent_dir") or ""
        return Path(d) if d else None

    def ref_context(self) -> refs.RefContext:
        p = self._paths()
        ld = self.latent_dir()
        roots = {"renders": Path(self.srv.OUT_DIR), "uploads": p.uploads}
        if ld is not None:
            roots["crops"] = ld
        return refs.RefContext(out_dir=Path(self.srv.OUT_DIR), uploads=p.uploads, latent_dir=ld,
                               decode_crop=self.decode_crop, roots=roots)

    def resolve_audio(self, ref) -> Path:
        return refs.resolve_audio(ref, self.ref_context())

    def decode_crop(self, crop_id) -> Path:
        out = self._paths().cache_dir("decode") / f"{refs.check_crop_id(crop_id)}.wav"
        if out.exists():
            return out
        srv = self.srv
        arr = srv._player_latent(crop_id)
        meta = srv._player_meta(crop_id) if (srv._player_latent_dir() / f"{crop_id}.json").exists() else None
        with srv.GPU_LOCK:
            audio = srv._player_decode(arr)
        audio = srv._player_trim(audio, meta, arr.shape[1])
        tmp = out.with_name(out.stem + ".part.wav")
        sf.write(tmp, np.ascontiguousarray(audio.T), srv.SR, subtype="FLOAT")
        os.replace(tmp, out)
        return out

    def load_audio(self, path) -> np.ndarray:
        return self.srv.load_audio(str(path))

    def encode_cached(self, audio: np.ndarray) -> torch.Tensor:
        """(2, N) float32 audio -> (1, 256, ceil(N/HOP)) float32 CPU latent, cached by content."""
        a = np.ascontiguousarray(audio, dtype=np.float32)
        key = hashlib.sha256(a.tobytes()).hexdigest()
        path = self._paths().cache_dir("encode") / f"{key}.npy"
        frames = int(np.ceil(a.shape[1] / HOP))
        if path.exists():
            return torch.from_numpy(np.load(path).astype(np.float32))
        srv = self.srv
        with srv.GPU_LOCK:
            z = srv.MODEL.encode(torch.from_numpy(a), srv.SR, chunked=True)
        z = z.detach().float().cpu()
        if z.dim() == 2:
            z = z.unsqueeze(0)
        if z.shape[-1] < frames:
            z = torch.nn.functional.pad(z, (0, frames - z.shape[-1]))
        z = z[..., :frames].contiguous()
        np.save(path, z.numpy().astype(np.float16))
        return z
```

- [ ] **Step 4: Implement `eval/forge_api.py`**

```python
"""Latent Forge HTTP routes (spec §6). Thin: parse, validate, dispatch into eval/forge/*.

The server imports this module and calls bind(sys.modules[__name__]) — NEVER
`import explorer_render_server` from here: run as a script the server is `__main__`,
and a second import would build a second, model-less copy of every global.
"""
import functools
import traceback

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from forge import contract, jobs as jobs_mod, logseq, progress
from forge.contract import ForgeError
from forge.paths import ForgePaths
from forge.services import Services

router = APIRouter()
SRV = None
QUEUE = None
_RUNNERS = {}
_VALIDATORS = {}
_SERVICES = None

EXISTING_OPS = {"generate": "_generate_impl", "a2a_track": "_a2a_track_impl", "a2a_mix": "_a2a_mix_impl",
                "longform": "_longform_impl", "decode": "_decode_impl", "bend": "_bend_impl"}


def ok(**kw):
    return {"ok": True, **kw}


def err(status, message, **extra):
    return JSONResponse({"ok": False, "error": message, **extra}, status_code=status)


def forge_route(fn):
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except ForgeError as e:
            return err(e.status, e.message)
        except Exception as e:  # noqa: BLE001
            SRV.log(f"[forge] error {e}")
            return err(500, str(e), traceback=traceback.format_exc())
    return wrapper


def paths() -> ForgePaths:
    return ForgePaths(SRV.OUT_DIR).ensure()


def services() -> Services:
    global _SERVICES
    if _SERVICES is None or _SERVICES.srv is not SRV:
        _SERVICES = Services(SRV, paths)
    return _SERVICES


def _existing_runner(op, impl_name):
    def run(job_id, payload):
        steps = 0 if op in ("decode", "bend") else int(payload.get("steps", 24))
        passes = len(payload.get("noise_levels") or [1]) if op == "a2a_track" else 1
        progress.begin(job_id, op, steps * passes)
        try:
            return getattr(SRV, impl_name)(payload)          # looked up per call: monkeypatchable
        finally:
            progress.end()
    return run


def _validate_existing(op, payload):
    if op == "generate":
        contract.check_cap(payload.get("duration", 47.0), "generate")
    if op == "longform" and not payload.get("audio_path"):
        contract.check_cap(payload.get("duration", 120.0), "longform")


def register_runner(op, fn, validator=None):
    _RUNNERS[op] = fn
    if validator is not None:
        _VALIDATORS[op] = validator
    if QUEUE is not None:
        QUEUE.set_runner(op, fn)


def reset_queue():
    global QUEUE
    if QUEUE is not None:
        QUEUE.stop()
    QUEUE = jobs_mod.JobQueue(_RUNNERS, max_pending=contract.MAX_PENDING_JOBS,
                              log=lambda m: SRV.log(m))
    return QUEUE


def bind(srv):
    global SRV
    SRV = srv
    for op, impl in EXISTING_OPS.items():
        register_runner(op, _existing_runner(op, impl),
                        validator=lambda p, _op=op: _validate_existing(_op, p))
    reset_queue()


# ------------------------------------------------------------------ jobs
@router.post("/forge/jobs")
@forge_route
async def jobs_submit(request: Request):
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        raise ForgeError(400, "body must be JSON {op, payload}")
    if not isinstance(body, dict) or not isinstance(body.get("op"), str):
        raise ForgeError(400, "body needs an 'op' string")
    op, payload = body["op"], body.get("payload")
    if op not in _RUNNERS:
        raise ForgeError(400, f"unknown op {op!r} (have {', '.join(sorted(_RUNNERS))})")
    if not isinstance(payload, dict):
        raise ForgeError(400, "payload must be a JSON object")
    if op in _VALIDATORS:
        _VALIDATORS[op](payload)
    try:
        jid, ahead = QUEUE.submit(op, payload)
    except jobs_mod.QueueFull:
        raise ForgeError(409, "job queue full")
    return JSONResponse({"ok": True, "job_id": jid, "position": ahead}, status_code=202)


@router.get("/forge/jobs")
@forge_route
async def jobs_list(limit: int = 50):
    return ok(jobs=QUEUE.list(limit))


@router.get("/forge/jobs/{job_id}")
@forge_route
async def jobs_get(job_id: str):
    rec = QUEUE.get(job_id)
    if rec is None:
        raise ForgeError(404, f"no job {job_id}")
    snap = progress.snapshot()
    prog = snap if (snap and snap["job_id"] == job_id and rec["state"] == "running") else None
    return ok(**rec, progress=prog)


@router.delete("/forge/jobs/{job_id}")
@forge_route
async def jobs_cancel(job_id: str):
    try:
        rec = QUEUE.cancel(job_id)
    except KeyError:
        raise ForgeError(404, f"no job {job_id}")
    except jobs_mod.CannotCancel:
        raise ForgeError(409, "cannot cancel a running pass")
    return ok(**rec, progress=None)


# ------------------------------------------------------------------ log
@router.get("/forge/log")
@forge_route
async def log_since(since: int = 0):
    last, lines = logseq.since(since)
    return ok(seq=last, lines=lines)
```

- [ ] **Step 5: Hook the server**

In `eval/explorer_render_server.py`:

(a) After line `import chroma_morph_transitions as cmt  ...` add:
```python
from forge import logseq as forge_logseq, progress as forge_progress  # noqa: E402
from forge.contract import ForgeError  # noqa: E402
```

(b) In `log(msg)` after `LOG_RING.append(line)` add:
```python
    forge_logseq.append(line)
```

(c) In `make_log_cb`, replace
```python
        i = counter["i"]
        counter["i"] += 1
```
with
```python
        i = counter["i"]
        counter["i"] += 1
        forge_progress.on_step(i + 1, steps)
```

(d) In `status()` change the return to:
```python
    return {"ok": True, "busy": busy, "job_id": CURRENT_JOB if busy else None,
            "log_tail": list(LOG_RING)[-20:], "progress": forge_progress.snapshot()}
```

(e) In `info()` add the key `"objective": getattr(getattr(MODEL, "model", None), "diffusion_objective", None),` to the returned dict.

(f) In `_run`, before `except Exception as e:` add:
```python
    except ForgeError as e:
        return JSONResponse({"error": e.message}, status_code=e.status)
```

(g) Immediately above `# ---------------------------------------------------------------- boot` add:
```python
# ---------------------------------------------------------------- Latent Forge
import forge_api  # noqa: E402
forge_api.bind(sys.modules[__name__])
app.include_router(forge_api.router)
```

- [ ] **Step 6: Run tests**

Run: `$PY -m pytest eval/tests/test_forge_api_jobs.py eval/tests/test_forge_boot.py eval/tests/test_render_server_ab.py -q`
Expected: all passed (the existing `/ab` tests must still pass).

- [ ] **Step 7: Commit**

```bash
git add eval/forge_api.py eval/forge/services.py eval/explorer_render_server.py eval/tests/test_forge_api_jobs.py
Misc/agent_commit.sh WINTERMUTE -m "forge: /forge router, async jobs over existing ops, log route, progress hooks"
```

---

### Task 9: Library routes — upload, files, audio, sessions, presets

**Files:**
- Modify: `eval/forge_api.py` (append routes)
- Create: `eval/tests/test_forge_api_library.py`

**Interfaces:**
- Consumes: `Services`, `JsonStore`, `UploadWriter`, `probe_audio`, `list_files`.
- Produces: `PUT /forge/upload`, `GET /forge/files`, `GET /forge/audio`, `GET /forge/sessions`, `GET|PUT /forge/sessions/{name}`, `GET /forge/presets/{level}`, `GET|PUT|DELETE /forge/presets/{level}/{name}`.

- [ ] **Step 1: Write the failing test**

```python
import io
import json

import numpy as np
import pytest
import soundfile as sf

import forge_testutil  # noqa: F401

fastapi_testclient = pytest.importorskip("fastapi.testclient")


@pytest.fixture
def client(monkeypatch, tmp_path):
    import explorer_render_server as srv
    import forge_api
    monkeypatch.setattr(srv, "OUT_DIR", tmp_path)
    monkeypatch.setattr(srv, "PLAYER_CFG", {"latent_dir": "", "chunk_size": 128, "overlap": 32})
    forge_api.reset_queue()
    return fastapi_testclient.TestClient(srv.app)


def wav_bytes(seconds=0.25):
    buf = io.BytesIO()
    sf.write(buf, np.zeros((int(44100 * seconds), 2), dtype=np.float32), 44100, format="WAV")
    return buf.getvalue()


def test_upload_then_audio_and_files(client):
    data = wav_bytes()
    r = client.put("/forge/upload?filename=take.wav", content=data)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ref"]["kind"] == "upload" and body["channels"] == 2 and body["duration_sec"] == 0.25
    again = client.put("/forge/upload?filename=other.wav", content=data).json()
    assert again["ref"] == body["ref"]
    a = client.get("/forge/audio", params={"ref": json.dumps(body["ref"])})
    assert a.status_code == 200 and a.headers["content-type"].startswith("audio/wav") and a.content == data
    files = client.get("/forge/files?root=uploads").json()
    assert files["files"][0]["ref"] == body["ref"]
    assert [r["id"] for r in files["roots"]] == ["crops", "renders", "uploads"]


def test_upload_rejects(client):
    assert client.put("/forge/upload?filename=x.txt", content=b"abc").status_code == 400
    r = client.put("/forge/upload?filename=x.wav", content=b"not audio at all")
    assert r.status_code == 400 and "readable" in r.json()["error"]


def test_audio_bad_ref(client):
    assert client.get("/forge/audio", params={"ref": "{not json"}).status_code == 400
    assert client.get("/forge/audio", params={"ref": json.dumps({"kind": "upload", "sha256": "c" * 64})}).status_code == 404


def test_sessions(client):
    assert client.get("/forge/sessions").json() == {"ok": True, "sessions": []}
    assert client.put("/forge/sessions/set1", json={"version": 1}).status_code == 400
    assert client.put("/forge/sessions/set1", json={"version": 2, "clips": [{}, {}]}).json() == {"ok": True}
    s = client.get("/forge/sessions").json()["sessions"][0]
    assert s["name"] == "set1" and s["n_clips"] == 2
    assert client.get("/forge/sessions/set1").json() == {"version": 2, "clips": [{}, {}]}
    assert client.get("/forge/sessions/nope").status_code == 404
    assert client.put("/forge/sessions/bad name", json={"version": 2}).status_code in (400, 404)


def test_presets(client):
    assert client.get("/forge/presets/render").json() == {"ok": True, "names": []}
    assert client.put("/forge/presets/render/warm", json={"prompt": "pad"}).json() == {"ok": True}
    assert client.get("/forge/presets/render").json()["names"] == ["warm"]
    assert client.get("/forge/presets/render/warm").json() == {"prompt": "pad"}
    assert client.get("/forge/presets/sampling").status_code == 400
    assert client.delete("/forge/presets/render/warm").json() == {"ok": True}
    assert client.delete("/forge/presets/render/warm").status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest eval/tests/test_forge_api_library.py -q`
Expected: FAIL — 404/405 on the new routes.

- [ ] **Step 3: Implement (append to `eval/forge_api.py`)**

Add imports at the top of the module:
```python
import json
from pathlib import Path

from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from forge import library, uploads
from forge.store import JsonStore
```

Append:
```python
# ------------------------------------------------------------------ library
_MEDIA = {".wav": "audio/wav", ".flac": "audio/flac", ".mp3": "audio/mpeg", ".m4a": "audio/mp4",
          ".ogg": "audio/ogg", ".aif": "audio/aiff", ".aiff": "audio/aiff"}


def parse_ref_param(raw):
    try:
        ref = json.loads(raw)
    except (TypeError, ValueError):
        raise ForgeError(400, "ref must be URL-encoded JSON")
    return ref


@router.put("/forge/upload")
@forge_route
async def upload(request: Request, filename: str = ""):
    w = uploads.UploadWriter(filename, paths().uploads, contract.UPLOAD_MAX_BYTES)
    try:
        async for chunk in request.stream():
            w.feed(chunk)
        dst, sha, n = w.finish()
    except BaseException:
        w.abort()
        raise
    try:
        info = await run_in_threadpool(uploads.probe_audio, dst)
    except ForgeError:
        dst.unlink(missing_ok=True)
        raise
    return ok(ref={"kind": "upload", "sha256": sha}, path=str(dst), bytes=n, **info)


@router.get("/forge/files")
@forge_route
async def files(root: str = "crops", q: str = "", limit: int = 500):
    ctx = services().ref_context()
    roots = {"crops": ctx.roots.get("crops"), "renders": ctx.roots.get("renders"), "uploads": ctx.roots.get("uploads")}
    return ok(**await run_in_threadpool(library.list_files, roots, root, q, limit))


@router.get("/forge/audio")
@forge_route
async def audio(ref: str):
    path = await run_in_threadpool(services().resolve_audio, parse_ref_param(ref))
    return FileResponse(path, media_type=_MEDIA.get(Path(path).suffix.lower(), "application/octet-stream"))


def _sessions():
    return JsonStore(paths().sessions, contract.SESSION_MAX_BYTES)


@router.get("/forge/sessions")
@forge_route
async def sessions_list():
    store = _sessions()
    rows = []
    for row in store.listing():
        try:
            n = len(store.get(row["name"]).get("clips") or [])
        except (ValueError, ForgeError):
            n = 0
        rows.append({**row, "n_clips": n})
    return ok(sessions=rows)


@router.get("/forge/sessions/{name}")
@forge_route
async def sessions_get(name: str):
    return _sessions().get(name)


@router.put("/forge/sessions/{name}")
@forge_route
async def sessions_put(name: str, request: Request):
    body = await request.json()
    if not isinstance(body, dict) or body.get("version") != 2:
        raise ForgeError(400, "session must be a JSON object with \"version\": 2")
    _sessions().put(name, body)
    return ok()


def _presets(level):
    return JsonStore(paths().preset_dir(level), contract.PRESET_MAX_BYTES)


@router.get("/forge/presets/{level}")
@forge_route
async def presets_list(level: str):
    return ok(names=_presets(level).names())


@router.get("/forge/presets/{level}/{name}")
@forge_route
async def presets_get(level: str, name: str):
    return _presets(level).get(name)


@router.put("/forge/presets/{level}/{name}")
@forge_route
async def presets_put(level: str, name: str, request: Request):
    _presets(level).put(name, await request.json())
    return ok()


@router.delete("/forge/presets/{level}/{name}")
@forge_route
async def presets_delete(level: str, name: str):
    _presets(level).delete(name)
    return ok()
```

- [ ] **Step 4: Run tests**

Run: `$PY -m pytest eval/tests/test_forge_api_library.py -q`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add eval/forge_api.py eval/tests/test_forge_api_library.py
Misc/agent_commit.sh WINTERMUTE -m "forge: upload, files, audio, sessions and presets routes"
```

---

### Task 10: Beat analysis

**Files:**
- Create: `eval/forge/analysis.py`, `eval/tests/test_forge_analysis.py`
- Modify: `eval/forge_api.py` (append `POST /forge/analyze`)

**Interfaces:**
- Produces: `analysis.analyze_audio(audio (C,N) or (N,), sr, bpm_hint=None) -> {"bpm","bpm_candidates","beats_sec","downbeats_sec","duration_sec","source"}`. Route `POST /forge/analyze {audio: AudioRef}`.

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
import pytest

import forge_testutil  # noqa: F401
from forge.analysis import analyze_audio


def click_track(bpm=120.0, seconds=16.0, sr=22050, accent_every=4):
    y = np.zeros(int(seconds * sr), dtype=np.float32)
    rng = np.random.default_rng(0)
    beat = 60.0 / bpm
    for k in range(int(seconds / beat)):
        s = int(k * beat * sr)
        amp = 1.0 if k % accent_every == 0 else 0.35
        n = int(0.012 * sr)
        y[s:s + n] += amp * rng.standard_normal(min(n, len(y) - s)).astype(np.float32)
    return np.stack([y, y])


def test_click_track_tempo_and_downbeats():
    sr = 22050
    r = analyze_audio(click_track(sr=sr), sr)
    assert r["source"] == "librosa"
    assert any(abs(c - 120.0) < 1.5 for c in r["bpm_candidates"])
    downs = np.asarray(r["downbeats_sec"])
    assert len(downs) >= 5
    assert np.median(np.diff(downs)) == pytest.approx(2.0, abs=0.06)
    phase = downs[0] % 2.0
    assert phase < 0.1 or phase > 1.9
    assert r["duration_sec"] == pytest.approx(16.0, abs=0.01)


def test_hint_wins():
    sr = 22050
    r = analyze_audio(click_track(sr=sr), sr, bpm_hint=122.4)
    assert r["bpm"] == 122.4 and r["source"] == "sidecar"


def test_silence_does_not_crash():
    r = analyze_audio(np.zeros((2, 22050 * 3), dtype=np.float32), 22050)
    assert r["duration_sec"] == pytest.approx(3.0)
    assert isinstance(r["bpm"], float)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest eval/tests/test_forge_analysis.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`eval/forge/analysis.py`:
```python
"""Tempo, beats and downbeats for a clip (spec §6.3 POST /forge/analyze).

Downbeat phase = the strongest mean onset energy among the four candidate phases — the
same heuristic as chroma_morph_transitions.downbeat_near, over the whole clip. No genre
tempo folding: the client offers bpm_candidates (t, 2t, t/2) instead.
"""
import numpy as np


def analyze_audio(audio, sr, bpm_hint=None) -> dict:
    import librosa

    y = np.asarray(audio, dtype=np.float32)
    mono = y.mean(axis=0) if y.ndim == 2 else y
    duration = mono.shape[0] / float(sr)
    beats = np.zeros(0)
    tempo_val = 120.0
    if np.any(mono):
        tempo, beats = librosa.beat.beat_track(y=mono, sr=sr, units="time", trim=False)
        beats = np.asarray(beats, dtype=np.float64)
        if len(beats) >= 8:
            tempo_val = 60.0 / float(np.median(np.diff(beats)))
        elif np.size(tempo):
            tempo_val = float(np.atleast_1d(tempo)[0]) or 120.0
    downbeats = beats
    if len(beats) >= 8:
        env = librosa.onset.onset_strength(y=mono, sr=sr)
        et = librosa.times_like(env, sr=sr)
        strength = np.interp(beats, et, env)
        phase = int(np.argmax([strength[p::4].mean() for p in range(4)]))
        downbeats = beats[phase::4]
    bpm = float(bpm_hint) if bpm_hint else float(tempo_val)
    return {"bpm": round(bpm, 3),
            "bpm_candidates": [round(tempo_val, 3), round(2 * tempo_val, 3), round(tempo_val / 2, 3)],
            "beats_sec": [round(float(b), 4) for b in beats],
            "downbeats_sec": [round(float(b), 4) for b in downbeats],
            "duration_sec": round(duration, 3),
            "source": "sidecar" if bpm_hint else "librosa"}
```

Append to `eval/forge_api.py`:
```python
from forge import analysis


def _crop_meta(crop_id):
    try:
        return SRV._player_meta(crop_id)
    except Exception:  # noqa: BLE001
        return None


def _analyze_ref(ref):
    svc = services()
    if isinstance(ref, dict) and ref.get("kind") == "crop":
        svc.resolve_audio(ref)                                  # validates + caches the decode
        meta = _crop_meta(ref["crop_id"]) or {}
        hint = meta.get("bpm_madmom") or meta.get("bpm_essentia")
        src = meta.get("source_path")
        if src and Path(src).is_file():
            import soundfile as sf
            a, sr = sf.read(src, dtype="float32", always_2d=True,
                            start=int(meta["start_sample"]), stop=int(meta["end_sample"]))
            return analysis.analyze_audio(a.T, sr, bpm_hint=hint)
        a = svc.load_audio(svc.decode_crop(ref["crop_id"]))
        return analysis.analyze_audio(a, SRV.SR, bpm_hint=hint)
    path = svc.resolve_audio(ref)
    return analysis.analyze_audio(svc.load_audio(path), SRV.SR)


@router.post("/forge/analyze")
@forge_route
async def analyze(request: Request):
    body = await request.json()
    return ok(**await run_in_threadpool(_analyze_ref, (body or {}).get("audio")))
```

- [ ] **Step 4: Run tests**

Run: `$PY -m pytest eval/tests/test_forge_analysis.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add eval/forge/analysis.py eval/forge_api.py eval/tests/test_forge_analysis.py
Misc/agent_commit.sh WINTERMUTE -m "forge: beat/downbeat analysis and /forge/analyze"
```

---

### Task 11: Bungee stretch

**Files:**
- Create: `eval/forge/stretch.py`, `eval/tests/test_forge_stretch.py`
- Modify: `eval/forge_api.py` (append `POST /forge/stretch`)

**Interfaces:**
- Produces: `stretch.BUNGEE_PY`, `stretch.BUNGEE_TAG = "bungee-0.2.1"`, `stretch.validate(speed, semitones) -> (float, float)`, `stretch.is_identity(speed, semitones) -> bool`, `stretch.cache_key(file_sha, speed, semitones) -> str`, `stretch.stretch_file(src, dst, speed, semitones, python=BUNGEE_PY) -> Path`. Route returns `{"ok", "ref": {"kind":"path","path"}, "duration_sec"}`.

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
import pytest
import soundfile as sf

import forge_testutil  # noqa: F401
from forge import stretch
from forge.contract import ForgeError


def test_validate_and_identity():
    assert stretch.validate(1.0, 0.0) == (1.0, 0.0)
    for bad in [(0.49, 0), (2.01, 0), (1, 24.5), ("x", 0)]:
        with pytest.raises(ForgeError):
            stretch.validate(*bad)
    assert stretch.is_identity(1.0004, 0.00005)
    assert not stretch.is_identity(1.001, 0)


def test_cache_key_rounding():
    a = stretch.cache_key("f" * 64, 1.0000001, 0.00001)
    b = stretch.cache_key("f" * 64, 1.0000004, 0.00004)
    assert a == b and len(a) == 64
    assert a != stretch.cache_key("f" * 64, 1.1, 0.0)


needs_bungee = pytest.mark.skipif(not stretch.BUNGEE_PY.exists(), reason="mir/.venv not present")


def dominant_hz(y, sr):
    spec = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    return np.fft.rfftfreq(len(y), 1 / sr)[int(np.argmax(spec))]


@needs_bungee
def test_speed_and_pitch(tmp_path):
    sr = 44100
    t = np.arange(2 * sr) / sr
    tone = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    src = tmp_path / "in.wav"
    sf.write(src, np.stack([tone, tone], axis=1), sr, subtype="FLOAT")
    fast = stretch.stretch_file(src, tmp_path / "fast.wav", 2.0, 0.0)
    y, _ = sf.read(fast, always_2d=True)
    assert y.shape[0] / sr == pytest.approx(1.0, rel=0.06)
    up = stretch.stretch_file(src, tmp_path / "up.wav", 1.0, 12.0)
    y2, _ = sf.read(up, always_2d=True)
    mid = y2[len(y2) // 4: 3 * len(y2) // 4, 0]
    assert dominant_hz(mid, sr) == pytest.approx(880.0, rel=0.03)
    assert not list(tmp_path.glob("*.part.wav"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest eval/tests/test_forge_stretch.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`eval/forge/stretch.py`:
```python
"""Time-stretch / pitch-shift through Bungee in mir/.venv (spec §6.3 POST /forge/stretch).

speed > 1 = faster (shorter), the Bungee convention; semitones > 0 = up.
"""
import hashlib
import math
import os
import subprocess
from pathlib import Path

from .contract import ForgeError

BUNGEE_PY = Path("/home/kim/Projects/mir/.venv/bin/python")
BUNGEE_TAG = "bungee-0.2.1"

_CODE = r"""
import sys
import numpy as np
import soundfile as sf
from bungee_python import bungee as B
src, dst, speed, semis = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
d, sr = sf.read(src, dtype="float32", always_2d=True)
st = B.Bungee(sample_rate=sr, channels=d.shape[1])
if abs(semis) > 1e-4:
    st.set_pitch(2.0 ** (semis / 12.0))
if abs(speed - 1.0) > 5e-4:
    st.set_speed(speed)
y = np.asarray(st.process(d), dtype=np.float32)
if y.ndim == 1:
    y = y.reshape(-1, d.shape[1])
sf.write(dst, y, sr, subtype="FLOAT")
"""


def validate(speed, semitones):
    try:
        sp, se = float(speed), float(semitones)
    except (TypeError, ValueError):
        raise ForgeError(400, "speed and semitones must be numbers")
    if not (math.isfinite(sp) and 0.5 <= sp <= 2.0):
        raise ForgeError(400, f"speed {speed!r} outside 0.5..2")
    if not (math.isfinite(se) and -24.0 <= se <= 24.0):
        raise ForgeError(400, f"semitones {semitones!r} outside -24..24")
    return sp, se


def is_identity(speed, semitones) -> bool:
    return abs(float(speed) - 1.0) < 5e-4 and abs(float(semitones)) < 1e-4


def cache_key(file_sha, speed, semitones) -> str:
    raw = f"{file_sha}|{round(float(speed), 6):.6f}|{round(float(semitones), 4):.4f}|{BUNGEE_TAG}"
    return hashlib.sha256(raw.encode()).hexdigest()


def stretch_file(src, dst, speed, semitones, python=BUNGEE_PY, timeout=900) -> Path:
    dst = Path(dst)
    tmp = dst.with_name(dst.stem + ".part.wav")
    r = subprocess.run([str(python), "-c", _CODE, str(src), str(tmp), repr(float(speed)), repr(float(semitones))],
                       capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0 or not tmp.exists():
        if tmp.exists():
            tmp.unlink()
        raise RuntimeError(f"bungee failed (rc={r.returncode}): {r.stderr.strip()[-400:]}")
    os.replace(tmp, dst)
    return dst
```

Append to `eval/forge_api.py`:
```python
from forge import stretch
from forge.hashing import file_sha256


def _stretch_ref(ref, speed, semitones):
    import soundfile as sf
    speed, semitones = stretch.validate(speed, semitones)
    svc = services()
    src = svc.resolve_audio(ref)
    if stretch.is_identity(speed, semitones):
        return {"ref": ref, "duration_sec": round(sf.info(str(src)).duration, 3)
                if src.suffix.lower() in (".wav", ".flac") else uploads.probe_audio(src)["duration_sec"]}
    sha = file_sha256(src)
    dst = paths().cache_dir("stretch") / f"{stretch.cache_key(sha, speed, semitones)}.wav"
    if not dst.exists():
        readable = src
        if src.suffix.lower() not in (".wav", ".flac"):
            readable = paths().cache_dir("decode") / f"{sha}.wav"
            if not readable.exists():
                sf.write(readable, svc.load_audio(src).T, SRV.SR, subtype="FLOAT")
        stretch.stretch_file(readable, dst, speed, semitones)
    return {"ref": {"kind": "path", "path": str(dst)}, "duration_sec": round(sf.info(str(dst)).duration, 3)}


@router.post("/forge/stretch")
@forge_route
async def stretch_route(request: Request):
    body = await request.json() or {}
    return ok(**await run_in_threadpool(_stretch_ref, body.get("audio"), body.get("speed", 1.0),
                                        body.get("semitones", 0.0)))
```

- [ ] **Step 4: Run tests**

Run: `$PY -m pytest eval/tests/test_forge_stretch.py -q`
Expected: 3 passed (the Bungee test runs because `mir/.venv` exists). If `test_speed_and_pitch` fails with `No module named soundfile` inside the subprocess, report BLOCKED with the stderr — do not install packages into `mir/.venv` without Kim.

- [ ] **Step 5: Commit**

```bash
git add eval/forge/stretch.py eval/forge_api.py eval/tests/test_forge_stretch.py
Misc/agent_commit.sh WINTERMUTE -m "forge: bungee stretch/pitch via mir/.venv subprocess, cached"
```

---

### Task 12: SAME chroma

**Files:**
- Create: `eval/forge/chroma.py`, `eval/tests/test_forge_chroma.py`
- Modify: `eval/forge_api.py` (append `POST /forge/chroma`)

**Interfaces:**
- Produces: `chroma.chroma_payload(audio (C,N), sr, compute=None, fold=None) -> {"frames","fps","bands":{"shape","scale","data_b64"},"fold12":{"shape","scale","data_b64"}}`; `chroma.chroma_384(audio (C,N), sr, frames:int) -> np.ndarray (384, frames)` (used by M8).

- [ ] **Step 1: Write the failing test**

```python
import base64
import sys
from pathlib import Path

import numpy as np
import pytest

import forge_testutil  # noqa: F401

MIRCHROMA = Path("/home/kim/Projects/mir-same-chroma/src")
pytestmark = pytest.mark.skipif(not MIRCHROMA.is_dir(), reason="mir-same-chroma checkout missing")
if MIRCHROMA.is_dir() and str(MIRCHROMA) not in sys.path:
    sys.path.insert(0, str(MIRCHROMA))

from forge.chroma import chroma_384, chroma_payload  # noqa: E402


def tone(hz, seconds=3.0, sr=44100):
    t = np.arange(int(seconds * sr)) / sr
    y = (0.5 * np.sin(2 * np.pi * hz * t)).astype(np.float32)
    return np.stack([y, y])


def test_a440_folds_to_pitch_class_a():
    p = chroma_payload(tone(440.0), 44100)
    T = p["frames"]
    assert p["fps"] == 44100 / 4096
    assert p["bands"]["shape"] == [3, 128, T] and len(p["bands"]["scale"]) == 3
    raw = np.frombuffer(base64.b64decode(p["bands"]["data_b64"]), dtype=np.uint8)
    assert raw.size == 3 * 128 * T
    f12 = np.frombuffer(base64.b64decode(p["fold12"]["data_b64"]), dtype=np.uint8).reshape(12, T)
    assert int(np.argmax(f12.mean(axis=1))) == 9          # C C# D D# E F F# G G# A -> 9
    assert f12.max() == 255


def test_silence_is_all_zero_but_valid():
    p = chroma_payload(np.zeros((2, 44100), dtype=np.float32), 44100)
    f12 = np.frombuffer(base64.b64decode(p["fold12"]["data_b64"]), dtype=np.uint8)
    assert f12.max() == 0 and all(s == 1.0 for s in p["bands"]["scale"])


def test_chroma_384_fits_frames():
    c = chroma_384(tone(220.0, 2.0), 44100, 30)
    assert c.shape == (384, 30) and c.dtype == np.float32
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest eval/tests/test_forge_chroma.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`eval/forge/chroma.py`:
```python
"""SAME octave-band chroma for the CHROMA tab (spec §5.4, §6.3): 3 bands x 128 bins = 384-d."""
import base64

import numpy as np

from .contract import FPS


def _same():
    from harmonic.same_chroma import compute_same_chroma, fold_to_12
    return compute_same_chroma, fold_to_12


def _b64(a: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(a).tobytes(order="C")).decode()


def _quant(a: np.ndarray):
    peak = float(a.max()) if a.size else 0.0
    scale = peak if peak > 0 else 1.0
    return np.clip(np.rint(a / scale * 255.0), 0, 255).astype(np.uint8), scale


def chroma_payload(audio, sr, compute=None, fold=None) -> dict:
    if compute is None or fold is None:
        compute, fold = _same()
    bands = np.maximum(np.asarray(compute(np.asarray(audio, dtype=np.float32).T, sr), dtype=np.float32), 0.0)
    T = int(bands.shape[-1])
    qs, scales = zip(*(_quant(bands[b]) for b in range(3)))
    f12 = np.asarray(fold(bands), dtype=np.float32).sum(axis=0)
    mx = f12.max(axis=0, keepdims=True)
    f12n = np.where(mx > 0, f12 / np.maximum(mx, 1e-12), 0.0)
    q12 = np.clip(np.rint(f12n * 255.0), 0, 255).astype(np.uint8)
    return {"frames": T, "fps": FPS,
            "bands": {"shape": [3, 128, T], "scale": [float(s) for s in scales], "data_b64": _b64(np.stack(qs))},
            "fold12": {"shape": [12, T], "scale": 1.0, "data_b64": _b64(q12)}}


def chroma_384(audio, sr, frames: int) -> np.ndarray:
    compute, _ = _same()
    c = np.asarray(compute(np.asarray(audio, dtype=np.float32).T, sr), dtype=np.float32).reshape(384, -1)
    if c.shape[1] >= frames:
        return np.ascontiguousarray(c[:, :frames])
    return np.pad(c, ((0, 0), (0, frames - c.shape[1])), mode="edge")
```

Append to `eval/forge_api.py`:
```python
from forge import chroma


def _chroma_ref(ref):
    svc = services()
    src = svc.resolve_audio(ref)
    cache = paths().cache_dir("chroma") / f"{file_sha256(src)}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    payload = chroma.chroma_payload(svc.load_audio(src), SRV.SR)
    cache.write_text(json.dumps(payload))
    return payload


@router.post("/forge/chroma")
@forge_route
async def chroma_route(request: Request):
    body = await request.json() or {}
    return ok(**await run_in_threadpool(_chroma_ref, body.get("audio")))
```

- [ ] **Step 4: Run tests**

Run: `$PY -m pytest eval/tests/test_forge_chroma.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add eval/forge/chroma.py eval/forge_api.py eval/tests/test_forge_chroma.py
Misc/agent_commit.sh WINTERMUTE -m "forge: SAME 3x128 chroma + 12-class fold, /forge/chroma"
```

---

### Task 13: Statistics and dataset scalars

**Files:**
- Create: `eval/forge/stats.py`, `eval/tests/test_forge_stats.py`
- Modify: `eval/forge_api.py` (append `POST /forge/stats`, `GET /forge/dataset_scalars`)

**Interfaces:**
- Produces: `stats.xcorr_payload(latents: list[np.ndarray (256,T)], max_frames) -> (n_frames, {"shape","data_b64"})`; `stats.resample_points(values, max_points) -> list[float|None]`; `stats.LIBROSA_FEATURES`; `stats.audio_feature(audio (C,N), sr, feature, n_frames) -> np.ndarray (n_frames,)`; `stats.DatasetIndex(latent_dir)` with `.fields() -> list[str]`, `.points(x, y, limit=6000) -> list[{"crop_id","x","y","label"}]`.

- [ ] **Step 1: Write the failing test**

```python
import base64
import json

import numpy as np
import pytest

import forge_testutil  # noqa: F401
from forge import stats
from forge.contract import ForgeError


def test_xcorr_payload_diag_and_correlated_dims():
    rng = np.random.default_rng(0)
    z = rng.standard_normal((256, 300))
    z[1] = z[0] * 2.0
    n, x = stats.xcorr_payload([z[:, :150], z[:, 150:]], max_frames=20000)
    assert n == 300 and x["shape"] == [256, 256]
    q = np.frombuffer(base64.b64decode(x["data_b64"]), dtype=np.uint8).reshape(256, 256)
    assert q[0, 0] == 255 and q[0, 1] == 255 and abs(int(q[2, 3]) - 128) < 40


def test_xcorr_subsamples():
    n, _ = stats.xcorr_payload([np.random.default_rng(1).standard_normal((256, 5000))], max_frames=100)
    assert n == 5000


def test_resample_points():
    assert stats.resample_points([1.0, 2.0], 10) == [1.0, 2.0]
    r = stats.resample_points(list(range(101)), 11)
    assert len(r) == 11 and r[0] == 0.0 and r[-1] == 100.0 and r[5] == pytest.approx(50.0)


def test_audio_feature_shapes():
    sr = 44100
    y = np.zeros((2, sr * 2), dtype=np.float32)
    y[:, sr:] = 0.5
    for f in stats.LIBROSA_FEATURES:
        v = stats.audio_feature(y, sr, f, 22)
        assert v.shape == (22,) and np.all(np.isfinite(v))
    rms = stats.audio_feature(y, sr, "rms", 22)
    assert rms[-3] > rms[2]
    with pytest.raises(ForgeError):
        stats.audio_feature(y, sr, "nope", 22)


def test_dataset_index(tmp_path):
    for i, (bpm, lufs) in enumerate([(120.0, -14.0), (140.0, -9.5), (None, -20.0)]):
        (tmp_path / f"{i:06d}.npy").write_bytes(b"x")
        (tmp_path / f"{i:06d}.json").write_text(json.dumps({
            "bpm_madmom": bpm, "lufs": lufs, "relative_position_start": 0.1 * i,
            "track_metadata_artist": "A", "track_metadata_title": f"T{i}", "padding_mask": [1, 1]}))
    (tmp_path / "000000.TIMESERIES.json").write_text("{}")
    idx = stats.DatasetIndex(tmp_path)
    assert {"bpm", "lufs", "rel_pos"} <= set(idx.fields())
    assert "padding_mask" not in idx.fields()
    pts = idx.points("bpm", "lufs")
    assert [(p["crop_id"], p["x"], p["y"]) for p in pts] == [("000000", 120.0, -14.0), ("000001", 140.0, -9.5)]
    assert pts[0]["label"] == "A — T0"
    with pytest.raises(ForgeError):
        idx.points("nope", "lufs")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest eval/tests/test_forge_stats.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`eval/forge/stats.py`:
```python
"""Statistics view data, first version: xcorr, XY scatter, time series (spec §4.4, §6.5)."""
import base64
import json
from pathlib import Path

import numpy as np

from .contract import HOP, ForgeError

LIBROSA_FEATURES = ("rms", "onset_strength", "spectral_centroid")
ALIASES = {"bpm": ("bpm_madmom", "bpm_essentia"), "rel_pos": ("relative_position_start",)}


def xcorr_payload(latents, max_frames=20000):
    X = np.concatenate([np.asarray(z, dtype=np.float64).T for z in latents], axis=0)
    n = int(X.shape[0])
    if n > max_frames:
        X = X[np.linspace(0, n - 1, int(max_frames)).round().astype(np.int64)]
    with np.errstate(invalid="ignore", divide="ignore"):
        c = np.nan_to_num(np.corrcoef(X, rowvar=False), nan=0.0)
    q = np.clip(np.rint((c + 1.0) / 2.0 * 255.0), 0, 255).astype(np.uint8)
    return n, {"shape": [256, 256], "data_b64": base64.b64encode(q.tobytes()).decode()}


def resample_points(values, max_points):
    v = np.asarray([np.nan if x is None else x for x in values], dtype=np.float64)
    if len(v) > max_points:
        v = np.interp(np.linspace(0, len(v) - 1, int(max_points)), np.arange(len(v)), v)
    return [None if not np.isfinite(x) else round(float(x), 6) for x in v]


def _fit(v, n):
    v = np.asarray(v, dtype=np.float64)
    if len(v) >= n:
        return v[:n]
    return np.pad(v, (0, n - len(v)), mode="edge") if len(v) else np.zeros(n)


def audio_feature(audio, sr, feature, n_frames):
    import librosa
    mono = np.asarray(audio, dtype=np.float32)
    mono = mono.mean(axis=0) if mono.ndim == 2 else mono
    if feature == "rms":
        v = librosa.feature.rms(y=mono, frame_length=2 * HOP, hop_length=HOP)[0]
    elif feature == "spectral_centroid":
        v = librosa.feature.spectral_centroid(y=mono, sr=sr, n_fft=2 * HOP, hop_length=HOP)[0]
    elif feature == "onset_strength":
        env = librosa.onset.onset_strength(y=mono, sr=sr, hop_length=512)
        k = HOP // 512
        m = len(env) // k
        v = env[: m * k].reshape(m, k).mean(axis=1) if m else env
    else:
        raise ForgeError(400, f"unknown audio feature {feature!r} (have {', '.join(LIBROSA_FEATURES)})")
    return _fit(v, int(n_frames))


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v)


class DatasetIndex:
    def __init__(self, latent_dir):
        self.rows = []
        keys = set()
        base = Path(latent_dir)
        for jp in sorted(base.glob("*.json")):
            if jp.name.endswith(".TIMESERIES.json") or not jp.with_suffix(".npy").exists():
                continue
            try:
                m = json.loads(jp.read_text())
            except (OSError, ValueError):
                continue
            fields = {k: float(v) for k, v in m.items() if _num(v)}
            for alias, sources in ALIASES.items():
                for s in sources:
                    if s in fields:
                        fields[alias] = fields[s]
                        break
            keys.update(fields)
            label = f"{m.get('track_metadata_artist', '')} — {m.get('track_metadata_title', '')}".strip(" —")
            self.rows.append({"crop_id": jp.stem, "fields": fields, "label": label})
        self._fields = sorted(keys)

    def fields(self):
        return list(self._fields)

    def points(self, x, y, limit=6000):
        for f in (x, y):
            if f not in self._fields:
                raise ForgeError(400, f"unknown field {f!r}")
        pts = [{"crop_id": r["crop_id"], "x": r["fields"][x], "y": r["fields"][y], "label": r["label"]}
               for r in self.rows if x in r["fields"] and y in r["fields"]]
        if len(pts) > limit:
            pts = [pts[i] for i in np.linspace(0, len(pts) - 1, int(limit)).round().astype(int)]
        return pts
```

Append to `eval/forge_api.py`:
```python
import numpy as np

from forge import stats

_DATASET = {"dir": None, "index": None}


def _latent_entry(ref):
    """LatentRef -> (z (256,T) float32, npz Path|None, audio_fn () -> (np (2,N), sr) | None)."""
    svc = services()
    if not isinstance(ref, dict):
        raise ForgeError(400, "latent ref must be an object")
    kind = ref.get("kind")
    if kind == "crop":
        from forge.refs import check_crop_id
        cid = check_crop_id(ref.get("crop_id"))
        ld = svc.latent_dir()
        if ld is None or not (ld / f"{cid}.npy").is_file():
            raise ForgeError(404, f"no crop {cid}")
        z = np.load(ld / f"{cid}.npy").astype(np.float32)
        z = z[0] if z.ndim == 3 else z
        meta = _crop_meta(cid) or {}
        content = int(sum(meta.get("padding_mask") or [])) or z.shape[1]
        npz = ld / f"{cid}.TIMESERIES.npz"
        return z[:, :content], (npz if npz.is_file() else None), \
            (lambda: (svc.load_audio(svc.decode_crop(cid)), SRV.SR))
    if kind == "path":
        p = Path(str(ref.get("path") or ""))
        if not p.is_absolute() or p.suffix != ".npy" or not p.is_file():
            raise ForgeError(404, f"no latent file {p}")
        z = np.load(p).astype(np.float32)
        z = z[0] if z.ndim == 3 else z
        wav = p.with_name(p.name[: -len(".z0.npy")] + ".wav") if p.name.endswith(".z0.npy") else None
        return z, None, ((lambda: (svc.load_audio(wav), SRV.SR)) if wav and wav.is_file() else None)
    if kind == "audio":
        path = svc.resolve_audio(ref.get("audio"))
        a = svc.load_audio(path)
        z = svc.encode_cached(a)[0].numpy()
        return z, None, (lambda: (a, SRV.SR))
    raise ForgeError(400, f"unknown latent ref kind {kind!r}")


def _stats(body):
    refs_in = body.get("latents") or []
    if not isinstance(refs_in, list) or not refs_in:
        raise ForgeError(400, "latents must be a non-empty list")
    features = body.get("features") or []
    max_frames = int(body.get("max_frames", 20000))
    max_points = int(body.get("max_points", 2000))
    entries = [_latent_entry(r) for r in refs_in]
    n, xc = stats.xcorr_payload([e[0] for e in entries], max_frames=max_frames)
    available = set(stats.LIBROSA_FEATURES)
    series = []
    for i, (z, npz, audio_fn) in enumerate(entries):
        ts = {}
        if npz is not None:
            with np.load(npz) as d:
                ts = {k: d[k] for k in d.files if k.endswith("_ts") and d[k].ndim == 1}
            available.update(ts)
        cached_audio = None
        for f in features:
            T = z.shape[1]
            if f in ts:
                vals = stats._fit(ts[f], T)
            elif f in stats.LIBROSA_FEATURES and audio_fn is not None:
                if cached_audio is None:
                    cached_audio = audio_fn()
                vals = stats.audio_feature(cached_audio[0], cached_audio[1], f, T)
            else:
                vals = [None] * T
            series.append({"index": i, "feature": f, "fps": contract.FPS,
                           "values": stats.resample_points(list(vals), max_points)})
    return {"n_frames": n, "xcorr": xc, "timeseries": series, "features_available": sorted(available)}


@router.post("/forge/stats")
@forge_route
async def stats_route(request: Request):
    return ok(**await run_in_threadpool(_stats, await request.json() or {}))


@router.get("/forge/dataset_scalars")
@forge_route
async def dataset_scalars(x: str = "bpm", y: str = "lufs"):
    ld = services().latent_dir()
    if ld is None or not ld.is_dir():
        raise ForgeError(404, "latent_dir not configured or not mounted")
    if _DATASET["dir"] != ld:
        _DATASET["index"] = await run_in_threadpool(stats.DatasetIndex, ld)
        _DATASET["dir"] = ld
    idx = _DATASET["index"]
    return ok(fields=idx.fields(), points=idx.points(x, y))
```

- [ ] **Step 4: Add a route test and run all stats tests**

Append to `eval/tests/test_forge_stats.py`:
```python
def test_stats_route_with_path_latents(monkeypatch, tmp_path):
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    import soundfile as sf
    import explorer_render_server as srv
    import forge_api
    monkeypatch.setattr(srv, "OUT_DIR", tmp_path)
    forge_api.reset_queue()
    rng = np.random.default_rng(0)
    for name in ("a", "b"):
        np.save(tmp_path / f"{name}.z0.npy", rng.standard_normal((256, 40)).astype(np.float16))
        sf.write(tmp_path / f"{name}.wav", np.zeros((4096 * 40, 2), dtype=np.float32), 44100)
    c = fastapi_testclient.TestClient(srv.app)
    r = c.post("/forge/stats", json={"latents": [{"kind": "path", "path": str(tmp_path / "a.z0.npy")},
                                                 {"kind": "path", "path": str(tmp_path / "b.z0.npy")}],
                                     "features": ["rms"], "max_points": 10})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["n_frames"] == 80 and body["xcorr"]["shape"] == [256, 256]
    assert [s["index"] for s in body["timeseries"]] == [0, 1]
    assert len(body["timeseries"][0]["values"]) == 10
    assert c.post("/forge/stats", json={"latents": []}).status_code == 400
```

Run: `$PY -m pytest eval/tests/test_forge_stats.py -q`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add eval/forge/stats.py eval/forge_api.py eval/tests/test_forge_stats.py
Misc/agent_commit.sh WINTERMUTE -m "forge: statistics (xcorr, time series) and dataset scalar index"
```

---

### Task 14: Backbone switching

**Files:**
- Create: `eval/forge/backbone.py`, `eval/tests/test_forge_backbone.py`
- Modify: `eval/forge_api.py` (append `GET|POST /forge/backbone`)

**Interfaces:**
- Produces: `backbone.BACKBONES` (ordered ids → fallback objective), `backbone.hub_dir() -> Path`, `backbone.cached_config(id, hub=None) -> Path|None`, `backbone.objective_of(id, hub=None) -> str`, `backbone.listing(hub=None) -> list[{"id","objective","cached"}]`.

- [ ] **Step 1: Write the failing test**

```python
import json

import pytest

import forge_testutil  # noqa: F401
from forge import backbone


def make_hub(tmp_path, model_id, objective):
    d = tmp_path / f"models--stabilityai--stable-audio-3-{model_id}" / "snapshots" / "abc"
    d.mkdir(parents=True)
    (d / "model_config.json").write_text(json.dumps({"model": {"diffusion": {"diffusion_objective": objective}}}))


def test_listing_from_hub(tmp_path):
    make_hub(tmp_path, "medium", "rf_denoiser")
    rows = backbone.listing(tmp_path)
    assert [r["id"] for r in rows] == ["medium", "medium-base", "small-music", "small-music-base"]
    assert rows[0] == {"id": "medium", "objective": "rf_denoiser", "cached": True}
    assert rows[1] == {"id": "medium-base", "objective": "rectified_flow", "cached": False}


def test_hub_dir_env(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    assert backbone.hub_dir() == tmp_path


def test_routes(monkeypatch, tmp_path):
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    import explorer_render_server as srv
    import forge_api
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    make_hub(tmp_path, "medium-base", "rectified_flow")
    monkeypatch.setattr(srv, "OUT_DIR", tmp_path)
    forge_api.reset_queue()
    c = fastapi_testclient.TestClient(srv.app)
    body = c.get("/forge/backbone").json()
    assert body["ok"] and [r["id"] for r in body["available"]][0] == "medium"
    assert c.post("/forge/backbone", json={"id": "large"}).status_code == 400
    r = c.post("/forge/backbone", json={"id": "medium"})
    assert r.status_code == 400 and "local HF cache" in r.json()["error"]
    srv.GPU_LOCK.acquire()
    try:
        assert c.post("/forge/backbone", json={"id": "medium-base"}).status_code == 409
    finally:
        srv.GPU_LOCK.release()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest eval/tests/test_forge_backbone.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`eval/forge/backbone.py`:
```python
"""SA3 backbones the forge can switch between (spec §5.3 MODEL STAGE, §6.4)."""
import json
import os
from pathlib import Path

BACKBONES = {"medium": "rf_denoiser", "medium-base": "rectified_flow",
             "small-music": "rf_denoiser", "small-music-base": "rectified_flow"}


def hub_dir() -> Path:
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"])
    if os.environ.get("HF_HOME"):
        return Path(os.environ["HF_HOME"]) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def cached_config(model_id, hub=None):
    snaps = Path(hub or hub_dir()) / f"models--stabilityai--stable-audio-3-{model_id}" / "snapshots"
    hits = sorted(snaps.glob("*/model_config.json")) if snaps.is_dir() else []
    return hits[0] if hits else None


def _find(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _find(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find(v, key)
            if found is not None:
                return found
    return None


def objective_of(model_id, hub=None) -> str:
    cfg = cached_config(model_id, hub)
    if cfg is not None:
        try:
            found = _find(json.loads(cfg.read_text()), "diffusion_objective")
            if found:
                return str(found)
        except (OSError, ValueError):
            pass
    return BACKBONES[model_id]


def listing(hub=None):
    return [{"id": i, "objective": objective_of(i, hub), "cached": cached_config(i, hub) is not None}
            for i in BACKBONES]
```

Append to `eval/forge_api.py`:
```python
import gc
import time as _time

from forge import backbone


def _active_backbone():
    return getattr(SRV.ARGS, "model", None)


@router.get("/forge/backbone")
@forge_route
async def backbone_get():
    active = _active_backbone()
    objective = getattr(getattr(SRV.MODEL, "model", None), "diffusion_objective", None)
    if objective is None and active in backbone.BACKBONES:
        objective = backbone.objective_of(active)
    return ok(active=active, objective=objective, available=backbone.listing())


def _switch_backbone(model_id):
    srv = SRV
    previous = srv.ARGS.model
    before = len(srv.SLOTS.slots)
    t0 = _time.time()
    warnings = []
    with srv.GPU_LOCK:
        srv.ARGS.model = model_id
        srv.MODEL = None
        gc.collect()
        srv.prepare_model(None, None)
        ds = srv.MODEL.model.pretransform.downsampling_ratio
        if ds != srv.DS or srv.MODEL.model.sample_rate != srv.SR:
            srv.ARGS.model = previous
            srv.MODEL = None
            gc.collect()
            srv.prepare_model(None, None)
            raise ForgeError(400, f"backbone {model_id} has a different latent rate (ds={ds}); restored {previous}")
    after = len(srv.SLOTS.slots)
    if after < before:
        warnings.append(f"{before - after} resident adapter slot(s) could not be re-applied on {model_id}")
    srv.log(f"[forge] backbone {previous} -> {model_id} in {_time.time() - t0:.1f}s")
    return {"active": model_id, "objective": srv.MODEL.model.diffusion_objective,
            "rebuild_sec": round(_time.time() - t0, 1), "warnings": warnings}


@router.post("/forge/backbone")
@forge_route
async def backbone_post(request: Request):
    body = await request.json() or {}
    model_id = body.get("id")
    if model_id not in backbone.BACKBONES:
        raise ForgeError(400, f"unknown backbone {model_id!r} (have {', '.join(backbone.BACKBONES)})")
    if SRV.GPU_LOCK.locked():
        raise ForgeError(409, "a pass is running — try again when the GPU is idle")
    if backbone.cached_config(model_id) is None:
        raise ForgeError(400, f"{model_id} is not in the local HF cache — download it first")
    if SRV.ARGS is None:
        raise ForgeError(409, "model not loaded yet")
    return ok(**await run_in_threadpool(_switch_backbone, model_id))
```

- [ ] **Step 4: Run tests**

Run: `$PY -m pytest eval/tests/test_forge_backbone.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add eval/forge/backbone.py eval/forge_api.py eval/tests/test_forge_backbone.py
Misc/agent_commit.sh WINTERMUTE -m "forge: backbone listing and switching (POST/BASE)"
```

---

### Task 15: Live verification and contract fixtures (GPU)

**Files:**
- Create: `eval/forge/record_fixtures.py`, `eval/tests/test_forge_fixtures.py`, `docs/latent-forge/contract/fixtures/*.json` (generated)

**Interfaces:**
- Produces: `record_fixtures.redact(obj) -> obj`; fixture files named below, consumed by every client plan's mock server.

- [ ] **Step 1: Write the failing test**

```python
import forge_testutil  # noqa: F401
from forge.record_fixtures import FIXTURE_DIR, redact


def test_redact_nested():
    obj = {"path": "/home/kim/Projects/sa3_render_out/job/out_00.wav",
           "files": ["/run/media/kim/Mantu/sa3_lora_runs/x.ckpt", "relative.wav"],
           "note": "loaded /home/kim/.cache/huggingface ok", "n": 3}
    assert redact(obj) == {"path": "/SERVER/Projects/sa3_render_out/job/out_00.wav",
                           "files": ["/SERVER/media/Mantu/sa3_lora_runs/x.ckpt", "relative.wav"],
                           "note": "loaded /SERVER/.cache/huggingface ok", "n": 3}


def test_fixture_dir_location():
    assert FIXTURE_DIR.parts[-3:] == ("latent-forge", "contract", "fixtures")


def test_recorded_fixtures_have_no_local_paths():
    if not FIXTURE_DIR.is_dir():
        return
    for p in FIXTURE_DIR.glob("*.json"):
        text = p.read_text()
        assert "/home/kim" not in text and "/run/media/kim" not in text, p.name
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PY -m pytest eval/tests/test_forge_fixtures.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `eval/forge/record_fixtures.py`**

```python
"""Record golden responses from the LIVE forge server for the client mock (spec §11.4).

Run with the dev server up: /home/kim/Projects/SAO/.venv/bin/python eval/forge/record_fixtures.py
Every string is redacted: /home/kim -> /SERVER, /run/media/kim -> /SERVER/media.

All 20 fixtures are REQUIRED. Four of them are recorded only if the live run got
far enough -- analyze and stats need the crops root to list something, chroma and
stretch need the generate job to come back with urls -- so a half-working run used
to write 15 files and exit 0, and four client plans would be told their fixtures
had landed when the ones covering analyze, stats, chroma and stretch had not. This
is a GPU-gated task at the end of the milestone: a silent shortfall costs another
GPU run to discover. main() therefore checks the set and exits non-zero, naming
what is missing.
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8056"
FIXTURE_DIR = Path(__file__).resolve().parents[2] / "docs" / "latent-forge" / "contract" / "fixtures"
_PATTERNS = [(re.compile(r"/run/media/kim"), "/SERVER/media"), (re.compile(r"/home/kim"), "/SERVER")]


def redact(obj):
    if isinstance(obj, str):
        for pat, rep in _PATTERNS:
            obj = pat.sub(rep, obj)
        return obj
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items()}
    return obj


def call(method, path, body=None, timeout=600):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


EXPECTED = (
    "info", "status_idle", "models_adapters", "slots", "schedule_model", "forge_backbone",
    "forge_files_crops", "forge_files_renders", "forge_analyze_crop", "forge_stats_crops",
    "forge_dataset_scalars", "forge_job_submit", "forge_job_running", "status_busy",
    "forge_job_generate_done", "forge_chroma_render", "forge_stretch_render", "forge_log",
    "forge_error_cap", "forge_audio_ref_example",
    "models_control_adapters", "forge_sessions_list", "forge_session_get",
    "forge_presets_latch_list", "forge_preset_latch_get",
)
RECORDED = set()


def save(name, status, body):
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    (FIXTURE_DIR / f"{name}.json").write_text(json.dumps({"status": status, "body": redact(body)}, indent=1) + "\n")
    RECORDED.add(name)
    print(f"  {name}: {status}")


def wait_job(job_id, timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s, b = call("GET", f"/forge/jobs/{job_id}")
        if b and b.get("state") in ("done", "error", "cancelled"):
            return s, b
        time.sleep(1)
    raise SystemExit(f"job {job_id} timed out")


def main():
    q = urllib.parse.quote
    save("info", *call("GET", "/info"))
    save("status_idle", *call("GET", "/status"))
    s, models = call("GET", "/models?family=adapter&loadable=1")
    if isinstance(models, dict) and isinstance(models.get("models"), list):
        models = {**models, "models": models["models"][:20]}
    save("models_adapters", s, models)
    # FiLM checkpoints are family "control_adapter" with control_mode "scalar" -- the only mode
    # the server's _install_film (ScalarAttributeEncoder) can load. There is no "film" family.
    s, ctrl = call("GET", "/models?family=control_adapter")
    if isinstance(ctrl, dict) and isinstance(ctrl.get("models"), list):
        ctrl = {**ctrl, "models": ctrl["models"][:20]}
    save("models_control_adapters", s, ctrl)
    save("slots", *call("GET", "/slots"))
    # Session + preset stores (M7). Round-trip a throwaway name so the GET fixtures are real
    # server bodies (raw object, no {ok} envelope). The preset is deleted afterwards; sessions have
    # no DELETE route, so "_fixture_probe" stays in the store (harmless, and named to say so).
    probe = {"version": 2, "clips": []}
    call("PUT", "/forge/sessions/_fixture_probe", probe)
    save("forge_sessions_list", *call("GET", "/forge/sessions"))
    save("forge_session_get", *call("GET", "/forge/sessions/_fixture_probe"))
    call("PUT", "/forge/presets/latch/_fixture_probe", {"latch_on": False})
    save("forge_presets_latch_list", *call("GET", "/forge/presets/latch"))
    save("forge_preset_latch_get", *call("GET", "/forge/presets/latch/_fixture_probe"))
    call("DELETE", "/forge/presets/latch/_fixture_probe")
    save("schedule_model", *call("POST", "/schedule", {"steps": 24, "duration": 47.0}))
    save("forge_backbone", *call("GET", "/forge/backbone"))
    s, crops = call("GET", "/forge/files?root=crops&limit=5")
    save("forge_files_crops", s, crops)
    save("forge_files_renders", *call("GET", "/forge/files?root=renders&limit=5"))
    crop_refs = [f["ref"] for f in (crops or {}).get("files", [])[:2]]
    if crop_refs:
        save("forge_analyze_crop", *call("POST", "/forge/analyze", {"audio": crop_refs[0]}))
        save("forge_stats_crops", *call("POST", "/forge/stats", {"latents": crop_refs,
                                                                   "features": ["rms", "onset_envelope_ts"],
                                                                   "max_points": 400}))
    save("forge_dataset_scalars", *call("GET", "/forge/dataset_scalars?x=bpm&y=lufs"))
    s, sub = call("POST", "/forge/jobs", {"op": "generate", "payload": {
        "prompt": "hypnotic melodic goa trance, rolling bassline", "duration": 10.0, "steps": 8, "seed": 1234}})
    save("forge_job_submit", s, sub)
    time.sleep(2)
    save("forge_job_running", *call("GET", f"/forge/jobs/{sub['job_id']}"))
    save("status_busy", *call("GET", "/status"))
    s, done = wait_job(sub["job_id"])
    save("forge_job_generate_done", s, done)
    res = done.get("result") or {}
    if res.get("urls"):
        ref = {"kind": "render", "job_id": res["job_id"], "file": res["urls"][0].split("/")[-1]}
        save("forge_chroma_render", *call("POST", "/forge/chroma", {"audio": ref}))
        save("forge_stretch_render", *call("POST", "/forge/stretch", {"audio": ref, "speed": 1.05, "semitones": -2}))
    save("forge_log", *call("GET", "/forge/log?since=0"))
    save("forge_error_cap", *call("POST", "/forge/jobs", {"op": "generate", "payload": {"prompt": "x", "duration": 400}}))
    save("forge_audio_ref_example", 200, {"url": "/forge/audio?ref=" + q(json.dumps({"kind": "crop", "crop_id": "000000"}))})
    missing = [n for n in EXPECTED if n not in RECORDED]
    if missing:
        print(f"\nINCOMPLETE: {len(RECORDED)}/{len(EXPECTED)} fixtures recorded.")
        print("  missing: " + ", ".join(missing))
        print("  analyze/stats need a non-empty crops root; chroma/stretch need the generate")
        print("  job to return urls. Fix the cause and re-run -- do NOT ship a partial set.")
        return 1
    print(f"\nall {len(EXPECTED)} fixtures recorded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the unit test**

Run: `$PY -m pytest eval/tests/test_forge_fixtures.py -q`
Expected: 3 passed (the third passes vacuously before recording).

- [ ] **Step 5: Full forge test suite**

Run: `$PY -m pytest eval/tests/test_forge_*.py eval/tests/test_render_server_ab.py eval/tests/test_render_server_slots_api.py -q`
Expected: all passed.

- [ ] **Step 6: Live server — start, exercise, record**

```bash
cd /home/kim/Projects/SAO && Misc/gpu_guard.sh who WINTERMUTE
cd /home/kim/Projects/sa3-studio-review
eval/forge/dev_server.sh stop || true
eval/forge/dev_server.sh start
curl -s localhost:8056/info | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['model'], d['objective'])"
$PY eval/forge/record_fixtures.py
```
Expected: `medium-base rectified_flow`, then one line per fixture, ending with `all 20 fixtures recorded` and exit 0. `forge_job_generate_done` must show status 200 and `"state": "done"`; `forge_error_cap` status 400. **If it prints `INCOMPLETE` and exits 1, stop** — the named fixtures were skipped because the crops root listed nothing or the generate job returned no urls, and the client plans depend on all of them.

Backbone round trip (only if `medium` shows `cached: true` in `forge_backbone.json`):
```bash
curl -s -X POST localhost:8056/forge/backbone -H 'Content-Type: application/json' -d '{"id":"medium"}'
curl -s localhost:8056/info | python3 -c "import json,sys; print(json.load(sys.stdin)['objective'])"
curl -s -X POST localhost:8056/forge/backbone -H 'Content-Type: application/json' -d '{"id":"medium-base"}'
curl -s localhost:8056/info | python3 -c "import json,sys; print(json.load(sys.stdin)['objective'])"
```
Expected: `"active": "medium"` … `rf_denoiser`, then `"active": "medium-base"` … `rectified_flow`.

- [ ] **Step 7: Leak scan, re-run fixture test, commit**

```bash
grep -rn -e '/home/kim' -e '/run/media/kim' docs/latent-forge/contract/fixtures && echo "LEAK — fix redact() before committing" || echo "clean"
$PY -m pytest eval/tests/test_forge_fixtures.py -q
git add eval/forge/record_fixtures.py eval/tests/test_forge_fixtures.py docs/latent-forge/contract/fixtures
Misc/agent_commit.sh WINTERMUTE -m "forge: recorded, redacted contract fixtures from the live server"
```
Expected: `clean`, 3 passed.

- [ ] **Step 8: Hand the GPU back**

If nothing else needs the forge server right now: `eval/forge/dev_server.sh stop`. Then check `cd /home/kim/Projects/SAO && Misc/gpu_guard.sh who WINTERMUTE` shows no WINTERMUTE holder.
