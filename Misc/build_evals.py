#!/usr/bin/env python3
"""build_evals.py — turn the served eval dumps into described, playable pages.

Reads the AAC staging (~/.cache/evals_aac/{control_runs,renders}) + the run
descriptions (riffer-evals/run_purposes.json), and writes a MIRROR under
site/evals/ containing ONLY index.html files (+ one CSS), self-contained
(inline CSS derived from edg3.css, so it survives any served layout):

  site/evals/index.html                         — the landing: every run/set described
  site/evals/control_runs/<run>/index.html       — same-playhead player for that folder
  site/evals/renders/<set>/index.html            — same-playhead player for that folder

Each per-folder index.html references its sibling *.m4a by filename, so WINTERMUTE
rsyncs the mirror over /files/evals/ (merging index.html into the existing clip
folders — clips untouched) and every folder becomes a player instead of a dump.

Same-playhead behaviour (MASTER §4): click a cell to play from the shared playhead;
switching cells keeps the position; re-click stops.
"""
import os, glob, json, html, shutil, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_grid

HOME = os.path.expanduser("~")
STAGING = f"{HOME}/.cache/evals_aac"

def _resolve_mantu():
    """The removable drive can remount under a different udisks2 id after a drop
    (Mantu -> Mantu1, etc. — MASTER §2's 'if a path 404s, the drive is unmounted,
    not gone', now also true of the mount NAME). Probe candidates in order, pick
    the first that's actually readable (an I/O-erroring stale mount entry can
    still exist as a directory, so os.path.isdir alone isn't enough)."""
    for cand in ("/run/media/kim/Mantu", "/run/media/kim/Mantu1"):
        try:
            os.listdir(cand)
            return cand
        except OSError:
            continue
    return "/run/media/kim/Mantu"  # nothing readable; keep the canonical name so errors are legible

MANTU = _resolve_mantu()
# where a control_runs/<name> folder's REAL source lives (staging is a redacted+
# transcoded copy whose mtimes are all transcode-day, not run-day)
SOURCE_DIRS = [f"{MANTU}/sa3_control_runs", f"{MANTU}/sa3_control_runs/composed_sweep", f"{MANTU}/sa3_lora_runs"]
SA3 = f"{HOME}/Projects/SAO/stable-audio-3"
# where a renders/<name> folder's REAL source lives (raw wavs + pq_scores.json/
# quality_eval.json; the staging copy under STAGING/renders/<name> only has the
# transcoded .m4a clips, no metrics json)
RENDERS_SOURCE_DIRS = [f"{SA3}/renders_dora", f"{SA3}/renders_dora2", f"{SA3}/renders_soups",
                       f"{SA3}/renders_dora_caut", f"{SA3}/renders_soups_caut"]
# Write the players + landing INTO the staging, colocated with the clips, so
# WINTERMUTE's existing rsync of ~/.cache/evals_aac -> /files/evals brings them
# live automatically. index.html/evals.css are additive; clips are never touched.
# Run AFTER the transcode (or fold into that pipeline) so a rebuild doesn't clobber.
OUT = STAGING
PURP = {}
try:
    PURP = json.load(open(f"{HOME}/riffer-evals/run_purposes.json"))
except Exception:
    pass

# ── redaction seam (CONTINUITY, SPEC §4) — sidecars carry ckpt names/paths/configs
# and stay LOCAL; anything rendered into PUBLIC html is scrubbed here at render time.
_ABS  = re.compile(r'/(?:home|run|opt|mnt|root|var|tmp|Users)/[^\s"<>]*')
_CKPT = re.compile(r'\b[\w.\-/]+\.(?:pt|ckpt|safetensors|pth)\b')
_ADDR = re.compile(r'\b(?:(?:\d{1,3}\.){3}\d{1,3}|localhost)(?::\d+)?\b')
_VENV = re.compile(r'[\w.\-/]*\.venv[\w.\-/]*')
def redact(s):
    s = _ABS.sub('…', str(s)); s = _CKPT.sub('[checkpoint]', s)
    s = _ADDR.sub('[addr]', s); s = _VENV.sub('[venv]', s)
    return s

# The 8 curated riffer-evals pages linked from the landing's "Curated players"
# section. Their source of truth is ~/riffer-evals/ (a separate git repo, built
# by its own ~/build_*.py generators) -- main() copies them + sync_riffer_clips()
# below into OUT/riffer/ on every run so the landing's relative links actually
# resolve, both locally (file://) and once WINTERMUTE rsyncs OUT to the server.
RIFFER_HTML = ["onset_eval.html", "disentangle.html", "dora_results.html",
               "chroma_steer.html", "gain_knee.html", "mp.html", "traj.html",
               "latch_sweep.html"]

