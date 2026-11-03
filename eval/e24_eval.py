#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""e24_eval.py -- EXPERIMENTS E24 arm C: does the centred-pitch stream steer the melody at inference? Instrument first, as E24 requires.

Instrument: MuScriptor on the audio -> the same skyline and centring as the pack (eval/e24_build_contour_packs.py) -> correlation with a stream, jointly voiced frames.
Positive control: each crop's own latent decoded, read against its own stream, against other crops' streams as the floor. If this does not separate, the render scores mean nothing.
Renders: 6 crops (T=256 windows with a busy line), checkpoints at 800, 1600, 2400 steps, one seed. Arms:
  true      the crop's own stream
  shuffled  the same stream, 8 blocks permuted: same notes, wrong placement
  foreign   another crop's stream
  zero      no stream (the trained null)
Score: corr(render line, FED stream), plus corr with the true stream for the controls. The kill test is true minus shuffled. 
Outputs: ~/evals_aac/control_runs/e24_contourC_eval_20261103/. RUN: eval/run_e24_eval.sh
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
SAO = HERE.parent
for p in (SAO / "control", SAO / "stable-audio-3", SAO / "stable-audio-3" / "scripts", HERE):
    sys.path.insert(0, str(p))
import numpy as np

OUT = Path("/home/kim/evals_aac/control_runs/e24_contourC_eval_20261103")
RUN = Path("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_lora_runs/e24_contourC_r128_2026-11-03")
PACK = Path("/run/media/kim/Lehto/latents-all-backup/latents_sa3_contourC")
LAT = Path("/run/media/kim/Kosmos/latents/latents_sa3")
STEPS = (800, 1600, 2400)
T = 256
FPS = 44100 / 4096
DUR = T / FPS
PROMPT = "goa trance, melodic mood, 145 bpm"
SEED = 1234
N_CROPS = 6
ARMS = ("true", "shuffled", "foreign", "zero")


def pick_crops():
    """Crops whose best 256-frame window has a long voiced and moving line, fixed order."""
    rng = np.random.default_rng(24)
    stems = sorted(p.name[: -len(".ctrl.npy")] for p in PACK.glob("*.ctrl.npy"))
    rng.shuffle(stems)
    out = []
    for s in stems:
        c = np.load(PACK / f"{s}.ctrl.npy", mmap_mode="r")
        best = None
        for w in range(0, 4096 - T, 128):
            v = c[1, w: w + T] > 0
            if v.mean() < 0.85:
                continue
            spread = float(np.std(np.asarray(c[0, w: w + T])[v]))
            if best is None or spread > best[0]:
                best = (spread, w)
        if best and 0.3 < best[0] < 1.2:
            out.append((s, best[1]))
        if len(out) == N_CROPS:
            return out
    return out


def stream(stem, w):
    return np.asarray(np.load(PACK / f"{stem}.ctrl.npy", mmap_mode="r")[:, w: w + T], dtype=np.float32)


def shuffled(st):
    idx = np.random.default_rng(7).permutation(8)
    blocks = np.array_split(st, 8, axis=1)
    return np.concatenate([blocks[i] for i in idx], axis=1)


def load_model(ck_path, device):
    """Base model + the DoRA + the trained mir_ctrl projections. Checks that both actually arrived: load_state_dict(strict=False) would hide a miss."""
    import torch
    from mir_control import MirCtrlConditioner, install_mir_control
    from stable_audio_3 import StableAudioModel

    sam = StableAudioModel.from_pretrained("medium-base", device=device)
    sam.load_lora([str(ck_path)])
    tfm = sam.model.model.model.transformer
    install_mir_control(sam.model, tfm, n_channels=2, blocks="12-23")
    sam.model.conditioner.conditioners["mir_ctrl"] = MirCtrlConditioner(n_channels=2, dropout_prob=0.0)
    ck = torch.load(ck_path, map_location="cpu", weights_only=False)
    sd = {k[len("model.transformer."):]: v for k, v in ck["state_dict"].items() if "modular_local_embeds.mir_ctrl" in k}
    missing, unexpected = tfm.load_state_dict(sd, strict=False)
    assert not unexpected and len(sd) == 12 * 4, (len(sd), unexpected[:3])
    md = next(tfm.parameters()).dtype
    for lay in tfm.layers:
        if "mir_ctrl" in lay.modular_local_embeds:
            lay.modular_local_embeds["mir_ctrl"].to(device=device, dtype=md)
    live = {n: q for n, q in sam.model.named_parameters() if n.endswith("lora_A")}
    saved = {k: v for k, v in ck["state_dict"].items() if k.endswith("lora_A")}
    probe = "to_timestep_embed.0.parametrizations.weight.0"
    a0 = next((q for n, q in sam.model.named_parameters() if probe in n and "lora_A" in n), None)
    b0 = next((v for k, v in saved.items() if probe in k), None)
    close = a0 is not None and b0 is not None and a0.shape == b0.shape and bool(torch.allclose(a0.float().cpu(), b0.float(), atol=1e-3))
    print(f"loaded {ck_path.name}: mir_ctrl tensors {len(sd)}, adapter params live {len(live)} saved {len(saved)}, probe matches {close}", flush=True)
    assert close and len(live) == len(saved)
    return sam, ck["state_dict"]


