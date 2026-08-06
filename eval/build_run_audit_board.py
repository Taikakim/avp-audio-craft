#!/usr/bin/env python3
"""Regeneratable RUN AUDIT BOARD for the SA3 LUMI training/render pipeline.

Reconciles three worlds for every LUMI run:
  (1) LUMI scratch ground-truth (hardcoded below -- the source of truth for what EXISTS on
      /scratch, since not everything is pulled locally and cannot be re-scanned);
  (2) the two local mirrors -- UUID (canonical, complete) and Mantu (redundant subset);
  (3) render + audit state -- render clips per set, analysis dirs, and each run_meta.json's
      kim_feedback (present => AUDITED, absent => the red-exclamation "unaudited" mark).

Emits a self-contained static HTML file (inline CSS, no external deps).

This is an INTERNAL OPS TRACKER, not a public eval page -- but it follows the same
UNAUDITED-until-kim_feedback convention (the red exclamation mark) used on the eval pages.

Usage:  /home/kim/Projects/SAO/.venv/bin/python eval/build_run_audit_board.py
Output: /run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/RUN_AUDIT_BOARD.html
CPU only; no torch, no GPU. Safe to re-run any time.
"""
import os, re, json, glob, html, datetime, sys, csv, argparse

# ---------------------------------------------------------------------------
# PUBLIC-SNAPSHOT redaction (Kim 2026-08-04): --public emits a second, path-redacted copy of
# the board so it can be hosted on aavepyora.online. Strips absolute local/infra paths per the
# MASTER §4 public-page rule (no absolute paths, no infra addresses, no secrets), then FAILS
# CLOSED if any known-sensitive token survives. The default (private) build never calls this.
DORA_BASE_URL_DEFAULT = "https://aavepyora.online/files/audit/dora_table.html"

# ordered (specific -> general); applied to the FINAL HTML string
_REDACTIONS = [
    ("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs", "the eval drive"),
    ("/run/media/kim/Mantu/lumi_runs", "the Mantu backup drive"),
]
_REDACT_RE = [
    (re.compile(r"/run/media/kim/[^\s\"'<>)]*"), "(local drive)"),
    (re.compile(r"/scratch/project_465003186[^\s\"'<>)]*"), "LUMI scratch"),
    (re.compile(r"/project/project_465003186[^\s\"'<>)]*"), "LUMI project"),
]
# residual tripwires -- if ANY of these survive redaction, refuse to write the public copy
_RESIDUAL = [r"/run/media", r"/home/kim", r"/scratch/project", r"/project/project",
             r"dreamhost", r"dh_4txyt6", r"akekim", r"efp\.lumi", r"csc\.fi", r"id_EFP"]


def redact_public(s):
    """Redact absolute local/infra paths from an HTML string, then assert nothing sensitive
    survives (fail closed). Returns the redacted string; raises SystemExit on a residual hit."""
    for a, b in _REDACTIONS:
        s = s.replace(a, b)
    for rx, repl in _REDACT_RE:
        s = rx.sub(repl, s)
    s = s.replace("/home/kim/Projects/SAO/", "")            # repo-root prefix -> empty
    s = re.sub(r"/home/kim[^\s\"'<>)]*", "(local path)", s)  # any other /home/kim... -> (local path)
    hits = [p for p in _RESIDUAL if re.search(p, s)]
    if hits:
        raise SystemExit(f"REDACTION FAILED (fail closed) -- residual sensitive tokens: {hits}")
    return s

# ---------------------------------------------------------------------------
# DoRA-rows cross-link (Kim 2026-08-04): each run that maps to a campaign FAMILY in the
# DoRA-rows table gets a link to that page pre-filtered to the family (?set=<name>). The set
# universe + membership come straight from the dora-table builder (same family() rule, same
# HIDE list, same CSV) so "set exists and is non-empty" is a real check, not a guess.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from build_dora_table_page import derive_model_sets, HIDE_MODEL_PREFIXES, AGG, OUT as DORA_OUT
    with open(AGG) as _f:
        _labels = sorted({r["model"] for r in csv.DictReader(_f)
                          if not r["model"].startswith(HIDE_MODEL_PREFIXES)})
    MODEL_SETS = derive_model_sets(_labels)
    DORA_PAGE = f"file://{DORA_OUT}"          # canonical page (OUT=ROOT/'dora_table.html')