CSS = """:root{--paper:#fafaf7;--paper-dim:#f2f3ef;--ink:#2b3538;--body:#3b4649;
--dim:#7a8a8e;--faint:#9aa7a9;--rule:#c9d2d0;--rule-light:#e2e6e2;--edge:#0f9e99;--edge-ink:#0c807c;
--mono:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace}
*{box-sizing:border-box}html{background:var(--paper)}
body{margin:0;color:var(--body);font-family:var(--mono);font-size:13px;line-height:1.7}
.wrap{max-width:900px;margin:0 auto;padding:34px 28px 72px}
a{color:var(--edge-ink);text-decoration:underline;text-decoration-style:dotted;text-underline-offset:3px}
a:hover{text-decoration-style:solid}
.over{margin:0;font-size:11px;letter-spacing:.45em;color:var(--faint)}
h1{font-size:20px;line-height:1.3;color:var(--ink);margin:18px 0 6px}
h2{font-size:12px;letter-spacing:.3em;text-transform:uppercase;color:var(--ink);
margin:40px 0 14px;padding-bottom:6px;border-bottom:1px solid var(--rule)}
h2 .mark{color:var(--edge)}
.lede{font-size:14px;color:var(--ink)}.dim{color:var(--dim)}.faint{color:var(--faint)}
.nav{margin:14px 0 0;padding-bottom:10px;border-bottom:1px solid var(--rule);font-size:11.5px;color:var(--dim)}
.nav a{color:var(--dim);text-decoration:none;margin-right:16px}.nav a:hover{color:var(--edge-ink)}
code{background:var(--paper-dim);border:1px solid var(--rule-light);padding:1px 5px;font-size:12px}
.run{border:1px solid var(--rule);border-top:3px solid var(--edge);padding:12px 16px;margin:0 0 12px;background:#fff}
.run .name{font-size:13px;font-weight:600;color:var(--ink)}
.run .when{font-size:10.5px;color:var(--faint);margin:1px 0 5px}
.run .desc{font-size:11.5px;color:var(--body);margin:3px 0 4px}
.run .verdict{font-size:11.5px;color:var(--edge-ink);margin:0 0 6px}
.run .meta{font-size:11px;color:var(--faint)}
.grid{display:flex;flex-wrap:wrap;gap:7px;margin:10px 0}
.cell{font-family:var(--mono);font-size:11px;color:var(--body);background:var(--paper-dim);
border:1px solid var(--rule);padding:6px 10px;cursor:pointer;border-radius:2px}
.cell:hover{border-color:var(--edge)}
.cell.playing{background:var(--edge);color:#fff;border-color:var(--edge)}
footer{margin-top:48px;padding-top:14px;border-top:1px solid var(--rule);font-size:11px;color:var(--faint)}
"""

PLAYER_JS = """<audio id="pl"></audio><script>
let cur=null,ph=0;const a=document.getElementById('pl');
a.addEventListener('timeupdate',()=>{if(!a.paused)ph=a.currentTime});
a.addEventListener('ended',()=>{if(cur){cur.classList.remove('playing');cur=null}});
function seekAndPlay(pos){
 // seeking as soon as loadedmetadata fires can land on a not-yet-buffered part
 // of the compressed stream and glitch right at playback start (Kim, 2026-07-07)
 const go=()=>{try{a.currentTime=Math.min(pos,(a.duration||1e9)-0.05)}catch(e){}a.play()};
 if(a.readyState>=3){go();return}
 let done=false;const fire=()=>{if(done)return;done=true;go()};
 a.addEventListener('canplay',fire,{once:true});setTimeout(fire,1200)}
function play(el){const s=el.dataset.src;
 if(cur===el){a.pause();el.classList.remove('playing');cur=null;return}
 if(cur)cur.classList.remove('playing');
 a.pause();a.src=s;seekAndPlay(ph);
 cur=el;el.classList.add('playing')}
</script>"""

def head(title, depth):
    css_ref = "../" * depth + "evals.css" if depth else "evals.css"
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title>'
            f'<link rel="preconnect" href="https://fonts.googleapis.com">'
            f'<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">'
            f'<link rel="stylesheet" href="{css_ref}"></head><body><div class="wrap">'
            f'<p class="over">VIBE ON THE EDG3 · EVALS</p>')

def real_date(kind, name):
    """Best-effort 'when did this run actually happen' — earliest mtime among files
    in the REAL source dir on Mantu, excluding run_meta.json (that sidecar is often a
    later provenance BACKFILL onto pre-existing dirs, per MASTER's eval-provenance
    note, so its mtime is import day, not run day). Falls back to the staged copy's
    own dir mtime (transcode day — less meaningful, but honest about what's known)."""
    if kind == "control_runs":
        for root in SOURCE_DIRS:
            d = f"{root}/{name}"
            if os.path.isdir(d):
                times = []
                for f in os.listdir(d):
                    if f == "run_meta.json":
                        continue
                    try:
                        times.append(os.path.getmtime(f"{d}/{f}"))
                    except OSError:
                        pass
                if times:
                    return min(times)
    if kind == "renders":
        d = find_renders_source_dir(name)
        if d:
            times = []
            for f in glob.glob(f"{d}/**/*", recursive=True):
                if os.path.basename(f) in ("run_meta.json", "_meta.json", "pq_scores.json", "quality_eval.json"):
                    continue
                try:
                    times.append(os.path.getmtime(f))
                except OSError:
                    pass
            if times:
                return min(times)
    try:
        return os.path.getmtime(f"{STAGING}/{kind}/{name}")
    except OSError:
        return None

