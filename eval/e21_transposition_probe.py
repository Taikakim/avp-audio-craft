#!/usr/bin/env python3
# Owner: CONTINUITY (created 2026-10-28)
"""e21_transposition_probe.py -- EXPERIMENTS E21: is our chroma steering transposition-equivariant?

WHY (Kim 2026-10-27, after the Equivariant Music Transformer paper 2608.03920): if we steer toward a chord and toward the
same chord moved up k semitones, does the output move by k? A symbolic transformer was not equivariant until trained to be;
our LatCH chroma heads were never tested for it.

DESIGN. Reuses the chroma-steering renderer (eval/chroma_steer_render.py: build_target_raw, in-process model.generate with
target_raw, cosine loss) and its meter (the OUTPUT audio's SAME chroma folded to 12 bins, bass and mid bands).
  heads    hpcp (12-d), same_chroma (384-d)          prompts  piano, synth        seeds 1234, 5678
  targets  static major triad on C, Eb, F#, A  = k 0, 3, 6, 9 semitones (multiples of 3 so the 128-bin bands roll exactly)
  gains    1024, 2048 (+ one gain-0 baseline per prompt/seed)
SCORE.  (a) steering: cos(output, target_k) - cos(baseline, target_k).  (b) equivariance: for each steered cell with k > 0,
r* = argmax_r cos(roll(p_k0, r), p_k) over the 12 rotations, where p_k0 is the k = 0 cell with the same head/prompt/seed/gain;
hit if r* == k (chance 1/12).  (c) positive control: the k = 0 render pitch-shifted by k with bungee (never sox;
eval/e21_bungee_posctl.py) must score a hit, or the meter cannot see a transposition.
Modes: --render (GPU, take the lock first), --score (CPU).
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
import argparse, json, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chroma_steer_render as CSR  # noqa: E402  (build_target_raw, sc, T, HEADS_DIR, FPS, STEPS, CFG)

OUT = Path("/run/media/kim/Mantu/sa3_control_runs/e21_transposition_probe_20261028")
HEADS = [("hpcp", "latch_sa3_hpcp_best.pt", 12), ("same_chroma", "latch_sa3_same_chroma_best.pt", 384)]
PROMPTS = ["piano", "synth"]
SEEDS = [1234, 5678]
KEYS = {0: "C", 3: "Eb", 6: "F#", 9: "A"}
GAINS = [1024, 2048]
DUR = 20.05


def name(head, prompt, k, gain, seed):
    return f"e21__{head}__{prompt}__k{k}__g{gain}__s{seed}.wav" if gain else f"e21__base__{prompt}__s{seed}.wav"


def profile(path):
    import soundfile as sf
    x, sr = sf.read(path, always_2d=True)                       # (T, C)
    ch = CSR.sc.compute_same_chroma(x, sr, align_to_latent=False)  # (3, 128, M)
    out = {}
    for bi, band in ((0, "bass"), (1, "mid")):
        v = CSR.sc.fold_to_12(ch[bi].mean(axis=-1)).astype(np.float64)
        out[band] = v / (np.linalg.norm(v) + 1e-9)
    return out


def render():
    import torch
    from stable_audio_3 import StableAudioModel
    from sa3_control.audio_io import save_audio
    OUT.mkdir(parents=True, exist_ok=True)
    meta = OUT / "run_meta.json"
    if not meta.exists():
        meta.write_text(json.dumps({
            "run": OUT.name, "created": time.strftime("%Y-%m-%d %H:%M"), "owner": "CONTINUITY",
            "purpose": "EXPERIMENTS E21 (Kim 2026-10-27): is chroma steering transposition-equivariant? Static major triads on C/Eb/F#/A, hpcp and same_chroma heads.",
            "hypothesis": "If the heads steer pitch class, the output chroma of the k-shifted target is the k=0 output rotated by k.",
            "kill": "Hit rate near the bungee positive control and steering delta > 0 => equivariant, no regulariser needed; close E21.",
            "recipe": {"model": "medium-base", "steps": CSR.STEPS, "cfg": CSR.CFG, "duration": DUR, "gains": GAINS,
                       "heads": [h[0] for h in HEADS], "prompts": PROMPTS, "seeds": SEEDS, "keys": KEYS, "loss": "cosine"},
            "status": "running", "result": None, "kim_feedback": None, "script": "eval/e21_transposition_probe.py"}, indent=1))
    n_frames = int(round(DUR * CSR.FPS))
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    prompts = {p["id"]: p["text"] for p in CSR.T.SOLO_INSTRUMENTS}
    cells = [(None, None, 0, 0, p, s) for p in PROMPTS for s in SEEDS]
    cells += [(h, d, k, g, p, s) for h, _, d in [(h[0], h[1], h[2]) for h in HEADS] for k in KEYS for g in GAINS for p in PROMPTS for s in SEEDS]
    ckpt = {h[0]: CSR.HEADS_DIR / h[1] for h in HEADS}
    for head, dim, k, g, p, s in cells:
        out = OUT / name(head, p, k, g, s)
        if out.exists():
            continue
        t0 = time.time()
        gen = dict(prompt=prompts[p], duration=DUR, steps=CSR.STEPS, cfg_scale=CSR.CFG, seed=s)
        if g:
            tgt = {"id": KEYS[k], "kind": "static", "chord": KEYS[k]}
            gen["latch_configs"] = [{"model_path": str(ckpt[head]), "target_raw": CSR.build_target_raw(dim, tgt, n_frames),
                                     "weight": 1.0, "loss_type": "cosine"}]
            gen["latch_hparams"] = {"rho": float(g), "mu": float(g)}
        audio = model.generate(**gen)
        save_audio(str(out), audio[0].float().cpu(), CSR.sc.SAME_SR)
        print(f"[e21] {out.name} {time.time() - t0:.1f}s", flush=True)


def score():
    rows, res = [], {}
    prof = {}
    def P(fn):
        if fn not in prof:
            prof[fn] = profile(str(OUT / fn))
        return prof[fn]
    tgt12 = {}
    from sa3_control.chroma_guided_generator import chord_to_chroma
    for k, c in KEYS.items():
        v = chord_to_chroma(c).astype(np.float64); tgt12[k] = v / np.linalg.norm(v)
    def best_shift(a, b):
        sims = [float(np.roll(a, r) @ b) for r in range(12)]
        return int(np.argmax(sims)), sims
    summary = {}
    for head, _, _ in HEADS:
        for g in GAINS:
            for band in ("bass", "mid"):
                deltas, hits, n = [], 0, 0
                for p in PROMPTS:
                    for s in SEEDS:
                        base = P(name(None, p, 0, 0, s))[band]
                        p0 = P(name(head, p, 0, g, s))[band]
                        for k in KEYS:
                            pk = P(name(head, p, k, g, s))[band]
                            deltas.append(float(pk @ tgt12[k] - base @ tgt12[k]))
                            if k:
                                r, _ = best_shift(p0, pk); hits += int(r == k); n += 1
                summary[f"{head}|g{g}|{band}"] = {"steer_delta_mean": round(float(np.mean(deltas)), 4),
                                                  "equivariance_hits": f"{hits}/{n}", "chance": "1/12"}
    # positive control: bungee-shifted k=0 renders, posctl__<k0 file stem>__k<k>.wav
    pc = {}
    for f in sorted(OUT.glob("posctl__*.wav")):
        stem, kk = f.stem.rsplit("__k", 1); kk = int(kk)
        src = stem[len("posctl__"):] + ".wav"
        for band in ("bass", "mid"):
            r, _ = best_shift(P(src)[band], P(f.name)[band])
            pc.setdefault(band, [0, 0]); pc[band][0] += int(r == kk); pc[band][1] += 1
    summary["positive_control_bungee"] = {b: f"{h}/{n}" for b, (h, n) in pc.items()}
    (OUT / "e21_results.json").write_text(json.dumps(summary, indent=1))
    for k, v in summary.items():
        print(k, v)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--render", action="store_true"); g.add_argument("--score", action="store_true")
    a = ap.parse_args()
    render() if a.render else score()
