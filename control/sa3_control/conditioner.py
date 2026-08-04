"""Control conditioners: raw control signals -> control tokens for the adapters.

MVP = the audio-reference (riffer) branch: encode a reference SAME latent into a
compact set of style/content tokens. (Attribute branches — dynamics/rhythm/melody
from the .TIMESERIES.npz — slot in the same way later.)
"""

from __future__ import annotations

import math

import torch
from torch import nn


class AttributeEncoder(nn.Module):
    """Time-varying control feature (B, C_in, T) -> TIME-ORDERED control tokens (B, T', control_dim).

    The time-aligned attribute branch — the chroma/curve analog of ScalarAttributeEncoder (one number)
    and AudioRefEncoder (global pool). Strided convs reduce T -> T' = T / 2**ceil(log2(downsample)) while
    STRICTLY preserving time order (no pooling), so the adapter's `add_fractional_positions` aligns each
    control token to its own time region — every output latent frame can attend to the control *at its
    moment*, approximating local conditioning.

    Use for SAME chroma (C_in = 384 = 3 octave-bands x 128), or any stacked per-frame feature
    (dynamics 4 / rhythm 3 / melody 12, …). The adapter's zero-init output gives the no-op training
    start, so this encoder is normally initialised (it should carry the time-varying signal from step 0).
    """

    def __init__(self, in_channels: int, control_dim: int = 768, hidden: int = 512, downsample: int = 8):
        super().__init__()
        self.in_channels = int(in_channels)
        self.control_dim = int(control_dim)
        n_down = max(0, round(math.log2(max(1, downsample))))     # number of stride-2 halvings
        self.downsample = 2 ** n_down
        layers = [nn.Conv1d(self.in_channels, hidden, 3, padding=1), nn.SiLU()]
        for _ in range(n_down):
            layers += [nn.Conv1d(hidden, hidden, 4, stride=2, padding=1), nn.SiLU()]   # exact T -> T/2
        layers += [nn.Conv1d(hidden, control_dim, 1)]
        self.net = nn.Sequential(*layers)

    def forward(self, feat):                                      # (B, C_in, T)
        h = self.net(feat.to(self.net[0].weight.dtype))          # (B, control_dim, T')
        return h.transpose(1, 2).contiguous()                    # (B, T', control_dim)


class ChromaAttributeEncoder(nn.Module):
    """SAME chroma (B, 384 = 3 bands x 128 bins, T) -> time-aligned control tokens (B, T', control_dim).

    Chroma-AWARE (vs the generic AttributeEncoder's flat 1-D conv): reshapes the 384 channels back
    into the 3 octave-bands x 128 pitch-class bins SAME regresses (paper §3.3.2), and convolves the
    pitch axis CIRCULARLY — pitch class wraps at the octave, so a chord spanning bin 127->0 is seen as
    adjacent (a plain conv would treat it as a hard edge). Bands enter as conv input channels (register
    is preserved); strided convs downsample TIME only (time-ordered tokens for the adapter's fractional
    positions); pitch is pooled after circular mixing. Output contract identical to AttributeEncoder.
    """

    def __init__(self, n_bands: int = 3, n_bins: int = 128, control_dim: int = 768,
                 hidden: int = 128, downsample: int = 8, pitch_pool: int = 8, pitch_k: int = 3):
        super().__init__()
        self.n_bands, self.n_bins, self.pitch_k = int(n_bands), int(n_bins), int(pitch_k)
        self.control_dim = int(control_dim)
        self.in_channels = self.n_bands * self.n_bins
        self.conv_in = nn.Conv2d(self.n_bands, hidden, (self.pitch_k, 3), padding=(0, 1))   # pitch pad=circular(manual)
        n_down = max(0, round(math.log2(max(1, downsample))))
        self.downsample = 2 ** n_down
        self.time_convs = nn.ModuleList([
            nn.Conv2d(hidden, hidden, (self.pitch_k, 4), stride=(1, 2), padding=(0, 1))      # time /2, pitch kept
            for _ in range(n_down)])
        self.pitch_pool = nn.AdaptiveAvgPool2d((pitch_pool, None))                           # pitch -> pitch_pool
        self.proj = nn.Linear(hidden * pitch_pool, control_dim)

    def _cpad(self, x):                                # circular pad the pitch axis (dim=2)
        p = (self.pitch_k - 1) // 2
        return torch.cat([x[:, :, -p:, :], x, x[:, :, :p, :]], dim=2) if p else x

    def forward(self, feat):                           # (B, 384, T) or (B, 3, 128, T)
        w = self.conv_in.weight
        if feat.dim() == 3:                            # (B, 384, T) -> (B, 3, 128, T)
            B, C, T = feat.shape
            feat = feat.view(B, self.n_bands, self.n_bins, T)
        x = torch.relu(self.conv_in(self._cpad(feat.to(w.dtype))))     # (B, hidden, 128, T)
        for cv in self.time_convs:
            x = torch.relu(cv(self._cpad(x)))                          # (B, hidden, 128, T/2^k)
        x = self.pitch_pool(x)                                         # (B, hidden, pitch_pool, T')
        B, h, pp, Tp = x.shape
        x = x.permute(0, 3, 1, 2).reshape(B, Tp, h * pp)               # (B, T', hidden*pitch_pool)
        return self.proj(x)                                            # (B, T', control_dim)