RENDERS_SOURCE_ROOTS = [f"{MANTU}/sa3_lora_runs"]  # root+name join, like SOURCE_DIRS -- new
# sa3_lora_runs-hosted render sets (e.g. newcap8_promptstyle) resolve here without
# needing a new hardcoded entry per eval.

def find_renders_source_dir(name):
    """RENDERS_SOURCE_DIRS entry whose basename matches name, else a
    RENDERS_SOURCE_ROOTS/<name> join, else None."""
    for d in RENDERS_SOURCE_DIRS:
        if os.path.basename(d.rstrip("/")) == name and os.path.isdir(d):
            return d
    for root in RENDERS_SOURCE_ROOTS:
        d = f"{root}/{name}"
        if os.path.isdir(d):
            return d
    return None

def find_source_dir(name):
    """First SOURCE_DIRS/<name> that exists on Mantu, or None."""
    for root in SOURCE_DIRS:
        d = f"{root}/{name}"
        if os.path.isdir(d):
            return d
    return None

def fmt_date(ts):
    if ts is None:
        return ""
    import datetime
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")

def onset_verdict(kind, name):
    """Plain-language read of a real onset_eval.json {gain,requested,measured} sweep
    (Mantu-only — never copied to staging). Pearson r between requested and measured,
    banded into an honest sentence; explicitly surfaces weak/no-control outcomes
    rather than only ever reporting wins."""
    if kind != "control_runs":
        return None
    for root in SOURCE_DIRS:
        p = f"{root}/{name}/onset_eval.json"
        if os.path.exists(p):
            try:
                entries = json.load(open(p))
            except Exception:
                return None
            reqs = [e["requested"] for e in entries if "requested" in e and "measured" in e]
            meas = [e["measured"] for e in entries if "requested" in e and "measured" in e]
            n = len(reqs)
            if n < 3:
                return None
            mr, mm = sum(reqs) / n, sum(meas) / n
            cov = sum((r - mr) * (m - mm) for r, m in zip(reqs, meas))
            vr = sum((r - mr) ** 2 for r in reqs)
            vm = sum((m - mm) ** 2 for m in meas)
            if vr == 0 or vm == 0:
                return "flat response — the measured value never moved across the sweep."
            corr = cov / (vr * vm) ** 0.5
            if corr >= 0.85:
                return f"strong control — measured output tracked the request closely (r={corr:.2f})."
            if corr >= 0.5:
                return f"moderate control — output followed the request loosely (r={corr:.2f})."
            if corr >= 0.15:
                return f"weak control — barely tracked the request (r={corr:.2f})."
            return f"little to no control — output didn't follow the request (r={corr:.2f})."
    return None