def gen(sam, st, seed=SEED, steps=24):
    return sam.generate(conditioning=[{"prompt": PROMPT, "seconds_total": DUR, "mir_ctrl": st}], sample_size=T * 4096, duration_padding_sec=0.0, steps=steps, cfg_scale=7.0, seed=seed, batch_size=1).float().cpu()


def render():
    import torch
    from sa3_control.audio_io import save_audio

    OUT.mkdir(parents=True, exist_ok=True)
    crops = pick_crops()
    (OUT / "crops.json").write_text(json.dumps(crops))
    print("crops", crops, flush=True)
    log = OUT / "cells.jsonl"
    done = {json.loads(l)["id"] for l in log.read_text().splitlines()} if log.exists() else set()

    def save(a, name):
        tmp = OUT / "_t.wav"
        save_audio(str(tmp), a, 44100, normalize=True)
        subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(tmp), "-c:a", "aac", "-b:a", "192k", str(OUT / f"{name}.m4a")], check=True)
        tmp.replace(OUT / f"{name}.wav")

    for step in STEPS:
        ck_path = RUN / f"step={step}.ckpt"
        if not ck_path.exists():
            print("missing", ck_path, flush=True)
            continue
        todo = [(s, w, a) for s, w in crops for a in ARMS if f"st{step}__{s}__{a}" not in done]
        need_ref = [(s, w) for s, w in crops if f"ref__{s}" not in done]
        if not todo and not need_ref:
            continue
        sam, _ = load_model(ck_path, "cuda:0")
        with torch.no_grad():
            for s, w in need_ref:
                z = torch.from_numpy(np.load(LAT / f"{s}.npy")[..., w: w + T].astype(np.float32)).reshape(1, 256, T).to("cuda:0", next(sam.same.parameters()).dtype)
                a = sam.same.decode(z).float().cpu()
                if bool(torch.isfinite(a).all()):
                    save(a[0], f"ref__{s}")
                    with log.open("a") as f:
                        f.write(json.dumps(dict(id=f"ref__{s}", step=0, stem=s, window=w, arm="ref")) + "\n")
        need_ref = []
        by = dict(crops)
        names = [c[0] for c in crops]
        with log.open("a") as f:
            for s, w, arm in todo:
                own = stream(s, w)
                other = names[(names.index(s) + 1) % len(names)]
                st = {"true": own, "shuffled": shuffled(own), "foreign": stream(other, by[other]), "zero": np.zeros_like(own)}[arm]
                a = gen(sam, st)
                if not bool(torch.isfinite(a).all()) or float(a.std()) < 1e-3:
                    print("FAULT", s, arm, flush=True)
                    continue
                cid = f"st{step}__{s}__{arm}"
                save(a[0][:, : int(DUR * 44100)], cid)
                f.write(json.dumps(dict(id=cid, step=step, stem=s, window=w, arm=arm, std=round(float(a.std()), 4))) + "\n")
                f.flush()
        del sam
        torch.cuda.empty_cache()


