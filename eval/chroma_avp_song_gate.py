#!/usr/bin/env python3
# Owner: THE-FINN (created 2026-11-04)
"""chroma_avp_song_gate.py -- first steering check of the leak-free AVP chroma head, on the model
a release would actually ship: medium-base + Kim's AVP DoRA (dora128adj_avp_aug10_lr1e4 ep74).

Reuses chroma_avp_matrix_render.py (grid, targets, guided baseline at gain 0, checked decode, meters)
with its heads, adapter and output swapped. goa_e13 is the private reference, there to say how much
steering is available on this adapter; it is never a release candidate. ep10 and ep20 are both run
because val loss has not predicted which epoch steers best (E13: ep10 won there, val best is ep20 here).

    render:  .venv/bin/python eval/chroma_avp_song_gate.py
    report:  .venv/bin/python eval/chroma_avp_song_gate.py --report

The report needs no GPU: lift against the same-prompt, same-seed gain-0 clip, target specificity
(the fed target against the other targets on the same clip), and the disintegration screen.
It screens; it does not hear. Output: <OUT>/report.json and printed table.
"""
import json
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chroma_avp_matrix_render as M  # noqa: E402

SONG = Path("/run/media/kim/Mantu/latch_sweep/chroma_retrain_avp_songsplit_20261030/C3_avp_song")
M.OUT = Path("/run/media/kim/Mantu/sa3_control_runs/__chroma/chroma_avp_song_gate_20261104")
M.AAC_DIR = Path("/home/kim/evals_aac/chroma_avp_song_gate")
M.DORA_FT = Path("/run/media/kim/Mantu/sa3_lora_runs/__finetunes/dora128adj_avp_aug10_lr1e4/epoch=74-step=3000.ckpt")
M.HEADS = {
    "goa_e13": M.HEADS["goa_e13"],
    "avp_song_ep10": SONG / "latch_sa3_same_chroma_ep10.pt",
    "avp_song_ep20": SONG / "latch_sa3_same_chroma_ep20.pt",
}
# Grid targets go through --targets: the gain-0 baselines still need "C" in M.TARGET_IDS (main looks it up by name).
TARGETS = "Am,i-VI-III-VII,keylift"
M.GAINS = [512, 2048, 8192]


def report():
    import soundfile as sf
    from disintegration_metrics import gate, measure
    rows = [json.loads(l) for l in (M.OUT / "cells.jsonl").read_text().splitlines() if l.strip()]

    n_frames = int(round(M.DURATION_SEC * M.FPS))

    def stats(fn):
        """(disintegration stats, fcos of this clip against every target), both from the staged AAC."""
        with tempfile.TemporaryDirectory() as d:
            w = Path(d) / "c.wav"
            subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(M.AAC_DIR / fn),
                            "-ar", str(M.sc.SAME_SR), "-ac", "2", str(w)], check=True)
            y, _ = sf.read(w, always_2d=True)
            return measure(w), M.measure(y.T, None, n_frames)

    base = {(r["prompt_id"], r["seed"]): r for r in rows if r["gain"] == 0}
    base_stats = {k: stats(r["fn"]) for k, r in base.items()}
    agg = defaultdict(list)
    for r in rows:
        if r["gain"] == 0:
            continue
        k = (r["prompt_id"], r["seed"])
        st, all_m = stats(r["fn"])
        g = gate(st, base_stats[k][0])
        others = [all_m[t]["mid"]["fcos"] for t in all_m if t != r["target"]]
        b = base[k]["measured_all"][r["target"]]["mid"]
        r2 = dict(lift_fcos=all_m[r["target"]]["mid"]["fcos"] - b["fcos"], lift_hit=all_m[r["target"]]["mid"]["hit"] - b["hit"],
                  spec=all_m[r["target"]]["mid"]["fcos"] - sum(others) / len(others), blown=g["blown"],
                  reasons=g["reasons"], z_ratio=r["z_std"] / base[k]["z_std"], fn=r["fn"])
        agg[(r["head"], r["gain"])].append(r2)
    out = {}
    print(f"{'head':16}{'gain':>6}{'n':>4}{'lift_fcos':>11}{'lift_hit':>10}{'specific':>10}{'blown':>7}{'z_ratio':>9}")
    for k in sorted(agg):
        v = agg[k]
        mean = lambda m: sum(x[m] for x in v) / len(v)
        out[f"{k[0]}@{k[1]}"] = dict(n=len(v), lift_fcos=mean("lift_fcos"), lift_hit=mean("lift_hit"), specific=mean("spec"),
                                     blown=sum(x["blown"] for x in v), z_ratio=mean("z_ratio"),
                                     blown_clips=[(x["fn"], x["reasons"]) for x in v if x["blown"]])
        o = out[f"{k[0]}@{k[1]}"]
        print(f"{k[0]:16}{k[1]:>6}{len(v):>4}{o['lift_fcos']:>+11.3f}{o['lift_hit']:>+10.3f}{o['specific']:>+10.3f}{o['blown']:>7}{o['z_ratio']:>9.3f}")
    (M.OUT / "report.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    if "--report" in sys.argv:
        report()
    else:
        sys.argv += ["--targets", TARGETS]
        M.main()
