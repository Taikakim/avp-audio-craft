#!/usr/bin/env python3
# Owner: KUANG (created 2026-10-17)
"""sensitive_directions.py -- find, render and try to NAME the directions SA3 is most sensitive to.

METHOD (after arXiv 2610.15724 "Spectral-Guided Quality-Diversity Diffusion", section 3.2, and the h-space idea it builds on):
  1. Euler-sample a prompt/seed to an intermediate step k (default: the first step with sigma <= --sigma 0.6; the paper finds
     mid-trajectory edits most meaningful).
  2. Take h = the output of DiT block --block (SA3's built-in early exit `exit_layer_ix`, conditional pass, no CFG) and find
     the top --k right singular vectors of the Jacobian dh/dx_k (--wrt latent) or dh/dc for the text cross-attention
     conditioning (--wrt cond), by subspace iteration: J V by central finite differences, J^T U by autograd, QR in between.
     Moving x_k along v_i changes the model's internal features the most per unit step.
  3. Render a ladder per direction: x_k + a * rms(x_k) * sqrt(N) * v_i for a in --alphas (perturbation RMS = a * RMS of x_k),
     then continue the same Euler/CFG sampling to the end (latent), or regenerate the whole clip with c + a*... (cond).
     a = 0 is the unperturbed render. (The paper inverts the edit back to x_T to archive it as a genotype; not needed for
     a ladder, not built.)
  4. NAME it: measure every ladder clip (eval/latch_drift_check.measure: onset rate, hi-hat onset rate, kick-band bpm,
     centroid, loudness; plus bass/mid/air band level and crest factor here; optional CLAP similarity to --clap-labels),
     fit the slope of each descriptor against a, and z-score the slope by that descriptor's spread across the run's
     unperturbed renders (other seeds/prompts). The name is the descriptor (and sign) with the largest |z|, with the
     runner-up for compound changes; "unnamed" when nothing passes --name-z. With --heads, also the cosine between v_i and
     each LatCH head's gradient at x_k: a direction we already control has |cos| near 1.
  5. Write results.json and index.html (listening page: ladders, names, descriptor slopes, head cosines).

CAVEATS (read before trusting a name):
  - Directions are LOCAL (one prompt, seed, step, block). Only a name that recurs across seeds/prompts means something;
    the summary counts recurrences.
  - The largest directions are likely the obvious ones (level, brightness, density); subtle factors sit lower: use a
    larger --k.
  - A large internal response is not an audible or a desirable change. Listening decides; the descriptors only propose.
  - The descriptors are blind to some factors (log-mel-type meters miss detune: V5 ladder gate). A direction they cannot
    describe is "unnamed", not "nothing".
  - Renders use the low-level conditioning path of stable-audio-3/scripts/latch/verify_latch.py with the model's own
    sampling_dist_shift; they are deterministic but not bit-identical to model.generate().

RUN (desktop, GPU):
  SAO/.venv/bin/python eval/sensitive_directions.py --prompt "psytrance, 140 bpm" --seeds 1234 77 --block 12 --k 8 \
      --heads <onset head .pt> <air head .pt> --clap-labels "brighter" "darker" "more percussive" "denser hi-hats" \
      --out ~/evals_aac/sensitive_directions/psy_b12
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

DESCRIPTOR_WORDS = {
    "onset_rate": ("denser onsets", "sparser onsets"),
    "hat_rate": ("more hi-hat onsets", "fewer hi-hat onsets"),
    "bpm": ("faster pulse", "slower pulse"),
    "centroid": ("brighter", "darker"),
    "rms_db": ("louder", "quieter"),
    "bass_db": ("more bass", "less bass"),
    "mid_db": ("more mids", "fewer mids"),
    "air_db": ("more air (>6 kHz)", "less air (>6 kHz)"),
    "crest_db": ("more dynamic (crest up)", "more compressed (crest down)"),
}


# ----------------------------------------------------------------------------------------------------------------
# core, model-agnostic (unit-tested on the laptop: eval/tests/test_sensitive_directions.py)
# ----------------------------------------------------------------------------------------------------------------
def _flat(t):
    return t.reshape(t.shape[0], -1)


def _orth(V):
    """Orthonormalise the k rows of V (k, *shape) with QR."""
    Q, _ = torch.linalg.qr(_flat(V).T.double())
    return Q.T.to(V.dtype).reshape(V.shape)


def top_right_singular(f, x, k=8, iters=12, fd_eps=1e-3, chunk=None, seed=0):
    """Top-k right singular vectors of J = df/dx at x (x has a leading batch dim of 1).

    f maps a batch (B, *x.shape[1:]) to a batch of features (B, ...). J V by central differences (step fd_eps*||x||, the
    vectors are unit norm), J^T U by autograd; subspace iteration V <- orth(J^T J V). Returns (V (k, *x.shape[1:]),
    sigma (k,), descending). chunk = max batch per call (memory)."""
    g = torch.Generator(device="cpu").manual_seed(seed)
    V = _orth(torch.randn((k,) + tuple(x.shape[1:]), generator=g).to(x.device, x.dtype))
    h = fd_eps * float(x.float().norm())
    chunk = chunk or k

    def jv(V):
        out = []
        for s in range(0, V.shape[0], chunk):
            Vs = V[s:s + chunk]
            with torch.no_grad():
                plus = f(x + h * Vs)
                minus = f(x - h * Vs)
            out.append((plus.float() - minus.float()) / (2 * h))
        return torch.cat(out)

    def jtu(U):
        out = []
        for s in range(0, U.shape[0], chunk):
            Us = U[s:s + chunk]
            X = x.repeat((Us.shape[0],) + (1,) * (x.ndim - 1)).detach().requires_grad_(True)
            y = f(X)
            (g_,) = torch.autograd.grad(y, X, grad_outputs=Us.to(y.dtype))
            out.append(g_.float())
        return torch.cat(out)

    for _ in range(iters):
        V = _orth(jtu(jv(V)).to(x.dtype))
    U = jv(V)
    sig = _flat(U).norm(dim=1)
    order = torch.argsort(sig, descending=True)
    return V[order], sig[order]


def perturb(x, v, a):
    """x + a * rms(x) * sqrt(N) * v for unit-norm v: the perturbation's RMS is a times the RMS of x."""
    n = x[0].numel()
    rms = float(x.float().pow(2).mean().sqrt())
    return x + (a * rms * math.sqrt(n)) * v.unsqueeze(0).to(x.dtype)


