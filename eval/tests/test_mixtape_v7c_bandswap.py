"""v7c band-swap render on SYNTHETIC clips (no Mantu data, no GPU): LR4 flatness, one bassline at a time, hand-over on
A's downbeat, finite output. Written while the clip drive was offline; real clips are the next check (replaycheck + gates)."""
import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfreqz, sosfiltfilt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mixtape_assemble_v7 as v7  # noqa: E402

SR = v7.SR
BPM = 140.0
BAR = int(round(240.0 / BPM * SR))


def clip(bass_hz, hat_seed, bars=16):
    n = BAR * bars
    t = np.arange(n) / SR
    rng = np.random.default_rng(hat_seed)
    kick = np.zeros(n, dtype=np.float32)
    for k in range(bars * 4):
        c = int(k * 60 / BPM * SR)
        m = min(4000, n - c)
        kick[c:c + m] += (np.exp(-np.arange(m) / 900) * np.sin(2 * np.pi * 50 * np.arange(m) / SR)).astype(np.float32)
    bass = (0.3 * np.sin(2 * np.pi * bass_hz * t)).astype(np.float32)
    hats = (0.05 * rng.standard_normal(n)).astype(np.float32)
    x = kick + bass + hats
    return np.stack([x, x]), np.arange(bars) * BAR / SR


def test_lr4_pair_is_magnitude_flat():
    w, hl = sosfreqz(v7.lr4_sos(150.0, "low"), worN=2048, fs=SR)
    _, hh = sosfreqz(v7.lr4_sos(150.0, "high"), worN=2048, fs=SR)
    mag = np.abs(hl + hh)
    assert abs(20 * np.log10(mag)).max() < 0.1


def build(handover_frac=0.8):
    A, adb = clip(55.0, 1)
    B, bdb = clip(43.65, 2)
    clips = [{"X": A, "Xdb": adb, "bpm": BPM}, {"X": B, "Xdb": bdb, "bpm": BPM}]
    W = 4
    L = W * BAR
    in_pos = BAR                                             # entry downbeat: one bar of pre-roll exists before it
    p = in_pos + 6 * BAR
    pa = {"T": 0, "in_pos": in_pos, "p": p, "L": L, "end_pos": p + L, "shift": 0}
    t_b = pa["T"] + (p - in_pos)
    pb = {"T": t_b, "in_pos": in_pos, "p": 0, "L": 0, "end_pos": in_pos + 8 * BAR, "shift": 0}
    total = pb["T"] + (pb["end_pos"] - pb["in_pos"])
    mix, info = v7.render_bandswap(clips, [pa, pb], [{}], 2, total, handover_frac=handover_frac)
    return mix[:, :total], info[0], A, B, pa, pb


def test_finite_and_handover_on_a_downbeat():
    mix, info, *_ = build()
    assert np.isfinite(mix).all() and np.abs(mix).max() < 4
    assert info["handover_dist_to_A_downbeat_ms"] < 0.1       # exactly one grid sample


def test_one_bassline_at_a_time():
    mix, info, A, B, pa, pb = build()
    assert info["ncc_low_before_A"] > 0.9 and abs(info["ncc_low_before_B"]) < 0.3
    assert info["ncc_low_after_B"] > 0.9 and abs(info["ncc_low_after_A"]) < 0.3


def test_handover_is_late_when_asked():
    early = build(0.3)[1]["handover_sample"]
    late = build(0.9)[1]["handover_sample"]
    assert late > early
