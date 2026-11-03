#!/usr/bin/env python3
# Owner: CONTINUITY (created 2026-11-03)
"""d2_wave_operator.py -- EXPERIMENTS D2 (registered 2026-08-19): does a wave operator on SAME chroma planes separate pad / glide / arp?

Operator: 2-D Fourier energy of a (128, T) chroma plane, binned by velocity v = k_time / k_pitch (1 bin/frame is about 1 semitone/s). A line moving
at v bins per frame concentrates on k_t = -v k_p. k_p = 0 is left out, so global loudness and percussion pumping do not count as motion.
Corpus-demeaned per bin, the "whitening" this repo found necessary for chroma (journal 2026-08-11).

Meter comes first (CLAUDE.md, audit the instrument):
  A. known rates: synthetic glides at 1..48 st/s, both directions. Does the measured velocity track the true rate, and where does it stop?
  B. known classes: pad, glide, arp, alone and mixed over drums. 5-fold accuracy against two baselines with no pitch-time geometry:
     chroma flux (one number) and the per-bin temporal modulation spectrum.
  C. same gestures INJECTED into real corpus crops (-6 dB, real music as the distractor), split by crop.
  D. real crops only, artist held-out: does the operator add anything over flux at predicting onset_density?
KILL: if it does not beat the baselines in C, L_wave has no case and stays shelved. Result only on these meters: no guidance term is tried here.
RUN: nice -n 10 .venv/bin/python eval/d2_wave_operator.py   (CPU only)
"""
import json, glob, os, re, sys
import numpy as np
from concurrent.futures import ProcessPoolExecutor
os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.path.insert(0, "/home/kim/Projects/mir-same-chroma/src")
from harmonic.same_chroma import compute_same_chroma
OUT = "/home/kim/Projects/SAO/eval/musicology/d2_wave_operator_2026-11-03"
SR, DUR, FPS, BINS_ST = 44100, 20.0, 44100 / 4096, 128 / 12
BANDS = {"mid": 1, "air": 2}
VEDGES = np.array([0, .25, .75, 2, 4, 8, 16, 32, 64, 1e9])
LAT = "/run/media/kim/Kosmos/latents/latents_sa3"
SRC = "/run/media/kim/Mantu/ai-music/Goa_Separated"


def saw(f_inst, partials=24):
    ph = 2 * np.pi * np.cumsum(f_inst) / SR
    out = np.zeros_like(ph)
    for k in range(1, partials + 1):
        out += np.where(k * f_inst < SR * .45, np.sin(k * ph) / k, 0)
    return out


def pad(rng):
    root = 440 * 2 ** (rng.integers(-5, 7) / 12)
    n = int(SR * DUR)
    x = sum(saw(np.full(n, root * 2 ** (s / 12))) for s in (0, rng.choice([3, 4]), 7))
    return x * (1 + .2 * np.sin(2 * np.pi * rng.uniform(.1, .5) * np.arange(n) / SR))


def glide(rng, rate=None, sign=None):
    rate = rng.choice([3., 6., 12., 24.]) if rate is None else rate
    sign = rng.choice([-1, 1]) if sign is None else sign
    n = int(SR * DUR)
    semis = (rng.uniform(0, 12) + sign * rate * np.arange(n) / SR) % 24      # sawtooth sweep over two octaves
    return saw(440 * 2 ** ((semis - 12) / 12))


def arp(rng):
    n = int(SR * DUR)
    step = 60 / rng.uniform(138, 150) / 4
    pat = rng.choice([0, 3, 5, 7, 10, 12, 15], size=rng.choice([4, 8]))
    root = rng.integers(-7, 5)
    idx = (np.arange(n) / SR / step).astype(int)
    semis = root + pat[idx % len(pat)]
    env = np.exp(-((np.arange(n) / SR) % step) / (step * .6))
    return saw(440 * 2 ** (semis / 12)) * env


def drums(rng):
    n = int(SR * DUR)
    t = np.arange(n) / SR
    beat = 60 / rng.uniform(138, 150)
    k = np.sin(2 * np.pi * 55 * t) * np.exp(-(t % beat) / .08)
    h = rng.standard_normal(n) * np.exp(-((t + beat / 2) % beat) / .02)
    return k + .5 * h


GEN = {"pad": pad, "glide": glide, "arp": arp}


