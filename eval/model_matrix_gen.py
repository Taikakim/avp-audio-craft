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


def _existing_manifest():
    """The manifest to READ for resume + prompt-sourcing. STAGING is ~/.cache (a cache dir,
    subject to cleaning) -- a missing STAGING manifest must NEVER read as 'nothing rendered'
    or a resume would re-do all ~60k clips. Fall back to the durable ~/evals_aac mirror.
    (Writes still go to MANIFEST; restore STAGING from the durable copy before a run so new
    appends land on the complete manifest -- see the length-variant spec's pre-run step.)"""
    for p in (MANIFEST,
              Path.home() / "evals_aac/model_matrix/manifest.jsonl",
              Path.home() / "evals_aac/model_matrix/manifest_live.jsonl"):
        if p.exists() and p.stat().st_size > 0:
            return p
    return MANIFEST
OVERRIDES_PATH = ROOT / "Misc/models_index_overrides.json"
MODELS_OVERRIDES = json.load(open(OVERRIDES_PATH)) if OVERRIDES_PATH.exists() else {}

CFGS = (1.0, 7.0, 16.0)
# Kim direct 2026-07-20: drop 0.6 from NEW renders (most models don't need it; speeds
# the grid up), add 2.0 (1.5 is well-handled by many models, worth seeing past it).
# Existing 0.6 cells in the manifest are NOT deleted -- they just stop growing.
STRENGTHS = (1.0, 1.5, 2.0)
STRENGTHS_LEGACY = (0.6, 1.0, 1.5)  # the old axis, kept for reference / any tooling that reads it
STEPS = 24
DURATION = 20.0

# Native-training-length audition cells (Kim ask 2026-07-20: "we should also have
# versions on the size the model is trained on" -- the standard grid above is a fixed
# 20s for every model regardless of what T it trained at, which is right for
# apples-to-apples cross-model comparison but hides how a checkpoint sounds at ITS OWN
# intended context length; the LUMI campaign alone now spans T=512..4096 (47.6s..380.4s).
# ADDITIVE, not a replacement: one extra small audition per (model,ckpt) at native T,
# not a full 108-cell re-sweep at every length (T=4096 clips cost ~8x a 20s render --
# a full native-T grid would be prohibitively expensive and isn't what was asked for).
FPS = 44100 / 4096  # = 10.7666 Hz, the canonical SA3-medium latent frame rate
NATIVE_LEN_CFG = 7.0
NATIVE_LEN_STRENGTH = 1.0


# label -> trained frames, populated from --native-frames-file (the render_jobs_*.txt
# tsv partition_render_jobs.py writes: label \t tag \t T<frames> \t ckpt). Authoritative
# over the recipe-text scrape below -- the 2026-08-03 overnight run silently skipped
# native cells for 30/37 local labels because their override recipes are dicts (or
# absent) with no 'T=' text; the jobs file had the correct T for every label all along.
NATIVE_FRAMES_MAP: dict[str, int] = {}


# Cells whose latent came back non-finite. A long render process can start emitting NaN
# partway through (GHOST-NOTE 2026-09-08: 110 of 216 cells in one pass, 108 of 110 in the
# next, while the SAME checkpoint+config rendered clean in a 24-cell process and in a direct
# generate() probe -- so it is process-lifetime state, not the weights, the length, the
# sample_size/pad clamp, or set_lora_strength; all four were ruled out by isolation tests).
#
# WHY A CHECK IS NEEDED AT ALL: a NaN latent decodes to a FULL-SCALE CONSTANT -- peak 1.0,
# RMS 1.0, i.e. maximum-volume noise. It is not truncated, not quiet, and not short, so every
# verification we had passed it: the file count was right, ffprobe reported the exact
# requested duration, and the render exited 0. It reached the listening board and was caught
# only by score_and_publish's latent-sanity gate, which inspects the cfg7/w1 subset alone --
# a NaN burst confined to other cfgs would still have shipped.
NONFINITE_CELLS: list[str] = []


def z0_is_finite(z0, where: str) -> bool:
    """True if `z0` is usable. On a non-finite latent, log loudly and return False so the
    caller SKIPS the whole cell -- no .wav, no .m4a, no manifest line. Writing nothing is
    deliberate: `existing` is keyed off the manifest, so an unwritten cell simply stays
    missing and the next resume re-renders it. Recording it instead would poison the board
    with noise AND make the resume skip it forever."""
    # torch is imported inside main() (line ~572) so --dry-run works without it -- import
    # locally rather than assume a module-level name that does not exist.
    import torch as _t

    bad = ~_t.isfinite(z0)
    n = int(bad.sum())
    if n == 0:
        return True
    NONFINITE_CELLS.append(where)
    print(f"  !! NON-FINITE LATENT -- CELL DROPPED: [{where}] {n}/{z0.numel()} elements "
          f"non-finite. Nothing written; the cell stays missing so a resume re-renders it. "
          f"If these cluster late in a long pass, split the run into smaller batches.",
          flush=True)
    return False


