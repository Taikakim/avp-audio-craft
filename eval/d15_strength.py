#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""d15_strength.py -- EXPERIMENTS D15: how do text CFG and note strength trade off on the pianoroll fine-tune? It plays invented melodies at cfg 7 with the stream at 1.0. This maps the range, so the ear has a grid and a future control has a default.

Grid: cfg {3, 5, 7, 10} x note strength {0.5, 1, 1.5, 2} (the fed roll multiplied, CFG on the stream), 6 prompts x 2 invented melodies, plus a no-stream clip per prompt and cfg. Melodies and scoring as eval/d15_new_melodies.py; the gate compares each clip with the no-stream clip of its prompt and cfg.
Outputs: ~/evals_aac/control_runs/pianoroll_strength_goa_t256_step2688_20261103/. RUN: eval/run_d15_strength.sh
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
OUT = Path("/home/kim/evals_aac/control_runs/pianoroll_strength_goa_t256_step2688_20261103")
CFGS = (3.0, 5.0, 7.0, 10.0)
STRENGTHS = (0.5, 1.0, 1.5, 2.0)
N_PROMPTS = 6
PER_PROMPT = 2


def plan():
    pr = list(json.loads(Y.PROMPTS.read_text()).values())
    out = []
    for p in range(N_PROMPTS):
        for cfg in CFGS:
            out.append(dict(id=f"p{p}__cfg{cfg:g}__zero", kind="zero", p=p, prompt=pr[p % len(pr)], seed=7000 + p, cfg=cfg, strength=0.0))
            for i in range(PER_PROMPT):
                m = p * PER_PROMPT + i
                for s in STRENGTHS:
                    out.append(dict(id=f"p{p}__m{m}__cfg{cfg:g}__s{s:g}", kind="new", p=p, melody=m, other=(m + 5) % (N_PROMPTS * PER_PROMPT), prompt=pr[p % len(pr)], seed=7000 + p, cfg=cfg, strength=s))
    return out


def render():
    import torch
    from sa3_control.audio_io import save_audio

    OUT.mkdir(parents=True, exist_ok=True)
    cells = plan()
    log = OUT / "cells.jsonl"
    done = {json.loads(l)["id"] for l in log.read_text().splitlines()} if log.exists() else set()
    sam = Y.load_fullft(D.RUN / D.CKPT, "cuda:0", 128)
    sam.model.model.model.modular_cfg_null = True
    with log.open("a") as f, torch.no_grad():
        for c in cells:
            if c["id"] in done:
                continue
            st = np.zeros((128, D.T), dtype=np.float32) if c["kind"] == "zero" else D.roll_of_line(D.melody(c["melody"])) * c["strength"]
            x = sam.generate(conditioning=[{"prompt": c["prompt"], "seconds_total": X.DUR, "mir_ctrl": st}], sample_size=D.T * 4096, duration_padding_sec=0.0, steps=24, cfg_scale=c["cfg"], seed=c["seed"], batch_size=1).float().cpu()
            if not bool(torch.isfinite(x).all()) or float(x.std()) < 1e-3:
                print("FAULT", c["id"], flush=True)
                continue
            tmp = OUT / "_t.wav"
            save_audio(str(tmp), x[0][:, : int(X.DUR * 44100)], 44100, normalize=True)
            subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(tmp), "-c:a", "aac", "-b:a", "192k", str(OUT / f"{c['id']}.m4a")], check=True)
            tmp.replace(OUT / f"{c['id']}.wav")
            f.write(json.dumps({**c, "std": round(float(x.std()), 4)}) + "\n")
            f.flush()


