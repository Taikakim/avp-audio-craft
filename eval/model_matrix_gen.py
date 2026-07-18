#!/usr/bin/env python
"""model_matrix_gen.py -- renders the overnight model matrix (Kim 2026-07-11 brief):
every DoRA/LoRA model (checkpoint-bracketed via CONTINUITY's rarity_bracket_manifest.json)
x checkpoint x cfg{1,7,16} x DoRA-strength{0.6,1.0,1.5} x a prompt subsample (rarity-band
stratified sample + kimlong-style detailed prompts from eval/kimlong_pool.json). Appends
one manifest.jsonl line per clip in WINTERMUTE's build_model_matrix.py schema
(~/.cache/evals_aac/model_matrix/manifest.jsonl) so the GUI self-populates as clips land --
rerun Misc/build_model_matrix.py + reship any time to pick up new coverage.

Duration/steps match rarity_gen_set (20s, steps24) -- Kim confirmed longer clips don't
degrade quality, no need to shorten for the bigger matrix.

base model: strength is n/a, so only ONE render per (cfg, prompt) happens; the manifest
gets 3 identical-file entries (one per strength value) so the GUI grid still lights up
without burning compute on 3x-redundant audio.

Resumable: skips wav generation AND manifest append when a (model,ckpt,cfg,strength,
prompt_id) cell is already in the manifest -- safe to stop/restart across GPU-card
turns with the fleet.

Run (SA3 venv):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE .venv/bin/python eval/model_matrix_gen.py \
      [--only LABEL] [--dry-run]
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
import argparse, json, random, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = Path("/run/media/kim/Mantu/sa3_lora_runs")
BRACKET = ROOT / "eval/rarity_bracket_manifest.json"
KIMLONG_POOL = ROOT / "eval/kimlong_pool.json"
RARITY_CLIP_INDEX = RUNS / "rarity_gen_set/clip_index.json"

STAGING = Path.home() / ".cache/evals_aac/model_matrix"
MANIFEST = STAGING / "manifest.jsonl"
RENDER_DIR = RUNS / "model_matrix"

CFGS = (1.0, 7.0, 16.0)
STRENGTHS = (0.6, 1.0, 1.5)
STEPS = 24
DURATION = 20.0

# additive prompt extension for the AVP-only models (Kim direct via CONTINUITY,
# 2026-07-11 18:55) -- canonical texts pulled from Misc/build_evals.py's
# AVP_PROMPT_TEXT dict (trig2) and eval/mp_crossmodel_render.py's PROMPTS dict
# (kimlong), not re-invented. "ecletic" in Kim's ask corrected to "eclectic".
EXTRA_PROMPTS = {
    "kimlong": ("bittersweet synth music with influences from goa trance and 80s retro "
                "videogame music, dorian scale, BPM 138, steady 90s trance beat, punchy "
                "bright kick, 16th octave bass runs, tight snares every second beat"),
    "trig2": "aavepyora",
    "techno": "techno music",
    "housestyle": "bittersweet eclectic house, aavepyora style",
}
EXTRA_SEED = 1234  # matches the established avp-board seed convention


def ckpt_tag(fname):
    m = re.search(r"epoch=(\d+)", fname)
    return f"ep{m.group(1)}" if m else Path(fname).stem


def build_prompts(n_per_band=3, n_kimlong=3):
    """rarity-band stratified sample (n_per_band/band) + kimlong-style detailed prompts.
    Defaults are the SAFE first-pass size (9h budget / real per-clip timing, see
    model_matrix_gen's DM in AGENT_DIALOGUE 2026-07-11) -- bump via CLI for a deeper
    second pass once pass 1's actual throughput is known (resumable, only adds cells)."""
    specs = [v for v in json.load(open(RARITY_CLIP_INDEX)).values() if v.get("source") == "base"]
    by_band = {}
    for s in specs:
        by_band.setdefault(s["band"], []).append(s)
    rnd = random.Random(20260711)
    chosen = []
    for band, items in sorted(by_band.items()):
        chosen += rnd.sample(items, min(n_per_band, len(items)))
    prompts = [{"id": f"rb_{s['band']}_{i}", "text": s["prompt"], "seed": s["seed"]}
               for i, s in enumerate(chosen)]
    if KIMLONG_POOL.exists() and n_kimlong > 0:
        pool = json.load(open(KIMLONG_POOL))
        rnd.shuffle(pool)
        for i, p in enumerate(pool[:n_kimlong]):
            prompts.append({"id": f"kl_{i}", "text": p["prompt"], "seed": 1000 + i})
    return prompts


def build_jobs(only=None, avp_only=False, base_full=False, only_labels=None, only_ckpts=None):
    """(model_label, ckpt_path_or_None, ckpt_tag) list, from CONTINUITY's bracket manifest.

    base_full: render ONLY the base model (medium-base, no adapter) -- completes the base
    row across the full prompt list x cfg axis so it's comparable to every DoRA row.
    only_labels/only_ckpts: comma-set subsets (guided budget-capped passes).
    Both 'models' (flat <label>/<ckpt>.ckpt) and 'legacy_goa_dora_nested' (picks are paths
    relative to RUNS/<label>/, incl. one doubled-nesting run -- verified on-disk 2026-07-11,
    RUNS/label/pick reproduces the doubled path correctly since the pick string itself
    already carries the extra nesting component) resolve the same way: RUNS/label/pick.

    avp_only: the AVP-dataset own-music models (Kim's 'avp8ep/dora256_avp/arm-G/H family'
    scope, 2026-07-11) -- any label containing 'avp' as a substring, EXCLUDING the mixed
    avp+goa 'everything' runs (those train on both corpora, not avp-only) and the legacy
    goa-side nested runs (never matched anyway, no 'avp' in those labels)."""
    if base_full:
        return [("base", None, "base")]
    bracket = json.load(open(BRACKET))
    jobs = [] if avp_only else [("base", None, "base")]
    # legacy section FIRST: it carries the HoF must-include x20b3ygb ep3 pick, worth
    # surfacing early rather than queued behind all 19 'models' entries
    sections = {k: v for k, v in bracket.get("legacy_goa_dora_nested", {}).items()
                if not k.startswith("_")}
    sections.update(bracket["models"])
    for label, spec in sections.items():
        if only and label != only:
            continue
        if avp_only and ("avp" not in label.lower() or "everything" in label.lower()):
            continue
        # optional per-model "root" override for runs saved outside the usual
        # Mantu sa3_lora_runs tree (e.g. dora128_47s_cont_from5, trained straight
        # to local NVMe -- Mantu wasn't the save target, so RUNS/label/pick would
        # 404 without this)
        d = Path(spec["root"]) / label if "root" in spec else RUNS / label
        for fname in spec["picks"]:
            p = d / fname
            if not p.exists():
                print(f"[skip-missing] {label}/{fname}")
                continue
            jobs.append((label, p, ckpt_tag(fname)))
    if only:
        jobs = [j for j in jobs if j[0] == only]
    if only_labels:
        jobs = [j for j in jobs if j[0] in only_labels]
    if only_ckpts:
        jobs = [j for j in jobs if j[2] in only_ckpts]
    return jobs


def clip_name(label, ckpt, cfg, strength, pid, seed, steps=STEPS):
    # steps suffix ONLY when non-default (24) so existing 24-step files + their resume
    # keys are byte-identical; a 48/64-step pass lands as a sibling (__st48) not an overwrite.
    st = f"__st{steps}" if steps != STEPS else ""
    return f"{label}__{ckpt}__cfg{int(cfg)}__w{int(round(strength * 100)):03d}__{pid}__s{seed}{st}.wav"


def manifest_key(e):
    # legacy entries predate the "steps" field -> default to STEPS(24), which is also
    # what a default render produces, so resume stays consistent across the schema bump.
    return f'{e["model"]}|{e["ckpt"]}|{e["cfg"]}|{e["strength"]}|{e["prompt_id"]}|st{e.get("steps", STEPS)}'


def load_existing_keys():
    if not MANIFEST.exists():
        return set()
    keys = set()
    for ln in MANIFEST.read_text().splitlines():
        try:
            keys.add(manifest_key(json.loads(ln)))
        except Exception:
            pass
    return keys


def append_manifest(entry):
    STAGING.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST, "a") as f:
        f.write(json.dumps(entry) + "\n")