def slopes(alphas, values):
    """Least-squares slope of each descriptor against alpha. values: list (len alphas) of dicts."""
    a = np.asarray(alphas, dtype=np.float64)
    out = {}
    for key in values[0]:
        y = np.asarray([v[key] for v in values], dtype=np.float64)
        ok = np.isfinite(y)
        if ok.sum() < 2 or np.ptp(a[ok]) == 0:
            out[key] = float("nan")
            continue
        out[key] = float(np.polyfit(a[ok], y[ok], 1)[0])
    return out


def name_direction(slope, base_spread, name_z=1.0, words=DESCRIPTOR_WORDS):
    """z = slope / spread of that descriptor across unperturbed renders. Name = top |z| (+ runner-up if within 2x)."""
    z = {k: s / base_spread[k] for k, s in slope.items()
         if k in base_spread and base_spread[k] > 0 and np.isfinite(s)}
    ranked = sorted(z.items(), key=lambda kv: -abs(kv[1]))
    if not ranked or abs(ranked[0][1]) < name_z:
        return {"name": "unnamed", "z": z}
    def word(k, v):
        w = words.get(k)
        return (w[0] if v > 0 else w[1]) if w else f"{k} {'up' if v > 0 else 'down'}"
    name = word(*ranked[0])
    if len(ranked) > 1 and abs(ranked[1][1]) >= max(name_z, abs(ranked[0][1]) / 2):
        name += " + " + word(*ranked[1])
    return {"name": name, "z": z, "top": ranked[0][0]}


