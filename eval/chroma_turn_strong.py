#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-04)
"""chroma_turn_strong.py -- EXPERIMENTS B6b: was the guidance route for melody closed too early? July's 0 of 12 used the weak production chroma head, and hpcp was dropped on a target off by 9 semitones.
Part M, the same 36 invented melodies, prompts and seeds as D15's pianoroll, so the two routes are read on one scale, folded to pitch class (chroma cannot see octaves):
  c3       same_chroma C3 lr 1e-3 ep10 EMA (E13), gain 8192
  c3sharp  the same, target squared then mean removed (E13x's 'sharp'), gain 32768
  hpcp     hpcp head, target rotated to its A = 0 bins, gain 8192
  c3slow   c3 with each melody 8x slower, notes 1.5 to 4.5 s (D16: guidance follows only slow movement)
  zero     guided sampler at gain 0, one per prompt: the chance level and the gate baseline
  pianoroll  no render: the D15 clips scored the same way
Part J, July's harness (eval/musicology/chroma_turning_2026-07-22/chromaturn.py), same patterns, seeds and scoring, with the C3 head: arm A free generation at gains 2048, 8192 and sharp 32768; arm B SDEdit from the pat1 render at gain 8192; unguided baselines and controls.
Stages: render, score (.venv, GPU), gate (mir venv, after clip_metrics). Outputs ~/evals_aac/control_runs/chroma_turning_strong_20261104/. RUN: eval/run_chroma_turn_strong.sh
"""
import argparse
import gc
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

for k, v in {"FLASH_ATTENTION_TRITON_AMD_ENABLE": "FALSE", "PYTORCH_TUNABLEOP_ENABLED": "0", "MIOPEN_FIND_MODE": "2"}.items():
    os.environ.setdefault(k, v)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "musicology" / "chroma_turning_2026-07-22"))
sys.path.insert(0, str(HERE.parent / "control"))
sys.path.insert(0, "/home/kim/Projects/mir-same-chroma/src")
import numpy as np

OUT = Path("/home/kim/evals_aac/control_runs/chroma_turning_strong_20261104")
PIANOROLL = Path("/home/kim/evals_aac/control_runs/pianoroll_newmelody_goa_t256_step2688_20261103")
HPCP = HERE.parent / "stable-audio-3" / "latch_weights_sa3_medium" / "latch_sa3_hpcp_best.pt"
C3 = Path("/run/media/kim/Mantu/latch_sweep/__chroma/chroma_retrain_2026-10-16/C3_chroma_d512_lr1e-3/latch_sa3_same_chroma_ep10.pt")
SLOW = 8
MARMS = {"c3": ("c3", 8192, False, False), "c3sharp": ("c3", 32768, True, False), "hpcp": ("hpcp", 8192, False, False), "c3slow": ("c3", 8192, False, True)}
JARMS = [("c3", 2048, False), ("c3", 8192, False), ("c3", 32768, True)]


