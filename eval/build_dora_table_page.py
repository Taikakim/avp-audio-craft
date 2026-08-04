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
      "batch", "lr", "optimizer", "dataset", "aug", "epoch", "steps", "train_N", "n_cells"]
METRICS = {"clap_matched": +1, "clap_margin_far": +1, "ce": +1, "pq": +1, "cu": +1, "pc": +1,
           "zcr": -1, "flatness": -1, "flux": +1, "hf_ratio": -1, "bpm": 0,
           "onset_p95": +1, "centroid": 0, "crest": -1, "rms": +1,
           # structure (native clips only; recurrence-SSM, Stable Audio longform paper §4.4)
           "recall": +1, "boundaries_per_min": 0, "loop_score": 0}
STRUCT_COLS = ["recall", "boundaries_per_min", "loop_score"]  # not in the base CSV -> merged in
NICE = {"clap_matched": "CLAP", "clap_margin_far": "CLAP·mgn", "alpha_over_rank": "α/rank",
        "frames_T": "T", "onset_p95": "onset", "hf_ratio": "hf", "flatness": "flat",
        "precision": "prec", "optimizer": "opt",
        "recall": "struct·recall", "boundaries_per_min": "sections/min", "loop_score": "loop"}

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
    "batch": "Training batch size. Marginal 'bigger better' is a confound; at matched context small batch is cleaner.",
    "lr": "Learning rate. Flat 1e-4↔2e-4; cliffs (collapses) at 6e-4.",
    "optimizer": "Optimizer: FusionOpt or AdamW.",
    "dataset": "Training corpus: goa (psytrance) · avp (Kim's own music) · mixed.",
    "aug": "Augmentation multiplier (pitch/stretch). 0 = none. aug10 is the cleanest single win (helps every axis).",
    "epoch": "This checkpoint's training epoch. Overtraining collapses UN-augmented runs by ~ep15; aug10 climbs to ep74 (corpus best).",
    "steps": "Total training optimizer steps at this checkpoint (steps/epoch × epoch, from the recipe's recorded step count). Blank where not recorded.",
    "train_N": "Training-set size = # latent crops. Anchored to the known encoded_dir (aug10=320, originals=288, everything=6111, goa=5401, avp=2393); variant runs estimated from steps/epoch×batch. LOW N = overfit-risk (a small set drilled hard can top CLAP by memorizing the prompt space).",
    "n_cells": "Number of rendered cells averaged into this row.",
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
    # MODEL_SETS derived from the VISIBLE models only (hidden families have no rows to select).
    model_labels = sorted({r["model"] for r in rows})
    model_sets = derive_model_sets(model_labels)
    print("MODEL_SETS (name -> count):")
    for name, members in model_sets.items():
        print(f"  {name:22s} {len(members)}")
    ref = json.loads(REF.read_text())
    cols = HP + [c for c in METRICS if c in rows[0] or c in STRUCT_COLS]

    # numeric coercion + per-column min/max for the heatmap
    def num(v):
        try:
            return float(v)
        except Exception:
            return None
    data = []
    for r in rows:
        data.append({c: (num(r.get(c)) if c in METRICS or c in
                         ("rank", "alpha", "alpha_over_rank", "frames_T", "batch", "lr", "aug", "epoch", "n_cells")
                         else r.get(c, "")) for c in cols})

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
.pbar select{max-width:220px}
#plabel{color:#9a9;flex:1;min-width:180px}
#plabel.playing{color:#7ed}#plabel.nomatch{color:#f76}
#pp{background:#1b1c22;color:#dde;border:1px solid #333;border-radius:4px;width:26px;height:22px;cursor:pointer}
#pseek{width:140px}
tbody tr{cursor:pointer}
tbody tr.nomatch{opacity:.35}
tbody tr.playing td{background:#183226 !important}tbody tr.playing td.model{background:#1c3c2c !important;color:#9fe}
tbody tr.rowloading td.model::after{content:' ⋯';color:#fc6}
@keyframes flashno{0%,100%{background:transparent}50%{background:#4a1f1f}}
tbody tr.flash td{animation:flashno .35s ease 2}
/* Notes panel (moved from model_matrix 2026-08-04) -- widget CSS itself ships in comments.js */
.notes{max-width:1000px;margin:14px 8px;padding:10px 12px;border:1px solid #2a2a30;border-radius:6px;background:#141418;font:13px system-ui;color:#e0e0e0}
.notes-hd{font-size:12px;color:#9cf;margin-bottom:6px}.notes-scope{color:#7ed}.notes-hint{color:#667;font-style:italic}
.notes-lvl{display:flex;gap:14px;margin-bottom:8px;font-size:12px;color:#bbb}.notes-lvl label{cursor:pointer}
</style></head><body>
<h1>DoRA hyperparameter × metric table</h1>
<p class=sub>Every trained model × checkpoint (each row aggregates its cfg×strength×prompt cells).
<b>Hover any column header for its definition</b>; click to sort. Each metric column is a
heat-map (green = better direction, red = worse). Filter below. Hyperparameters parsed from the
checkpoint recipes.</p>
<div class=base id=base></div>
<div class=ctl>
 <label>model set <select id=modelset title="campaign family (or 'all'). Filters BOTH the metric rows and the audio picker to this set; updates the URL (?set=) so the filtered view is shareable."></select></label>
 <label>dataset <select id=fds><option value="">all</option><option>goa</option><option>avp</option><option>mixed</option></select></label>
 <label>rank <select id=frank><option value="">all</option></select></label>
 <label>arch <select id=farch><option value="">all</option></select></label>
 <label>find <input id=ftext placeholder="model substring" size=18></label>
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
const nfmt=(c,v)=>{if(v==null||v==='')return '';if(typeof v!=='number')return v;
 if(['lr'].includes(c))return v.toExponential(1);
 if(['rank','alpha','frames_T','batch','aug','epoch','n_cells','bpm'].includes(c))return v%1?v.toFixed(1):v.toFixed(0);
 return v.toFixed(3);};
// per-column min/max for heatmap
const ext={};
for(const c in metrics){const vs=rows.map(r=>r[c]).filter(v=>typeof v==='number');ext[c]=[Math.min(...vs),Math.max(...vs)];}
function heat(c,v){if(typeof v!=='number'||!(c in metrics)||metrics[c]===0)return '';
 const [lo,hi]=ext[c];let t=(v-lo)/(hi-lo+1e-9);if(metrics[c]<0)t=1-t;   // direction-aware
 const r=Math.round(200*(1-t)+30*t),g=Math.round(60*(1-t)+180*t);return `background:rgba(${r},${g},70,0.30)`;}
let sortCol='clap_matched',sortDir=-1;
function hdr(){const tr=document.getElementById('hrow');tr.innerHTML='';
 for(const c of cols){const th=document.createElement('th');const isTxt=typeof rows[0][c]!=='number';
  th.className=(isTxt?'txt ':'')+(c===sortCol?'sorted':'');th.textContent=nice[c]||c;
  th.title=(desc[c]||c)+'  ·  click to sort';
  if(c===sortCol)th.innerHTML+=' <span class=arrow>'+(sortDir<0?'▼':'▲')+'</span>';
  th.onclick=()=>{if(sortCol===c)sortDir*=-1;else{sortCol=c;sortDir=(c in metrics&&metrics[c]>=0)||typeof rows[0][c]!=='number'?-1:-1;}render();};
  tr.appendChild(th);}}
function render(){
 const ds=fds.value,rk=frank.value,ar=farch.value,tx=ftext.value.toLowerCase();
 let rs=rows.filter(r=>inSet(r.model)&&(!ds||r.dataset===ds)&&(!rk||String(r.rank)===rk)&&(!ar||r.arch===ar)&&(!tx||String(r.model).toLowerCase().includes(tx)));
 rs.sort((a,b)=>{let x=a[sortCol],y=b[sortCol];if(x==null)return 1;if(y==null)return -1;
  if(typeof x==='number')return (x-y)*sortDir;return String(x).localeCompare(String(y))*sortDir;});
 const body=document.getElementById('body');body.innerHTML='';
 for(const r of rs){const tr=document.createElement('tr');
  tr.dataset.model=r.model;tr.dataset.ckpt=r.ckpt;
  for(const c of cols){const td=document.createElement('td');const v=r[c];
   if(c==='model')td.className='model';else if(typeof v!=='number')td.className='txt';
   td.textContent=nfmt(c,v);const h=heat(c,v);if(h)td.style.cssText=h;tr.appendChild(td);}
  body.appendChild(tr);}
 hdr();count.textContent=rs.length+' / '+rows.length+' rows';
 markAvailability();markPlaying();}

// ---- cell picker + click-a-row player (Kim 2026-07-22: pick a prompt×cfg×weight cell up
// top, click a model row to hear THAT model at that cell, if it was rendered). Reads the
// SAME live manifest model_matrix.html itself reads (evals/model_matrix/manifest_live.jsonl
// -- only ever entries whose m4a actually exists), so "no clip" here means truly not
// rendered, not a stale link. Click-to-toggle + loop-until-stopped, matches the established
// site convention (no hover-autoplay -- see model_matrix.html / the other eval pages).
let cellIndex=null,nativeIndex=null,cellsByMC=null,playingKey=null,playingModel=null,playingCkpt=null,curLabel='';
const HIDE=(D.hide||[]);                 // hidden model-label prefixes (borked families)
const isHidden=m=>HIDE.some(p=>String(m).startsWith(p));
// clip / SSM base path: served page lives at /files/ (clips under evals/); a local file://
// copy lives beside its model_matrix/ and ssm/ dirs -> no 'evals/' prefix.
// the page lives at /files/evals/dora_table.html (served) and ~/evals_aac/dora_table.html
// (local) -- in BOTH, the clips + ssm are siblings, so a plain relative base works everywhere.
const CB='model_matrix/';
const SB='ssm/';
const pl=document.getElementById('pl');pl.loop=true;
function cellKey(m,c,pid,cfg,w){return m+''+c+''+pid+''+cfg+''+w}
// post-trained toggle (Kim 2026-07-23, corrected 2026-07-23 later same day: cfg7 was
// wrong, PT-native is cfg1/8-step): the PT-medium base only rendered at cfg1/w1 (it
// glitches elsewhere), so checking it forces+locks those two selects and every lookup is
// keyed on "<model>_ptm" instead of "<model>" -- same rows, a different underlying render.
function modelKey(m){return m+(pptm.checked?'_ptm':'')}
// ptm playback is PINNED to cfg1/w1 (Kim 2026-08-02, reversed same-day): higher cfg/weight
// ptm renders are universally broken/glitchy -- some model families (e.g. fp32cmp) DID render
// a fuller ptm grid, but nobody should ever audition those cells, so resolution ignores the
// picker's cfg/weight while checked rather than trusting per-model availability. The picker's
// OWN select values are untouched (no DOM write) so unchecking reveals whatever was selected
// before, unchanged -- only the resolved cfg/w is pinned, not the visible controls.
function currentSel(){return {pid:pprompt.value,
 cfg:pptm.checked?1:parseFloat(pcfg.value),
 w:pptm.checked?1:parseFloat(pstrength.value)}}
// the "lock" half of the tooltip's forces+locks: grey the two selects out while ptm is
// checked, so a control that no longer affects playback READS as locked rather than broken.
// Deliberately disabled-only -- no value write -- to keep the no-DOM-write rule above intact
// (disabled selects retain .value, so unchecking restores the prior selection untouched).
function applyPtmLock(){const on=pptm.checked;pcfg.disabled=on;pstrength.disabled=on;
 const t=on?'pinned to cfg1 / w1 while post-trained is checked':'';
 pcfg.title=t;pstrength.title=t;}
// GRACEFUL CELL RESOLUTION (Kim 2026-08-02): the global cfg/weight/prompt picker can request
// a combo a given (model,ckpt) never rendered (e.g. the _ptm winning variants are cfg1-ONLY)
// -> a dead 'no clip rendered' cell. Resolve any miss to the NEAREST available cell for that
// model: exact -> same-prompt nearest cfg/w -> any prompt nearest cfg/w -> the sibling view
// (base<->_ptm) if the selected view has nothing at all. So a click always plays SOMETHING
// when the model has any clip, and the label marks non-exact hits.
function mcGroup(mkey,ckpt){                     // -> {arr,mkey} of cells for a model-ckpt, or null
 if(!cellsByMC)return null;
 let arr=cellsByMC.get(mkey+'\x01'+ckpt);
 if(arr&&arr.length)return {arr,mkey};
 const sib=mkey.endsWith('_ptm')?mkey.slice(0,-4):mkey+'_ptm';   // last resort: cross the view toggle
 arr=cellsByMC.get(sib+'\x01'+ckpt);
 return (arr&&arr.length)?{arr,mkey:sib}:null;}
function resolveCell(mkey,ckpt,pid,cfg,w){
 const g=mcGroup(mkey,ckpt);if(!g)return null;
 let e=g.arr.find(c=>c.pid===pid&&c.cfg===cfg&&c.w===w);
 if(e)return {file:e.file,pid:e.pid,cfg:e.cfg,w:e.w,mkey:g.mkey,exact:true};
 const sp=g.arr.filter(c=>c.pid===pid);           // prefer the requested prompt; else any prompt
 const pool=(sp.length?sp:g.arr).slice()
   .sort((a,b)=>(Math.abs(a.cfg-cfg)-Math.abs(b.cfg-cfg))||(Math.abs(a.w-w)-Math.abs(b.w-w)));
 e=pool[0];return {file:e.file,pid:e.pid,cfg:e.cfg,w:e.w,mkey:g.mkey,exact:false};}
// NATIVE-LENGTH overlay (Kim 2026-08-02 spec): resolution always runs over the 20s universe
// (the densest grid); when the checkbox is on, swap in the native-length twin of the RESOLVED
// cell if one exists (terminal checkpoints only), else keep the 20s clip and say so. Returns
// {file,tag,nkey} -- nkey feeds playingKey so toggling the box mid-play re-resolves the src.
function nativeSwap(hit,ckpt){
 const base={file:hit.file,tag:'',nkey:''};
 if(!pnative.checked||!nativeIndex)return base;
 const nf=nativeIndex.get(cellKey(hit.mkey,ckpt,hit.pid,hit.cfg,hit.w));
 return nf?{file:nf,tag:' ·native',nkey:'\x01N'}:{file:hit.file,tag:' ·20s',nkey:''};}
// dim rows that have NO clip at the selected PROMPT (with graceful-resolve, cfg/w mismatch
// no longer means "unplayable" -- only a missing prompt is a meaningful "nothing here" signal).
function markAvailability(){
 if(!cellsByMC)return;
 const {pid}=currentSel();
 document.querySelectorAll('#body tr').forEach(tr=>{
  const g=mcGroup(modelKey(tr.dataset.model),tr.dataset.ckpt);
  const hasPrompt=g&&g.arr.some(c=>c.pid===pid);
  tr.classList.toggle('nomatch',!hasPrompt);});}
function markPlaying(){
 document.querySelectorAll('#body tr.playing').forEach(x=>x.classList.remove('playing'));
 if(!playingModel)return;
 document.querySelectorAll('#body tr').forEach(tr=>{
  if(tr.dataset.model===playingModel&&tr.dataset.ckpt===playingCkpt)tr.classList.add('playing');});}
function stopPlaying(){pl.pause();playingKey=playingModel=playingCkpt=null;
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
 if(!playingModel||pl.paused)return;                 // nothing playing -> just re-dim rows
 const {pid,cfg,w}=currentSel();
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
 const {pid,cfg,w}=currentSel();
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
pp.addEventListener('click',()=>{if(pl.paused){if(pl.src)pl.play()}else pl.pause()});
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
function buildCellsByMC(){
 cellsByMC=new Map();
 if(cellIndex)for(const [k,f] of cellIndex){const p=k.split('\x01');
  if(!inSet(p[0]))continue;                 // keep the picker index to the active set
  const g=p[0]+'\x01'+p[1];
  let a=cellsByMC.get(g);if(!a){a=[];cellsByMC.set(g,a);}
  a.push({pid:p[2],cfg:parseFloat(p[3]),w:parseFloat(p[4]),file:f});}}
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
 [...cfgSet].filter(v=>!HIDECFG.has(v)).sort((a,b)=>a-b).forEach(v=>pcfg.add(new Option('cfg '+v,v)));
 [...wSet].sort((a,b)=>a-b).forEach(v=>pstrength.add(new Option('w '+v,v)));
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