def cosine(a, b):
    a, b = a.flatten().float(), b.flatten().float()
    return float((a @ b) / (a.norm() * b.norm()).clamp_min(1e-30))


# ----------------------------------------------------------------------------------------------------------------
# audio descriptors
# ----------------------------------------------------------------------------------------------------------------
def describe(path):
    import soundfile as sf
    from scipy.signal import stft
    from latch_drift_check import measure
    m = measure(path)
    x, sr = sf.read(path, dtype="float32", always_2d=False)
    x = x.mean(1) if x.ndim > 1 else x
    f, _, S = stft(x, fs=sr, nperseg=2048, noverlap=1536)
    P = (np.abs(S) ** 2).mean(1)
    def band(lo, hi):
        return float(10 * np.log10(P[(f >= lo) & (f < hi)].sum() + 1e-12))
    m.update(bass_db=band(20, 200), mid_db=band(200, 2000), air_db=band(6000, sr / 2),
             crest_db=float(20 * np.log10((np.abs(x).max() + 1e-9) / (np.sqrt((x ** 2).mean()) + 1e-9))))
    return m


def load_clap(device):
    """laion_clap as in eval/clap_score.py (argv hidden at import; full torch.load for the official checkpoint)."""
    argv = sys.argv[:]
    sys.argv = [argv[0]]
    try:
        import laion_clap
    finally:
        sys.argv = argv
    model = laion_clap.CLAP_Module(enable_fusion=False, amodel="HTSAT-tiny", device=device)
    orig_load, orig_lsd = torch.load, model.model.load_state_dict
    torch.load = lambda *a, **k: orig_load(*a, **{**k, "weights_only": False})
    model.model.load_state_dict = lambda sd, strict=True: orig_lsd(sd, strict=False)
    try:
        model.load_ckpt(model_id=1)
    finally:
        torch.load, model.model.load_state_dict = orig_load, orig_lsd
    model.eval()
    return model


def clap_scores(model, wavs, labels):
    t = model.get_text_embedding(labels)
    a = model.get_audio_embedding_from_filelist(x=wavs)
    t, a = np.asarray(t, dtype=np.float64), np.asarray(a, dtype=np.float64)
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    a /= np.linalg.norm(a, axis=1, keepdims=True)
    return a @ t.T                                         # (n_wavs, n_labels)


# ----------------------------------------------------------------------------------------------------------------
# SA3 glue (desktop)
# ----------------------------------------------------------------------------------------------------------------
def _repeat_cond(cond, b):
    out = {}
    for k, v in cond.items():
        if torch.is_tensor(v):
            out[k] = v.repeat((b,) + (1,) * (v.ndim - 1))
        elif isinstance(v, list) and v and all(torch.is_tensor(e) for e in v):
            out[k] = [e.repeat((b,) + (1,) * (e.ndim - 1)) for e in v]
        else:
            out[k] = v
    return out


def build_conditioning(model, prompt, duration, device, dtype):
    from stable_audio_3 import StableAudioModel
    cond, _ = StableAudioModel._build_conditioning_dicts(prompt, None, duration, 1)
    sample_size = model._adapt_sample_size(cond, 5292032, 6.0)
    latent_len = sample_size // model.model.pretransform.downsampling_ratio
    ct = model.model.conditioner(cond, device)
    ct["inpaint_mask"] = [torch.zeros(1, 1, latent_len, device=device)]
    ct["inpaint_masked_input"] = [torch.zeros(1, model.model.io_channels, latent_len, device=device)]
    ci = model.model.get_conditioning_inputs(ct)
    return {k: (v.type(dtype) if torch.is_tensor(v) else v) for k, v in ci.items()}, latent_len


