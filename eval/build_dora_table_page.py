#!/usr/bin/env python3
"""
build_dora_table_page.py -- interactive web page over the DoRA hyperparameter x metric table
(Kim 2026-07-22: "prepare a web page with the same content but interactive ordering by different
columns, colour coding per column"). Reads eval/clap_dora_aggregate.csv (234 model x checkpoint
rows: hyperparams + CLAP degeneration + Audiobox + DSP) + eval/corpus_reference.json (goa/avp
training baselines). Emits a single self-contained HTML (no external deps): click a header to
sort, every numeric column is a direction-aware heatmap, filter by dataset/rank, and a pinned
DATASET-BASELINE strip so drift-from-source is readable (the stereo-narrowing answer).

OUT: eval/dora_table.html (canonical, committed) -- ALSO copied to STAGING (Kim
2026-07-23: the landing-page link should open a local file, not round-trip to the
live site) so it rides the normal STAGING->live sync alongside every other eval page.
"""
import argparse
import csv
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

ROOT = Path("/home/kim/Projects/SAO/eval")
AGG = ROOT / "clap_dora_aggregate.csv"
REF = ROOT / "corpus_reference.json"
OUT = ROOT / "dora_table.html"
OUT_PUBLIC = ROOT / "dora_table_public.html"
MANIFEST = Path.home() / ".cache/evals_aac/model_matrix/manifest_live.jsonl"

# ---------------------------------------------------------------------------
# PUBLIC-SNAPSHOT redaction (Kim 2026-08-04): --public emits a path-redacted dora_table_public.html
# for hosting on aavepyora.online. The page already uses only RELATIVE clip/ssm bases (model_matrix/,
# ssm/) and carries no absolute paths today, so this is mostly a fail-closed VERIFICATION -- but the
# same MASTER §4 rule (no absolute paths / infra addresses / secrets on public pages) is enforced so
# a future data change that leaks a path is caught at build time. The ?set= filter, table, and
# cell-picker are untouched, so ?set=NAME still loads only that set's models on the hosted page.
_REDACTIONS = [
    ("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs", "the eval drive"),
    ("/run/media/kim/Mantu/lumi_runs", "the Mantu backup drive"),
]
_REDACT_RE = [
    (re.compile(r"/run/media/kim/[^\s\"'<>)]*"), "(local drive)"),
    (re.compile(r"/scratch/project_465003186[^\s\"'<>)]*"), "LUMI scratch"),
    (re.compile(r"/project/project_465003186[^\s\"'<>)]*"), "LUMI project"),
]
_RESIDUAL = [r"/run/media", r"/home/kim", r"/scratch/project", r"/project/project",
             r"dreamhost", r"dh_4txyt6", r"akekim", r"efp\.lumi", r"csc\.fi", r"id_EFP"]


def redact_public(s):
    """Redact absolute local/infra paths from an HTML string, then assert nothing sensitive
    survives (fail closed). Returns the redacted string; raises SystemExit on a residual hit."""
    for a, b in _REDACTIONS:
        s = s.replace(a, b)
    for rx, repl in _REDACT_RE:
        s = rx.sub(repl, s)
    s = s.replace("/home/kim/Projects/SAO/", "")
    s = re.sub(r"/home/kim[^\s\"'<>)]*", "(local path)", s)
    hits = [p for p in _RESIDUAL if re.search(p, s)]
    if hits:
        raise SystemExit(f"REDACTION FAILED (fail closed) -- residual sensitive tokens: {hits}")
    return s


def _jsnum(x):
    f = float(x)
    return str(int(f)) if f == int(f) else repr(f)


# Model-label prefixes hidden from the board entirely -- borked runs that only add noise.
# Applied to BOTH the metric rows (main) AND this embedded cell-index, so hidden models leave
# no row to select and no clip in the file:// index. The live-fetch path guards on the same
# list in JS (const HIDE). xft* = the borked fullft xftdora*/xftlora* families (Kim 2026-08-02).
HIDE_MODEL_PREFIXES = ("xft",)


def cell_fallback():
    """Embedded cell-index so the picker works on file:// (browsers block fetch there).
    Keys match the page's cellKey(model,ckpt,pid,cfg,w) String-concat format exactly."""
    if not MANIFEST.exists():
        return None
    idx, nidx, prompts, cfgs, ws = {}, {}, {}, set(), set()
    for ln in MANIFEST.read_text().splitlines():
        if not ln.strip():
            continue
        try:
            e = json.loads(ln)
        except Exception:
            continue
        if str(e.get("model", "")).startswith(HIDE_MODEL_PREFIXES):
            continue
        cf, w = _jsnum(e["cfg"]), _jsnum(e["strength"])
        # SEP must match the page's cellKey(): m+'\x01'+c+'\x01'+pid+'\x01'+cfg+'\x01'+w
        # (G uses \x01 SOH as a collision-safe separator; a plain concat never matches it).
        key = "\x01".join([e["model"], e["ckpt"], str(e["prompt_id"]), cf, w])
        # native-length renders (duration_mode=native, __dNNN files) live in a PARALLEL index:
        # same 5-tuple key as their 20s twin, selected by the 'native length' checkbox. Keeping
        # them out of idx also fixes a real clobber -- the 5-tuple key has no duration dimension,
        # so a shared index would let whichever entry came last in the manifest win.
        if e.get("duration_mode") == "native":
            nidx[key] = e["file"]
        else:
            idx[key] = e["file"]
            cfgs.add(cf); ws.add(w)
        prompts.setdefault(str(e["prompt_id"]), e.get("prompt_text", ""))
    return {"idx": idx, "nidx": nidx, "prompts": prompts,
            "cfgs": sorted(cfgs, key=float), "ws": sorted(ws, key=float)}
STAGING_COPY = Path.home() / ".cache/evals_aac/dora_table.html"

# column groups + per-metric direction (+1 = higher is better/green, -1 = lower is better)
HP = ["model", "ckpt", "arch", "rank", "alpha", "alpha_over_rank", "precision", "frames_T",
      "batch", "effective_batch", "lr", "optimizer", "dataset", "aug", "epoch", "steps",
      "train_N", "n_cells", "caption_probs", "params_source"]
METRICS = {"clap_matched": +1, "clap_margin_far": +1, "ce": +1, "pq": +1, "cu": +1, "pc": +1,
           "zcr": -1, "flatness": -1, "flux": +1, "hf_ratio": -1, "bpm": 0,
           "onset_p95": +1, "centroid": 0, "crest": -1, "rms": +1,
           # structure (native clips only; recurrence-SSM, Stable Audio longform paper §4.4)
           "recall": +1, "boundaries_per_min": 0, "loop_score": 0}
STRUCT_COLS = ["recall", "boundaries_per_min", "loop_score"]  # not in the base CSV -> merged in
NICE = {"clap_matched": "CLAP", "clap_margin_far": "CLAP·mgn", "alpha_over_rank": "α/rank",
        "frames_T": "T", "onset_p95": "onset", "hf_ratio": "hf", "flatness": "flat",
        "precision": "prec", "optimizer": "opt",
        "effective_batch": "eff·b", "caption_probs": "cap·p", "params_source": "src",
        "recall": "struct·recall", "boundaries_per_min": "sections/min", "loop_score": "loop"}

# Dataset labels arrived from two extraction paths and disagree on spelling for the SAME
# corpus (2026-08-21): the name-regex path emits avp/goa, the sbatch path emits the
# encoded_dir basename (latents_avp / latents_sa3 / latents_avp_aug10). Left as-is they
# split every dataset-grouped view in two and read as five corpora where there are three.
DATASET_ALIASES = {"latents_avp": "avp", "latents_sa3": "goa",
                   "latents_avp_aug10": "avp_aug10", "latents_avp_originals": "avp_originals"}

