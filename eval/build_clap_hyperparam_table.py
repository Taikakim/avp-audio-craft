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
LR_BASE = 2e-4  # the "1x" reference (recipe: lr1x -> 0.0002, lr3x -> 0.0006)
FPS = 44100 / 4096  # latent frame rate 10.7666 Hz -> duration = T / FPS

# T(latent frames) -> seconds, for recipes that quote seconds not frames
SEC_TO_T = {23.78: 256, 47.6: 512, 47.56: 512, 95.1: 1024, 190.2: 2048, 380.4: 4096}


def _num(s):
    try:
        return float(s)
    except Exception:
        return np.nan


def parse_recipe(recipe, label):
    """Return a dict of structured hyperparams. recipe (authoritative) first, label fallback."""
    r = (recipe or "").lower()
    lab = label.lower()
    d = {}

    # arch family
    if "full fine-tune" in r or "full-finetune" in r or "unfrozen" in r or lab.startswith("fullft"):
        d["arch"] = "fullft"
    elif lab in ("base", "base_ptm") or (recipe and "no adapter" in r):
        d["arch"] = "base"
    else:
        d["arch"] = "dora"

    # rank / alpha  (recipe: "rank 128 alpha 128"; name: doraN / rN)
    m = re.search(r"rank (\d+)", r) or re.search(r"\br(\d+)\b", r)
    d["rank"] = int(m.group(1)) if m else (int(re.search(r"dora(\d+)", lab).group(1)) if re.search(r"dora(\d+)", lab)
                                           else (int(re.search(r"[_-]r(\d+)", lab).group(1)) if re.search(r"[_-]r(\d+)", lab) else np.nan))
    m = re.search(r"alpha (\d+)", r) or re.search(r"α(\d+)", recipe or "")
    d["alpha"] = int(m.group(1)) if m else np.nan
    d["alpha_over_rank"] = (d["alpha"] / d["rank"]) if (d.get("alpha") and d.get("rank")) else np.nan

    # precision
    d["precision"] = "fp32" if ("fp32" in r or "32-true" in r or "fp32" in lab) else ("bf16" if ("bf16" in r or "bf16" in lab) else "bf16")

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
    d["optimizer"] = "fusionopt" if ("fusion" in r or "fusion" in lab) else ("adamw" if "adamw" in r or "adamw" in lab else np.nan)

    # dataset + augmentation + base target
    d["dataset"] = "avp" if "avp" in lab else ("goa" if "goa" in lab else ("mixed" if "everything" in lab else np.nan))
    ma = re.search(r"aug(\d+)", lab)
    d["aug"] = int(ma.group(1)) if ma else 0
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
        "SELECT path, dur, rms, crest, zcr, onset_p95, centroid, flatness, flux, hf_ratio, bpm, ce, pq, cu, pc "
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
    hp = {m: parse_recipe(resolve_recipe(m, ov), m) for m in df["model"].unique()}
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
               "batch", "lr", "optimizer", "dataset", "aug", "base_target", "epoch", "steps", "train_N"]
    ctrl_cols = ["cfg", "strength"]
    metric_cols = ["clap_matched", "clap_margin_far", "retrieval_rank", "beats_all_far",
                   "ce", "pq", "cu", "pc", "zcr", "flatness", "flux", "hf_ratio", "bpm",
                   "onset_p95", "centroid", "crest", "rms", "dur"]
    keep = ["model", "ckpt", "prompt_id", "is_repr"] + hp_cols + ctrl_cols + [c for c in metric_cols if c in df]
    out = df[keep].copy()
    out.to_csv(ROOT / "eval/clap_full_table.csv", index=False)
    print(f"[table] wrote clap_full_table.csv  ({len(out)} cells, {len(keep)} cols)")

    # per (model,ckpt) aggregate: hyperparams + mean of metrics (exclude _repr dupes)
    agg_metrics = {c: "mean" for c in metric_cols if c in df}
    base = out[~out["is_repr"]]
    grp = base.groupby(["model", "ckpt"] + hp_cols, dropna=False)
    aggd = grp.agg({**agg_metrics, "prompt_id": "count"}).rename(columns={"prompt_id": "n_cells"}).reset_index()
    aggd.to_csv(ROOT / "eval/clap_dora_aggregate.csv", index=False)
    print(f"[table] wrote clap_dora_aggregate.csv  ({len(aggd)} model-checkpoints)")

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
