#!/usr/bin/env python3
"""Composed control x LatCH sweep driver — one CONDITION per invocation.

Spec: docs/superpowers/specs/2026-07-03-composed-control-latch-sweep.md. The condition
matrix is (server graph = adapter) x (--latch on/off); the adapter is chosen by which
control-DiT ONNX the control_eval_server was booted with, so this driver runs once per
condition against that server. Kim's grid verbatim: canonical 3 prompts x seeds
{1234,4242} x gains {1,2,3} x densities {1,3,5,6,7,7.5,8,9,12} = 162 cells/condition.

Extends Misc/cpu_onset_grid_eval.py with: two seeds, spectral flatness (smear guard),
and the latch payload (requested density -> raw envelope target via the frozen corpus
map onnx/envelope_density_map.json; density 12 is outside corpus support by design —
rows carry in_support so the ceiling cells are analyzed separately).

Run (mir venv for librosa):
    mir/bin/python Misc/composed_sweep_eval.py --queue-root composed_eval_queue \
        --out <dir> --condition F_fusion_latch --latch --rho-mu 512 \
        --run onset_Fusion_lr1e-4_randomcrop --notes "Stage 1 cell F"
"""
import argparse, json, os, shutil, sys
from pathlib import Path

SAO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SAO / "onnx"))
from submit_control_job import submit, wait_for_server_ready, _new_job_id  # noqa: E402
from envelope_density_map import density_to_env  # noqa: E402

CANONICAL_PROMPTS = [
    "aggressive upbeat goa trance",
    "energetic acid techno, 130 BPM, driving analog bassline, crisp drum machine",
    "psytrance, 140 bpm",
]
DEFAULT_HEAD = str(SAO / "stable-audio-3/latch_weights_sa3_medium/latch_sa3_onset_envelope_best.pt")


def build_job(prompt, prompt_idx, seed, gain, density, steps, cfg, fit, latch_cfg, name):
    """One queue job for a grid cell. latch_cfg None -> plain control render;
    else {head_ckpt, rho, mu} -> composed render with the corpus-mapped raw target.
    Returns (job, in_support) — in_support False marks the extrapolated ceiling cells."""
    job = {"job_id": _new_job_id(), "prompt": prompt, "onset_density": float(density),
           "gain": float(gain), "steps": int(steps), "cfg_scale": float(cfg),
           "seed": int(seed), "out_name": name}
    raw, in_support = density_to_env(density, fit, return_in_support=True)
    if latch_cfg:
        job["latch"] = {"head_ckpt": latch_cfg["head_ckpt"], "target_raw": raw,
                        "rho": float(latch_cfg["rho"]), "mu": float(latch_cfg["mu"])}
    return job, in_support


def measure(wav_path):
    import numpy as np  # noqa: F401
    import soundfile as sf
    import librosa
    y, sr = sf.read(wav_path)
    if y.ndim > 1:
        y = y.mean(axis=1)
    y = y.astype("float32")
    dur = len(y) / sr
    on = librosa.onset.onset_detect(y=y, sr=sr, units="time")
    flat = float(librosa.feature.spectral_flatness(y=y).mean())
    return len(on) / dur, flat