# ── curated plain-language pairs (subtitle, verdict) for the well-documented
# campaigns — hand-written from WORKLOG/run_purposes.json so laypeople get the real
# story, wins AND partial/failed results alike. Matched by substring against the
# folder name (case-insensitive); first match wins.
CURATED = [
    ("opb_10ep", "Early test: does a tempo-invariant control target kill the "
     "'just play faster' cheat the onset-density heads had learned?",
     "Confirmed the cheat was dead, but control itself was still weak (+0.37 correlation) "
     "— a partial result that motivated the longer follow-up run below."),
    ("opb", "Does a tempo-invariant control target kill the 'just play faster' cheat?",
     "Yes. Control strengthened from +0.29 to +0.96 correlation over training while the "
     "tempo-cheat stayed dead the whole time. A clean success."),
    ("lr2e5", "Long, low-learning-rate training run for onset-density control.",
     "The team's favourite by ear — not the top scorer on paper, but closest to the "
     "target sound. A case where the numbers and the ears didn't fully agree."),
    ("lr8e5", "Higher learning-rate variant, probing for faster control authority.",
     "Exploratory step in a larger sweep — no standalone verdict, judged against its siblings."),
    ("adamw_lr7.5e-5_continuous", "Crop-mode test: fixed continuous crops instead of random ones.",
     "Ablation only — compared against the random-crop sibling run, no standalone verdict."),
    ("adamw_lr7.5e-5_randomcrop_20ep", "AdamW baseline to 20 epochs, with full training telemetry.",
     "Reference run used to cross-check training behaviour against control quality, not "
     "itself a pass/fail test."),
    ("adamw_lr7.5e-5_randomcrop", "AdamW baseline with random-crop augmentation.",
     "Comparator run — no standalone verdict; judged against its siblings in the sweep."),
    ("adamw_lr1e-4", "AdamW at a higher learning rate.", None),
    ("fusioncaut", "Fusion optimizer with the 'cautious' masking variant, onset-density control.",
     "The cautious-masking mechanism turned out to scramble per-coordinate gradient "
     "signs almost randomly (keep-fraction ≈0.53) — one run under this recipe NaN'd "
     "outright from a hidden +37% gradient-norm inflation. A genuine, useful failure: "
     "it's why 'cautious' masking isn't the default recipe."),
    ("fusion_lr1e-4_randomcrop", "Fusion optimizer at a higher learning rate, random-crop training.",
     "Optimizer/LR comparison against the AdamW baselines — no standalone verdict."),
    ("targeted", "Grab-bag of one-off checks: gain-range probes, model-soup tests, fixed-config renders.",
     "A bucket of small checks, not one experiment — see WORKLOG for any individual result."),
    ("collapse", "Deliberately pushed a checkpoint past its healthy training window.",
     "Confirmed collapse — quality degrades as expected once training overshoots. "
     "A negative result kept on record on purpose."),
    ("es_conditioner", "Gradient-free (evolutionary) search for a control conditioner, "
     "judged against real rendered audio.",
     "An early attempt in an ongoing line — instructive rather than final; later "
     "iterations superseded it."),
    ("flowsep", "Text-prompted 'separation' via FlowEdit — asking the model to isolate "
     "a sound without ever training it to do so.",
     "Works well at moderate guidance strength; the published state-of-the-art path "
     "for this model. Not a mask — it re-synthesises, so it shines on open-vocabulary "
     "asks ('the acid lead') rather than clean stems."),
    ("zerosep", "Text-prompted separation via true flow-inversion (round-trip the audio "
     "through the model and back).",
     "Near-transparent round-trip; the sweet spot for actually separating something "
     "(rather than rebuilding the original mix) sits in a narrow middle range of the "
     "faithfulness dial — push too far either way and it either does nothing or undoes itself."),
    ("renders_dora_caut", "DoRA finetune renders using the 'cautious' optimizer masking.",
     "See the cautious-masking verdict above — this recipe's gradient-masking mechanism "
     "is now known to be unreliable; kept here for the record, not the recommended path."),
    ("renders_soups_caut", "Checkpoint-averaging renders built from cautious-masked training runs.",
     "Inherits the cautious-masking caveat above; audition with that in mind."),
    ("renders_dora", "DoRA (weight-decomposed LoRA) finetune renders on the Goa corpus.", None),
    ("renders_soups", "Checkpoint-averaging ('model soup') renders.", None),
    ("soup_caut", "Averaging checkpoints trained under the 'cautious' optimizer masking.",
     "Inherits the cautious-masking caveat (see that verdict elsewhere on this page) on "
     "top of the usual mixed soup-vs-single-best picture — read this one with both grains of salt."),
    ("soup", "Averaging several training checkpoints together instead of picking one 'best' one.",
     "Mixed — some blends beat the single best checkpoint, others didn't; worth listening "
     "per blend rather than trusting one number."),
    ("renders_cross", "Cross-prompt renders — same control settings, different text prompts.", None),
    ("_demos", "Loose demonstration clips, not part of a specific test.", None),
]

def curated_for(name):
    n = name.lower()
    for key, subtitle, verdict in CURATED:
        if key in n:
            return subtitle, verdict
    return None, None

def enrich(kind, name, purpose, cat):
    """(date_str, subtitle, verdict) — the approachable-for-laypeople trio Kim asked
    for: when it ran, what was tested, what happened. Priority: curated hand-written
    pairs > sidecar-purpose / data-derived > category fallback. Subtitle is always
    non-empty; verdict is left blank if genuinely undocumented (never invented)."""
    date_str = fmt_date(real_date(kind, name))
    c_subtitle, c_verdict = curated_for(name)
    subtitle = c_subtitle or purpose or f"{cat[0].upper()}{cat[1:]}."
    verdict = c_verdict if c_verdict is not None else onset_verdict(kind, name)
    return date_str, subtitle, verdict

def desc_for(name, kind):
    """description for a run/set — prefer its self-describing sidecar (_meta.json or the
    run_meta.json convention onset_eval.py writes; redacted), else run_purposes.json, else
    a parsed hint. Everything returned is public-safe."""
    for fname in ("_meta.json", "run_meta.json"):
        meta = f"{STAGING}/{kind}/{name}/{fname}"
        if os.path.exists(meta):
            try:
                m = json.load(open(meta))
                purpose = m.get("purpose") or m.get("notes") or ""
                extra = " · ".join(f"{kk}={m[kk]}" for kk in ("optimizer","lr","scalar_field") if m.get(kk))
                return redact(purpose).strip(), redact(extra)
            except Exception:
                pass
    for k, v in PURP.items():
        if k == "_doc" or not isinstance(v, dict):
            continue
        if v.get("run") == name or k == name or (v.get("run","") and v["run"] in name):
            extra = " · ".join(f"{kk}={vv}" for kk in ("optimizer","lr","scalar_field") if (vv:=v.get(kk)))
            return redact((v.get("purpose","") or "").strip()), redact(extra)
    return "", redact(name.replace("_"," "))

def clean_label(fn):
    base = fn.split("/")[-1]                        # label = filename, not the relative path
    return redact(re.sub(r"\.m4a$","",base).replace("__"," · ").replace("_"," "))

