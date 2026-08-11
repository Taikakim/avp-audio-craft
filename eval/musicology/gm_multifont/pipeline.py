#!/usr/bin/env python
"""pipeline.py -- GM multi-font melody probe: does timbre encoding cluster by GM patch
number ACROSS soundfonts, and do SAME latent frames carry pitch-independent HYSTERESIS
(predecessor-note memory)?

Reuses: eval/musicology/gm_timbre_pitch/pipeline.py (fluidsynth render convention,
kill+retry-once, SAME pretransform encode, .gpu.lock discipline) and
eval/musicology/test_midis_v2/gen_test_midis_v2.py (write_midi tick math -- called here
with bars=1 and ABSOLUTE step indices 0..255 so one call renders the whole 16-bar battery
without per-bar repetition) and ridge/LDA helpers from
eval/musicology/latent_melody_analysis/analyze_melody_encoding.py.

Stages (--stages select,gen,render,encode,analyze):
  select   CPU. 40 Kim-listed GM programs x <=16 fonts/variants from sf2_catalog ->
           selection.csv.
  gen      CPU. ONE MIDI: the interval battery (pedal / oscillation cells k in
           {1,2,3,5,7,12} / recovery / mixed pivot run) -> manifest.json ground-truth grid.
  render   CPU. fluidsynth per selection row (bank-select CC0 + program_change), kill+retry
           once on hang, else skip+log.
  encode   GPU. ONE .gpu.lock window (handle CONTINUITY-gmmf), SAME pretransform, fp16.
  analyze  CPU. (a) program-number clustering (silhouette, within/cross cosine + permutation
           p, generic-supercluster replication), (b) interval decodability (LDA per k, per
           direction), (c) hysteresis (predecessor-identity classifier + decay curve +
           release-tail-vs-intrinsic control), (d) REPORT.md + results.json + hysteresis_decay.csv.
"""
import argparse
import csv
import itertools
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

BASE = Path("/home/kim/Projects/SAO/eval/musicology/gm_multifont")
MIDIS = BASE / "midis"
RENDERS = BASE / "renders"
LATENTS = BASE / "latents"
SF2_JSONL = Path("/home/kim/Projects/SAO/eval/musicology/sf2_catalog/sf2_presets.jsonl")
GPU_LOCK = Path("/home/kim/Projects/SAO/.gpu.lock")
FILELOCK_PY = "/home/kim/Projects/SAO/Misc/filelock.py"
HANDLE = "CONTINUITY-gmmf"
SR = 44100
BPM = 161.4990234375  # 16th == 1 SAME frame (lock 1)
NFRAMES = 256  # 16 bars x 16 sixteenths

sys.path.insert(0, "/home/kim/Projects/SAO/eval/musicology/test_midis_v2")
import gen_test_midis_v2 as genv2  # noqa: E402  (write_midi, TICKS_16TH conventions)
sys.path.insert(0, "/home/kim/Projects/SAO/eval/musicology/latent_melody_analysis")
import analyze_melody_encoding as v1  # noqa: E402  (ridge_loo)

E3 = 52  # matches gen_test_midis_v2's E3

# ---------------------------------------------------------------- GM program list, names
GM_NAMES = [
    "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano", "Honky-tonk Piano",
    "Electric Piano 1", "Electric Piano 2", "Harpsichord", "Clavinet",
    "Celesta", "Glockenspiel", "Music Box", "Vibraphone", "Marimba", "Xylophone", "Tubular Bells", "Dulcimer",
    "Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ", "Reed Organ", "Accordion", "Harmonica", "Tango Accordion",
    "Acoustic Guitar (nylon)", "Acoustic Guitar (steel)", "Electric Guitar (jazz)", "Electric Guitar (clean)",
    "Electric Guitar (muted)", "Overdriven Guitar", "Distortion Guitar", "Guitar Harmonics",
    "Acoustic Bass", "Electric Bass (finger)", "Electric Bass (pick)", "Fretless Bass",
    "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2",
    "Violin", "Viola", "Cello", "Contrabass", "Tremolo Strings", "Pizzicato Strings", "Orchestral Harp", "Timpani",
    "String Ensemble 1", "String Ensemble 2", "Synth Strings 1", "Synth Strings 2",
    "Choir Aahs", "Voice Oohs", "Synth Voice", "Orchestra Hit",
    "Trumpet", "Trombone", "Tuba", "Muted Trumpet", "French Horn", "Brass Section", "Synth Brass 1", "Synth Brass 2",
    "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax", "Oboe", "English Horn", "Bassoon", "Clarinet",
    "Piccolo", "Flute", "Recorder", "Pan Flute", "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina",
    "Lead 1 (square)", "Lead 2 (sawtooth)", "Lead 3 (calliope)", "Lead 4 (chiff)",
    "Lead 5 (charang)", "Lead 6 (voice)", "Lead 7 (fifths)", "Lead 8 (bass+lead)",
    "Pad 1 (new age)", "Pad 2 (warm)", "Pad 3 (polysynth)", "Pad 4 (choir)",
    "Pad 5 (bowed)", "Pad 6 (metallic)", "Pad 7 (halo)", "Pad 8 (sweep)",
    "FX 1 (rain)", "FX 2 (soundtrack)", "FX 3 (crystal)", "FX 4 (atmosphere)",
    "FX 5 (brightness)", "FX 6 (goblins)", "FX 7 (echoes)", "FX 8 (sci-fi)",
    "Sitar", "Banjo", "Shamisen", "Koto", "Kalimba", "Bag pipe", "Fiddle", "Shanai",
    "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock", "Taiko Drum", "Melodic Tom", "Synth Drum", "Reverse Cymbal",
]
assert len(GM_NAMES) == 120

# Kim's 1-based GM program numbers -> 0-based preset numbers (GM program N == preset N-1).
GM_1BASED = [1, 3, 30, 31, 39, 40, 51, 52, 63, 69, 74] + list(range(81, 105)) + [108, 109, 112, 113, 116]
assert len(GM_1BASED) == 40, len(GM_1BASED)
GM_0BASED = [n - 1 for n in GM_1BASED]
FLUIDR3 = "FluidR3_GM.sf2"
N_VARIANTS = 16
MIN_FONT_MB = 2.0

# ---------------------------------------------------------------- select
def stage_select():
    BASE.mkdir(parents=True, exist_ok=True)
    by_pp = {pp: [] for pp in GM_0BASED}  # pp -> list of candidate rows
    font_mb = {}
    with open(SF2_JSONL) as f:
        for line in f:
            d = json.loads(line)
            if "error" in d:
                continue
            font_mb[d["font"]] = d["mb"]
            if d["bank"] != 0 or d["preset"] not in by_pp:
                continue
            if d["mb"] < MIN_FONT_MB:
                continue
            name = (d.get("name") or "").strip()
            if not name or name.lower() == "untitled":
                continue
            by_pp[d["preset"]].append(d)

    rows = []
    coverage_log = []
    for gm1, pp in zip(GM_1BASED, GM_0BASED):
        cands = by_pp[pp]
        # dedup by font basename (keep the largest/first hit per font)
        best_per_font = {}
        for d in cands:
            f = d["font"]
            if f not in best_per_font or d["mb"] > best_per_font[f]["mb"]:
                best_per_font[f] = d
        fonts = list(best_per_font.values())
        fluidr3 = [d for d in fonts if d["font"] == FLUIDR3]
        others = [d for d in fonts if d["font"] != FLUIDR3]
        others.sort(key=lambda d: -d["mb"])  # prefer larger fonts (likelier-complete GM sets)
        ordered = (fluidr3 + others) if fluidr3 else others
        picked = ordered[:N_VARIANTS]
        if len(picked) < N_VARIANTS:
            coverage_log.append(f"gm{gm1}({GM_NAMES[pp]}): only {len(picked)}/{N_VARIANTS} eligible fonts")
        for vi, d in enumerate(picked, 1):
            rows.append({
                "gm_1based": gm1, "gm_0based": pp, "gm_name": GM_NAMES[pp],
                "variant_idx": vi, "font": d["font"], "sf2_path": d["sf2"],
                "bank": d["bank"], "preset": d["preset"], "patch_name": d["name"],
            })

    with open(BASE / "selection.csv", "w", newline="") as f:
        cols = ["gm_1based", "gm_0based", "gm_name", "variant_idx", "font", "sf2_path", "bank", "preset", "patch_name"]
        wr = csv.DictWriter(f, fieldnames=cols)
        wr.writeheader()
        wr.writerows(rows)
    with open(BASE / "selection_coverage.log", "w") as f:
        f.write("\n".join(coverage_log) + ("\n" if coverage_log else ""))
    print(f"[select] {len(rows)} renders selected across {len(GM_1BASED)} GM programs "
          f"(target {len(GM_1BASED)*N_VARIANTS}); {len(coverage_log)} programs under quota "
          f"(see selection_coverage.log)")