# hover tooltips per column (native title=). ↑ = higher is better, ↓ = lower is better.
DESC = {
    "model": "Training run label (the recipe). Each row aggregates that run's cfg×strength×prompt cells.",
    "ckpt": "Checkpoint = the training epoch snapshot rendered (ep<N>).",
    "arch": "Adapter type: dora (DoRA rows) · fullft (whole DiT fine-tuned) · base (no adapter).",
    "rank": "DoRA/LoRA rank = adapter capacity. r16 harsh/worst; ≥64 plateaus; 128 = safe default.",
    "alpha": "DoRA alpha = adapter scaling. With α<rank the adapter is applied more gently.",
    "alpha_over_rank": "alpha ÷ rank (effective scale). <1 = 'adjusted' (adj) — beats the standard α=rank.",
    "precision": "Training precision: fp32 or bf16. ≈equal for genre-adherence & buzz; fp32's edge is fidelity (ear-only).",
    "frames_T": "Latent context length in frames (T). ×0.0928 s = seconds. Optimum ~1024; T4096 (long) is worse.",
    "batch": "PER-RANK training batch size. Marginal 'bigger better' is a confound; within a single "
             "dataset the spread is ~0.1 PQ (8→7.57, 4→7.51, 1→7.46) and n.s. at run level.",
    "effective_batch": "batch × ddp_world_size × accumulate_grad_batches. ⚠ TRUST WITH CARE "
                       "(2026-08-21, C's DDP incident): this assumes the ranks form ONE DDP group. "
                       "The Pattern-2 fleet arms did NOT — all 8 ranks ran as INDEPENDENT REPLICAS "
                       "(eight LOCAL_RANK:0, -vN versioned ckpts, full dataset per rank with no ÷8), "
                       "so each replica's true optimizer batch is the PER-RANK `batch` and this column "
                       "is 8× overstated for them. A run dir from those arms is an 8-seed ensemble, "
                       "not one model. Verify per job: LOCAL_RANK 0..7 once each, UN-versioned ckpts, "
                       "steps/epoch ÷8. Recorded for ~42% of runs; blank elsewhere.",
    "caption_probs": "Caption-tier sampling probabilities (T1,T2,T3) the run trained with. Blank where "
                     "not recorded in the launch script.",
    "params_source": "Where this row's hyperparameters came from: `sbatch` = parsed from the actual "
                     "launch script (authoritative) · `name-regex` = inferred from the run name "
                     "(a guess — treat rank/alpha/lr here as unverified).",
    "lr": "Learning rate. Flat 1e-4↔2e-4; cliffs (collapses) at 6e-4.",
    "optimizer": "Optimizer: FusionOpt or AdamW.",
    "dataset": "Training corpus: goa (psytrance) · avp (Kim's own music) · mixed.",
    "aug": "Augmentation multiplier (pitch/stretch). 0 = none. aug10 is the cleanest single win (helps every axis).",
    "epoch": "This checkpoint's training epoch. Overtraining collapses UN-augmented runs by ~ep15; aug10 climbs to ep74 (corpus best).",
    "steps": "Total training optimizer steps at this checkpoint (steps/epoch × epoch, from the recipe's recorded step count). Blank where not recorded.",
    "train_N": "Training-set size = # latent crops. Anchored to the known encoded_dir (aug10=320, originals=288, everything=6111, goa=5401, avp=2393); variant runs estimated from steps/epoch×batch. LOW N = overfit-risk (a small set drilled hard can top CLAP by memorizing the prompt space).",
    "n_cells": "Number of rendered cells total (every cfg×strength×prompt). The metric columns "
               "default to the narrower cfg7/w1 (ptm: cfg1/w1) subset -- check 'all scores' to "
               "average in all of these instead.",
    "clap_matched": "↑ CLAP cosine(audio, its OWN prompt) = genre/prompt ADHERENCE. Low = output drifted off-genre (degeneration).",
    "clap_margin_far": "↑ CLAP gap between the true prompt and out-of-genre control prompts. Higher = more decisively on-genre.",
    "ce": "↑ Audiobox Content Enjoyment (learned subjective 'is it enjoyable'). ~scale 1–10.",
    "pq": "↑ Audiobox Production Quality (learned 'how well produced'). Nearly collinear with CU.",
    "cu": "↑ Audiobox Content Usefulness (learned). Nearly collinear with PQ.",
    "pc": "Audiobox Production Complexity (learned). Neutral — more/less complex, not better/worse.",
    "zcr": "↓ Zero-crossing rate = noise/brightness proxy. High = noisier/buzzier.",
    "flatness": "↓ Spectral flatness (Wiener entropy) = noise-like vs tonal. High = whitened/noisy (buzz).",
    "flux": "↑ Spectral flux = frame-to-frame spectral change (dynamism). Low = static/drone-like.",
    "hf_ratio": "↓ Fraction of spectral energy above 6 kHz = HF-blowout / static-buzz signature. High = harsh.",
    "bpm": "Estimated tempo (BPM). Informational — uncorrelated with quality.",
    "onset_p95": "↑ 95th-pct onset strength = rhythmic density / attack presence. Higher = busier/punchier.",
    "centroid": "Spectral centroid = brightness (Hz). Neutral.",
    "crest": "↓ Crest factor (peak÷RMS). High = peaky/transient; low = more sustained/filled. Genre-adherent output trends lower.",
    "rms": "↑ RMS energy = overall loudness/fullness.",
    "recall": "↑ STRUCTURE: strongest far-lag diagonal in the recurrence SSM = do LATE sections repeat EARLY ones (real musical form). NATIVE clips only. Corr +0.53 with CLAP. goa gen 0.075≈real 0.073; avp gen 0.046<real 0.063 (under-structures).",
    "boundaries_per_min": "STRUCTURE: section count via Foote novelty. Neutral (count alone isn't quality — recall is). Native clips only.",
    "loop_score": "STRUCTURE: most self-similar 30 s stretch = 'stuck'/loop. Generations sit BELOW real music (not the MusicGen loop failure). Native clips only.",
}


# ---------------------------------------------------------------------------
# CAMPAIGN FAMILIES (Kim 2026-08-04: serve arbitrary model SETS; default "all").
# family(label) = the leading campaign token before the config suffix. In practice every
# label is "<family>_<dataset>_<config-ish tokens...>", so the first '_'-delimited token IS
# the campaign stem (adamw / bf16cmp / fp32cmp / fp32frames / dora16 / dora128 / dora128adj /
# dora256 / dora64 / fullft / longctx / winning / smoke / base). avp+goa variants collapse into
# one family (adamw_avp* and adamw_goa* are both "adamw"); _ptm post-trained variants stay in
# their base family (post-trained-medium is a variant, not a separate campaign) because '_ptm'
# is a trailing config token, not the leading one. Two carve-outs:
#   - the older goa DoRA-47s campaign is hyphen-delimited (sa3-goa-dora-47s-b4-cont, ...) so its
#     first '_' token varies; collapse the whole prefix to one family.
#   - dora128_everything_* is the "everything"-dataset (6111-crop) campaign, kept SEPARATE from
#     the dora128_47s/newcap runs per the family list, so 'everything' overrides the dora128 stem.
def family(label):
    if label.startswith("sa3-goa-dora-47s"):
        return "sa3-goa-dora-47s"
    if "everything" in label:
        return "everything"
    return label.split("_")[0]


def derive_model_sets(models):
    """{set_name: [model_labels]} over the VISIBLE (post-HIDE) models. 'all' first, then each
    campaign family. Returns the dict in the canonical order used to seed the dropdown too:
    'all', then families by size desc (ties broken by name)."""
    fam = defaultdict(list)
    for m in models:
        fam[family(m)].append(m)
    ordered = {"all": list(models)}
    for f in sorted(fam, key=lambda k: (-len(fam[k]), k)):
        ordered[f] = sorted(fam[f])
    return ordered


def main(public=False):
    rows = list(csv.DictReader(AGG.open()))
    # Hide borked model families (see HIDE_MODEL_PREFIXES): they vanish from the table entirely.
    rows = [r for r in rows if not r.get("model", "").startswith(HIDE_MODEL_PREFIXES)]
    # Collapse the two spellings of each corpus (see DATASET_ALIASES) before anything groups on it.
    for r in rows:
        ds = (r.get("dataset") or "").strip()
        if ds in DATASET_ALIASES:
            r["dataset"] = DATASET_ALIASES[ds]
    # MODEL_SETS derived from the VISIBLE models only (hidden families have no rows to select).
    model_labels = sorted({r["model"] for r in rows})
    model_sets = derive_model_sets(model_labels)
    print("MODEL_SETS (name -> count):")
    for name, members in model_sets.items():
        print(f"  {name:22s} {len(members)}")
    ref = json.loads(REF.read_text())
    cols = HP + [c for c in METRICS if c in rows[0] or c in STRUCT_COLS]
    # "all scores" sibling columns (Kim 2026-08-15): clap_dora_aggregate.csv now carries BOTH
    # the cfg7/w1-filtered default (plain column name, e.g. "clap_matched") and the unfiltered
    # all-cells mean ("clap_matched_all"). Not part of `cols` (not a separate table column) --
    # ride along on each row so the page's "all scores" toggle can swap the ACTIVE value without
    # a rebuild. STRUCT_COLS (recall/boundaries_per_min/loop_score) never had a cfg/w axis to
    # begin with, so they have no _all sibling.
    all_cols = [c for c in METRICS if f"{c}_all" in rows[0]]

    # numeric coercion + per-column min/max for the heatmap
    def num(v):
        try:
            return float(v)
        except Exception:
            return None
    data = []
    for r in rows:
        d = {c: (num(r.get(c)) if c in METRICS or c in
                 ("rank", "alpha", "alpha_over_rank", "frames_T", "batch", "lr", "aug", "epoch", "n_cells")
                 else r.get(c, "")) for c in cols}
        for c in all_cols:
            d[f"{c}_all"] = num(r.get(f"{c}_all"))
        d["default_is_fallback"] = str(r.get("default_is_fallback", "")).strip().lower() == "true"
        data.append(d)

    # structure metrics (native clips only) -> per (model,ckpt) mean merged into the rows,
    # + a per-FILE lookup for the on-play SSM readout (images at evals/ssm/<stem>.png).
    struct_file = {}
    struct_csv = ROOT / "structure_native.csv"
    if struct_csv.exists():
        agg = {}
        for s in csv.DictReader(struct_csv.open()):
            k = (s["model"], s["ckpt"])
            agg.setdefault(k, {m: [] for m in STRUCT_COLS})
            for m in STRUCT_COLS:
                try:
                    agg[k][m].append(float(s[m]))
                except Exception:
                    pass
            struct_file[s["file"]] = {m: (round(float(s[m]), 3) if s.get(m) not in (None, "") else None)
                                      for m in STRUCT_COLS}
        smc = {k: {m: (round(sum(xs) / len(xs), 3) if xs else None) for m, xs in v.items()}
               for k, v in agg.items()}
        for d in data:
            sm = smc.get((d["model"], d["ckpt"]))
            for m in STRUCT_COLS:
                d[m] = sm.get(m) if sm else None

    # dataset-baseline strip (only the cleanly-comparable axes -- same algorithm as eval extractors)
    base = {}
    for c in ("goa", "avp"):
        b = ref.get(c, {})
        base[c] = {"stereo_corr": b.get("stereo_corr", {}).get("mean"),
                   "stereo_width": b.get("stereo_width", {}).get("mean"),
                   "dissonance": b.get("dissonance", {}).get("mean"),
                   "inharmonicity": b.get("inharmonicity", {}).get("mean"),
                   "mood_top": (b.get("mood_top10") or [])[:6]}

    payload = {"cols": cols, "rows": data, "metrics": METRICS, "hp": HP,
               "nice": NICE, "base": base, "desc": DESC, "struct": struct_file,
               "hide": list(HIDE_MODEL_PREFIXES),   # JS guards the live-fetch index on these
               "hidecfg": [15, 24],   # non-standard cfgs (2 stray models) -- dropdown clutter, hidden
               "model_sets": model_sets,   # {set_name:[labels]} campaign families for the ?set= filter
               "cf": cell_fallback()}   # embedded cell-index so the picker works on file://
    html = _PAGE.replace("__DATA__", json.dumps(payload))
    OUT.write_text(html)
    shutil.copy2(OUT, STAGING_COPY)
    print(f"wrote {OUT}  ({len(rows)} rows, {len(cols)} cols)  + staged copy at {STAGING_COPY}")

    if public:
        phtml = redact_public(html)
        OUT_PUBLIC.write_text(phtml)
        print(f"wrote {OUT_PUBLIC}  ({len(phtml)} bytes)  [public: paths redacted / verified, "
              f"?set= filter + cell-picker intact]")