def plane(x):
    x = x / (np.abs(x).max() + 1e-9) * .8
    ch = compute_same_chroma(np.stack([x, x], 1), SR, align_to_latent=False)
    return {b: np.asarray(ch[i], np.float64) for b, i in BANDS.items()}


def wave(P):
    """velocity energy fractions, signed: [up bands..., down bands...], plus static."""
    T = P.shape[1]
    F = np.abs(np.fft.fft2(P * np.hanning(T)[None])) ** 2
    kp, kt = np.fft.fftfreq(128), np.fft.fftfreq(T)
    Kp, Kt = np.meshgrid(kp, kt, indexing="ij")
    mask = (np.abs(Kp) > 0) & (np.abs(Kp) <= 12 / 128)       # one cycle per 128 bins up to about semitone detail
    v = np.where(mask, -Kt / np.where(Kp == 0, 1, Kp), 0) * FPS / BINS_ST    # st/s, sign = direction
    tot = F[mask].sum() + 1e-12
    out = []
    for s in (1, -1):
        for a, b in zip(VEDGES[:-1], VEDGES[1:]):
            m = mask & (s * v >= a) & (s * v < b)
            out.append(F[m].sum() / tot)
    return np.array(out)


def speed_centroid(w):
    n = len(VEDGES) - 1
    e = w[:n] + w[n:]
    c = np.sqrt(VEDGES[:-1].clip(.1) * VEDGES[1:].clip(max=128))
    return float(np.exp((e * np.log(c)).sum() / (e.sum() + 1e-12)))


def flux(P):
    d = np.diff(P, axis=1)
    return float(np.sqrt((d ** 2).sum(0)).mean())


def mod_spec(P):
    F = np.abs(np.fft.rfft(P * np.hanning(P.shape[1])[None], axis=1)) ** 2
    F = F.mean(0)
    idx = np.array_split(np.arange(len(F)), 10)
    v = np.array([F[i].sum() for i in idx])
    return v / (v.sum() + 1e-12)


def _synth(a):
    kind, seed, with_drums = a
    r = np.random.default_rng(seed)
    x = GEN[kind](r)
    if with_drums:
        x = x / np.abs(x).max() + .7 * drums(r) / 1.5
    return kind, plane(x)


def _rate(a):
    rate, sign, seed = a
    r = np.random.default_rng(seed)
    return rate, sign, plane(glide(r, rate, sign))


def crop_list(n):
    rng = np.random.default_rng(7)
    ids = [os.path.basename(f)[:-5] for f in sorted(glob.glob(f"{LAT}/[0-9]*.json"))]
    rng.shuffle(ids)
    out = []
    for i in ids:
        try:
            j = json.load(open(f"{LAT}/{i}.json"))
            st = j["source_track"]
            p = f"{SRC}/{st}/full_mix.flac"
            if os.path.exists(p):
                out.append((i, p, float(j.get("seconds_start", 0) or 0), float(j["onset_density"]), float(j.get("onset_per_beat", 0)), st))
        except Exception:
            pass
        if len(out) >= n:
            break
    return out


def _real(a):
    import soundfile as sf
    (cid, p, start, od, opb, st), inject, seed = a
    try:
        info = sf.info(p)
        s0 = min(int((start + 30) * info.samplerate), max(0, info.frames - int(DUR * info.samplerate)))
        x, sr = sf.read(p, start=s0, frames=int(DUR * info.samplerate), always_2d=True)
        if sr != SR or len(x) < int(DUR * SR):
            return None
        x = x.mean(1)
        if inject:
            g = GEN[inject](np.random.default_rng(seed))
            x = x / (np.sqrt((x ** 2).mean()) + 1e-9) + .5 * g / (np.sqrt((g ** 2).mean()) + 1e-9)
        return cid, st, od, opb, inject, plane(x)
    except Exception as e:
        return None


def cv_acc(X, y, g=None):
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold, StratifiedKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    sp = GroupKFold(5).split(X, y, g) if g is not None else StratifiedKFold(5, shuffle=True, random_state=0).split(X, y)
    ok = np.zeros(len(y), bool)
    for a, b in sp:
        ok[b] = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.)).fit(X[a], y[a]).predict(X[b]) == y[b]
    return float(ok.mean())


def demean(ps):
    mu = np.mean([p.mean(1) for p in ps], 0)
    return [p - mu[:, None] for p in ps]


