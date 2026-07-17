#!/usr/bin/env python3
"""chroma384_eval.py -- control-response eval for 384-d same-chroma steering
(spec: docs/superpowers/specs/2026-07-16-chroma384-eval-design.md).

Subcommands:
  build-targets  write the five target types (T1 reference / T2 static-12TET /
                 T3 palette / T4 progression / T5 wrong-key) as .npz jobs
  score          score rendered clips: Delta-cos12 vs same-seed gain-0 baseline
                 (the chroma-trap rule), per band, + key detect via essentia
  render         drive the a2a renders through chroma_morph_transitions
                 machinery (GPU; pilot Fri night)

mir venv. Targets are (3, 128, T) SAME-format, band-major.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, "/home/kim/Projects/mir-same-chroma/src")
from harmonic.same_chroma import (compute_same_chroma, fold_to_12,        # noqa: E402
                                  make_steering_target, PITCH_CLASSES)

SAO = Path("/home/kim/Projects/SAO")
FPS = 10.7666

MINOR = np.array([1, 0, .4, .8, 0, .6, 0, .9, .5, 0, .7, 0], float)  # natural-minor-ish profile


def _rot(w, root): return np.roll(w, root)


def t2_static(n_frames, root, gain=1.0):
    return make_steering_target(n_frames, _rot(MINOR, root), bass_root=root,
                                bass_gain=gain, mid_gain=gain)


def t4_progression(n_frames, roots, gain=1.0):
    seg = n_frames // len(roots)
    tgt = np.zeros((3, 128, n_frames), np.float32)
    for i, r in enumerate(roots):
        s, e = i * seg, (n_frames if i == len(roots) - 1 else (i + 1) * seg)
        tgt[:, :, s:e] = t2_static(e - s, r, gain)
    return tgt


def cos12(a12, b12):
    """time-avg cosine of 12-d profiles, per band. a12/b12: (3,12) or (3,12,T)."""
    if a12.ndim == 3: a12 = a12.mean(-1)
    if b12.ndim == 3: b12 = b12.mean(-1)
    num = (a12 * b12).sum(-1)
    den = np.linalg.norm(a12, axis=-1) * np.linalg.norm(b12, axis=-1) + 1e-9
    return num / den


def clip_chroma12(path):
    import librosa
    y, sr = librosa.load(path, sr=44100, mono=False)
    if y.ndim == 1: y = np.stack([y, y])
    return fold_to_12(compute_same_chroma(y.T, sr))          # (3,12,T)


def score(args):
    """jobs json rows: {clip, baseline, target_npz, name}. Emits Delta-cos12."""
    jobs = json.load(open(args.jobs))
    out = []
    for j in jobs:
        t12 = fold_to_12(np.load(j["target_npz"])["target"])
        c_out, c_base = clip_chroma12(j["clip"]), clip_chroma12(j["baseline"])
        d = cos12(c_out, t12) - cos12(c_base, t12)           # (3,) per band
        row = {"name": j["name"], "dcos12_bass": round(float(d[0]), 4),
               "dcos12_mid": round(float(d[1]), 4), "dcos12_air": round(float(d[2]), 4)}
        try:                                                  # independent extractor check
            import essentia.standard as es
            audio = es.MonoLoader(filename=j["clip"], sampleRate=44100)()
            key, scale, strength = es.KeyExtractor()(audio)
            row.update({"key": f"{key}{'m' if scale=='minor' else ''}", "key_strength": round(float(strength), 3)})
        except Exception as e:
            row["key"] = f"err:{e}"
        out.append(row); print(row, flush=True)
    Path(args.out).write_text(json.dumps(out, indent=1))


def selftest(args):
    """Metric-direction sanity on the SHIPPED morph render (no GPU): the
    'coolest in 30 years' clip folded to F#m melody -> a T2 F#-minor target
    must out-cosine a wrong-key (C-major-ish) target."""
    clip = "/run/media/kim/Mantu/sa3_lora_runs/chroma_morph_transitions/kaikki2angelic__w1024_nl42_chroma.wav"
    c12 = clip_chroma12(clip)
    fsharp = 6
    good = fold_to_12(t2_static(64, fsharp))
    wrong = fold_to_12(make_steering_target(64, _rot(np.array([1,0,.5,0,.8,.6,0,.9,0,.7,0,.4]), 0), bass_root=0))
    cg, cw = cos12(c12, good), cos12(c12, wrong)
    print("clip vs F#m target  cos12 bass/mid: %.3f / %.3f" % (cg[0], cg[1]))
    print("clip vs C-maj target cos12 bass/mid: %.3f / %.3f" % (cw[0], cw[1]))
    ok = cg[1] > cw[1]
    print("METRIC DIRECTION:", "OK (matched key wins)" if ok else "FAIL")
    return 0 if ok else 1


def build_targets(args):
    outdir = Path(args.out); outdir.mkdir(parents=True, exist_ok=True)
    n = int(args.frames)
    jobs = []
    root = int(args.root)
    specs = {
        "T2_static": t2_static(n, root),
        "T4_prog": t4_progression(n, [root, (root + 5) % 12, (root + 10) % 12, root]),
        "T5_wrongkey": t2_static(n, (root + 1) % 12),
    }
    if args.reference:
        import librosa
        y, sr = librosa.load(args.reference, sr=44100, mono=False)
        if y.ndim == 1: y = np.stack([y, y])
        c = compute_same_chroma(y.T, sr)
        from harmonic.same_chroma import interpolate_linear
        specs["T1_reference"] = interpolate_linear(c, n).astype(np.float32)
    for name, tgt in specs.items():
        np.savez_compressed(outdir / f"{name}.npz", target=tgt)
        jobs.append({"name": name, "target_npz": str(outdir / f"{name}.npz")})
    (outdir / "jobs.json").write_text(json.dumps(jobs, indent=1))
    print(f"wrote {len(jobs)} targets -> {outdir} (root={PITCH_CLASSES[root]})")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build-targets"); b.add_argument("--out", default=str(SAO / "eval/chroma384_targets"))
    b.add_argument("--frames", default=256); b.add_argument("--root", default=6)
    b.add_argument("--reference", default="")
    s = sub.add_parser("score"); s.add_argument("--jobs", required=True); s.add_argument("--out", required=True)
    sub.add_parser("selftest")
    a = ap.parse_args()
    if a.cmd == "build-targets": build_targets(a)
    elif a.cmd == "score": score(a)
    else: sys.exit(selftest(a))


if __name__ == "__main__":
    main()
