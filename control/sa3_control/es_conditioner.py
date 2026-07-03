"""Echo-location ES for the FiLM scalar conditioner (#2 in the perceptual-signal plan).

The conditioner runs HOST-SIDE in numpy on the CPU eval path (onnx/sa3_control_onnx.py::
control_tokens_from_npz over the exported cond.npz) — so we can evolve it with NO export
cycle and NO gradients: perturb the weights in memory, compute candidate control tokens,
render via the file-drop control_eval_server (job field ``raw_control_tokens_npy``), and
score the ACTUAL rendered audio with librosa. The fitness is the real measurement — the
thing RF loss (and even the differentiable cc-probe) can only approximate. This is the
"throw rocks and listen" idea fully realized: gradient-free, meaning-first.

Algorithm: OpenAI-ES (Salimans et al. 2017) — antithetic pairs + centered-rank fitness
shaping — on a REDUCED parameter set (default: tokens + film0 + film2 bias, ~37k params;
film2_w's 6.3M stay frozen at their trained values). Small populations, expensive fitness
(~1 render per grid cell per candidate): keep the grid mini and the generations few; this
is a REFINER on top of a trained conditioner, not from-scratch search.

Spec + risks: docs/superpowers/specs/2026-07-02-perceptual-signal-optimizer-directions.md.
Reward-hacking note: the fitness is the same librosa measurement the onset-injection
cheat games — we LOG spectral flatness per candidate as the smear guard and can add it
to the fitness (--lambda-flat) once a baseline is measured.

Run (any venv with numpy+soundfile+librosa, server already up):
    mir/bin/python -m sa3_control.es_conditioner \
        --cond-npz <ctrl.cond.npz> --queue-root <Q> --out-dir <run_dir> \
        --generations 20 --pairs 6 --sigma 0.02 --lr 0.01
"""
from __future__ import annotations

import argparse, json, os, sys, time
from pathlib import Path

import numpy as np

# Keys evolved by default: everything EXCEPT film2_w (6.3M — frozen; the rest is ~37k).
DEFAULT_EVOLVED_KEYS = ("tokens", "film0_w", "film0_b", "film2_b")

CANONICAL_PROMPTS = [
    "aggressive upbeat goa trance",
    "energetic acid techno, 130 BPM, driving analog bassline, crisp drum machine",
    "psytrance, 140 bpm",
]


# ---------- pure core (unit-tested) ----------

def pack_params(cond: dict, keys=DEFAULT_EVOLVED_KEYS) -> np.ndarray:
    return np.concatenate([np.asarray(cond[k], np.float32).ravel() for k in keys])


def unpack_params(vec: np.ndarray, cond: dict, keys=DEFAULT_EVOLVED_KEYS) -> dict:
    out = dict(cond)
    i = 0
    for k in keys:
        a = np.asarray(cond[k], np.float32)
        out[k] = vec[i:i + a.size].reshape(a.shape).astype(np.float32)
        i += a.size
    return out


def control_tokens_np(cond: dict, raw_value: float) -> np.ndarray:
    """ScalarAttributeEncoder forward from a param DICT (mirror of
    sa3_control_onnx.control_tokens_from_npz, kept in exact parity — tested)."""
    s = np.float32((raw_value - float(cond["mean"])) / float(cond["std"]))
    x = np.array([[s]], np.float32)
    h = x @ np.asarray(cond["film0_w"]).T + np.asarray(cond["film0_b"])
    h = h * (1.0 / (1.0 + np.exp(-h)))                                  # SiLU
    nt, cd = int(cond["n_tokens"]), int(cond["control_dim"])
    gb = (h @ np.asarray(cond["film2_w"]).T + np.asarray(cond["film2_b"])).reshape(1, nt, cd, 2)
    return (np.asarray(cond["tokens"])[None] * (1.0 + gb[..., 0]) + gb[..., 1]).astype(np.float32)


def centered_ranks(fitness: np.ndarray) -> np.ndarray:
    """OpenAI-ES fitness shaping: fitness -> ranks -> uniform in [-0.5, 0.5]."""
    n = len(fitness)
    ranks = np.empty(n, np.float32)
    ranks[np.argsort(fitness)] = np.arange(n, dtype=np.float32)
    return ranks / max(n - 1, 1) - 0.5