class MelodyContourEncoder(nn.Module):
    """Per-frame melody-contour CLASS stream (B, T) int64 -> time-ordered control tokens
    (B, T', control_dim). Head B of the melodic-LatCH/FiLM design
    (docs/superpowers/specs/2026-07-22-melodic-latch-film.md §2).

    A plain nn.Embedding lookup over the folded contour class set
    {rest, pedal, |1|, |2|, |3|, |5|, |7|, |12|} (indices 0..7, prep_melody_conditioning
    order) — the discrete-symbol analog of AttributeEncoder's conv stack. The stream is
    already ON the latent time grid (10.766 Hz, built frame-aligned by the Head A prep),
    so no resampling is needed at train time; inference-side streams are rasterized to T
    by the caller (same pad/resample-to-T contract as the onset/attribute path). Tokens
    stay per-frame by default (downsample=1); downsample>1 mean-pools embedded tokens
    over time (a soft class mixture — acceptable, but melody detail lives at ~1 frame,
    so the default keeps full rate). The adapter's add_fractional_positions gives each
    token its time identity, exactly like AttributeEncoder output.

    n_classes=9 = the 8 folded data classes + index 8 RESERVED as an explicit learned
    null/mask symbol (StemGen-style; not emitted by the datasets today — condition
    dropout instead zeroes the TOKENS, the fleet-wide trained-null convention that
    inference unconds rely on. The slot exists so a future masked/partial-conditioning
    arm needs no re-init).

    Condition dropout for this source is INDEPENDENT of text cfg-dropout (train.py
    --melody-dropout vs text cfg_dropout_prob) — the StemGen multi-source-CFG POOL item
    (docs/todos.md "[POOL, C] (2026-07-22, StemGen 2312.08723 ...)"), implemented here:
    independent draws expose all four {text, melody} on/off states, enabling per-source
    guidance scales (λ_text, λ_melody) at inference.
    """

    def __init__(self, control_dim: int = 768, n_classes: int = 9, downsample: int = 1):
        super().__init__()
        self.control_dim = int(control_dim)
        self.n_classes = int(n_classes)
        self.downsample = max(1, int(downsample))
        self.embed = nn.Embedding(self.n_classes, self.control_dim)
        nn.init.normal_(self.embed.weight, std=0.02)

    def forward(self, cls):                                    # (B, T) int
        h = self.embed(cls.long())                             # (B, T, control_dim)
        if self.downsample > 1:
            h = h.transpose(1, 2)                              # (B, C, T)
            h = torch.nn.functional.avg_pool1d(h, self.downsample, self.downsample)
            h = h.transpose(1, 2)
        return h                                               # (B, T', control_dim)