def native_len_seconds(label: str) -> float | None:
    """Trained context length in seconds for `label`, if known (from
    --native-frames-file first, else the recipe override's 'T=<frames>' text) --
    else None (native-length cell skipped, logged at the render site)."""
    for cand in (label, label.removesuffix("_ptm"), label.removesuffix("_ptm").removesuffix("_repr")):
        if cand in NATIVE_FRAMES_MAP:
            return round(NATIVE_FRAMES_MAP[cand] / FPS, 2)
    for suf in ("_ptm", "_repr"):
        label = label.removesuffix(suf)
    doc = MODELS_OVERRIDES.get(label, {})
    if not isinstance(doc, dict):
        return None
    # recipe may be a legacy STRING or a commentary-schema DICT (2026-07-30 THE-FINN);
    # the 'T=<frames>' text can live in either, or in recipe_legacy_str after a dict
    # upgrade preserved the original string there. Normalize all sources to one blob.
    r = doc.get("recipe")
    blob = r if isinstance(r, str) else (json.dumps(r) if isinstance(r, dict) else "")
    if doc.get("recipe_legacy_str"):
        blob += " " + doc["recipe_legacy_str"]
    m = re.search(r"T=(\d+)", blob)
    return round(int(m.group(1)) / FPS, 2) if m else None

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

# rb_bracket_0/kl_bracket_0 (Kim 2026-07-20: "these clips should exist for all models") --
# text+seed copied VERBATIM from eval/interval_schedule_bracket.py's PROMPTS, which only
# ever rendered these two for its own 2-checkpoint sweep. Those clips landed in this same
# shared manifest.jsonl, so the ids already show up as board rows -- just empty for every
# other model. Own dict (not folded into EXTRA_PROMPTS) so each keeps ITS OWN seed instead
# of collapsing onto EXTRA_SEED, matching the clips that already exist for those 2 ckpts
# (manifest_key doesn't include seed, so this doesn't create duplicate/orphaned cells --
# it just means new renders reuse the same seed as the originals).
BRACKET_PROMPTS = [
    {"id": "rb_bracket_0", "text": "2020s goa trance, melodic mood, 148 bpm", "seed": 1102008041},
    {"id": "kl_bracket_0", "text": ("This track is a high-energy Psytrance piece that blends driving "
                                     "trance rhythms with the hypnotic, acid-inflected textures typical "
                                     "of the genre."), "seed": 1000},
]

# Prompts introduced by the 2026-08-02 length-variant run (Kim). Own dict so build_prompts()
# and the extra/bracket sets stay untouched; surfaced only under --all-prompts. goa_organic =
# the new detailed 90s-goatrance description (spec 2026-08-02-eval-native-ptm-length-render-design).
NEW_PROMPTS = [
    {"id": "goa_organic", "seed": 2026, "text": (
        "This track is a high-energy psychedelic 90s goatrance piece that blends the driving pulse "
        "of classic Goa trance with organic and crisp sound of analog synthesizers. It sits at 143 "
        "BPM in a 4/4 time signature and is rooted in F minor. Instrumentation & production: The "
        "arrangement is built around a relentless four-on-the-floor kick and a thick, "
        "side-chain-compressed synth bass that anchors the low end, together with moody pads and "
        "distorted roland tb303-style acid riffs and resonant filtered saw wave legato synth lead "
        "with a rubbery portamento")},
]


def ckpt_tag(fname):
    """Label for a checkpoint file — INCLUDING its replica marker when it has one.

    ⚠ THE -vN IS NOT A DUPLICATE MARKER, IT IS A DIFFERENT MODEL (GHOST-NOTE measured this
    2026-09-03). Under the Pattern-2 DDP incident (EXPERIMENTS A4/A9/A10) the 8 srun ranks
    were independent single-GCD trainers writing collision filenames, so
    epoch=19-step=5980.ckpt and epoch=19-step=5980-v1.ckpt are separately-trained models
    (521/522 DiT tensors differ, max|delta| 0.21).

    This function used to return "ep19" for BOTH. That destroyed replica identity in the
    render FILENAME, i.e. upstream of every rating and metric: manifest.jsonl stores this
    tag rather than a path, and all 22,036 fullft/wfleet rows in clip_metrics.db carry no
    -vN marker. No path-keyed export can recover it after the fact.

    Bare filenames are UNCHANGED ("ep19"), so existing joins keep working; only a replica
    file gets the extra suffix it should always have had.
    """
    m = re.search(r"epoch=(\d+)", fname)
    if not m:
        return Path(fname).stem
    rep = re.search(r"-v(\d+)(?:\.|$)", Path(fname).stem)
    return f"ep{m.group(1)}" + (f"v{rep.group(1)}" if rep else "")


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


