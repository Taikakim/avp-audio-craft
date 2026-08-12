#!/usr/bin/env python
"""nspace.py — per-stem NEGATIVE-SPACE (gate-rhythm) descriptor from RMS.

Kim 2026-08-12: the "space" between notes is a rhythm at a lower level of the hierarchy
(Eisner: the action happens between the frames). It lives in the RMS envelope — but only
per-STEM: a full mix never goes dark (layers fill each other's gaps), so a single element's
negative space is only visible in isolation. INTENTIONALITY IS EMERGENT: we measure EVERY
stem and let the metric self-select — a sustained pad reads ~flat (no trough rhythm), a 16th
bass/arp/hat reads a strong periodic trough rhythm. No pre-labelling of "which stems should".

Per stem, from the RMS envelope e(t) (normalised to peak):
  - silence_frac   = fraction of frames below a floor (the low-energy duty cycle = how much space)
  - trough_strength= strongest normalised autocorrelation peak of (e - mean(e)) in a musical
                     lag range = HOW PERIODIC the gate/space pattern is (0=constant, 1=strictly periodic)
  - period_s       = lag of that peak = the note-division rate of the space rhythm
  - env_flux       = mean |Δe| = raw envelope activity (sanity: pads low, percussion high)
Rhythmic-gate stems (bass/arp/hat/perc) surface with high trough_strength; sustained
stems (pads/sustained leads) read low. The metric IS the intentionality detector.

Run: /home/kim/Projects/mir/mir/bin/python nspace.py "<track dir>" [--sr 16000] [--fps 100]
Reads <track dir>/_classification.json for per-stem category labels (Kim's own, unverified —
used for REPORTING only, never to filter the measurement).
"""
import argparse, glob, json, os, sys
import numpy as np

SR = 16000
FPS = 100                      # RMS-envelope frame rate (Hz)
FLOOR = 0.08                   # normalised-RMS floor defining "space"
LAG_MIN_S, LAG_MAX_S = 0.05, 0.6   # gate-rhythm period search (fast: 20 Hz .. ~1.7 Hz)
DETREND_S = 1.0                    # highpass window: remove swells slower than ~1 s


def nspace_metrics(env, fps=FPS, floor=FLOOR):
    """Pure fn: normalised RMS envelope (>=0) -> negative-space metrics.
    space_score = silence_frac * trough_strength needs BOTH real silence AND periodicity:
    a pad (no silence) and a random-gap drone (no periodicity) both read ~0; only a
    rhythmically-gated stem (16th bass/arp/hat) scores high. NB trough_strength alone is
    amplitude-blind (normalised AC ~1 for any smooth signal) -> never rank on it alone."""
    env = np.asarray(env, np.float64)
    d = dict(silence_frac=0.0, trough_strength=0.0, period_s=0.0, env_flux=0.0, space_score=0.0)
    peak = env.max()
    if peak <= 0:
        d['silence_frac'] = 1.0
        return d
    e = env / peak
    d['silence_frac'] = float((e < floor).mean())
    d['env_flux'] = float(np.abs(np.diff(e)).mean())
    w = max(3, int(round(DETREND_S * fps)))              # highpass: kill swells slower than ~1 s
    x = e - np.convolve(e, np.ones(w) / w, mode='same')  # (a pad swells periodically too)
    denom = float(x @ x)
    lo, hi = int(LAG_MIN_S * fps), min(int(LAG_MAX_S * fps), len(x) - 1)
    if denom >= 1e-9 and hi > lo + 1:
        ac = np.correlate(x, x, 'full')[len(x) - 1:] / denom
        seg = ac[lo:hi]
        # a real gate rhythm makes AC PEAK at the period; a smooth/sparse envelope's AC just
        # decays monotonically from lag 0 (global-max would sit at the floor = spurious, and a
        # stem that's merely SPARSE — long silent gaps, not fast gating — has no periodic peak).
        # Require a genuine local maximum = true periodicity.
        peaks = [(seg[i], i) for i in range(1, len(seg) - 1)
                 if seg[i] > seg[i - 1] and seg[i] >= seg[i + 1]]
        if peaks:
            val, i = max(peaks)
            d['trough_strength'] = float(val)
            d['period_s'] = round((lo + i) / fps, 4)
    d['space_score'] = round(d['silence_frac'] * d['trough_strength'], 4)
    return d


def _self_test():
    fps = 100
    t = np.arange(0, 10, 1 / fps)
    # sustained pad: constant + slow swell -> low trough_strength
    pad = 0.8 + 0.05 * np.sin(2 * np.pi * 0.1 * t)
    m_pad = nspace_metrics(pad, fps)
    # 16th-ish gate at 8 Hz: strong periodic trough rhythm, high silence_frac
    gate = (np.arange(len(t)) % 10 < 3).astype(float)   # 3-frame pulse every 10 frames = 0.1 s period
    m_gate = nspace_metrics(gate, fps)
    # space_score (silence * periodicity) is the honest separator; trough alone is amplitude-blind
    assert m_gate['space_score'] > 0.3 > m_pad['space_score'], (m_pad, m_gate)
    assert m_gate['silence_frac'] > m_pad['silence_frac']
    assert abs(m_gate['period_s'] - 0.1) < 0.02, m_gate['period_s']   # integer-frame period
    print('[self-test] nspace_metrics: space_score separates pad vs gate OK', flush=True)


def rms_env(path, sr=SR, fps=FPS):
    import librosa
    y, _sr = librosa.load(path, sr=sr, mono=True)
    hop = max(1, int(round(sr / fps)))
    return librosa.feature.rms(y=y, frame_length=hop * 4, hop_length=hop)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('track_dir')
    ap.add_argument('--sr', type=int, default=SR)
    ap.add_argument('--fps', type=int, default=FPS)
    ap.add_argument('--limit', type=int, default=0, help='cap #stems (smoke)')
    args = ap.parse_args()
    _self_test()
    cj = os.path.join(args.track_dir, '_classification.json')
    cats = {}
    if os.path.exists(cj):
        cats = {k: v.get('category', '?') for k, v in json.load(open(cj)).get('stems', {}).items()}
    stems = sorted(f for f in glob.glob(os.path.join(args.track_dir, '*.flac'))
                   if 'full mix' not in os.path.basename(f).lower())
    if args.limit:
        stems = stems[:args.limit]
    rows = []
    for p in stems:
        b = os.path.basename(p)
        try:
            m = nspace_metrics(rms_env(p, args.sr, args.fps), args.fps)
        except Exception as e:
            print(f'  SKIP {b[:40]}: {str(e)[:50]}', flush=True); continue
        rows.append((cats.get(b, '?'), b, m))
    rows.sort(key=lambda r: -r[2]['space_score'])
    print(f'\n{"cat":<8} {"space":>6} {"trough":>6} {"period":>7} {"silence":>7} {"flux":>6}  stem')
    for cat, b, m in rows:
        print(f'{cat:<8} {m["space_score"]:6.3f} {m["trough_strength"]:6.3f} {m["period_s"]:7.3f} '
              f'{m["silence_frac"]:7.3f} {m["env_flux"]:6.3f}  {b[:46]}', flush=True)


if __name__ == '__main__':
    main()