class MetricalEncoder(nn.Module):
    """Per-frame metrical-tree POSITION streams -> time-ordered control tokens
    (B, T', control_dim). E3 of the metrical-tree-PE design
    (docs/superpowers/specs/2026-07-31-metrical-tree-pe-design.md §1–3) — the
    metrical sibling of MelodyContourEncoder (same output contract, same
    time-grid/downsample convention).

    Consumes TWO aligned inputs on the latent time grid (10.766 Hz, T=4096 sidecars):
      cls  (B, 5, T) int64 — rows = (subdiv_in_beat 0..3, beat_in_bar 0..3,
           bar_in_phrase 0..7, phrase_idx 0..7, coverage_flag 0/1)
      conf (B, T) float — per-frame coverage confidence.
    Rows 0..3 go through four nn.Embedding tables (4/4/8/8 classes, each
    control_dim//5 wide — HARD classes, not soft probabilities: the
    prep_melody_conditioning lesson, design doc §1/§8); (coverage_flag, conf) go
    through a small linear to the remaining dims; the concat is projected back to
    control_dim. Streams stay per-frame by default (downsample=1); downsample>1
    mean-pools the projected tokens over time, exactly the MelodyContourEncoder
    convention — the adapter's add_fractional_positions gives each token its time
    identity.

    The NULL token = the ALL-ZERO input (every class row 0, coverage 0, conf 0) —
    what uncovered crops carry in the sidecars and what --metrical-dropout feeds
    during training (zero-condition dropout, design doc §2), so the null is a
    trained state, not a reserved index. Like MelodyContourEncoder, this encoder is
    normally initialised (no zero-init projection) — the adapter's zero-init output
    already gives the no-op training start; the encoder should carry signal from
    step 0.
    """

    def __init__(self, control_dim: int = 768, downsample: int = 1,
                 level_sizes: "tuple[int, ...]" = (4, 4, 8, 8)):
        super().__init__()
        self.control_dim = int(control_dim)
        self.downsample = max(1, int(downsample))
        self.level_sizes = tuple(int(s) for s in level_sizes)
        lvl_dim = self.control_dim // (len(self.level_sizes) + 1)   # split: 4 levels + cov/conf block
        self.embeds = nn.ModuleList([nn.Embedding(n, lvl_dim) for n in self.level_sizes])
        for e in self.embeds:
            nn.init.normal_(e.weight, std=0.02)
        self.cov_proj = nn.Linear(2, self.control_dim - len(self.level_sizes) * lvl_dim)
        self.proj = nn.Linear(self.control_dim, self.control_dim)

    def forward(self, cls, conf):                              # (B, 5, T) int, (B, T) float
        w = self.proj.weight
        lv = [emb(cls[:, i].long()) for i, emb in enumerate(self.embeds)]    # 4 x (B, T, lvl_dim)
        cc = torch.stack([cls[:, 4].to(w.dtype), conf.to(w.dtype)], dim=-1)  # (B, T, 2)
        h = torch.cat(lv + [self.cov_proj(cc)], dim=-1)        # (B, T, control_dim)
        h = self.proj(h)                                       # (B, T, control_dim)
        if self.downsample > 1:
            h = h.transpose(1, 2)                              # (B, C, T)
            h = torch.nn.functional.avg_pool1d(h, self.downsample, self.downsample)
            h = h.transpose(1, 2)
        return h                                               # (B, T', control_dim)


