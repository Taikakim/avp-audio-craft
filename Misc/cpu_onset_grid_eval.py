#!/usr/bin/env python3
"""CPU onset-density control eval via the ONNX control-eval server — CANONICAL config.

For a running control_eval_server (one head's control DiT ONNX on the ORT CPU EP), sweep
the CANONICAL THREE PROMPTS x gains x densities, collect the server's wavs, measure onset
density with librosa (same measurement as sa3_control/onset_eval.py), and write
onset_eval.json ({prompt_idx, prompt, gain, requested, measured}) + run_meta.json with the
per-(prompt,gain) and per-gain correlations. GPU-free; lets the FiLM A/B run while the GPU
trains DoRA.

Gains default to the EFFECTIVE range (<=3) — above ~2-3 the control oversteers into
onset-smear/saturation (per operator experience), so those cells are not informative.

NOTE vs the historical GPU multi_eval.py: generation is ONNX/CPU at fewer steps (24) rather
than torch/GPU at 50, but every head here goes through the IDENTICAL path so the A/B is
internally consistent. Verdict remains audition-first; this is the authority instrument.

Server must already be up on --queue-root. Run:
    mir/bin/python Misc/cpu_onset_grid_eval.py --queue-root Q --out <dir> \
        --gains 0.5,1,2,3 --densities 3,6,7,8,9,12 --steps 24 --seed 1234 \
        --run onset_FusionCaut --optimizer fusion+cautious --lr 1e-4
"""
import argparse, json, os, shutil, sys
from pathlib import Path

sys.path.insert(0, "/home/kim/Projects/SAO/onnx")
from submit_control_job import submit, wait_for_server_ready, _new_job_id  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import librosa  # noqa: E402

CANONICAL_PROMPTS = [
    "aggressive upbeat goa trance",
    "energetic acid techno, 130 BPM, driving analog bassline, crisp drum machine",
    "psytrance, 140 bpm",
]


def onset_density(wav_path):
    y, sr = sf.read(wav_path)
    if y.ndim > 1:
        y = y.mean(axis=1)
    y = y.astype("float32")
    dur = len(y) / sr
    on = librosa.onset.onset_detect(y=y, sr=sr, units="time")
    return len(on) / dur, dur


def _corr(xs, ys):
    return round(float(np.corrcoef(xs, ys)[0, 1]), 3) if len(set(xs)) > 1 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--prompts", default="||".join(CANONICAL_PROMPTS),
                    help="'||'-separated; defaults to the canonical three")
    ap.add_argument("--gains", default="0.5,1,2,3")          # effective range (<=3)
    ap.add_argument("--densities", default="3,6,7,8,9,12")   # canonical multiprompt set
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg", type=float, default=6.0)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--run", default=""); ap.add_argument("--optimizer", default="")
    ap.add_argument("--lr", default=""); ap.add_argument("--notes", default="")
    ap.add_argument("--timeout", type=float, default=1800.0)
    a = ap.parse_args()

    a.out.mkdir(parents=True, exist_ok=True)
    if not wait_for_server_ready(a.queue_root, timeout=a.timeout):
        sys.exit(f"[fatal] server not ready at {a.queue_root}/.server_ready")

    prompts = [p for p in a.prompts.split("||") if p]
    gains = [float(x) for x in a.gains.split(",")]
    dens = [float(x) for x in a.densities.split(",")]
    outbox = a.queue_root / "outbox"
    rows = []
    for pi, prompt in enumerate(prompts):
        for g in gains:
            for d in dens:
                name = f"p{pi}_g{g:g}_d{d:g}"
                job = {"job_id": _new_job_id(), "prompt": prompt, "onset_density": d, "gain": g,
                       "steps": a.steps, "cfg_scale": a.cfg, "seed": a.seed, "out_name": name}
                res = submit(a.queue_root, job, timeout=a.timeout)
                wav = outbox / f"{name}.wav"
                if not wav.exists() and res.get("wav"):
                    wav = Path(res["wav"])
                if not wav.exists():
                    print(f"[warn] no wav for {name}; skip", flush=True); continue
                od, dur = onset_density(str(wav))
                dst = a.out / f"onset_p{pi}_g{g:g}_d{d:g}.wav"
                if not dst.exists():
                    try: os.link(wav, dst)
                    except OSError: shutil.copy(wav, dst)
                rows.append({"prompt_idx": pi, "prompt": prompt, "gain": g,
                             "requested": d, "measured": round(od, 3)})
                print(f"  p{pi} g{g:g} d{d:g} -> {od:.2f} onsets/s", flush=True)

    # correlations: per-gain (pooled over prompts) and per (prompt,gain)
    corr_gain = {}
    for g in gains:
        gr = [r for r in rows if r["gain"] == g]
        corr_gain[f"{g:g}"] = _corr([r["requested"] for r in gr], [r["measured"] for r in gr])
    corr_pg = {}
    for pi in range(len(prompts)):
        for g in gains:
            gr = [r for r in rows if r["gain"] == g and r["prompt_idx"] == pi]
            corr_pg[f"p{pi}_g{g:g}"] = _corr([r["requested"] for r in gr], [r["measured"] for r in gr])

    json.dump(rows, open(a.out / "onset_eval.json", "w"), indent=2)
    meta = {"dir": a.out.name, "run": a.run, "optimizer": a.optimizer, "lr": a.lr,
            "scalar_field": "onset_density", "corr_per_gain": corr_gain, "corr_prompt_gain": corr_pg,
            "eval": {"prompts": prompts, "gains": gains, "densities": dens, "steps": a.steps,
                     "cfg": a.cfg, "seed": a.seed,
                     "method": "CPU ONNX control-eval server (ORT CPU EP), canonical 3-prompt sweep"},
            "purpose": a.notes}
    json.dump(meta, open(a.out / "run_meta.json", "w"), indent=2)
    print(f"[done] {a.out}/onset_eval.json ({len(rows)} cells) | corr/gain: {corr_gain}")


if __name__ == "__main__":
    main()