except Exception as _e:                        # CSV/module missing -> no links (all show "—")
    MODEL_SETS, DORA_PAGE = {}, "file:///home/kim/Projects/SAO/eval/dora_table.html"
    print(f"WARN: MODEL_SETS unavailable ({_e}); DoRA links suppressed", file=sys.stderr)

# LUMI run key -> DoRA-rows campaign set. Only runs whose renders map to a real family are here;
# melody-wall grids / headb_melody / aug8_* / render jobs / hq_campaign have NO DoRA-table models.
# NOTE (deviations from the task's suggested dict, both toward the ACTUAL render family):
#   fp32_frames -> fp32frames (a distinct 'frames' family DOES exist; PREFIX_TO_RUN maps
#                  fp32frames_ -> fp32_frames), not fp32cmp.
#   fp32_winning -> winning   (its renders are winning_*; PREFIX_TO_RUN maps winning_ -> fp32_winning),
#                  not fp32cmp -- linking to fp32cmp would show the wrong models.
RUN_TO_SET = {
    "adamw_bf16_sweep":   "adamw",
    "bf16_twin":          "bf16cmp",
    "fp32_compare":       "fp32cmp",
    "fp32_frames":        "fp32frames",
    "fp32_winning":       "winning",
    "fullft":             "fullft",
    "longctx_t1024_r128": "longctx",
    "longctx_t2048_r128": "longctx",
    # melody-wall families (added 2026-08-05 once they had DoRA-table rows -- they were scored
    # that night: DSP + Audiobox + CLAP, which is what created the sets they point at. Before
    # scoring these legitimately showed "—", since derive_model_sets only sees models with rows).
    "x0equiv_grid":         "x0eq",
    "x0equiv_grid_mt":      "x0eq",
    "subspace_loss_grid":   "subloss",
    "subspace_loss_grid_mt": "subloss",
    "lr_equiv_grid":        "lreq",
    "lr_equiv_grid_mt":     "lreq",
}

def dora_link(run, page_base=None):
    """A 'DoRA rows ▸' link to the family-filtered table, or an em-dash when the run maps to no
    (existing, non-empty) family set. `page_base` overrides the link target (default = the local
    file:// DORA_PAGE); the public build passes the HOSTED dora_table URL instead."""
    s = RUN_TO_SET.get(run)
    if not s or not MODEL_SETS.get(s):
        return '<span class="n">&mdash;</span>'
    n = len(MODEL_SETS[s])
    href = f"{page_base or DORA_PAGE}?set={s}"
    return (f'<a class="dora" href="{esc(href)}" '
            f'title="open the DoRA-rows table filtered to the {esc(s)} set ({n} models)">'
            f'DoRA rows &#9656;</a>')

UUID_ROOT  = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs"
UUID_RUNS  = os.path.join(UUID_ROOT, "runs")
UUID_REND  = os.path.join(UUID_ROOT, "renders")
UUID_ANAL  = os.path.join(UUID_ROOT, "analysis")
MANTU_ROOT = "/run/media/kim/Mantu/lumi_runs"           # run dirs at TOP LEVEL here
OUT_HTML   = os.path.join(UUID_ROOT, "RUN_AUDIT_BOARD.html")

