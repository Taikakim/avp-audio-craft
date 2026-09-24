#!/usr/bin/env python3
"""
build_clap_hyperparam_table.py -- join the full CLAP degeneration scan with clip_metrics.db
and the per-checkpoint training recipes, parse every training hyperparameter into its own
column, and run a first-pass quantitative analysis (metric correlation matrix + per-parameter
marginal effects + hyperparam->metric correlations). (WINTERMUTE 2026-07-22, Kim's request:
"csv table ... with ranks, batch size, frame length, lr ... along with CE, zero crossing and
all our other metrics, for each DoRA ... full qualitative analysis of how each parameter
affects the whole".)

Sources (all local, read-only):
  eval/clap_degen_model_matrix.csv  -- per-cell CLAP (matched/margin/rank/beats_far)
  eval/clip_metrics.db              -- per-cell ce/pq/cu/pc + DSP (zcr/flatness/flux/hf_ratio/...)
  Misc/models_index_overrides.json  -- per-model recipe strings (real hyperparams THE-FINN
                                       extracted from each checkpoint 2026-07-12) = ground truth

Hyperparam precedence: recipe string (authoritative) > label-name parse (fallback). `_repr`
symlinks resolve to their parent run's recipe; `_ptm` = the same adapter applied to the
POST-TRAINED medium (base_target=ptm). Relative LRs (lr0.5x/1x/3x) resolve against the 2e-4 base.

Outputs:
  eval/clap_full_table.csv       -- per-cell, every hyperparam + every metric (the table Kim asked for)
  eval/clap_dora_aggregate.csv   -- per (model,ckpt): hyperparams + mean/median of each metric
  + prints the analysis tables (correlation matrix, marginal effects) to stdout.
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/home/kim/Projects/SAO")
CLAP = ROOT / "eval/clap_degen_model_matrix.csv"
DB = ROOT / "eval/clip_metrics.db"
OV = ROOT / "Misc/models_index_overrides.json"
STATS_DIR = ROOT / "checkpoint-stats"  # optimizer-velocity library (checkpoint_trajectory_stats.py)
LR_BASE = 2e-4  # the "1x" reference (recipe: lr1x -> 0.0002, lr3x -> 0.0006)
FPS = 44100 / 4096  # latent frame rate 10.7666 Hz -> duration = T / FPS

# T(latent frames) -> seconds, for recipes that quote seconds not frames
SEC_TO_T = {23.78: 256, 47.6: 512, 47.56: 512, 95.1: 1024, 190.2: 2048, 380.4: 4096}


def _num(s):
    try:
        return float(s)
    except Exception:
        return np.nan


def _recipe_to_text(recipe):
    """Flatten a recipe into one lowercased text blob the regex parser below can read,
    regardless of which schema produced it: a bare legacy string, THE-FINN's mechanical
    extractor dict (lora_config.rank/alpha, optimizer.lr/weight_decay, epoch/global_step --
    Misc/extract_recipes.py, 2026-07-30), or the commentary-spec dict (flat descriptive
    strings under base_model/method/rank_alpha/optimizer/... -- docs/experiment-commentary-
    spec.md). Both dict shapes coexist in models_index_overrides.json now; this is the single
    place that reconciles them so parse_recipe's regexes never see a dict directly (the
    AttributeError this replaces: 'dict' object has no attribute 'lower', GHOST-NOTE 2026-07-30
    while rebuilding the aggregate after the fp32frames/fp32cmp commentary backfill)."""
    if isinstance(recipe, str):
        return recipe
    if not isinstance(recipe, dict):
        return ""
    parts = []
    lc = recipe.get("lora_config")
    if isinstance(lc, dict):
        if lc.get("rank") is not None:
            parts.append(f"rank {lc['rank']}")
        if lc.get("alpha") is not None:
            parts.append(f"alpha {lc['alpha']}")
    opt = recipe.get("optimizer")
    if isinstance(opt, dict):
        if opt.get("lr") is not None:
            parts.append(f"lr {opt['lr']}")
        parts.append("fusionopt" if "beta_p" in opt or "mu" in opt or "gamma_min" in opt else "")
    ep, gs = recipe.get("epoch"), recipe.get("global_step")
    if ep is not None and gs is not None:
        parts.append(f"epoch {ep} / step {gs}")
    # everything else (method/precision/context_len/optimizer-as-string/rank_alpha-as-string/
    # kind/provenance) -- just fold every string leaf in, recursively, so the existing regexes
    # still get a shot at whatever free text is there (e.g. my adamw entries' "rank 128, alpha
    # 128 ... " already reads as a normal sentence the regexes below already handle).
    def leaves(v):
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                leaves(x)
        elif isinstance(v, list):
            for x in v:
                leaves(x)
    leaves(recipe)
    return " ".join(p for p in parts if p)


# ── SCRIPT-DERIVED PARAMS (2026-08-21, Kim: "we should have all of the training parameters for
# every run in one script or another: SAO/lumi") ─────────────────────────────────────────────
# parse_recipe below reconstructs hyperparameters by REGEX OVER THE MODEL NAME plus a free-text
# recipe string, so it only ever knew what someone happened to encode in a filename. Measured
# gaps that caused: optimizer missing on 88% of models, batch 74%, lr 49%, rank 37%. Worse than
# missing, some fields were SILENTLY DEFAULTED -- precision fell through to "bf16" when unknown,
# so "I don't know" and "it is bf16" were indistinguishable, and a controlled bf16-vs-fp32
# comparison run against this column was comparing fp32 against a bucket that mostly meant
# UNKNOWN. lumi/run_params_extracted.json carries the values read out of the sbatch scripts that
# actually launched the runs, with file:line provenance. Those win; the regexes are the fallback.
_EXTRACTED = {}
_EXTRACT_PATH = Path(__file__).resolve().parents[1] / "lumi" / "run_params_extracted.json"
if _EXTRACT_PATH.is_file():
    try:
        _raw = json.loads(_EXTRACT_PATH.read_text())
        for _k, _v in _raw.items():
            _base = _k.split("#")[0]              # collision suffixes: keep the first, see below
            _EXTRACTED.setdefault(_base, _v)
    except Exception as _e:
        print(f"[hyper] WARNING: could not read {_EXTRACT_PATH}: {_e}")

# Fields the scripts state directly. Anything not listed stays with parse_recipe.
_SCRIPT_FIELDS = ("rank", "alpha", "lr", "batch", "frames_T", "precision", "optimizer",
                  "dataset", "epochs", "weight_decay", "grad_clip_mode", "caption_probs",
                  "adapter_type", "ddp_world_size", "accumulate_grad_batches", "use_ema")


def script_params(label):
    """Params read from the launching sbatch, for `label` or the run it derives from.

    _ptm / _repr are RENDER-TIME variants of the same trained weights, so they inherit their
    parent's training params -- but NOT base_target, which is exactly what distinguishes them.
    """
    for cand in (label, label.replace("_repr", ""), label.replace("_ptm", ""),
                 label.replace("_repr_ptm", "").replace("_ptm", "").replace("_repr", "")):
        if cand in _EXTRACTED:
            return _EXTRACTED[cand]
    return {}


def parse_recipe(recipe, label):
    """Return a dict of structured hyperparams. recipe (authoritative) first, label fallback."""
    r = _recipe_to_text(recipe).lower()
    lab = label.lower()
    d = {}

    # arch family
    if "full fine-tune" in r or "full-finetune" in r or "unfrozen" in r or lab.startswith("fullft"):
        d["arch"] = "fullft"
    elif lab in ("base", "base_ptm") or (recipe and "no adapter" in r):
        d["arch"] = "base"
    else:
        d["arch"] = "dora"

    # rank / alpha  (recipe: "rank 128 alpha 128" OR "rank128 alpha128" -- 2026-09-23, the
    # ModularOptimizer recipes write it with no space; name: doraN / rN)
    m = re.search(r"rank\s*(\d+)", r) or re.search(r"\br(\d+)\b", r)
    d["rank"] = int(m.group(1)) if m else (int(re.search(r"dora(\d+)", lab).group(1)) if re.search(r"dora(\d+)", lab)
                                           else (int(re.search(r"[_-]r(\d+)", lab).group(1)) if re.search(r"[_-]r(\d+)", lab) else np.nan))
    m = re.search(r"alpha\s*(\d+)", r) or re.search(r"α(\d+)", r)
    d["alpha"] = int(m.group(1)) if m else np.nan
    d["alpha_over_rank"] = (d["alpha"] / d["rank"]) if (d.get("alpha") and d.get("rank")) else np.nan

    # precision
    # NO DEFAULT. The old final `else "bf16"` made unknown indistinguishable from bf16 on 226
    # of 293 models, and any analysis keyed on this column silently inherited that guess.
    if "fp32" in r or "32-true" in r or "fp32" in lab:
        d["precision"] = "fp32"
    elif "bf16" in r or "bf16" in lab:
        d["precision"] = "bf16"
    else:
        d["precision"] = np.nan

    # frame length T
    T = np.nan
    m = re.search(r"t=(\d+)", r) or re.search(r"[_-]t(\d+)", lab) or re.search(r"[_-]f(\d+)", lab)
    if m:
        T = int(m.group(1))
    else:
        ms = re.search(r"(\d+\.?\d*)\s*s\b", r)  # "47.6s"
        if ms:
            T = SEC_TO_T.get(round(float(ms.group(1)), 2)) or SEC_TO_T.get(round(float(ms.group(1)), 1))
        elif "47s" in lab:
            T = 512
    d["frames_T"] = T
    d["duration_s"] = round(T / FPS, 1) if T and not np.isnan(T) else np.nan

    # batch
    m = re.search(r"batch (\d+)", r) or re.search(r"bs(\d+)", lab) or re.search(r"[_-]b(\d+)\b", lab)
    d["batch"] = int(m.group(1)) if m else np.nan

    # lr  (absolute in recipe, relative in some labels)
    lr = np.nan
    m = re.search(r"lr (\d[\d.e+-]*)", r)
    if m:
        lr = _num(m.group(1))
    else:
        mrel = re.search(r"lr(\d\.?\d*)x", lab)
        if mrel:
            lr = float(mrel.group(1)) * LR_BASE
        else:
            mn = re.search(r"lr(\d)e(\d)", lab)  # lr1e4 -> 1e-4
            if mn:
                lr = float(mn.group(1)) * 10 ** (-int(mn.group(2)))
            elif re.search(r"(\d)xlr", lab):
                lr = float(re.search(r"(\d)xlr", lab).group(1)) * LR_BASE
    d["lr"] = lr

    # optimizer
    d["optimizer"] = ("modular" if ("modular" in r or "modular" in lab)
                       else "fusionopt" if ("fusion" in r or "fusion" in lab)
                       else "adamw" if ("adamw" in r or "adamw" in lab) else np.nan)

    # dataset + augmentation + base target
    # 2026-09-23 (Kim direct: "does not support the 300 track dataset"): this used to check
    # ONLY the label, unlike every other field here ("recipe authoritative, label fallback"
    # per the docstring) -- the ModularOptimizer ladder's labels carry no dataset hint at all
    # (e.g. 'modular_sfswap_20260921__step100'), the corpus is named ONLY in the recipe prose
    # ("canonical 300 subset"), and there was no case for it regardless -- three hardcoded
    # datasets (avp/goa/mixed) with no catch-all. 'subset300' matches docs/data.md's
    # `latents_sa3_subset300` / `latents_sa3_lora300` naming for the 300-track LoRA corpus.
    d["dataset"] = ("avp" if ("avp" in lab or "avp" in r)
                     else "goa" if ("goa" in lab or "goa" in r)
                     else "mixed" if ("everything" in lab or "everything" in r)
                     else "subset300" if (re.search(r"\b300\b", lab) or re.search(r"\b300\b", r)
                                           or "subset300" in lab or "subset300" in r
                                           or "lora300" in lab or "lora300" in r)
                     else np.nan)
    ma = re.search(r"aug(\d+)", lab)
    d["aug"] = int(ma.group(1)) if ma else (0 if "aug" not in lab else np.nan)
    d["base_target"] = "ptm" if (lab.endswith("_ptm") or "post-trained" in r) else "base"

    # training steps: the recipe records "epoch M/step S (this ckpt)" -> steps/epoch = S/M,
    # then steps(ckpt) = steps_per_epoch × that ckpt's epoch (computed per-row in main).
    mse = re.search(r"epoch (\d+)\s*/\s*step (\d+)", r)
    d["steps_per_epoch"] = (int(mse.group(2)) / int(mse.group(1))) if (mse and int(mse.group(1)) > 0) else np.nan
    return d


def resolve_recipe(model, ov):
    """Recipe string for a model, resolving _repr symlinks and _ptm to the parent run."""
    if model in ov and ov[model].get("recipe"):
        return ov[model]["recipe"]
    for suf in ("_repr", "_ptm"):
        if model.endswith(suf) and model[: -len(suf)] in ov:
            return ov[model[: -len(suf)]].get("recipe", "")
    return ""


def main():
    ov = json.loads(OV.read_text())
    clap = pd.read_csv(CLAP)
    clap["ckpt"] = clap["ckpt"].astype(str)

    # clip_metrics (read-only; G may be writing concurrently)
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    met = pd.read_sql_query(
        "SELECT path, dur, rms, crest, zcr, onset_p95, centroid, flatness, flux, hf_ratio, bpm, ce, pq, cu, pc, "
        "n_bad_jumps "
        "FROM metrics WHERE path LIKE '%/model_matrix/%'", con)
    con.close()
    # A cell is ONE logical clip regardless of container. Meter rows may key as .wav
    # (lossless Mantu source, Kim 2026-07-27 "run the metrics on the wav versions" — no AAC
    # artifacts in flatness/hf_ratio/centroid) OR .m4a (staged). Different metric FAMILIES can
    # live on different container rows: the CPU-DSP pass now meters wav, while Audiobox
    # (ce/pq/cu/pc) keys to the staged m4a. So COALESCE per stem, not a whole-row pick — sort so
    # the wav row is last, then groupby.last() (which SKIPS NaN) takes the wav value for every
    # column the wav row has, and falls back to the m4a value where wav is null (e.g. Audiobox
    # ce that only exists on the m4a row). A naive drop_duplicates(keep=wav-row) would silently
    # drop those Audiobox scores.
    met["file"] = met["path"].str.split("/model_matrix/").str[-1]
    met["stem"] = met["file"].str.replace(r"\.(wav|m4a|mp3|flac|ogg)$", "", regex=True)
    met = (met.drop(columns=["path"])
              .sort_values("file")                 # 'X.m4a' < 'X.wav' → wav LAST → wav wins per col
              .drop(columns=["file"])
              .groupby("stem", as_index=False).last())
    clap["stem"] = clap["file"].str.replace(r"\.(wav|m4a|mp3|flac|ogg)$", "", regex=True)

    df = clap.merge(met, on="stem", how="left").drop(columns=["stem"])

    # per-model hyperparams
    hp = {}
    _from_script = 0
    for m in df["model"].unique():
        d = parse_recipe(resolve_recipe(m, ov), m)
        sp = script_params(m)
        if sp:
            _from_script += 1
            for f in _SCRIPT_FIELDS:
                if f in sp and sp[f] not in (None, ""):
                    key = {"epochs": "epoch_total"}.get(f, f)
                    d[key] = sp[f]
            # effective batch: per-rank batch x DDP world size x grad accumulation. The scripts
            # record batch PER RANK; several runs are 8- or 16-GCD, so a batch comparison that
            # ignores this is wrong by that factor -- which is how a batch analysis on this table
            # produced "no effect" from data that never held effective batch constant.
            b, w, a = sp.get("batch"), sp.get("ddp_world_size") or 1, sp.get("accumulate_grad_batches") or 1
            if b:
                d["effective_batch"] = float(b) * float(w) * float(a)
            d["alpha_over_rank"] = (d["alpha"] / d["rank"]) if (d.get("alpha") and d.get("rank")) else d.get("alpha_over_rank", np.nan)
            d["params_source"] = "sbatch"
        else:
            d["params_source"] = "name-regex"
        # Kim 2026-08-20: every run is FusionOpt unless the name says adamw. Validated 84/84
        # against the rows that recorded it. Applied HERE, after extraction, and marked as
        # imputed so it is never mistaken for something a script stated.
        if not isinstance(d.get("optimizer"), str) or not d.get("optimizer"):
            d["optimizer"] = "adamw" if "adamw" in m.lower() else "fusionopt"
            d["optimizer_source"] = "imputed-from-name"
        else:
            d["optimizer_source"] = d.get("params_source")
        hp[m] = d
    print(f"[hyper] params from sbatch scripts: {_from_script}/{len(hp)} models; "
          f"{len(hp)-_from_script} fall back to name-regex")
    hpdf = pd.DataFrame(hp).T.reset_index().rename(columns={"index": "model"})
    df = df.merge(hpdf, on="model", how="left")

    # per-cell epoch from ckpt
    df["epoch"] = df["ckpt"].str.extract(r"ep(\d+)").astype(float)
    df["steps"] = (df["steps_per_epoch"].astype(float) * df["epoch"]).round()

    # train_N = training-set size (# latent crops). Anchored to the known encoded_dir counts
    # where the label maps; else estimated from steps_per_epoch × batch≈4 (DoRA default). The
    # small ones (aug10=320, originals=288) are the overfit-risk runs Kim flagged.
    DIR_N = {"aug10": 320, "everything": 6111, "originals": 288, "summamutikka": 78, "aavepyora": 194}

    def train_n(model, spe):
        m = str(model).lower()
        for k, n in DIR_N.items():
            if k in m:
                return n
        if "goa" in m or "longctx" in m:
            return 5401                                  # latents_sa3 (goa corpus)
        if any(k in m for k in ("fp32cmp_avp", "bf16cmp_avp", "fullft_avp")):
            return 2393                                  # latents_avp (full avp crops)
        if spe == spe and spe:                           # variant/unknown -> steps/epoch × batch≈4
            return int(round(spe * 4))
        return None

    df["train_N"] = [train_n(m, s) for m, s in zip(df["model"], df["steps_per_epoch"])]
    df["is_repr"] = df["model"].str.endswith("_repr")

    # tidy column order
    hp_cols = ["arch", "rank", "alpha", "alpha_over_rank", "precision", "frames_T", "duration_s",
               "batch", "effective_batch", "lr", "optimizer", "dataset", "aug", "base_target",
               "epoch", "steps", "train_N",
               # New columns, all swept axes the table never carried (2026-08-21). weight_decay in
               # particular routes into FusionOpt's spectral_wd and takes 0.0/0.01/0.03/0.1 across
               # real runs -- it was invisible to every analysis while being one of the levers most
               # suspected of driving late-training drift.
               "weight_decay", "grad_clip_mode", "caption_probs", "adapter_type",
               "ddp_world_size", "accumulate_grad_batches", "use_ema", "epoch_total",
               # provenance: did these numbers come from the launching script, or from guessing at
               # the model name? An analysis should be able to filter on this.
               "params_source", "optimizer_source"]
    ctrl_cols = ["cfg", "strength"]
    metric_cols = ["clap_matched", "clap_margin_far", "retrieval_rank", "beats_all_far",
                   "ce", "pq", "cu", "pc", "zcr", "flatness", "flux", "hf_ratio", "bpm",
                   "onset_p95", "centroid", "crest", "rms", "dur"]
    keep = (["model", "ckpt", "prompt_id", "is_repr", "file"] + hp_cols + ctrl_cols
            + [c for c in metric_cols if c in df] + [c for c in ("n_bad_jumps",) if c in df])
    out = df[keep].copy()
    out.to_csv(ROOT / "eval/clap_full_table.csv", index=False)
    print(f"[table] wrote clap_full_table.csv  ({len(out)} cells, {len(keep)} cols)")

    # per (model,ckpt) aggregate: hyperparams + mean of metrics (exclude _repr dupes).
    #
    # DEFAULT vs ALL SCORES (Kim 2026-08-15, dora_table.html: "many models are dragged down by
    # their w2, cfg1 etc scores unfairly"). This used to mean every rendered cfg x strength x
    # prompt cell, unfiltered -- a model's displayed score was diluted by its off-operating-point
    # renders (cfg1, cfg16, w2, ...) exactly as reported. cfg7/w1 is the real operating point for
    # every family except the post-trained `_ptm` rows, which only ever render cfg1/w1 (PT-native;
    # see the cfg1-only-by-design note in build_dora_table_page.py). So the DEFAULT columns
    # (unprefixed, e.g. "clap_matched") are now the cfg7/w1 (or ptm: cfg1/w1) mean, and the
    # unfiltered mean survives alongside as "<metric>_all" for the page's "all scores" toggle.
    # A model with genuinely no cfg7/w1 (or ptm cfg1/w1) cells -- e.g. a family that only ever
    # rendered cfg1 -- falls back to its all-cells mean rather than going blank, flagged via
    # default_is_fallback so the page can mark it instead of silently passing it off as the same
    # thing.
    agg_metrics = {c: "mean" for c in metric_cols if c in df}
    base = out[~out["is_repr"]]
    group_keys = ["model", "ckpt"] + hp_cols

    grp_all = base.groupby(group_keys, dropna=False)
    agg_all = (grp_all.agg({**agg_metrics, "prompt_id": "count"})
               .rename(columns={"prompt_id": "n_cells_all", **{c: f"{c}_all" for c in agg_metrics}})
               .reset_index())

    is_ptm_row = base["base_target"] == "ptm"
    dflt_mask = ((~is_ptm_row) & (base["cfg"] == 7) & (base["strength"] == 1)) | \
                (is_ptm_row & (base["cfg"] == 1) & (base["strength"] == 1))
    grp_dflt = base[dflt_mask].groupby(group_keys, dropna=False)
    agg_dflt = (grp_dflt.agg({**agg_metrics, "prompt_id": "count"})
                .rename(columns={"prompt_id": "n_cells_default"}).reset_index())

    aggd = agg_all.merge(agg_dflt, on=group_keys, how="left")
    aggd["n_cells_default"] = aggd["n_cells_default"].fillna(0).astype(int)
    aggd["default_is_fallback"] = aggd["n_cells_default"] == 0
    for c in agg_metrics:
        aggd[c] = aggd[c].where(aggd["n_cells_default"] > 0, aggd[f"{c}_all"])
    aggd = aggd.rename(columns={"n_cells_all": "n_cells"})

    # ---- BAD-SAMPLE COUNT (Kim 2026-09-22, corrected 2026-09-23) ------------------
    # "count them from cfg7 clips only, and cfg1 for ptm clips" -- the SAME operating-point
    # split as dflt_mask above (cfg7/w1 for normal rows, cfg1/w1 for _ptm rows -- medium's
    # post-trained config), not an OR-across-both-cfgs pool. The first cut of this counted
    # cfg IN (1,7) for every row, which double-pools a base row's off-operating-point cfg1
    # sweep cell together with its real cfg7 operating point. n_bad_jumps comes from
    # corruption_scan_to_db.py -- computed ONCE there, this is just a column read + a sum,
    # never a re-scan. A model with none of these cells gets NaN (honest -- matches
    # n_cells_default's fallback pattern), not a false zero.
    if "n_bad_jumps" in base:
        # AUDIT-THE-METER (MASTER.md): a group with zero SCANNED cells must report NaN, not 0 --
        # "0 bad samples" has to mean "scanned and clean", never "never scanned". n_bad_jumps is
        # only populated for cells corruption_scan_to_db.py has actually touched; every other
        # existing row is unscanned, and a naive fillna(0)>0 would report those as a
        # confirmed-clean 0 -- a false negative, not an absence of evidence.
        grp_cfg17 = base[dflt_mask].groupby(group_keys, dropna=False)
        agg_cfg17 = (grp_cfg17.agg(bad_samples_cfg17_w1=("n_bad_jumps", lambda s: (s > 0).sum()),
                                    n_scanned_cfg17_w1=("n_bad_jumps", "count"),
                                    n_cells_cfg17_w1=("n_bad_jumps", "size"))
                     .reset_index())
        agg_cfg17["bad_samples_cfg17_w1"] = agg_cfg17["bad_samples_cfg17_w1"].where(
            agg_cfg17["n_scanned_cfg17_w1"] > 0, np.nan)
        aggd = aggd.merge(agg_cfg17, on=group_keys, how="left")

    # ---- OPTIMIZER VELOCITY (Kim 2026-09-22) --------------------------------------
    # Reads checkpoint_trajectory_stats.py's standing-practice library (SAO/checkpoint-stats/,
    # MASTER Section 4) -- computed ONCE per run from the weights themselves (no audio
    # involved), keyed by exact trajectory label or (for a "<run>__stepN" one-arm-per-
    # checkpoint naming, e.g. the modular_sfswap_2026-09-21 ladder) the label with its
    # __stepN/__epN suffix stripped, then matched to THIS row's own step via `ckpt`.
    # Absent for the vast majority of existing rows -- most runs only kept a terminal
    # checkpoint locally, and a trajectory needs at least two -- so NaN here means "not
    # computable from what's on disk", not "zero movement".
    _bracket_models = None

    def _step_from_bracket(model, ckpt):
        """Fallback when the short ckpt TAG has no step number -- model_matrix_gen.py
        shortens 'epoch=166-step=1500.ckpt' to just 'ep166' for the tag, silently dropping
        the step (2026-09-22, caught on the modular_sfswap ladder: 'ep166'/'ep277' tags have
        no digit sequence a step=?(\\d+) regex can find). The real filename survives in
        rarity_bracket_manifest.json's picks list for the same label -- reuse it rather than
        going velocity-blind on every epoch-tagged pick."""
        nonlocal _bracket_models
        if _bracket_models is None:
            try:
                _bracket_models = json.loads((ROOT / "eval/rarity_bracket_manifest.json").read_text())["models"]
            except Exception:
                _bracket_models = {}
        for pick in _bracket_models.get(model, {}).get("picks", []):
            # replicate model_matrix_gen.py::ckpt_tag() exactly -- 'epoch=166-...' -> 'ep166',
            # a bare filename -> its own stem -- so this compares against the SAME tag the
            # manifest/aggregate actually carries, not a guess at the naming convention.
            em = re.search(r"epoch=(\d+)", pick)
            tag = f"ep{em.group(1)}" if em else Path(pick).stem
            if tag == ckpt:
                m = re.search(r"step=?(\d+)", pick)
                if m:
                    return int(m.group(1))
        return None

    def _velocity_for(model, ckpt):
        step_m = re.search(r"step=?(\d+)", str(ckpt))
        step = int(step_m.group(1)) if step_m else _step_from_bracket(model, ckpt)
        if step is None:
            return np.nan
        for cand in dict.fromkeys([model, re.split(r"__(?:step|ep)\d", model)[0]]):
            f = STATS_DIR / f"{cand}_trajectory.json"
            if f.exists():
                try:
                    traj = json.loads(f.read_text())
                except Exception:
                    continue
                for r in traj.get("rows", []):
                    if r.get("step") == step:
                        return r.get("d_from_prev")
        return np.nan

    if STATS_DIR.is_dir():
        aggd["opt_velocity"] = [_velocity_for(m, c) for m, c in zip(aggd["model"], aggd["ckpt"])]

    # ---- MODEL DATE (Kim 2026-09-23: "models per date is the useful one ... also for the DoRA
    # rows page") -- earliest staged-clip mtime per (model,ckpt) row, epoch seconds. Same signal
    # as model_matrix.html's "models by date" (Misc/build_model_matrix.py), computed independently
    # here since this is a different page reading a different aggregate.
    _stage_mm = Path.home() / "evals_aac" / "model_matrix"

    def _mtime_for(fname):
        try:
            return (_stage_mm / fname).stat().st_mtime
        except OSError:
            return np.nan

    base["_mtime"] = base["file"].map(_mtime_for)
    agg_date = base.groupby(group_keys, dropna=False)["_mtime"].min().reset_index().rename(
        columns={"_mtime": "model_date"})
    aggd = aggd.merge(agg_date, on=group_keys, how="left")

    # ---- QUARANTINE (Kim 2026-08-21) ----------------------------------------------
    # xft* = DoRAs EXTRACTED from full finetunes. Kim: "all of them are more or less
    # broken ... they should be quarantined and removed from all tables and statistics."
    # dora_table.html has hidden them since 2026-08-02 (HIDE_MODEL_PREFIXES), but they
    # stayed in THIS csv -- and the csv's `arch` column calls them `dora`, so every
    # statistic computed off it silently pooled 60 broken checkpoints into the DoRA
    # population. That is what suppressed the adapter-vs-fullft effect (eta^2 0.024,
    # actually d=0.84) and it skewed the frame-length table too.
    # Split rather than dropped: the rows move to a sibling csv so the record survives,
    # but nothing that reads the main file can pick them up by accident.
    QUARANTINE_PREFIXES = ("xft",)
    QUARANTINE_REASON = "DoRA extracted from a full finetune; family is broken (Kim 2026-08-21)"
    is_q = aggd["model"].astype(str).str.startswith(QUARANTINE_PREFIXES)
    if is_q.any():
        q = aggd[is_q].copy()
        q["quarantine_reason"] = QUARANTINE_REASON
        q.to_csv(ROOT / "eval/clap_dora_quarantined.csv", index=False)
        print(f"[table] QUARANTINED {len(q)} rows ({q['model'].nunique()} runs) -> "
              f"eval/clap_dora_quarantined.csv  [{QUARANTINE_REASON}]")
        aggd = aggd[~is_q].reset_index(drop=True)
    # -------------------------------------------------------------------------------

    aggd.to_csv(ROOT / "eval/clap_dora_aggregate.csv", index=False)
    n_fb = int(aggd["default_is_fallback"].sum())
    print(f"[table] wrote clap_dora_aggregate.csv  ({len(aggd)} model-checkpoints, "
          f"{n_fb} fell back to all-cells mean for lack of cfg7/w1 cells)")

    # scored_models.json (Kim 2026-08-15, "the polluted models can be removed from the
    # rating"): rate.html pools straight from manifest_live.jsonl with zero regard for
    # whether a model ever passed the latent-sanity gate -- 3 blown-up-latent dronesweep
    # models were rateable in a blind A/B alongside real audio. This list is the single
    # source of "has this model actually been scored" (== has an aggregate row == passed
    # sanity) that any client-side page can fetch the same way it fetches the manifest.
    # Staged next to manifest_live.jsonl (not committed to git -- STAGE, not ROOT) so it
    # rides the same publish path (leg_publish already includes *.json).
    STAGE_MATRIX = Path.home() / "evals_aac" / "model_matrix"
    scored = sorted(aggd["model"].unique().tolist())
    (STAGE_MATRIX / "scored_models.json").write_text(json.dumps(scored))
    print(f"[table] wrote scored_models.json  ({len(scored)} scored models)")

    # scored_models_avp.json (Kim 2026-08-15): the public evaluator.html only surfaces
    # models fine-tuned on Kim's own music (dataset=='avp') -- "that'll land better with
    # musicians because of fully ethical process". Also excludes the xft* family: same
    # HIDE_MODEL_PREFIXES borked-run exclusion build_dora_table_page.py already applies
    # internally (SVD-extracted, "only add noise") -- 30 of the 98 raw avp models are xft*;
    # letting those leak onto a public page would undercut exactly the credibility this page
    # is for.
    HIDE_PREFIXES_PUBLIC = ("xft",)
    avp_scored = sorted(
        aggd[(aggd["dataset"] == "avp") & ~aggd["model"].str.startswith(HIDE_PREFIXES_PUBLIC)]
        ["model"].unique().tolist())
    (STAGE_MATRIX / "scored_models_avp.json").write_text(json.dumps(avp_scored))
    print(f"[table] wrote scored_models_avp.json  ({len(avp_scored)} scored avp models, "
          f"xft* excluded)")

    # ---------- analysis (printed; narrative written separately) ----------
    an = base.copy()
    num_metrics = ["clap_matched", "ce", "pq", "cu", "pc", "zcr", "flatness", "flux",
                   "hf_ratio", "bpm", "onset_p95", "centroid", "crest", "rms"]
    print("\n########## METRIC CORRELATION MATRIX (Spearman, non-repr cells) ##########")
    corr = an[num_metrics].corr(method="spearman")
    print(corr.round(2).to_string())

    print("\n########## PER-PARAMETER MARGINAL EFFECTS (mean over non-repr cells) ##########")
    show = ["clap_matched", "ce", "pq", "zcr", "flatness", "hf_ratio", "bpm"]
    for p in ["arch", "rank", "batch", "frames_T", "lr", "precision", "optimizer",
              "dataset", "aug", "alpha_over_rank", "epoch", "cfg", "strength"]:
        if p not in an:
            continue
        g = an.groupby(p, dropna=False).agg({**{m: "mean" for m in show}, "model": "count"}).rename(columns={"model": "n"})
        g = g[g["n"] >= 20]
        if len(g) < 2:
            continue
        print(f"\n--- {p} ---")
        print(g.round(3).to_string())

    print("\n########## HYPERPARAM -> METRIC CORRELATION (Spearman, DoRA cells only) ##########")
    dora = an[an["arch"] == "dora"].copy()
    for c in ["rank", "batch", "frames_T", "lr", "aug", "alpha_over_rank", "epoch", "cfg", "strength"]:
        dora[c] = pd.to_numeric(dora[c], errors="coerce")
    rows = []
    for p in ["rank", "batch", "frames_T", "lr", "aug", "alpha_over_rank", "epoch", "cfg", "strength"]:
        row = {"param": p}
        for m in show:
            sub = dora[[p, m]].dropna()
            row[m] = round(sub[p].corr(sub[m], method="spearman"), 2) if len(sub) > 50 else np.nan
        rows.append(row)
    print(pd.DataFrame(rows).set_index("param").to_string())


if __name__ == "__main__":
    main()