def slowed(line):
    return line[np.arange(len(line)) // SLOW]


def target_384(pcs, sharp):
    import chromaturn as CT

    raw = CT.target_raw_384(pcs)
    if sharp:
        raw = raw ** 2
        raw = raw - raw.mean(axis=0, keepdims=True)
    return raw.astype(np.float32)


def target_12(pcs):
    out = np.zeros((12, len(pcs)), dtype=np.float32)
    v = pcs >= 0
    out[(pcs[v] - 9) % 12, np.nonzero(v)[0]] = 1.0  # hpcp bin i = pitch class (i + 9) % 12
    return out


def plan():
    import chromaturn as CT
    import d15_new_melodies as D

    base = D.plan()
    out = [dict(id=f"m__zero__p{c['p']}", part="M", arm="zero", head="c3", gain=0, sharp=False, slow=False, p=c["p"], prompt=c["prompt"], seed=c["seed"]) for c in base if c["kind"] == "zero"]
    for arm, (h, g, sh, sl) in MARMS.items():
        for c in base:
            if c["kind"] == "new":
                out.append(dict(id=f"m__{arm}__p{c['p']}__m{c['melody']}", part="M", arm=arm, head=h, gain=g, sharp=sh, slow=sl, p=c["p"], melody=c["melody"], other=c["other"], prompt=c["prompt"], seed=c["seed"]))
    for s in CT.SEEDS:
        out.append(dict(id=CT.clip_name(dict(arm="A", target=None, head=None, gain=0, nl=None, seed=s)), part="J", arm="A", target=None, head=None, gain=0, nl=None, seed=s, prompt=CT.PROMPT_FREE))
        for t in ("pat2", "pat3", "pat6"):
            for h, g, sh in JARMS:
                c = dict(arm="A", target=t, head="c3sharp" if sh else h, gain=g, nl=None, seed=s, prompt=CT.PROMPT_FREE)
                out.append(dict(c, id=CT.clip_name(c), part="J", sharp=sh))
    for nl in CT.NLS:
        c = dict(arm="C", target=None, head=None, gain=0, nl=nl, seed=1234, prompt=CT.PROMPT_A2A, source="pat1")
        out.append(dict(c, id=CT.clip_name(c), part="J"))
        for t in ("pat2", "pat6"):
            c = dict(arm="B", target=t, head="c3", gain=8192, nl=nl, seed=1234, prompt=CT.PROMPT_A2A, source="pat1")
            out.append(dict(c, id=CT.clip_name(c), part="J", sharp=False))
    return out


def render():
    import soundfile as sf
    import torch
    from sa3_control.audio_io import save_audio
    from stable_audio_3 import StableAudioModel
    import chromaturn as CT
    import d15_new_melodies as D

    OUT.mkdir(parents=True, exist_ok=True)
    meta_p = OUT / "run_meta.json"
    if not meta_p.exists():
        meta_p.write_text(json.dumps({"purpose": "EXPERIMENTS B6b: can a strong chroma head play or turn a melody through guidance alone? Same melodies as the pianoroll for a direct comparison, and July's harness with the stronger head.", "hypothesis": "July's 0 of 12 had the weak production head. E13's head moves chroma far more, so the old verdict may not hold. Against that, D16 found guidance follows only slow movement, so note-rate lines may still fail and slow ones may not.", "heads": {"c3": str(C3.name), "hpcp": HPCP.name}, "training": "E13 C3 lr 1e-3 ep10 EMA, latch/run_chroma_retrain.sh, goa latents_sa3, 5400 crops; hpcp production head", "paths": {"script": "eval/chroma_turn_strong.py", "runner": "eval/run_chroma_turn_strong.sh", "experiment": "EXPERIMENTS B6"}, "kim_feedback": None}, indent=1))
    log = OUT / "cells.jsonl"
    done = {json.loads(l)["id"] for l in log.read_text().splitlines()} if log.exists() else set()
    gt = {p: CT.midi_frame_pcs(p) for p in ("pat2", "pat3", "pat6")}
    src_np, src_sr = sf.read(str(CT.SOURCE_WAV), dtype="float32")
    src_wav = torch.from_numpy(src_np.T)[:, : int(CT.DURATION * src_sr)]
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    with log.open("a") as f:
        for c in plan():
            if c["id"] in done:
                continue
            gen = dict(prompt=c["prompt"], duration=CT.DURATION, steps=CT.STEPS, cfg_scale=CT.CFG, seed=c["seed"])
            if c["part"] == "M":
                line = D.melody(c.get("melody", 0))
                line = slowed(line) if c["slow"] else line
                pcs = line % 12
                head = HPCP if c["head"] == "hpcp" else C3
                raw = target_12(pcs) if c["head"] == "hpcp" else target_384(pcs, c["sharp"])
            else:
                if c.get("source"):
                    gen["init_audio"] = (CT.SR, src_wav)
                    gen["init_noise_level"] = float(c["nl"])
                head = C3
                raw = target_384(gt[c["target"]] if c["target"] else gt["pat2"], c.get("sharp", False))
            gen["latch_configs"] = [{"model_path": str(head), "target_raw": raw, "weight": 1.0, "loss_type": "cosine"}]
            gen["latch_hparams"] = {"rho": float(c["gain"]), "mu": float(c["gain"])}
            sink = []
            audio = model.generate(latents_sink=sink, **gen)
            z = sink[-1].float()
            wav = audio[0].float().cpu()
            if not torch.isfinite(z).all() or not torch.isfinite(wav).all() or float(wav.std()) < 1e-3:
                print("FAULT", c["id"], flush=True)
                continue
            wp = OUT / f"{c['id']}.wav"
            save_audio(str(wp), wav, CT.SR)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wp), "-c:a", "aac", "-b:a", "192k", str(OUT / f"{c['id']}.m4a")], check=True)
            f.write(json.dumps({**c, "z_std": round(float(z.std()), 4)}) + "\n")
            f.flush()
            del audio, z, wav, sink
            gc.collect()
            torch.cuda.empty_cache()


def transcribe(model, wav, mid):
    if not mid.exists():
        mid.write_bytes(model.transcribe_to_midi(wav))