def category(name, kind):
    """a friendly category from the folder — NO configs (lr/optimizer/epoch stay out of view)."""
    n = name.lower()
    if kind == "renders":
        if n == "_demos": return "demo renders"
        if "dora" in n:   return "DoRA renders"
        if "soup" in n:   return "model-soup renders"
        if "flowsep" in n: return "flow-separation renders"
        if "zerosep" in n: return "zero-shot separation"
        if "cross" in n:  return "cross-prompt renders"
        if "audition" in n: return "audition renders"
        if "weight_garden" in n: return "weight-mutation renders"
        if "glitchheal" in n: return "glitch-heal renders"
        return "renders"
    if n == "_demos":       return "demo clips"
    if "collapse" in n:     return "collapse test"
    if "opb" in n:          return "onset-per-beat control"
    if n.startswith("bracket"): return "bracket sweep"
    if n.startswith("cmp"): return "comparison"
    if n.startswith("onset"): return "onset control"
    if "multihead_bracket" in n: return "multihead bracket sweep"
    if "multihead_glitch" in n: return "weight-mutation x control stack"
    if n.startswith("composed_sweep") or n in ("e_fusion_v2", "a_cc_v2", "e_fusion", "a_cc"): return "composed control sweep"
    return "control run"

def write_grid_folder(kind, name, label, purpose, date_str, source_dir):
    """Rich gain x density grid renderer (eval_grid.py) for onset_eval.json-bearing
    dirs — restores build_onset_eval_page.py's layout, generalized. See
    docs/superpowers/specs/2026-07-05-eval-grid-rich-renderer.md."""
    staged_dir = f"{OUT}/{kind}/{name}"
    staged_stems = {os.path.splitext(f)[0] for f in os.listdir(staged_dir) if f.endswith(".m4a")}

    def clip_lookup(stem):
        return f"{stem}.m4a" if stem in staged_stems else None

    records = eval_grid.load_grid_data(source_dir, clip_lookup)
    if not records:
        return False

    head_html = head(f"{html.escape(label)} — evals", depth=2)
    head_html += ('<p class="nav"><a href="../../index.html">← all evals</a>'
                  '<a href="https://aavepyora.online/files/">the studio</a></p>')
    footer_html = '<footer>aavepyora.online · evals · same-playhead · gain x density grid</footer></div></body></html>'
    doc = eval_grid.render_grid_page(
        head_html=head_html, css_extra=eval_grid.GRID_CSS, title=label, label=label,
        purpose=redact(purpose), date_str=date_str, records=records, footer_html=footer_html,
    )
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

def write_table_folder(kind, name, label, purpose, date_str, source_dir):
    """Human-first sortable table + dual-checkpoint compare (eval_grid.py) for
    DoRA-audition dirs (pq_scores.json rows carrying a `checkpoint` key). See
    docs/superpowers/specs/2026-07-06-eval-tables-human-first.md."""
    staged_dir = f"{OUT}/{kind}/{name}"
    staged_stems = {os.path.relpath(os.path.splitext(f)[0], staged_dir)
                    for f in glob.glob(f"{staged_dir}/**/*.m4a", recursive=True)}

    def clip_lookup(stem):
        return f"{stem}.m4a" if stem in staged_stems else None

    records = eval_grid.load_dora_data(source_dir, clip_lookup)
    if not records:
        return False

    head_html = head(f"{html.escape(label)} — evals", depth=2)
    head_html += ('<p class="nav"><a href="../../index.html">← all evals</a>'
                  '<a href="https://aavepyora.online/files/">the studio</a></p>')
    footer_html = '<footer>aavepyora.online · evals · same-playhead · sortable table + checkpoint compare</footer></div></body></html>'
    doc = eval_grid.render_table_compare_page(
        head_html=head_html, title=label, label=label,
        purpose=redact(purpose), date_str=date_str, records=records, footer_html=footer_html,
    )
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

def write_style_compare_folder(kind, name, label, purpose, date_str, source_dir):
    """Dual-pane arm compare with plain-vs-styled columns side by side
    (pq_scores.json rows carrying `prompt_key`/`style`). See eval_grid.py's
    load_promptstyle_data()/render_style_compare_page()."""
    staged_dir = f"{OUT}/{kind}/{name}"
    staged_stems = {os.path.relpath(os.path.splitext(f)[0], staged_dir)
                    for f in glob.glob(f"{staged_dir}/**/*.m4a", recursive=True)}

    def clip_lookup(stem):
        return f"{stem}.m4a" if stem in staged_stems else None

    records = eval_grid.load_promptstyle_data(source_dir, clip_lookup)
    if not records:
        return False

    head_html = head(f"{html.escape(label)} — evals", depth=2)
    head_html += ('<p class="nav"><a href="../../index.html">← all evals</a>'
                  '<a href="https://aavepyora.online/files/">the studio</a></p>')
    footer_html = '<footer>aavepyora.online · evals · same-playhead · plain-vs-styled arm compare</footer></div></body></html>'
    doc = eval_grid.render_style_compare_page(
        head_html=head_html, title=label, label=label,
        purpose=redact(purpose), date_str=date_str, records=records, footer_html=footer_html,
    )
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