def euler(dit, x, sigmas, i0, i1, cond, cfg):
    with torch.no_grad():
        for i in range(i0, i1):
            t = sigmas[i] * torch.ones(x.shape[0], device=x.device, dtype=x.dtype)
            v = dit(x, t, **cond, cfg_scale=cfg, batch_cfg=True, rescale_cfg=True, apg_scale=1.0)
            x = x + (sigmas[i + 1] - sigmas[i]) * v
    return x


def decode_write(model, lat, path, sr, n_samples):
    import soundfile as sf
    with torch.no_grad():
        audio = model.model.pretransform.decode(lat.type(next(model.model.pretransform.parameters()).dtype))
    y = audio[0].float().cpu().numpy()[:, :n_samples]
    if not np.isfinite(y).all():
        return False
    pk = float(np.abs(y).max()) or 1e-9
    sf.write(path, (y / pk * 0.8913 if pk > 1 else y).T, sr)
    return True


def head_gradients(heads, x, t, device):
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "stable-audio-3"))
    from scripts.latch.latch_model import LatCH
    out = {}
    for p in heads:
        ck = torch.load(p, map_location=device, weights_only=False)
        sd = ck["state_dict"]
        arch = ck.get("arch") or {}
        dim = arch.get("dim", sd["latent_proj.weight"].shape[0])
        depth = arch.get("depth", 1 + max(int(k.split(".")[1]) for k in sd if k.startswith("blocks.")))
        head = LatCH(in_channels=256, out_channels=ck["out_channels"], dim=dim, depth=depth,
                     num_heads=arch.get("num_heads", 8), t_injection=ck.get("t_injection", "adaln_zero")).to(device)
        head.load_state_dict(sd)
        head.eval()
        xx = x.detach().float().requires_grad_(True)
        y = head(xx, t.float().expand(xx.shape[0]))
        (g,) = torch.autograd.grad(y.mean(), xx)
        out[ck.get("feature_name", os.path.basename(p))] = g[0].detach()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="medium-base")
    ap.add_argument("--prompt", nargs="+", default=["psytrance, 140 bpm"])
    ap.add_argument("--seeds", type=int, nargs="+", default=[1234, 77])
    ap.add_argument("--duration", type=float, default=20.0)
    ap.add_argument("--steps", type=int, default=50)
    ap.add_argument("--cfg", type=float, default=7.0)
    ap.add_argument("--sigma", type=float, default=0.6, help="probe at the first step with sigma <= this")
    ap.add_argument("--block", type=int, default=None, help="DiT block (exit_layer_ix); default the middle block")
    ap.add_argument("--audio-tokens-only", action=argparse.BooleanOptionalAction, default=True,
                    help="h = the block output on the audio frames only (drop prepended conditioning tokens)")
    ap.add_argument("--wrt", choices=["latent", "cond"], default="latent")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--iters", type=int, default=12)
    ap.add_argument("--fd-eps", type=float, default=1e-3)
    ap.add_argument("--chunk", type=int, default=2, help="max batch per Jacobian call (memory)")
    ap.add_argument("--alphas", type=float, nargs="+", default=[-0.3, -0.15, 0.0, 0.15, 0.3])
    ap.add_argument("--name-z", type=float, default=1.0)
    ap.add_argument("--heads", nargs="*", default=[], help="LatCH head checkpoints: cosine with their gradients")
    ap.add_argument("--clap-labels", nargs="*", default=[])
    ap.add_argument("--half", action="store_true", help="bf16 model (default fp32: finite differences need it)")
    ap.add_argument("--device", default=None, help="default: cuda if available")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    from stable_audio_3 import StableAudioModel
    from stable_audio_3.inference.sampling import build_schedule
    os.makedirs(a.out, exist_ok=True)
    dev = a.device or ("cuda" if torch.cuda.is_available() else "cpu")
    model = StableAudioModel.from_pretrained(a.model, device=dev, model_half=a.half)
    dit = model.model.model
    dtype = next(dit.parameters()).dtype
    sr = model.model.sample_rate
    n_layers = len(dit.model.transformer.layers)
    block = a.block if a.block is not None else n_layers // 2
    meta = {"args": vars(a), "block": block, "n_layers": n_layers, "model": a.model}
    json.dump(meta, open(os.path.join(a.out, "run_meta.json"), "w"), indent=1)

    runs, base_desc = [], []
    for prompt in a.prompt:
        cond, T = build_conditioning(model, prompt, a.duration, dev, dtype)
        n_samples = int(a.duration * sr)
        sigmas = build_schedule(steps=a.steps, sigma_max=1.0, dist_shift=model.model.sampling_dist_shift,
                                fallback_seq_len=T, include_endpoint=True, device=dev)
        k_step = int(next(i for i, s in enumerate(sigmas.tolist()) if s <= a.sigma))
        for seed in a.seeds:
            tag = f"p{a.prompt.index(prompt)}_s{seed}"
            torch.manual_seed(seed)
            noise = torch.randn(1, model.model.io_channels, T, device=dev).type(dtype)
            x_k = euler(dit, noise, sigmas, 0, k_step, cond, a.cfg)
            t_k = sigmas[k_step] * torch.ones(1, device=dev)

            def feats(X, C=None):
                c = _repeat_cond(cond if C is None else {**cond, "cross_attn_cond": C}, X.shape[0])
                h = dit(X, t_k.expand(X.shape[0]).to(X.dtype), **c, cfg_scale=1.0, exit_layer_ix=block)
                return h[:, -T:, :] if a.audio_tokens_only else h

            if a.wrt == "latent":
                V, sig = top_right_singular(lambda X: feats(X), x_k, k=a.k, iters=a.iters, fd_eps=a.fd_eps,
                                            chunk=a.chunk, seed=seed)
            else:
                if not torch.is_tensor(cond.get("cross_attn_cond")):
                    raise SystemExit(f"--wrt cond: no cross_attn_cond tensor in the conditioning inputs ({sorted(cond)})")
                c0 = cond["cross_attn_cond"]
                V, sig = top_right_singular(lambda C: feats(x_k.repeat(C.shape[0], 1, 1), C), c0, k=a.k,
                                            iters=a.iters, fd_eps=a.fd_eps, chunk=a.chunk, seed=seed)
            hg = head_gradients(a.heads, x_k, t_k, dev) if (a.heads and a.wrt == "latent") else {}

            rows = []
            base_path = os.path.join(a.out, f"{tag}_base.wav")
            if decode_write(model, euler(dit, x_k, sigmas, k_step, a.steps, cond, a.cfg), base_path, sr, n_samples):
                base_desc.append(describe(base_path))
            for i in range(V.shape[0]):
                ladder = []
                for al in a.alphas:
                    p = os.path.join(a.out, f"{tag}_d{i}_a{al:+.2f}.wav")
                    if al == 0.0:
                        p = base_path
                    elif a.wrt == "latent":
                        lat = euler(dit, perturb(x_k, V[i], al), sigmas, k_step, a.steps, cond, a.cfg)
                        if not decode_write(model, lat, p, sr, n_samples):
                            p = None
                    else:
                        c2 = {**cond, "cross_attn_cond": perturb(cond["cross_attn_cond"], V[i], al)}
                        lat = euler(dit, noise, sigmas, 0, a.steps, c2, a.cfg)
                        if not decode_write(model, lat, p, sr, n_samples):
                            p = None
                    ladder.append({"alpha": al, "wav": os.path.basename(p) if p else None,
                                   "desc": describe(p) if p else None})
                rows.append({"dir": i, "sigma": float(sig[i]), "ladder": ladder,
                             "head_cos": {n: cosine(V[i], g) for n, g in hg.items()}})
                print(f"[{tag}] direction {i}: sigma {float(sig[i]):.3g}", flush=True)
            runs.append({"tag": tag, "prompt": prompt, "seed": seed, "probe_step": k_step,
                         "probe_sigma": float(sigmas[k_step]), "directions": rows})
            torch.save({"V": V.cpu(), "sigma": sig.cpu(), "x_k": x_k.cpu()}, os.path.join(a.out, f"{tag}_dirs.pt"))

    keys = list(base_desc[0]) if base_desc else []
    spread = {k: float(np.nanstd([d[k] for d in base_desc])) for k in keys} if len(base_desc) > 1 else {}
    if not spread:
        print("only one unperturbed render: descriptor slopes cannot be z-scored; names use raw units", flush=True)
        spread = {k: 1.0 for k in keys}
    clap = load_clap(dev) if a.clap_labels else None
    counts = {}
    for r in runs:
        for d in r["directions"]:
            ok = [s for s in d["ladder"] if s["desc"] is not None]
            if len(ok) < 2:
                d["name"] = {"name": "render failed"}
                continue
            d["slopes"] = slopes([s["alpha"] for s in ok], [s["desc"] for s in ok])
            d["name"] = name_direction(d["slopes"], spread, a.name_z)
            if clap is not None:
                M = clap_scores(clap, [os.path.join(a.out, s["wav"]) for s in ok], a.clap_labels)
                d["clap_slopes"] = {lab: float(np.polyfit([s["alpha"] for s in ok], M[:, j], 1)[0])
                                    for j, lab in enumerate(a.clap_labels)}
            counts.setdefault(d["name"]["name"], []).append(f"{r['tag']}/d{d['dir']}")
    res = {"meta": meta, "base_spread": spread, "recurrence": counts, "runs": runs}
    json.dump(res, open(os.path.join(a.out, "results.json"), "w"), indent=1)
    write_page(res, os.path.join(a.out, "index.html"))
    print("names across seeds/prompts:")
    for n, where in sorted(counts.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(where):2d}x  {n}")
    print(f"-> {a.out}/index.html")
    return 0