# ---------------------------------------------------------------- gen: the interval battery
INTERVALS = [1, 2, 3, 5, 7, 12]


def build_battery(root=E3):
    """Returns (steps, grid) where steps = [(abs_step0..255, dur16=1, pitch, gate)], and
    grid = per-frame ground truth dicts (bar, step_in_bar, section, pitch, semitone_offset,
    predecessor_pitch, predecessor_offset, k, direction). `root` defaults to E3 (main battery);
    the mix stage calls build_battery(root=E4) for the two-voice lead track."""
    pitches = [None] * NFRAMES
    section = [None] * NFRAMES
    k_of = [None] * NFRAMES
    dir_of = [None] * NFRAMES

    def fill(rng, pitch_fn, sec, k=None, d=None):
        for i in rng:
            pitches[i] = pitch_fn(i)
            section[i] = sec
            k_of[i] = k
            dir_of[i] = d

    # bar 1 (steps 0-15): pedal root
    fill(range(0, 16), lambda i: root, "pedal_intro")
    # bars 2-13 (steps 16-207): oscillation cells, one bar each, order +k then -k per k
    bar = 1  # next bar index (0-based), bar 1 already used
    for k in INTERVALS:
        for d, sign in (("up", +1), ("down", -1)):
            lo = bar * 16
            fill(range(lo, lo + 16),
                 lambda i, lo=lo, sign=sign, k=k: (root + sign * k) if (i - lo) % 2 else root,
                 f"osc_k{k}_{d}", k=k, d=d)
            bar += 1
    assert bar == 13  # bars 2..13 consumed (0-indexed 1..12), bar14 (idx13) is recovery
    # bar 14 (steps 208-223): recovery pedal
    fill(range(208, 224), lambda i: root, "pedal_recovery")
    # bars 15-16 (steps 224-255): mixed pivot run, ascending then descending, padded to 16-grid
    lo = 224
    for d, sign in (("up", +1), ("down", -1)):
        for j, k in enumerate(INTERVALS):
            pitches[lo + 2 * j] = root
            section[lo + 2 * j] = f"pivot_{d}_pre"
            pitches[lo + 2 * j + 1] = root + sign * k
            section[lo + 2 * j + 1] = f"pivot_{d}_k{k}"
            k_of[lo + 2 * j + 1] = k
            dir_of[lo + 2 * j + 1] = d
        for j in range(12, 16):  # pad tail of each pivot bar with pedal root
            pitches[lo + j] = root
            section[lo + j] = "pivot_pad"
        lo += 16
    assert all(p is not None for p in pitches)

    steps = [(i, 1, pitches[i], 0.8) for i in range(NFRAMES)]
    grid = []
    for i in range(NFRAMES):
        pred = pitches[i - 1] if i > 0 else None
        succ = pitches[i + 1] if i < NFRAMES - 1 else None  # anticipation target (Kim 2026-07-23)
        grid.append({
            "frame": i, "bar": i // 16 + 1, "step_in_bar": i % 16, "section": section[i],
            "pitch": pitches[i], "semitone_offset": pitches[i] - root,
            "predecessor_pitch": pred, "predecessor_offset": (pred - root) if pred is not None else None,
            "successor_pitch": succ, "successor_offset": (succ - root) if succ is not None else None,
            "k": k_of[i], "direction": dir_of[i],
        })
    return steps, grid


SINE_STEM = "battery__sine"