def main():
    os.makedirs(OUT, exist_ok=True)
    R = {}
    from scipy.stats import spearmanr
    with ProcessPoolExecutor(10) as ex:
        print("A rates", flush=True)
        jobs = [(r, s, i) for r in (1., 2., 3., 6., 12., 24., 48.) for s in (1, -1) for i in range(4)]
        res = list(ex.map(_rate, jobs))
        for b in BANDS:
            ps = demean([x[2][b] for x in res])
            rows = {}
            for (rate, sign, _), P in zip(res, ps):
                w = wave(P)
                n = len(VEDGES) - 1
                rows.setdefault(rate, []).append((speed_centroid(w), float(np.sign(w[:n].sum() - w[n:].sum()) == sign), flux(P)))
            R[f"A_{b}"] = {str(k): {"speed_centroid_st_s": round(float(np.median([x[0] for x in v])), 2), "direction_correct": float(np.mean([x[1] for x in v])), "flux": round(float(np.mean([x[2] for x in v])), 4)} for k, v in rows.items()}
            rates = [x[0] for x in res]
            R[f"A_{b}_spearman"] = {"wave": round(float(spearmanr(rates, [speed_centroid(wave(P)) for P in ps])[0]), 3), "flux": round(float(spearmanr(rates, [flux(P) for P in ps])[0]), 3)}
            print(b, R[f"A_{b}"], R[f"A_{b}_spearman"], flush=True)
        print("B classes", flush=True)
        jobs = [(k, 1000 * i + j, d) for i, k in enumerate(GEN) for j in range(60) for d in (False, True)]
        res = list(ex.map(_synth, jobs))
        y = np.array([x[0] for x in res])
        for b in BANDS:
            ps = demean([x[1][b] for x in res])
            X = np.array([wave(P) for P in ps]); Fx = np.array([[flux(P)] for P in ps]); M = np.array([mod_spec(P) for P in ps])
            R[f"B_{b}"] = {"wave": cv_acc(X, y), "flux": cv_acc(Fx, y), "modspec": cv_acc(M, y), "chance": 1 / 3, "n": len(y)}
            print(b, R[f"B_{b}"], flush=True)
        print("C injected into real", flush=True)
        crops = crop_list(300)
        print(len(crops), "crops", len({c[5] for c in crops}), "tracks", flush=True)
        jobs = [(c, k, 5000 + i) for i, c in enumerate(crops) for k in GEN]
        res = [x for x in ex.map(_real, jobs, chunksize=4) if x is not None]
        y = np.array([x[4] for x in res]); g = np.array([x[1] for x in res])
        for b in BANDS:
            ps = demean([x[5][b] for x in res])
            X = np.array([wave(P) for P in ps]); Fx = np.array([[flux(P)] for P in ps]); M = np.array([mod_spec(P) for P in ps])
            R[f"C_{b}"] = {"wave": cv_acc(X, y, g), "flux": cv_acc(Fx, y, g), "modspec": cv_acc(M, y, g), "wave+modspec": cv_acc(np.c_[X, M], y, g), "chance": 1 / 3, "n": len(y), "tracks": len(set(g))}
            print(b, R[f"C_{b}"], flush=True)
        print("D real crops", flush=True)
        res = [x for x in ex.map(_real, [(c, None, 0) for c in crops], chunksize=4) if x is not None]
    from sklearn.linear_model import RidgeCV
    from sklearn.model_selection import GroupKFold
    from sklearn.metrics import r2_score
    od = np.array([x[2] for x in res]); art = np.array([re.split(r"\s+-\s+", x[1])[0].lower() for x in res])
    for b in BANDS:
        ps = demean([x[5][b] for x in res])
        X = np.array([wave(P) for P in ps]); Fx = np.array([[flux(P)] for P in ps]); M = np.array([mod_spec(P) for P in ps])
        d = {"n": len(od), "artists": len(set(art))}
        for name, Z in (("flux", Fx), ("modspec", M), ("wave", X), ("flux+wave", np.c_[Fx, X])):
            Z = (Z - Z.mean(0)) / (Z.std(0) + 1e-9)
            s = np.zeros(len(od))
            for a, c in GroupKFold(5).split(Z, od, art):
                s[c] = RidgeCV(alphas=np.logspace(-2, 3, 12)).fit(Z[a], od[a]).predict(Z[c])
            d[name] = round(float(r2_score(od, s)), 3)
        R[f"D_{b}"] = d
        print(b, d, flush=True)
    json.dump(R, open(f"{OUT}/results.json", "w"), indent=1)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
