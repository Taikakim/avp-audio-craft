#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""d15_checks.py -- EXPERIMENTS D15: three cheap checks on "the pianoroll fine-tune plays invented melodies", same 36 melodies and prompts as eval/d15_new_melodies.py, cfg 7.
  both     the stream in both CFG branches, the old way, same seeds: how much of the generalisation is down to the fix?
  seed2    CFG on the stream, other render seeds: is it one lucky seed set?
  ema      CFG on the stream, the run's EMA weights (under one half-life, so mostly the starting point): does the shadow play notes at all?
  s2       CFG on the stream, the run's second training seed, online weights: is it this checkpoint only?
  zero     no stream, per prompt, for each model and seed set, as the chance level and the gate baseline.
Scoring as d15_new_melodies.py. Outputs: ~/evals_aac/control_runs/pianoroll_checks_goa_t256_20261103/. RUN: eval/run_d15_checks.sh
"""
import argparse
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

for k, v in {"FLASH_ATTENTION_TRITON_AMD_ENABLE": "FALSE", "PYTORCH_TUNABLEOP_ENABLED": "0", "MIOPEN_FIND_MODE": "2"}.items():
    os.environ.setdefault(k, v)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np
import d15_new_melodies as D

X, Y = D.X, D.Y
OUT = Path("/home/kim/evals_aac/control_runs/pianoroll_checks_goa_t256_20261103")
S2 = D.RUN.parent / "proll_fullft_t256_bf16_s2"
# arm: (checkpoint dir, weights prefix, CFG on the stream, seed offset, baseline group)
ARMS = {"both": (D.RUN, "diffusion.model.", False, 0, "online"), "seed2": (D.RUN, "diffusion.model.", True, 100, "online2"), "ema": (D.RUN, "diffusion_ema.ema_model.", True, 0, "ema"), "s2": (S2, "diffusion.model.", True, 0, "s2")}
ZERO = {"online": (D.RUN, "diffusion.model.", 0), "online2": (D.RUN, "diffusion.model.", 100), "ema": (D.RUN, "diffusion_ema.ema_model.", 0), "s2": (S2, "diffusion.model.", 0)}


def ckpt_in(d):
    return sorted(d.glob("epoch=*.ckpt"))[-1]


def load(run, prefix):
    import torch
    from mir_control import MirCtrlConditioner, install_mir_control
    from stable_audio_3 import StableAudioModel

    ck = ckpt_in(run)
    sam = StableAudioModel.from_pretrained("medium-base", device="cuda:0")
    tgt = sam.model.model
    install_mir_control(sam.model, tgt.model.transformer, n_channels=128, blocks="12-23")
    sam.model.conditioner.conditioners["mir_ctrl"] = MirCtrlConditioner(n_channels=128, dropout_prob=0.0)
    raw = torch.load(ck, map_location="cpu", weights_only=False)["state_dict"]
    dt = next(tgt.parameters()).dtype
    keys = set(tgt.state_dict())
    sd = {k[len(prefix):]: v.to(dt) for k, v in raw.items() if k.startswith(prefix) and k[len(prefix):] in keys}
    missing, _ = tgt.load_state_dict(sd, strict=False)
    cov = 1 - len(missing) / max(1, len(keys))
    print(f"loaded {run.name}/{ck.name} {prefix}: {len(sd)} tensors, coverage {cov:.1%}, mir_ctrl {sum('mir_ctrl' in k for k in sd)}", flush=True)
    assert cov > 0.99 and sum("mir_ctrl" in k for k in sd) == 48, missing[:3]
    csd = {k[len("diffusion.conditioner."):]: v for k, v in raw.items() if k.startswith("diffusion.conditioner.")}
    if csd:
        sam.model.conditioner.load_state_dict(csd, strict=False)
    return sam


def plan():
    base = [c for c in D.plan() if c["kind"] == "new"]
    zero = {c["p"]: c for c in D.plan() if c["kind"] == "zero"}
    out = []
    for g, (_, _, off) in ZERO.items():
        for p, c in zero.items():
            out.append(dict(id=f"{g}__p{p}__zero", kind="zero", arm="zero", group=g, p=p, prompt=c["prompt"], seed=c["seed"] + off))
    for arm, (_, _, _, off, g) in ARMS.items():
        for c in base:
            out.append(dict(id=f"{arm}__p{c['p']}__m{c['melody']}", kind="new", arm=arm, group=g, p=c["p"], melody=c["melody"], other=c["other"], prompt=c["prompt"], seed=c["seed"] + off))
    return out


def model_key(c):
    if c["kind"] == "zero":
        r, pfx, _ = ZERO[c["group"]]
    else:
        r, pfx, _, _, _ = ARMS[c["arm"]]
    return str(r), pfx


def render():
    import torch
    from sa3_control.audio_io import save_audio

    OUT.mkdir(parents=True, exist_ok=True)
    cells = plan()
    log = OUT / "cells.jsonl"
    done = {json.loads(l)["id"] for l in log.read_text().splitlines()} if log.exists() else set()
    by = defaultdict(list)
    for c in cells:
        if c["id"] not in done:
            by[model_key(c)].append(c)
    with log.open("a") as f, torch.no_grad():
        for (run, pfx), todo in by.items():
            sam = load(Path(run), pfx)
            dit = sam.model.model.model
            for c in todo:
                dit.modular_cfg_null = c["arm"] != "both"
                st = np.zeros((128, D.T), dtype=np.float32) if c["kind"] == "zero" else D.roll_of_line(D.melody(c["melody"]))
                x = sam.generate(conditioning=[{"prompt": c["prompt"], "seconds_total": X.DUR, "mir_ctrl": st}], sample_size=D.T * 4096, duration_padding_sec=0.0, steps=24, cfg_scale=7.0, seed=c["seed"], batch_size=1).float().cpu()
                if not bool(torch.isfinite(x).all()) or float(x.std()) < 1e-3:
                    print("FAULT", c["id"], flush=True)
                    continue
                tmp = OUT / "_t.wav"
                save_audio(str(tmp), x[0][:, : int(X.DUR * 44100)], 44100, normalize=True)
                subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(tmp), "-c:a", "aac", "-b:a", "192k", str(OUT / f"{c['id']}.m4a")], check=True)
                tmp.replace(OUT / f"{c['id']}.wav")
                f.write(json.dumps({**c, "std": round(float(x.std()), 4)}) + "\n")
                f.flush()
            del sam
            torch.cuda.empty_cache()


def score():
    from e24_build_contour_packs import skyline
    from muscriptor import TranscriptionModel

    cells = [json.loads(l) for l in (OUT / "cells.jsonl").read_text().splitlines()]
    midd = OUT / "midi"
    midd.mkdir(exist_ok=True)
    model = None
    if any(not (midd / f"{c['id']}.mid").exists() for c in cells):
        model = TranscriptionModel.load_model("medium", device="cuda")
    all_cells = plan()
    rows = []
    for c in cells:
        p = midd / f"{c['id']}.mid"
        if not p.exists():
            p.write_bytes(model.transcribe_to_midi(OUT / f"{c['id']}.wav"))
        roll, top = Y.roll_of(p), skyline(str(p))[:D.T]
        r = dict(c)
        if c["kind"] == "new":
            m, o = D.melody(c["melody"]), D.melody(c["other"])
            r.update(recall=D.any_on_line(roll, m), top=D.on_line(top, m), recall_other=D.any_on_line(roll, o), top_other=D.on_line(top, o))
        else:
            ms = [D.melody(k["melody"]) for k in all_cells if k["kind"] == "new" and k["p"] == c["p"] and k["arm"] == "seed2"]
            r.update(recall=float(np.mean([D.any_on_line(roll, m) for m in ms])), top=float(np.mean([D.on_line(top, m) for m in ms])))
        rows.append(r)
    (OUT / "scores.json").write_text(json.dumps(rows, indent=0))


def gate_stage():
    import sqlite3

    from control_head_disintegration_eval import DB, gate

    db = sqlite3.connect(DB)
    cols = [r[1] for r in db.execute("PRAGMA table_info(metrics)").fetchall()]
    met = {r[0]: dict(zip(cols, r)) for r in db.execute("select * from metrics where path like ?", (f"{OUT}/%",))}
    rows = json.loads((OUT / "scores.json").read_text())
    rng = np.random.default_rng(1)

    def ci(d):
        d = np.asarray(d)
        b = [rng.choice(d, d.size).mean() for _ in range(4000)]
        return f"{d.mean():+.3f} [{np.percentile(b, 2.5):+.3f}, {np.percentile(b, 97.5):+.3f}] {int((d > 0).sum())}/{d.size}"

    L = ["Same 36 invented melodies, cfg 7. Fed pitch sounds anywhere, top line on it, measured by MuScriptor, not heard. Reference run with CFG on the stream, online weights, first seeds: 73%, 67%, gate 2/36."]
    for arm in ARMS:
        s = [r for r in rows if r["arm"] == arm]
        g = ARMS[arm][4]
        z = [r for r in rows if r["kind"] == "zero" and r["group"] == g]
        why, fails, n, ce, pq = Counter(), 0, 0, [], []
        for r in s:
            m, b = met.get(str(OUT / f"{r['id']}.m4a")), met.get(str(OUT / f"{g}__p{r['p']}__zero.m4a"))
            if m and b:
                bad, w, _ = gate(m, b, rhythmic=True)
                n += 1
                fails += int(bad)
                why.update(x.split("(")[0] for x in w)
                ce.append(m.get("ce") or np.nan)
                pq.append(m.get("pq") or np.nan)
        L.append(f"{arm}: n {len(s)}; sounds {np.mean([r['recall'] for r in s]):.1%}, top {np.mean([r['top'] for r in s]):.1%}; no stream {np.mean([r['recall'] for r in z]):.1%}, {np.mean([r['top'] for r in z]):.1%}; fed minus other, sounds {ci([r['recall'] - r['recall_other'] for r in s])}; gate {fails}/{n} {dict(why)}; CE {np.nanmean(ce):.2f}, PQ {np.nanmean(pq):.2f}")
    (OUT / "report.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("render", "score", "gate"), required=True)
    a = ap.parse_args()
    {"render": render, "score": score, "gate": gate_stage}[a.stage]()