def write_checkpoint_audit_folder(kind, name, label, purpose, date_str, member_names):
    """Aggregate many INDEPENDENT gain x density grids (e.g. dozens of separately-
    linked 'onset control N' runs) into one dropdown-browsable audit page (Kim,
    2026-07-07: dozens of individual landing links is "messy AF"). Each member's
    clips stay in its own existing staged folder -- this writes a NEW sibling
    folder (`name`) whose index.html references them via relative ../<member>/
    paths, so nothing about the per-member folders needs to move."""
    staged_dir = f"{OUT}/{kind}/{name}"
    os.makedirs(staged_dir, exist_ok=True)
    all_records = []
    for member in member_names:
        source_dir = find_source_dir(member)
        if not source_dir or not os.path.exists(f"{source_dir}/onset_eval.json"):
            continue
        member_dir = f"{OUT}/{kind}/{member}"
        staged_stems = {os.path.relpath(os.path.splitext(f)[0], member_dir)
                        for f in glob.glob(f"{member_dir}/**/*.m4a", recursive=True)}

        def clip_lookup(stem, _member=member, _stems=staged_stems):
            return f"../{_member}/{stem}.m4a" if stem in _stems else None

        records = eval_grid.load_grid_data(source_dir, clip_lookup)
        if records:
            all_records.extend(records)
    if not all_records:
        return False

    head_html = head(f"{html.escape(label)} — evals", depth=2)
    head_html += ('<p class="nav"><a href="../../index.html">← all evals</a>'
                  '<a href="https://aavepyora.online/files/">the studio</a></p>')
    footer_html = '<footer>aavepyora.online · evals · same-playhead · multi-checkpoint audit</footer></div></body></html>'
    doc = eval_grid.render_checkpoint_audit_page(
        head_html=head_html, title=label, label=label,
        purpose=redact(purpose), date_str=date_str, records=all_records, footer_html=footer_html,
    )
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

def write_misc_bundle_folder(kind, name, label, purpose, date_str, entries):
    """Index page for the leftover uncurated runs that don't share a common
    schema (audition/multiprompt/trajectory/soup/pilot/bracket/etc -- too
    heterogeneous for one shared table). Each member keeps its OWN
    individually-generated player page (written earlier in pass 2, exactly
    like any other folder -- some of these are large multi-epoch telemetry
    sweeps with thousands of clips, far too many to inline onto one page).
    This page is just a compact table-of-contents linking to them, so the
    landing page collapses dozens of links into one without forcing
    thousands of clips onto a single page. entries: list of
    (member_name, label, desc, n_clips, date_str, subtitle, verdict)."""
    staged_dir = f"{OUT}/{kind}/{name}"
    os.makedirs(staged_dir, exist_ok=True)
    doc = head(f"{html.escape(label)} — evals", depth=2)
    doc += ('<p class="nav"><a href="../../index.html">← all evals</a>'
            '<a href="https://aavepyora.online/files/">the studio</a></p>')
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    doc += (f'<p class="faint">{len(entries)} uncurated runs, each linked to its own player below '
            '(bracket sweeps, pilots, audition/multiprompt variants, and a few large multi-epoch '
            'telemetry sweeps -- too structurally different from each other, and in some cases too '
            'large, to fold onto one shared page)</p>')
    for member_name, m_label, m_desc, n_clips, m_date, m_subtitle, m_verdict in sorted(
            entries, key=lambda e: e[4], reverse=True):
        doc += (f'<div class="run"><div class="name"><a href="../{html.escape(member_name)}/index.html">'
                f'{html.escape(m_label)}</a></div>')
        if m_date:
            doc += f'<div class="when">{html.escape(m_date)}</div>'
        subtitle = m_subtitle or m_desc
        if subtitle:
            doc += f'<div class="desc">{html.escape(subtitle)}</div>'
        if m_verdict:
            doc += f'<div class="verdict">{html.escape(m_verdict)}</div>'
        doc += f'<div class="meta">{n_clips} clips</div></div>'
    doc += '<footer>aavepyora.online · evals · same-playhead · uncurated-run index</footer></div></body></html>'
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

def write_folder(kind, name, label, purpose, clips, date_str="", verdict=None):
    doc = head(f"{html.escape(label)} — evals", depth=2)
    doc += ('<p class="nav"><a href="../../index.html">← all evals</a>'
            '<a href="https://aavepyora.online/files/">the studio</a></p>')
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    if verdict:
        doc += f'<p style="color:var(--edge-ink)">{html.escape(verdict)}</p>'
    doc += f'<p class="faint">{len(clips)} clips · click to play (shared playhead; switching keeps position; re-click stops)</p>'
    doc += '<div class="grid">'
    for c in clips:
        doc += f'<span class="cell" data-src="{html.escape(c)}" onclick="play(this)">{html.escape(clean_label(c))}</span>'
    doc += '</div>' + PLAYER_JS
    doc += '<footer>aavepyora.online · evals · same-playhead</footer></div></body></html>'
    od = f"{OUT}/{kind}/{name}"
    os.makedirs(od, exist_ok=True)
    open(f"{od}/index.html","w").write(doc)

