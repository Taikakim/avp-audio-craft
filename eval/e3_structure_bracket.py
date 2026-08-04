#!/usr/bin/env python
"""e3_structure_bracket.py — E3 metrical_position structure-recall bracket (3-way).

Design doc: docs/superpowers/specs/2026-07-31-metrical-tree-pe-design.md §4 (readouts).
Template: control/sa3_control/melody_pilot_eval.py — the proven FiLM-adapter generation
harness; model/adapter/conditioner loading is mirrored from it, incl. the LOAD-ORDER fix
(add_lora on the RAW DiT BEFORE install_adapters; ckpt lora_state load AFTER the wrap —
serialized dora keys carry the post-wrap `cross_attn.base_attention.*` prefix; loading
before the wrap = every key "unexpected", the melody-bracket crash, job 20328757).

Three models, matched prompts+seeds:
  base      — no adapter, unconditioned render (capacity floor).
  real      — metrical adapter trained on TRUE metrical sidecars.
  shuffled  — metrical adapter trained on PERMUTED sidecars (collapse baseline: matched
              params, no real metrical info — design doc §3 "shuffled/zeroed baseline").
Adapter arms are conditioned on a CONSTRUCTED steady 145 BPM 4/4 metrical grid covering
all T=512 frames (subdiv/beat/bar/phrase advancing from frame 0, coverage=1, conf=1).

Hypothesis: real arm shows higher phrase-lag (8-bar) self-similarity than shuffled arm at
matched quality; shuffled ~ base = the conditioning carries the effect, not capacity.

Subcommands:
  render    GPU, venv SAO/.venv. 3 models x 4 prompts x 3 seeds, T=512 (47.55 s —
            LOCAL-SAFE; this script hard-refuses T>=2048), cfg 6, 24 steps. Saves wav +
            z0 fp16 (standing directive: latents next to every render) + manifest to
            /run/media/kim/Mantu/sa3_control_runs/e3_metrical/bracket/<model>/.
  analyze   CPU, venv SAO/.venv (librosa). Per clip: half-beat-synchronous chroma
            self-similarity matrix -> mean similarity at lag = 1 bar, lag = 8 bars (the
            PHRASE-RETURN diagnostic), and at random non-metrical (off-beat) lags (the
            control floor); + flatness/hf_ratio vs the matched base clip (disintegration
            guard, eval/disintegration_metrics.py thresholds). Prints the verdict table,
            writes results.json (MANIFEST v2 fields: hypothesis / result / kim_feedback).

GPU discipline (melody_pilot_eval convention): this script does NOT take the GPU mutex
itself — the CALLER holds /home/kim/Projects/SAO/.gpu.lock around `render`
(`python3 Misc/filelock.py acquire /home/kim/Projects/SAO/.gpu.lock --handle <H>
--pid-aware --pid $$`). `analyze` and `--dry-run` never touch the GPU.

Validation without hardware: `--dry-run` builds the metrical grid, prints first/last
frames per row + cycle-period checks, loads nothing heavy, and exits.
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
E3_ROOT = Path("/run/media/kim/Mantu/sa3_control_runs/e3_metrical")
BRACKET = E3_ROOT / "bracket"
ARM_DIRS = {"real": E3_ROOT / "real", "shuffled": E3_ROOT / "shuffled"}
MANIFEST = BRACKET / "manifest.json"

FPS = 10.7666015625                  # SA3 latent frame rate
N_FRAMES = 512                       # T=512 = 47.554 s. LOCAL-SAFE (never T>=2048 locally)
DURATION = N_FRAMES / FPS
STEPS = 24
CFG = 6.0
SR = 44100
BPM = 145.0
SEEDS = [1111, 2222, 3333]
PROMPTS = [                          # 'goa trance, 1996, 145' variants (task spec)
    "goa trance, 1996, 145 BPM",
    "goa trance, 1996, 145 BPM, hypnotic acid lead, driving rolling bassline",
    "psychedelic goa trance, 1996, 145 BPM, layered arpeggios, full-power groove",
    "goa trance, 1996, 145 BPM, melodic breakdown building back into the main theme",
]

# metrical-tree geometry (matches the dataset sidecar convention, dataset.py rows =
# subdiv/beat/bar/phrase/coverage; MetricalEncoder level_sizes (4,4,8,8))
SUBDIV_PER_BEAT = 4
BEATS_PER_BAR = 4
BARS_PER_PHRASE = 8
N_PHRASES = 8                        # phrase_idx wraps at P=8 (design doc §1)
ROW_NAMES = ["subdiv_in_beat", "beat_in_bar", "bar_in_phrase", "phrase_idx", "coverage"]

HYPOTHESIS = ("real arm shows higher phrase-lag (8-bar) self-similarity than shuffled "
              "arm at matched quality; shuffled ~ base = conditioning carries the "
              "effect, not capacity")


def build_metrical_grid(n_frames: int = N_FRAMES, bpm: float = BPM):
    """Steady metrical grid at `bpm`, 4/4, phrase = 8 bars, covering `n_frames` latent
    frames from position zero. Returns (cls (5, T) int64, conf (T,) float32) — the same
    shapes/dtypes the dataset emits per item (dataset.py: "metrical_cls" (5, T) int64 +
    "metrical_conf" (T,) float32). Frame CENTERS ((f+0.5)/FPS) are rasterized onto the
    beat grid, the melody_pilot_eval cell_class_stream convention. Coverage row = 1 and
    conf = 1 everywhere (a fully-confident constructed grid)."""
    cls = np.zeros((5, n_frames), dtype=np.int64)
    conf = np.ones(n_frames, dtype=np.float32)
    f = np.arange(n_frames, dtype=np.float64)
    beats = (f + 0.5) / FPS * (bpm / 60.0)                     # beats elapsed at frame center
    subdiv_total = np.floor(beats * SUBDIV_PER_BEAT).astype(np.int64)
    beat_total = np.floor(beats).astype(np.int64)
    bar_total = beat_total // BEATS_PER_BAR
    cls[0] = subdiv_total % SUBDIV_PER_BEAT
    cls[1] = beat_total % BEATS_PER_BAR
    cls[2] = bar_total % BARS_PER_PHRASE
    cls[3] = (bar_total // BARS_PER_PHRASE) % N_PHRASES
    cls[4] = 1                                                 # coverage flag
    return cls, conf


def clips():
    for m in ("base", "real", "shuffled"):
        for pi, prompt in enumerate(PROMPTS):
            for seed in SEEDS:
                yield dict(model=m, prompt_idx=pi, prompt=prompt, seed=seed,
                           clip=f"{m}__p{pi}__s{seed}")


def pick_ckpt(arm: str, step) -> Path:
    d = ARM_DIRS[arm]
    if step:
        p = d / f"riffer_step{int(step)}.pt"
        if not p.exists():
            sys.exit(f"[{arm}] no {p}")
        return p
    cands = sorted(d.glob("riffer_step*.pt"),
                   key=lambda p: int(p.stem.replace("riffer_step", "")))
    if not cands:
        sys.exit(f"[{arm}] no riffer_step*.pt under {d} (arm not trained yet? "
                 f"use --models to subset)")
    return cands[-1]


# ── dry-run (no heavy imports) ──────────────────────────────────────────────────────

def dry_run():
    cls, conf = build_metrical_grid()
    fpb = FPS * 60.0 / BPM
    print(f"[grid] T={N_FRAMES} @ {BPM:g} BPM 4/4, phrase={BARS_PER_PHRASE} bars | "
          f"frames/beat={fpb:.4f} frames/bar={fpb * BEATS_PER_BAR:.4f} "
          f"frames/phrase={fpb * BEATS_PER_BAR * BARS_PER_PHRASE:.4f}")
    for i, name in enumerate(ROW_NAMES):
        row = cls[i]
        print(f"  {name:14s} first20={row[:20].tolist()} last10={row[-10:].tolist()} "
              f"uniq={sorted(set(row.tolist()))}")
    print(f"  conf           first5={conf[:5].tolist()} last5={conf[-5:].tolist()}")
    # cycle checks
    def increments(row):
        return np.flatnonzero(np.diff(row) != 0) + 1
    sd_period = np.diff(increments(cls[0]))
    beat_inc = increments(cls[1])
    bar_inc = increments(cls[2])
    ph_inc = increments(cls[3])
    print(f"[check] subdiv change interval mean={sd_period.mean():.3f} frames "
          f"(expect ~{fpb / SUBDIV_PER_BEAT:.3f})")
    print(f"[check] beat change interval mean={np.diff(beat_inc).mean():.3f} frames "
          f"(expect ~{fpb:.3f})")
    print(f"[check] bar_in_phrase advances at frames {bar_inc.tolist()[:9]}... "
          f"mean interval={np.diff(bar_inc).mean():.3f} (expect ~{fpb * 4:.3f})")
    print(f"[check] phrase increments at frames {ph_inc.tolist()} "
          f"(expect ~every {fpb * 32:.1f} frames)")
    ok = (set(cls[0]) == set(range(4)) and set(cls[1]) == set(range(4))
          and set(cls[2]) == set(range(8)) and cls[3].max() >= 3
          and abs(np.diff(bar_inc).mean() - fpb * 4) < 0.5
          and abs(np.diff(ph_inc).mean() - fpb * 32) < 2.0 if len(ph_inc) > 1 else True)
    print(f"[dry-run] grid {'OK' if ok else 'MISMATCH — check the math'}")


# ── render (GPU; caller holds /home/kim/Projects/SAO/.gpu.lock) ─────────────────────

def render(args):
    assert N_FRAMES < 2048, "LOCAL-SAFE guard: never render T>=2048 locally (MASTER §5)"
    import torch
    from stable_audio_3 import StableAudioModel
    sys.path.insert(0, str(SAO / "control"))
    from sa3_control.adapters import ControlContext, use_control_context
    from sa3_control.audio_io import save_audio
    from sa3_control.conditioner import MetricalEncoder
    from sa3_control.generate import load_adapter_state
    from sa3_control.inject import install_adapters

    models = [m for m in ("base", "real", "shuffled") if m in args.models.split(",")]
    BRACKET.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"clips": []}
    done = {c["clip"] for c in manifest["clips"]
            if (BRACKET / c["model"] / (c["clip"] + ".wav")).exists()}
    manifest["clips"] = [c for c in manifest["clips"] if c["clip"] in done]

    cls_np, conf_np = build_metrical_grid()
    np.save(BRACKET / "metrical_grid_cls.npy", cls_np.astype(np.int8))
    np.save(BRACKET / "metrical_grid_conf.npy", conf_np)

    ckpts = {}
    for arm in ("real", "shuffled"):
        if arm in models:
            p = pick_ckpt(arm, args.step)
            ck = torch.load(p, map_location="cpu", weights_only=False)
            assert ck.get("control_mode") == "metrical_position", \
                f"{p}: control_mode={ck.get('control_mode')}"
            ckpts[arm] = (p, ck)
            print(f"[{arm}] ckpt {p.name} (dora_rank={ck.get('dora_rank', 0)})", flush=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    _model_id = next(iter(ckpts.values()))[1].get("args", {}).get("model", "medium-base") \
        if ckpts else "medium-base"
    sam = StableAudioModel.from_pretrained(_model_id, device=device)
    md = next(sam.model.model.parameters()).dtype
    dit = sam.model.model
    decode_dtype = next(sam.model.pretransform.parameters()).dtype

    def gen_clips(model, ctrl):
        odir = BRACKET / model
        odir.mkdir(parents=True, exist_ok=True)
        for c in clips():
            if c["model"] != model or c["clip"] in done:
                continue
            t0 = time.time()
            if ctrl is None:                                   # base: unconditioned
                z0 = sam.generate(prompt=c["prompt"], duration=DURATION, steps=STEPS,
                                  cfg_scale=CFG, seed=c["seed"], sampler_type="euler",
                                  return_latents=True)
            else:
                with use_control_context(ControlContext(ctrl, gain=args.gain)):
                    z0 = sam.generate(prompt=c["prompt"], duration=DURATION, steps=STEPS,
                                      cfg_scale=CFG, seed=c["seed"], sampler_type="euler",
                                      return_latents=True)
            np.save(odir / f"{c['clip']}.z0.npy", z0.cpu().to(torch.float16).numpy())
            with torch.no_grad():
                audio = sam.model.pretransform.decode(z0.type(decode_dtype))
            audio = audio.to(torch.float32).cpu()
            audio = (audio / audio.abs().amax().clamp(min=1.0))[0]
            save_audio(str(odir / f"{c['clip']}.wav"), audio, SR)
            manifest["clips"].append(dict(**c, ckpt=str(ckpts[model][0]) if model in ckpts
                                          else None, elapsed=round(time.time() - t0, 1)))
            done.add(c["clip"])
            MANIFEST.write_text(json.dumps(manifest, indent=1))
            print(f"[{c['clip']}] {manifest['clips'][-1]['elapsed']}s", flush=True)

    # base FIRST — must render on the raw, un-parametrized, un-wrapped DiT.
    if "base" in models:
        gen_clips("base", None)

    # arms. Adapters install ONCE; the second arm's state overwrites the first's in place
    # (both arms are the matched-recipe pair, so dora rank/alpha must agree — asserted).
    wrappers = None
    installed = None                                           # (dora_rank, dora_alpha)
    for arm in ("real", "shuffled"):
        if arm not in ckpts:
            continue
        p, ck = ckpts[arm]
        cargs = ck.get("args", {})
        r = int(ck.get("dora_rank", 0) or 0)
        alpha = ck.get("dora_alpha") or (float(r) if r else None)
        if wrappers is None:
            # LOAD-ORDER (template fix, train.py:391-418 parity): add_lora on the RAW DiT
            # BEFORE install_adapters (dora covers the base DiT only, never the adapter
            # Linears); the ckpt lora_state load happens AFTER the wrap below — serialized
            # keys carry the post-wrap cross_attn.base_attention.* prefix.
            if r > 0:
                from functools import partial
                from stable_audio_3.models.lora import add_lora, LoRAParametrization
                lcfg = {torch.nn.Linear: {"weight": partial(
                            LoRAParametrization.from_linear, rank=r, lora_alpha=alpha,
                            adapter_type="dora-rows")},
                        torch.nn.Conv1d: {"weight": partial(
                            LoRAParametrization.from_conv1d, rank=r, lora_alpha=alpha,
                            adapter_type="dora-rows")}}
                add_lora(dit, lcfg)                            # raw DiT, BEFORE wrap
            wrappers = install_adapters(sam, control_dim=int(cargs.get("control_dim", 768)))
            installed = (r, alpha)
        elif installed != (r, alpha):
            sys.exit(f"[{arm}] dora mismatch vs first arm ({installed} != {(r, alpha)}) — "
                     f"the arms aren't the matched pair; render them in separate "
                     f"invocations via --models")
        if r > 0:                                              # AFTER wrap (see above)
            missing, unexpected = dit.load_state_dict(ck["lora_state"], strict=False)
            assert not unexpected, f"unexpected lora keys: {unexpected[:4]}"
            n_loaded = len(ck["lora_state"]) - len([k for k in ck["lora_state"] if k in missing])
            print(f"[{arm}] dora r{r} alpha={alpha:g}: {n_loaded}/{len(ck['lora_state'])} "
                  f"tensors loaded", flush=True)
        # generate.py::build_conditioner has NO metrical_position branch (it would fall
        # through to AudioRefEncoder) -> construct the encoder directly, train.py parity.
        cond_enc = MetricalEncoder(control_dim=int(cargs.get("control_dim", 768)))
        load_adapter_state(ck["state"], wrappers, cond_enc)
        for w in wrappers:
            w.adapter.to(device=device, dtype=md)
        cond_enc.to(device=device, dtype=md).eval()

        m_cls = torch.from_numpy(cls_np)[None].to(device)                     # (1, 5, T)
        m_conf = torch.from_numpy(conf_np)[None].to(device)                   # (1, T)
        with torch.inference_mode():
            ctrl = cond_enc(m_cls, m_conf)                                    # (1, T, d)
            if CFG != 1.0:
                # CFG batch [cond, uncond]. The metrical TRAINED NULL is the ALL-ZERO
                # INPUT *encoded* (train.py:784-801: dropout zeroes the input, never the
                # tokens) — NOT torch.zeros_like(ctrl) (that's the melody/audio_ref null).
                null = cond_enc(torch.zeros_like(m_cls), torch.zeros_like(m_conf))
                ctrl = torch.cat([ctrl, null], dim=0)
        gen_clips(arm, ctrl)

    _write_run_meta(args, ckpts, manifest)
    print(f"[render done] {len(manifest['clips'])} clips", flush=True)


def _write_run_meta(args, ckpts, manifest):
    (BRACKET / "run_meta.json").write_text(json.dumps({
        "purpose": ("E3 structure-recall bracket: does metrical_position FiLM conditioning "
                    "(4-level metrical tree) give the model a usable phrase coordinate? "
                    "base (no adapter) vs real-sidecar arm vs shuffled-sidecar collapse "
                    "baseline, matched prompts+seeds, steady constructed 145 BPM grid."),
        "hypothesis": HYPOTHESIS,
        "recipe": {"ckpts": {a: str(p) for a, (p, _) in ckpts.items()},
                   "train_args": {a: ck.get("args", {}) for a, (_, ck) in ckpts.items()},
                   "prompts": PROMPTS, "seeds": SEEDS, "bpm": BPM, "cfg": CFG,
                   "steps": STEPS, "n_frames": N_FRAMES,
                   "duration_sec": round(DURATION, 3), "gain": args.gain,
                   "grid": {"subdiv_per_beat": SUBDIV_PER_BEAT,
                            "beats_per_bar": BEATS_PER_BAR,
                            "bars_per_phrase": BARS_PER_PHRASE, "coverage": 1, "conf": 1},
                   "scripts": ["eval/e3_structure_bracket.py",
                               "control/sa3_control/train.py (metrical_position mode)",
                               "control/sa3_control/conditioner.py (MetricalEncoder)"]},
        "dataset_info": {a: {"metrical_dir": ck.get("metrical_dir"),
                             "metrical_dropout": ck.get("metrical_dropout"),
                             "encoded_dir": ck.get("args", {}).get("encoded_dir")}
                         for a, (_, ck) in ckpts.items()},
        "result": {"clips": len(manifest["clips"])},
        "kim_feedback": None,
        "related": ["docs/superpowers/specs/2026-07-31-metrical-tree-pe-design.md",
                    "control/sa3_control/melody_pilot_eval.py (template harness)",
                    "eval/disintegration_metrics.py"],
    }, indent=2))


# ── analyze (CPU) ───────────────────────────────────────────────────────────────────

HALF_BEATS_PER_BEAT = 2              # SSM time base: half-beats -> off-beat lags exist
LAG_1BAR = BEATS_PER_BAR * HALF_BEATS_PER_BEAT                # 8 half-beats  (~1.655 s)
LAG_8BAR = LAG_1BAR * BARS_PER_PHRASE                         # 64 half-beats (~13.24 s)
N_FLOOR_LAGS = 16


def _halfbeat_chroma_ssm(wav_path: Path):
    """Half-beat-synchronous chroma self-similarity matrix, on the KNOWN steady 145 BPM
    grid (all three arms render at the same prompted/conditioned tempo, so a fixed grid
    beats beat-tracking for cross-arm comparability)."""
    import librosa
    y, sr = librosa.load(str(wav_path), sr=22050, mono=True)
    hop = 512
    C = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
    hb = 60.0 / BPM / HALF_BEATS_PER_BEAT                      # half-beat duration (s)
    bounds = librosa.time_to_frames(np.arange(0.0, len(y) / sr, hb), sr=sr, hop_length=hop)
    Cs = librosa.util.sync(C, bounds, aggregate=np.mean)       # (12, n_halfbeats)
    Cn = Cs / (np.linalg.norm(Cs, axis=0, keepdims=True) + 1e-9)
    return Cn.T @ Cn                                           # cosine SSM


def _lag_mean(S: np.ndarray, lag: int) -> float:
    d = np.diagonal(S, offset=lag)
    return float(d.mean()) if d.size else float("nan")


def _floor_lags(rng: np.random.Generator):
    """Random NON-METRICAL lags: odd half-beat offsets (never on a beat, so never on a
    bar/phrase multiple), sampled between ~1.5 beats and ~10 bars."""
    pool = [k for k in range(3, LAG_8BAR + 2 * LAG_1BAR) if k % 2 == 1]
    return sorted(rng.choice(pool, size=N_FLOOR_LAGS, replace=False).tolist())


def analyze(args):
    sys.path.insert(0, str(SAO / "eval"))
    from disintegration_metrics import measure, gate

    manifest = json.loads(MANIFEST.read_text())
    rng = np.random.default_rng(0)
    floor_lags = _floor_lags(rng)
    base_by_key = {(c["prompt_idx"], c["seed"]): c for c in manifest["clips"]
                   if c["model"] == "base"}

    dsp, rows = {}, []
    for c in manifest["clips"]:
        wav = BRACKET / c["model"] / f"{c['clip']}.wav"
        if not wav.exists():
            continue
        dsp[c["clip"]] = measure(wav)
    for c in manifest["clips"]:
        wav = BRACKET / c["model"] / f"{c['clip']}.wav"
        if not wav.exists():
            continue
        S = _halfbeat_chroma_ssm(wav)
        row = dict(c)
        row["sim_1bar"] = round(_lag_mean(S, LAG_1BAR), 4)
        row["sim_8bar"] = round(_lag_mean(S, LAG_8BAR), 4)
        row["sim_floor"] = round(float(np.mean([_lag_mean(S, k) for k in floor_lags])), 4)
        row["phrase_gain"] = round(row["sim_8bar"] - row["sim_floor"], 4)
        row["flatness"] = round(dsp[c["clip"]]["flatness"], 4)
        row["hf_ratio"] = round(dsp[c["clip"]]["hf"], 4)
        nb = base_by_key.get((c["prompt_idx"], c["seed"]))
        if c["model"] != "base" and nb and nb["clip"] in dsp:
            g = gate(dsp[c["clip"]], dsp[nb["clip"]])
            row["gate"] = "BLOWN:" + ",".join(g["reasons"]) if g["blown"] else "clean"
        else:
            row["gate"] = "baseline" if c["model"] == "base" else "no-base-ref"
        rows.append(row)

    summary = {}
    for m in ("base", "real", "shuffled"):
        mr = [r for r in rows if r["model"] == m]
        if not mr:
            continue
        summary[m] = {
            "n": len(mr),
            "sim_1bar": round(float(np.mean([r["sim_1bar"] for r in mr])), 4),
            "sim_8bar": round(float(np.mean([r["sim_8bar"] for r in mr])), 4),
            "sim_floor": round(float(np.mean([r["sim_floor"] for r in mr])), 4),
            "phrase_gain": round(float(np.mean([r["phrase_gain"] for r in mr])), 4),
            "flatness": round(float(np.mean([r["flatness"] for r in mr])), 4),
            "hf_ratio": round(float(np.mean([r["hf_ratio"] for r in mr])), 4),
            "gates_blown": sum(1 for r in mr if str(r["gate"]).startswith("BLOWN")),
        }

    cols = ["model", "n", "sim_1bar", "sim_8bar", "sim_floor", "phrase_gain",
            "flatness", "hf_ratio", "gates_blown"]
    print("\n=== E3 structure-recall bracket — verdict table ===")
    print(f"(lag_1bar={LAG_1BAR} half-beats ~{LAG_1BAR * 60 / BPM / 2:.2f}s, "
          f"lag_8bar={LAG_8BAR} ~{LAG_8BAR * 60 / BPM / 2:.2f}s, "
          f"floor = mean over {N_FLOOR_LAGS} odd half-beat lags {floor_lags})")
    print("\t".join(cols))
    for m, s in summary.items():
        print("\t".join(str(dict(s, model=m).get(k, "")) for k in cols))
    if {"real", "shuffled"} <= summary.keys():
        d = summary["real"]["phrase_gain"] - summary["shuffled"]["phrase_gain"]
        print(f"\n[reading] real-vs-shuffled phrase_gain delta = {d:+.4f} "
              f"(hypothesis wants > 0 with clean gates; DSP screen only — the ear is "
              f"the verdict, and per-clip spread matters: see results.json)")

    (BRACKET / "results.json").write_text(json.dumps({
        "hypothesis": HYPOTHESIS,
        "metrics_meta": {"ssm": "half-beat-synchronous chroma cosine SSM @ fixed 145 BPM",
                         "lag_1bar_halfbeats": LAG_1BAR, "lag_8bar_halfbeats": LAG_8BAR,
                         "floor_lags_halfbeats": floor_lags},
        "clips": rows,
        "summary": summary,
        "result": None,              # Kim-audited verdict slot (MANIFEST v2; ❗ until set)
        "kim_feedback": None,
    }, indent=1))
    print(f"[analyze done] {len(rows)} clips -> {BRACKET / 'results.json'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="E3 metrical structure-recall bracket "
                                             "(base vs real vs shuffled)")
    ap.add_argument("mode", nargs="?", choices=["render", "analyze"],
                    help="render (GPU, caller holds .gpu.lock) | analyze (CPU)")
    ap.add_argument("--step", type=int, default=None,
                    help="checkpoint step for BOTH arms (default: latest riffer_step*.pt)")
    ap.add_argument("--models", default="base,real,shuffled",
                    help="comma subset of base,real,shuffled")
    ap.add_argument("--gain", type=float, default=1.0, help="ControlContext gain (as trained)")
    ap.add_argument("--dry-run", action="store_true",
                    help="build + print the metrical grid, load nothing heavy, exit")
    a = ap.parse_args()
    if a.dry_run:
        dry_run()
    elif a.mode == "render":
        render(a)
    elif a.mode == "analyze":
        analyze(a)
    else:
        ap.error("need a mode (render|analyze) or --dry-run")
