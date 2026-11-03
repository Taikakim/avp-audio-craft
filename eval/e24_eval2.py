#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""e24_eval2.py -- EXPERIMENTS E24, second eval of a trained contour arm. The first (e24_eval.py) was uninformative: one prompt and one seed made every render read as the same held note.

24 crops, each with its own prompt and seed, shared by all of that crop's arms, so a comparison is paired within a crop. Checkpoint given by --run and --step. Arms:
  true       the crop's stream in both CFG branches
  shuffled   the same stream with 8 blocks permuted, both branches
  true_null  the crop's stream, zeros in the uncond branch, so CFG scales the stream as well (dit.py modular_cfg_null)
  shuf_null  the shuffled stream, zeros in the uncond branch
  zero       no stream, the baseline for the gate
Instrument as e24_eval.py: MuScriptor -> skyline -> correlation with the fed stream's centred pitch, jointly sounding frames. A line with no pitch change scores 0 and is counted, not dropped.
Positive control: the crop's latent decoded, read against its stream. Results are also given for the crops where that reads at least 0.5.
Arm C: the stream fed is the centred pitch. Arm B (--pack B): L3 shapes fed, scored on the centred pitch of the same notes.
RUN: eval/run_e24_eval2.sh
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

for k, v in {"FLASH_ATTENTION_TRITON_AMD_ENABLE": "FALSE", "PYTORCH_TUNABLEOP_ENABLED": "0", "MIOPEN_FIND_MODE": "2"}.items():
    os.environ.setdefault(k, v)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np
import e24_eval as X

X.N_CROPS = 24
PROMPTS = Path("/home/kim/evals_aac/control_runs/mood_deconf_20261103/prompts.json")
PACKS = {"C": (X.PACK, 2), "B": (Path("/run/media/kim/Lehto/latents-all-backup/latents_sa3_contourB"), 15)}
ARMS = ("true", "shuffled", "true_null", "shuf_null", "zero")
LOCAL_FRAMES = 16


def feed(pack, stem, w):
    return np.asarray(np.load(PACKS[pack][0] / f"{stem}.ctrl.npy", mmap_mode="r")[:, w: w + X.T], dtype=np.float32)


def plan():
    pr = list(json.loads(PROMPTS.read_text()).values())
    return [dict(stem=s, window=w, prompt=pr[i % len(pr)], seed=9000 + i) for i, (s, w) in enumerate(X.pick_crops())]


def render(a):
    import torch
    from sa3_control.audio_io import save_audio

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    crops = plan()
    (out / "crops.json").write_text(json.dumps(crops, indent=0))
    log = out / "cells.jsonl"
    done = {json.loads(l)["id"] for l in log.read_text().splitlines()} if log.exists() else set()

    def save(x, name):
        tmp = out / "_t.wav"
        save_audio(str(tmp), x, 44100, normalize=True)
        subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(tmp), "-c:a", "aac", "-b:a", "192k", str(out / f"{name}.m4a")], check=True)
        tmp.replace(out / f"{name}.wav")

    sam, _ = X.load_model(Path(a.run) / f"step={a.step}.ckpt", "cuda:0", n_channels=PACKS[a.pack][1])
    dit = sam.model.model.model
    with log.open("a") as f, torch.no_grad():
        for c in crops:
            s, w = c["stem"], c["window"]
            cid = f"ref__{s}"
            if cid not in done:
                z = torch.from_numpy(np.load(X.LAT / f"{s}.npy")[..., w: w + X.T].astype(np.float32)).reshape(1, 256, X.T).to("cuda:0", next(sam.same.parameters()).dtype)
                x = sam.same.decode(z).float().cpu()
                if bool(torch.isfinite(x).all()):
                    save(x[0], cid)
                    f.write(json.dumps(dict(id=cid, stem=s, window=w, arm="ref")) + "\n")
                    f.flush()
            st = feed(a.pack, s, w)
            for arm in ARMS:
                cid = f"st{a.step}__{s}__{arm}"
                if cid in done:
                    continue
                dit.modular_cfg_null = arm.endswith("_null")
                stream = {"true": st, "true_null": st, "shuffled": X.shuffled(st), "shuf_null": X.shuffled(st), "zero": np.zeros_like(st)}[arm]
                x = sam.generate(conditioning=[{"prompt": c["prompt"], "seconds_total": X.DUR, "mir_ctrl": stream}], sample_size=X.T * 4096, duration_padding_sec=0.0, steps=24, cfg_scale=7.0, seed=c["seed"], batch_size=1).float().cpu()
                if not bool(torch.isfinite(x).all()) or float(x.std()) < 1e-3:
                    print("FAULT", cid, flush=True)
                    continue
                save(x[0][:, : int(X.DUR * 44100)], cid)
                f.write(json.dumps(dict(id=cid, stem=s, window=w, arm=arm, std=round(float(x.std()), 4))) + "\n")
                f.flush()