def build_landing(control, renders):
    doc = head("Evals — Vibe on The Edg3", depth=0)
    doc += ('<p class="nav"><a href="https://aavepyora.online/files/">← the studio</a>'
            '<a href="https://aavepyora.online/files/AGENT_DIALOGUE.html">dialogue</a></p>')
    doc += ('<h1>Evals</h1><p class="lede">Listening results — what the control heads, adapters, and '
            'renders actually sound like. Each folder is a same-playhead player, not a dump.</p>')
    doc += ('<p class="faint">Bookmark this page: '
            '<a href="https://aavepyora.online/files/evals/">aavepyora.online/files/evals/</a> — '
            'the canonical, always-current entry point for the listening review.</p>')
    doc += '<h2><span class="mark">§</span> Curated players</h2>'
    doc += ('<p class="dim">The measured, annotated grids — same-playhead, with per-run info boxes:</p>')
    _riffer_labels = {"onset_eval.html": "onset control-authority", "disentangle.html": "disentanglement",
                       "dora_results.html": "DoRA auditions", "chroma_steer.html": "chroma steer",
                       "gain_knee.html": "gain knee", "mp.html": "multiprompt", "traj.html": "trajectories",
                       "latch_sweep.html": "LatCH head sweep"}
    _riffer = [(f"riffer/{f}", _riffer_labels[f]) for f in RIFFER_HTML]
    for _href, _lbl in _riffer:
        doc += f'<div class="run"><div class="name"><a href="{_href}">{_lbl}</a></div></div>'
    for lbl, kind, items in (("Control runs","control_runs",control),("Renders","renders",renders)):
        doc += f'<h2><span class="mark">§</span> {lbl} <span class="faint">({len(items)})</span></h2>'
        for name, label, purpose, n, date_str, subtitle, verdict in items:
            doc += (f'<div class="run"><div class="name"><a href="{kind}/{html.escape(name)}/index.html">'
                    f'{html.escape(label)}</a></div>')
            if date_str:
                doc += f'<div class="when">{html.escape(date_str)}</div>'
            if subtitle:
                doc += f'<div class="desc">{html.escape(subtitle)}</div>'
            if verdict:
                doc += f'<div class="verdict">{html.escape(verdict)}</div>'
            doc += f'<div class="meta">{n} clips</div></div>'
    doc += '<footer>aavepyora.online · evals · generated by Misc/build_evals.py</footer></div></body></html>'
    open(f"{OUT}/index.html","w").write(doc)

def sync_riffer_pages():
    """Copy the curated riffer-evals HTML pages (+ their clip dirs) into
    OUT/riffer/ so the landing's "Curated players" links actually resolve.
    build_evals.py only ever WROTE these links, never synced the pages
    themselves -- they lived solely in ~/riffer-evals/, so file:// browsing of
    the staging mirror 404'd on every curated player (Kim, 2026-07-06)."""
    src_root = f"{HOME}/riffer-evals"
    dst_root = f"{OUT}/riffer"
    if not os.path.isdir(src_root):
        return
    os.makedirs(dst_root, exist_ok=True)
    copied = 0
    for fname in RIFFER_HTML:
        src = f"{src_root}/{fname}"
        if os.path.isfile(src):
            shutil.copy2(src, f"{dst_root}/{fname}")
            copied += 1
    # clip dirs referenced by the html (clips*/...) -- copy2 tree, skip if the
    # destination already has the exact same file count (cheap staleness check,
    # avoids re-copying gigabytes of audio on every rebuild).
    for entry in os.listdir(src_root):
        if not entry.startswith("clips"):
            continue
        src = f"{src_root}/{entry}"
        dst = f"{dst_root}/{entry}"
        if not os.path.isdir(src):
            continue
        if os.path.isdir(dst) and len(os.listdir(dst)) == len(os.listdir(src)):
            continue
        shutil.copytree(src, dst, dirs_exist_ok=True)
    print(f"riffer:       {copied}/{len(RIFFER_HTML)} curated pages synced from {src_root}")