def prompts_from_manifest(only_ids, fallback):
    """Return [{id,text,seed}] for `only_ids`, sourcing text+seed from the EXISTING manifest —
    the exact prompt already-rendered clips used — so length/ptm variants of a prompt_id stay
    IDENTICAL to its 20s clips (the pool drifted: kl_0's pool text no longer matches the clips
    on disk, 2026-08-02). Ids absent from the manifest fall back to `fallback` (e.g. NEW_PROMPTS,
    for goa_organic). Majority (text,seed) per id wins, so pre-drift originals dominate."""
    from collections import Counter
    counts = {}
    mf = _existing_manifest()
    if mf.exists():
        for ln in mf.read_text().splitlines():
            if not ln.strip():
                continue
            try:
                e = json.loads(ln)
            except Exception:
                continue
            pid = str(e.get("prompt_id"))
            counts.setdefault(pid, Counter())[(e.get("prompt_text", ""), e.get("seed"))] += 1
    fb = {p["id"]: p for p in fallback}
    out = []
    for pid in only_ids:
        if pid in counts:
            (text, seed), _ = counts[pid].most_common(1)[0]
            out.append({"id": pid, "text": text, "seed": int(seed) if seed is not None else 0})
        elif pid in fb:
            out.append(fb[pid])
        else:
            print(f"[prompt-missing] {pid}: not in manifest, not in fallback -- skipped")
    return out


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
            if not p.exists() and fname.endswith(".ckpt") and not fname.endswith(".weights.ckpt"):
                # lumi/prune_optimizer_states.py (Kim 2026-07-19) keeps advancing through
                # the LUMI runs tree, arm by arm, deleting each non-final fat .ckpt and
                # replacing it with a slim <name>.weights.ckpt (same state_dict/lora_config,
                # loads identically -- see WORKLOG 2026-07-20). It's an ONGOING background
                # process, not a one-time event, so hand-patching the bracket manifest's
                # picks every time it advances further doesn't scale -- fall back here
                # instead, transparently, so re-pruning never needs a manifest edit again.
                wp = d / (fname[:-5] + ".weights.ckpt")
                if wp.exists():
                    p = wp
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


# label -> EMA beta from the run's own recipe. beta is NOT in the checkpoint, so it must come
# from a recipe source; anything absent here falls back to train_lora's 0.9999 default and is
# reported as "assumed default" rather than passed off as known. Populated from
# Misc/models_index_overrides.json / run_meta.json by _load_ema_betas() below.
EMA_BETAS: dict[str, float] = {}


def _load_ema_betas():
    """Scrape `--ema-beta`/`ema_beta` out of the recipe text we already keep per arm."""
    import re as _re
    for label, doc in MODELS_OVERRIDES.items():
        if not isinstance(doc, dict):
            continue
        blob = " ".join(str(doc.get(k, "")) for k in ("recipe", "recipe_legacy_str", "purpose"))
        m = _re.search(r"ema[-_ ]?beta[ =:]+([0-9.]+)", blob, _re.I)
        if m:
            try: EMA_BETAS[label] = float(m.group(1))
            except ValueError: pass


def ema_convergence(state_dict, beta=None, beta_source="assumed default"):
    """How far an EMA shadow actually travelled from its STARTING weights.

    The checkpoint records the true update count itself: `diffusion_ema.ema_step`. Use it --
    do NOT substitute `global_step`. They differ by the accumulation factor (a suomi full-FT
    read global_step 3160 but ema_step 12600, a 4x error in the wrong direction), and guessing
    from the step count is how this gets mis-reported.

    R = ema_step / halflife, halflife = ln2 / (1 - beta). R is "how many halvings of the
    initial weights have happened", so the residual starting weight is 0.5**R. CONTINUITY's
    band (2026-09-10): R = 3..10 is useful; below 3 the shadow is still substantially its own
    starting point, and for a WARM START that starting point is another model entirely.

    beta is NOT stored in the checkpoint (`hyper_parameters` is empty on ours), so it has to
    come from the run's recipe -- run_meta.json / the census -- or fall back to the 0.9999
    default, which is flagged as assumed rather than silently taken as fact.
    """
    step = state_dict.get("diffusion_ema.ema_step")
    if step is None:
        return None
    import math
    n = int(step)
    b = 0.9999 if beta is None else float(beta)
    half = math.log(2) / (1.0 - b)
    r = n / half
    return {"ema_step": n, "beta": b, "beta_source": beta_source,
            "halflives": r, "residual_init": 0.5 ** r, "converged": r >= 3.0}


def clip_name(label, ckpt, cfg, strength, pid, seed, steps=STEPS, duration=DURATION):
    # steps/duration suffixes ONLY when non-default so existing files + their resume
    # keys are byte-identical; a different steps/duration pass lands as a sibling
    # (__st48 / __dNNN), never an overwrite.
    st = f"__st{steps}" if steps != STEPS else ""
    du = f"__d{int(round(duration))}" if duration != DURATION else ""
    return f"{label}__{ckpt}__cfg{int(cfg)}__w{int(round(strength * 100)):03d}__{pid}__s{seed}{st}{du}.wav"


def manifest_key(e):
    # legacy entries predate the "steps"/"duration" fields -> default to STEPS(24)/
    # DURATION(20s), which is also what a default render produces, so resume stays
    # consistent across the schema bump.
    return (f'{e["model"]}|{e["ckpt"]}|{e["cfg"]}|{e["strength"]}|{e["prompt_id"]}|'
           f'st{e.get("steps", STEPS)}|d{e.get("duration", DURATION)}')