# ---------------------------------------------------------------------------
# GROUND TRUTH -- what exists on LUMI /scratch runs/ (from Kim). This is the
# authority for on_LUMI; local mirrors are a (possibly partial) projection of it.
# kind: training | render_job | encode | campaign | smoke
# ---------------------------------------------------------------------------
LUMI_RUNS = {
    "adamw_bf16_sweep": dict(task="DoRA-sweep", kind="training",
        desc="Length-variant AdamW DoRA bf16 sweep (avp/goa x bs1/bs4 x lr 5e-5/1e-4/2e-4, T512).",
        rendered="matrix_cells"),
    "aug8_encode": dict(task="#68", kind="encode", ckpts_lumi_only=True,
        desc="Augmentation encode pass -- produces aug latents; NO checkpoints.",
        rendered=None),
    "aug8_train_ddp": dict(task="#68", kind="training", ckpts_lumi_only=True,
        desc="DDP augmentation training -- checkpoints NOT pulled (stay on LUMI).",
        rendered=None),
    "bf16_twin": dict(task="#52", kind="training",
        desc="bf16 precision-twin arms for the fp32-vs-bf16 DoRA comparison (t512).",
        rendered=None),
    "fp32_compare": dict(task="#52", kind="training",
        desc="DoRA precision twins -- fp32 vs bf16 (the #52 precision comparison).",
        rendered="native_cells"),
    "fp32_frames": dict(task="#54", kind="training",
        desc="fp32 frame-length sweep (DoRA r128, fusion, fp32, T256..4096).",
        rendered="native_cells"),
    "fp32_winning": dict(task="#52/#54", kind="training",
        desc="fp32 winning-arms follow-on, continued toward ep20 (+alpha & bf16 twins, avpaug10).",
        rendered="matrix_cells"),
    "fullft": dict(task="#68", kind="training",
        desc="Earlier full-finetune batch -- all DiT weights trainable, T256..4096, avp/goa.",
        rendered="matrix_cells"),
    "fullft_cells_hq": dict(task="#57", kind="render_job", ckpts_lumi_only=True,
        desc="Native-cell HQ RENDER job (fullft models) -> native_cells. No own ckpts.",
        rendered="native_cells"),
    "fullft_mem_probe": dict(task="#68", kind="training", ckpts_lumi_only=True, disposable=True,
        desc="Full-FT memory probe -- disposable, passed (minimal provenance ok).",
        rendered=None),
    "headb_melody": dict(task="control", kind="training",
        desc="Melody-contour control adapter (head B). Has hand-written run_meta.",
        rendered="headb_bracket"),
    "longctx_t1024_r128": dict(task="#50", kind="training",
        desc="Long-context DoRA r128 at T=1024 (95.1s).",
        rendered=None),
    "longctx_t2048_r128": dict(task="#50", kind="training",
        desc="Long-context DoRA r128 at T=2048 (190.2s).",
        rendered="native_cells"),
    "lr_equiv_grid": dict(task="#59", kind="training", ckpts_lumi_only=True,
        desc="Melody-wall lr-equivalence grid. Ckpts stay on LUMI; renders in matrix_cells.",
        rendered="matrix_cells", analyzed="melody_wall"),
    "lr_equiv_grid_mt": dict(task="#59", kind="training", ckpts_lumi_only=True,
        desc="Melody-wall lr-equivalence grid (matched-training-length variant).",
        rendered="matrix_cells", analyzed="melody_wall"),
    "native_cells_hq": dict(task="#57", kind="render_job", ckpts_lumi_only=True,
        desc="Native-cell HQ RENDER job -> native_cells. No own ckpts.",
        rendered="native_cells"),
    "smoke_r256_a256_lr1e4_f512_bs8": dict(task="smoke", kind="smoke",
        desc="Pipeline smoke test (DoRA r256/a256, lr1e-4, T512, bs8, tiny budget). Disposable.",
        disposable=True, rendered=None),
    "subspace_loss_grid": dict(task="#59", kind="training", ckpts_lumi_only=True,
        desc="Melody-wall subspace-loss grid. Ckpts on LUMI; renders in matrix_cells.",
        rendered="matrix_cells", analyzed="melody_wall"),
    "subspace_loss_grid_mt": dict(task="#59", kind="training", ckpts_lumi_only=True,
        desc="Melody-wall subspace-loss grid (matched-training-length variant).",
        rendered="matrix_cells", analyzed="melody_wall"),
    "x0equiv_grid": dict(task="#59", kind="training", ckpts_lumi_only=True,
        desc="Melody-wall x0-equivalence grid. Ckpts on LUMI; renders in matrix_cells.",
        rendered="matrix_cells", analyzed="melody_wall"),
    "x0equiv_grid_mt": dict(task="#59", kind="training", ckpts_lumi_only=True,
        desc="Melody-wall x0-equivalence grid (matched-training-length variant).",
        rendered="matrix_cells", analyzed="melody_wall"),
    "hq_campaign_job1-109": dict(task="HQ", kind="campaign", ckpts_lumi_only=True,
        desc="HyperQueue campaign (job-1 .. job-109, ~100 tasks). NOT pulled locally -- "
             "cannot inspect. Represent as a single on-LUMI / needs-probe row.",
        rendered=None, needs_probe=True),
}

# prefix (field before first '__' in a render clip name) -> canonical run key
PREFIX_TO_RUN = [
    ("fp32frames_", "fp32_frames"),
    ("fp32cmp_",    "fp32_compare"),
    ("bf16cmp_",    "bf16_twin"),
    ("winning_",    "fp32_winning"),
    ("adamw_",      "adamw_bf16_sweep"),
    ("fullft_aug8ddp_", "aug8_train_ddp"),   # must precede the generic fullft_ entry below
    ("dora_aug8ddp_",   "aug8_train_ddp"),
    ("fullft_",     "fullft"),
    ("longctx_t1024", "longctx_t1024_r128"),
    ("longctx_t2048", "longctx_t2048_r128"),
    ("lreq_",       "lr_equiv_grid"),
    ("x0eq_",       "x0equiv_grid"),
    ("subloss_",    "subspace_loss_grid"),
    ("riffer",      "headb_melody"),
]