def _corr(xs, ys):
    import numpy as np
    return round(float(np.corrcoef(xs, ys)[0, 1]), 3) if len(set(xs)) > 1 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--condition", required=True,
                    help="condition tag, e.g. E_fusion / F_fusion_latch / A_cc / B_cc_latch")
    ap.add_argument("--prompts", default="||".join(CANONICAL_PROMPTS))
    ap.add_argument("--seeds", default="1234,4242")
    ap.add_argument("--gains", default="1,2,3")
    ap.add_argument("--densities", default="1,3,5,6,7,7.5,8,9,12")
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg", type=float, default=6.0)
    ap.add_argument("--latch", action="store_true")
    ap.add_argument("--head-ckpt", default=DEFAULT_HEAD)
    ap.add_argument("--rho-mu", type=float, default=512.0,
                    help="guidance strength (rho=mu), from the calibration probe")
    ap.add_argument("--env-map", type=Path, default=SAO / "onnx/envelope_density_map.json")
    ap.add_argument("--run", default=""); ap.add_argument("--notes", default="")
    ap.add_argument("--timeout", type=float, default=1800.0)
    a = ap.parse_args()

    a.out.mkdir(parents=True, exist_ok=True)
    fit = json.load(open(a.env_map))
    latch_cfg = ({"head_ckpt": a.head_ckpt, "rho": a.rho_mu, "mu": a.rho_mu}
                 if a.latch else None)
    if not wait_for_server_ready(a.queue_root, timeout=a.timeout):
        sys.exit(f"[fatal] server not ready at {a.queue_root}/.server_ready")

    prompts = [p for p in a.prompts.split("||") if p]
    seeds = [int(x) for x in a.seeds.split(",")]
    gains = [float(x) for x in a.gains.split(",")]
    dens = [float(x) for x in a.densities.split(",")]
    outbox = a.queue_root / "outbox"
    rows, n_total = [], len(prompts) * len(seeds) * len(gains) * len(dens)
    for pi, prompt in enumerate(prompts):
        for seed in seeds:
            for g in gains:
                for d in dens:
                    name = f"{a.condition}_p{pi}_s{seed}_g{g:g}_d{d:g}"
                    job, in_support = build_job(prompt, pi, seed, g, d, a.steps, a.cfg,
                                                fit, latch_cfg, name)
                    res = submit(a.queue_root, job, timeout=a.timeout)
                    wav = outbox / f"{name}.wav"
                    if not wav.exists() and res.get("paths", {}).get("wav"):
                        wav = Path(res["paths"]["wav"])
                    if not wav.exists():
                        print(f"[warn] no wav for {name}; skip", flush=True); continue
                    od, flat = measure(str(wav))
                    dst = a.out / f"{name}.wav"
                    if not dst.exists():
                        try: os.link(wav, dst)
                        except OSError: shutil.copy(wav, dst)
                    rows.append({"prompt_idx": pi, "prompt": prompt, "seed": seed,
                                 "gain": g, "requested": d, "measured": round(od, 3),
                                 "flatness": round(flat, 5), "in_support": in_support})
                    print(f"  [{len(rows)}/{n_total}] p{pi} s{seed} g{g:g} d{d:g} -> "
                          f"{od:.2f} onsets/s flat {flat:.4f}", flush=True)

    corr_gain = {}
    for g in gains:
        gr = [r for r in rows if r["gain"] == g]
        corr_gain[f"{g:g}"] = _corr([r["requested"] for r in gr], [r["measured"] for r in gr])
    corr_pg = {}
    for pi in range(len(prompts)):
        for g in gains:
            gr = [r for r in rows if r["gain"] == g and r["prompt_idx"] == pi]
            corr_pg[f"p{pi}_g{g:g}"] = _corr([r["requested"] for r in gr],
                                             [r["measured"] for r in gr])

    json.dump(rows, open(a.out / "onset_eval.json", "w"), indent=2)
    meta = {"dir": a.out.name, "condition": a.condition, "run": a.run,
            "scalar_field": "onset_density",
            "latch": (dict(latch_cfg, env_map=str(a.env_map)) if latch_cfg else None),
            "corr_per_gain": corr_gain, "corr_prompt_gain": corr_pg,
            "eval": {"prompts": prompts, "seeds": seeds, "gains": gains, "densities": dens,
                     "steps": a.steps, "cfg": a.cfg,
                     "method": "CPU ONNX composed eval (control-DiT +/- LatCH guidance), "
                               "spec 2026-07-03-composed-control-latch-sweep"},
            "purpose": a.notes}
    json.dump(meta, open(a.out / "run_meta.json", "w"), indent=2)
    print(f"[done] {a.condition}: {a.out}/onset_eval.json ({len(rows)} cells) | "
          f"corr/gain: {corr_gain}", flush=True)


if __name__ == "__main__":
    main()
