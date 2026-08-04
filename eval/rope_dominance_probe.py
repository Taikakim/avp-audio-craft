#!/usr/bin/env python
"""rope_dominance_probe.py — RoPE-frequency dominance diagnostic for the a2a loop
attractor (task #60; UltraViCo 2511.20123 + LoL 2601.16914 convergent lead, F's papers
sprint 2026-07-30, redone on SA3's 1D temporal RoPE per the model-specificity caveat).

Hypothesis: loop collapse is attention-geometric — in the video models, ONE temporal-RoPE
frequency dominating attention amplitude discriminated looping (79.6%) from non-looping
(31.6%) models, prompt-independently. SCOPE (the null that stays valid): our LoL
rope-jitter null covered WINDOWED longform (positions reset per window — aliasing
precondition absent); THIS probe targets the WITHIN-window loop attractor (Kim's ear,
nl.55+: generated material loops a short phrase for minutes inside one window,
docs/a2a-loop-attractor.md).

Method: encode matched segments of Kim-labeled LOOPY (nl60/70) vs NON-LOOPY (nl35/42)
renders of the same track/ckpt/prompt (a2a_kaikkialla_evr1x ladder); noise each latent to
sigma {0.5, 0.8}; one conditioned DiT forward each with the SAME model that generated
them (base + evr1x adapter); wrap every Attention.apply_attn to capture post-RoPE q,k
(self-attn only: filtered by n_q == n_k; differential main branch = first call per
module per forward); per layer compute the mean relative-offset logit profile
a(delta) = mean_{i,h} q_i . k_{i+delta} / sqrt(d), then its FFT power spectrum;
DOMINANCE = max single non-DC frequency's share of total power. Verdict axis: does
dominance separate loopy from non-loopy inputs?

Run (SA3 venv, GPU, hold SAO/.gpu.lock):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/rope_dominance_probe.py
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "latch"))
from stable_audio_3 import StableAudioModel          # noqa: E402
from stable_audio_3.models.transformer import Attention  # noqa: E402

LADDER = Path("/run/media/kim/Mantu/sa3_lora_runs/a2a_kaikkialla_evr1x")
CKPT = "/run/media/kim/Mantu/sa3_lora_runs/dora128_everything_8ep_lr1x/epoch=7-step=12216.ckpt"
CLIPS = {"nl35": "nonloopy", "nl42": "nonloopy", "nl60": "loopy", "nl70": "loopy"}
PROMPT = "aggressive upbeat goa trance"
SEG = (60.0, 155.108)      # the day's standard window
SIGMAS = [0.5, 0.8]
MAX_LAG = 128
N_QUERIES = 256
OUT = Path("/run/media/kim/Mantu/sa3_lora_runs/rope_dominance_probe")


def profile_from_qk(q, k, max_lag=MAX_LAG, n_queries=N_QUERIES):
    """q,k: [b,h,n,d] post-RoPE. Mean logit vs relative offset, a(delta)."""
    b, h, n, d = q.shape
    qs = torch.linspace(max_lag, n - max_lag - 1, n_queries).long()
    prof = torch.zeros(2 * max_lag + 1, dtype=torch.float32)
    qsel = q[0, :, qs, :].float()                        # [h, nq, d]
    for j, dl in enumerate(range(-max_lag, max_lag + 1)):
        ksel = k[0, :, qs + dl, :].float()               # [h, nq, d]
        prof[j] = (qsel * ksel).sum(-1).mean() / (d ** 0.5)
    return prof.numpy()


def dominance(prof):
    x = prof - prof.mean()
    p = np.abs(np.fft.rfft(x)) ** 2
    p = p[1:]                                            # drop DC
    return float(p.max() / (p.sum() + 1e-12)), int(np.argmax(p) + 1)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    model.load_lora([CKPT])
    cdm = model.model
    device = next(cdm.model.parameters()).device
    mdtype = next(cdm.model.parameters()).dtype
    sr_model = cdm.sample_rate

    # ---- capture rig: wrap every Attention.apply_attn (self-attn filtered by n match)
    captured = {}          # layer_name -> profile (first self-attn call this forward)
    def wrap(name, attn):
        orig = attn.apply_attn
        def wrapped(q, k, v, **kw):
            if name not in captured and q.shape[-2] == k.shape[-2] and q.shape[-2] > 2 * MAX_LAG + 8:
                captured[name] = profile_from_qk(q.detach().cpu(), k.detach().cpu())
            return orig(q, k, v, **kw)
        attn.apply_attn = wrapped
    for name, mod in cdm.model.named_modules():
        if isinstance(mod, Attention):
            wrap(name, mod)

    results = {}
    for stem, cls in CLIPS.items():
        wav = LADDER / f"a2a_{stem}.wav"
        audio, sr = sf.read(wav, dtype="float32", always_2d=True)
        seg = torch.tensor(audio.T[None, :, int(SEG[0]*sr):int(SEG[1]*sr)]).to(device)
        with torch.no_grad():
            z = cdm.pretransform.encode(seg.to(mdtype))      # [1,256,T]
        # conditioning assembly mirrored from latch/extract_layer_activations.extract()
        tensors = cdm.conditioner([{"prompt": PROMPT, "seconds_total": SEG[1] - SEG[0]}], str(device))
        T = z.shape[-1]
        tensors["inpaint_mask"] = [torch.zeros((1, 1, T), device=device)]
        tensors["inpaint_masked_input"] = [torch.zeros_like(z, device=device)]
        cond_inputs = cdm.get_conditioning_inputs(tensors)
        cond_inputs = {k: (v.type(mdtype) if torch.is_tensor(v) else v)
                       for k, v in cond_inputs.items()}
        for s in SIGMAS:
            g = torch.Generator(device="cpu").manual_seed(7)
            eps = torch.randn(z.shape, generator=g).to(device, mdtype)
            zs = (1 - s) * z.to(device, mdtype) + s * eps
            t = torch.full((1,), float(s), device=device, dtype=mdtype)
            captured.clear()
            with torch.no_grad():
                cdm.model(zs, t, **cond_inputs)
            for lname, prof in captured.items():
                dom, fbin = dominance(prof)
                results.setdefault(f"{stem}|s{s}", {})[lname] = {
                    "dominance": round(dom, 4), "top_bin": fbin}
            print(f"[fwd] {stem} ({cls}) sigma={s}: {len(captured)} self-attn layers captured", flush=True)

    # ---- verdict table: mean dominance per layer, loopy vs non-loopy
    layers = sorted({l for r in results.values() for l in r},
                    key=lambda x: int("".join(c for c in x.split(".")[1] if c.isdigit()) or 0))
    def mean_dom(cls, layer):
        vals = [results[k][layer]["dominance"] for k in results
                if CLIPS[k.split("|")[0]] == cls and layer in results[k]]
        return float(np.mean(vals)) if vals else float("nan")
    print(f"\n{'layer':<28} {'loopy':>7} {'nonloopy':>9} {'delta':>7}")
    summary = {}
    for l in layers:
        lo = mean_dom("loopy", l)
        no = mean_dom("nonloopy", l)
        summary[l] = {"loopy": round(lo, 4), "nonloopy": round(no, 4)}
        print(f"{l:<28} {lo:>7.3f} {no:>9.3f} {lo-no:>+7.3f}")
    all_lo = np.mean([v["loopy"] for v in summary.values()])
    all_no = np.mean([v["nonloopy"] for v in summary.values()])
    print(f"\nMEAN dominance: loopy {all_lo:.3f} vs non-loopy {all_no:.3f} "
          f"(video-paper reference: 0.796 vs 0.316)")

    (OUT / "results.json").write_text(json.dumps(
        {"per_forward": results, "per_layer_summary": summary,
         "mean": {"loopy": round(float(all_lo), 4), "nonloopy": round(float(all_no), 4)},
         "clips": CLIPS, "sigmas": SIGMAS, "segment_s": SEG, "prompt": PROMPT,
         "ckpt": CKPT, "max_lag": MAX_LAG, "n_queries": N_QUERIES,
         "method": "post-RoPE q.k mean relative-offset logit profile -> FFT power -> max non-DC share",
         "result": None, "kim_feedback": None}, indent=2))
    print(f"[done] -> {OUT}/results.json")


if __name__ == "__main__":
    main()