_PAGE = r"""<!doctype html><html><head><meta charset=utf-8><title>DoRA hyperparameter × metric table</title>
<style>
body{font:12px system-ui;margin:0;background:#0f0f12;color:#e2e2e6}
h1{font-size:16px;margin:12px 14px 2px}.sub{color:#9a9;margin:0 14px 8px;font-size:12px;max-width:1100px;line-height:1.5}
.base{margin:8px 14px;padding:8px 12px;background:#15161b;border:1px solid #2a2c34;border-radius:7px;font-size:12px}
.base b{color:#8cf}.hi{color:#f97;font-weight:bold}
.ctl{margin:8px 14px;display:flex;gap:14px;flex-wrap:wrap;align-items:center}
.ctl label{color:#9a9}select,input{background:#1b1c22;color:#dde;border:1px solid #333;border-radius:4px;padding:3px 5px;font-size:12px}
.wrap{overflow:auto;max-height:78vh;margin:0 8px;border:1px solid #23242c;border-radius:6px}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{padding:3px 7px;text-align:right;white-space:nowrap;border-bottom:1px solid #1c1d24}
th{position:sticky;top:0;background:#181920;cursor:pointer;user-select:none;border-bottom:2px solid #2a2c34;z-index:2}
th:hover{background:#20222b}th.sorted{color:#8cf}
td.txt,th.txt{text-align:left}td.model{text-align:left;color:#cde;position:sticky;left:0;background:#12131a;z-index:1}
tr:hover td{background:#191a22 !important}tr:hover td.model{background:#1c1e28 !important}
.arrow{font-size:9px;color:#8cf}
.pbar{margin:8px 14px;padding:8px 12px;background:#15161b;border:1px solid #2a2c34;border-radius:7px;
 display:flex;gap:12px;flex-wrap:wrap;align-items:center;font-size:12px}
.pbar b{color:#8cf;white-space:nowrap}
.pbar label{color:#9a9;white-space:nowrap}
.pbar label.unavail{opacity:.4}
.pbar select{max-width:220px}
#plabel{color:#9a9;flex:1;min-width:180px}
#plabel.playing{color:#7ed}#plabel.nomatch{color:#f76}
#pp{background:#1b1c22;color:#dde;border:1px solid #333;border-radius:4px;width:26px;height:22px;cursor:pointer}
#pseek{width:140px}
tbody tr{cursor:pointer}
tbody tr.nomatch{opacity:.35}
tbody tr.approx{opacity:.72}   /* plays a nearest-match clip, NOT dead -- see markAvailability */
tbody tr.playing td{background:#183226 !important}tbody tr.playing td.model{background:#1c3c2c !important;color:#9fe}
tbody tr.rowloading td.model::after{content:' ⋯';color:#fc6}
@keyframes flashno{0%,100%{background:transparent}50%{background:#4a1f1f}}
tbody tr.flash td{animation:flashno .35s ease 2}
/* Notes panel (moved from model_matrix 2026-08-04) -- widget CSS itself ships in comments.js */
.notes{max-width:1000px;margin:14px 8px;padding:10px 12px;border:1px solid #2a2a30;border-radius:6px;background:#141418;font:13px system-ui;color:#e0e0e0}
.notes-hd{font-size:12px;color:#9cf;margin-bottom:6px}.notes-scope{color:#7ed}.notes-hint{color:#667;font-style:italic}
.notes-lvl{display:flex;gap:14px;margin-bottom:8px;font-size:12px;color:#bbb}.notes-lvl label{cursor:pointer}
/* Weighted-sort (HYBRID) panel -- ported from model_matrix.html's per-clip hybrid-weight
   sliders (Kim 2026-08-15: "isn't this page supposed to have a multi-parameter weighted
   sorting mechanism? it used to be on the bottom?"). Same visual language, adapted to score
   whole rows instead of one clip's siblings. */
.hybridpanel{max-width:1000px;margin:14px 8px;padding:10px 12px;border:1px solid #2a2a30;border-radius:6px;background:#141418;font:13px system-ui;color:#e0e0e0}
.hp-hd{font-size:12px;color:#9cf;margin-bottom:8px;line-height:1.5}
.hp-weights{display:flex;flex-wrap:wrap;gap:9px 14px;font-size:11px;color:#9ab;align-items:center}
.hw{display:flex;align-items:center;gap:4px}.hw input{width:74px;accent-color:#7cf}
.hw .hwl{cursor:help}.hw .hwv{color:#7cf;width:14px;display:inline-block}
th.hyth{color:#8a9}th.hyth.sorted{color:#8cf}td.hytd{font-weight:600;color:#cde}
</style></head><body>
<h1>DoRA hyperparameter × metric table</h1>
<p class=sub>Every trained model × checkpoint. Each row's metrics default to its <b>cfg7/w1 cells only</b>
(ptm rows: cfg1/w1, their only native config) &mdash; the real operating point, not diluted by
off-config renders. Check "all scores" to go back to every rendered cfg×strength×prompt cell
averaged in. <b>Hover any column header for its definition</b>; click to sort. Each metric column is a
heat-map (green = better direction, red = worse). The last column, <b>HYBRID</b>, is a weighted
multi-metric composite &mdash; set its weights in the panel below the table. Filter below.
Hyperparameters parsed from the checkpoint recipes.</p>
<div class=base id=base></div>
<div class=ctl>
 <label>model set <select id=modelset title="campaign family (or 'all'). Filters BOTH the metric rows and the audio picker to this set; updates the URL (?set=) so the filtered view is shareable."></select></label>
 <label>dataset <select id=fds><option value="">all</option><option>goa</option><option>avp</option><option>mixed</option></select></label>
 <label>rank <select id=frank><option value="">all</option></select></label>
 <label>arch <select id=farch><option value="">all</option></select></label>
 <label>find <input id=ftext placeholder="model substring" size=18></label>
 <label title="Default scores every metric column to the cfg7/w1 cell mean (ptm rows: cfg1/w1, their only native config) -- the real operating point, not diluted by off-config renders (cfg1/cfg16/w2...). Check this to go back to the old behaviour: every rendered cfg×strength×prompt cell averaged in."><input type=checkbox id=fallscores> all scores <span style="color:#667">(ignore cfg7/w1 default)</span></label>
 <span id=count style=color:#9a9></span>
</div>
<div class=pbar>
 <b>Cell picker</b>
 <label>prompt <select id=pprompt></select></label>
 <label>cfg <select id=pcfg></select></label>
 <label>weight <select id=pstrength></select></label>
 <label title="the post-trained (rf_denoiser/ping-pong) base model instead of medium-base, with this row's own adapter applied. Only rendered at cfg1/w1/8-step (its PT-native config) -- higher cfg 'cooks' the output, so checking this forces+locks cfg/weight."><input type=checkbox id=pptm> post-trained</label>
 <label title="play the native-training-length render (e.g. 47.5s for T512 models) instead of the 20s comparison cell. Native grids exist at TERMINAL checkpoints only -- other rows fall back to their 20s clip, marked ·20s in the label. Combines with post-trained (ptm+native)."><input type=checkbox id=pnative> native length</label>
 <button id=pp title="play/pause">&#9654;</button>
 <input type=range id=pseek min=0 max=1000 value=0>
 <span id=ptm style=color:#9a9>0:00 / 0:00</span>
 <a id=pdl href="#" download title="download the clip playing now" style="display:none;color:#7ed;text-decoration:none;font-size:16px;padding:0 4px">&#8681;</a>
 <span id=plabel>loading clip index…</span>
</div>
<div class=wrap><table id=t><thead><tr id=hrow></tr></thead><tbody id=body></tbody></table></div>
<!-- Weighted sort (ported from model_matrix.html's per-clip hybrid-weight sliders, Kim
     2026-08-15). The HYBRID column (last, in the table above) is a weighted composite of these
     sliders: each metric min-max normalized (direction-adjusted) across the rows CURRENTLY
     SHOWN (respects every filter above, including all-scores), weight 0 = ignored. Click the
     HYBRID header to sort by it. -->
<div class="hybridpanel" id="hybridpanel">
 <div class="hp-hd">Weighted sort &mdash; drag a slider to weight that metric into the <b>HYBRID</b>
  column (0 = ignored). Normalized per-metric across the rows currently filtered/shown, so the
  ranking stays meaningful whichever model set or dataset filter is active.</div>
 <div id="hweights" class="hp-weights"></div>
</div>
<!-- NOTES (moved here from model_matrix, Kim 2026-08-04: this is the table he actually auditions
     from, and public visitors were never going to leave notes on the matrix). WRITE-ONLY widget
     -- posts to comment.php, nothing is ever read back or displayed (injection boundary, MASTER
     section 4). Lives outside <table> so render() rebuilding #body can't wipe a half-typed note. -->
<div class="notes">
 <div class="notes-hd">Notes &mdash; <span id="nscope" class="notes-hint">click a model row to play, then comment on it</span></div>
 <div class="notes-lvl">
  <label><input type="radio" name="nlvl" value="clip"> this clip</label>
  <label><input type="radio" name="nlvl" value="ckpt"> checkpoint</label>
  <label><input type="radio" name="nlvl" value="model" checked> model</label>
 </div>
 <div id="notebox" class="cmts"></div>
</div>
<audio id=pl></audio>
<div id=ssmpanel style="display:none;position:fixed;right:12px;bottom:12px;background:#15161b;border:1px solid #2a2c34;border-radius:8px;padding:8px;z-index:20;box-shadow:0 4px 18px #000a">
 <div id=structreadout style="font-size:11px;color:#9cf;margin-bottom:4px;max-width:210px"></div>
 <img id=ssmimg style="width:210px;height:210px;object-fit:contain;background:#0a0a0c;border-radius:4px;display:none" alt="recurrence SSM">
 <div style="font-size:10px;color:#778;margin-top:3px">recurrence SSM · off-diagonal lines = repeated sections</div>
</div>
<script>
const D=__DATA__;
const {cols,rows,metrics,nice,base,desc}=D;
// ---- MODEL SETS (Kim 2026-08-04): serve arbitrary campaign families; default "all".
// URL wins: ?set=<family> (a MODEL_SETS key) > ?models=<comma list of labels> > default all.
// memberSet=null means "all" (no filtering). inSet() gates BOTH the metric rows (render) and the
// cell-picker index (buildCellsByMC / coverage), so the table and the audio picker show the same set.
const MODEL_SETS=D.model_sets||{all:rows.map(r=>r.model)};
let activeSet='all',memberSet=null;
(function initSet(){
 const q=new URLSearchParams(location.search);
 const s=q.get('set'),ms=q.get('models');
 if(s&&MODEL_SETS[s]){activeSet=s;memberSet=new Set(MODEL_SETS[s]);}
 else if(ms){activeSet='';memberSet=new Set(ms.split(',').map(x=>x.trim()).filter(Boolean));}
})();
const inSet=m=>!memberSet||memberSet.has(m);
// ---- cfg7/w1 DEFAULT vs ALL SCORES (Kim 2026-08-15: "many models are dragged down by their
// w2, cfg1 etc scores unfairly"). Every metric column's default value IS already the cfg7/w1
// mean (ptm rows: cfg1/w1) -- see build_clap_hyperparam_table.py. The "<metric>_all" sibling on
// each row is the old unfiltered all-cells mean. mv() is the single place that reads a metric
// off a row, so heat/sort/hybrid all respect the toggle without a data rebuild.
let showAll=false;
function mv(r,c){if(showAll){const av=r[c+'_all'];if(typeof av==='number')return av;}return r[c];}
const nfmt=(c,v)=>{if(v==null||v==='')return '';if(typeof v!=='number')return v;
 if(['lr'].includes(c))return v.toExponential(1);
 if(['rank','alpha','frames_T','batch','aug','epoch','n_cells','bpm'].includes(c))return v%1?v.toFixed(1):v.toFixed(0);
 return v.toFixed(3);};
// per-column min/max for heatmap -- recomputed on the all-scores toggle since the active
// value set changes (computeExt, not a bare const, for that reason).
let ext={};
function computeExt(){ext={};for(const c in metrics){const vs=rows.map(r=>mv(r,c)).filter(v=>typeof v==='number');ext[c]=vs.length?[Math.min(...vs),Math.max(...vs)]:[0,1];}}
computeExt();
function heat(c,v){if(typeof v!=='number'||!(c in metrics)||metrics[c]===0)return '';
 const [lo,hi]=ext[c];let t=(v-lo)/(hi-lo+1e-9);if(metrics[c]<0)t=1-t;   // direction-aware
 const r=Math.round(200*(1-t)+30*t),g=Math.round(60*(1-t)+180*t);return `background:rgba(${r},${g},70,0.30)`;}
// ---- WEIGHTED SORT / HYBRID column (ported from model_matrix.html's per-clip hybrid-weight
// sliders, Kim 2026-08-15: "isn't this page supposed to have a multi-parameter weighted sorting
// mechanism?"). Same design there: each scorable metric (has a direction in `metrics`) is
// min-max normalized (direction-adjusted, 1=best) across a comparison set, then combined by
// user-set slider weights. Here the comparison set is the CURRENTLY FILTERED rows (`rs` in
// render()), recomputed every render so the ranking stays meaningful under any filter.
const HYBRID_DEFAULT_ON=new Set(['clap_matched','clap_margin_far','ce','pq','cu','recall']);
let mWeights={};
for(const c in metrics)if(metrics[c]!==0)mWeights[c]=HYBRID_DEFAULT_ON.has(c)?1:0;
function hybridMetrics(){return Object.keys(mWeights).filter(m=>mWeights[m]>0);}
function normFn(rs,c){
 const dir=metrics[c],vs=rs.map(r=>mv(r,c)).filter(v=>typeof v==='number');
 if(!vs.length)return()=>null;
 const lo=Math.min(...vs),hi=Math.max(...vs);
 return r=>{const v=mv(r,c);if(typeof v!=='number')return null;
  const n=(hi>lo)?(v-lo)/(hi-lo):0.5;return dir<0?1-n:n;};}
function hybridScores(rs){
 const ms=hybridMetrics(),norms={};for(const m of ms)norms[m]=normFn(rs,m);
 const out=new Map();
 for(const r of rs){let s=0,w=0;for(const m of ms){const n=norms[m](r);if(n!=null){s+=mWeights[m]*n;w+=mWeights[m];}}
  out.set(r,w?s/w:null);}
 return out;}
function heatHybrid(n){if(typeof n!=='number')return '';
 const r=Math.round(200*(1-n)+30*n),g=Math.round(60*(1-n)+180*n);return `background:rgba(${r},${g},70,0.30)`;}
function buildWeightUI(){
 const box=document.getElementById('hweights');if(!box)return;let h='';
 for(const c in mWeights){
  h+='<span class=hw><span class=hwl title="'+(desc[c]||c)+' ('+(metrics[c]>0?'higher':'lower')+'-is-better)">'+(nice[c]||c)+'</span>'
    +'<input type=range min=0 max=3 step=0.5 value="'+mWeights[c]+'" oninput="setW(\''+c+'\',this.value)">'
    +'<span class=hwv id="hwv-'+c+'">'+mWeights[c]+'</span></span>';}
 box.innerHTML=h;}
function setW(c,v){mWeights[c]=parseFloat(v);const el=document.getElementById('hwv-'+c);if(el)el.textContent=v;render();}
let sortCol='clap_matched',sortDir=-1;
function hdr(){const tr=document.getElementById('hrow');tr.innerHTML='';
 for(const c of cols){const th=document.createElement('th');const isTxt=typeof rows[0][c]!=='number';
  th.className=(isTxt?'txt ':'')+(c===sortCol?'sorted':'');th.textContent=nice[c]||c;
  th.title=(desc[c]||c)+'  ·  click to sort';
  if(c===sortCol)th.innerHTML+=' <span class=arrow>'+(sortDir<0?'▼':'▲')+'</span>';
  th.onclick=()=>{if(sortCol===c)sortDir*=-1;else{sortCol=c;sortDir=(c in metrics&&metrics[c]>=0)||typeof rows[0][c]!=='number'?-1:-1;}render();};
  tr.appendChild(th);}
 const hth=document.createElement('th');
 hth.className='hyth'+(sortCol==='hybrid'?' sorted':'');hth.textContent='HYBRID';
 hth.title='Weighted composite of the sliders below the table, min-max normalized (direction-adjusted) across the rows currently shown. Click to sort.';
 if(sortCol==='hybrid')hth.innerHTML+=' <span class=arrow>'+(sortDir<0?'▼':'▲')+'</span>';
 hth.onclick=()=>{if(sortCol==='hybrid')sortDir*=-1;else{sortCol='hybrid';sortDir=-1;}render();};
 tr.appendChild(hth);}
function render(){
 const ds=fds.value,rk=frank.value,ar=farch.value,tx=ftext.value.toLowerCase();
 let rs=rows.filter(r=>inSet(r.model)&&(!ds||r.dataset===ds)&&(!rk||String(r.rank)===rk)&&(!ar||r.arch===ar)&&(!tx||String(r.model).toLowerCase().includes(tx)));
 const hy=hybridScores(rs);
 for(const r of rs)r.hybrid=hy.get(r);
 const val=(r,c)=>c==='hybrid'?r.hybrid:mv(r,c);
 rs.sort((a,b)=>{let x=val(a,sortCol),y=val(b,sortCol);if(x==null)return 1;if(y==null)return -1;
  if(typeof x==='number')return (x-y)*sortDir;return String(x).localeCompare(String(y))*sortDir;});
 const body=document.getElementById('body');body.innerHTML='';
 for(const r of rs){const tr=document.createElement('tr');
  tr.dataset.model=r.model;tr.dataset.ckpt=r.ckpt;
  for(const c of cols){const td=document.createElement('td');const v=mv(r,c);
   if(c==='model'){td.className='model';td.textContent=nfmt(c,v)+(r.default_is_fallback?' †':'');
    if(r.default_is_fallback)td.title='no cfg7/w1 (ptm rows: cfg1/w1) cells rendered for this model -- showing the all-cells mean instead';}
   else{if(typeof v!=='number')td.className='txt';td.textContent=nfmt(c,v);}
   const h=heat(c,v);if(h)td.style.cssText=h;tr.appendChild(td);}
  const htd=document.createElement('td');htd.className='hytd';
  htd.textContent=typeof r.hybrid==='number'?(r.hybrid*100).toFixed(0):'·';
  const hh=heatHybrid(r.hybrid);if(hh)htd.style.cssText=hh;
  tr.appendChild(htd);
  body.appendChild(tr);}
 hdr();count.textContent=rs.length+' / '+rows.length+' rows';
 markAvailability();markPlaying();}

// ---- cell picker + click-a-row player (Kim 2026-07-22: pick a prompt×cfg×weight cell up
// top, click a model row to hear THAT model at that cell, if it was rendered). Reads the
// SAME live manifest model_matrix.html itself reads (evals/model_matrix/manifest_live.jsonl
// -- only ever entries whose m4a actually exists), so "no clip" here means truly not
// rendered, not a stale link. Click-to-toggle + loop-until-stopped, matches the established
// site convention (no hover-autoplay -- see model_matrix.html / the other eval pages).
let cellIndex=null,nativeIndex=null,cellsByMC=null,nativeByMC=null,playingKey=null,playingModel=null,playingCkpt=null,curLabel='';
const HIDE=(D.hide||[]);                 // hidden model-label prefixes (borked families)
const isHidden=m=>HIDE.some(p=>String(m).startsWith(p));
// clip / SSM base path: served page lives at /files/ (clips under evals/); a local file://
// copy lives beside its model_matrix/ and ssm/ dirs -> no 'evals/' prefix.
// the page lives at /files/evals/dora_table.html (served) and ~/evals_aac/dora_table.html
// (local) -- in BOTH, the clips + ssm are siblings, so a plain relative base works everywhere.
const CB='model_matrix/';
const SB='ssm/';
const pl=document.getElementById('pl');pl.loop=true;
// userPaused (Kim 2026-08-15: "switching away from the post trained by declicking the
// checkbox does not return to playing the normal clip") -- distinct from pl.paused, which
// also reads true for a brief async window during every INTERNAL src-swap a picker/checkbox
// change makes (pl.pause();pl.src=...;seekAndPlay(ph) -- the play() inside seekAndPlay hasn't
// resolved yet). repickCurrent() used to gate its resolve-and-swap on pl.paused directly: check
// post-trained, then uncheck it again before that first swap's play() has resolved, and the
// uncheck's repickCurrent() call reads pl.paused===true (a LEFTOVER from the checked
// transition's own pause()) and bails out before ever resolving/swapping to the base clip --
// a race, not a permanent break, which is why it looked like only "switching away" failed.
// userPaused is set ONLY by the actual play/pause button, so a picker/checkbox change always
// re-resolves; only a genuine user pause suppresses auto-resume.
let userPaused=false;
function cellKey(m,c,pid,cfg,w){return m+''+c+''+pid+''+cfg+''+w}
// post-trained toggle (Kim 2026-07-23, corrected 2026-07-23 later same day: cfg7 was
// wrong, PT-native is cfg1/8-step): the PT-medium base only rendered at cfg1/w1 (it
// glitches elsewhere), so checking it forces+locks those two selects and every lookup is
// keyed on "<model>_ptm" instead of "<model>" -- same rows, a different underlying render.
// a row is "intrinsically" ptm when ITS OWN label carries the suffix (e.g. a dedicated
// "..._ptm" model row), as opposed to the checkbox appending it to a normal row's lookup.
function isPtmModel(m){return String(m).endsWith('_ptm')}
// guard against double-suffixing: an intrinsically-ptm row plus a checked checkbox used to
// produce "..._ptm_ptm", which resolves to nothing (Kim 2026-08-13 fix, found while wiring
// the ptm-row cfg/weight lock below).
function modelKey(m){return isPtmModel(m)?m:(m+(pptm.checked?'_ptm':''))}
// ptm playback is PINNED to cfg1/w1 (Kim 2026-08-02, reversed same-day): higher cfg/weight
// ptm renders are universally broken/glitchy -- some model families (e.g. fp32cmp) DID render
// a fuller ptm grid, but nobody should ever audition those cells, so resolution ignores the
// picker's cfg/weight while checked rather than trusting per-model availability.
// EXTENDED 2026-08-13 (Kim): the pin now covers BOTH the checkbox AND any row whose OWN name
// already ends in _ptm -- same broken-at-higher-cfg renders, they just got there via the row's
// own label instead of the toggle. `model` is the row currently being resolved/played, if any.
function ptmActive(model){return pptm.checked||(model&&isPtmModel(model))}
function currentSel(model){return {pid:pprompt.value,
 cfg:ptmActive(model)?1:parseFloat(pcfg.value),
 w:ptmActive(model)?1:parseFloat(pstrength.value)}}
// the "lock" half of "forces+locks": grey the two selects out AND set them to 1/1 so the
// picker visibly shows what is actually playing, not just what resolution silently pins.
// 2026-08-13 (Kim: "selecting a ptm row automatically changes cfg to 1"): this used to be
// disabled-only with no value write, specifically to let unchecking the box restore whatever
// was selected before. Kim's ask is the opposite -- the dropdown should SHOW 1/1, not hide the
// pin -- so this now writes the value (only if "1" is actually an available option; a corpus
// that never rendered cfg1 would otherwise get pinned to a value its own dropdown doesn't have).
// Deactivating just re-enables the controls; it does not attempt to restore a prior selection.
function applyPtmLock(model){const on=ptmActive(model);
 pcfg.disabled=on;pstrength.disabled=on;
 if(on){if([...pcfg.options].some(o=>o.value==='1'))pcfg.value='1';
        if([...pstrength.options].some(o=>o.value==='1'))pstrength.value='1';}
 const t=on?'pinned to cfg1 / w1 (post-trained)':'';
 pcfg.title=t;pstrength.title=t;}
// GRACEFUL CELL RESOLUTION (Kim 2026-08-02): the global cfg/weight/prompt picker can request
// a combo a given (model,ckpt) never rendered (e.g. the _ptm winning variants are cfg1-ONLY)
// -> a dead 'no clip rendered' cell. Resolve any miss to the NEAREST available cell for that
// model: exact -> same-prompt nearest cfg/w -> any prompt nearest cfg/w -> the sibling view
// (base<->_ptm) if the selected view has nothing at all. So a click always plays SOMETHING
// when the model has any clip, and the label marks non-exact hits.
// NATIVE-ONLY FALLBACK (G's diagnosis, 2026-08-09): 97 of 723 model-ckpt groups -- every non-terminal
// checkpoint of the fp32frames/fullft/fp32cmp families -- were rendered ONLY at native length, never on
// the 20s grid. Resolution ran over the 20s universe alone, so those rows found nothing and reported
// "no clip rendered" while 705 playable native clips sat in the parallel index. The native overlay
// could not save them either: it swaps the twin of an ALREADY-RESOLVED hit, so a miss in the 20s grid
// failed before native was ever consulted. Fallback order keeps the variant honest: own 20s -> own
// native -> sibling 20s -> sibling native, so we never cross base<->_ptm while the active variant has
// any clip at all (the property F verified on 2026-08-04).
function mcGroup(mkey,ckpt){          // -> {arr,mkey,native} of cells for a model-ckpt, or null
 if(!cellsByMC)return null;
 const sib=mkey.endsWith('_ptm')?mkey.slice(0,-4):mkey+'_ptm';   // last resort: cross the view toggle
 for(const [k,nat] of [[mkey,false],[mkey,true],[sib,false],[sib,true]]){
  const src=nat?nativeByMC:cellsByMC;
  const arr=src&&src.get(k+'\x01'+ckpt);
  if(arr&&arr.length)return {arr,mkey:k,native:nat};}
 return null;}
function resolveCell(mkey,ckpt,pid,cfg,w){
 const g=mcGroup(mkey,ckpt);if(!g)return null;
 let e=g.arr.find(c=>c.pid===pid&&c.cfg===cfg&&c.w===w);
 if(e)return {file:e.file,pid:e.pid,cfg:e.cfg,w:e.w,mkey:g.mkey,native:g.native,exact:true};
 const sp=g.arr.filter(c=>c.pid===pid);           // prefer the requested prompt; else any prompt
 const pool=(sp.length?sp:g.arr).slice()
   .sort((a,b)=>(Math.abs(a.cfg-cfg)-Math.abs(b.cfg-cfg))||(Math.abs(a.w-w)-Math.abs(b.w-w)));
 e=pool[0];return {file:e.file,pid:e.pid,cfg:e.cfg,w:e.w,mkey:g.mkey,native:g.native,exact:false};}
// NATIVE-LENGTH overlay (Kim 2026-08-02 spec): resolution always runs over the 20s universe
// (the densest grid); when the checkbox is on, swap in the native-length twin of the RESOLVED
// cell if one exists (terminal checkpoints only), else keep the 20s clip and say so. Returns
// {file,tag,nkey} -- nkey feeds playingKey so toggling the box mid-play re-resolves the src.
// The swap used to demand an EXACT (prompt,cfg,weight) native twin of the resolved 20s cell.
// Native renders exist at only a sparse subset of the grid -- 3 cfgs x 3 weights x a handful
// of prompts -- so only 3451 of 65002 cells (5.3%) had an exact twin, and for everything else
// ticking the box could do nothing but add a '·20s' label. That is what "the native length
// button does not seem to do much" was (Kim, 2026-08-11). So resolve INSIDE the native
// universe the same way we resolve inside the 20s one: nearest cell for that model-ckpt,
// same prompt preferred. Reach goes from 5.3% of cells to every cell whose model-ckpt has any
// native render at all -- 29310 of 65002 (45.1%), i.e. 25859 more cells where the button does
// something. Rows whose model never got a native render still say ·20s, honestly.
function nativeSwap(hit,ckpt){
 // already a native-only cell (no 20s twin exists to swap to, either way the box is set) --
 // label it ·native so the long clip is never mistaken for the 20s grid render.
 if(hit.native)return {file:hit.file,tag:' ·native',nkey:'\x01N'};
 const base={file:hit.file,tag:'',nkey:''};
 if(!pnative.checked||!nativeIndex)return base;
 const nf=nativeIndex.get(cellKey(hit.mkey,ckpt,hit.pid,hit.cfg,hit.w));
 if(nf)return {file:nf,tag:' ·native',nkey:'\x01N'};
 const g=nativeByMC&&nativeByMC.get(hit.mkey+'\x01'+ckpt);      // nearest native for this model-ckpt
 if(g&&g.length){
  const sp=g.filter(c=>c.pid===hit.pid);                        // same prompt if it has one
  const e=(sp.length?sp:g).slice().sort((a,b)=>
    (Math.abs(a.cfg-hit.cfg)-Math.abs(b.cfg-hit.cfg))||(Math.abs(a.w-hit.w)-Math.abs(b.w-hit.w)))[0];
  return {file:e.file,tag:' ·native·nearest',nkey:'\x01N'+e.pid+e.cfg+e.w};}
 return {file:hit.file,tag:' ·20s',nkey:''};}
// dim rows that have NO clip at the selected PROMPT (with graceful-resolve, cfg/w mismatch
// no longer means "unplayable" -- only a missing prompt is a meaningful "nothing here" signal).
// Availability must mirror what CLICKING actually does (Kim 2026-08-05: "clickables still missing
// for many models"). This used to dim any row lacking the SELECTED prompt -- but resolveCell falls
// back across prompts, so those rows played fine and merely looked dead: on every prompt except the
// default, 147 of 583 rows greyed out with clips sitting right there. Three honest states now:
//   exact   -> normal        (has a clip at this prompt)
//   approx  -> lightly dimmed (plays the nearest cell instead; label says ·nearest)
//   nomatch -> heavily dimmed (nothing anywhere -- genuinely dead)
function markAvailability(){
 if(!cellsByMC)return;
 const {pid}=currentSel();
 document.querySelectorAll('#body tr').forEach(tr=>{
  const g=mcGroup(modelKey(tr.dataset.model),tr.dataset.ckpt);
  const any=!!(g&&g.arr.length);
  const hasPrompt=any&&g.arr.some(c=>c.pid===pid);
  tr.classList.toggle('nomatch',!any);
  tr.classList.toggle('approx',any&&!hasPrompt);
  const nat=any&&g.native?'native-length only — no 20s grid render for this checkpoint':'';
  tr.title=any?[nat,hasPrompt?'':'no clip at this prompt — clicking plays the nearest available cell']
                 .filter(Boolean).join(' · ')
              :'no clip rendered for this model/checkpoint at any setting';});}
function markPlaying(){
 document.querySelectorAll('#body tr.playing').forEach(x=>x.classList.remove('playing'));
 annotateAvailabilityMarkers();
 if(!playingModel)return;
 document.querySelectorAll('#body tr').forEach(tr=>{
  if(tr.dataset.model===playingModel&&tr.dataset.ckpt===playingCkpt)tr.classList.add('playing');});}
// OPTION AVAILABILITY MARKERS (Kim 2026-08-13, extended to cfg/w same day): "green N" for
// values with an alternate NATIVE-length render, "blue P" for values with an alternate
// POST-TRAINED render -- for whichever model is currently playing (annotations are
// per-model; with nothing playing the options just show plain text). Applied to all three
// pickers (prompt/cfg/w) the same way: each option's marker asks "does the alt-universe
// group for this model-ckpt contain ANY cell with this option's value in this field" --
// unfiltered by the other two pickers' current selection, same as the original prompt-only
// version (graceful resolution already finds the nearest cfg/w on a click, so this is a
// coverage hint, not an exact-match promise). A native <option> cannot render two
// differently-coloured letters within one string -- no inline HTML/spans are permitted
// inside option text, and per-character CSS colour isn't available even where whole-option
// colour is -- so this uses a coloured circle glyph directly beside each plain letter
// (\u{1F7E2}N green, \u{1F535}P blue) as the closest faithful rendering of "green letter N /
// blue letter P" a plain <select> can actually produce. Recomputed on every markPlaying()
// call (i.e. on every play/stop/re-pick) so the markers always describe the model actually
// selected, not a stale one.
// DARKEN pptm/pnative when there's nothing for them to switch TO (Kim 2026-08-15: "darken
// native/ptm checkbox if none available for clip" -- missing entirely before this; the two
// checkboxes stayed fully clickable-but-inert with no visual cue, unlike the N/P dropdown
// markers below which already flag per-option availability).
function setCheckboxAvail(el,avail){
 el.disabled=!avail;
 const lbl=el.closest('label');if(lbl)lbl.classList.toggle('unavail',!avail);}
function annotateAvailabilityMarkers(){
 const axes=[[pprompt,'pid'],[pcfg,'cfg'],[pstrength,'w']];
 if(!playingModel||!cellsByMC){
  axes.forEach(([sel])=>{[...sel.options].forEach(o=>{o.textContent=o.title;});});
  setCheckboxAvail(pptm,true);setCheckboxAvail(pnative,true);
  return;}
 const mk=modelKey(playingModel);
 const ng=nativeByMC&&nativeByMC.get(mk+'\x01'+playingCkpt)||[];
 // P (and PN below) only make sense from the non-ptm side ("an alternate POST-TRAINED
 // render exists"). When the ROW ITSELF is intrinsically ptm (isPtmModel(playingModel), NOT
 // isPtmModel(mk)), there is no alternate post-trained render to offer -- you're already on
 // it with no way back short of clicking a different row -- so the mcGroup-style base<->_ptm
 // swap would instead match the BASE model's cells and mislabel "the base model also has
 // this value" as blue P. Kim, 2026-08-13: P lit up on nearly every prompt while playing
 // winning_avpaug10_t512_a45_fp32_ptm, because the base family has near-full grid coverage.
 // Suppress P (and PN) outright in that case.
 //
 // Gating on isPtmModel(mk) instead (mk = modelKey(playingModel), which ALSO gains the _ptm
 // suffix whenever the pptm CHECKBOX is on) was a second bug Kim caught 2026-08-14: checking
 // the post-trained box on an ordinary row is a fully reversible toggle -- P had just told you
 // this exact prompt/cfg/w has a post-trained alternate, you check the box to go look at it,
 // and P vanishes the instant you do, on the row it was advertising. The sibling lookup itself
 // must also key off playingModel, not mk -- mk already carries the checkbox's suffix when the
 // box is checked, so mk+'_ptm' would double-suffix and silently find nothing.
 const rawPtm=isPtmModel(playingModel);
 const pg=rawPtm?[]:cellsByMC.get(playingModel+'_ptm\x01'+playingCkpt)||[];
 // Coarser than the per-option N/P markers below (not matchesOthers-filtered to the current
 // cfg/w/prompt) on purpose: checking either box can itself reveal different cfg/w/prompt
 // combos (native and ptm grids are sparse), so "any cell at all for this model-ckpt" is the
 // right question for a checkbox, not "a cell at exactly what's currently selected". ng is
 // read against mk (the CURRENTLY ACTIVE variant, base or _ptm per pptm's own state), so
 // native's availability re-derives correctly the instant post-trained is toggled.
 setCheckboxAvail(pptm,!rawPtm&&pg.length>0);
 setCheckboxAvail(pnative,ng.length>0);
 // PN (Kim 2026-08-13, "in addition ... if there's native ptm clips" -- confirmed we have
 // them, 464 across the corpus incl. 4 on this exact winning/ptm pair): a render that is
 // BOTH native-length AND post-trained is a distinct third thing from "N exists somewhere"
 // plus "P exists somewhere" as two unrelated clips -- it's ONE clip differing from the
 // current selection on both axes at once. N (nativeByMC keyed on mk) and P (cellsByMC
 // keyed on mk+'_ptm') can never surface this: neither index is ever consulted with BOTH
 // the native table AND the _ptm-suffixed key at the same time. That combination --
 // nativeByMC keyed on mk+'_ptm' -- is exactly the gap. Shown as two adjacent monochrome
 // circles beside "PN" (no single glyph renders half-green/half-blue in a plain <option>),
 // additively alongside N/P, not replacing them -- a value can legitimately carry all three
 // if three distinct clips back each claim.
 const png=rawPtm?[]:nativeByMC&&nativeByMC.get(playingModel+'_ptm\x01'+playingCkpt)||[];
 // Kim 2026-08-13, "every dropdown must consider all of the current settings": a value only
 // counts as an alternate for THIS axis if the render also matches what's currently picked
 // on the OTHER two axes -- e.g. cfg=4 only lights up green if a native render exists at
 // cfg=4 for the CURRENTLY selected prompt and w, not at some unrelated prompt/w combo that
 // happens to share the cfg value. Without this, a huge corpus made every cfg/w option look
 // available regardless of what else was selected, same failure shape as the original P bug.
 const cur=currentSel(playingModel);
 const matchesOthers=(c,field)=>(field==='pid'||c.pid===cur.pid)
   &&(field==='cfg'||c.cfg===cur.cfg)&&(field==='w'||c.w===cur.w);
 axes.forEach(([sel,field])=>{
  const nVals=new Set(ng.filter(c=>matchesOthers(c,field)).map(c=>String(c[field])));
  const pVals=new Set(pg.filter(c=>matchesOthers(c,field)).map(c=>String(c[field])));
  const pnVals=new Set(png.filter(c=>matchesOthers(c,field)).map(c=>String(c[field])));
  [...sel.options].forEach(o=>{
   let t=o.title;
   if(nVals.has(o.value))t+=' \u{1F7E2}N';
   if(pVals.has(o.value))t+=' \u{1F535}P';
   if(pnVals.has(o.value))t+=' \u{1F7E2}\u{1F535}PN';
   o.textContent=t;});});}
function stopPlaying(){pl.pause();userPaused=true;playingKey=playingModel=playingCkpt=null;
 plabel.className='';plabel.textContent='click a model row to play';
 document.getElementById('ssmpanel').style.display='none';document.getElementById('pdl').style.display='none';markPlaying();}
// SAME-PLAYHEAD A/B (Kim 2026-07-23): switching checkpoint (row) or setting (picker) mid-play
// resumes the new clip at the SAME position, so you compare the identical moment. `ph` is the
// shared playhead; seekAndPlay loads the new src then seeks to `ph` once it can play.
let ph=0;
function seekAndPlay(pos){
 const go=()=>{try{const d=pl.duration||1e9;pl.currentTime=(pos>d-0.5)?0:Math.min(pos,d-0.05);}catch(e){}pl.play();};
 if(pl.readyState>=2){go();return;}
 let done=false;const fire=()=>{if(done)return;done=true;go();};
 pl.addEventListener('loadedmetadata',fire,{once:true});setTimeout(fire,1500);}
// re-resolve the CURRENTLY-playing model at a changed picker setting, continue from ph
function repickCurrent(){
 markAvailability();
 // Markers depend on ALL THREE current picker values now (matchesOthers, above), not just
 // (model,ckpt) -- so they must be recomputed on every picker change, including the ones
 // below that bail out early (paused, no hit, resolves to the clip already playing) and
 // would otherwise never reach the markPlaying() call at the bottom that used to be the
 // only thing recomputing them.
 annotateAvailabilityMarkers();
 if(!playingModel||userPaused)return;                 // nothing playing / user hit pause -> just re-dim rows
 applyPtmLock(playingModel);
 const {pid,cfg,w}=currentSel(playingModel);
 const hit=resolveCell(modelKey(playingModel),playingCkpt,pid,cfg,w);
 if(!hit)return;                                      // model has no clip at all -> keep playing
 const sw=nativeSwap(hit,playingCkpt);
 const key=cellKey(hit.mkey,playingCkpt,hit.pid,hit.cfg,hit.w)+sw.nkey;
 if(key===playingKey)return;                          // already on the resolved clip
 playingKey=key;
 curLabel=hit.mkey+' '+playingCkpt+' × '+hit.pid+' cfg'+hit.cfg+' w'+hit.w+(hit.exact?'':' ·nearest')+sw.tag;
 plabel.className='playing';plabel.textContent='▶ '+curLabel;
 pl.pause();pl.src=CB+sw.file;seekAndPlay(ph);showSSM(sw.file);setDL(sw.file);
 noteFromPlay(playingModel,playingCkpt,sw.file);markPlaying();}
function playRow(tr){
 if(!cellIndex)return;   // manifest still loading -- ignore clicks until the index is ready
 userPaused=false;       // clicking a row is always "play this" -- clears any earlier pause
 applyPtmLock(tr.dataset.model);        // lock (and visibly pin to 1/1) BEFORE resolving, so a
                                        // clicked ptm row's own resolution sees the pinned values
 const {pid,cfg,w}=currentSel(tr.dataset.model);
 const hit=resolveCell(modelKey(tr.dataset.model),tr.dataset.ckpt,pid,cfg,w);
 if(!hit){               // truly no clip for this model-ckpt in EITHER view -> genuine dead row
  tr.classList.remove('flash');void tr.offsetWidth;tr.classList.add('flash');
  plabel.className='nomatch';
  plabel.textContent='no clip rendered for '+modelKey(tr.dataset.model)+' '+tr.dataset.ckpt;
  return;}
 const sw=nativeSwap(hit,tr.dataset.ckpt);
 const key=cellKey(hit.mkey,tr.dataset.ckpt,hit.pid,hit.cfg,hit.w)+sw.nkey;
 if(playingKey===key){stopPlaying();return;}
 playingKey=key;playingModel=tr.dataset.model;playingCkpt=tr.dataset.ckpt;
 curLabel=hit.mkey+' '+tr.dataset.ckpt+' × '+hit.pid+' cfg'+hit.cfg+' w'+hit.w+(hit.exact?'':' ·nearest')+sw.tag;
 plabel.className='playing';plabel.textContent='loading… '+curLabel;
 pl.pause();pl.src=CB+sw.file;seekAndPlay(ph);     // resume at the shared playhead (A/B), not from 0
 showSSM(sw.file);setDL(sw.file);
 noteFromPlay(playingModel,playingCkpt,sw.file);
 markPlaying();}
// STRUCTURE panel: on a NATIVE clip, show its recurrence-SSM image + the 3 structure metrics
// (W 2026-07-22). Non-native clips have no entry in D.struct -> panel stays hidden.
function showSSM(f){
 const panel=document.getElementById('ssmpanel'),img=document.getElementById('ssmimg'),ro=document.getElementById('structreadout');
 const st=(D.struct||{})[f];
 if(!st){panel.style.display='none';return;}
 ro.innerHTML='<b>structure</b> · recall '+(st.recall??'?')+' · sections/min '+(st.boundaries_per_min??'?')+' · loop '+(st.loop_score??'?');
 img.onerror=()=>{img.style.display='none'};img.onload=()=>{img.style.display='block'};
 img.style.display='none';img.src=SB+f.replace(/\.m4a$/,'.png');
 panel.style.display='block';}
// download button: point it at the clip playing now (Kim 2026-07-23, for grabbing good evals)
function setDL(f){const a=document.getElementById('pdl');a.href=CB+f;a.setAttribute('download',f);a.style.display='inline';}
document.getElementById('body').addEventListener('click',e=>{
 const tr=e.target.closest('tr');if(!tr||!tr.dataset.model)return;playRow(tr);});
['pprompt','pcfg','pstrength'].forEach(id=>document.getElementById(id).onchange=repickCurrent);
pptm.addEventListener('change',()=>{applyPtmLock();repickCurrent();});
pnative.addEventListener('change',repickCurrent);
// transport: play/pause + seek + time, matching model_matrix.html's player
const fmtT=s=>{s=Math.max(0,s|0);return (s/60|0)+':'+String(s%60).padStart(2,'0')};
let seeking=false;
pp.addEventListener('click',()=>{if(pl.paused){userPaused=false;if(pl.src)pl.play()}else{userPaused=true;pl.pause()}});
pl.addEventListener('play',()=>pp.innerHTML='&#9208;');
pl.addEventListener('pause',()=>pp.innerHTML='&#9654;');
pl.addEventListener('waiting',()=>{document.querySelectorAll('#body tr.playing').forEach(x=>x.classList.add('rowloading'));});
pl.addEventListener('playing',()=>{document.querySelectorAll('#body tr.rowloading').forEach(x=>x.classList.remove('rowloading'));
 if(playingKey){plabel.className='playing';plabel.textContent='▶ '+curLabel;}});
pl.addEventListener('timeupdate',()=>{if(!pl.paused&&!seeking)ph=pl.currentTime;if(seeking||!pl.duration)return;pseek.value=Math.round(pl.currentTime/pl.duration*1000);ptm.textContent=fmtT(pl.currentTime)+' / '+fmtT(pl.duration);});
pl.addEventListener('durationchange',()=>{if(pl.duration)ptm.textContent=fmtT(pl.currentTime)+' / '+fmtT(pl.duration);});
pseek.addEventListener('input',()=>{seeking=true;if(pl.duration)ptm.textContent=fmtT(pseek.value/1000*pl.duration)+' / '+fmtT(pl.duration);});
pseek.addEventListener('change',()=>{if(pl.duration){pl.currentTime=pseek.value/1000*pl.duration;ph=pl.currentTime;}seeking=false;});
// per-MODEL availability: group every clip by (model,ckpt) so graceful-resolve can find the
// nearest cell a given model actually rendered (Kim 2026-08-02). RESTRICTED to member models
// (Kim 2026-08-04) so the picker index shows only the active set. Rebuilt on set change.
// Both universes get a group map: the 20s grid drives resolution, and the native index is the
// FALLBACK for model-ckpts that only ever rendered native (G 2026-08-09 -- see mcGroup).
function groupByMC(idx){
 const m=new Map();
 if(idx)for(const [k,f] of idx){const p=k.split('\x01');
  if(!inSet(p[0]))continue;                 // keep the picker index to the active set
  const g=p[0]+'\x01'+p[1];
  let a=m.get(g);if(!a){a=[];m.set(g,a);}
  a.push({pid:p[2],cfg:parseFloat(p[3]),w:parseFloat(p[4]),file:f});}
 return m;}
function buildCellsByMC(){cellsByMC=groupByMC(cellIndex);nativeByMC=groupByMC(nativeIndex);}
function fillPicker(promptTxt,cfgSet,wSet){
 // Same source of truth as the picker -- built from the manifest/snapshot cellIndex, both paths.
 buildCellsByMC();
 // per-prompt coverage = # distinct (model,ckpt) with any clip at that prompt, from the clip index
 // (Kim 2026-08-02: default to the WIDEST-coverage prompt so the opening view greys the fewest rows).
 const cov={};
 if(cellIndex)for(const k of cellIndex.keys()){const p=k.split('\x01');if(!inSet(p[0]))continue;(cov[p[2]]=cov[p[2]]||new Set()).add(p[0]+'\x01'+p[1]);}
 for(const [pid,txt] of [...promptTxt].sort((a,b)=>a[0].localeCompare(b[0]))){
  const t=txt||pid;const o=new Option(t,pid);o.title=t;pprompt.add(o);}   // full prompt text (Kim: show full)
 let best=null,bn=-1;for(const pid in cov)if(cov[pid].size>bn){bn=cov[pid].size;best=pid;}
 if(best!=null)pprompt.value=best;                                        // default = widest coverage
 const HIDECFG=new Set(D.hidecfg||[]);   // non-standard cfgs kept out of the dropdown (clutter)
 // .title = the base label, same convention as the prompt options above -- annotateAvailabilityMarkers()
 // rewrites textContent from .title on every play/re-pick, so an option missing .title would go blank.
 [...cfgSet].filter(v=>!HIDECFG.has(v)).sort((a,b)=>a-b).forEach(v=>{const o=new Option('cfg '+v,v);o.title=o.text;pcfg.add(o);});
 [...wSet].sort((a,b)=>a-b).forEach(v=>{const o=new Option('w '+v,v);o.title=o.text;pstrength.add(o);});
 if(cfgSet.has(7))pcfg.value='7';           // Kim's worked example default
 if(wSet.has(1))pstrength.value='1';
 applyPtmLock();  // the page never restores ptm itself, but browsers re-check the box from their
                  // own form-state cache on F5/back-nav -- without this the lock would be missing
 markAvailability();}
async function loadManifest(){
 cellIndex=new Map();nativeIndex=new Map();
 const promptTxt=new Map(),cfgSet=new Set(),wSet=new Set();
 try{
  const r=await fetch('model_matrix/manifest_live.jsonl',{cache:'no-store'});
  if(!r.ok)throw new Error('HTTP '+r.status);
  const txt=await r.text();
  for(const line of txt.split('\n')){
   if(!line.trim())continue;let e;try{e=JSON.parse(line)}catch(_){continue}
   if(isHidden(e.model))continue;   // keep hidden families out of the client index too
   if(!promptTxt.has(e.prompt_id))promptTxt.set(e.prompt_id,e.prompt_text);
   // native-length renders go to the parallel index (same 5-tuple key as the 20s twin --
   // sharing cellIndex would clobber whichever entry the manifest lists first)
   if(e.duration_mode==='native'){nativeIndex.set(cellKey(e.model,e.ckpt,e.prompt_id,e.cfg,e.strength),e.file);continue;}
   cellIndex.set(cellKey(e.model,e.ckpt,e.prompt_id,e.cfg,e.strength),e.file);
   cfgSet.add(e.cfg);wSet.add(e.strength);}
  fillPicker(promptTxt,cfgSet,wSet);
  plabel.textContent='click a model row to play';return;
 }catch(err){/* file:// blocks fetch, or offline -> embedded snapshot below */}
 const cf=(typeof D!=='undefined')?D.cf:null;
 if(cf&&cf.idx){
  for(const k in cf.idx)cellIndex.set(k,cf.idx[k]);       // keys already in cellKey format
  for(const k in (cf.nidx||{}))nativeIndex.set(k,cf.nidx[k]);
  for(const pid in cf.prompts)promptTxt.set(pid,cf.prompts[pid]);
  cf.cfgs.forEach(v=>cfgSet.add(parseFloat(v)));cf.ws.forEach(v=>wSet.add(parseFloat(v)));
  fillPicker(promptTxt,cfgSet,wSet);
  plabel.textContent='offline snapshot — click a row to play';
 }else{plabel.textContent='clip index unavailable — open the served page for playback';}}
// model-set dropdown: 'all' first, then families in MODEL_SETS' own order (built size-desc).
for(const name of Object.keys(MODEL_SETS)){
 const o=new Option(name==='all'?'all ('+MODEL_SETS.all.length+')':name+' ('+MODEL_SETS[name].length+')',name);
 modelset.add(o);}
if(activeSet&&MODEL_SETS[activeSet])modelset.value=activeSet;   // '' (custom ?models=) selects nothing
// switch sets: re-filter table + picker index + availability, and make the view shareable via ?set=.
function applySet(name){
 activeSet=name;
 memberSet=(name==='all'||!MODEL_SETS[name])?null:new Set(MODEL_SETS[name]);
 buildCellsByMC();render();markAvailability();
 const u=new URL(location);
 if(name==='all')u.searchParams.delete('set');else u.searchParams.set('set',name);
 u.searchParams.delete('models');   // an explicit dropdown pick supersedes any ?models= list
 history.replaceState(null,'',u);}
modelset.onchange=()=>applySet(modelset.value);
// filters
for(const id of ['fds','frank','farch'])document.getElementById(id);
[...new Set(rows.map(r=>r.rank).filter(v=>v!=null))].sort((a,b)=>a-b).forEach(v=>frank.add(new Option(v,v)));
[...new Set(rows.map(r=>r.arch).filter(Boolean))].forEach(v=>farch.add(new Option(v,v)));
['fds','frank','farch'].forEach(id=>document.getElementById(id).onchange=render);
ftext.oninput=render;
fallscores.onchange=()=>{showAll=fallscores.checked;computeExt();render();};
buildWeightUI();
// dataset baseline strip
let bh='<b>Dataset training baselines</b> (same algorithm as the eval extractors → drift-readable). ';
bh+='<span class=hi>Stereo narrowing is a MODEL artifact:</span> goa training stereo_corr '+base.goa.stereo_corr+' / avp '+base.avp.stereo_corr+' (wide) vs renders ≈0.88 (narrow). ';
bh+='<br><b>goa</b>: stereo_corr '+base.goa.stereo_corr+' · dissonance '+base.goa.dissonance+' · inharm '+base.goa.inharmonicity+' · moods '+(base.goa.mood_top||[]).slice(0,5).join(', ');
bh+='<br><b>avp</b>: stereo_corr '+base.avp.stereo_corr+' · dissonance '+base.avp.dissonance+' · inharm '+base.avp.inharmonicity+' · moods '+(base.avp.mood_top||[]).slice(0,5).join(', ');
document.getElementById('base').innerHTML=bh;
// NOTES scope -- follows whatever row you're auditioning (playRow/repickCurrent call this).
// WRITE-ONLY: CommentWidget POSTs to comment.php and never reads or renders anything back.
let noteCtx=null,noteKey='';
function setNoteScope(){
 const box=document.getElementById('notebox'),sc=document.getElementById('nscope');
 if(!noteCtx||!noteCtx.model){sc.textContent='click a model row to play, then comment on it';
  sc.className='notes-hint';box.innerHTML='';noteKey='';return;}
 const lvl=(document.querySelector('input[name=nlvl]:checked')||{}).value||'model';
 const ck=(lvl==='model')?'':(noteCtx.ckpt||''),cl=(lvl==='clip')?(noteCtx.clip||''):'';
 sc.className='notes-scope';
 sc.textContent = lvl==='model'?noteCtx.model
   : lvl==='ckpt'?(noteCtx.model+' ▸ '+noteCtx.ckpt)
   : (noteCtx.model+' ▸ '+noteCtx.ckpt+' ▸ '+(noteCtx.clip||'').replace(/\.m4a$/,''));
 // re-init ONLY on a real scope change: init() rewrites the box, which would eat a half-typed
 // note every time the picker or the playhead moved the resolved clip under you.
 const key=lvl+'|'+noteCtx.model+'|'+ck+'|'+cl; if(key===noteKey)return; noteKey=key;
 box.dataset.page='dora_table';box.dataset.model=noteCtx.model;box.dataset.ckpt=ck;box.dataset.clip=cl;
 if(window.CommentWidget)CommentWidget.init(box);}
function noteFromPlay(model,ckpt,file){noteCtx={model:model,ckpt:ckpt,clip:file};setNoteScope();}
document.querySelectorAll('input[name=nlvl]').forEach(r=>r.addEventListener('change',setNoteScope));
render();
loadManifest();
</script>
<script src="/files/comments.js"></script></body></html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build the DoRA hyperparameter x metric web page.")
    ap.add_argument("--public", action="store_true",
                    help="ALSO emit a path-redacted dora_table_public.html for hosting on "
                         "aavepyora.online (default eval/dora_table.html + staged copy unchanged).")
    args = ap.parse_args()
    main(public=args.public)
