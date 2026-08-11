#!/usr/bin/env python
"""chromaturn.py — melody-turning feasibility probe via frame-level chroma steering
(Kim direct 2026-07-22: "try to turn melodies to different ones with frame level
chroma steering").

Question: can per-frame 12-dim chroma targets, pushed through the EXISTING LatCH
guidance stack (`model.generate(latch_configs=[{target_raw: (C,T)}])`, the exact slot
the chroma-morph transitions + chroma_steer eval used), turn melody A into melody B —
(a) imposing a target melody on free generation, and (b) SDEdit a2a from a synthetic
source render while steering toward a DIFFERENT pattern's chroma stream?

Ground truth: eval/musicology/test_midis — frame-locked BPM 161.499 patterns where
one 16th == exactly one latent frame (10.7666 fps), so the per-frame pitch-class
target is EXACT, and the source renders (sawlead etc.) have exact known melodies.

Heads: latch_sa3_same_chroma_best.pt (384-d 3-band SAME chroma; the strongest head in
the 2026-07-19 chroma_steer grid: mean dcos12 mid +0.032 @ g2048 vs hpcp's +/-0.003)
+ a 2-cell side-arm with the stem chroma_other head (the chroma-morph head, todos:15).
Gains {1536, 2048} = the proven pitch-steering band. hpcp omitted (measured dead).

Subcommands:
  targets  CPU. Build + sanity-check every per-frame target (shapes, pc streams).
  render   GPU (caller must hold /home/kim/Projects/SAO/.gpu.lock). Resumable.
  analyze  CPU. Per-render frame-level pitch-class recovery vs TARGET and SOURCE
           patterns (muscriptor .mid cache from hook_eval_renders.py), per-frame
           chroma cosine, disintegration gate, turn verdicts -> results.json + table.

Venv: /home/kim/Projects/SAO/.venv (has stable_audio_3 + muscriptor + mido + librosa).
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SAO = Path("/home/kim/Projects/SAO")
sys.path.insert(0, "/home/kim/Projects/mir-same-chroma/src")
sys.path.insert(0, str(SAO / "eval"))

MIDI_DIR = SAO / "eval/musicology/test_midis"
RENDERS_DIR = MIDI_DIR / "renders"
OUT = HERE
WAV_DIR = OUT / "renders"
MANIFEST = OUT / "manifest.json"

FPS = 10.7666015625
N_FRAMES = 256
DURATION = N_FRAMES / FPS            # 23.777 s (256-frame tile, MASTER frames rule)
STEPS = 24
CFG = 7.0
SR = 44100

HEADS = {
    "same_chroma": str(SAO / "stable-audio-3/latch_weights_sa3_medium/latch_sa3_same_chroma_best.pt"),
    "chroma_other": "/run/media/kim/Mantu/sa3_lora_runs/cu_reward_renders/analysis/chroma_heads/latch_sa3_chroma_other_best.pt",
}

PATS = {
    "pat1": "pat1_const16_1pitch_bpm161p5_32bars.mid",
    "pat2": "pat2_const16_2pitch_bpm161p5_32bars.mid",
    "pat3": "pat3_const16_arp4_bpm161p5_32bars.mid",
    "pat6": "pat6_pedal_b2trill_bpm161p5_32bars.mid",
}
SOURCE_WAV = RENDERS_DIR / "pat1_const16_1pitch_bpm161p5_32bars__sawlead.wav"

PROMPT_FREE = ("melodic goa trance, hypnotic arpeggiated lead, driving rolling "
               "bassline, 161 BPM")
PROMPT_A2A = ("TrackType: Instrument, a solo analog synth lead playing a hypnotic "
              "arpeggiated melodic line, 161 BPM")

GAINS = [1536, 2048]
SEEDS = [1234, 5678]
NLS = [0.45, 0.6]


# ── ground truth: per-frame pitch class from the frame-locked MIDIs ────────────────

def midi_frame_pcs(pat: str, n_frames: int = N_FRAMES) -> np.ndarray:
    """(n_frames,) int pitch-class per frame (frame-locked: 1 note == 1 frame),
    -1 where silent."""
    import mido
    m = mido.MidiFile(MIDI_DIR / PATS[pat])
    notes = []
    for tr in m.tracks:
        abs_t, tempo, pend = 0, 500000, {}
        for msg in tr:
            abs_t += msg.time
            if msg.type == "set_tempo":
                tempo = msg.tempo
            if msg.type == "note_on" and msg.velocity > 0:
                pend[msg.note] = abs_t
            elif msg.type in ("note_off", "note_on") and msg.note in pend:
                notes.append((pend.pop(msg.note), abs_t, msg.note, tempo))
    notes.sort()
    tempo = notes[0][3]
    out = np.full(n_frames, -1, dtype=np.int64)
    for a, b, n, _ in notes:
        t0 = mido.tick2second(a, m.ticks_per_beat, tempo)
        f = int(round(t0 * FPS))
        if 0 <= f < n_frames:
            out[f] = n % 12
    return out


def target_raw_384(pcs: np.ndarray) -> np.ndarray:
    """(384, T) SAME 3-band steering target from a per-frame pc stream — the exact
    expansion chroma_steer_render.build_target_raw used (bass locked to the frame's
    pc, one-hot mel12)."""
    from harmonic import same_chroma as sc
    cache = {}
    out = np.zeros((3, 128, len(pcs)), dtype=np.float32)
    for f, pc in enumerate(pcs):
        if pc < 0:
            continue
        if pc not in cache:
            mel12 = np.zeros(12, dtype=np.float64)
            mel12[pc] = 1.0
            cache[pc] = sc.make_steering_target(1, mel12, bass_root=int(pc),
                                                bass_gain=1.0, mid_gain=1.0,
                                                air_gain=0.3)[:, :, 0]
        out[:, :, f] = cache[pc]
    return out.reshape(384, len(pcs))


# ── the grid ───────────────────────────────────────────────────────────────────────

def cells():
    """Yield cell dicts. ~26 renders total."""
    # Arm A — free generation + chroma stream: does the melody follow the target?
    for tgt in ("pat2", "pat3", "pat6"):
        for g in GAINS:
            for s in SEEDS:
                yield dict(arm="A", target=tgt, head="same_chroma", gain=g,
                           nl=None, seed=s, prompt=PROMPT_FREE)
    for s in SEEDS:  # unguided baselines (gate anchor + adoption null)
        yield dict(arm="A", target=None, head=None, gain=0, nl=None, seed=s,
                   prompt=PROMPT_FREE)
    # Arm B — MELODY TURNING: SDEdit from pat1 sawlead + steer to a different pattern
    for tgt in ("pat2", "pat6"):
        for nl in NLS:
            for g in GAINS:
                yield dict(arm="B", target=tgt, head="same_chroma", gain=g,
                           nl=nl, seed=1234, prompt=PROMPT_A2A, source="pat1")
    # Arm Bx — head comparison: the chroma-morph stem head, best-guess combo
    for tgt in ("pat2", "pat6"):
        yield dict(arm="Bx", target=tgt, head="chroma_other", gain=2048,
                   nl=0.6, seed=1234, prompt=PROMPT_A2A, source="pat1")
    # Arm C — control: same SDEdit, NO chroma guidance (does the melody stay A?)
    for nl in NLS:
        yield dict(arm="C", target=None, head=None, gain=0, nl=nl, seed=1234,
                   prompt=PROMPT_A2A, source="pat1")
    # Arm Bext — gain extension (coordinator follow-up 2026-07-22): the one lever the
    # base probe left unexhausted. Best cells only, wide gains.
    for tgt in ("pat2", "pat6"):
        for g in (4096, 8192):
            for s in SEEDS:
                yield dict(arm="Bext", target=tgt, head="same_chroma", gain=g,
                           nl=0.6, seed=s, prompt=PROMPT_A2A, source="pat1")
    # second-seed control for the extension's null/gate
    yield dict(arm="C", target=None, head=None, gain=0, nl=0.6, seed=5678,
               prompt=PROMPT_A2A, source="pat1")


def clip_name(c) -> str:
    tgt = c["target"] or "none"
    head = c["head"] or "nohead"
    nl = "nlNA" if c["nl"] is None else f"nl{int(c['nl']*100):02d}"
    return f"{c['arm']}__{tgt}__{head}__g{c['gain']}__{nl}__s{c['seed']}"


# ── render (GPU; caller holds .gpu.lock) ───────────────────────────────────────────

def render():
    import torch
    import soundfile as sf
    from stable_audio_3 import StableAudioModel
    sys.path.insert(0, str(SAO / "control"))
    from sa3_control.audio_io import save_audio

    WAV_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"cells": []}
    done = {c["clip"] for c in manifest["cells"]}

    tgt_streams = {p: midi_frame_pcs(p) for p in PATS}
    raw384 = {p: target_raw_384(tgt_streams[p]) for p in ("pat2", "pat3", "pat6")}

    src_np, src_sr = sf.read(str(SOURCE_WAV), dtype="float32")   # (N, C)
    src_wav = torch.from_numpy(src_np.T)[:, : int(DURATION * src_sr)]
    assert src_sr == SR

    model = StableAudioModel.from_pretrained("medium-base", device="cuda")

    for c in cells():
        name = clip_name(c)
        if name in done:
            continue
        t0 = time.time()
        gen = dict(prompt=c["prompt"], duration=DURATION, steps=STEPS,
                   cfg_scale=CFG, seed=c["seed"], return_latents=True)
        if c.get("source"):
            gen["init_audio"] = (SR, src_wav)
            gen["init_noise_level"] = float(c["nl"])
        if c["gain"] > 0:
            gen["latch_configs"] = [{"model_path": HEADS[c["head"]],
                                     "target_raw": raw384[c["target"]],
                                     "weight": 1.0, "loss_type": "cosine"}]
            gen["latch_hparams"] = {"rho": float(c["gain"]), "mu": float(c["gain"])}
        z0 = model.generate(**gen)
        # save z0 next to the render (standing directive), then decode + normalize
        np.save(WAV_DIR / f"{name}.z0.npy", z0.cpu().to(torch.float16).numpy())
        decode_dtype = next(model.model.pretransform.parameters()).dtype
        with torch.no_grad():
            audio = model.model.pretransform.decode(z0.type(decode_dtype))
        audio = audio.to(torch.float32).cpu()
        peak = audio.abs().amax().clamp(min=1.0)
        audio = (audio / peak)[0]
        save_audio(str(WAV_DIR / f"{name}.wav"), audio, SR)
        row = dict(clip=name, **{k: v for k, v in c.items()},
                   elapsed=round(time.time() - t0, 1))
        manifest["cells"].append(row)
        done.add(name)
        MANIFEST.write_text(json.dumps(manifest, indent=1))
        print(f"[{name}] {row['elapsed']}s", flush=True)

    _write_run_meta(manifest)
    print(f"[render done] {len(manifest['cells'])} cells")


def _write_run_meta(manifest):
    (OUT / "run_meta.json").write_text(json.dumps({
        "purpose": ("Melody-turning feasibility probe (Kim direct 2026-07-22): impose a "
                    "per-frame chroma target stream (exact, from frame-locked test MIDIs) "
                    "through LatCH target_raw guidance — free-gen melody adoption (arm A) "
                    "and SDEdit a2a melody TURNING pat1->pat2/pat6 (arm B) vs unguided "
                    "SDEdit control (arm C)."),
        "hypothesis": ("If training-free frame-level chroma steering has real per-frame "
                       "pitch authority (not just static-key authority), arm B outputs "
                       "keep the source texture but adopt the target melody: "
                       "target-adoption high, source-retention low, disintegration gate "
                       "clean. Bears directly on Head B's role."),
        "recipe": {"entry": "model.generate(latch_configs target_raw 384-d, rho=mu=gain)",
                   "gains": GAINS, "nls": NLS, "steps": STEPS, "cfg": CFG,
                   "duration_sec": round(DURATION, 3), "n_frames": N_FRAMES,
                   "loss_type": "cosine", "seeds": SEEDS,
                   "source_audio": str(SOURCE_WAV),
                   "heads": HEADS,
                   "scripts": [str(HERE / "chromaturn.py"),
                               str(SAO / "eval/hook_eval_renders.py")]},
        "dataset_info": "no training — pretrained SA3 medium-base + shipped LatCH chroma heads",
        "result": {"clips": len(manifest["cells"])},
        "kim_feedback": None,
        "related": ["eval/chroma_steer_render.py", "eval/musicology/test_midis/manifest.json",
                    "docs/todos.md:15 (chroma-morph)", "eval/disintegration_metrics.py"],
    }, indent=2))


# ── analyze (CPU) ──────────────────────────────────────────────────────────────────

def _frame_pcs_from_mid(mid_path: Path, n_frames: int = N_FRAMES) -> np.ndarray:
    """(n_frames,) skyline pitch-class per frame from a transcribed .mid, -1=silent.
    Uses hook_metric.notes_from_midi_bytes (mido; drums = channel 9 excluded)."""
    sys.path.insert(0, str(SAO / "eval/musicology"))
    from hook_metric import notes_from_midi_bytes
    notes = notes_from_midi_bytes(mid_path.read_bytes())
    out = np.full(n_frames, -1, dtype=np.int64)
    best = np.full(n_frames, -1, dtype=np.int64)  # highest sounding pitch
    for s0, s1, pitch, vel, is_drum, _ti in notes:
        if is_drum:
            continue
        f0 = max(0, int(np.floor(s0 * FPS)))
        f1 = min(n_frames, int(np.ceil(s1 * FPS)))
        for f in range(f0, f1):
            if pitch > best[f]:
                best[f] = pitch
                out[f] = pitch % 12
    return out


def _match(out_pcs, ref_pcs, mask=None, shift=0):
    """Fraction of (masked) ref frames whose pc the output hits (+-1 frame slop),
    under a global shift of the output."""
    n = len(ref_pcs)
    idx = np.arange(n)
    if mask is None:
        mask = ref_pcs >= 0
    hits, tot = 0, 0
    for f in idx[mask]:
        tot += 1
        for d in (0, -1, 1):
            g = f + shift + d
            if 0 <= g < n and out_pcs[g] == ref_pcs[f]:
                hits += 1
                break
    return hits / max(tot, 1)


def _nonmodal_mask(ref_pcs):
    """Frames whose pc differs from the pattern's modal pc (the melody's MOVING part —
    a one-note drone on the modal pc scores 0 here instead of the modal fraction)."""
    valid = ref_pcs >= 0
    mode = np.bincount(ref_pcs[valid], minlength=12).argmax()
    return valid & (ref_pcs != mode)


def _best_shift(out_pcs, ref_pcs, mask, span=16):
    best = (0, -1.0)
    for s in range(-span, span + 1):
        m = _match(out_pcs, ref_pcs, mask, s)
        if m > best[1]:
            best = (s, m)
    return best


def _chroma_cos(wav_path: Path, pcs: np.ndarray, mask):
    """Mean per-frame cosine between output chroma (CQT, hop=4096 -> 10.766 fps) and
    the one-hot target pc, over masked frames."""
    import librosa
    y, _ = librosa.load(str(wav_path), sr=SR, mono=True)
    C = librosa.feature.chroma_cqt(y=y, sr=SR, hop_length=4096)  # (12, T)
    C = C / (np.linalg.norm(C, axis=0, keepdims=True) + 1e-9)
    vals = []
    for f in np.arange(len(pcs))[mask]:
        if pcs[f] >= 0 and f < C.shape[1]:
            vals.append(float(C[pcs[f], f]))
    return float(np.mean(vals)) if vals else float("nan")


def analyze():
    from disintegration_metrics import measure, gate

    manifest = json.loads(MANIFEST.read_text())
    midi_cache = OUT / "hook_scores_midi"
    gt = {p: midi_frame_pcs(p) for p in PATS}
    hook = {}
    hs = OUT / "hook_scores.jsonl"
    if hs.exists():
        for line in open(hs):
            r = json.loads(line)
            hook[r["clip"]] = r

    # gate baselines: armA g0 per seed; armB/Bx -> armC same nl
    dsp = {}
    for c in manifest["cells"]:
        p = WAV_DIR / f"{c['clip']}.wav"
        if p.exists():
            dsp[c["clip"]] = measure(p)

    def gate_baseline(c):
        if c["arm"] == "A":
            return next((x for x in manifest["cells"] if x["arm"] == "A"
                         and x["gain"] == 0 and x["seed"] == c["seed"]), None)
        return next((x for x in manifest["cells"] if x["arm"] == "C"
                     and x["nl"] == c["nl"]), None) or \
            next((x for x in manifest["cells"] if x["arm"] == "C"), None)

    results = []
    for c in manifest["cells"]:
        name = c["clip"]
        row = dict(c)
        mid = midi_cache / f"{name}.mid"
        out_pcs = _frame_pcs_from_mid(mid) if mid.exists() else None
        tgt = c.get("target")
        src = c.get("source")
        if out_pcs is not None:
            row["coverage"] = round(float((out_pcs >= 0).mean()), 3)
            for label, ref in (("target", tgt), ("source", src)):
                if not ref:
                    continue
                ref_pcs = gt[ref]
                other = gt[src] if (label == "target" and src) else \
                        (gt[tgt] if (label == "source" and tgt) else None)
                # discriminative frames: where this ref differs from the other stream
                dmask = (ref_pcs >= 0) if other is None else \
                        ((ref_pcs >= 0) & (ref_pcs != other))
                amask = ref_pcs >= 0
                nmask = _nonmodal_mask(ref_pcs)
                if c["arm"] == "A":
                    s, m = _best_shift(out_pcs, ref_pcs, nmask)
                    row[f"{label}_shift"] = s
                    row[f"{label}_all"] = round(_match(out_pcs, ref_pcs, amask, s), 3)
                    row[f"{label}_nonmodal"] = round(m, 3)
                    row[f"{label}_disc"] = round(_match(out_pcs, ref_pcs, dmask, s), 3) \
                        if other is not None else None
                else:
                    row[f"{label}_all"] = round(_match(out_pcs, ref_pcs, amask, 0), 3)
                    row[f"{label}_nonmodal"] = round(_match(out_pcs, ref_pcs, nmask, 0), 3)
                    row[f"{label}_disc"] = round(_match(out_pcs, ref_pcs, dmask, 0), 3) \
                        if other is not None else None
            # arm-A unguided baselines: would-be adoption of every candidate pattern
            # (the empirical null floor for arm A's target_nonmodal)
            if c["arm"] == "A" and c["gain"] == 0:
                for cand in ("pat2", "pat3", "pat6"):
                    ref_pcs = gt[cand]
                    nmask = _nonmodal_mask(ref_pcs)
                    s, m = _best_shift(out_pcs, ref_pcs, nmask)
                    row[f"null_{cand}_nonmodal"] = round(m, 3)
            # control arms (source, no target): would-be adoption of each candidate
            # target = the empirical null floor for arm B's target_disc
            if src and not tgt and c["arm"] in ("C",):
                for cand in ("pat2", "pat6"):
                    ref_pcs = gt[cand]
                    dmask = (ref_pcs >= 0) & (ref_pcs != gt[src])
                    row[f"null_{cand}_disc"] = round(_match(out_pcs, ref_pcs, dmask, 0), 3)
                    row[f"null_{cand}_chroma"] = round(
                        _chroma_cos(WAV_DIR / f"{c['clip']}.wav", ref_pcs, dmask), 3)
            # null rate: adoption expected from the output's marginal pc distribution
            if tgt:
                ref_pcs = gt[tgt]
                vm = (out_pcs >= 0)
                if vm.any():
                    pdist = np.bincount(out_pcs[vm], minlength=12) / vm.sum()
                    row["null_rate"] = round(float(np.mean(
                        [pdist[p] for p in ref_pcs[ref_pcs >= 0]])) * 3, 3)  # ~+-1 slop
        # chroma-level (transcription-free); nonmodal mask when there is no source
        if tgt:
            ref_pcs = gt[tgt]
            srcm = gt[src] if src else None
            dmask = _nonmodal_mask(ref_pcs) if srcm is None else \
                ((ref_pcs >= 0) & (ref_pcs != srcm))
            row["tgt_chroma_cos_disc"] = round(_chroma_cos(WAV_DIR / f"{name}.wav",
                                                           ref_pcs, dmask), 3)
        if c["arm"] == "A" and c["gain"] == 0:
            for cand in ("pat2", "pat3", "pat6"):
                row[f"null_{cand}_chroma"] = round(_chroma_cos(
                    WAV_DIR / f"{name}.wav", gt[cand], _nonmodal_mask(gt[cand])), 3)
        if src:
            ref_pcs = gt[src]
            tgtm = gt[tgt] if tgt else None
            dmask = (ref_pcs >= 0) if tgtm is None else ((ref_pcs >= 0) & (ref_pcs != tgtm))
            row["src_chroma_cos_disc"] = round(_chroma_cos(WAV_DIR / f"{name}.wav",
                                                           ref_pcs, dmask), 3)
        # disintegration gate
        b = gate_baseline(c)
        if c["gain"] > 0 and b and b["clip"] in dsp and name in dsp:
            g = gate(dsp[name], dsp[b["clip"]])
            row["gate"] = "BLOWN:" + ",".join(g["reasons"]) if g["blown"] else "clean"
        elif c["gain"] == 0:
            row["gate"] = "baseline"
        if name in hook:
            row["hook_melodic_ratio"] = hook[name].get("hook_melodic_ratio")
            row["n_lead"] = hook[name].get("n_lead")
        results.append(row)

    (OUT / "results.json").write_text(json.dumps(results, indent=1))
    # table
    cols = ["clip", "gate", "coverage", "target_all", "target_nonmodal", "target_disc",
            "source_all", "source_disc", "tgt_chroma_cos_disc", "src_chroma_cos_disc",
            "null_pat2_nonmodal", "null_pat3_nonmodal", "null_pat6_nonmodal",
            "null_pat2_disc", "null_pat6_disc", "null_pat2_chroma", "null_pat3_chroma",
            "null_pat6_chroma"]
    print("\t".join(cols))
    for r in sorted(results, key=lambda r: r["clip"]):
        print("\t".join(str(r.get(k, "")) for k in cols))


def targets_check():
    for p in PATS:
        pcs = midi_frame_pcs(p)
        uniq = sorted(set(pcs[pcs >= 0].tolist()))
        print(f"{p}: frames={len(pcs)} silent={(pcs<0).sum()} pcs={uniq} "
              f"first16={pcs[:16].tolist()}")
    for p in ("pat2", "pat3", "pat6"):
        raw = target_raw_384(midi_frame_pcs(p))
        assert raw.shape == (384, N_FRAMES) and np.isfinite(raw).all()
        print(f"{p}: target_raw 384x{N_FRAMES} ok, nonzero-frac={float((raw!=0).mean()):.3f}")
    n = sum(1 for _ in cells())
    print(f"grid = {n} renders; source wav exists: {SOURCE_WAV.exists()}")
    for h, pth in HEADS.items():
        print(f"head {h}: exists={Path(pth).exists()}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["targets", "render", "analyze"])
    a = ap.parse_args()
    {"targets": targets_check, "render": render, "analyze": analyze}[a.mode]()