def synth_sine_battery(steps, bpm, out_path, amp=0.35, ramp_ms=5.0):
    """Adapted from gen_test_midis_v2.synth_sine (same convention: 5ms linear attack/release,
    sample-accurate onsets, no reverb tail) for our absolute-step (0..255) battery, which is one
    non-repeating 256-step sequence rather than a repeated per-bar pattern -- the original sizes
    its buffer as bars*16 sixteenths, which underflows for our case (bars=1 trick would allocate
    only 16 sixteenths of audio for a 256-step battery)."""
    import soundfile as sf
    sec16 = 60.0 / bpm / 4.0
    nsteps = max(on16 + dur16 for on16, dur16, _, _ in steps)
    total = int(round((nsteps * sec16 + 0.5) * SR))
    y = np.zeros(total, dtype=np.float64)
    nramp = int(round(ramp_ms * 1e-3 * SR))
    for on16, dur16, pitch, gate in steps:
        i0 = int(round(on16 * sec16 * SR))
        ndur = int(round(dur16 * sec16 * gate * SR))
        f = 440.0 * 2.0 ** ((pitch - 69) / 12.0)
        t = np.arange(ndur) / SR
        seg = np.sin(2 * np.pi * f * t)
        env = np.ones(ndur)
        r = min(nramp, ndur // 2)
        env[:r] = np.linspace(0, 1, r, endpoint=False)
        env[ndur - r:] = np.linspace(1, 0, r)
        seg *= env
        y[i0:i0 + ndur] += seg
    y *= amp
    sf.write(out_path, np.stack([y, y], 1).astype(np.float32), SR, subtype="PCM_16")


def stage_gen():
    MIDIS.mkdir(parents=True, exist_ok=True)
    RENDERS.mkdir(parents=True, exist_ok=True)
    steps, grid = build_battery()
    genv2.write_midi(MIDIS / "battery.mid", steps, bars=1, bpm=BPM)
    man = {
        "bpm": BPM, "nframes": NFRAMES, "bars": 16, "e3_midi": E3, "intervals": INTERVALS,
        "sections": ["pedal_intro(bar1)", "osc_k{1,2,3,5,7,12}_{up,down}(bars2-13, one each)",
                     "pedal_recovery(bar14)", "pivot_up/down(bars15-16, 6 pairs + 4-step pad each)"],
        "grid": grid,
    }
    json.dump(man, open(BASE / "manifest.json", "w"), indent=1)
    # Sine control (Kim 2026-07-23): pure-numpy render, 5ms attack/release, sample-accurate
    # onsets, NO acoustic release tail -> any predecessor decodability here is encoder-intrinsic
    # (no fluidsynth reverb/decay confound). Reuses gen_test_midis_v2.synth_sine verbatim; bars=1
    # + absolute step indices works the same way it does for write_midi.
    synth_sine_battery(steps, BPM, RENDERS / f"{SINE_STEM}.wav")
    print(f"[gen] battery.mid + {SINE_STEM}.wav written ({NFRAMES} frames), manifest.json grid written")


# ---------------------------------------------------------------- render
def render_one(task):
    # task = (midi_path, sf2_path, bank, preset, channel, out); channel defaults to 0 for the
    # 5-tuple form used by the original 640-row selection matrix.
    if len(task) == 4:
        sf2_path, bank, preset, out = task
        midi_path, channel = MIDIS / "battery.mid", 0
    else:
        midi_path, sf2_path, bank, preset, channel, out = task
    if out.exists():
        return "skip", out.name
    import mido
    for attempt in (1, 2):
        mid = mido.MidiFile(midi_path)
        tr = mid.tracks[0]
        ins = [mido.Message("program_change", program=preset, channel=channel, time=0)]
        if bank != 0:
            msb, lsb = (bank >> 7) & 0x7F, bank & 0x7F
            ins.insert(0, mido.Message("control_change", control=32, value=lsb, channel=channel, time=0))
            ins.insert(0, mido.Message("control_change", control=0, value=msb, channel=channel, time=0))
        for m in reversed(ins):
            tr.insert(1, m)
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as tf:
            tmp = Path(tf.name)
        mid.save(tmp)
        try:
            r = subprocess.run(
                ["fluidsynth", "-ni", "-g", "0.5", "-r", str(SR), "-F", str(out), sf2_path, str(tmp)],
                capture_output=True, text=True, timeout=90)
            ok = r.returncode == 0 and out.exists()
        except subprocess.TimeoutExpired:
            ok = False
            err = "TIMEOUT"
        else:
            err = r.stderr[-200:] if not ok else ""
        finally:
            tmp.unlink(missing_ok=True)
        if ok:
            return "ok", out.name
        if attempt == 2:
            out.unlink(missing_ok=True)
            return "SKIP", f"{out.name}: {err}"
    return "SKIP", out.name


def sel_rows():
    with open(BASE / "selection.csv") as f:
        return list(csv.DictReader(f))


def render_name(row):
    return f"gm{int(row['gm_1based']):03d}__v{int(row['variant_idx']):02d}__{Path(row['font']).stem}.wav"


def stage_render(jobs=12):
    RENDERS.mkdir(parents=True, exist_ok=True)
    rows = sel_rows()
    tasks = [(row["sf2_path"], int(row["bank"]), int(row["preset"]), RENDERS / render_name(row)) for row in rows]
    print(f"[render] {len(tasks)} fluidsynth renders, {jobs} workers")
    skips = []
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        futs = {ex.submit(render_one, t): t for t in tasks}
        for i, f in enumerate(as_completed(futs)):
            status, msg = f.result()
            if status == "SKIP":
                skips.append(msg)
                print(f"[SKIP] {msg}", flush=True)
            if (i + 1) % 50 == 0:
                print(f"  {i+1}/{len(tasks)}  {time.time()-t0:.0f}s", flush=True)
    n = len(list(RENDERS.glob("*.wav")))
    print(f"[render] done: {n} wavs present in {time.time()-t0:.0f}s, {len(skips)} skipped")
    json.dump(skips, open(BASE / "render_skips.json", "w"), indent=1)


# ---------------------------------------------------------------- encode
def stage_encode():
    rc = subprocess.run([sys.executable, FILELOCK_PY, "acquire", str(GPU_LOCK), "--handle", HANDLE,
                         "--pid-aware", "--pid", str(__import__("os").getppid()), "--timeout", "600"]).returncode
    if rc != 0:
        print("[encode] could not acquire .gpu.lock, aborting encode stage")
        return
    try:
        _encode_impl()
    finally:
        subprocess.run([sys.executable, FILELOCK_PY, "release", str(GPU_LOCK), "--handle", HANDLE])


def _encode_impl():
    import torch
    import soundfile as sf
    from safetensors.torch import load_file
    from stable_audio_3.model_configs import all_models
    from stable_audio_3.factory import create_pretransform_from_config
    from stable_audio_3.loading_utils import copy_state_dict

    LATENTS.mkdir(parents=True, exist_ok=True)
    wavs = sorted(RENDERS.glob("*.wav"))
    todo = [w for w in wavs if not (LATENTS / f"{w.stem}.z0.npy").exists()]
    print(f"[encode] {len(todo)}/{len(wavs)} to do", flush=True)
    if not todo:
        return

    cfg_path, ckpt_path = all_models["medium-base"].resolve()
    _cfg = json.load(open(cfg_path))
    sr = _cfg["sample_rate"]
    pt = create_pretransform_from_config(_cfg.get("model", _cfg), sr).to("cuda").half().eval().requires_grad_(False)
    _sd = load_file(ckpt_path)
    copy_state_dict(pt, {k[len("pretransform."):]: v for k, v in _sd.items() if k.startswith("pretransform.")})
    ds = int(pt.downsampling_ratio)
    print(f"[encode] pretransform up: sr={sr} ds={ds}", flush=True)

    t0 = time.time()
    for i, w in enumerate(todo):
        y, in_sr = sf.read(w, dtype="float32", always_2d=True)
        assert in_sr == sr, f"{w.name}: sr {in_sr} != {sr}"
        x = torch.from_numpy(y.T)
        if x.shape[0] == 1:
            x = x.repeat(2, 1)
        n = x.shape[-1]
        pad = (ds - n % ds) % ds
        if pad:
            x = torch.nn.functional.pad(x, (0, pad))
        x = x.unsqueeze(0).cuda().half()
        with torch.no_grad():
            z = pt.encode(x)
        z = z[0].float().cpu().numpy().astype(np.float16)
        np.save(LATENTS / f"{w.stem}.z0.npy", z)
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(todo)}  {time.time()-t0:.0f}s", flush=True)
    print(f"[encode] done {len(todo)} in {time.time()-t0:.0f}s", flush=True)


# ---------------------------------------------------------------- analyze
def zload(stem):
    return np.load(LATENTS / f"{stem}.z0.npy").astype(np.float32)


def load_all():
    rows = sel_rows()
    grid = json.load(open(BASE / "manifest.json"))["grid"]
    data = []
    for row in rows:
        stem = render_name(row)[:-4]
        p = LATENTS / f"{stem}.z0.npy"
        if not p.exists():
            continue
        z = zload(stem)  # [C, T]
        if z.shape[1] < NFRAMES:
            continue
        z = z[:, :NFRAMES].T  # [256, C]
        data.append({"row": row, "z": z})
    return data, grid


def pitch_decoder_weight(z, grid):
    """Ridge decoder of current semitone-offset from latent frame, trained on THIS render's
    own battery ground truth (per-render weight vector, as spec'd)."""
    y = np.array([g["semitone_offset"] for g in grid], dtype=float)
    w, Xm, ym, r2_loo = v1.ridge_loo(z, y, lam=20.0)
    return w, r2_loo


def cosine(a, b):
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