def resolve_prefix(pfx):
    for token, run in PREFIX_TO_RUN:
        if pfx.startswith(token):
            return run
    return None

# ---------------------------------------------------------------------------
# Filesystem scans
# ---------------------------------------------------------------------------
def check_mounts():
    for p in (UUID_RUNS, MANTU_ROOT):
        if not os.path.isdir(p):
            raise SystemExit(f"FATAL: mirror not mounted / missing: {p}  -- STOP.")

def _ckpts_in(dirpath):
    """Return (fat, slim, pt) checkpoint file lists in a single dir.
    Lightning: epoch=*.ckpt (fat) / epoch=*.weights.ckpt (slim).
    sa3_control: riffer_*.pt / *.pt dumps."""
    fat = [f for f in glob.glob(os.path.join(dirpath, "epoch=*.ckpt")) if not f.endswith(".weights.ckpt")]
    slim = glob.glob(os.path.join(dirpath, "epoch=*.weights.ckpt"))
    pt = glob.glob(os.path.join(dirpath, "*.pt"))
    return fat, slim, pt

def scan_run_dir(base, run):
    """Return dict for a run dir under `base`: present, ckpt counts, arms, metas, audited."""
    d = os.path.join(base, run)
    info = dict(present=False, fat=0, slim=0, pt=0, arms=0, metas=0, audited=0,
                meta_kim=[], arms_no_meta=[])
    if not os.path.isdir(d):
        return info
    info["present"] = True
    arm_dirs = [os.path.join(d, x) for x in sorted(os.listdir(d))
                if os.path.isdir(os.path.join(d, x)) and x != "lightning_logs"]
    top_fat, top_slim, top_pt = _ckpts_in(d)
    top_has_ckpts = bool(top_fat or top_slim or top_pt)
    top_has_meta = os.path.exists(os.path.join(d, "run_meta.json"))
    # targets = the dirs that behave as a "run unit" (carry ckpts + a meta)
    targets = []
    if top_has_ckpts or top_has_meta:
        targets.append(d)          # single-run dir (top-level ckpts/.pt or run-level meta)
    if arm_dirs and not (top_has_ckpts and not arm_dirs):
        targets += arm_dirs        # campaign arms
    seen = set()
    for t in targets:
        if t in seen:
            continue
        seen.add(t)
        fat, slim, pt = _ckpts_in(t)
        info["fat"] += len(fat); info["slim"] += len(slim); info["pt"] += len(pt)
        has_ckpts = bool(fat or slim or pt)
        if t != d:
            info["arms"] += 1
        mp = os.path.join(t, "run_meta.json")
        if os.path.exists(mp):
            info["metas"] += 1
            try:
                m = json.load(open(mp))
                if m.get("kim_feedback"):
                    info["audited"] += 1
                    info["meta_kim"].append((os.path.basename(t), m["kim_feedback"]))
            except Exception:
                pass
        elif has_ckpts:   # ckpt-bearing dir with no run_meta = missing provenance
            info["arms_no_meta"].append(os.path.basename(t))
    return info

def scan_renders():
    """clips per set + per-run attribution from filename prefixes."""
    sets = {}
    per_run = {}   # run -> {set: count}
    # native_cells_BROKEN_120s_window is intentionally excluded (superseded / ignore).
    for setname in ("matrix_cells", "native_cells", "headb_bracket"):
        sd = os.path.join(UUID_REND, setname)
        if not os.path.isdir(sd):
            continue
        wavs = glob.glob(os.path.join(sd, "*.wav"))
        # headb_bracket stores clips in per-ckpt SUBDIRS (subdir/renders/*.wav)
        if not wavs:
            wavs = glob.glob(os.path.join(sd, "**", "*.wav"), recursive=True)
        sets[setname] = len(wavs)
        for w in wavs:
            pfx = os.path.basename(w).split("__")[0]
            run = resolve_prefix(pfx)
            if run:
                per_run.setdefault(run, {}).setdefault(setname, 0)
                per_run[run][setname] += 1
    return sets, per_run

