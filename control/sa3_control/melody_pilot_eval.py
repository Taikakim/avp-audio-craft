#!/usr/bin/env python
"""melody_pilot_eval.py — Head B (melody_contour FiLM adapter) local-pilot renders + eval.

Spec: docs/superpowers/specs/2026-07-22-melodic-latch-film.md §2/§8; Head A postmortem
(eval/musicology/head_a_ceiling_act/REPORT.md) made forward conditioning THE melody path.
Pilot bar (a DIRECTION check, not the ≥60% production bar): conditioned clips' contour
adoption > null/rest clips' by a clear margin, with disintegration gates clean.

Subcommands (each in the right venv):
  render    GPU (caller holds /home/kim/Projects/SAO/.gpu.lock). 8 cells: 4 conditioned on
            motif_catalog cells (2 pedal-heavy + 2 oscillation), 4 with an all-rest stream
            (seed-matched controls). Saves wav + z0 (standing directive) + manifest.
            Venv: SAO/.venv.
  analyze   CPU. muscriptor .mid cache (hook_eval_renders.py) -> per-frame skyline contour
            classes -> adoption vs the conditioning stream (chromaturn harness pattern:
            adoption / null floor / disintegration gate) + z0 causal check + semantic
            columns merged from clap.json/mood.json if present. Venv: SAO/.venv.
  clap      CPU. CLAP genre-hold on all 8 (W-mandated semantic column, spec §8 W-review #1).
            Venv: stable-audio-tools/sat-venv (laion_clap).
  mood      CPU. mood_drift 'melodic' tag + cosine to the goa corpus mood reference
            (eval/corpus_reference.json). Venv: mir/bin/python (essentia+TF).
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")

import numpy as np

SAO = Path("/home/kim/Projects/SAO")
# OUT is env-overridable (HEADB_OUT) so a bracket driver can point each (ckpt,cfg,gain)
# cell at its own dir on the EVAL DRIVE (MASTER §4: eval outputs live on Mantu/
# sa3_control_runs, never the SAO tree). Default = the original pilot dir (unchanged).
OUT = Path(os.environ.get("HEADB_OUT", str(SAO / "eval/musicology/head_b_pilot_2026-07-23")))
WAV_DIR = OUT / "renders"
MANIFEST = OUT / "manifest.json"

FPS = 10.7666015625
N_FRAMES = 512                      # T=512 (MASTER frames rule) = 47.554 s, matches training crop
DURATION = N_FRAMES / FPS
STEPS = 24
CFG = float(os.environ.get("HEADB_CFG", "7.0"))     # env-overridable for the bracket sweep
SR = 44100
BPM = 143.0                         # corpus tri-modal center-ish; spec §0 grid reference
GAIN = float(os.environ.get("HEADB_GAIN", "1.0"))   # as trained; env-overridable for bracket
SEEDS = [1111, 2222, 3333, 4444]
PROMPT = ("psychedelic goa trance, hypnotic melodic acid lead line, driving rolling "
          "bassline, 143 BPM")

FOLD_NAMES = ["rest", "pedal", "m1", "m2", "m3", "m5", "m7", "m12"]
ALLOWED = [1, 2, 3, 5, 7, 12]
_MAG_MAP = {}                       # nearest allowed magnitude (prep_targets convention)
for a in range(1, 128):
    aa = min(a, 12)
    _MAG_MAP[a] = min(ALLOWED, key=lambda m: (abs(aa - m), m))

# The 4 catalog cells (eval/musicology/motif_catalog.json families_grid, by gram):
# 2 pedal-heavy + 2 oscillation per the pilot tasking. grams are per-16th intervals.
CELLS = {
    "pedal4":    {"gram": [0, 0, 0, 0],        "klass": "pedal",          "seed": SEEDS[0]},
    "descrun":   {"gram": [-1, 0, 0, 0],       "klass": "descending run", "seed": SEEDS[1]},
    "oct_osc":   {"gram": [12, -12, 12, -12],  "klass": "oscillation",    "seed": SEEDS[2]},
    "m3_osc":    {"gram": [3, -3, 0, 0],       "klass": "oscillation",    "seed": SEEDS[3]},
}
LEAD_PITCH_MIN = 56                 # prep_targets convention


def fold_of_interval(d: int) -> int:
    if d == 0:
        return 1                                            # pedal
    return 2 + ALLOWED.index(_MAG_MAP[abs(d)])


def cell_class_stream(gram, n_frames=N_FRAMES, bpm=BPM) -> np.ndarray:
    """(n_frames,) int64 folded class stream: the cell's per-16th classes tiled across
    the render at `bpm`, sampled nearest-frame onto the 10.766 Hz latent grid (the same
    grid->frame rasterization prep_targets used, minus the sub-frame overlap split —
    a conditioning input wants one symbol per frame)."""
    step = 60.0 / bpm / 4.0                                 # 16th duration (s)
    cls16 = [fold_of_interval(d) for d in gram]             # class of each 16th in the cell
    out = np.empty(n_frames, dtype=np.int64)
    for f in range(n_frames):
        slot = int(((f + 0.5) / FPS) / step)
        out[f] = cls16[slot % len(cls16)]
    return out


def cells():
    for name, c in CELLS.items():
        yield dict(cell=name, klass=c["klass"], gram=c["gram"], seed=c["seed"],
                   conditioned=True)
    for s in SEEDS:                                          # null/rest controls, seed-matched
        yield dict(cell="null", klass="null", gram=None, seed=s, conditioned=False)


def clip_name(c) -> str:
    return f"{'cond' if c['conditioned'] else 'null'}__{c['cell']}__s{c['seed']}"


# ── render (GPU; caller holds the .gpu.lock) ────────────────────────────────────────

def render(args):
    import torch
    from stable_audio_3 import StableAudioModel
    sys.path.insert(0, str(SAO / "control"))
    from sa3_control.adapters import ControlContext, use_control_context
    from sa3_control.audio_io import save_audio
    from sa3_control.generate import build_conditioner, load_adapter_state
    from sa3_control.inject import install_adapters

    WAV_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"cells": []}
    done = {c["clip"] for c in manifest["cells"] if (WAV_DIR / (c["clip"] + ".wav")).exists()}
    manifest["cells"] = [c for c in manifest["cells"] if c["clip"] in done]

    ck = torch.load(args.ckpt, map_location="cpu", weights_only=False)
    assert ck.get("control_mode") == "melody_contour", ck.get("control_mode")
    cargs = ck.get("args", {})

    device = "cuda" if torch.cuda.is_available() else "cpu"
    sam = StableAudioModel.from_pretrained(cargs.get("model", "medium-base"), device=device)
    md = next(sam.model.model.parameters()).dtype
    dit = sam.model.model

    # dora-rows (joint-trained) — rebuild the same parametrization, load the saved state.
    # ORDER MATTERS (matches train.py:374-401): add_lora on the RAW DiT MUST run BEFORE
    # install_adapters (so the control-adapter Linears are NOT dora-parametrized — dora covers
    # the base DiT only), but the LOAD must run AFTER install_adapters wraps each cross_attn into
    # ControlledCrossAttention.base_attention (adapters.py:151) — get_lora_state_dict serialized
    # the dora keys post-wrap, so ck["lora_state"] carries the `cross_attn.base_attention.*`
    # prefix and only resolves once the wrapper exists. Loading before the wrap = every key
    # "unexpected" (the melody-bracket crash, job 20328757).
    _dora = int(ck.get("dora_rank", 0) or 0) > 0
    if _dora:
        from functools import partial
        from stable_audio_3.models.lora import add_lora, LoRAParametrization
        r = int(ck["dora_rank"])
        alpha = ck.get("dora_alpha") or float(r)
        lcfg = {torch.nn.Linear: {"weight": partial(LoRAParametrization.from_linear,
                                                    rank=r, lora_alpha=alpha,
                                                    adapter_type="dora-rows")},
                torch.nn.Conv1d: {"weight": partial(LoRAParametrization.from_conv1d,
                                                    rank=r, lora_alpha=alpha,
                                                    adapter_type="dora-rows")}}
        add_lora(dit, lcfg)                       # raw DiT, BEFORE wrap (as trained)

    wrappers = install_adapters(sam, control_dim=int(cargs.get("control_dim", 768)))

    if _dora:                                     # AFTER wrap: keys now carry base_attention.*
        missing, unexpected = dit.load_state_dict(ck["lora_state"], strict=False)
        n_loaded = len(ck["lora_state"]) - len([k for k in ck["lora_state"] if k in missing])
        assert not unexpected, f"unexpected lora keys: {unexpected[:4]}"
        print(f"[dora] r{r} alpha={alpha:g} rebuilt; {n_loaded}/{len(ck['lora_state'])} "
              f"tensors loaded", flush=True)
    cond_enc = build_conditioner(ck, device, md)
    load_adapter_state(ck["state"], wrappers, cond_enc)
    for w in wrappers:
        w.adapter.to(device=device, dtype=md)
    cond_enc.to(device=device, dtype=md).eval()

    for c in cells():
        name = clip_name(c)
        if name in done:
            continue
        t0 = time.time()
        stream = (cell_class_stream(c["gram"]) if c["conditioned"]
                  else np.zeros(N_FRAMES, dtype=np.int64))       # all-rest null stream
        with torch.inference_mode():
            ctrl = cond_enc(torch.from_numpy(stream)[None].to(device))    # (1, T, d)
        if CFG != 1.0:      # CFG batch [cond, uncond]; zero TOKENS = the trained null
            ctrl = torch.cat([ctrl, torch.zeros_like(ctrl)], dim=0)
        with use_control_context(ControlContext(ctrl, gain=GAIN)):
            z0 = sam.generate(prompt=PROMPT, duration=DURATION, steps=STEPS,
                              cfg_scale=CFG, seed=c["seed"], sampler_type="euler",
                              return_latents=True)
        np.save(WAV_DIR / f"{name}.z0.npy", z0.cpu().to(torch.float16).numpy())
        decode_dtype = next(sam.model.pretransform.parameters()).dtype
        with torch.no_grad():
            audio = sam.model.pretransform.decode(z0.type(decode_dtype))
        audio = audio.to(torch.float32).cpu()
        audio = (audio / audio.abs().amax().clamp(min=1.0))[0]
        save_audio(str(WAV_DIR / f"{name}.wav"), audio, SR)
        np.save(WAV_DIR / f"{name}.stream.npy", stream.astype(np.int8))
        manifest["cells"].append(dict(clip=name, **{k: v for k, v in c.items()},
                                      elapsed=round(time.time() - t0, 1)))
        done.add(name)
        MANIFEST.write_text(json.dumps(manifest, indent=1))
        print(f"[{name}] {manifest['cells'][-1]['elapsed']}s", flush=True)

    _write_run_meta(args, manifest)
    print(f"[render done] {len(manifest['cells'])} cells", flush=True)


def _write_run_meta(args, manifest):
    (OUT / "run_meta.json").write_text(json.dumps({
        "purpose": ("Head B pilot: first melody-contour CONDITIONING adapter "
                    "(control_mode=melody_contour + joint dora-rows). 4 catalog-motif "
                    "conditioned renders vs 4 seed-matched all-rest controls — does the "
                    "conditioning stream move the rendered contour at all?"),
        "hypothesis": ("Forward conditioning removes the conditional-averaging entropy "
                       "(spec §7 M2), so conditioned clips should adopt the supplied "
                       "contour above the null clips' floor WITHOUT disintegration-gate "
                       "failures. Direction check only; production bar (≥60% frame "
                       "recovery) is NOT this pilot's bar."),
        "recipe": {"ckpt": str(args.ckpt), "prompt": PROMPT, "bpm": BPM, "gain": GAIN,
                   "cfg": CFG, "steps": STEPS, "duration_sec": round(DURATION, 3),
                   "n_frames": N_FRAMES, "seeds": SEEDS,
                   "cells": {k: v["gram"] for k, v in CELLS.items()},
                   "scripts": ["control/sa3_control/melody_pilot_eval.py",
                               "control/sa3_control/train.py (melody_contour mode)",
                               "control/sa3_control/prep_melody_conditioning.py",
                               "eval/hook_eval_renders.py"]},
        "dataset_info": ("goa latents_sa3 melody-covered subset (~800 crops of 2649, "
                         "subset_tracks=0.3 seed 42), teacher-forced (crop, own lead "
                         "stream) pairs; targets reused from head_a_ceiling prep"),
        "result": {"clips": len(manifest["cells"])},
        "kim_feedback": None,
        "related": ["docs/superpowers/specs/2026-07-22-melodic-latch-film.md",
                    "eval/musicology/head_a_ceiling_act/REPORT.md",
                    "eval/musicology/chroma_turning_2026-07-22/ (harness pattern)",
                    "eval/musicology/motif_catalog.json"],
    }, indent=2))


# ── analyze (CPU) ───────────────────────────────────────────────────────────────────

def _skyline_frame_pitch(mid_path: Path, n_frames=N_FRAMES) -> np.ndarray:
    """(n_frames,) skyline MIDI pitch per frame from a transcribed .mid (-1 = silent),
    non-drum notes with pitch >= LEAD_PITCH_MIN (prep_targets lead convention)."""
    sys.path.insert(0, str(SAO / "eval/musicology"))
    from hook_metric import notes_from_midi_bytes
    notes = notes_from_midi_bytes(mid_path.read_bytes())
    best = np.full(n_frames, -1, dtype=np.int64)
    for s0, s1, pitch, vel, is_drum, _t in notes:
        if is_drum or pitch < LEAD_PITCH_MIN:
            continue
        f0 = max(0, int(np.floor(s0 * FPS)))
        f1 = min(n_frames, max(f0 + 1, int(np.ceil(s1 * FPS))))
        for f in range(f0, f1):
            if pitch > best[f]:
                best[f] = pitch
    return best


def _contour_classes(frame_pitch: np.ndarray, gap_frames=8) -> np.ndarray:
    """Frame pitch stream -> folded contour class per frame (0=rest). Note = a maximal
    constant-pitch run; class = interval from the previous note (pedal if equal or if
    the gap exceeds gap_frames = phrase restart, prep_targets semantics)."""
    n = len(frame_pitch)
    cls = np.zeros(n, dtype=np.int64)
    prev_pitch, prev_end = None, -10**9
    i = 0
    while i < n:
        p = frame_pitch[i]
        if p < 0:
            i += 1
            continue
        j = i
        while j < n and frame_pitch[j] == p:
            j += 1
        if prev_pitch is None or (i - prev_end) > gap_frames or p == prev_pitch:
            c = 1                                            # pedal / phrase start
        else:
            c = fold_of_interval(int(p - prev_pitch))
        cls[i:j] = c
        prev_pitch, prev_end = p, j
        i = j
    return cls


def _match(out_cls, ref_cls, mask, shift=0, slop=1):
    n = len(ref_cls)
    hits = tot = 0
    for f in np.arange(n)[mask]:
        tot += 1
        for d in range(-slop, slop + 1):
            g = f + shift + d
            if 0 <= g < n and out_cls[g] == ref_cls[f]:
                hits += 1
                break
    return hits / max(tot, 1)


def _best_shift(out_cls, ref_cls, mask, span=24):
    best = (0, -1.0)
    for s in range(-span, span + 1):
        m = _match(out_cls, ref_cls, mask, s)
        if m > best[1]:
            best = (s, m)
    return best


def analyze(args):
    sys.path.insert(0, str(SAO / "eval"))
    from disintegration_metrics import measure, gate

    manifest = json.loads(MANIFEST.read_text())
    midi_cache = OUT / "hook_scores_midi"
    hook = {}
    hs = OUT / "hook_scores.jsonl"
    if hs.exists():
        for line in open(hs):
            r = json.loads(line)
            hook[r["clip"]] = r
    clap = json.loads((OUT / "clap.json").read_text()) if (OUT / "clap.json").exists() else {}
    mood = json.loads((OUT / "mood.json").read_text()) if (OUT / "mood.json").exists() else {}

    streams = {k: cell_class_stream(v["gram"]) for k, v in CELLS.items()}
    dsp = {c["clip"]: measure(WAV_DIR / f"{c['clip']}.wav") for c in manifest["cells"]
           if (WAV_DIR / f"{c['clip']}.wav").exists()}
    null_by_seed = {c["seed"]: c for c in manifest["cells"] if not c["conditioned"]}

    results = []
    for c in manifest["cells"]:
        name = c["clip"]
        row = dict(c)
        mid = midi_cache / f"{name}.mid"
        out_cls = None
        if mid.exists():
            fp = _skyline_frame_pitch(mid)
            out_cls = _contour_classes(fp)
            row["lead_coverage"] = round(float((fp >= 0).mean()), 3)
            row["pedal_occupancy"] = round(float((out_cls == 1).sum() / max((out_cls > 0).sum(), 1)), 3)
            # marginal class distribution (for the by-chance floor)
            vm = out_cls > 0
            row["class_marginal"] = {FOLD_NAMES[k]: round(float((out_cls == k).mean()), 3)
                                     for k in range(8) if (out_cls == k).any()}
        # adoption vs EVERY motif stream. Conditioned clips: own requested stream = `adopt_*`,
        # the three NON-requested streams = `xtarg_<t>_*` (the CONFUSION baseline — own-vs-wrong
        # is the steering test that survives the null floor collapsing at high cfg, where the
        # all-rest null clips stop producing any lead). Null clips: all four = `null_<t>_*`
        # (the empirical by-chance floor, chromaturn pattern).
        if out_cls is not None:
            if c["conditioned"]:
                order = [(t, "adopt" if t == c["cell"] else f"xtarg_{t}") for t in CELLS]
            else:
                order = [(t, f"null_{t}") for t in CELLS]
            for tname, key in order:
                ref = streams[tname]
                amask = ref > 0                              # all frames (streams are restless)
                mmask = ref > 1                              # moving (non-pedal) frames only
                s, m_all = _best_shift(out_cls, ref, amask)
                row[f"{key}_shift"] = s
                row[f"{key}_all"] = round(m_all, 3)
                row[f"{key}_moving"] = (round(_match(out_cls, ref, mmask, s), 3)
                                        if mmask.any() else None)
                # active-only: restrict to frames where the render HAS a lead — splits
                # "wrong contour" from "no lead rendered at all"
                act = amask & (out_cls > 0)
                row[f"{key}_active"] = round(_match(out_cls, ref, act, s), 3) if act.any() else None
        # z0 causal check vs the seed-matched null (did conditioning change ANYTHING?)
        nb = null_by_seed.get(c["seed"])
        if c["conditioned"] and nb:
            za = np.load(WAV_DIR / f"{name}.z0.npy").astype(np.float32).ravel()
            zb = np.load(WAV_DIR / f"{nb['clip']}.z0.npy").astype(np.float32).ravel()
            row["z0_cos_vs_null"] = round(float((za @ zb) /
                                          (np.linalg.norm(za) * np.linalg.norm(zb) + 1e-9)), 4)
        # disintegration gate vs the seed-matched null baseline
        if c["conditioned"] and nb and name in dsp and nb["clip"] in dsp:
            g = gate(dsp[name], dsp[nb["clip"]])
            row["gate"] = "BLOWN:" + ",".join(g["reasons"]) if g["blown"] else "clean"
        elif not c["conditioned"]:
            row["gate"] = "baseline"
        if name in hook:
            row["hook_melodic_ratio"] = hook[name].get("hook_melodic_ratio")
            row["n_lead"] = hook[name].get("n_lead")
        if name in clap:
            row.update({f"clap_{k}": v for k, v in clap[name].items()})
        if name in mood:
            row.update({f"mood_{k}": v for k, v in mood[name].items()})
        results.append(row)

    (OUT / "results.json").write_text(json.dumps(results, indent=1))
    cols = ["clip", "gate", "lead_coverage", "pedal_occupancy",
            "adopt_all", "adopt_moving", "adopt_active", "adopt_shift", "z0_cos_vs_null",
            "hook_melodic_ratio", "clap_genre_hold", "mood_melodic", "mood_cos_to_goa"]
    ncols = [f"null_{t}_{s}" for t in CELLS for s in ("all", "moving")]
    print("\t".join(cols + ncols))
    for r in sorted(results, key=lambda r: r["clip"]):
        print("\t".join(str(r.get(k, "")) for k in cols + ncols))


# ── clap (sat-venv) ────────────────────────────────────────────────────────────────

def clap_score(args):
    import torch
    import librosa
    import laion_clap
    manifest = json.loads(MANIFEST.read_text())
    model = laion_clap.CLAP_Module(enable_fusion=False, amodel="HTSAT-tiny", device="cpu")
    _orig_load = torch.load
    torch.load = lambda *aa, **kk: _orig_load(*aa, **{**kk, "weights_only": False})
    _orig_lsd = model.model.load_state_dict
    model.model.load_state_dict = lambda sd, strict=True: _orig_lsd(sd, strict=False)
    try:
        model.load_ckpt()
    finally:
        torch.load = _orig_load
        model.model.load_state_dict = _orig_lsd
    genre_prompts = [PROMPT, "goa trance", "ambient drone music", "solid techno",
                     "classical piano music", "static noise"]
    temb = model.get_text_embedding(genre_prompts, use_tensor=False)
    temb = temb / (np.linalg.norm(temb, axis=1, keepdims=True) + 1e-9)
    out = {}
    for c in manifest["cells"]:
        p = WAV_DIR / f"{c['clip']}.wav"
        if not p.exists():
            continue
        y, _ = librosa.load(str(p), sr=48000, mono=True)
        aemb = model.get_audio_embedding_from_data(x=y[None, :], use_tensor=False)
        aemb = aemb / (np.linalg.norm(aemb) + 1e-9)
        sims = (temb @ aemb.T).ravel()
        out[c["clip"]] = {
            "genre_hold": round(float(sims[0]), 4),          # cos(clip, its own prompt)
            "goa_cos": round(float(sims[1]), 4),
            "distractor_mean": round(float(sims[2:].mean()), 4),
            "margin": round(float(sims[0] - sims[2:].mean()), 4),
        }
        print(f"[clap] {c['clip']}: hold={out[c['clip']]['genre_hold']} "
              f"margin={out[c['clip']]['margin']}", flush=True)
    (OUT / "clap.json").write_text(json.dumps(out, indent=1))


# ── mood (mir venv) ────────────────────────────────────────────────────────────────

def mood_score(args):
    sys.path.insert(0, "/home/kim/Projects/mir/src")
    import essentia.standard as es
    from spectral.whole_track_expanded import ExpandedExtractor, MODEL_PATHS
    ref = json.loads((SAO / "eval/corpus_reference.json").read_text())
    labels = ref["moodtheme_labels"]
    goa = np.array(ref["goa"]["mood_mean"], dtype=np.float32)
    mel_i = labels.index("melodic")
    ext = ExpandedExtractor(enable_models=True, enable_dsp=False)
    manifest = json.loads(MANIFEST.read_text())
    out = {}
    for c in manifest["cells"]:
        p = WAV_DIR / f"{c['clip']}.wav"
        if not p.exists():
            continue
        mono16 = es.MonoLoader(filename=str(p), sampleRate=16000)()
        emb = np.asarray(ext._predictor("effnet")(mono16))
        mv = np.asarray(ext._predictor("moodtheme")(emb)).mean(axis=0)
        cos = float(mv @ goa / (np.linalg.norm(mv) * np.linalg.norm(goa) + 1e-9))
        out[c["clip"]] = {"melodic": round(float(mv[mel_i]), 4),
                          "cos_to_goa": round(cos, 4),
                          "top5": "|".join(f"{labels[j]}:{mv[j]:.2f}"
                                           for j in np.argsort(mv)[::-1][:5])}
        print(f"[mood] {c['clip']}: melodic={out[c['clip']]['melodic']} "
              f"cos_goa={out[c['clip']]['cos_to_goa']}", flush=True)
    (OUT / "mood.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["render", "analyze", "clap", "mood"])
    ap.add_argument("--ckpt", default="", help="render: trained melody_contour checkpoint")
    a = ap.parse_args()
    if a.mode == "render" and not a.ckpt:
        sys.exit("render needs --ckpt")
    {"render": render, "analyze": analyze, "clap": clap_score, "mood": mood_score}[a.mode](a)