class ScalarAttributeEncoder(nn.Module):
    """A single scalar control (e.g. normalized onset_density) -> control tokens.

    The FIRST explicit attribute branch (vs the opaque audio-reference riffer). A bank of
    `n_tokens` learned base tokens is FiLM-modulated by the scalar, giving cross-attention a
    small, expressive token set parametrised by one interpretable number. Same output contract
    as AudioRefEncoder -> (B, n_tokens, control_dim), so it drops into the same adapters.

    Input scalar is expected pre-normalised (~standardised); 0 == the dataset mean == the
    natural cfg-dropout null.
    """

    def __init__(self, control_dim: int = 768, n_tokens: int = 16, hidden: int = 256):
        super().__init__()
        self.n_tokens = n_tokens
        self.control_dim = control_dim
        self.tokens = nn.Parameter(torch.randn(n_tokens, control_dim) * 0.02)
        self.film = nn.Sequential(
            nn.Linear(1, hidden), nn.SiLU(),
            nn.Linear(hidden, n_tokens * control_dim * 2),     # per (token,dim) scale + shift
        )
        nn.init.zeros_(self.film[-1].weight)                   # start as identity (scale=0, shift=0)
        nn.init.zeros_(self.film[-1].bias)

    def forward(self, scalar):                                 # (B,) or (B,1)
        x = scalar.reshape(-1, 1).to(self.tokens.dtype)
        gb = self.film(x).view(-1, self.n_tokens, self.control_dim, 2)
        scale, shift = gb[..., 0], gb[..., 1]
        return self.tokens[None] * (1.0 + scale) + shift       # (B, n_tokens, control_dim)


class FingerprintEncoder(nn.Module):
    """A style fingerprint VECTOR (B, in_dim) -> control tokens (B, n_tokens, control_dim).

    Generalizes ScalarAttributeEncoder from a 1-dim scalar to an in_dim-dim fingerprint
    (genre softmax + other, release_year, bpm, syncopation, [+ window onset/energy]).
    A bank of n_tokens learned base tokens is FiLM-modulated by the fingerprint. Widening
    the FiLM input from 1 to ~15 dims adds negligible params, so the adapter is the same
    size as the scalar one. Zero-init FiLM output -> identity at init (no-op start).

    Fingerprint dims are expected pre-normalized; the all-zero vector is the cfg-dropout null.
    """

    def __init__(self, in_dim: int, control_dim: int = 768, n_tokens: int = 16, hidden: int = 256):
        super().__init__()
        self.in_dim = int(in_dim)
        self.n_tokens = int(n_tokens)
        self.control_dim = int(control_dim)
        self.tokens = nn.Parameter(torch.randn(n_tokens, control_dim) * 0.02)
        self.film = nn.Sequential(
            nn.Linear(self.in_dim, hidden), nn.SiLU(),
            nn.Linear(hidden, n_tokens * control_dim * 2),
        )
        nn.init.zeros_(self.film[-1].weight)
        nn.init.zeros_(self.film[-1].bias)

    def forward(self, vec):                                     # (B, in_dim)
        x = vec.reshape(-1, self.in_dim).to(self.tokens.dtype)
        gb = self.film(x).view(-1, self.n_tokens, self.control_dim, 2)
        scale, shift = gb[..., 0], gb[..., 1]
        return self.tokens[None] * (1.0 + scale) + shift       # (B, n_tokens, control_dim)


class AudioRefEncoder(nn.Module):
    """Reference SAME latent (B, latent_dim, T) -> control tokens (B, n_tokens, control_dim).

    Downsamples the 4096-frame latent to a small token set (the reference is a
    style/content summary, not time-aligned to the target), so cross-attention stays
    cheap. Strided convs (/16) then adaptive pool to exactly `n_tokens`.
    """

    def __init__(self, latent_dim: int = 256, control_dim: int = 768,
                 n_tokens: int = 256, hidden: int = 512):
        super().__init__()
        self.n_tokens = n_tokens
        self.net = nn.Sequential(
            nn.Conv1d(latent_dim, hidden, 3, padding=1), nn.SiLU(),
            nn.Conv1d(hidden, hidden, 4, stride=4, padding=0), nn.SiLU(),   # T/4
            nn.Conv1d(hidden, hidden, 4, stride=4, padding=0), nn.SiLU(),   # T/16
            nn.Conv1d(hidden, control_dim, 1),
        )
        self.pool = nn.AdaptiveAvgPool1d(n_tokens)

    def forward(self, ref_latent):                 # (B, latent_dim, T)
        h = self.net(ref_latent.to(self.net[0].weight.dtype))   # (B, control_dim, ~T/16)
        h = self.pool(h)                           # (B, control_dim, n_tokens)
        return h.transpose(1, 2).contiguous()      # (B, n_tokens, control_dim)