def load_existing_keys():
    mf = _existing_manifest()
    if not mf.exists():
        return set()
    keys = set()
    for ln in mf.read_text().splitlines():
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
    ap.add_argument("--all-prompts", action="store_true",
                     help="UNION every prompt source (rarity+pool build_prompts + EXTRA_PROMPTS + "
                          "BRACKET_PROMPTS + NEW_PROMPTS incl. goa_organic), deduped by id, so "
                          "--only-prompts can select across all of them (the length-variant 9-set). "
                          "Overrides --extra-prompts.")
    ap.add_argument("--prompts-from-manifest", action="store_true",
                     help="source the --only-prompts ids' text+seed from the EXISTING manifest (the "
                          "exact prompt already-rendered clips used) instead of the drifted pool, so "
                          "length/ptm variants stay identical to their 20s clips. Ids not in the "
                          "manifest fall back to NEW_PROMPTS (goa_organic). Requires --only-prompts.")
    ap.add_argument("--terminal-only", action="store_true",
                     help="per model label, keep ONLY its highest-epoch checkpoint (the terminal "
                          "audition point) -- for the native/ptm length-variant passes.")
    ap.add_argument("--native-grid", action="store_true",
                     help="render the native-length cell as a FULL prompt x cfg x strength grid "
                          "(vs the default single cfg7/w1 audition cell). Duration is each model's "
                          "own trained T (native_len_seconds); the active --only-cfgs/--only-strengths "
                          "bound the grid (e.g. --only-cfgs 1 --only-strengths 1.0 for the ptm pass). "
                          "Combine with --terminal-only; T>=2048 still routes to LUMI.")
    ap.add_argument("--require-file", action="store_true",
                     help="treat a cell as done only when its manifest key AND its .m4a on disk both "
                          "exist -- re-renders/re-transcodes manifest-known cells whose clip is "
                          "missing (closes the manifest-vs-playability drift, task #71).")
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
    ap.add_argument("--weights", choices=("auto","ema","online"), default="auto",
                    help="which tensor set to load from a FULL-FINETUNE checkpoint. auto (default) "
                         "= EMA when the checkpoint carries one, else online. EMA is what the run "
                         "was set up to produce, but SimpleEMA's beta=0.9999 has a ~10k-step time "
                         "constant, so short runs have an under-converged EMA still dominated by "
                         "early training -- use 'online' to render the optimizer's own weights, or "
                         "to reproduce cells rendered before 2026-09-04, when this loop always "
                         "loaded online. Ignored for LoRA/DoRA (no EMA there).")
    ap.add_argument("--pt-medium", action="store_true",
                     help="load the POST-TRAINED 'medium' (rf_denoiser / ping-pong) instead of "
                          "medium-base and suffix every label with '_ptm' -- tests base-trained "
                          "adapters on the post-trained model (Kim 2026-07-21, Discord/Dadabots/"
                          "Zach-Stability claim). Combine with --steps 8 --only-cfgs 1 for the "
                          "PT-native config; cfg>1 reportedly 'cooks' PT output.")
    ap.add_argument("--only-labels", default=None,
                     help="comma-separated model labels to render (guided subset)")
    ap.add_argument("--only-ckpts", default=None,
                     help="comma-separated ckpt tags (e.g. ep3,ep5) to render (guided subset)")
    ap.add_argument("--only-prompts", default=None,
                     help="comma-separated prompt ids to render (guided subset)")
    ap.add_argument("--only-cfgs", default=None,
                     help="comma-separated cfg values to render (guided subset, e.g. 7)")
    ap.add_argument("--only-strengths", default=None,
                     help="comma-separated strength values to render, OVERRIDING the normal "
                          "adapter sweep (STRENGTHS) and skipping the base-row cross-strength "
                          "mirror -- for a fixed-strength pass like --pt-medium, where the PT "
                          "model glitches away from one known-good (cfg,strength). fullft/base "
                          "rows are already forced to (1.0,); intersecting with a strength they "
                          "don't have renders nothing for that row, not an error.")
    ap.add_argument("--duration-seconds", type=float, default=None,
                     help="override the STANDARD grid's render duration (default 20s), in "
                          "seconds -- e.g. 95.11=T1024, 190.22=T2048 -- for extrapolation tests "
                          "(rendering a model beyond the context length it was trained at). "
                          "Frames (duration*FPS) must be a multiple of 256. T>=2048 frames is "
                          "BLOCKED from local rendering -- same VRAM/display-crash precedent as "
                          "native cells (MASTER.md sec 5) -- set SA3_ALLOW_LONG_NATIVE=1 to "
                          "override, or route to LUMI instead. Lands as a __dNNN manifest "
                          "cell (distinct key from the default-duration grid, never overwrites "
                          "it), landing on the SAME rows in dora_table.html/model_matrix.html.")
    ap.add_argument("--native-frames-file", type=str, default=None,
                     help="tsv from partition_render_jobs.py (label \\t tag \\t T<frames> \\t ckpt) "
                          "giving each label's trained frames -- authoritative source for the "
                          "native-cell length, overriding the recipe-override 'T=' text scrape "
                          "(which is absent for the dora/sa3-goa families and silently skipped "
                          "their native cells on the 2026-08-03 run).")
    ap.add_argument("--limit", type=int, default=None,
                     help="cap number of prompts after filtering (smoke tests)")
    ap.add_argument("--time-budget-hours", type=float, default=None,
                     help="stop cleanly after this many wall-clock hours (finishes current clip, "
                          "flushes manifest; resumable via the skip-if-exists cells)")
    args = ap.parse_args()
    _load_ema_betas()   # recipe-derived betas; absent -> reported as assumed default

    if args.native_frames_file:
        for ln in Path(args.native_frames_file).read_text().splitlines():
            parts = ln.strip().split("\t")
            if len(parts) >= 3 and parts[2].startswith("T") and parts[2][1:].isdigit():
                NATIVE_FRAMES_MAP[parts[0]] = int(parts[2][1:])
        print(f"[model_matrix] native frames map: {len(NATIVE_FRAMES_MAP)} labels "
              f"from {args.native_frames_file}")

    steps = args.steps
    save_latents = not args.no_save_latents
    only_labels = set(s for s in args.only_labels.split(",") if s) if args.only_labels else None
    only_ckpts = set(s for s in args.only_ckpts.split(",") if s) if args.only_ckpts else None
    cfgs = tuple(float(s) for s in args.only_cfgs.split(",") if s) if args.only_cfgs else CFGS
    only_strengths = (tuple(float(s) for s in args.only_strengths.split(",") if s)
                      if args.only_strengths else None)
    # NATIVE_LEN_CFG (7.0) is the general-purpose native-cell cfg, but it's HARDCODED
    # into every native-length render regardless of --only-cfgs -- meaning a --pt-medium
    # run's native cell would render at cfg7 even though cfg1 is the only PT-native
    # config (cfg>1 "cooks" the PT-medium base). Caught 2026-07-24 before it produced a
    # glitchy native cell; override to 1.0 specifically for --pt-medium runs.
    native_cfg = 1.0 if args.pt_medium else NATIVE_LEN_CFG

    # explicit duration override for the STANDARD grid (Kim 2026-07-24: T1024/T2048
    # extrapolation tests on T512-trained arms). duration=... alone would NOT actually
    # change the generated latent window -- sample_size does that (duration only sets
    # seconds_total + the final trim) -- same bug CONTINUITY caught on LUMI's native-cell
    # path (2026-07-22, all "native" cells silently rendered at the 120s default window
    # regardless of filename). Mirrors the native-cell fix: explicit sample_size=frames*4096.
    duration = DURATION
    duration_sample_size = None
    if args.duration_seconds is not None:
        dur_frames = int(round(args.duration_seconds * FPS))
        if dur_frames % 256 != 0:
            raise SystemExit(f"--duration-seconds {args.duration_seconds} -> {dur_frames} "
                             f"frames, must be a multiple of 256 (e.g. 47.55=T512, "
                             f"95.11=T1024, 190.22=T2048)")
        if dur_frames >= 2048 and os.environ.get("SA3_ALLOW_LONG_NATIVE") != "1":
            raise SystemExit(f"[model_matrix] --duration-seconds {args.duration_seconds}s -> "
                             f"{dur_frames} frames >= 2048: BLOCKED from local rendering -- "
                             f"same VRAM/display-crash precedent as native cells (MASTER.md "
                             f"sec 5). Set SA3_ALLOW_LONG_NATIVE=1 to override, or route to LUMI.")
        duration = args.duration_seconds
        duration_sample_size = dur_frames * 4096

    if args.prompts_from_manifest:
        if not args.only_prompts:
            raise SystemExit("--prompts-from-manifest requires --only-prompts <id,...>")
        want_ids = [s for s in args.only_prompts.split(",") if s]
        prompts = prompts_from_manifest(want_ids, NEW_PROMPTS)
    elif args.all_prompts:
        # union of every source, deduped by id (first occurrence wins) so --only-prompts can
        # select the length-variant 9-set across sources that are otherwise mutually exclusive.
        merged, seen_pid = [], set()
        for src in (build_prompts(args.n_per_band, args.n_kimlong),
                    [{"id": pid, "text": t, "seed": EXTRA_SEED} for pid, t in EXTRA_PROMPTS.items()],
                    BRACKET_PROMPTS, NEW_PROMPTS):
            for p in src:
                if p["id"] not in seen_pid:
                    merged.append(p); seen_pid.add(p["id"])
        prompts = merged
    elif args.extra_prompts:
        prompts = [{"id": pid, "text": text, "seed": EXTRA_SEED} for pid, text in EXTRA_PROMPTS.items()]
        prompts += BRACKET_PROMPTS
    else:
        prompts = build_prompts(args.n_per_band, args.n_kimlong)
    if args.only_prompts:
        want = set(s for s in args.only_prompts.split(",") if s)
        prompts = [p for p in prompts if p["id"] in want]
    if args.limit is not None:
        prompts = prompts[:args.limit]
    jobs = build_jobs(args.only, args.avp_only, base_full=args.base_full,
                      only_labels=only_labels, only_ckpts=only_ckpts)
    if args.pt_medium:
        # distinct labels => distinct page rows, so PT-medium cells sit NEXT TO the
        # medium-base rows of the same adapter instead of overwriting their cells
        jobs = [(f"{label}_ptm", ckpt_path, tag) for label, ckpt_path, tag in jobs]
    if args.terminal_only:
        # per label, keep only the highest-epoch checkpoint (the terminal audition point).
        # tag epoch = trailing integer of the tag ("ep15" -> 15); tags without one (e.g.
        # "base") sort as -1 and are kept as their label's sole job.
        def _ep(tag):
            m = re.search(r"(\d+)$", tag)
            return int(m.group(1)) if m else -1
        best = {}
        for j in jobs:
            lbl = j[0]
            if lbl not in best or _ep(j[2]) > _ep(best[lbl][2]):
                best[lbl] = j
        jobs = list(best.values())
    n_cells = 0
    for label, ckpt_path, _tag in jobs:
        _sw = (1.0,) if (ckpt_path is None or label.startswith("fullft_")) else STRENGTHS
        if only_strengths is not None:
            _sw = tuple(w for w in _sw if w in only_strengths)
        n_cells += len(prompts) * len(cfgs) * len(_sw)
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
        if only_strengths is not None:
            strengths_to_render = tuple(w for w in strengths_to_render if w in only_strengths)
        # skip the whole (model,ckpt) load if every cell is already done
        need_any = False
        for prompt in prompts:
            for cfg in cfgs:
                for w in strengths_to_render:
                    key = f'{label}|{tag}|{cfg}|{w}|{prompt["id"]}|st{steps}|d{duration}'
                    if key not in existing:
                        need_any = True
        # the skip-all key set above covers STANDARD cells only — a label whose standard
        # grid is complete would skip its NATIVE cell forever (bit the 6 fullft T<2048
        # labels after the 2026-07-22 native quarantine). Mirror the native block's key.
        if not need_any:
            nd = native_len_seconds(label)
            if (nd is not None and nd * FPS >= 2048
                    and os.environ.get("SA3_ALLOW_LONG_NATIVE") != "1"):
                nd = None
            if nd is not None and prompts:
                if args.native_grid:
                    for pr in prompts:
                        for c in cfgs:
                            for w in strengths_to_render:
                                if f'{label}|{tag}|{c}|{w}|{pr["id"]}|st{steps}|d{nd}' not in existing:
                                    need_any = True
                else:
                    np_chk = next((p for p in prompts if p["id"].startswith("kl_")), prompts[0])
                    nw_chk = NATIVE_LEN_STRENGTH if (ckpt_path and not is_fullft) else 1.0
                    nkey = f'{label}|{tag}|{native_cfg}|{nw_chk}|{np_chk["id"]}|st{steps}|d{nd}'
                    if nkey not in existing:
                        need_any = True
        if not need_any:
            print(f"[skip-all] {label}/{tag}")
            continue

        model = StableAudioModel.from_pretrained(
            "medium" if args.pt_medium else "medium-base", device="cuda")
        sr = model.model.sample_rate
        _wset = None
        if ckpt_path and is_fullft:
            # whole-model checkpoint: load the full state dict over the base DiT.
            # FAIL LOUD on partial coverage — a fullft ckpt silently part-loading
            # onto base weights would fake a result (W's guard, 2026-07-18).
            import torch as _t
            _ck = _t.load(str(ckpt_path), map_location="cpu", weights_only=False)
            _sd_raw = _ck.get("state_dict", _ck)
            _tgt = model.model.model  # the ConditionedDiffusionModelWrapper's DiT side
            _tgt_keys = set(dict(_tgt.named_parameters())) | set(dict(_tgt.named_buffers()))
            # real LUMI full-finetune checkpoints prefix DiT params "diffusion.model.model.X"
            # (the target module itself expects a leading "model." -> strip "diffusion.model."
            # to land on "model.X"); the bare "model." this was originally written against
            # never matches those checkpoints and silently 0%-covers -- caught 2026-07-21 when
            # a retry loop that only checked for OOM mislabeled 4 straight AssertionErrors as
            # "succeeded". Try both prefixes, keep whichever actually matches the target.
            # WEIGHT-SET CHOICE (GHOST-NOTE 2026-09-04). A full-FT checkpoint trained with
            # EMA carries BOTH sets: "diffusion.model.*" (online — where the optimizer is)
            # and "diffusion_ema.ema_model.*" (the smoothed average). Generation is supposed
            # to use the EMA set — stable-audio-3/CLAUDE.md has carried that as an open TODO
            # in the render path since 2026-08-03. Until now this loop stripped only
            # "diffusion.model." and so silently rendered the ONLINE set for every
            # EMA-carrying checkpoint (18 of 19 unrendered full-FT arms carry one), while the
            # >99% coverage assert passed happily because the online set fills the model 100%.
            #
            # NOT unconditionally better, and that is why --weights exists: SimpleEMA's default
            # beta=0.9999 has a ~10,000-step time constant, so on a 3,000-step run the EMA is
            # still ~74% its own starting point and is dominated by early training. Prefer EMA
            # where it exists (the run asked for it), but make the choice explicit and RECORD
            # it per clip so no cell is ever ambiguous about which tensors produced it.
            _has_ema = any(k.startswith("diffusion_ema.ema_model.") for k in _sd_raw)
            _want = args.weights
            _use_ema = _has_ema if _want == "auto" else (_want == "ema")
            if _use_ema and not _has_ema:
                raise SystemExit(f"--weights ema but {ckpt_path} carries no EMA tensors")
            _prefixes = (("diffusion_ema.ema_model.",) if _use_ema
                         else ("diffusion.model.", "model."))
            _sd = max(
                ({(k[len(_pfx):] if k.startswith(_pfx) else k): v for k, v in _sd_raw.items()}
                 for _pfx in _prefixes),
                key=lambda sd: sum(1 for k in sd if k in _tgt_keys))
            _wset = "ema" if _use_ema else "online"
            print(f"[weights] {label}/{tag}: {_wset}"
                  + ("" if _has_ema else " (no EMA in ckpt)"), flush=True)
            # WARN when the shadow we are about to render never left its starting point.
            # Silent is how this cost us the suomi full-FTs and both AVP sweeps.
            _emac = ema_convergence(_sd_raw, beta=EMA_BETAS.get(label))
            if _emac:
                _src = _emac["beta_source"]
                _msg = (f"[ema] {label}/{tag}: {_emac['ema_step']} EMA updates, "
                        f"beta {_emac['beta']} ({_src}) -> {_emac['halflives']:.2f} half-lives, "
                        f"shadow is still {_emac['residual_init']:.0%} its STARTING weights")
                if _use_ema and not _emac["converged"]:
                    print("  !! " + _msg, flush=True)
                    print("  !! UNCONVERGED EMA (want >=3 half-lives). You are rendering mostly "
                          "the run's starting point, not what it learned. For a WARM START that "
                          "starting point is ANOTHER MODEL. Re-run with --weights online to hear "
                          "the trained weights.", flush=True)
                else:
                    print("  " + _msg, flush=True)
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
                    key = f'{label}|{tag}|{cfg}|{w}|{prompt["id"]}|st{steps}|d{duration}'
                    wav_name = clip_name(label, tag, cfg, w, prompt["id"], prompt["seed"], steps,
                                         duration=duration)
                    m4a_name = wav_name.replace(".wav", ".m4a")
                    if key not in existing or (args.require_file and not (RENDER_DIR / m4a_name).exists()):
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
                            z0 = model.generate(prompt=prompt["text"], duration=duration, steps=steps,
                                                cfg_scale=float(cfg), seed=int(prompt["seed"]), batch_size=1,
                                                return_latents=True, sample_size=duration_sample_size)
                            if not z0_is_finite(z0, f"{label}/{tag} cfg{cfg} w{w} "
                                                    f"{prompt['id']} st{steps}"):
                                continue
                            if save_latents:
                                # compact fp16 z0 next to the wav (base + DoRA share decoder weights)
                                np.save(wav_path.with_suffix(".z0.npy"),
                                        z0.detach().to(torch.float16).cpu().numpy())
                            with torch.no_grad():
                                audio = model.same.decode(z0.to(decode_dtype))
                            # truncate to the requested duration (the model would have, pre-decode),
                            # then save_audio peak-normalizes -> matches the old internal-decode path.
                            audio = audio.to(torch.float32)[:, :, :int(duration * sr)]
                            save_audio(wav_path, audio[0].cpu(), sr, normalize=True)
                            print(f"  [{label}/{tag} cfg{cfg} w{w} {prompt['id']} st{steps}] {time.time() - t0:5.1f}s", flush=True)
                        m4a_path = RENDER_DIR / m4a_name
                        if not m4a_path.exists():
                            transcode(wav_path, m4a_path)
                        append_manifest({"model": label, "ckpt": tag, "weights": _wset, "cfg": cfg, "strength": w,
                                         "prompt_id": prompt["id"], "prompt_text": prompt["text"],
                                         "seed": prompt["seed"], "steps": steps, "file": m4a_name})
                        existing.add(key)
                    if base_m4a_name is None:
                        base_m4a_name = m4a_name
                if ckpt_path is None and only_strengths is None and base_m4a_name is not None:
                    # base_m4a_name is None only if the single base render was DROPPED for a
                    # non-finite latent -- mirroring then would write manifest lines pointing at
                    # a file that does not exist. Skip; the resume re-renders the real cell.
                    # base: strength n/a -- mirror the one render across the other strength
                    # cells so the grid lights up without 3x-redundant compute. Skipped under
                    # --only-strengths: the caller asked for an exact strength set (e.g. the
                    # PT-medium cfg7/w1-only pass) and synthetic mirror cells would misrepresent
                    # coverage at strengths that were never actually requested.
                    for w in STRENGTHS:
                        if w in strengths_to_render:
                            continue
                        key = f'{label}|{tag}|{cfg}|{w}|{prompt["id"]}|st{steps}|d{duration}'
                        if key in existing:
                            continue
                        append_manifest({"model": label, "ckpt": tag, "weights": _wset, "cfg": cfg, "strength": w,
                                         "prompt_id": prompt["id"], "prompt_text": prompt["text"],
                                         "seed": prompt["seed"], "steps": steps, "file": base_m4a_name})
                        existing.add(key)

        # native-training-length audition cell (additive; see NATIVE_LEN_* above) --
        # one prompt, one setting, at whatever T this checkpoint actually trained on.
        # T>=2048 natives are BANNED locally (Kim direct 2026-07-21: a fullft native
        # render's long-sequence attention VRAM starved the compositor -> display
        # crash, forced logout). Those cells render on LUMI (64GB headless GCDs) via
        # lumi/render_native_cells.py + W's ingest. SA3_ALLOW_LONG_NATIVE=1 overrides.
        native_dur = native_len_seconds(label)
        if native_dur is None:
            # no-silent-caps: this skip cost the 2026-08-03 run 30/37 labels' native
            # cells with zero log evidence. Say what was dropped and how to fix it.
            print(f"[native-skip] {label}/{tag} native T UNKNOWN (no --native-frames-file "
                  f"entry, no 'T=' in recipe override) -> native cell(s) not rendered")
        if (native_dur is not None and native_dur * FPS >= 2048
                and os.environ.get("SA3_ALLOW_LONG_NATIVE") != "1"):
            print(f"[native-skip] {label}/{tag} T~{native_dur*FPS:.0f} >= 2048 -> LUMI lane")
            native_dur = None
        if native_dur is not None and prompts:
            native_frames = int(round(native_dur * FPS))
            assert native_frames % 256 == 0, (label, native_frames)
            # Default: ONE audition cell (native_cfg/w1, one prompt). --native-grid: the FULL
            # prompt x cfg x strength grid at this model's trained T (bounded by --only-cfgs/
            # --only-strengths; e.g. cfg1/w1 for the ptm pass). native_cfg's cfg7->cfg1 pt_medium
            # override applies to the single-cell default; the grid uses each loop's own cfg.
            if args.native_grid:
                native_cells = [(pr, c, w) for pr in prompts for c in cfgs for w in strengths_to_render]
            else:
                np0 = next((p for p in prompts if p["id"].startswith("kl_")), prompts[0])
                nw0 = NATIVE_LEN_STRENGTH if (ckpt_path and not is_fullft) else 1.0
                native_cells = [(np0, native_cfg, nw0)]
            for np_, ncfg, nw in native_cells:
                if over_budget():
                    stopped = True
                    break
                nkey = f'{label}|{tag}|{ncfg}|{nw}|{np_["id"]}|st{steps}|d{native_dur}'
                nwav_name = clip_name(label, tag, ncfg, nw, np_["id"], np_["seed"],
                                      steps, duration=native_dur)
                nm4a_path = RENDER_DIR / nwav_name.replace(".wav", ".m4a")
                if nkey in existing and not (args.require_file and not nm4a_path.exists()):
                    continue
                if ckpt_path and not is_fullft:
                    try:
                        model.set_lora_strength(nw)
                    except Exception:
                        pass
                nwav_path = RENDER_DIR / nwav_name
                if not nwav_path.exists():
                    t0 = time.time()
                    # sample_size = the model's TRAINED window, not the 120s default:
                    # generate()'s `duration` only sets seconds_total + trim; without
                    # sample_size every "native" cell actually ran at a 1292-frame
                    # (120s) context (caught on LUMI 2026-07-22, same bug both places).
                    z0 = model.generate(prompt=np_["text"], duration=native_dur, steps=steps,
                                        cfg_scale=float(ncfg), seed=int(np_["seed"]),
                                        batch_size=1, return_latents=True,
                                        sample_size=native_frames * 4096)
                    assert z0.shape[-1] == native_frames, (z0.shape, native_frames)
                    if not z0_is_finite(z0, f"{label}/{tag} NATIVE {native_dur}s cfg{ncfg} "
                                            f"w{nw} {np_['id']} st{steps}"):
                        continue
                    if save_latents:
                        np.save(nwav_path.with_suffix(".z0.npy"),
                               z0.detach().to(torch.float16).cpu().numpy())
                    with torch.no_grad():
                        naudio = model.same.decode(z0.to(decode_dtype))
                    naudio = naudio.to(torch.float32)[:, :, :int(native_dur * sr)]
                    save_audio(nwav_path, naudio[0].cpu(), sr, normalize=True)
                    print(f"  [{label}/{tag} NATIVE {native_dur}s cfg{ncfg} "
                         f"w{nw} {np_['id']} st{steps}] {time.time() - t0:5.1f}s", flush=True)
                if not nm4a_path.exists():
                    transcode(nwav_path, nm4a_path)
                append_manifest({"model": label, "ckpt": tag, "weights": _wset, "cfg": ncfg, "strength": nw,
                                 "prompt_id": np_["id"], "prompt_text": np_["text"], "seed": np_["seed"],
                                 "steps": steps, "duration": native_dur, "duration_mode": "native",
                                 "file": nm4a_path.name})
                existing.add(nkey)

        del model
        torch.cuda.empty_cache()
        if stopped:
            break
    if stopped:
        print(f"[model_matrix] STOPPED on time budget ({args.time_budget_hours}h) -- resumable, "
              f"re-run the same command to continue", flush=True)
    if NONFINITE_CELLS:
        print(f"[model_matrix] {len(NONFINITE_CELLS)} CELL(S) DROPPED for non-finite latents "
              f"-- they were NOT written and are NOT on the board; re-run to fill them, "
              f"preferably in smaller batches:", flush=True)
        for w in NONFINITE_CELLS:
            print(f"    dropped: {w}", flush=True)
    print("[model_matrix] done", flush=True)
    if NONFINITE_CELLS:
        # exit non-zero so a wrapper/cron notices; the artifacts already written are valid.
        sys.exit(3)


if __name__ == "__main__":
    main()