def score():
    from e24_build_contour_packs import skyline
    from muscriptor import TranscriptionModel
    import chromaturn as CT
    import d15_new_melodies as D

    Y = D.Y
    cells = [json.loads(l) for l in (OUT / "cells.jsonl").read_text().splitlines()]
    mdir = OUT / "hook_scores_midi"
    mdir.mkdir(exist_ok=True)
    model = TranscriptionModel.load_model("medium", device="cuda") if any(not (mdir / f"{c['id']}.mid").exists() for c in cells) else None
    for c in cells:
        if model:
            transcribe(model, OUT / f"{c['id']}.wav", mdir / f"{c['id']}.mid")

    def metrics(mid, line, other):
        roll, top = Y.roll_of(mid), skyline(str(mid))[: D.T]
        return dict(recall_pc=D.any_on_line(roll, line, pc=True), top_pc=D.on_line(top, line, pc=True), recall=D.any_on_line(roll, line), top=D.on_line(top, line), recall_pc_other=D.any_on_line(roll, other, pc=True), top_pc_other=D.on_line(top, other, pc=True))

    new = [c for c in D.plan() if c["kind"] == "new"]
    rows = []
    for c in cells:
        if c["part"] != "M":
            continue
        if c["arm"] == "zero":
            ms = [k for k in new if k["p"] == c["p"]]
            for slow in (False, True):
                ls = [slowed(D.melody(k["melody"])) if slow else D.melody(k["melody"]) for k in ms]
                vals = [metrics(mdir / f"{c['id']}.mid", l, l) for l in ls]
                rows.append({**{k: c[k] for k in ("id", "arm", "p")}, "slow": slow, **{k: float(np.mean([v[k] for v in vals])) for k in vals[0]}})
        else:
            tf = slowed if c["slow"] else (lambda x: x)
            rows.append({**{k: c[k] for k in ("id", "arm", "p", "melody")}, "slow": c["slow"], **metrics(mdir / f"{c['id']}.mid", tf(D.melody(c["melody"])), tf(D.melody(c["other"])))})
    for k in new:
        mid = PIANOROLL / "midi" / f"{k['id']}.mid"
        rows.append({"id": k["id"], "arm": "pianoroll", "p": k["p"], "melody": k["melody"], "slow": False, **metrics(mid, D.melody(k["melody"]), D.melody(k["other"]))})
    (OUT / "scores.json").write_text(json.dumps(rows, indent=0))
    # July's analyzer, unchanged, pointed at this run
    jc = [c for c in cells if c["part"] == "J"]
    CT.OUT, CT.WAV_DIR, CT.MANIFEST = OUT, OUT, OUT / "manifest.json"
    CT.MANIFEST.write_text(json.dumps({"cells": [{**c, "clip": c["id"]} for c in jc]}, indent=1))
    CT.analyze()


