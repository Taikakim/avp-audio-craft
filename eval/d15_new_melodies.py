#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""d15_new_melodies.py -- EXPERIMENTS D15: does the pianoroll fine-tune play notes it was NOT trained on? With zeros for the stream in CFG's uncond branch it plays training rolls at F1 0.65 (source crop 0.61), even shuffled, but those are its training crops.

Two kinds of stream, neither in the training set:
  new      an invented single-voice melody: scale walks and arpeggios, in random keys, notes of 2-6 frames, 12 prompts x 3 melodies each
  transp   a real crop's roll transposed by +5 or -7 semitones, 12 crops
  zero     no stream, the baseline for the gate
All with modular_cfg_null on. Instrument: MuScriptor on the render, as the training rolls were made.
Scores for new: recall = share of fed note frames that sound; on_fed = share of the top line's frames on the fed pitch, against the same melody in shuffled 3 s blocks (placement) and against another melody (content). Pitch class too, as the octave may move.
Scores for transp: (pitch, frame) F1 with the transposed roll against the roll as it was: does it move with the transposition?
Outputs: ~/evals_aac/control_runs/pianoroll_newmelody_goa_t256_step2688_20261103/. RUN: eval/run_d15_new_melodies.sh
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
import e24_eval2 as Y

OUT = Path("/home/kim/evals_aac/control_runs/pianoroll_newmelody_goa_t256_step2688_20261103")
RUN = Path("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/pianoroll_fullft/proll_fullft_t256_bf16_s1")
CKPT = "epoch=31-step=2688.ckpt"
T = X.T
SCALES = {"phrygian": (0, 1, 3, 5, 7, 8, 10), "minor": (0, 2, 3, 5, 7, 8, 10), "dorian": (0, 2, 3, 5, 7, 9, 10)}
N_PROMPTS = 12
PER_PROMPT = 3
TRANSP = (5, -7)


