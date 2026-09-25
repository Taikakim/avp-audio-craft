#!/usr/bin/env python
"""interval_cfg_render.py -- interval-CFG grid (task #26 melody angle, 2026-07-23).

HYPOTHESIS (from the P2 finding, eval/musicology/hook_pilot_cfg_axis_2026-07-22.md):
CFG's prompt-mean pull suppresses melodic commitment (mechanism M2) -- hmr falls
cfg7->cfg16 in 8/10 families. Interval-CFG = full guidance EARLY in the trajectory
(high sigma, where prompt adherence/structure is decided) but OFF late (low sigma,
where fine content commits) should keep prompt adherence while letting melody commit.
Independent field support: Zach/Stability + German on Discord
(docs/ai-research/2026-07-21-zach-stability-discord-notes.md, "cfg_interval_min",
"high early, off late is the only way to have acceptable quality at over 8 steps").

NO SAMPLER CHANGE NEEDED (discovery 2026-07-23): the DiT already gates CFG natively on
a sigma interval -- dit.py:479 `cfg_scale != 1.0 and (cfg_interval[0] <= sigma[0] <=
cfg_interval[1])`; outside the interval the step is cond-only (== cfg 1). generate()
threads `cfg_interval=(lo, hi)` through **sampler_kwargs -> common_kwargs -> every
model forward (verified sampling.py:477-503; live-verified by the explorer server
2026-07-08, WORKLOG). Intervals here are in SIGMA units (1.0 = noise, 0 = clean), the
same domain dit.py compares against; the actual on/off step split under the model's
dist_shift schedule is recorded in run_meta.json (cfg_steps_on per arm).

ARMS (per model): c7/c16 constant controls (reuse model_matrix cells where the exact
file exists), ivA cfg16@(0.5,1.0), ivB cfg16@(0.7,1.0), ivC cfg7@(0.5,1.0), and
ivD cfg16@(0.0,0.5) = INVERSE control (guidance only late; M2 predicts WORSE melody).

Grid: 3 models x 6 arms x 6 prompts x 2 seeds = 216 cells, 36 reused -> ~180 renders
of 20 s @ steps24. Resumable (skips existing wavs). GPU under the fleet mutex
(.gpu.lock, handle CONTINUITY-icfg, --pid-aware), acquired per model block and
released between blocks so co-queued agents can interleave.

Outputs: /run/media/kim/Mantu/sa3_lora_runs/interval_cfg_2026-07-23/renders/*.wav
(+ .z0.npy per standing directive) + manifest.jsonl + run_meta.json. The SAO-tree
experiment dir eval/musicology/interval_cfg_2026-07-23/ symlinks renders/ (eval audio
never lives in the SAO tree, MASTER section 4).

Run (SA3 venv):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE \
  /home/kim/Projects/SAO/stable-audio-3/.venv/bin/python eval/interval_cfg_render.py \
      [--dry-run] [--limit N] [--only-model LABEL]
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = Path("/run/media/kim/Mantu/sa3_lora_runs")
MATRIX_DIR = RUNS / "model_matrix"
OUT_ROOT = RUNS / "interval_cfg_2026-07-23"
RENDERS = OUT_ROOT / "renders"
GPU_LOCK = "/home/kim/Projects/SAO/.gpu.lock"
LOCK_HANDLE = "CONTINUITY-icfg"
FILELOCK = ROOT / "Misc/filelock.py"
SNAPSHOT = ROOT / "lumi/matrix_prompts_snapshot.json"

STEPS = 24
DURATION = 20.0

# arm -> (cfg_scale, cfg_interval-or-None). Sigma units, 1.0 = full noise.
ARMS = {
    "c7":  (7.0,  None),          # constant control (partly reused from model_matrix)
    "c16": (16.0, None),          # constant control (ditto)
    "ivA": (16.0, (0.5, 1.0)),    # full guidance early, off for sigma < 0.5
    "ivB": (16.0, (0.7, 1.0)),    # off earlier still (sigma < 0.7)
    "ivC": (7.0,  (0.5, 1.0)),    # moderate guidance, early only
    "ivD": (16.0, (0.0, 0.5)),    # INVERSE control: guidance only late -> expect WORSE
}

# kl_0 / kl_1 / kl_bracket_0 / rb_mid_3 / techno / housestyle. The brief said
# "rb_mid_0" but no such id exists in the snapshot or the matrix -- rb_mid_3 is the
# first mid-band prompt (ids are globally indexed across bands), noted in REPORT.md.
PROMPT_IDS = ["kl_0", "kl_1", "kl_bracket_0", "rb_mid_3", "techno", "housestyle_uml"]  # housestyle -> _uml 2026-09-26: misspelled trigger retired

MODELS = [
    ("base", None, "base"),
    ("fp32cmp_goa_t4096_bs4_lr1e4",
     RUNS / "fp32cmp_goa_t4096_bs4_lr1e4/epoch=4-step=6750.ckpt", "ep4"),
    ("fullft_goa_t4096",
     RUNS / "fullft_goa_t4096/epoch=7-step=10800.weights.ckpt", "ep7"),
]


def load_prompts():
    snap = json.load(open(SNAPSHOT))
    by_id = {p["id"]: p for p in snap["prompts"]}
    missing = [pid for pid in PROMPT_IDS if pid not in by_id]
    assert not missing, f"prompt ids not in snapshot: {missing}"
    return [by_id[pid] for pid in PROMPT_IDS]


def clip_name(label, tag, arm, pid, seed):
    return f"{label}__{tag}__{arm}__{pid}__s{seed}.wav"


def matrix_control_name(label, tag, cfg, pid, seed):
    # model_matrix convention (eval/model_matrix_gen.py clip_name, defaults st24/d20)
    return f"{label}__{tag}__cfg{int(cfg)}__w100__{pid}__s{seed}.wav"


def gpu_lock():
    rc = subprocess.call(["python3", str(FILELOCK), "acquire", GPU_LOCK,
                          "--handle", LOCK_HANDLE, "--pid-aware",
                          "--pid", str(os.getpid()), "--timeout", "43200"])
    if rc != 0:
        sys.exit(f"[icfg] could not acquire {GPU_LOCK} (rc={rc}) -- card busy 12h+, giving up")
    # lock-vs-VRAM teardown race (bit this run at 37/216: acquire succeeded the moment
    # the previous holder released, but its VRAM hadn't drained -> 0 bytes free, OOM).
    # Belt-and-suspenders per the fleet doctrine: after acquire, wait for measured free
    # VRAM before touching the card (same guard the head_b pilot chain uses).
    import re as _re
    for _ in range(40):  # up to ~20 min
        try:
            out = subprocess.run(["rocm-smi", "--showmeminfo", "vram"],
                                 capture_output=True, text=True, timeout=30).stdout
            used = [int(m) for m in _re.findall(r"Used Memory.*?:\s*(\d+)", out)]
            total = [int(m) for m in _re.findall(r"Total Memory.*?:\s*(\d+)", out)]
            if used and total and (total[0] - used[0]) / 1e9 > 9.0:
                return
        except Exception:
            pass
        time.sleep(30)
    gpu_unlock()
    sys.exit("[icfg] VRAM never freed (>9GiB) within 20min of lock acquire -- releasing and giving up")


def gpu_unlock():
    subprocess.call(["python3", str(FILELOCK), "release", GPU_LOCK,
                     "--handle", LOCK_HANDLE])


def load_fullft(model, ckpt_path):
    """Whole-model checkpoint over the base DiT -- FAIL LOUD on partial coverage
    (copied from eval/model_matrix_gen.py incl. the key-prefix fix, 2026-07-21)."""
    import torch as _t
    _ck = _t.load(str(ckpt_path), map_location="cpu", weights_only=False)
    _sd_raw = _ck.get("state_dict", _ck)
    _tgt = model.model.model
    _tgt_keys = set(dict(_tgt.named_parameters())) | set(dict(_tgt.named_buffers()))
    _sd = max(
        ({(k[len(_pfx):] if k.startswith(_pfx) else k): v for k, v in _sd_raw.items()}
         for _pfx in ("diffusion.model.", "model.")),
        key=lambda sd: sum(1 for k in sd if k in _tgt_keys))
    _missing, _unexpected = _tgt.load_state_dict(
        {k: v.to(next(_tgt.parameters()).dtype) for k, v in _sd.items()
         if k in dict(_tgt.named_parameters()) or k in dict(_tgt.named_buffers())},
        strict=False)
    _cov = 1 - len(_missing) / max(1, len(list(_tgt.state_dict())))
    assert _cov > 0.99, (
        f"fullft ckpt covers only {_cov:.1%} -- refusing part-loaded render "
        f"({len(_missing)} missing, e.g. {_missing[:3]})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="cap renders (smoke test)")
    ap.add_argument("--only-model", default=None)
    ap.add_argument("--no-lock", action="store_true",
                    help="skip the .gpu.lock mutex (ONLY when the caller already holds it)")
    args = ap.parse_args()

    prompts = load_prompts()
    models = [m for m in MODELS if args.only_model in (None, m[0])]

    # cell list: (label, ckpt, tag, arm, prompt, seed)
    cells = []
    for label, ckpt, tag in models:
        for prompt in prompts:
            for seed in (int(prompt["seed"]), int(prompt["seed"]) + 1):
                for arm in ARMS:
                    cells.append((label, ckpt, tag, arm, prompt, seed))
    print(f"[icfg] {len(models)} models x {len(ARMS)} arms x {len(prompts)} prompts "
          f"x 2 seeds = {len(cells)} cells")

    RENDERS.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT_ROOT / "manifest.jsonl"
    have = set()
    if manifest_path.exists():
        for ln in manifest_path.read_text().splitlines():
            try:
                have.add(json.loads(ln)["file"])
            except Exception:
                pass

    def emit(entry):
        with open(manifest_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        have.add(entry["file"])

    # Pass 1: link in reusable constant-control cells (no GPU needed).
    n_reused = 0
    todo = []
    for label, ckpt, tag, arm, prompt, seed in cells:
        cfg, interval = ARMS[arm]
        wav = RENDERS / clip_name(label, tag, arm, prompt["id"], seed)
        entry = {"model": label, "ckpt": tag, "arm": arm, "cfg": cfg,
                 "cfg_interval": list(interval) if interval else None,
                 "prompt_id": prompt["id"], "prompt_text": prompt["text"],
                 "seed": seed, "steps": STEPS, "duration": DURATION,
                 "file": wav.name}
        if wav.exists() or wav.is_symlink():
            if wav.name not in have:
                emit({**entry, "reused": wav.is_symlink()})
            continue
        if interval is None:
            src = MATRIX_DIR / matrix_control_name(label, tag, cfg, prompt["id"], seed)
            if src.exists():
                wav.symlink_to(src)
                z0src = src.with_suffix(".z0.npy")
                if z0src.exists():
                    wav.with_suffix(".z0.npy").symlink_to(z0src)
                # reuse the cached transcription too (hook_renders_midi keys on stem)
                mid_src = ROOT / "eval/hook_renders_midi" / (src.stem + ".mid")
                if mid_src.exists():
                    midi_dir = OUT_ROOT / "midi"
                    midi_dir.mkdir(exist_ok=True)
                    mid_dst = midi_dir / (wav.stem + ".mid")
                    if not mid_dst.exists():
                        mid_dst.symlink_to(mid_src)
                emit({**entry, "reused": True, "reused_from": str(src)})
                n_reused += 1
                continue
        todo.append((label, ckpt, tag, arm, prompt, seed, entry))
    print(f"[icfg] {n_reused} newly linked from model_matrix, "
          f"{len(cells) - len(todo) - n_reused} already present, {len(todo)} to render")
    if args.limit:
        todo = todo[:args.limit]
    if args.dry_run or not todo:
        for t in todo[:12]:
            print("  would render:", t[6]["file"])
        return

    import torch  # noqa: E402
    import numpy as np  # noqa: E402
    sys.path.insert(0, str(ROOT / "control"))
    from sa3_control.audio_io import save_audio          # noqa: E402
    from stable_audio_3 import StableAudioModel          # noqa: E402
    from stable_audio_3.inference.sampling import build_schedule  # noqa: E402

    # group by model so each ckpt loads once; lock per model block
    by_model = {}
    for item in todo:
        by_model.setdefault(item[0], []).append(item)

    meta_extra = {}
    for label, items in by_model.items():
        ckpt, tag = items[0][1], items[0][2]
        print(f"[icfg] waiting for GPU lock ({label}: {len(items)} renders)", flush=True)
        if not args.no_lock:
            gpu_lock()
        try:
            model = StableAudioModel.from_pretrained("medium-base", device="cuda")
            sr = model.model.sample_rate
            if ckpt is not None and label.startswith("fullft_"):
                load_fullft(model, ckpt)
            elif ckpt is not None:
                model.load_lora([str(ckpt)])
                try:
                    model.set_lora_strength(1.0)
                except Exception:
                    pass
            decode_dtype = next(model.same.parameters()).dtype
            # record the real sigma schedule + per-arm CFG-on steps, once
            if not meta_extra:
                sig = build_schedule(STEPS, dist_shift=model.model.sampling_dist_shift,
                                     effective_seq_len=int(DURATION * 44100 / 4096),
                                     device="cpu")
                sig = [round(float(s), 4) for s in sig]
                meta_extra["sigma_schedule_steps24_20s"] = sig
                meta_extra["arm_cfg_steps_on"] = {
                    a: [i for i in range(STEPS)
                        if iv is None or (iv[0] <= sig[i] <= iv[1])]
                    for a, (c, iv) in ARMS.items()}
                print("[icfg] sigma schedule:", sig, flush=True)
                for a, on in meta_extra["arm_cfg_steps_on"].items():
                    print(f"  {a}: cfg on at steps {on}", flush=True)
            print(f"[load] {label}/{tag}", flush=True)

            for _label, _ckpt, _tag, arm, prompt, seed, entry in items:
                cfg, interval = ARMS[arm]
                wav_path = RENDERS / entry["file"]
                if wav_path.exists():
                    if entry["file"] not in have:
                        emit(entry)
                    continue
                kw = {}
                if interval is not None:
                    kw["cfg_interval"] = tuple(interval)
                t0 = time.time()
                z0 = model.generate(prompt=prompt["text"], duration=DURATION,
                                    steps=STEPS, cfg_scale=float(cfg), seed=int(seed),
                                    batch_size=1, return_latents=True, **kw)
                np.save(wav_path.with_suffix(".z0.npy"),
                        z0.detach().to(torch.float16).cpu().numpy())
                with torch.no_grad():
                    audio = model.same.decode(z0.to(decode_dtype))
                audio = audio.to(torch.float32)[:, :, :int(DURATION * sr)]
                save_audio(wav_path, audio[0].cpu(), sr, normalize=True)
                emit({**entry, "reused": False, "wall_s": round(time.time() - t0, 1)})
                print(f"  [{label}/{tag} {arm} {prompt['id']} s{seed}] "
                      f"{time.time() - t0:5.1f}s", flush=True)
            del model
            torch.cuda.empty_cache()
        finally:
            if not args.no_lock:
                gpu_unlock()

    # run_meta.json (MANIFEST v2)
    meta_path = OUT_ROOT / "run_meta.json"
    meta = json.load(open(meta_path)) if meta_path.exists() else {}
    meta.update({
        "purpose": ("Interval-CFG vs melodic commitment (task #26): does full guidance "
                    "early + off late preserve prompt adherence (CLAP) while lifting "
                    "hook_melodic_ratio, per mechanism M2 (CFG prompt-mean pull "
                    "suppresses melody, hook_pilot_cfg_axis_2026-07-22.md)?"),
        "hypothesis": ("ivA/ivB (cfg16 early only) recover hmr toward cfg7 levels at "
                       "cfg16-level CLAP; ivD (inverse, guidance late only) degrades "
                       "melody further -- a directional test of M2."),
        "spec": "docs/superpowers/specs/2026-07-22-melodic-latch-film.md section 7",
        "script": "eval/interval_cfg_render.py",
        "scoring": ["eval/hook_eval_renders.py", "eval/clap_score.py",
                    "eval/disintegration_metrics.py"],
        "models": {label: {"ckpt": str(c) if c else None, "tag": t}
                   for label, c, t in MODELS},
        "training_data": {
            "fp32cmp_goa_t4096_bs4_lr1e4": "LUMI fp32-compare DoRA arm, goa corpus, T=4096, bs4, lr 1e-4 (ep4 pick)",
            "fullft_goa_t4096": "LUMI whole-1.4B full fine-tune, goa-only crops, T=4096, FusionOpt lr 1e-4 (ep7 final)",
            "base": "medium-base, no adapter"},
        "arms": {a: {"cfg": c, "cfg_interval": iv} for a, (c, iv) in ARMS.items()},
        "mechanism": ("native dit.py:479 sigma-gated CFG via generate(cfg_interval=...); "
                      "no sampler code change"),
        "steps": STEPS, "duration": DURATION,
        "prompt_note": "brief said rb_mid_0; no such id exists -- rb_mid_3 used (first mid-band prompt)",
        **meta_extra,
    })
    json.dump(meta, open(meta_path, "w"), indent=1)
    print("[icfg] done", flush=True)


if __name__ == "__main__":
    main()