def scan_analysis():
    dirs = {}
    if os.path.isdir(UUID_ANAL):
        for x in sorted(os.listdir(UUID_ANAL)):
            p = os.path.join(UUID_ANAL, x)
            if os.path.isdir(p):
                purpose = ""
                for cand in ("run_meta.json", "_meta.json", "sidecar.json", "summary.json"):
                    cp = os.path.join(p, cand)
                    if os.path.exists(cp):
                        try:
                            purpose = json.load(open(cp)).get("purpose", "") or ""
                        except Exception:
                            pass
                        if purpose:
                            break
                dirs[x] = purpose
    return dirs

# analysis dir -> which runs it pertains to (for the per-run "Analyzed" column)
ANALYSIS_TO_RUNS = {
    "melody_wall": ["subspace_loss_grid", "subspace_loss_grid_mt", "x0equiv_grid",
                    "x0equiv_grid_mt", "lr_equiv_grid", "lr_equiv_grid_mt"],
    "precision_weight_diff_5400": ["fp32_compare", "bf16_twin"],
    "precision_injection_ab": ["fp32_compare"],
    "update_disappearance": ["fp32_compare", "bf16_twin"],
}

# ---------------------------------------------------------------------------
# Build rows
# ---------------------------------------------------------------------------
def build():
    check_mounts()
    rend_sets, rend_per_run = scan_renders()
    anal_dirs = scan_analysis()
    run_to_analysis = {}
    for adir, runs in ANALYSIS_TO_RUNS.items():
        if adir in anal_dirs:
            for r in runs:
                run_to_analysis.setdefault(r, []).append(adir)

    rows = []
    left_to_audit, left_to_pull, no_provenance = [], [], []

    for run, gt in LUMI_RUNS.items():
        u = scan_run_dir(UUID_RUNS, run)
        m = scan_run_dir(MANTU_ROOT, run)
        rendered = rend_per_run.get(run, {})
        rendered_sets = ", ".join(f"{s} ({n})" for s, n in sorted(rendered.items())) or ""
        if not rendered_sets and gt.get("rendered"):
            # ground-truth says rendered but no prefix-attributed clips (e.g. _mt folded into base)
            rendered_sets = f"{gt['rendered']} (folded/shared prefix)" if gt["kind"]=="training" else gt["rendered"]
        analyzed = run_to_analysis.get(run, [])
        if not analyzed and gt.get("analyzed"):
            analyzed = [gt["analyzed"]]
        analyzed_str = ", ".join(analyzed)

        ckpt_count = u["fat"] + u["slim"] + u["pt"]
        audited = u["audited"] > 0 or bool(m["audited"])
        # provenance = every ckpt-bearing local unit has a run_meta.json
        has_local_ckpts = ckpt_count > 0
        missing_prov = u["arms_no_meta"] if has_local_ckpts else []
        has_renders = bool(rendered)

        # AUDITED semantics: disposable/smoke/encode/render_job/campaign don't need Kim's ears
        needs_ears = gt["kind"] in ("training",) and not gt.get("disposable")
        if needs_ears and not audited and (has_local_ckpts or has_renders or gt.get("ckpts_lumi_only")):
            left_to_audit.append((run, gt))
        # LEFT TO PULL: on LUMI, artifacts exist there, not pulled to UUID (skip disposables)
        ckpts_lumi_only = gt.get("ckpts_lumi_only", False)
        if (ckpts_lumi_only or gt.get("needs_probe")) and not u["present"] and not gt.get("disposable"):
            left_to_pull.append((run, gt))
        if missing_prov:
            no_provenance.append((run, missing_prov))

        rows.append(dict(
            run=run, gt=gt,
            uuid=u, mantu=m,
            ckpt_count=ckpt_count,
            rendered=rendered_sets,
            analyzed=analyzed_str,
            audited=audited,
            audited_verdicts=u["meta_kim"] + m["meta_kim"],
            missing_prov=missing_prov,
        ))
    return rows, rend_sets, anal_dirs, left_to_audit, left_to_pull, no_provenance

# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
def esc(x):
    return html.escape(str(x)) if x is not None else ""

def yn(b, yes="yes", no="no"):
    return (f'<span class="y">{yes}</span>' if b else f'<span class="n">{no}</span>')