def melody(i):
    """(T,) int16: MIDI pitch per frame. Deterministic per i."""
    rng = np.random.default_rng(5000 + i)
    root = 45 + int(rng.integers(0, 12)) + 12
    scale = SCALES[list(SCALES)[i % 3]]
    pcs = np.array([root + o * 12 + s for o in range(0, 3) for s in scale])
    pcs = pcs[(pcs >= 48) & (pcs <= 90)]
    kind = i % 4
    phrase = []
    k = int(rng.integers(3, len(pcs) - 6))
    for n in range(16):
        if kind == 0:            # scale walk
            k = int(np.clip(k + rng.choice((-2, -1, 1, 2)), 0, len(pcs) - 1))
        elif kind == 1:          # arpeggio up and down
            k = int(np.clip(k + (2 if (n // 4) % 2 == 0 else -2), 0, len(pcs) - 1))
        elif kind == 2:          # leaps around a pedal
            k = int(np.clip((k + rng.choice((3, 4, -3, -4))) if n % 2 else k, 0, len(pcs) - 1))
        else:                    # slow wide contour
            k = int(np.clip(k + rng.choice((-1, 1, 3, -3)), 0, len(pcs) - 1))
        phrase.append(int(pcs[k]))
    durs = rng.choice((2, 3, 4, 6), 16)
    out = np.zeros(T, dtype=np.int16)
    t, j = 0, 0
    while t < T:
        d = int(durs[j % 16])
        out[t:t + d] = phrase[j % 16]
        t, j = t + d, j + 1
    return out


def roll_of_line(line):
    r = np.zeros((128, T), dtype=np.float32)
    r[line, np.arange(T)] = 1.0
    return r


def shuffle_line(line):
    return np.concatenate([np.array_split(line, 8)[i] for i in np.random.default_rng(7).permutation(8)])


def plan():
    pr = list(json.loads(Y.PROMPTS.read_text()).values())
    crops = X.pick_crops()
    out, mid = [], 0
    for p in range(N_PROMPTS):
        pt, seed = pr[p % len(pr)], 7000 + p
        out.append(dict(id=f"p{p}__zero", kind="zero", prompt=pt, seed=seed, p=p))
        for _ in range(PER_PROMPT):
            out.append(dict(id=f"p{p}__new{mid}", kind="new", melody=mid, other=(mid + 5) % (N_PROMPTS * PER_PROMPT), prompt=pt, seed=seed, p=p))
            mid += 1
        s, w = crops[p]
        for tr in TRANSP:
            out.append(dict(id=f"p{p}__tr{tr:+d}", kind="transp", stem=s, window=w, semis=tr, prompt=pt, seed=seed, p=p))
    return out


def stream_of(c):
    if c["kind"] == "zero":
        return np.zeros((128, T), dtype=np.float32)
    if c["kind"] == "new":
        return roll_of_line(melody(c["melody"]))
    return np.roll(Y.feed("P", c["stem"], c["window"]), c["semis"], axis=0)


def render():
    import torch
    from sa3_control.audio_io import save_audio

    OUT.mkdir(parents=True, exist_ok=True)
    cells = plan()
    (OUT / "plan.json").write_text(json.dumps(cells, indent=0))
    log = OUT / "cells.jsonl"
    done = {json.loads(l)["id"] for l in log.read_text().splitlines()} if log.exists() else set()
    sam = Y.load_fullft(RUN / CKPT, "cuda:0", 128)
    sam.model.model.model.modular_cfg_null = True
    with log.open("a") as f, torch.no_grad():
        for c in cells:
            if c["id"] in done:
                continue
            x = sam.generate(conditioning=[{"prompt": c["prompt"], "seconds_total": X.DUR, "mir_ctrl": stream_of(c)}], sample_size=T * 4096, duration_padding_sec=0.0, steps=24, cfg_scale=7.0, seed=c["seed"], batch_size=1).float().cpu()
            if not bool(torch.isfinite(x).all()) or float(x.std()) < 1e-3:
                print("FAULT", c["id"], flush=True)
                continue
            tmp = OUT / "_t.wav"
            save_audio(str(tmp), x[0][:, : int(X.DUR * 44100)], 44100, normalize=True)
            subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(tmp), "-c:a", "aac", "-b:a", "192k", str(OUT / f"{c['id']}.m4a")], check=True)
            tmp.replace(OUT / f"{c['id']}.wav")
            f.write(json.dumps({**c, "std": round(float(x.std()), 4)}) + "\n")
            f.flush()


def on_line(top, line, pc=False):
    v = top >= 0
    if v.sum() < 16:
        return 0.0
    return float(((top[v] % 12) == (line[v] % 12)).mean()) if pc else float((top[v] == line[v]).mean())


def any_on_line(roll, line, pc=False):
    """Share of the melody's frames at which the fed pitch sounds anywhere in the render: recall, not fooled by a louder voice above it."""
    if pc:
        pcs = np.stack([roll[k::12].any(0) for k in range(12)])
        return float(pcs[line % 12, np.arange(T)].mean())
    return float(roll[line, np.arange(T)].mean())


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
        roll, top = Y.roll_of(p), skyline(str(p))[:T]
        r = dict(c)
        if c["kind"] == "new":
            m, o = melody(c["melody"]), melody(c["other"])
            s = shuffle_line(m)
            for name, fn in (("recall", any_on_line), ("top", on_line)):
                r[f"{name}_fed"], r[f"{name}_shuf"], r[f"{name}_other"] = fn(roll if name == "recall" else top, m), fn(roll if name == "recall" else top, s), fn(roll if name == "recall" else top, o)
                r[f"{name}_pc_fed"], r[f"{name}_pc_shuf"], r[f"{name}_pc_other"] = fn(roll if name == "recall" else top, m, True), fn(roll if name == "recall" else top, s, True), fn(roll if name == "recall" else top, o, True)
        elif c["kind"] == "transp":
            orig = Y.feed("P", c["stem"], c["window"]) > 0
            r["f1_fed"], r["f1_orig"] = Y.f1(roll, np.roll(orig, c["semis"], axis=0)), Y.f1(roll, orig)
        else:                      # the no-stream clip against every melody of its prompt: the chance level
            ms = [melody(k["melody"]) for k in cells if k["kind"] == "new" and k["p"] == c["p"]]
            r["recall_fed"] = float(np.mean([any_on_line(roll, m) for m in ms]))
            r["recall_pc_fed"] = float(np.mean([any_on_line(roll, m, True) for m in ms]))
            r["top_fed"] = float(np.mean([on_line(top, m) for m in ms]))
            r["top_pc_fed"] = float(np.mean([on_line(top, m, True) for m in ms]))
        rows.append(r)
    (OUT / "scores.json").write_text(json.dumps(rows, indent=0))
    rng = np.random.default_rng(1)

    def ci(d):
        d = np.asarray(d)
        b = [rng.choice(d, d.size).mean() for _ in range(4000)]
        return f"{d.mean():+.3f} [{np.percentile(b, 2.5):+.3f}, {np.percentile(b, 97.5):+.3f}] {int((d > 0).sum())}/{d.size}"

    new = [r for r in rows if r["kind"] == "new"]
    zero = [r for r in rows if r["kind"] == "zero"]
    tr = [r for r in rows if r["kind"] == "transp"]
    L = [f"Pianoroll fine-tune, step 2688, CFG on the stream. {len(new)} clips of invented melodies, {len(tr)} of transposed crops, {len(zero)} without a stream. MuScriptor on the render. Measured, not heard."]
    for k, lab in (("recall", "the fed pitch sounds anywhere"), ("recall_pc", "same, any octave"), ("top", "the top line is on the fed pitch"), ("top_pc", "same, any octave")):
        L.append(f"{lab}: fed {np.mean([r[k + '_fed'] for r in new]):.3f}, shuffled {np.mean([r[k + '_shuf'] for r in new]):.3f}, other melody {np.mean([r[k + '_other'] for r in new]):.3f}, no stream {np.mean([r[k + '_fed'] for r in zero]):.3f}")
        L.append(f"   fed minus shuffled {ci([r[k + '_fed'] - r[k + '_shuf'] for r in new])}; fed minus other {ci([r[k + '_fed'] - r[k + '_other'] for r in new])}")
    L.append(f"transposed crops, F1 with the transposed roll {np.mean([r['f1_fed'] for r in tr]):.3f}, with the roll as it was {np.mean([r['f1_orig'] for r in tr]):.3f}; difference {ci([r['f1_fed'] - r['f1_orig'] for r in tr])}")
    (OUT / "report.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


def gate_stage():
    import sqlite3
    from collections import Counter

    from control_head_disintegration_eval import DB, gate

    db = sqlite3.connect(DB)
    cols = [r[1] for r in db.execute("PRAGMA table_info(metrics)").fetchall()]
    rows = {r[0]: dict(zip(cols, r)) for r in db.execute("select * from metrics where path like ?", (f"{OUT}/%",))}
    res = {}
    for l in (OUT / "cells.jsonl").read_text().splitlines():
        c = json.loads(l)
        if c["kind"] == "zero":
            continue
        m, b = rows.get(str(OUT / f"{c['id']}.m4a")), rows.get(str(OUT / f"p{c['p']}__zero.m4a"))
        r = res.setdefault(c["kind"], dict(n=0, fails=0, why=Counter(), missing=0))
        if not m or not b:
            r["missing"] += 1
            continue
        bad, why, _ = gate(m, b, rhythmic=True)
        r["n"] += 1
        r["fails"] += int(bad)
        r["why"].update(x.split("(")[0] for x in why)
    L = ["GATE, against the no-stream clip of the same prompt and seed:"] + [f"{k}: {r['fails']}/{r['n']} fail {dict(r['why'])}" + (f" missing {r['missing']}" if r["missing"] else "") for k, r in res.items()]
    with (OUT / "report.txt").open("a") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("render", "score", "gate"), required=True)
    a = ap.parse_args()
    {"render": render, "score": score, "gate": gate_stage}[a.stage]()