def write_page(res, path):
    import html
    rows = []
    for r in res["runs"]:
        rows.append(f"<h2>{html.escape(r['prompt'])} &middot; seed {r['seed']} &middot; probe step {r['probe_step']} "
                    f"(sigma {r['probe_sigma']:.2f})</h2><table><tr><th>dir</th><th>sigma</th><th>name</th><th>ladder</th>"
                    f"<th>top z</th><th>heads</th></tr>")
        for d in r["directions"]:
            lad = "".join(f"<div>{s['alpha']:+.2f} <audio controls preload='none' src='{html.escape(s['wav'] or '')}'></audio></div>"
                          for s in d["ladder"])
            z = d.get("name", {}).get("z", {})
            zt = ", ".join(f"{k} {v:+.1f}" for k, v in sorted(z.items(), key=lambda kv: -abs(kv[1]))[:3])
            hc = ", ".join(f"{k} {v:+.2f}" for k, v in d.get("head_cos", {}).items())
            rows.append(f"<tr><td>{d['dir']}</td><td>{d['sigma']:.3g}</td><td><b>{html.escape(d.get('name', {}).get('name', ''))}</b></td>"
                        f"<td>{lad}</td><td>{html.escape(zt)}</td><td>{html.escape(hc)}</td></tr>")
        rows.append("</table>")
    rec = "".join(f"<li>{len(w)}x {html.escape(n)}</li>" for n, w in sorted(res["recurrence"].items(), key=lambda kv: -len(kv[1])))
    doc = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Sensitive directions</title>"
        "<style>body{font-family:sans-serif;margin:16px;background:#fff;color:#111}"
        "table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:4px;vertical-align:top}"
        "audio{height:28px;width:220px}</style></head><body>"
        f"<h1>Sensitive directions, block {res['meta']['block']} of {res['meta']['n_layers']}</h1>"
        "<p>Names are PROPOSALS from descriptor slopes (z vs the spread of unperturbed renders). Listening decides. "
        "A name only counts if it recurs across seeds and prompts:</p>"
        f"<ul>{rec}</ul>" + "".join(rows) + "</body></html>")
    open(path, "w", encoding="utf-8").write(doc)


if __name__ == "__main__":
    sys.exit(main())
