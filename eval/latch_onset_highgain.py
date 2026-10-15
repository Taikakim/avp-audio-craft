#!/usr/bin/env python3
# Owner: filed from Kim's 2026-10-15 ask (Claude Sonnet 5.5 session; handle not asserted)
"""latch_onset_highgain.py -- extend the onset-LatCH matrix UPWARD in gain: target density 7, gains 4608..8192 step 512.

WHY (Kim, 2026-10-15, after listening to latch_onset_matrix_ema.html): measured onset density barely changes with
gain; only >=2048 moves anything, and then it pulls the WHOLE clip somewhere new. Proposed: at requested density 7,
raise gain in steps of 512 from 4096 (the matrix's top) to 8192, original seed. 4096 already exists in the matrix,
so this renders 4608..8192 (8 gains) x {ema, online} x seed 1234 = 16 clips (~5 s each once the model is loaded).
READ-OUT NOTE: in the matrix the response saturates at ~9 on/s for every target >= 7 at EVERY gain (gain 128 already
gives 8.15 at target 7; 4096 gives 8.6), and the unguided seed-1234 clip is 7.3 -- so "does density rise with gain at
target 7" has little headroom. The informative axis at high gain is the DOWNWARD one (target 0: 6.0 at g128 -> 2.9 at
g4096, EMA) and drift of the clip, hence --targets to add 3 (and 0) for the same gains.

Thin wrapper: reuses eval/latch_onset_matrix_ema.py (same prompt/cfg/steps/sampler/alpha schedule/window; ids and
cells.jsonl format identical, so the page builder can merge it). Writes to a SEPARATE dir; resumable.
RUN (hold the GPU lock first): ROCR_VISIBLE_DEVICES=0 SAO/.venv/bin/python eval/latch_onset_highgain.py [--targets 7,3] [--dry]
"""
import argparse
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import latch_onset_matrix_ema as m  # noqa: E402

HEAD = "/run/media/kim/Mantu2/latch_sweep/modular_2026-09-30/phaseE/E04ema_b32_ep20"
OUT = "/run/media/kim/Mantu2/sa3_control_runs/latch_onset_highgain_20261015"

ap = argparse.ArgumentParser()
ap.add_argument("--targets", default="7", help="comma list of requested onsets/s (default 7)")
ap.add_argument("--seeds", default="1234")
ap.add_argument("--dry", action="store_true")
a = ap.parse_args()

m.OUT = OUT
m.GAINS = tuple(range(4608, 8192 + 1, 512))
m.TARGETS = tuple(int(t) for t in a.targets.split(","))
m.SEEDS = tuple(int(s) for s in a.seeds.split(","))
_orig_cells = m.cells
m.cells = lambda: [c for c in _orig_cells() if c["weights"] != "base"]  # unguided clips already in the matrix dir

# EP-matched EMA/online pair from the same run (the matrix used _best.pt + its epoch's _online.pt)
import torch  # noqa: E402  (cheap, CPU) -- only to read the best epoch
best = f"{HEAD}/latch_sa3_onset_per_beat_ts_best.pt"
ep = torch.load(best, map_location="cpu", weights_only=False)["epoch"]
online = f"{HEAD}/latch_sa3_onset_per_beat_ts_ep{ep}_online.pt"
sys.argv = ["latch_onset_matrix_ema.py", "--ema", best, "--online", online] + (["--dry"] if a.dry else [])
sys.exit(m.main())