def score(a):
    from e24_build_contour_packs import skyline
    from muscriptor import TranscriptionModel

    out = Path(a.out)
    cells = {}
    for l in (out / "cells.jsonl").read_text().splitlines():
        c = json.loads(l)
        cells[c["id"]] = c
    midd = out / "midi"
    midd.mkdir(exist_ok=True)
    model = None
    if any(not (midd / f"{i}.mid").exists() for i in cells):
        model = TranscriptionModel.load_model("medium", device="cuda")

    def corr(line, target):
        v = (line >= 0) & (target[1] > 0)
        if v.sum() < 16:
            return None, False
        flat = np.std(line[v]) == 0
        return (0.0 if flat or np.std(target[0][v]) == 0 else float(np.corrcoef(line[v], target[0][v])[0, 1])), flat

    def corr_local(line, target, win=LOCAL_FRAMES):
        """The same correlation after taking out each curve's running mean over win frames (about 1.5 s), so only note-scale movement counts."""
        v = (line >= 0) & (target[1] > 0)
        if v.sum() < 2 * win:
            return 0.0
        a, b = line[v].astype(np.float64), target[0][v].astype(np.float64)
        k = np.ones(win) / win
        a, b = a - np.convolve(a, k, "same"), b - np.convolve(b, k, "same")
        return 0.0 if np.std(a) == 0 or np.std(b) == 0 else float(np.corrcoef(a, b)[0, 1])

    rows = []
    for c in cells.values():
        p = midd / f"{c['id']}.mid"
        if not p.exists():
            p.write_bytes(model.transcribe_to_midi(out / f"{c['id']}.wav"))
        line = skyline(str(p))[:X.T]
        own = X.stream(c["stem"], c["window"])          # always the centred-pitch stream of arm C: the same notes, for any pack
        mixed = X.shuffled(own)
        shuf_arm = c["arm"] in ("shuffled", "shuf_null")
        fed, other = (mixed, own) if shuf_arm else (own, mixed)
        r, flat = corr(line, fed)
        ro, _ = corr(line, other)
        v = line >= 0
        rows.append(dict(c, r_fed=r, r_other=ro, rl_fed=corr_local(line, fed), rl_other=corr_local(line, other), flat=bool(flat), pitches=int(len(np.unique(line[v]))), changes=int((np.diff(line[v]) != 0).sum()) if v.sum() else 0))
    (out / "scores.json").write_text(json.dumps(rows, indent=0))
    report(a, rows)


