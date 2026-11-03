#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-11-03)
"""d5_adaptive_grid.py -- EXPERIMENTS D5: does a step grid that follows the flow's curvature reduce discretization error on base renders?

2608.15103 section 5.2 equidistributes sqrt(local growth) and reports -7 to -16% discretization error at N = 16 to 64. Ours:
  pilot     3 prompts not in the test set, Euler at N = 64 on the model's own schedule. Velocity v_i = (x_{i+1} - x_i) / dt_i from the path,
            growth g(t) = ||dv/dt|| normalised per prompt, averaged. One global curve.
  adaptive  grid for N steps: equal quantiles of the integral of sqrt(g(t)) dt over t in (0, 1].
  test      14 canonical prompts with their own seeds, base model, cfg 7, Euler. For N in 16, 24, 32: default schedule vs adaptive.
            Reference for each prompt: N = 256 on the default schedule.
  error     ||z_N - z_ref|| / ||z_ref|| on the final latent, paired per prompt. Clips kept for Audiobox PQ and listening.
Sharpens a render at best; it adds nothing to melody (per the plan). Base model only: an adapter may have a different curve.
Outputs in ~/evals_aac/control_runs/d5_adaptive_grid_20261103/: cells.jsonl, grids.json, report.txt, clips, run_meta.json.
RUN: eval/run_d5.sh
"""
import json
import os
import subprocess
import sys
from pathlib import Path

for k, v in {"FLASH_ATTENTION_TRITON_AMD_ENABLE": "FALSE", "PYTORCH_TUNABLEOP_ENABLED": "0", "MIOPEN_FIND_MODE": "2"}.items():
    os.environ.setdefault(k, v)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "control"))
sys.path.insert(0, str(HERE.parent / "stable-audio-3"))
sys.path.insert(0, str(HERE))
import numpy as np
import torch

OUT = Path("/home/kim/evals_aac/control_runs/d5_adaptive_grid_20261103")
DUR = 23.79
CFG = 7.0
NS = (16, 24, 32)
REF_N = 256
PILOT = [("goa trance, melodic mood, 140 bpm", 11), ("mid 90s psy-trance, 146 bpm", 22), ("2010s techno, space mood, 132 bpm", 33)]


