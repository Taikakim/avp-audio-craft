"""latent_bend.py — latent data-bending ops for SA3 latents shaped (1, 256, T).

The latent-space sibling of stable-audio-3/scripts/weight_mutations.py: every op
is a pure function (tensor in, tensor out), deterministic given a torch.Generator,
and the op-spec format mirrors weight_mutations' Condition ops — an ordered list of
dicts {"op": ..., "amount": ..., + op-specific keys} — so the two benders read the
same recipe grammar. Entry point: apply_bends(latent, ops, seed).

Accepts torch tensors or numpy arrays, (1, C, T) or (C, T); returns the same
type/shape/dtype it was given. All randomness comes from one CPU generator seeded
once, ops consume it in list order, so a (ops, seed) pair reproduces exactly.

Ops:
  channel_swap    {"amount": frac}                       — swap random channel PAIRS
                                                           (frac of C channels involved)
  channel_roll    {"k": n, "shift": frames}              — roll k random channels along T
                                                           (shift omitted → random per channel)
  noise           {"amount": sigma_frac, "channels": []} — gaussian, sigma = amount ×
                                                           per-channel std (channels optional)
  quantize        {"bits": b, "amount": mix}             — bit-crush to 2**b levels over the
                                                           per-channel range, wet/dry mix
  segment_shuffle {"seg": frames, "amount": frac}        — shuffle frac of fixed-length time
                                                           segments among themselves
  splice          {"spans": [[t0, t1], ...], "xfade": f} — crossfade a SECOND latent in over
                                                           the given frame spans (linear ramps)
  band_scale      {"channels": [...], "amount": mult}    — scale an explicit channel subset
                                                           (xcorr-map targeting: pick channels
                                                           from mir/stats/latent_dim_feature_xcorr.csv)

Server hook (audit §4.3): decode-after-bend in explorer_render_server._decode_impl
and /a2a_mix's composite z. Smoke test: run this file under SAO/.venv/bin/python.
"""
from __future__ import annotations

import torch

import numpy as np

BEND_OPS = ("channel_swap", "channel_roll", "noise", "quantize",
            "segment_shuffle", "splice", "band_scale")


# ------------------------------------------------------------------ ops
# All ops take and return a float32 torch tensor shaped (C, T) and never
# mutate their input. Random draws happen on CPU with the supplied generator.