def report(a, rows):
    out = Path(a.out)
    ref = {r["stem"]: r["r_fed"] for r in rows if r["arm"] == "ref"}
    good = {s for s, r in ref.items() if r is not None and r >= 0.5}
    by = {arm: {r["stem"]: r for r in rows if r["arm"] == arm} for arm in ARMS}
    rng = np.random.default_rng(1)
    L = [f"run {a.run}, step {a.step}, pack {a.pack}. corr(MuScriptor line of the render, centred pitch of the fed notes), jointly sounding frames. Flat lines score 0.",
         f"Positive control, decoded crop against its own stream: mean {np.mean([x for x in ref.values() if x is not None]):.3f}, at least 0.5 on {len(good)}/{len(ref)}."]
    for arm in ARMS:
        rs = list(by[arm].values())
        L.append(f"{arm:10s} n {len(rs)} r_fed {np.mean([r['r_fed'] or 0 for r in rs]):+.3f} flat {sum(r['flat'] for r in rs)} pitches {np.median([r['pitches'] for r in rs]):.0f} changes {np.median([r['changes'] for r in rs]):.0f}")

    def follow(arms, keep, name, fed="r_fed", other="r_other"):
        """The test: each render against the stream it was fed minus the stream it was not. Each arm scored only against its own stream cannot separate them, since both can follow."""
        d = np.array([(r[fed] or 0) - (r[other] or 0) for a in arms for k, r in by[a].items() if k in keep])
        if not d.size:
            return f"{name}: no clips"
        boot = [rng.choice(d, d.size).mean() for _ in range(4000)]
        return f"{name}: {d.mean():+.3f} [{np.percentile(boot, 2.5):+.3f},{np.percentile(boot, 97.5):+.3f}] positive {int((d > 0).sum())}/{d.size}"

    both, nul = ("true", "shuffled"), ("true_null", "shuf_null")
    for lab, keep in (("all crops", set(ref)), ("control >= 0.5", good)):
        L.append(f"FOLLOW, fed minus other, {lab}: " + follow(both, keep, "both branches") + " | " + follow(nul, keep, "null uncond"))
        L.append(f"  note scale, running mean of {LOCAL_FRAMES} frames removed, {lab}: " + follow(both, keep, "both branches", "rl_fed", "rl_other") + " | " + follow(nul, keep, "null uncond", "rl_fed", "rl_other"))
    refs = [r for r in rows if r["arm"] == "ref"]
    L.append(f"  note scale, decoded crops: fed {np.mean([r['rl_fed'] for r in refs]):+.3f}, other {np.mean([r['rl_other'] for r in refs]):+.3f}")
    (out / "report.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


def gate_stage(a):
    import sqlite3
    from collections import Counter

    from control_head_disintegration_eval import DB, gate

    out = Path(a.out)
    db = sqlite3.connect(DB)
    cols = [r[1] for r in db.execute("PRAGMA table_info(metrics)").fetchall()]
    rows = {r[0]: dict(zip(cols, r)) for r in db.execute("select * from metrics where path like ?", (f"{out}/%",))}
    res = {}
    for l in (out / "cells.jsonl").read_text().splitlines():
        c = json.loads(l)
        if c["arm"] in ("zero", "ref"):
            continue
        m, b = rows.get(str(out / f"{c['id']}.m4a")), rows.get(str(out / f"st{a.step}__{c['stem']}__zero.m4a"))
        r = res.setdefault(c["arm"], dict(n=0, fails=0, why=Counter(), missing=0))
        if not m or not b:
            r["missing"] += 1
            continue
        bad, why, _ = gate(m, b, rhythmic=True)
        r["n"] += 1
        r["fails"] += int(bad)
        r["why"].update(x.split("(")[0] for x in why)
    L = ["GATE, against the zero arm of the same crop:"] + [f"{k}: {r['fails']}/{r['n']} fail {dict(r['why'])}" + (f" missing {r['missing']}" if r["missing"] else "") for k, r in res.items()]
    with (out / "report.txt").open("a") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("render", "score", "gate"), required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--step", type=int, default=2400)
    ap.add_argument("--pack", choices=tuple(PACKS), default="C")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    {"render": render, "score": score, "gate": gate_stage}[args.stage](args)