def score():
    from e24_build_contour_packs import skyline
    from muscriptor import TranscriptionModel

    cells = [json.loads(l) for l in (OUT / "cells.jsonl").read_text().splitlines()]
    midd = OUT / "midi"
    midd.mkdir(exist_ok=True)
    model = None
    if any(not (midd / f"{c['id']}.mid").exists() for c in cells):
        model = TranscriptionModel.load_model("medium", device="cuda")
    rows = []
    for c in cells:
        p = midd / f"{c['id']}.mid"
        if not p.exists():
            p.write_bytes(model.transcribe_to_midi(OUT / f"{c['id']}.wav"))
        roll, top = Y.roll_of(p), skyline(str(p))[:D.T]
        r = dict(c)
        if c["kind"] == "new":
            m, o = D.melody(c["melody"]), D.melody(c["other"])
            r.update(recall=D.any_on_line(roll, m), recall_other=D.any_on_line(roll, o), top=D.on_line(top, m), top_other=D.on_line(top, o))
        rows.append(r)
    (OUT / "scores.json").write_text(json.dumps(rows, indent=0))


def gate_stage():
    import sqlite3

    from control_head_disintegration_eval import DB, gate

    db = sqlite3.connect(DB)
    cols = [r[1] for r in db.execute("PRAGMA table_info(metrics)").fetchall()]
    met = {r[0]: dict(zip(cols, r)) for r in db.execute("select * from metrics where path like ?", (f"{OUT}/%",))}
    rows = json.loads((OUT / "scores.json").read_text())
    g = defaultdict(lambda: dict(n=0, fails=0, why=Counter(), recall=[], top=[], other=[], ce=[], pq=[]))
    for r in rows:
        if r["kind"] != "new":
            continue
        k = (r["cfg"], r["strength"])
        e = g[k]
        e["recall"].append(r["recall"])
        e["top"].append(r["top"])
        e["other"].append(r["recall_other"])
        m, b = met.get(str(OUT / f"{r['id']}.m4a")), met.get(str(OUT / f"p{r['p']}__cfg{r['cfg']:g}__zero.m4a"))
        if not m or not b:
            continue
        bad, why, _ = gate(m, b, rhythmic=True)
        e["n"] += 1
        e["fails"] += int(bad)
        e["why"].update(x.split("(")[0] for x in why)
        if m.get("ce") is not None:
            e["ce"].append(m["ce"])
        if m.get("pq") is not None:
            e["pq"].append(m["pq"])
    zr = defaultdict(lambda: dict(ce=[], pq=[]))
    for r in rows:
        if r["kind"] == "zero":
            m = met.get(str(OUT / f"{r['id']}.m4a"))
            if m and m.get("ce") is not None:
                zr[r["cfg"]]["ce"].append(m["ce"])
                zr[r["cfg"]]["pq"].append(m["pq"])
    L = ["Fed pitch sounds / top line on it / another melody sounds; gate fails; CE, PQ. Invented melodies, 12 per cell. Measured, not heard."]
    table = []
    for cfg in CFGS:
        z = zr[cfg]
        L.append(f"cfg {cfg:g} (no stream: CE {np.mean(z['ce']):.2f}, PQ {np.mean(z['pq']):.2f})")
        for s in STRENGTHS:
            e = g[(cfg, s)]
            row = dict(cfg=cfg, strength=s, recall=float(np.mean(e["recall"])), top=float(np.mean(e["top"])), other=float(np.mean(e["other"])), fails=e["fails"], n=e["n"], why=dict(e["why"]), ce=float(np.mean(e["ce"])) if e["ce"] else None, pq=float(np.mean(e["pq"])) if e["pq"] else None)
            table.append(row)
            L.append(f"  x{s:g}: {row['recall']:.0%} / {row['top']:.0%} / {row['other']:.0%}; {row['fails']}/{row['n']} {row['why'] or ''}; CE {row['ce']:.2f}, PQ {row['pq']:.2f}")
    (OUT / "grid.json").write_text(json.dumps(table, indent=0))
    (OUT / "report.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("render", "score", "gate"), required=True)
    a = ap.parse_args()
    {"render": render, "score": score, "gate": gate_stage}[a.stage]()