def channel_swap(z, amount, gen):
    """Swap random channel pairs. `amount` = fraction of channels involved;
    value-preserving (rows move, nothing is rescaled)."""
    if amount <= 0:
        return z
    c = z.shape[0]
    n_pairs = min(c // 2, max(1, int(round(amount * c / 2))))
    perm = torch.randperm(c, generator=gen)
    out = z.clone()
    for i in range(n_pairs):
        a, b = perm[2 * i].item(), perm[2 * i + 1].item()
        out[a], out[b] = z[b], z[a]
    return out


def channel_roll(z, k, gen, shift=None, max_shift=None):
    """Roll `k` random channels along T. `shift` frames applies to all picked
    channels; omitted → independent random shift per channel in ±max_shift
    (default T // 8)."""
    if k <= 0:
        return z
    c, t = z.shape
    k = min(k, c)
    idx = torch.randperm(c, generator=gen)[:k]
    if max_shift is None:
        max_shift = max(1, t // 8)
    out = z.clone()
    for ch in idx.tolist():
        s = shift if shift is not None else int(
            torch.randint(-max_shift, max_shift + 1, (1,), generator=gen).item())
        out[ch] = torch.roll(z[ch], shifts=s, dims=0)
    return out


def noise(z, amount, gen, channels=None):
    """Add gaussian noise, sigma = amount * per-channel std. `channels`
    restricts to an explicit subset (default all)."""
    if amount <= 0:
        return z
    sigma = z.std(dim=1, keepdim=True) * amount
    eps = torch.randn(z.shape, generator=gen, dtype=torch.float32)
    if channels is not None:
        mask = torch.zeros(z.shape[0], 1)
        mask[list(channels)] = 1.0
        sigma = sigma * mask
    return z + eps * sigma


def quantize(z, bits, amount=1.0):
    """Bit-crush: snap values to 2**bits levels across the per-channel
    [min, max] range; `amount` is the wet/dry mix (1 = fully crushed)."""
    if amount <= 0 or bits >= 24:
        return z
    lo = z.min(dim=1, keepdim=True).values
    hi = z.max(dim=1, keepdim=True).values
    span = (hi - lo).clamp(min=1e-12)
    levels = float(2 ** int(bits) - 1)
    q = torch.round((z - lo) / span * levels) / levels * span + lo
    return z * (1.0 - amount) + q * amount


def segment_shuffle(z, seg, amount, gen):
    """Shuffle `amount` of the fixed-`seg`-frame time segments among
    themselves (all channels move together; any tail < seg is untouched)."""
    if amount <= 0 or seg <= 0:
        return z
    t = z.shape[1]
    n_seg = t // seg
    if n_seg < 2:
        return z
    n_pick = min(n_seg, max(2, int(round(amount * n_seg))))
    picked = torch.randperm(n_seg, generator=gen)[:n_pick]
    perm = torch.randperm(n_pick, generator=gen)
    out = z.clone()
    src = z[:, : n_seg * seg].reshape(z.shape[0], n_seg, seg)
    dst = out[:, : n_seg * seg].reshape(out.shape[0], n_seg, seg)
    for i in range(n_pick):
        dst[:, picked[i]] = src[:, picked[perm[i]]]
    return out


def splice(z, other, spans, xfade=8):
    """Crossfade `other` in over the given [t0, t1) frame spans, linear
    `xfade`-frame ramps at both edges (ramps live inside the span)."""
    if not spans:
        return z
    c, t = z.shape
    if other.shape[0] != c:
        raise ValueError(f"splice: channel mismatch {other.shape[0]} vs {c}")
    if other.shape[1] < t:
        raise ValueError(f"splice: second latent too short ({other.shape[1]} < {t})")
    w = torch.zeros(t)
    for t0, t1 in spans:
        t0, t1 = max(0, int(t0)), min(t, int(t1))
        if t1 <= t0:
            continue
        f = max(0, min(int(xfade), (t1 - t0) // 2))
        w[t0:t1] = 1.0
        if f > 0:
            ramp = torch.linspace(0.0, 1.0, f + 2)[1:-1]
            w[t0:t0 + f] = torch.minimum(w[t0:t0 + f], ramp)
            w[t1 - f:t1] = torch.minimum(w[t1 - f:t1], ramp.flip(0))
    return z * (1.0 - w) + other[:, :t] * w


def band_scale(z, channels, amount):
    """Scale an explicit channel subset by `amount`. The caller picks the
    channels — e.g. the dims most correlated with a feature per
    mir/stats/latent_dim_feature_xcorr.csv — so bends can target features."""
    if not channels or amount == 1.0:
        return z
    out = z.clone()
    out[list(channels)] = z[list(channels)] * amount
    return out


# ------------------------------------------------------------------ entry point

def _to_ct(latent):
    """→ (float32 torch (C, T) view-copy, restore(bent) closure)."""
    is_np = isinstance(latent, np.ndarray)
    x = torch.from_numpy(np.ascontiguousarray(latent)) if is_np else latent
    if x.ndim == 3:
        if x.shape[0] != 1:
            raise ValueError(f"expected batch 1, got shape {tuple(x.shape)}")
        ct = x[0]
    elif x.ndim == 2:
        ct = x
    else:
        raise ValueError(f"expected (1, C, T) or (C, T), got shape {tuple(x.shape)}")
    in_dtype, batched = x.dtype, x.ndim == 3

    def restore(bent):
        y = bent.to(in_dtype)
        if batched:
            y = y[None]
        return y.numpy() if is_np else y

    return ct.detach().float().cpu(), restore


def apply_bends(latent, ops, seed=1234, second=None):
    """Apply an ordered op-spec list to one latent; returns a new latent of
    the same type/shape/dtype (input untouched).

    latent : torch tensor or numpy array, (1, C, T) or (C, T), any float dtype
    ops    : [{"op": <name>, "amount": float, + op-specific keys}, ...] —
             see module docstring; unknown op names fail loud
    seed   : one CPU generator drives all randomness, ops consume it in list
             order → (ops, seed) reproduces exactly
    second : second latent for "splice" (a spec's own "other" key wins)
    """
    z, restore = _to_ct(latent)
    gen = torch.Generator()
    gen.manual_seed(seed)
    for spec in ops:
        op, amount = spec["op"], spec.get("amount", 0.0)
        if op == "channel_swap":
            z = channel_swap(z, amount, gen)
        elif op == "channel_roll":
            k = int(spec.get("k", max(1, round(amount * z.shape[0]))))
            z = channel_roll(z, k, gen, shift=spec.get("shift"),
                             max_shift=spec.get("max_shift"))
        elif op == "noise":
            z = noise(z, amount, gen, channels=spec.get("channels"))
        elif op == "quantize":
            z = quantize(z, spec.get("bits", 6), amount=spec.get("amount", 1.0))
        elif op == "segment_shuffle":
            z = segment_shuffle(z, int(spec.get("seg", 64)), amount, gen)
        elif op == "splice":
            src = spec.get("other", second)
            if src is None:
                raise ValueError("splice needs a second latent (spec 'other' or second=)")
            other, _ = _to_ct(src)
            z = splice(z, other, spec.get("spans", []), xfade=spec.get("xfade", 8))
        elif op == "band_scale":
            z = band_scale(z, spec.get("channels", []), amount)
        else:
            raise ValueError(f"unknown bend op {op!r} (known: {BEND_OPS})")
    return restore(z)


# ------------------------------------------------------------------ smoke test

if __name__ == "__main__":
    torch.manual_seed(7)
    z = torch.randn(1, 256, 512, dtype=torch.float32)
    z2 = torch.randn(1, 256, 512, dtype=torch.float32)
    ops = [
        {"op": "channel_swap", "amount": 0.25},
        {"op": "channel_roll", "k": 16, "shift": 32},
        {"op": "noise", "amount": 0.1, "channels": [0, 5, 250]},
        {"op": "quantize", "bits": 5, "amount": 0.8},
        {"op": "segment_shuffle", "seg": 64, "amount": 0.5},
        {"op": "splice", "spans": [[100, 200], [400, 480]], "xfade": 16},
        {"op": "band_scale", "channels": [10, 20, 30], "amount": 1.5},
    ]
    orig = z.clone()
    a = apply_bends(z, ops, seed=42, second=z2)
    b = apply_bends(z, ops, seed=42, second=z2)
    c = apply_bends(z, ops, seed=43, second=z2)
    assert a.shape == z.shape and a.dtype == z.dtype, "shape/dtype not preserved"
    assert torch.equal(z, orig), "input latent was mutated"
    assert torch.equal(a, b), "same seed must reproduce exactly"
    assert not torch.equal(a, c), "different seed should differ"
    assert not torch.equal(a, z), "ops should change the latent"
    # numpy + fp16 + unbatched round-trips
    zn = z[0].numpy().astype(np.float16)
    an = apply_bends(zn, ops, seed=42, second=z2[0].numpy())
    bn = apply_bends(zn, ops, seed=42, second=z2[0].numpy())
    assert isinstance(an, np.ndarray) and an.shape == zn.shape and an.dtype == zn.dtype
    assert np.array_equal(an, bn), "numpy path must be deterministic too"
    # each op alone is deterministic and shape-preserving
    for spec in ops:
        s1 = apply_bends(z, [spec], seed=1, second=z2)
        s2 = apply_bends(z, [spec], seed=1, second=z2)
        assert torch.equal(s1, s2) and s1.shape == z.shape, f"op {spec['op']} broken"
    print(f"latent_bend smoke OK — {len(ops)} ops on (1, 256, 512): "
          f"shape/dtype preserved, deterministic per seed, "
          f"mean |Δ| = {(a - z).abs().mean().item():.4f}")
