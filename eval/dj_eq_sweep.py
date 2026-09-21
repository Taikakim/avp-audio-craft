#!/usr/bin/env python
"""dj_eq_sweep.py — time-varying EQ sweep modeling a manual DJ EQ move on the
INCOMING track of a mixtape seam (Kim 2026-09-16).

Why this exists: a real DJ brings a new track in with the low end (and often the
top end) pulled out — the incoming track starts "thin", mostly mids — then
progressively opens the mids/highs while the outgoing track is still playing, and
only snaps the BASS back in fast right at the moment the new track's beat actually
locks in (the "kick" instant: a strong downbeat where the new groove properly
starts). Doing this by ear is exactly how DJs avoid two basslines fighting in a
crossfade — the low end doesn't clash until the outgoing track is basically gone.
This module is the programmatic version of that automation curve, meant to run on
the incoming clip's audio ahead of / during a mixtape seam blend (see
mixtape_seam_align_test.py and chain_outpaint_xfade_a2a.py for the seam machinery
this is meant to sit alongside — this module is audio-domain EQ only, no latent
work, no model calls).

Timeline (see eq_sweep_incoming docstring for the exact contract):
    t_start                  t_kick   t_kick+bass_ramp_sec        t_end
      |thin, mids-only         |bass snaps in fast|   full range     |
      |hp corner: high->low_cut|hp: low_cut -> ~open|                |
      |lp corner: high_cut->open (by t_kick)         |                |

Engineering approach — short-window segmented filtering, crossfaded (the
"simplest to get right" option): tile the active region with 50%-overlapping
Hann-windowed segments, apply a static Butterworth high-pass/low-pass cascade
per segment (corner frequencies sampled at the segment's center time off a
piecewise log-frequency schedule), zero-phase filter each segment
(`sosfiltfilt`, so no added phase smear), then reconstruct via NORMALIZED
overlap-add (divide by the summed window weight, not just assume exact COLA) —
that makes the reconstruction robust at the two boundaries of the processed
region regardless of window/hop choice, rather than relying on an exact
constant-overlap-add identity. Adjacent segments differ only slightly in their
filter corners (the schedule is smooth), so the Hann crossfade between them
produces an audibly continuous sweep with no zipper/stepping — there is never a
hard switch between two filter *states* mid-signal, only a continuous blend of
their outputs.

No prior art found for a *time-varying* EQ in this repo (2026-09-16 grep of
eval/, control/, ARCHITECTURE.md, DISCOVERIES.md for eq_sweep / time-varying
filter turned up nothing); several eval scripts define a STATIC
`bandpass()`/`highpass()` helper around `scipy.signal.butter` + `sosfiltfilt`
(e.g. eval/length_hf_comparison.py, eval/hf_clarity_diagnosis.py,
eval/musicology/latent_melody_analysis_v2/analyze_melody_encoding_v2.py) — this
module follows that same butter+sosfiltfilt convention, just with the corner
frequencies swept over time instead of fixed.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfiltfilt
from scipy.signal.windows import hann

__all__ = ["eq_sweep_incoming"]

# "Off" sentinels: a corner at/beyond these values means "skip that filter,
# it would be audibly transparent anyway" — keeps Butterworth design well away
# from numerically dicey normalized frequencies near 0 or near Nyquist.
_HP_OFF_HZ = 20.0
_LP_OFF_FRAC_OF_NYQUIST = 0.45  # capped further by an absolute ceiling below
_LP_OFF_CEILING_HZ = 20000.0

# sosfiltfilt on a 2-section (hp+lp) order-2 cascade needs len(x) > padlen
# (measured: padlen=15 for a 44.1kHz 1500/8000Hz cascade -> len<=15 raises
# ValueError). The tiling loop below can leave a final segment shorter than
# this near the tail of `tile_end` (whenever (tile_end - tile_start) % hop
# lands small) -- below this floor we skip filtering that one segment
# (passthrough) rather than crash; at <64 samples (~1.5ms @44.1kHz) the
# difference is inaudible.
_MIN_FILTER_LEN = 64


def eq_sweep_incoming(
    audio: np.ndarray,
    sr: int,
    t_start: float,
    t_kick: float,
    t_end: float,
    low_cut_hz: float = 250.0,
    high_cut_hz: float = 8000.0,
    bass_ramp_sec: float = 0.3,
    *,
    hp_start_mult: float = 6.0,
    window_sec: float = 0.30,
    filter_order: int = 2,
) -> np.ndarray:
    """Time-varying EQ sweep for a mixtape seam's INCOMING track.

    Models a manual DJ EQ move: thin/mids-only at ``t_start``, progressively
    fuller through ``[t_start, t_kick]`` (mids opening, then highs), then the
    bass snaps back in over ``bass_ramp_sec`` starting at ``t_kick`` (the
    beat-drop instant), full range from ``t_kick + bass_ramp_sec`` onward.

    Args:
        audio: ``(channels, samples)`` float array (mono ``(samples,)`` also
            accepted and returned in the same shape). Must cover at least
            ``[t_start, t_end]`` seconds at sample rate ``sr``.
        sr: sample rate in Hz.
        t_start: seconds, start of the EQ automation (incoming track begins
            thin here).
        t_kick: seconds, the strong downbeat where the new track's beat
            properly locks in — bass starts snapping back in at this instant.
        t_end: seconds, end of the automation window; audio at/after this is
            passed through unfiltered. Must satisfy ``t_start <= t_kick <=
            t_end``; the bass-restore ramp is internally clipped to end at or
            before ``t_end`` so nothing outside ``[t_start, t_end]`` is ever
            touched.
        low_cut_hz: the high-pass corner the sweep glides DOWN to by
            ``t_kick`` (bass still cut/attenuated at that corner) and then
            ramps the rest of the way open from, starting at ``t_kick``.
        high_cut_hz: the low-pass corner at ``t_start`` (mild top trim —
            "mostly mids"); this corner glides UP/opens fully by ``t_kick``.
        bass_ramp_sec: how fast the bass snaps in once ``t_kick`` hits
            (default 0.3 s — deliberately much shorter than the
            ``t_start -> t_kick`` sweep, since this is the "rapid" DJ move).
        hp_start_mult: how many multiples of ``low_cut_hz`` the starting
            high-pass corner sits at (default 6x, within the "roughly 4-8x"
            thin/mids-only starting point).
        window_sec: analysis window length in seconds for the segmented
            filter (50% hop overlap). Smaller = finer-grained sweep but more
            filter calls; 0.3 s is fine-grained relative to a multi-second
            sweep and coarse relative to audible zipper thresholds.
        filter_order: Butterworth order per side (high-pass and low-pass are
            independent cascaded filters, so effective slope is roughly
            ``2 * filter_order * 6 dB/oct`` when both are active).

    Returns:
        Array of the same shape and dtype as ``audio``. Samples outside
        ``[t_start, t_end]`` are bit-identical to the input.
    """
    x = np.asarray(audio, dtype=np.float64)
    squeeze_back = x.ndim == 1
    if squeeze_back:
        x = x[None, :]
    n_ch, n_samp = x.shape

    t_start = max(0.0, float(t_start))
    t_kick = max(t_start, float(t_kick))
    t_end = max(t_kick, float(t_end))
    ramp_end = min(t_kick + max(0.0, float(bass_ramp_sec)), t_end)

    p0 = int(round(t_start * sr))
    p1 = int(round(t_end * sr))
    p0 = min(max(p0, 0), n_samp)
    p1 = min(max(p1, p0), n_samp)

    out = x.copy()
    if p1 <= p0:
        # Degenerate/empty window — nothing to do.
        result = out[0] if squeeze_back else out
        return result.astype(audio.dtype, copy=False)

    lp_off_hz = min(_LP_OFF_FRAC_OF_NYQUIST * sr, _LP_OFF_CEILING_HZ)
    hp_start = max(low_cut_hz * hp_start_mult, low_cut_hz + 1.0)
    lp_start = min(max(high_cut_hz, low_cut_hz * 2.0), lp_off_hz)
    hp_kick = max(low_cut_hz, _HP_OFF_HZ * 1.01)

    # Piecewise-log-frequency corner schedule, three breakpoints:
    #   t_start -> thin start;  t_kick -> mids+highs open, bass still cut;
    #   ramp_end -> fully open. np.interp clamps outside this range to the
    # nearest edge value, which is exactly what we want on both sides:
    # "hp_start" for context just before t_start, "off" for the tail after
    # ramp_end out to t_end.
    cp_t = np.maximum.accumulate(np.array([t_start, t_kick, ramp_end], dtype=np.float64))
    log_cp_hp = np.log(np.array([hp_start, hp_kick, _HP_OFF_HZ], dtype=np.float64))
    log_cp_lp = np.log(np.array([lp_start, lp_off_hz, lp_off_hz], dtype=np.float64))

    def corners_at(t_center: float) -> tuple[float, float]:
        hp = float(np.exp(np.interp(t_center, cp_t, log_cp_hp)))
        lp = float(np.exp(np.interp(t_center, cp_t, log_cp_lp)))
        return hp, lp

    win_len = max(int(round(window_sec * sr)), 64)
    if win_len % 2:
        win_len += 1
    hop = win_len // 2
    window = hann(win_len, sym=False)  # periodic Hann: exact COLA at 50% hop

    # Tile one extra window of context on each side of [p0, p1) so every
    # output sample in the active region is covered by >=2 overlapping
    # windows (robust crossfade at the edges too, not just the interior).
    tile_start = max(p0 - win_len, 0)
    tile_end = min(p1 + win_len, n_samp)

    acc = np.zeros((n_ch, n_samp), dtype=np.float64)
    wsum = np.zeros(n_samp, dtype=np.float64)
    nyq = sr / 2.0

    pos = tile_start
    while pos < tile_end:
        seg_end = min(pos + win_len, n_samp)
        seg_len = seg_end - pos
        if seg_len <= 0:
            break
        w = window[:seg_len]
        t_center = (pos + seg_len / 2.0) / sr
        hp, lp = corners_at(t_center)

        chunk = x[:, pos:seg_end]
        need_hp = hp > _HP_OFF_HZ
        need_lp = lp < lp_off_hz
        if (need_hp or need_lp) and seg_len > _MIN_FILTER_LEN:
            sos_list = []
            if need_hp:
                hp_n = min(hp, nyq * 0.99)
                sos_list.append(butter(filter_order, hp_n, btype="high", fs=sr, output="sos"))
            if need_lp:
                lp_n = min(max(lp, 1.0), nyq * 0.99)
                sos_list.append(butter(filter_order, lp_n, btype="low", fs=sr, output="sos"))
            sos = np.vstack(sos_list)
            filtered = sosfiltfilt(sos, chunk, axis=-1)
        else:
            filtered = chunk

        acc[:, pos:seg_end] += filtered * w[None, :]
        wsum[pos:seg_end] += w
        pos += hop

    covered = np.where(wsum > 1e-8)[0]
    if covered.size:
        lo, hi = int(covered.min()), int(covered.max()) + 1
        out[:, lo:hi] = acc[:, lo:hi] / wsum[lo:hi]

    # Safety net, not the mechanism: a resonance-free Butterworth cascade
    # shouldn't add energy, but clamp defensively so a pathological input
    # can never hand a clipped sample downstream un-flagged. Do this BEFORE
    # restoring the passthrough region below, not after: SA3's raw
    # (un-normalized) generate() output routinely has peaks above +-1
    # (MASTER.md Sec 5 "audio file writers clip" gotcha), and clipping here
    # after the passthrough copy would silently break the "bit-identical
    # outside [t_start, t_end]" contract for exactly that input.
    np.clip(out, -1.0, 1.0, out=out)

    # Contract: bit-identical outside [t_start, t_end] no matter what the
    # windowing above touched incidentally via its context margin, or what
    # the clip above just did to samples in that range.
    out[:, :p0] = x[:, :p0]
    out[:, p1:] = x[:, p1:]

    result = out[0] if squeeze_back else out
    return result.astype(audio.dtype, copy=False)