def stage_analyze():
    from sklearn.metrics import silhouette_score
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA
    from sklearn.model_selection import StratifiedKFold

    data, grid = load_all()
    print(f"[analyze] {len(data)} renders with complete latents")
    programs = sorted(set(int(d["row"]["gm_1based"]) for d in data))

    # ---- descriptors ----
    frame_mean = {}
    pitch_w = {}
    ridge_r2 = {}
    for d in data:
        stem = render_name(d["row"])[:-4]
        frame_mean[stem] = d["z"].mean(0)
        w, r2 = pitch_decoder_weight(d["z"], grid)
        pitch_w[stem] = w
        ridge_r2[stem] = r2
    stems = list(frame_mean.keys())
    prog_of = {render_name(d["row"])[:-4]: int(d["row"]["gm_1based"]) for d in data}
    font_of = {render_name(d["row"])[:-4]: d["row"]["font"] for d in data}

    # ---- (a) clustering around patch number ----
    def cluster_report(desc, label):
        X = np.stack([desc[s] for s in stems])
        y = np.array([prog_of[s] for s in stems])
        counts = {p: (y == p).sum() for p in programs}
        keep = np.array([counts[p] >= 2 for p in y])
        sil = float(silhouette_score(X[keep], y[keep], metric="cosine")) if keep.sum() > 1 and len(set(y[keep])) > 1 else float("nan")
        # within vs cross cosine
        Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)
        sim = Xn @ Xn.T
        n = len(stems)
        same = (y[:, None] == y[None, :]) & ~np.eye(n, dtype=bool)
        diff = (y[:, None] != y[None, :])
        within = float(sim[same].mean()) if same.any() else float("nan")
        cross = float(sim[diff].mean())
        # permutation p-value on (within-cross)
        rng = np.random.default_rng(0)
        obs = within - cross
        n_perm = 200
        ge = 0
        for _ in range(n_perm):
            yp = rng.permutation(y)
            samep = (yp[:, None] == yp[None, :]) & ~np.eye(n, dtype=bool)
            diffp = (yp[:, None] != yp[None, :])
            if samep.any():
                d_ = float(sim[samep].mean()) - float(sim[diffp].mean())
                if d_ >= obs:
                    ge += 1
        p_perm = (ge + 1) / (n_perm + 1)
        per_prog_within = {}
        for p in programs:
            idx = np.where(y == p)[0]
            if len(idx) < 2:
                continue
            s = sim[np.ix_(idx, idx)]
            iu = np.triu_indices(len(idx), 1)
            per_prog_within[p] = float(s[iu].mean()) if len(iu[0]) else float("nan")
        ranked = sorted(per_prog_within.items(), key=lambda kv: -kv[1])
        return {
            "label": label, "silhouette_cosine": round(sil, 4) if sil == sil else None,
            "within_program_cosine": round(within, 4), "cross_program_cosine": round(cross, 4),
            "permutation_p": round(p_perm, 4),
            "top8_coherent": [{"gm": p, "name": GM_NAMES[p - 1], "within_cos": round(v, 4)} for p, v in ranked[:8]],
            "bottom8_coherent": [{"gm": p, "name": GM_NAMES[p - 1], "within_cos": round(v, 4)} for p, v in ranked[-8:]],
        }

    cluster_timbre = cluster_report(frame_mean, "frame_mean_latent")
    cluster_pitch = cluster_report(pitch_w, "pitch_decoder_weight")

    # generic-supercluster replication: do variants of DIFFERENT "generic" (non-orchestral,
    # broadly-implemented) programs mix in frame_mean space? Use 3-cluster kmeans-free proxy:
    # nearest-program-centroid confusion matrix top confusions.
    X = np.stack([frame_mean[s] for s in stems])
    Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)
    y = np.array([prog_of[s] for s in stems])
    cent = {p: Xn[y == p].mean(0) for p in programs}
    cent_mat = np.stack([cent[p] for p in programs])
    cent_mat /= (np.linalg.norm(cent_mat, axis=1, keepdims=True) + 1e-12)
    csim = cent_mat @ cent_mat.T
    np.fill_diagonal(csim, -1)
    confusions = []
    for i, p in enumerate(programs):
        j = int(np.argmax(csim[i]))
        confusions.append({"gm": p, "name": GM_NAMES[p - 1], "nearest_other_gm": programs[j],
                            "nearest_other_name": GM_NAMES[programs[j] - 1], "cos": round(float(csim[i, j]), 4)})
    mean_nearest_cos = float(np.mean([c["cos"] for c in confusions]))

    # ---- (b) interval decodability ----
    def dprime_binary(Za, Zb):
        mu_a, sd_a = Za.mean(0), Za.std(0) + 1e-6
        mu_b, sd_b = Zb.mean(0), Zb.std(0) + 1e-6
        pooled = np.sqrt(0.5 * (sd_a ** 2 + sd_b ** 2)) + 1e-6
        w = (mu_b - mu_a) / pooled ** 2
        sa, sb = Za @ w, Zb @ w
        denom = 0.5 * (sa.std() + sb.std()) + 1e-9
        return float((sb.mean() - sa.mean()) / denom)

    interval_results = []
    for k in INTERVALS:
        sec_up, sec_down = f"osc_k{k}_up", f"osc_k{k}_down"
        mask_pedal = np.array([g["section"] == "pedal_intro" for g in grid])
        for direction, sec in [("up", sec_up), ("down", sec_down)]:
            mask_cell = np.array([g["section"] == sec and g["semitone_offset"] == 0 for g in grid])
            Xs, ys, per_prog = [], [], {}
            for d in data:
                z = d["z"]
                Xs.append(z[mask_cell]); ys.append(np.ones(mask_cell.sum()))
                Xs.append(z[mask_pedal]); ys.append(np.zeros(mask_pedal.sum()))
            Xall = np.concatenate(Xs); yall = np.concatenate(ys)
            skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
            accs = [LDA().fit(Xall[tr], yall[tr]).score(Xall[te], yall[te]) for tr, te in skf.split(Xall, yall)]
            # lightweight per-program-class breakdown: pooled d' (16 variants/program), not
            # a per-program CV (kept cheap for the token/time budget) -- report spread across
            # the 40 GM programs rather than a full per-program table.
            for p in programs:
                pd_ = [d for d in data if int(d["row"]["gm_1based"]) == p]
                if len(pd_) < 2:
                    continue
                Za = np.concatenate([d["z"][mask_pedal] for d in pd_])
                Zb = np.concatenate([d["z"][mask_cell] for d in pd_])
                per_prog[p] = dprime_binary(Za, Zb)
            interval_results.append({
                "k": k, "direction": direction, "test": "cell_vs_pedal", "lda_acc_5fold": round(float(np.mean(accs)), 4),
                "per_program_dprime_min": round(min(per_prog.values()), 3) if per_prog else None,
                "per_program_dprime_max": round(max(per_prog.values()), 3) if per_prog else None,
                "per_program_dprime_mean": round(float(np.mean(list(per_prog.values()))), 3) if per_prog else None,
            })
        # direction: +k vs -k (pooled across programs)
        mu = np.array([g["section"] == sec_up and g["semitone_offset"] == 0 for g in grid])
        md = np.array([g["section"] == sec_down and g["semitone_offset"] == 0 for g in grid])
        Xu = np.concatenate([d["z"][mu] for d in data]); Xd = np.concatenate([d["z"][md] for d in data])
        Xall = np.concatenate([Xu, Xd]); yall = np.concatenate([np.ones(len(Xu)), np.zeros(len(Xd))])
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
        accs = [LDA().fit(Xall[tr], yall[tr]).score(Xall[te], yall[te]) for tr, te in skf.split(Xall, yall)]
        per_prog_dir = {}
        for p in programs:
            pd_ = [d for d in data if int(d["row"]["gm_1based"]) == p]
            if len(pd_) < 2:
                continue
            Za = np.concatenate([d["z"][mu] for d in pd_])
            Zb = np.concatenate([d["z"][md] for d in pd_])
            per_prog_dir[p] = dprime_binary(Za, Zb)
        interval_results.append({
            "k": k, "direction": "up_vs_down", "test": "direction", "lda_acc_5fold": round(float(np.mean(accs)), 4),
            "per_program_dprime_min": round(min(per_prog_dir.values()), 3) if per_prog_dir else None,
            "per_program_dprime_max": round(max(per_prog_dir.values()), 3) if per_prog_dir else None,
            "per_program_dprime_mean": round(float(np.mean(list(per_prog_dir.values()))), 3) if per_prog_dir else None,
        })

    # ---- (c) hysteresis: predecessor (memory) + successor (anticipation) identity from the
    # current E3 frame, held-out fonts. classes: pedal + {+/-}k for k in INTERVALS = 13.
    def class_of_offset(off):
        if off is None:
            return None
        if off == 0:
            return "pedal"
        sign = "+" if off > 0 else "-"
        mag = abs(off)
        return f"{sign}{mag}" if mag in INTERVALS else None

    pred_class = [class_of_offset(g["predecessor_offset"]) for g in grid]
    succ_class = [class_of_offset(g["successor_offset"]) for g in grid]
    e3_pred_frames = np.array([g["pitch"] == E3 and pred_class[g["frame"]] is not None for g in grid])
    e3_succ_frames = np.array([g["pitch"] == E3 and succ_class[g["frame"]] is not None for g in grid])
    fonts = sorted(set(font_of[s] for s in stems))
    rng = np.random.default_rng(1)
    perm = rng.permutation(fonts)
    n_test_fonts = max(3, len(fonts) // 5)
    test_fonts = set(perm[:n_test_fonts])
    train_fonts = set(perm[n_test_fonts:])

    def multiclass_acc(sel_mask, labels):
        Xtr, ytr, Xte, yte = [], [], [], []
        for d in data:
            stem = render_name(d["row"])[:-4]
            z = d["z"]
            for i in np.where(sel_mask)[0]:
                c = labels[i]
                if c is None:
                    continue
                bucket = (Xte, yte) if font_of[stem] in test_fonts else (Xtr, ytr)
                bucket[0].append(z[i]); bucket[1].append(c)
        if not Xtr or not Xte or len(set(ytr)) < 2:
            return float("nan"), 0
        clf = LDA()
        clf.fit(np.stack(Xtr), ytr)
        pred = clf.predict(np.stack(Xte))
        yte = np.array(yte)
        bal = np.mean([np.mean(pred[yte == c] == c) for c in sorted(set(yte)) if (yte == c).sum() > 0])
        return float(bal), len(yte)

    pred_acc, pred_n = multiclass_acc(e3_pred_frames, pred_class)
    succ_acc, succ_n = multiclass_acc(e3_succ_frames, succ_class)
    chance = 1.0 / 13
    print(f"[c] predecessor 13-class balanced_acc={pred_acc:.4f} n={pred_n}; "
          f"successor(anticipation) balanced_acc={succ_acc:.4f} n={succ_n}; chance={chance:.4f}")

    # ---- decay curves: binary LDA discriminability of "recency-r frame carries the last-event
    # identity" vs a genuine no-context reference pool (frames with NO recent transition anywhere
    # nearby), held-out fonts. Fixes an earlier design (single fixed battery MIDI -> a literal
    # per-offset frame index has only ONE true class across all renders, so a 13-way classifier
    # at a single offset is degenerate/label-free; binary vs-reference sidesteps that).
    # predecessor chain: bar14 onset (idx 208..), identity = "-12" (osc_k12_down precedes it).
    #   reference (no-context) = bar1 deep-pedal frames 8-15 (battery start, no prior event).
    # successor/anticipation chain: bar1 tail counting backward from idx15 toward the bar1/bar2
    #   boundary, identity = "+1" (osc_k1_up follows). reference = bar14 mid frames 212-215
    #   (isolated from both the preceding "-12" and following "+1" transitions).
    def binary_decay(target_idxs_with_recency, ref_idxs):
        rows = []
        for recency, idx in target_idxs_with_recency:
            Xtr, ytr, Xte, yte = [], [], [], []
            for d in data:
                stem = render_name(d["row"])[:-4]
                z = d["z"]
                bucket = (Xte, yte) if font_of[stem] in test_fonts else (Xtr, ytr)
                bucket[0].append(z[idx]); bucket[1].append(1)
                for ridx in ref_idxs:
                    bucket[0].append(z[ridx]); bucket[1].append(0)
            clf = LDA()
            clf.fit(np.stack(Xtr), ytr)
            pred = clf.predict(np.stack(Xte))
            yte = np.array(yte)
            bal = float(np.mean([np.mean(pred[yte == c] == c) for c in (0, 1)]))
            rows.append({"recency_frames": recency, "balanced_acc": round(bal, 4)})
        return rows

    pred_decay = binary_decay([(o + 1, 208 + o) for o in range(8)], ref_idxs=list(range(8, 16)))
    succ_decay = binary_decay([(o + 2, 15 - o) for o in range(8)], ref_idxs=list(range(212, 216)))

    # sine-control decay: single render, no train/test split possible -> report the descriptive
    # magnitude directly (cosine distance from the same reference-pool centroid, in the sine
    # latent alone). No acoustic release tail in this render (5ms ramps only) -> any nonzero
    # decay here is encoder-intrinsic context, not reverb/decay bleed.
    sine_path = LATENTS / f"{SINE_STEM}.z0.npy"
    sine_pred_decay = sine_succ_decay = None
    hyst_mag_sine = None
    if sine_path.exists():
        zsine = np.load(sine_path).astype(np.float32)[:, :NFRAMES].T
        pred_ref = zsine[8:16].mean(0)
        succ_ref = zsine[212:216].mean(0)
        sine_pred_decay = [{"recency_frames": o + 1, "cos_dist_from_ref": round(float(1 - cosine(zsine[208 + o], pred_ref)), 4)}
                            for o in range(8)]
        sine_succ_decay = [{"recency_frames": o + 2, "cos_dist_from_ref": round(float(1 - cosine(zsine[15 - o], succ_ref)), 4)}
                            for o in range(8)]
        pedal_ref_sine = zsine[np.array([g["section"] == "pedal_intro" for g in grid])].mean(0)
        hyst_mag_sine = float(1 - cosine(zsine[208], pedal_ref_sine))

    with open(BASE / "hysteresis_decay.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["chain", "method", "recency_frames", "value"])
        wr.writeheader()
        for r in pred_decay:
            wr.writerow({"chain": "predecessor_bar14", "method": "lda_balanced_acc_pooled_patches",
                         "recency_frames": r["recency_frames"], "value": r["balanced_acc"]})
        for r in succ_decay:
            wr.writerow({"chain": "successor_bar1tail", "method": "lda_balanced_acc_pooled_patches",
                         "recency_frames": r["recency_frames"], "value": r["balanced_acc"]})
        if sine_pred_decay:
            for r in sine_pred_decay:
                wr.writerow({"chain": "predecessor_bar14", "method": "sine_cosdist_from_ref",
                             "recency_frames": r["recency_frames"], "value": r["cos_dist_from_ref"]})
            for r in sine_succ_decay:
                wr.writerow({"chain": "successor_bar1tail", "method": "sine_cosdist_from_ref",
                             "recency_frames": r["recency_frames"], "value": r["cos_dist_from_ref"]})

    # release-tail-vs-intrinsic control: correlate per-render hysteresis "magnitude" proxy
    # (cosine distance of bar14-onset frame from the pooled pedal centroid) against bar14
    # energy-decay (release length proxy: frames for ||z|| to settle after bar14 onset).
    release_len = {}
    hyst_mag = {}
    for d in data:
        stem = render_name(d["row"])[:-4]
        z = d["z"]
        pedal_ref = z[np.array([g["section"] == "pedal_intro" for g in grid])].mean(0)
        e0 = z[208]
        hyst_mag[stem] = float(1 - cosine(e0, pedal_ref))
        energies = np.linalg.norm(z[208:224], axis=1)
        settled = energies[-1]
        thr = settled + 0.1 * (energies[0] - settled + 1e-9)
        above = np.where(energies > thr)[0]
        release_len[stem] = int(above[-1] + 1) if len(above) else 0
    common = [s for s in stems if s in release_len]
    rl = np.array([release_len[s] for s in common]); hm = np.array([hyst_mag[s] for s in common])
    tail_corr = float(np.corrcoef(rl, hm)[0, 1]) if len(common) > 2 and rl.std() > 0 and hm.std() > 0 else float("nan")
    mean_patch_hyst_mag = float(np.mean(list(hyst_mag.values())))

    results = {
        "n_renders": len(data), "n_programs": len(programs),
        "clustering": {"frame_mean_latent": cluster_timbre, "pitch_decoder_weight": cluster_pitch,
                       "generic_supercluster_replication": {
                           "mean_nearest_other_program_cos": round(mean_nearest_cos, 4),
                           "confusions": confusions}},
        "interval_decodability": interval_results,
        "hysteresis": {
            "predecessor_13class_balanced_acc": round(pred_acc, 4) if pred_acc == pred_acc else None,
            "successor_13class_balanced_acc": round(succ_acc, 4) if succ_acc == succ_acc else None,
            "chance": round(chance, 4), "n_test_frames_predecessor": pred_n, "n_test_frames_successor": succ_n,
            "test_fonts": sorted(test_fonts), "train_fonts_n": len(train_fonts),
            "decay_csv": "hysteresis_decay.csv",
            "predecessor_decay_patches": pred_decay, "successor_decay_patches": succ_decay,
            "sine_predecessor_decay": sine_pred_decay, "sine_successor_decay": sine_succ_decay,
            "hysteresis_magnitude_mean_patches": round(mean_patch_hyst_mag, 4),
            "hysteresis_magnitude_sine": round(hyst_mag_sine, 4) if hyst_mag_sine is not None else None,
            "release_tail_vs_intrinsic_corr": round(tail_corr, 4) if tail_corr == tail_corr else None,
        },
    }
    json.dump(results, open(BASE / "results.json", "w"), indent=1)
    write_report(results)
    print(f"[analyze] wrote results.json, hysteresis_decay.csv, REPORT.md in {BASE}")
    return results


def write_report(res):
    lines = ["# GM Multi-Font Melody Probe -- REPORT\n"]
    lines.append(f"{res['n_renders']} renders across {res['n_programs']} GM programs "
                 "(<=16 fonts/variants each).\n")
    c = res["clustering"]["frame_mean_latent"]
    cp = res["clustering"]["pitch_decoder_weight"]
    lines.append("## (a) Clustering around patch number\n")
    lines.append(f"Frame-mean-latent space: silhouette(cosine)={c['silhouette_cosine']}, "
                 f"within-program cos={c['within_program_cosine']} vs cross-program cos="
                 f"{c['cross_program_cosine']} (permutation p={c['permutation_p']}).\n")
    lines.append(f"Pitch-decoder-weight space: silhouette={cp['silhouette_cosine']}, "
                 f"within={cp['within_program_cosine']} vs cross={cp['cross_program_cosine']} "
                 f"(p={cp['permutation_p']}).\n")
    lines.append(f"Most coherent (frame-mean): {[t['name'] for t in c['top8_coherent']]}\n")
    lines.append(f"Least coherent (frame-mean): {[t['name'] for t in c['bottom8_coherent']]}\n")
    gs = res["clustering"]["generic_supercluster_replication"]
    lines.append(f"Generic-supercluster check: mean nearest-OTHER-program centroid cosine = "
                 f"{gs['mean_nearest_other_program_cos']} (higher -> more cross-program mixing).\n")
    lines.append("## (b) Interval decodability\n")
    for r in res["interval_decodability"]:
        lines.append(f"- k={r['k']} {r['test']} ({r['direction']}): 5-fold LDA acc = {r['lda_acc_5fold']}, "
                     f"per-program d' [{r['per_program_dprime_min']}, {r['per_program_dprime_mean']}, "
                     f"{r['per_program_dprime_max']}] (min/mean/max)")
    lines.append("")
    h = res["hysteresis"]
    lines.append("## (c) Hysteresis\n")
    lines.append(f"Predecessor-identity (13-class) balanced acc = {h['predecessor_13class_balanced_acc']}; "
                 f"successor/anticipation (13-class) balanced acc = {h['successor_13class_balanced_acc']} "
                 f"vs chance {h['chance']} (held-out fonts: {h['test_fonts']}). Predecessor >> successor "
                 f"would indicate mostly acoustic tails; predecessor ~= successor indicates symmetric/"
                 f"architectural (non-causal receptive field) context.\n")
    lines.append(f"Hysteresis magnitude (cos-dist of bar14-onset frame from pedal centroid): "
                 f"mean over patch renders = {h['hysteresis_magnitude_mean_patches']}; "
                 f"SINE CONTROL (no acoustic release tail, 5ms ramps only) = {h['hysteresis_magnitude_sine']} "
                 f"-- any nonzero sine value is encoder-intrinsic context, not reverb bleed.\n")
    lines.append(f"Decay curves (balanced acc vs recency in frames, binary vs no-context reference; "
                 f"full data in hysteresis_decay.csv):\n")
    lines.append(f"- predecessor (bar14 chain, patch-pooled): {h['predecessor_decay_patches']}")
    lines.append(f"- successor/anticipation (bar1-tail chain, patch-pooled): {h['successor_decay_patches']}")
    if h.get("sine_predecessor_decay"):
        lines.append(f"- predecessor (sine, cos-dist from ref, descriptive): {h['sine_predecessor_decay']}")
        lines.append(f"- successor (sine, cos-dist from ref, descriptive): {h['sine_successor_decay']}")
    lines.append(f"\nRelease-tail-vs-intrinsic correlation (release length vs hysteresis magnitude, patches "
                 f"only) = {h['release_tail_vs_intrinsic_corr']}.\n")
    (BASE / "REPORT.md").write_text("\n".join(lines))


# ---------------------------------------------------------------- mix (Kim scope addition)
# Two-voice separability + drum-robustness probe. Renders solo stems only (lead x8, bass x4,
# drum-kit x2 = 14 fluidsynth calls) then constructs MIX/MIX+DRUM/LEAD+DRUM clips as numpy
# PCM sums of the aligned solo stems. This is mathematically IDENTICAL to a true multi-channel
# fluidsynth render (digital audio mixing is linear superposition; fluidsynth's own polyphonic
# engine does the same summation internally) and sidesteps fluidsynth's soundfont-stack
# priority ambiguity (a single process loading 2 different full-GM soundfonts cannot cleanly
# pin channel0 to font A's preset and channel1 to font B's preset for a shared program number
# without a synth command-file `select` API). It also gives full 32-pair coverage instead of a
# fluidsynth-cost-bounded subset. Documented deviation from the literal "96+16 renders" ask.
MIX_LEAD_PROGRAMS = [81, 82, 91, 102]
MIX_BASS_PROGRAMS = [39, 40]
E4 = 64
E2 = 40
B2 = 47  # fifth above E2
DRUM_KITS = [
    {"name": "Crisis", "font": "CrisisGeneralMidi3.01.sf2",
     "sf2": "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/torrents/500-soundfonts-full-gm-sets/"
            "500_Soundfonts_Full_GM_Sets/CrisisGeneralMidi3.01.sf2", "bank": 128, "preset": 0},
    {"name": "DSoundGaming", "font": "DSoundFont Gaming Edition (3.51).sf2",
     "sf2": "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/torrents/500-soundfonts-full-gm-sets/"
            "500_Soundfonts_Full_GM_Sets/DSoundFont Gaming Edition (3.51).sf2", "bank": 128, "preset": 0},
]
KICK, SNARE, OHAT = 36, 38, 46  # GM percussion map, channel 9


def build_bass_line():
    """256-frame bass line: E2 pedal, fifth (B2) in bars 6-7, octave (E2+12) in bar 13."""
    pitches = [E2] * NFRAMES
    for i in range(80, 112):   # bars 6-7 (1-based) = 0-idx bars 5-6 = steps 80-111
        pitches[i] = B2
    for i in range(192, 208):  # bar 13 (1-based) = 0-idx bar 12 = steps 192-207
        pitches[i] = E2 + 12
    steps = [(i, 1, pitches[i], 0.8) for i in range(NFRAMES)]
    grid = []
    for i in range(NFRAMES):
        pred = pitches[i - 1] if i > 0 else None
        grid.append({"frame": i, "bar": i // 16 + 1, "pitch": pitches[i], "semitone_offset": pitches[i] - E2,
                     "predecessor_pitch": pred})
    return steps, grid


def write_drum_midi(path, bpm):
    """Basic goa beat, channel 9: 4-on-floor kick, offbeat open hat, snare on 2&4."""
    import mido
    mid = mido.MidiFile(type=1, ticks_per_beat=genv2.TPB)
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    tr.append(mido.MetaMessage("set_tempo", tempo=int(60e6 / bpm), time=0))
    events = []
    for i in range(NFRAMES):
        step = i % 16
        notes = []
        if step % 4 == 0:
            notes.append(KICK)
        if step % 4 == 2:
            notes.append(OHAT)
        if step % 8 == 4:
            notes.append(SNARE)
        t_on = i * genv2.TICKS_16TH
        t_off = t_on + int(0.5 * genv2.TICKS_16TH)
        for n in notes:
            events.append((t_on, 1, "on", n))
            events.append((t_off, 0, "off", n))
    events.sort()
    last = 0
    for tick, _, kind, n in events:
        dt = tick - last
        last = tick
        if kind == "on":
            tr.append(mido.Message("note_on", note=n, velocity=100, time=dt, channel=9))
        else:
            tr.append(mido.Message("note_off", note=n, velocity=0, time=dt, channel=9))
    mid.save(path)


def stage_mix_render_solo(jobs=8):
    MIDIS.mkdir(parents=True, exist_ok=True)
    RENDERS.mkdir(parents=True, exist_ok=True)
    lead_steps, lead_grid = build_battery(root=E4)
    genv2.write_midi(MIDIS / "mix_lead.mid", lead_steps, bars=1, bpm=BPM)
    bass_steps, bass_grid = build_bass_line()
    genv2.write_midi(MIDIS / "mix_bass.mid", bass_steps, bars=1, bpm=BPM)
    write_drum_midi(MIDIS / "mix_drum.mid", BPM)
    json.dump({"lead_grid": lead_grid, "bass_grid": bass_grid, "e4_root": E4, "e2_root": E2,
               "bass_moves": {"fifth_B2_bars_1based": [6, 7], "octave_E2plus12_bar_1based": 13},
               "drum_kits": DRUM_KITS, "drum_map": {"kick": KICK, "snare": SNARE, "open_hat": OHAT}},
              open(BASE / "mix_manifest.json", "w"), indent=1)

    rows = sel_rows()

    def pick(programs, n_each=2):
        out = []
        for p in programs:
            out += [r for r in rows if int(r["gm_1based"]) == p][:n_each]
        return out

    lead_rows, bass_rows = pick(MIX_LEAD_PROGRAMS), pick(MIX_BASS_PROGRAMS)
    tasks, lead_idx, bass_idx, drum_idx = [], [], [], []
    for r in lead_rows:
        out = RENDERS / f"solo_lead__gm{r['gm_1based']}__{Path(r['font']).stem}.wav"
        tasks.append((MIDIS / "mix_lead.mid", r["sf2_path"], 0, int(r["preset"]), 0, out))
        lead_idx.append({"font": r["font"], "gm": r["gm_1based"], "wav": str(out)})
    for r in bass_rows:
        out = RENDERS / f"solo_bass__gm{r['gm_1based']}__{Path(r['font']).stem}.wav"
        tasks.append((MIDIS / "mix_bass.mid", r["sf2_path"], 0, int(r["preset"]), 0, out))
        bass_idx.append({"font": r["font"], "gm": r["gm_1based"], "wav": str(out)})
    for kit in DRUM_KITS:
        out = RENDERS / f"solo_drum__{kit['name']}.wav"
        tasks.append((MIDIS / "mix_drum.mid", kit["sf2"], kit["bank"], kit["preset"], 9, out))
        drum_idx.append({"name": kit["name"], "wav": str(out)})

    print(f"[mix-render-solo] {len(tasks)} solo stems ({len(lead_idx)} lead, {len(bass_idx)} bass, {len(drum_idx)} drum)")
    skips = []
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        futs = {ex.submit(render_one, t): t for t in tasks}
        for f in as_completed(futs):
            status, msg = f.result()
            if status == "SKIP":
                skips.append(msg)
                print("[SKIP]", msg)
    json.dump({"lead": lead_idx, "bass": bass_idx, "drum": drum_idx, "skips": skips},
              open(BASE / "mix_solo_index.json", "w"), indent=1)


def _read_wav(p):
    import soundfile as sf
    y, sr = sf.read(p, dtype="float32", always_2d=True)
    return y, sr


def _write_wav(p, y, sr):
    import soundfile as sf
    sf.write(p, y, sr, subtype="PCM_16")


def _pad(y, n):
    z = np.zeros((n, 2), np.float32)
    z[:len(y)] = y
    return z


def stage_mix_build():
    idx = json.load(open(BASE / "mix_solo_index.json"))
    lead, bass, drum = idx["lead"], idx["bass"], idx["drum"]
    if any(not Path(e["wav"]).exists() for e in lead + bass + drum):
        print("[mix-build] some solo stems missing (see skips) -- proceeding with what exists")
        lead = [e for e in lead if Path(e["wav"]).exists()]
        bass = [e for e in bass if Path(e["wav"]).exists()]
        drum = [e for e in drum if Path(e["wav"]).exists()]
    pairs = list(itertools.product(range(len(lead)), range(len(bass))))
    drum_pairs = list(range(min(8, len(pairs))))
    built = []
    for pi, (li, bi) in enumerate(pairs):
        yl, sr = _read_wav(lead[li]["wav"])
        yb, _ = _read_wav(bass[bi]["wav"])
        n = max(len(yl), len(yb))
        ymix = _pad(yl, n) + _pad(yb, n)
        out = RENDERS / f"mix__L{li}_{Path(lead[li]['wav']).stem}__B{bi}_{Path(bass[bi]['wav']).stem}.wav"
        _write_wav(out, ymix, sr)
        rec = {"pair": pi, "lead_idx": li, "bass_idx": bi, "lead_font": lead[li]["font"],
               "bass_font": bass[bi]["font"], "mix_wav": str(out),
               "solo_lead_wav": lead[li]["wav"], "solo_bass_wav": bass[bi]["wav"]}
        if pi in drum_pairs and drum:
            kit = drum[pi % len(drum)]
            yd, _ = _read_wav(kit["wav"])
            n2 = max(n, len(yd))
            ymixd = _pad(ymix, n2) + _pad(yd, n2)
            outmd = RENDERS / f"mixdrum__L{li}_B{bi}__{kit['name']}.wav"
            _write_wav(outmd, ymixd, sr)
            yld = _pad(yl, n2) + _pad(yd, n2)
            outld = RENDERS / f"leaddrum__L{li}__{kit['name']}.wav"
            _write_wav(outld, yld, sr)
            rec.update({"mixdrum_wav": str(outmd), "leaddrum_wav": str(outld), "drum_kit": kit["name"]})
        built.append(rec)
    json.dump(built, open(BASE / "mix_pairs.json", "w"), indent=1)
    print(f"[mix-build] {len(pairs)} mix pairs ({len(drum_pairs)} with drum variants)")


def _z(path_stem):
    p = LATENTS / f"{path_stem}.z0.npy"
    return zload(path_stem)[:, :NFRAMES].T if p.exists() else None  # [256, C]


def stage_mix_analyze():
    from sklearn.metrics import r2_score
    mixman = json.load(open(BASE / "mix_manifest.json"))
    lead_grid, bass_grid = mixman["lead_grid"], mixman["bass_grid"]
    pairs = json.load(open(BASE / "mix_pairs.json"))
    lead_off = np.array([g["semitone_offset"] for g in lead_grid], float)
    bass_off = np.array([g["semitone_offset"] for g in bass_grid], float)

    def zof(wav_path):
        stem = Path(wav_path).stem
        return _z(stem)

    # ---- per-variant solo decoders ----
    lead_stems = sorted(set(p["solo_lead_wav"] for p in pairs))
    bass_stems = sorted(set(p["solo_bass_wav"] for p in pairs))
    lead_w, lead_r2_solo = {}, {}
    for w in lead_stems:
        z = zof(w)
        if z is None:
            continue
        wt, Xm, ym, r2 = v1.ridge_loo(z, lead_off, lam=20.0)
        lead_w[w] = (wt, Xm, ym)
        lead_r2_solo[w] = r2
    bass_w, bass_r2_solo = {}, {}
    for w in bass_stems:
        z = zof(w)
        if z is None:
            continue
        wt, Xm, ym, r2 = v1.ridge_loo(z, bass_off, lam=20.0)
        bass_w[w] = (wt, Xm, ym)
        bass_r2_solo[w] = r2

    def apply_decoder(z, wt_pack):
        wt, Xm, ym = wt_pack
        return (z - Xm) @ wt + ym

    def r2_against(yhat, y):
        ss = np.sum((y - y.mean()) ** 2)
        return float(1 - np.sum((y - yhat) ** 2) / ss) if ss > 0 else float("nan")

    # ---- (a) separability: retention r2 on MIX, + superposition test ----
    lead_retention, bass_retention, cos_super, resid_super = [], [], [], []
    section_cos = {}
    for p in pairs:
        zmix = zof(p["mix_wav"])
        zl = zof(p["solo_lead_wav"])
        zb = zof(p["solo_bass_wav"])
        if zmix is None or zl is None or zb is None or p["solo_lead_wav"] not in lead_w or p["solo_bass_wav"] not in bass_w:
            continue
        n = min(len(zmix), len(zl), len(zb))
        zmix, zl, zb = zmix[:n], zl[:n], zb[:n]
        yh_lead = apply_decoder(zmix, lead_w[p["solo_lead_wav"]])
        yh_bass = apply_decoder(zmix, bass_w[p["solo_bass_wav"]])
        lead_retention.append(r2_against(yh_lead, lead_off[:n]) / max(1e-6, lead_r2_solo[p["solo_lead_wav"]]))
        bass_retention.append(r2_against(yh_bass, bass_off[:n]) / max(1e-6, bass_r2_solo[p["solo_bass_wav"]]))
        zsum = zl + zb
        c = np.array([cosine(zmix[t], zsum[t]) for t in range(n)])
        r = np.linalg.norm(zmix - zsum, axis=1) / (np.linalg.norm(zmix, axis=1) + 1e-9)
        cos_super.append(c.mean()); resid_super.append(r.mean())
        for t in range(n):
            sec = lead_grid[t]["section"]
            section_cos.setdefault(sec, []).append(c[t])
    sep = {
        "lead_retention_r2_ratio_mean": round(float(np.nanmean(lead_retention)), 4) if lead_retention else None,
        "bass_retention_r2_ratio_mean": round(float(np.nanmean(bass_retention)), 4) if bass_retention else None,
        "superposition_cos_mean": round(float(np.mean(cos_super)), 4) if cos_super else None,
        "superposition_resid_mean": round(float(np.mean(resid_super)), 4) if resid_super else None,
        "superposition_cos_by_section_worst5": sorted(
            [{"section": s, "cos": round(float(np.mean(v)), 4)} for s, v in section_cos.items()],
            key=lambda r: r["cos"])[:5],
        "n_pairs_analyzed": len(cos_super),
    }

    # ---- (b) voice confusion: does the lead decoder track bass truth on mix? ----
    lead_vs_bass_leak, bass_vs_lead_leak = [], []
    for p in pairs:
        zmix = zof(p["mix_wav"])
        if zmix is None or p["solo_lead_wav"] not in lead_w or p["solo_bass_wav"] not in bass_w:
            continue
        n = min(len(zmix), len(lead_off), len(bass_off))
        yh_lead = apply_decoder(zmix[:n], lead_w[p["solo_lead_wav"]])
        yh_bass = apply_decoder(zmix[:n], bass_w[p["solo_bass_wav"]])
        if np.std(yh_lead) > 0:
            lead_vs_bass_leak.append(float(np.corrcoef(yh_lead, bass_off[:n])[0, 1]))
        if np.std(yh_bass) > 0:
            bass_vs_lead_leak.append(float(np.corrcoef(yh_bass, lead_off[:n])[0, 1]))
    confusion = {
        "lead_decoder_corr_with_true_bass_pitch": round(float(np.nanmean(lead_vs_bass_leak)), 4) if lead_vs_bass_leak else None,
        "bass_decoder_corr_with_true_lead_pitch": round(float(np.nanmean(bass_vs_lead_leak)), 4) if bass_vs_lead_leak else None,
    }

    # ---- (c) drum robustness ----
    drum_rows = [p for p in pairs if "mixdrum_wav" in p]
    lead_r2_mix, lead_r2_mixdrum, lead_r2_leaddrum = [], [], []
    kick_delta, offbeat_delta = [], []
    step = np.arange(NFRAMES) % 16
    kick_mask, hat_mask = (step % 4 == 0), (step % 4 == 2)
    for p in drum_rows:
        wt_pack = lead_w.get(p["solo_lead_wav"])
        if wt_pack is None:
            continue
        zl = zof(p["solo_lead_wav"])
        zmix = zof(p["mix_wav"])
        zmixdrum = zof(p["mixdrum_wav"])
        zleaddrum = zof(p["leaddrum_wav"])
        if any(z is None for z in (zl, zmix, zmixdrum, zleaddrum)):
            continue
        n = min(len(zl), len(zmix), len(zmixdrum), len(zleaddrum), NFRAMES)
        lead_r2_mix.append(r2_against(apply_decoder(zmix[:n], wt_pack), lead_off[:n]))
        lead_r2_mixdrum.append(r2_against(apply_decoder(zmixdrum[:n], wt_pack), lead_off[:n]))
        lead_r2_leaddrum.append(r2_against(apply_decoder(zleaddrum[:n], wt_pack), lead_off[:n]))
        dz = np.linalg.norm(zleaddrum[:n] - zl[:n], axis=1)
        km, hm = kick_mask[:n], hat_mask[:n]
        if km.any():
            kick_delta.append(float(dz[km].mean()))
        if hm.any():
            offbeat_delta.append(float(dz[hm].mean()))
    drums = {
        "n_drum_pairs": len(drum_rows),
        "lead_r2_mix_no_drum": round(float(np.nanmean(lead_r2_mix)), 4) if lead_r2_mix else None,
        "lead_r2_mix_with_drum": round(float(np.nanmean(lead_r2_mixdrum)), 4) if lead_r2_mixdrum else None,
        "lead_r2_lead_plus_drum_only": round(float(np.nanmean(lead_r2_leaddrum)), 4) if lead_r2_leaddrum else None,
        "kick_frame_latent_delta_mean": round(float(np.mean(kick_delta)), 4) if kick_delta else None,
        "offbeat_hat_frame_latent_delta_mean": round(float(np.mean(offbeat_delta)), 4) if offbeat_delta else None,
    }

    mix_results = {"separability": sep, "voice_confusion": confusion, "drum_robustness": drums}
    results_path = BASE / "results.json"
    results = json.load(open(results_path)) if results_path.exists() else {}
    results["mix"] = mix_results
    json.dump(results, open(results_path, "w"), indent=1)

    lines = ["\n## (mix) Two-voice separability + drum robustness\n"]
    lines.append(f"Retention (r2-on-mix / r2-on-solo): lead={sep['lead_retention_r2_ratio_mean']}, "
                 f"bass={sep['bass_retention_r2_ratio_mean']} (1.0 = perfect retention).\n")
    lines.append(f"Superposition test z(mix) vs z(solo_lead)+z(solo_bass): mean cos={sep['superposition_cos_mean']}, "
                 f"mean relative residual={sep['superposition_resid_mean']}. Worst-cos sections: "
                 f"{sep['superposition_cos_by_section_worst5']}.\n")
    lines.append(f"Voice confusion: lead-decoder-on-mix corr with TRUE bass pitch = "
                 f"{confusion['lead_decoder_corr_with_true_bass_pitch']}; bass-decoder-on-mix corr with TRUE "
                 f"lead pitch = {confusion['bass_decoder_corr_with_true_lead_pitch']} (near 0 = clean separation).\n")
    lines.append(f"Drum robustness (n={drums['n_drum_pairs']} pairs): lead decoder r2 mix(no drum)="
                 f"{drums['lead_r2_mix_no_drum']}, mix+drum={drums['lead_r2_mix_with_drum']}, "
                 f"lead+drum-only={drums['lead_r2_lead_plus_drum_only']}. Latent delta from drum injection: "
                 f"kick frames={drums['kick_frame_latent_delta_mean']} vs offbeat-hat frames="
                 f"{drums['offbeat_hat_frame_latent_delta_mean']}.\n")
    with open(BASE / "REPORT.md", "a") as f:
        f.write("\n".join(lines))
    print(f"[mix-analyze] separability={sep}")
    print(f"[mix-analyze] confusion={confusion}")
    print(f"[mix-analyze] drums={drums}")
    return mix_results


def stage_mix():
    stage_mix_render_solo()
    stage_mix_build()
    stage_encode()  # generic: globs RENDERS/*.wav, only encodes the new mix/solo files
    stage_mix_analyze()


STAGES = {"select": stage_select, "gen": stage_gen, "render": stage_render, "encode": stage_encode,
          "analyze": stage_analyze, "mix": stage_mix}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="select,gen,render,encode,analyze")
    ap.add_argument("--jobs", type=int, default=12)
    a = ap.parse_args()
    for s in a.stages.split(","):
        s = s.strip()
        if not s:
            continue
        print(f"===== STAGE {s} =====", flush=True)
        if s == "render":
            stage_render(a.jobs)
        else:
            STAGES[s]()