def main():
    os.makedirs(OUT, exist_ok=True)
    open(f"{OUT}/evals.css","w").write(CSS + eval_grid.GRID_CSS + eval_grid.TABLE_CSS + eval_grid.STYLE_CSS + eval_grid.AUDIT_CSS)
    sync_riffer_pages()
    # pass 1: gather every folder (+ loose demos) with its purpose
    gathered = []  # (kind, name, purpose, clips)
    for kind in ("control_runs", "renders"):
        base = f"{STAGING}/{kind}"
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            if name.startswith("."):   # skip hidden dirs (.venv etc.)
                continue
            d = f"{base}/{name}"
            if not os.path.isdir(d):
                continue
            clips = sorted(os.path.relpath(c, d) for c in glob.glob(f"{d}/**/*.m4a", recursive=True))
            if clips:
                purpose, _ = desc_for(name, kind)
                gathered.append((kind, name, purpose, clips))
        loose = sorted(os.path.basename(c) for c in glob.glob(f"{base}/*.m4a"))
        if loose:
            gathered.append((kind, "_demos", "loose top-level demo clips", [f"../{c}" for c in loose]))
    # pass 1.5: split off uncurated control_runs entries for aggregation (Kim,
    # 2026-07-07: dozens of individually-linked "onset control N" links is
    # "messy AF" -- fold every uncurated control_runs folder into exactly two
    # pages instead: a rich multi-checkpoint audit for the real gain x density
    # grids, and a simple bundle for the structurally-different leftovers).
    # A folder only gets pulled into aggregation if desc_for() found NOTHING
    # for it -- anything with a real curated purpose keeps its own page/link.
    normal, audit_members, misc_members = [], [], []
    for kind, name, purpose, clips in gathered:
        if kind == "control_runs" and not purpose and name != "_demos":
            source_dir = find_source_dir(name)
            if source_dir and os.path.exists(f"{source_dir}/onset_eval.json"):
                audit_members.append(name)
                continue
            misc_members.append((kind, name, purpose, clips))
            continue
        normal.append((kind, name, purpose, clips))
    misc_keys = {(k, n) for k, n, p, c in misc_members}

    # pass 2: FRIENDLY labels — the description, else category + per-category index. Never the raw
    # folder name (which embeds lr/optimizer/epoch configs). Kim's ruling, WINTERMUTE's leak-catch.
    # misc_members are routed through this SAME loop (own real page written for
    # each, same grid/table/style/flat fallback as any other folder -- some are
    # large multi-epoch telemetry sweeps, too big to inline into a bundle page)
    # but their landing-entry goes to misc_meta instead of out[kind], since the
    # bundle page is their only top-level link.
    counters, out, misc_meta = {}, {"control_runs": [], "renders": []}, []
    for kind, name, purpose, clips in normal + misc_members:
        cat = category(name, kind)
        if purpose:
            label = purpose if len(purpose) <= 60 else purpose[:57].rstrip() + "…"
        else:
            counters[cat] = counters.get(cat, 0) + 1
            label = f"{cat} {counters[cat]}"
        desc = purpose if purpose and purpose != label else ""
        date_str, subtitle, verdict = enrich(kind, name, desc, cat)
        if subtitle == label:   # don't repeat the title verbatim as its own subtitle
            subtitle = ""
        source_dir = find_source_dir(name) if kind == "control_runs" else find_renders_source_dir(name)
        is_grid = source_dir and os.path.exists(f"{source_dir}/onset_eval.json")
        wrote_grid = is_grid and write_grid_folder(kind, name, label, desc or subtitle, date_str, source_dir)
        # table+compare (DoRA auditions, checkpoint x prompt x seed) — tried when the
        # dir isn't a gain/density grid; falls through to the flat player if the source
        # has no checkpoint-tagged pq_scores.json (not every renders/ dir is a DoRA audition).
        wrote_table = (not wrote_grid) and source_dir and write_table_folder(
            kind, name, label, desc or subtitle, date_str, source_dir)
        # style-compare (plain-vs-styled prompt A/B, pq_scores.json rows with prompt_key/style)
        wrote_style = (not wrote_grid) and (not wrote_table) and source_dir and write_style_compare_folder(
            kind, name, label, desc or subtitle, date_str, source_dir)
        if not wrote_grid and not wrote_table and not wrote_style:
            write_folder(kind, name, label, desc or subtitle, clips, date_str, verdict)
        entry = (name, label, desc, len(clips), date_str, subtitle, verdict)
        if (kind, name) in misc_keys:
            misc_meta.append(entry)
        else:
            out[kind].append(entry)

    # the two aggregated pages, each exactly one landing entry regardless of
    # how many folders they fold in.
    if audit_members:
        name = "_onset_control_audit"
        label = "Onset-control checkpoint audit (all runs)"
        purpose = (f"Every uncurated onset-density control-adapter run in one place — "
                   f"{len(audit_members)} checkpoints, pick one from the dropdown, sort any "
                   f"column, same-playhead. Was {len(audit_members)} separate landing links; "
                   f"now one.")
        n_clips = sum(len(c) for k, n, p, c in gathered if n in audit_members)
        if write_checkpoint_audit_folder("control_runs", name, label, purpose, "", audit_members):
            out["control_runs"].append((name, label, purpose, n_clips, "", "", ""))
    if misc_meta:
        name = "_misc_uncurated_runs"
        label = "Other uncurated control runs (bracket sweeps, pilots, etc.)"
        purpose = (f"{len(misc_meta)} uncurated runs too structurally different from each "
                   f"other for one shared table (bracket sweeps, pilot experiments, audition/"
                   f"multiprompt variants, and a few large multi-epoch telemetry sweeps) — "
                   f"each keeps its own player; this page is just an index.")
        n_clips = sum(e[3] for e in misc_meta)
        if write_misc_bundle_folder("control_runs", name, label, purpose, "", misc_meta):
            out["control_runs"].append((name, label, purpose, n_clips, "", "", ""))

    # order runs newest-first within each category (Kim's request). date_str is
    # "%Y-%m-%d %H:%M" -> lexicographic sort == chronological; undated ("") sorts last.
    for _k in out:
        out[_k].sort(key=lambda it: it[4], reverse=True)
    build_landing(out["control_runs"], out["renders"])
    print(f"control_runs: {len(out['control_runs'])} playable folders")
    print(f"renders:      {len(out['renders'])} playable folders")
    print(f"friendly labels; landing + {len(out['control_runs'])+len(out['renders'])} players -> {OUT}")

if __name__ == "__main__":
    main()