def es_step(v: np.ndarray, fitness_fn, n_pairs: int, sigma: float, lr: float,
            rng: np.random.Generator, weight_decay: float = 0.0,
            anchor: np.ndarray | None = None, shaping: str = "rank",
            scales: np.ndarray | None = None, stats_out: dict | None = None) -> np.ndarray:
    """One antithetic-ES generation (OpenAI-ES family, 2026 best-practice trimmings).

    fitness_fn(candidate_vec) -> float (higher better).
    - Rank-shaped ('rank', default) or per-pair sign-shaped ('sign' — EGGROLL
      arXiv:2511.16652; maximally robust when each eval is a noisy render).
    - The shaped gradient is NORMALIZED to unit norm before the lr step: with expensive
      fitness and tiny populations the raw /sigma magnitude is noise; a fixed step size
      gives controlled drift from the trained init.
    - `anchor`: Anchored Weight Decay (arXiv:2605.30148) — decay pulls toward the
      TRAINED weights, not zero; the published fix for ES random-walk drift/forgetting.
    - `scales`: per-coordinate perturbation scale (per-tensor RMS); perturbations and
      the step are applied in the scaled basis so no tensor dominates by sheer norm.
    """
    s = scales if scales is not None else 1.0
    eps = rng.standard_normal((n_pairs, v.size)).astype(np.float32)
    fit = np.empty(2 * n_pairs, np.float32)
    for i in range(n_pairs):
        fit[2 * i] = fitness_fn(v + sigma * s * eps[i])
        fit[2 * i + 1] = fitness_fn(v - sigma * s * eps[i])
    if shaping == "sign":
        w = np.sign(fit[0::2] - fit[1::2]).astype(np.float32)
        grad = (w[:, None] * eps).mean(axis=0)
    else:
        r = centered_ranks(fit)
        grad = ((r[0::2] - r[1::2])[:, None] * eps).mean(axis=0)
    # PER-COORDINATE RMS normalization (v3 fix): global L2-normalizing spreads the step
    # over sqrt(N) dims — at N=37k the center moved ~0.025% RMS/gen while sigma explored
    # at 15% RMS (600:1 explore/exploit — the v2 postmortem). RMS-normalizing makes each
    # coordinate step ~lr*s, commensurate with the perturbations that found the signal.
    g = float(np.sqrt((grad ** 2).mean()))
    if g > 1e-12:
        grad = grad / g
    if stats_out is not None:
        stats_out["spread"] = float(fit.max() - fit.min())
        stats_out["fit_mean"] = float(fit.mean())
    ref = anchor if anchor is not None else v
    return (v + lr * s * grad - lr * weight_decay * (v - ref)).astype(np.float32)


def per_key_scales(cond: dict, keys=DEFAULT_EVOLVED_KEYS) -> np.ndarray:
    """Per-coordinate scale vector: each key's RMS (floored) broadcast over its slots."""
    parts = []
    for k in keys:
        a = np.asarray(cond[k], np.float32)
        parts.append(np.full(a.size, max(float(np.sqrt((a ** 2).mean())), 1e-3), np.float32))
    return np.concatenate(parts)


# ---------- fitness via the CPU eval server ----------

def _measure(wav_path: str):
    """(onsets/sec, spectral flatness mean) — density fitness + smear guard."""
    import soundfile as sf, librosa
    y, sr = sf.read(wav_path)
    if y.ndim > 1:
        y = y.mean(axis=1)
    y = y.astype("float32")
    dur = len(y) / sr
    on = librosa.onset.onset_detect(y=y, sr=sr, units="time")
    flat = float(librosa.feature.spectral_flatness(y=y).mean())
    return len(on) / max(dur, 1e-6), flat