def gate_stage():
    import sqlite3

    from control_head_disintegration_eval import DB, gate

    db = sqlite3.connect(DB)
    cols = [r[1] for r in db.execute("PRAGMA table_info(metrics)").fetchall()]
    met = {r[0]: dict(zip(cols, r)) for r in db.execute("select * from metrics where path like ?", (f"{OUT}/%",))}
    rows = json.loads((OUT / "scores.json").read_text())
    z = {json.loads(l)["id"]: json.loads(l)["z_std"] for l in (OUT / "cells.jsonl").read_text().splitlines()}
    rng = np.random.default_rng(1)

    def ci(d):
        d = np.asarray(d)
        b = [rng.choice(d, d.size).mean() for _ in range(4000)]
        return f"{d.mean():+.3f} [{np.percentile(b, 2.5):+.3f}, {np.percentile(b, 97.5):+.3f}] {int((d > 0).sum())}/{d.size}"

    L = ["Part M. Same 36 invented melodies, folded to pitch class. Measured by MuScriptor, not heard. Sounds = the fed pitch class sounds anywhere; top = the top line on it."]
    zero = {s: [r for r in rows if r["arm"] == "zero" and r["slow"] == s] for s in (False, True)}
    for s in (False, True):
        L.append(f"no stream ({'slow' if s else 'as fed'} lines): sounds {np.mean([r['recall_pc'] for r in zero[s]]):.1%}, top {np.mean([r['top_pc'] for r in zero[s]]):.1%}")
    for arm in ("pianoroll", "c3", "c3sharp", "hpcp", "c3slow"):
        S = [r for r in rows if r["arm"] == arm]
        if not S:
            continue
        why, fails, n = Counter(), 0, 0
        for r in S:
            m, b = met.get(str(OUT / f"{r['id']}.m4a")), met.get(str(OUT / f"m__zero__p{r['p']}.m4a"))
            if m and b:
                bad, w, _ = gate({**m, "z_std": z[r["id"]]}, {**b, "z_std": z[f"m__zero__p{r['p']}"]}, rhythmic=True)
                n += 1
                fails += int(bad)
                why.update(x.split("(")[0] for x in w)
        g = f"gate {fails}/{n} {dict(why)}" if n else "gate: D15 record"
        L.append(f"{arm}: n {len(S)}; sounds {np.mean([r['recall_pc'] for r in S]):.1%}, top {np.mean([r['top_pc'] for r in S]):.1%}; exact pitch sounds {np.mean([r['recall'] for r in S]):.1%}; fed minus other, sounds {ci([r['recall_pc'] - r['recall_pc_other'] for r in S])}, top {ci([r['top_pc'] - r['top_pc_other'] for r in S])}; {g}")
    L.append("")
    L.append("Part J. July's harness, C3 head. target_nonmodal = moving part of the target pattern found, after the best shift. July's production head: pat2 0.07-0.555, pat3 0.07-0.281, pat6 0.")
    res = json.loads((OUT / "results.json").read_text())
    null = {r["seed"]: r for r in res if r["arm"] == "A" and not r["gain"]}
    for r in sorted(res, key=lambda r: r["clip"]):
        if r["arm"] == "A" and r["gain"]:
            L.append(f"{r['clip']}: target {r.get('target_nonmodal')}, null {null[r['seed']].get('null_' + r['target'] + '_nonmodal')}, chroma {r.get('tgt_chroma_cos_disc')} vs {null[r['seed']].get('null_' + r['target'] + '_chroma')}, {r.get('gate')}")
        elif r["arm"] in ("B", "C"):
            L.append(f"{r['clip']}: target_disc {r.get('target_disc')}, source_disc {r.get('source_disc')}, target chroma {r.get('tgt_chroma_cos_disc')}, source chroma {r.get('src_chroma_cos_disc')}, nulls {r.get('null_pat2_disc')}, {r.get('null_pat6_disc')}, {r.get('gate')}")
    (OUT / "report.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


def melodia_job(c):
    import d15_melodia_check as MC
    import d15_new_melodies as D

    f0 = MC.f0_of(str(OUT / f"{c['id']}.wav"))
    if c["arm"] == "zero":
        ms = [k["melody"] for k in D.plan() if k["kind"] == "new" and k["p"] == c["p"]]
        return dict(id=c["id"], arm="zero", p=c["p"], fed=float(np.mean([MC.near(f0, D.melody(k))[0] for k in ms])), fed_slow=float(np.mean([MC.near(f0, slowed(D.melody(k)))[0] for k in ms])))
    tf = slowed if c["slow"] else (lambda x: x)
    m, o = tf(D.melody(c["melody"])), tf(D.melody(c["other"]))
    return dict(id=c["id"], arm=c["arm"], p=c["p"], fed=MC.near(f0, m)[0], other=MC.near(f0, o)[0], voiced=MC.near(f0, m)[1])


def melodia():
    """Second meter on part M, as eval/d15_melodia_check.py: voiced frames within 1 semitone of the line, octave folded. Mir venv, CPU."""
    from concurrent.futures import ProcessPoolExecutor

    cells = [json.loads(l) for l in (OUT / "cells.jsonl").read_text().splitlines()]
    cells = [c for c in cells if c["part"] == "M"]
    with ProcessPoolExecutor(12) as ex:
        rows = list(ex.map(melodia_job, cells))
    (OUT / "melodia.json").write_text(json.dumps(rows, indent=0))
    rng = np.random.default_rng(1)

    def ci(d):
        d = np.asarray(d)
        b = [rng.choice(d, d.size).mean() for _ in range(4000)]
        return f"{d.mean():+.3f} [{np.percentile(b, 2.5):+.3f}, {np.percentile(b, 97.5):+.3f}] {int((d > 0).sum())}/{d.size}"

    z = [r for r in rows if r["arm"] == "zero"]
    L = ["", f"Melodia, a second meter on part M: voiced frames within 1 semitone of a line, octave folded. No stream {np.mean([r['fed'] for r in z]):.1%}, against slow lines {np.mean([r['fed_slow'] for r in z]):.1%}. Pianoroll on the same melodies, D15 record: fed 74%, other 17%, fed minus other +0.58 [+0.50, +0.65], 34/36."]
    for arm in MARMS:
        s = [r for r in rows if r["arm"] == arm]
        L.append(f"{arm}: fed {np.mean([r['fed'] for r in s]):.1%}, other {np.mean([r['other'] for r in s]):.1%}, fed minus other {ci([r['fed'] - r['other'] for r in s])}")
    with (OUT / "report.txt").open("a") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("render", "score", "gate", "melodia"), required=True)
    a = ap.parse_args()
    {"render": render, "score": score, "gate": gate_stage, "melodia": melodia}[a.stage]()