def main():
    import stable_audio_3.inference.sampling as S
    import model_matrix_gen as M
    from sa3_control.audio_io import save_audio
    from stable_audio_3 import StableAudioModel

    OUT.mkdir(parents=True, exist_ok=True)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda:0")
    default_build = S.build_schedule
    prompts = [dict(id=p["id"], text=p.get("text") or p.get("prompt"), seed=int(p["seed"])) for p in M.build_prompts(n_per_band=3, n_kimlong=3)]

    def run(text, seed, n, grid=None, callback=None):
        sink = []
        if grid is not None:
            S.build_schedule = lambda *a, **k: torch.tensor(grid, device=k.get("device", "cpu"), dtype=torch.float32)
        try:
            kw = dict(callback=callback) if callback else {}
            a = model.generate(prompt=text, duration=DUR, steps=n, cfg_scale=CFG, seed=seed, batch_size=1, sampler_type="euler", latents_sink=sink, **kw)
        finally:
            S.build_schedule = default_build
        return a.float().cpu(), sink[0].float().cpu()

    # Pilot: growth along the path on the model's own schedule
    captured = []
    orig_euler = S.sample_discrete_euler

    def spy(m, x, sigmas, callback=None, disable_tqdm=False, **extra):
        captured.append(sigmas.detach().float().cpu().numpy().copy())
        return orig_euler(m, x, sigmas=sigmas, callback=callback, disable_tqdm=disable_tqdm, **extra)

    S.sample_discrete_euler = spy
    grid_t = np.linspace(1, 0, 501)
    curves = []
    for text, seed in PILOT:
        xs = []
        run(text, seed, 64, callback=lambda d: xs.append(d["x"].detach().float().cpu()))
        sig = captured[-1].ravel()
        n = min(len(xs), len(sig) - 1)
        v = [(xs[i + 1] - xs[i]) / float(sig[i + 1] - sig[i]) for i in range(n - 1)]
        tm = np.array([(sig[i] + sig[i + 1]) / 2 for i in range(n - 1)])
        g = np.array([float((v[i + 1] - v[i]).norm()) / abs(float(tm[i + 1] - tm[i])) for i in range(len(v) - 1)])
        tg = (tm[:-1] + tm[1:]) / 2
        g = g / g.mean()
        curves.append(np.interp(grid_t[::-1], tg[::-1], g[::-1])[::-1])
    S.sample_discrete_euler = orig_euler
    g = np.mean(curves, axis=0)
    dens = np.sqrt(np.maximum(g, 1e-9))
    cum = np.concatenate([[0], np.cumsum((dens[:-1] + dens[1:]) / 2 * np.abs(np.diff(grid_t)))])
    cum /= cum[-1]
    grids = {n: np.interp(np.linspace(0, 1, n + 1), cum, grid_t).tolist() for n in NS}
    for n in NS:
        grids[n][0], grids[n][-1] = 1.0, 0.0
    default_grids = {n: default_build(steps=n, sigma_max=1.0, dist_shift=model.model.sampling_dist_shift, effective_seq_len=None, fallback_seq_len=int(DUR * 44100 / model.model.pretransform.downsampling_ratio),
                                      include_endpoint=True).cpu().numpy().ravel().tolist() for n in NS}
    (OUT / "grids.json").write_text(json.dumps({"adaptive": grids, "default": default_grids, "growth_t": grid_t[::25].tolist(), "growth": g[::25].round(4).tolist()}, indent=1))
    print("adaptive 24:", np.round(grids[24], 3).tolist(), flush=True)
    print("default  24:", np.round(default_grids[24], 3).tolist(), flush=True)

    def save(a, name):
        tmp = OUT / "_t.wav"
        save_audio(str(tmp), a[0], 44100, normalize=True)
        subprocess.run(["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(tmp), "-c:a", "aac", "-b:a", "192k", str(OUT / f"{name}.m4a")], check=True)
        tmp.unlink()

    log = (OUT / "cells.jsonl").open("a")
    run(prompts[0]["text"], prompts[0]["seed"], 8)                # first render of a process, not used
    for p in prompts:
        ar, zr = run(p["text"], p["seed"], REF_N)
        save(ar, f"{p['id']}__ref{REF_N}")
        for n in NS:
            for arm, grid in (("default", None), ("adaptive", grids[n])):
                a, z = run(p["text"], p["seed"], n, grid=grid)
                err = float((z - zr).norm() / zr.norm())
                save(a, f"{p['id']}__{arm}__n{n}")
                log.write(json.dumps(dict(pid=p["id"], seed=p["seed"], n=n, arm=arm, err=round(err, 5), audio_std=round(float(a.std()), 5), finite=bool(torch.isfinite(a).all()))) + "\n")
                log.flush()
        print("done", p["id"], flush=True)
    log.close()
    rows = [json.loads(l) for l in (OUT / "cells.jsonl").read_text().splitlines()]
    L, rng = [], np.random.default_rng(1)
    for n in NS:
        d = {r["pid"]: r["err"] for r in rows if r["n"] == n and r["arm"] == "default"}
        a = {r["pid"]: r["err"] for r in rows if r["n"] == n and r["arm"] == "adaptive"}
        ids = sorted(set(d) & set(a))
        ratio = np.array([a[i] / d[i] - 1 for i in ids]) * 100
        boot = rng.choice(ratio, size=(4000, len(ratio))).mean(1)
        L.append(f"N={n}: mean error default {np.mean([d[i] for i in ids]):.4f} adaptive {np.mean([a[i] for i in ids]):.4f}; change {ratio.mean():+.1f}% [{np.percentile(boot, 2.5):+.1f}, {np.percentile(boot, 97.5):+.1f}]; lower on {int((ratio < 0).sum())}/{len(ids)} prompts")
    (OUT / "report.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L), flush=True)


if __name__ == "__main__":
    main()