def score():
    from e24_build_contour_packs import skyline
    from muscriptor import TranscriptionModel

    cells = [json.loads(l) for l in (OUT / "cells.jsonl").read_text().splitlines()]
    crops = json.loads((OUT / "crops.json").read_text())
    by = dict(map(tuple, crops))
    names = [c[0] for c in crops]
    model = TranscriptionModel.load_model("medium", device="cuda")
    midd = OUT / "midi"
    midd.mkdir(exist_ok=True)
    rows = []

    def line_of(cid):
        """The same skyline as the pack, from a MuScriptor transcription of the clip."""
        p = midd / f"{cid}.mid"
        if not p.exists():
            p.write_bytes(model.transcribe_to_midi(OUT / f"{cid}.wav"))
        return skyline(str(p))[:T]

    def corr(line, st):
        v = (line >= 0) & (st[1] > 0)
        if v.sum() < 16 or np.std(line[v]) == 0 or np.std(st[0][v]) == 0:
            return None
        return float(np.corrcoef(line[v], st[0][v])[0, 1])

    for c in cells:
        s, w = c["stem"], c["window"]
        own = stream(s, w)
        line = line_of(c["id"])
        other = names[(names.index(s) + 1) % len(names)]
        fed = {"true": own, "ref": own, "shuffled": shuffled(own), "foreign": stream(other, by[other]), "zero": own}[c["arm"]]
        foreign = [corr(line, stream(n, by[n])) for n in names if n != s]
        rows.append(dict(c, voiced=float((line >= 0).mean()), r_fed=corr(line, fed), r_own=corr(line, own), r_foreign=float(np.mean([x for x in foreign if x is not None] or [0.0]))))
    (OUT / "scores.json").write_text(json.dumps(rows, indent=0))
    m = lambda xs: round(float(np.mean([x for x in xs if x is not None])), 3) if any(x is not None for x in xs) else None
    L = ["corr(MuScriptor line of the audio, stream). r_fed: the stream this clip was given. r_own: the crop's true stream. r_foreign: other crops' streams.", ""]
    refs = [r for r in rows if r["arm"] == "ref"]
    L.append(f"POSITIVE CONTROL (decoded crop): r_own {m([r['r_own'] for r in refs])} r_foreign {m([r['r_foreign'] for r in refs])} over {len(refs)} crops; {[round(r['r_own'], 2) if r['r_own'] is not None else None for r in refs]}")
    for st in STEPS:
        sub = [r for r in rows if r["step"] == st]
        if not sub:
            continue
        line = f"step {st}: " + "; ".join(f"{a} r_fed {m([r['r_fed'] for r in sub if r['arm'] == a])} r_own {m([r['r_own'] for r in sub if r['arm'] == a])}" for a in ARMS)
        tr = {r["stem"]: r for r in sub if r["arm"] == "true"}
        sh = {r["stem"]: r for r in sub if r["arm"] == "shuffled"}
        d = [tr[k]["r_fed"] - sh[k]["r_fed"] for k in tr if k in sh and tr[k]["r_fed"] is not None and sh[k]["r_fed"] is not None]
        L.append(line + f" | true - shuffled {m(d)}, positive {sum(x > 0 for x in d)}/{len(d)}")
    (OUT / "report.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


def gate_stage():
    """Disintegration gate: each fed arm against the zero arm of the same checkpoint and crop."""
    import sqlite3
    from collections import Counter

    from control_head_disintegration_eval import DB, gate

    cells = [json.loads(l) for l in (OUT / "cells.jsonl").read_text().splitlines()]
    db = sqlite3.connect(DB)
    cols = [r[1] for r in db.execute("PRAGMA table_info(metrics)").fetchall()]
    rows = {r[0]: dict(zip(cols, r)) for r in db.execute("select * from metrics where path like ?", (f"{OUT}/%",))}
    met = lambda c: rows.get(str(OUT / f"{c['id']}.m4a"))
    base = {(c["step"], c["stem"]): met(c) for c in cells if c["arm"] == "zero"}
    res = {}
    for c in cells:
        if c["arm"] in ("zero", "ref"):
            continue
        k = (c["step"], c["arm"])
        r = res.setdefault(k, dict(n=0, fails=0, why=Counter(), missing=0))
        m, b = met(c), base.get((c["step"], c["stem"]))
        if not m or not b:
            r["missing"] += 1
            continue
        bad, why, _ = gate(m, b, rhythmic=True)
        r["n"] += 1
        r["fails"] += int(bad)
        r["why"].update(x.split("(")[0] for x in why)
    L = ["", "GATE (fed arm vs zero arm, same checkpoint and crop):"]
    for (st, arm), r in sorted(res.items()):
        L.append(f"step {st} {arm}: {r['fails']}/{r['n']} fail {dict(r['why'])}" + (f" missing metrics {r['missing']}" if r["missing"] else ""))
    with (OUT / "report.txt").open("a") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("render", "score", "gate"), required=True)
    a = ap.parse_args()
    {"render": render, "score": score, "gate": gate_stage}[a.stage]()