class ServerFitness:
    """Render the mini-grid for a candidate via the file-drop server; return fitness.

    fitness = -mean(|measured - requested|) - lambda_flat * max(0, flat - flat_ref)
    (flat_ref measured once from the base conditioner; guard off until calibrated).
    """

    def __init__(self, queue_root: Path, base_cond: dict, keys, grid, gain: float,
                 steps: int, cfg: float, seed: int, work_dir: Path,
                 lambda_flat: float = 0.0):
        sys.path.insert(0, "/home/kim/Projects/SAO/onnx")
        from submit_control_job import submit, _new_job_id  # noqa
        self._submit, self._new_id = submit, _new_job_id
        self.q, self.base, self.keys = Path(queue_root), base_cond, keys
        self.grid, self.gain, self.steps, self.cfg, self.seed = grid, gain, steps, cfg, seed
        self.work = Path(work_dir); self.work.mkdir(parents=True, exist_ok=True)
        self.lambda_flat, self.flat_ref = lambda_flat, None
        self.n_evals = 0

    def __call__(self, vec: np.ndarray) -> float:
        cond = unpack_params(vec, self.base, self.keys)
        errs, flats = [], []
        for (prompt, dens) in self.grid:
            tok = control_tokens_np(cond, dens)
            tpath = self.work / f"ct_{self.n_evals}_{dens:g}.npy"
            np.save(tpath, tok)
            name = f"es_{self.n_evals}_d{dens:g}"
            job = {"job_id": self._new_id(), "prompt": prompt, "onset_density": dens,
                   "gain": self.gain, "steps": self.steps, "cfg_scale": self.cfg,
                   "seed": self.seed, "out_name": name,
                   "raw_control_tokens_npy": str(tpath)}
            self._submit(self.q, job, timeout=900.0)
            od, flat = _measure(str(self.q / "outbox" / f"{name}.wav"))
            errs.append(abs(od - dens)); flats.append(flat)
            tpath.unlink(missing_ok=True)
        self.n_evals += 1
        f = -float(np.mean(errs))
        if self.lambda_flat > 0 and self.flat_ref is not None:
            f -= self.lambda_flat * max(0.0, float(np.mean(flats)) - self.flat_ref)
        self._last_flat = float(np.mean(flats))
        return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cond-npz", required=True)
    ap.add_argument("--queue-root", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--generations", type=int, default=20)
    ap.add_argument("--pairs", type=int, default=6)
    ap.add_argument("--sigma", type=float, default=0.02)
    ap.add_argument("--lr", type=float, default=0.01)
    ap.add_argument("--weight-decay", type=float, default=1e-3,
                    help="pulls the evolved params back toward the trained init")
    ap.add_argument("--densities", default="3,12", help="mini-grid (keep tiny: cost = renders)")
    ap.add_argument("--prompt-idx", type=int, default=0, help="index into the canonical 3")
    ap.add_argument("--gain", type=float, default=2.0)
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--cfg", type=float, default=6.0)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--lambda-flat", type=float, default=0.0)
    ap.add_argument("--shaping", choices=["rank", "sign"], default="sign",
                    help="'sign' (per-antithetic-pair) is the noisy-fitness-robust default")
    ap.add_argument("--rotate-seeds", type=int, default=3,
                    help="advance the render seed every N generations (anti seed-overfit); 0=never")
    ap.add_argument("--noise-floor", type=int, default=0,
                    help="render the INIT this many times and report the fitness noise floor, "
                         "then exit — run this FIRST; sigma is right when population spread "
                         ">= 3x this floor")
    ap.add_argument("--resume", default="")
    args = ap.parse_args()

    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    base = dict(np.load(args.cond_npz))
    keys = DEFAULT_EVOLVED_KEYS
    v = pack_params(base, keys)
    print(f"[es] evolving {v.size} params ({', '.join(keys)}); film2_w frozen "
          f"({base['film2_w'].size} params)", flush=True)

    grid = [(CANONICAL_PROMPTS[args.prompt_idx], float(d)) for d in args.densities.split(",")]
    fit = ServerFitness(Path(args.queue_root), base, keys, grid, args.gain, args.steps,
                        args.cfg, args.seed, out / "work", args.lambda_flat)

    rng = np.random.default_rng(args.seed)
    anchor = v.copy()                        # AWD anchor = the trained init
    scales = per_key_scales(base, keys)      # per-tensor RMS perturbation scaling
    hist, best_v, best_f = [], v.copy(), -1e18
    if args.resume and os.path.exists(args.resume):
        st = np.load(args.resume)
        v, best_v, best_f = st["v"], st["best_v"], float(st["best_f"])
        print(f"[es] resumed: best_f={best_f:.3f}", flush=True)

    if args.noise_floor > 0:                 # measure repeat-render noise, then exit
        fs = [fit(v) for _ in range(args.noise_floor)]
        print(f"[es] noise floor over {len(fs)} repeats: std={np.std(fs):.4f} "
              f"(mean {np.mean(fs):.3f}) — want population fitness spread >= 3x this",
              flush=True)
        return

    f0 = fit(v)
    fit.flat_ref = fit._last_flat            # calibrate the smear guard on the trained init
    best_v, best_f = v.copy(), f0
    print(f"[es] gen 0 (trained init): fitness={f0:.3f} flat_ref={fit.flat_ref:.4f}", flush=True)
    hist.append({"gen": 0, "fitness": f0, "flat": fit._last_flat})

    for g in range(1, args.generations + 1):
        t0 = time.time()
        if args.rotate_seeds and g % args.rotate_seeds == 0:
            fit.seed += 1                    # rotate CRN seed (anti seed-set overfitting)
        stats = {}
        v = es_step(v, fit, args.pairs, args.sigma, args.lr, rng, args.weight_decay,
                    anchor=anchor, shaping=args.shaping, scales=scales, stats_out=stats)
        f = fit(v)
        hist.append({"gen": g, "fitness": f, "flat": fit._last_flat,
                     "pop_spread": stats.get("spread"), "pop_mean": stats.get("fit_mean"),
                     "renders": fit.n_evals * len(grid), "sec": round(time.time() - t0, 1)})
        mark = ""
        if f > best_f:
            best_f, best_v = f, v.copy(); mark = "  <-- best"
        print(f"[es] gen {g}/{args.generations}: fitness={f:.3f} "
              f"(best {best_f:.3f}) flat={fit._last_flat:.4f} "
              f"{time.time()-t0:.0f}s{mark}", flush=True)
        np.savez(out / "es_state.npz", v=v, best_v=best_v, best_f=best_f)
        # per-gen center snapshots -> the ES walk is MAPPABLE (trajectory-PCA +
        # random-walk null distinguish directed evolution from drift; ~150KB/gen)
        np.save(out / f"center_gen{g:03d}.npy", v)
        json.dump(hist, open(out / "es_history.json", "w"), indent=2)
        # export the best candidate as a drop-in cond.npz (same schema as the trained one)
        np.savez(out / "cond_es_best.npz", **unpack_params(best_v, base, keys))

    print(f"[es] done. init {f0:.3f} -> best {best_f:.3f} "
          f"({fit.n_evals * len(grid)} renders). cond_es_best.npz is drop-in.", flush=True)


if __name__ == "__main__":
    main()