def render_html(rows, rend_sets, anal_dirs, left_audit, left_pull, no_prov,
                public=False, dora_base=None):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    tracker_label = ("internal ops tracker &middot; public snapshot (paths redacted)"
                     if public else "internal ops tracker")
    dora_page_base = dora_base if public else None
    total = len(rows)
    n_aud = sum(1 for r in rows if r["audited"])
    n_unaud = sum(1 for r in rows if not r["audited"] and r["gt"]["kind"]=="training" and not r["gt"].get("disposable"))
    n_noprov = len(no_prov)

    P = []
    P.append(f"""<title>SA3 LUMI Run Audit Board</title>
<style>
:root{{color-scheme:light}}
*{{box-sizing:border-box}}
body{{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;background:#f4f5f7;color:#1b1f24;line-height:1.45}}
.wrap{{max-width:100%;padding:22px 26px}}
h1{{margin:0 0 4px;font-size:22px}}
h2{{margin:26px 0 8px;font-size:16px;border-bottom:2px solid #d7dbe0;padding-bottom:4px}}
.sub{{color:#5a636e;font-size:13px;margin-bottom:14px}}
.legend{{background:#fff;border:1px solid #e0e4e8;border-radius:8px;padding:12px 16px;font-size:13px;margin-bottom:8px}}
.legend code{{background:#eef0f2;padding:1px 5px;border-radius:4px}}
.bang{{color:#c0392b;font-weight:700}}
.pill{{display:inline-block;padding:1px 7px;border-radius:10px;font-size:11px;font-weight:600}}
.pill.audited{{background:#d6f0dc;color:#1e6b34}}
.pill.unaud{{background:#fbe1de;color:#a5281b}}
.pill.na{{background:#e7eaee;color:#5a636e}}
.stats{{display:flex;gap:14px;flex-wrap:wrap;margin:10px 0 4px}}
.stat{{background:#fff;border:1px solid #e0e4e8;border-radius:8px;padding:8px 14px;font-size:13px}}
.stat b{{font-size:19px;display:block}}
.tblwrap{{overflow-x:auto;border:1px solid #dfe3e7;border-radius:8px;background:#fff}}
table{{border-collapse:collapse;width:100%;font-size:12.5px}}
th,td{{padding:6px 9px;text-align:left;border-bottom:1px solid #eceef1;vertical-align:top;white-space:nowrap}}
th{{background:#eef1f4;position:sticky;top:0;font-weight:600}}
td.desc{{white-space:normal;min-width:280px;color:#41474e;font-size:11.5px}}
tr:hover td{{background:#f7f9fb}}
.y{{color:#1e7d3a;font-weight:600}}
.n{{color:#9aa2ab}}
.kind{{font-size:10.5px;color:#6a7480;text-transform:uppercase;letter-spacing:.3px}}
.mono{{font-family:ui-monospace,Menlo,Consolas,monospace}}
a.dora{{color:#2c6fbb;text-decoration:none;font-weight:600;font-size:11.5px;white-space:nowrap}}
a.dora:hover{{text-decoration:underline}}
.actions{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}}
.card{{background:#fff;border:1px solid #e0e4e8;border-radius:8px;padding:12px 16px}}
.card.audit{{border-top:3px solid #c0392b}}
.card.pull{{border-top:3px solid #2c6fbb}}
.card.prov{{border-top:3px solid #7a53b5}}
.card h3{{margin:0 0 8px;font-size:14px}}
.card ul{{margin:0;padding-left:18px;font-size:12.5px}}
.card li{{margin:3px 0}}
.empty{{color:#1e7d3a;font-size:12.5px}}
.verdict{{white-space:normal;font-size:11px;color:#356}}
footer{{margin-top:26px;color:#8a929c;font-size:11.5px}}
</style>
<div class="wrap">
<h1>SA3 LUMI Run Audit Board <span class="kind">{tracker_label}</span></h1>
<div class="sub">Reconciles LUMI /scratch ground-truth vs the two local mirrors (UUID canonical, Mantu subset) vs render/audit state. Generated {now} by <code>eval/build_run_audit_board.py</code> &mdash; re-run any time.</div>

<div class="legend">
<b>How to read this board.</b> Each row is one LUMI run (or run-family). <b>on-LUMI</b> = it exists on /scratch (ground truth &mdash; hardcoded, since not everything is pulled locally). <b>UUID / Mantu</b> = whether the run dir is mirrored to each local drive (UUID is canonical/complete; Mantu is a redundant subset). <b>ckpts</b> = checkpoint files present on UUID (fat + slim). <b>Rendered</b> = which render set holds this run's audition clips (attributed by filename prefix). <b>Analyzed</b> = which <code>analysis/</code> dir studied it. <b>DoRA</b> = link to the DoRA-rows metric table pre-filtered to this run's campaign family (<code>&mdash;</code> when the run has no DoRA-table models).
<b>Audited</b>: a run is AUDITED only once its <code>run_meta.json</code> carries a <code>kim_feedback</code> verdict &mdash; until then it shows the red <span class="bang">&#10071;</span> (Kim hasn't listened yet). Disposable/smoke/encode/render-job/campaign rows don't need Kim's ears, shown <span class="pill na">n/a</span>.
</div>

<div class="stats">
<div class="stat"><b>{total}</b> runs tracked</div>
<div class="stat"><b>{n_aud}</b> audited</div>
<div class="stat"><b class="bang">{n_unaud}</b> &#10071; awaiting Kim's ears</div>
<div class="stat"><b>{n_noprov}</b> runs missing provenance</div>
</div>
""")

    # ---- main table
    P.append('<h2>Reconciliation table</h2><div class="tblwrap"><table>')
    P.append("<tr><th>Run</th><th>Task</th><th>Kind</th><th>on-LUMI</th><th>UUID</th><th>Mantu</th>"
             "<th>ckpts</th><th>Rendered</th><th>Analyzed</th><th>DoRA</th><th>Audited</th><th>What it is</th></tr>")
    for r in rows:
        gt = r["gt"]; run = r["run"]
        needs_ears = gt["kind"] == "training" and not gt.get("disposable")
        if not needs_ears:
            aud_cell = '<span class="pill na">n/a</span>'
        elif r["audited"]:
            aud_cell = '<span class="pill audited">AUDITED</span>'
        else:
            aud_cell = '<span class="pill unaud">&#10071; UNAUD</span>'
        uuid_cell = yn(r["uuid"]["present"])
        if r["uuid"]["present"] and r["uuid"]["arms"]:
            uuid_cell += f' <span class="n">({r["uuid"]["arms"]} arms)</span>'
        mantu_cell = yn(r["mantu"]["present"])
        ck = r["ckpt_count"]
        u = r["uuid"]
        parts = []
        if u["fat"]: parts.append(f'{u["fat"]}f')
        if u["slim"]: parts.append(f'{u["slim"]}s')
        if u["pt"]: parts.append(f'{u["pt"]}pt')
        ckcell = (f'{ck} <span class="n">({"/".join(parts)})</span>'
                  if ck else ('<span class="n">LUMI-only</span>' if gt.get("ckpts_lumi_only") else '<span class="n">0</span>'))
        prov_flag = ' <span class="bang" title="ckpt dir(s) without run_meta.json">&#10071;prov</span>' if r["missing_prov"] else ""
        P.append("<tr>"
                 f'<td class="mono"><b>{esc(run)}</b>{prov_flag}</td>'
                 f'<td>{esc(gt["task"])}</td>'
                 f'<td class="kind">{esc(gt["kind"])}</td>'
                 f'<td>{yn(True)}</td>'
                 f'<td>{uuid_cell}</td>'
                 f'<td>{mantu_cell}</td>'
                 f'<td>{ckcell}</td>'
                 f'<td>{esc(r["rendered"]) or "<span class=\'n\'>&mdash;</span>"}</td>'
                 f'<td>{esc(r["analyzed"]) or "<span class=\'n\'>&mdash;</span>"}</td>'
                 f'<td>{dora_link(run, dora_page_base)}</td>'
                 f'<td>{aud_cell}</td>'
                 f'<td class="desc">{esc(gt["desc"])}</td>'
                 "</tr>")
    P.append("</table></div>")

    # ---- render sets summary
    P.append('<h2>Render sets (clip tallies)</h2><div class="legend">')
    P.append(" &nbsp; ".join(f'<b>{esc(k)}</b>: {v} clips' for k, v in sorted(rend_sets.items())))
    P.append('<br><span class="n">Clip = one <code>.wav</code>. matrix_cells is the shared model-matrix board fed by many runs; native_cells = #57 native-length HQ cells; headb_bracket = headb_melody control render.</span></div>')

    # ---- analysis dirs
    P.append('<h2>Analysis dirs</h2><div class="tblwrap"><table><tr><th>dir</th><th>purpose</th></tr>')
    for k, v in anal_dirs.items():
        P.append(f'<tr><td class="mono">{esc(k)}</td><td class="desc">{esc(v)}</td></tr>')
    P.append("</table></div>")

    # ---- action lists
    P.append('<h2>Prioritized action lists</h2><div class="actions">')

    P.append('<div class="card audit"><h3>&#10071; LEFT TO AUDIT (Kim\'s ears)</h3>')
    if left_audit:
        P.append("<ul>")
        for run, gt in left_audit:
            P.append(f'<li class="mono">{esc(run)} <span class="n">[{esc(gt["task"])}] &mdash; {esc(gt["desc"][:70])}</span></li>')
        P.append("</ul>")
    else:
        P.append('<div class="empty">None &mdash; every training run has a kim_feedback verdict.</div>')
    P.append("</div>")

    P.append('<div class="card pull"><h3>LEFT TO PULL (on LUMI, not on UUID)</h3>')
    if left_pull:
        P.append("<ul>")
        for run, gt in left_pull:
            note = "needs probe" if gt.get("needs_probe") else "ckpts LUMI-only"
            P.append(f'<li class="mono">{esc(run)} <span class="n">[{esc(gt["task"])}] &mdash; {note}</span></li>')
        P.append("</ul>")
    else:
        P.append('<div class="empty">None outstanding.</div>')
    P.append('<div class="n" style="font-size:11px;margin-top:6px">Note: #59 melody-wall grids &amp; render-jobs are intentionally ckpts-LUMI-only (renders pulled, checkpoints stay on scratch). The HyperQueue campaign needs a probe before deciding what to pull.</div>')
    P.append("</div>")

    P.append('<div class="card prov"><h3>NO PROVENANCE (should be 0)</h3>')
    if no_prov:
        P.append("<ul>")
        for run, arms in no_prov:
            P.append(f'<li class="mono">{esc(run)} <span class="n">&mdash; {len(arms)} ckpt dir(s) w/o run_meta.json</span></li>')
        P.append("</ul>")
    else:
        P.append('<div class="empty">None &mdash; every pulled ckpt-bearing dir carries a run_meta.json.</div>')
    P.append("</div>")

    P.append("</div>")  # actions

    P.append(f'<footer>Source of truth for on-LUMI = the hardcoded LUMI_RUNS list in the builder. UUID root: <span class="mono">{esc(UUID_ROOT)}</span> &middot; Mantu subset: <span class="mono">{esc(MANTU_ROOT)}</span>.</footer>')
    P.append("</div>")
    return "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>" + P[0] + "</head><body>" + "".join(P[1:]) + "</body></html>"