def transcode(wav_path, m4a_path):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path),
                    "-c:a", "aac", "-b:a", "192k", str(m4a_path)], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="restrict to one model label")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--n-per-band", type=int, default=3, help="rarity prompts per band (x3 bands)")
    ap.add_argument("--n-kimlong", type=int, default=3, help="kimlong-style detailed prompts")
    ap.add_argument("--extra-prompts", action="store_true",
                     help="use EXTRA_PROMPTS (kimlong/trig2/techno/housestyle) instead of the "
                          "rarity-band+pool sample -- additive extension pass")
    ap.add_argument("--avp-only", action="store_true",
                     help="restrict jobs to AVP-dataset own-music models (excludes 'everything' "
                          "mixed-corpus runs and base)")
    ap.add_argument("--steps", type=int, default=STEPS,
                     help=f"diffusion steps (default {STEPS}); non-default lands as __st<N> siblings")
    ap.add_argument("--no-save-latents", action="store_true",
                     help="do NOT save the pre-decode z0 latent (.z0.npy) per clip (default: save)")
    ap.add_argument("--base-full", action="store_true",
                     help="render ONLY medium-base across the full prompt list x cfg axis "
                          "(completes the base row; strength n/a)")
    ap.add_argument("--only-labels", default=None,
                     help="comma-separated model labels to render (guided subset)")
    ap.add_argument("--only-ckpts", default=None,
                     help="comma-separated ckpt tags (e.g. ep3,ep5) to render (guided subset)")
    ap.add_argument("--only-prompts", default=None,
                     help="comma-separated prompt ids to render (guided subset)")
    ap.add_argument("--only-cfgs", default=None,
                     help="comma-separated cfg values to render (guided subset, e.g. 7)")
    ap.add_argument("--limit", type=int, default=None,
                     help="cap number of prompts after filtering (smoke tests)")
    ap.add_argument("--time-budget-hours", type=float, default=None,
                     help="stop cleanly after this many wall-clock hours (finishes current clip, "
                          "flushes manifest; resumable via the skip-if-exists cells)")
    args = ap.parse_args()

    steps = args.steps
    save_latents = not args.no_save_latents
    only_labels = set(s for s in args.only_labels.split(",") if s) if args.only_labels else None
    only_ckpts = set(s for s in args.only_ckpts.split(",") if s) if args.only_ckpts else None
    cfgs = tuple(float(s) for s in args.only_cfgs.split(",") if s) if args.only_cfgs else CFGS

    if args.extra_prompts:
        prompts = [{"id": pid, "text": text, "seed": EXTRA_SEED} for pid, text in EXTRA_PROMPTS.items()]
    else:
        prompts = build_prompts(args.n_per_band, args.n_kimlong)
    if args.only_prompts:
        want = set(s for s in args.only_prompts.split(",") if s)
        prompts = [p for p in prompts if p["id"] in want]
    if args.limit is not None:
        prompts = prompts[:args.limit]
    jobs = build_jobs(args.only, args.avp_only, base_full=args.base_full,
                      only_labels=only_labels, only_ckpts=only_ckpts)
    n_cells = 0
    for label, ckpt_path, _tag in jobs:
        n_cells += len(prompts) * len(cfgs) * (1 if ckpt_path is None else len(STRENGTHS))
    print(f"[model_matrix] {len(jobs)} (model,ckpt) jobs x {len(prompts)} prompts -> "
          f"{n_cells} manifest cells ({n_cells - sum(len(prompts) * len(cfgs) * 2 for l, c, t in jobs if c is None)} "
          f"actual renders, base cells triple-counted for the grid)")
    print(f"[model_matrix] steps={steps} save_latents={save_latents} base_full={args.base_full}"
          f"{' time_budget=%sh' % args.time_budget_hours if args.time_budget_hours else ''}")
    if args.dry_run:
        for label, ckpt_path, tag in jobs:
            print(" ", label, tag, ckpt_path)
        for p in prompts:
            print("  prompt", p["id"], "->", p["text"][:80])
        return

    existing = load_existing_keys()
    print(f"[model_matrix] {len(existing)} cells already in manifest, resuming")

    import torch  # noqa: E402
    import numpy as np  # noqa: E402
    sys.path.insert(0, str(ROOT / "control"))
    from sa3_control.audio_io import save_audio          # noqa: E402
    from stable_audio_3 import StableAudioModel           # noqa: E402

    RENDER_DIR.mkdir(parents=True, exist_ok=True)

    run_t0 = time.time()
    budget_s = args.time_budget_hours * 3600 if args.time_budget_hours else None

    def over_budget():
        return budget_s is not None and (time.time() - run_t0) > budget_s

    stopped = False
    for label, ckpt_path, tag in jobs:
        if over_budget():
            stopped = True
            break
        is_fullft = label.startswith("fullft_")
        # fullft arms are whole-model fine-tunes: no adapter, no strength sweep —
        # the w axis collapses to 1.0 (W's loader recommendation 2026-07-18)
        strengths_to_render = (1.0,) if (ckpt_path is None or is_fullft) else STRENGTHS
        # skip the whole (model,ckpt) load if every cell is already done
        need_any = False
        for prompt in prompts:
            for cfg in cfgs:
                for w in strengths_to_render:
                    key = f'{label}|{tag}|{cfg}|{w}|{prompt["id"]}|st{steps}'
                    if key not in existing:
                        need_any = True
        if not need_any:
            print(f"[skip-all] {label}/{tag}")
            continue

        model = StableAudioModel.from_pretrained("medium-base", device="cuda")
        sr = model.model.sample_rate
        if ckpt_path and is_fullft:
            # whole-model checkpoint: load the full state dict over the base DiT.
            # FAIL LOUD on partial coverage — a fullft ckpt silently part-loading
            # onto base weights would fake a result (W's guard, 2026-07-18).
            import torch as _t
            _ck = _t.load(str(ckpt_path), map_location="cpu", weights_only=False)
            _sd = _ck.get("state_dict", _ck)
            _sd = { (k[len("model."):] if k.startswith("model.") else k): v
                    for k, v in _sd.items() }
            _tgt = model.model.model  # the ConditionedDiffusionModelWrapper's DiT side
            _missing, _unexpected = _tgt.load_state_dict(
                { k: v.to(next(_tgt.parameters()).dtype) for k, v in _sd.items()
                  if k in dict(_tgt.named_parameters()) or k in dict(_tgt.named_buffers()) },
                strict=False)
            _cov = 1 - len(_missing) / max(1, len(list(_tgt.state_dict())))
            assert _cov > 0.99, (
                f"fullft ckpt covers only {_cov:.1%} of the model — refusing to "
                f"render a part-loaded model ({len(_missing)} missing keys, e.g. {_missing[:3]})")
            del _ck, _sd
        elif ckpt_path:
            model.load_lora([str(ckpt_path)])
        # STANDING DIRECTIVE: decode the pre-decode latent z0 ourselves through the pretransform
        # (aliased model.same). LoRA never touches pretransform, so base + DoRA decode through
        # identical decoder weights. decode_dtype = the pretransform's own param dtype.
        decode_dtype = next(model.same.parameters()).dtype
        print(f"[load] {label}/{tag}", flush=True)

        for prompt in prompts:
            if over_budget():
                stopped = True
                break
            for cfg in cfgs:
                if over_budget():
                    stopped = True
                    break
                base_m4a_name = None
                for w in strengths_to_render:
                    key = f'{label}|{tag}|{cfg}|{w}|{prompt["id"]}|st{steps}'
                    wav_name = clip_name(label, tag, cfg, w, prompt["id"], prompt["seed"], steps)
                    m4a_name = wav_name.replace(".wav", ".m4a")
                    if key not in existing:
                        if ckpt_path:
                            try:
                                model.set_lora_strength(w)
                            except Exception:
                                pass
                        wav_path = RENDER_DIR / wav_name
                        if not wav_path.exists():
                            t0 = time.time()
                            # return_latents=True -> the pre-decode z0 (B,C,T); this path SKIPS
                            # the model's internal peak-normalize + truncation, so we do both here.
                            z0 = model.generate(prompt=prompt["text"], duration=DURATION, steps=steps,
                                                cfg_scale=float(cfg), seed=int(prompt["seed"]), batch_size=1,
                                                return_latents=True)
                            if save_latents:
                                # compact fp16 z0 next to the wav (base + DoRA share decoder weights)
                                np.save(wav_path.with_suffix(".z0.npy"),
                                        z0.detach().to(torch.float16).cpu().numpy())
                            with torch.no_grad():
                                audio = model.same.decode(z0.to(decode_dtype))
                            # truncate to the requested duration (the model would have, pre-decode),
                            # then save_audio peak-normalizes -> matches the old internal-decode path.
                            audio = audio.to(torch.float32)[:, :, :int(DURATION * sr)]
                            save_audio(wav_path, audio[0].cpu(), sr, normalize=True)
                            print(f"  [{label}/{tag} cfg{cfg} w{w} {prompt['id']} st{steps}] {time.time() - t0:5.1f}s", flush=True)
                        m4a_path = RENDER_DIR / m4a_name
                        if not m4a_path.exists():
                            transcode(wav_path, m4a_path)
                        append_manifest({"model": label, "ckpt": tag, "cfg": cfg, "strength": w,
                                         "prompt_id": prompt["id"], "prompt_text": prompt["text"],
                                         "seed": prompt["seed"], "steps": steps, "file": m4a_name})
                        existing.add(key)
                    if base_m4a_name is None:
                        base_m4a_name = m4a_name
                if ckpt_path is None:
                    # base: strength n/a -- mirror the one render across the other strength
                    # cells so the grid lights up without 3x-redundant compute
                    for w in STRENGTHS:
                        if w in strengths_to_render:
                            continue
                        key = f'{label}|{tag}|{cfg}|{w}|{prompt["id"]}|st{steps}'
                        if key in existing:
                            continue
                        append_manifest({"model": label, "ckpt": tag, "cfg": cfg, "strength": w,
                                         "prompt_id": prompt["id"], "prompt_text": prompt["text"],
                                         "seed": prompt["seed"], "steps": steps, "file": base_m4a_name})
                        existing.add(key)
        del model
        torch.cuda.empty_cache()
        if stopped:
            break
    if stopped:
        print(f"[model_matrix] STOPPED on time budget ({args.time_budget_hours}h) -- resumable, "
              f"re-run the same command to continue", flush=True)
    print("[model_matrix] done", flush=True)


if __name__ == "__main__":
    main()