def main():
    ap = argparse.ArgumentParser(description="Build the SA3 LUMI run-audit board.")
    ap.add_argument("--public", action="store_true",
                    help="ALSO emit a path-redacted RUN_AUDIT_BOARD_public.html for hosting on "
                         "aavepyora.online (private default output is unchanged).")
    ap.add_argument("--dora-base-url", default=DORA_BASE_URL_DEFAULT,
                    help="hosted dora_table URL the public board's DoRA-rows links point at "
                         f"(default: {DORA_BASE_URL_DEFAULT}).")
    args = ap.parse_args()

    rows, rend_sets, anal_dirs, la, lp, npv = build()

    # ---- private (default) build -- byte-identical to pre-change output
    doc = render_html(rows, rend_sets, anal_dirs, la, lp, npv)
    with open(OUT_HTML, "w") as f:
        f.write(doc)
    print(f"wrote {OUT_HTML} ({len(doc)} bytes)")
    print(f"runs={len(rows)}  render_sets={rend_sets}")
    print(f"LEFT TO AUDIT ({len(la)}): {[r for r,_ in la]}")
    print(f"LEFT TO PULL  ({len(lp)}): {[r for r,_ in lp]}")
    print(f"NO PROVENANCE ({len(npv)}): {[r for r,_ in npv]}")

    # ---- public build (opt-in) -- redacted copy + hosted DoRA links
    if args.public:
        pdoc = render_html(rows, rend_sets, anal_dirs, la, lp, npv,
                           public=True, dora_base=args.dora_base_url)
        pdoc = redact_public(pdoc)
        pub_path = os.path.join(os.path.dirname(OUT_HTML), "RUN_AUDIT_BOARD_public.html")
        with open(pub_path, "w") as f:
            f.write(pdoc)
        print(f"wrote {pub_path} ({len(pdoc)} bytes)  [public: paths redacted, "
              f"DoRA links -> {args.dora_base_url}?set=...]")

if __name__ == "__main__":
    main()
