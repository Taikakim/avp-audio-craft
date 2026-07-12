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
# newcap8_promptstyle_longform: 2048-frame (3:10) renders, a 512-frame latent
# slerp crossfade centered mid-render (longform.py's CrossfadeStitcher; see
# WORKLOG 2026-07-07). No per-clip timestamp is recorded, so this is derived
# from the frame counts at SA3's ~10.767 Hz grid rate -- approximate, not exact.
_LF_HZ = 10.767
LONGFORM_XFADE_LEN = 512 / _LF_HZ
LONGFORM_XFADE_START = (2048 / _LF_HZ - LONGFORM_XFADE_LEN) / 2

RIFFER_HTML = ["onset_eval.html", "disentangle.html", "dora_results.html",
               "chroma_steer.html", "gain_knee.html", "mp.html", "traj.html",
               "latch_sweep.html", "breathing.html", "rarity.html"]


CSS = """:root{--paper:#fafaf7;--paper-dim:#f2f3ef;--ink:#2b3538;--body:#3b4649;
--dim:#7a8a8e;--faint:#9aa7a9;--rule:#c9d2d0;--rule-light:#e2e6e2;--edge:#0f9e99;--edge-ink:#0c807c;
--mono:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace}
*{box-sizing:border-box}html{background:var(--paper);overflow-x:hidden}
/* overflow-x:hidden on html+body (Kim, 2026-07-10): if ANY content on the page is
   wider than the viewport, mobile browsers expand the layout viewport to fit it,
   and the waveform popup's position:fixed;left:50% centering (below) then centers
   against that expanded width instead of the visible screen -- the popup appears
   shifted off to the side. Clipping horizontal overflow at the body level is the
   fix; wide inner elements (tables) still need their own overflow-x:auto wrapper
   to stay reachable, this just stops them from blowing out the whole page. */
body{margin:0;color:var(--body);font-family:var(--mono);font-size:13px;line-height:1.7;
max-width:100vw;overflow-x:hidden}
.wrap{max-width:900px;margin:0 auto;padding:34px 28px 72px}
a{color:var(--edge-ink);text-decoration:underline;text-decoration-style:dotted;text-underline-offset:3px}
a:hover{text-decoration-style:solid}
.over{margin:0;font-size:11px;letter-spacing:.45em;color:var(--faint)}
h1{font-size:20px;line-height:1.3;color:var(--ink);margin:18px 0 6px}
h2{font-size:12px;letter-spacing:.3em;text-transform:uppercase;color:var(--ink);
margin:40px 0 14px;padding-bottom:6px;border-bottom:1px solid var(--rule)}
h2 .mark{color:var(--edge)}
h3{font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:var(--dim);margin:16px 0 6px}
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
.unaudited{color:#e33;font-size:12px;cursor:help}
.grid{display:flex;flex-wrap:wrap;gap:7px;margin:10px 0}
.cell{font-family:var(--mono);font-size:11px;color:var(--body);background:var(--paper-dim);
border:1px solid var(--rule);padding:6px 10px;cursor:pointer;border-radius:2px}
.cell:hover{border-color:var(--edge)}
.cell.playing{background:var(--edge);color:#fff;border-color:var(--edge)}
footer{margin-top:48px;padding-top:14px;border-top:1px solid var(--rule);font-size:11px;color:var(--faint)}
"""

# ── waveform popup player (eval-tables spec §13, Kim 2026-07-07) ──────────────
# Shared across EVERY page kind (grid/table/style/audit/density/composed/
# epoch-progress/longform/transitions/a2a/chroma-morph/flat fallback) without
# touching any of their individual play() implementations: patches window.Audio
# so every `new Audio()` this page creates is auto-tracked, and separately
# scans literal `<audio>` DOM elements (the id="pl"/"lfpl" pattern used by the
# flat/longform/transitions/a2a/chroma-morph pages) once the document parses.
# Whichever audio object a page is actually playing becomes "the" tracked one
# -- the popup drives THAT object (play/pause/seek), never a second Audio
# instance, so the same-playhead convention holds even through the popup.
WAVEFORM_CSS = """
#wf-bar{position:fixed;left:50%;bottom:16px;transform:translateX(-50%) translateY(120%);
display:flex;align-items:center;gap:10px;background:#fff;border:1px solid var(--rule);
border-top:3px solid var(--edge);border-radius:4px;padding:8px 14px;box-shadow:0 4px 18px rgba(0,0,0,.12);
font-family:var(--mono);font-size:11.5px;color:var(--body);z-index:40;
transition:transform .18s ease;max-width:min(560px,92vw)}
#wf-bar.show{transform:translateX(-50%) translateY(0)}
#wf-bar .wf-lbl{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:360px;color:var(--dim)}
#wf-toggle{background:var(--edge);color:#fff;border:none;border-radius:3px;padding:7px 12px;
cursor:pointer;font-family:var(--mono);font-size:13px;min-width:44px;min-height:32px}
#wf-toggle:hover{background:var(--edge-ink)}
#wf-modal{display:none;position:fixed;inset:0;background:rgba(20,26,27,.55);z-index:50;
align-items:center;justify-content:center}
#wf-modal.open{display:flex}
.wf-panel{width:min(1400px,90vw);background:#fff;border:1px solid var(--rule);border-radius:6px;
padding:16px 20px 20px;box-shadow:0 12px 40px rgba(0,0,0,.25)}
.wf-hd{display:flex;justify-content:space-between;align-items:center;margin:0 0 10px;gap:10px}
.wf-hd span{font-size:12.5px;color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#wf-close{background:var(--paper-dim);border:1px solid var(--rule);border-radius:3px;
min-width:44px;min-height:38px;cursor:pointer;font-family:var(--mono);font-size:14px}
.wf-wrap{position:relative;width:100%;height:160px;background:var(--paper-dim);
border:1px solid var(--rule);border-radius:3px;cursor:pointer;touch-action:none}
#wf-canvas{width:100%;height:100%;display:block}
.wf-fallback{display:none;position:absolute;inset:0;padding:0 12px;display:flex;align-items:center}
.wf-fallback input{width:100%}
#wf-cursor{position:absolute;top:0;bottom:0;left:0;width:2px;background:var(--edge-ink);pointer-events:none}
.wf-time{display:flex;justify-content:space-between;font-size:11px;color:var(--faint);margin:8px 2px 0}
@media (max-width:820px){.wf-panel{width:100vw;height:100vh;border-radius:0;box-sizing:border-box}
.wf-wrap{height:96px}#wf-bar .wf-lbl{max-width:44vw}}
"""

WAVEFORM_JS = """<script>
(function(){
const peakCache = new Map();
let tracked = null;

function attach(a){
  if (a.__wfAttached) return;
  a.__wfAttached = true;
  const onActive = () => { tracked = a; updateBar(); };
  a.addEventListener('loadedmetadata', onActive);
  a.addEventListener('play', onActive);
  a.addEventListener('timeupdate', () => { if (tracked === a) render(); });
}

const NativeAudio = window.Audio;
function PatchedAudio(...args){ const a = new NativeAudio(...args); attach(a); return a; }
PatchedAudio.prototype = NativeAudio.prototype;
window.Audio = PatchedAudio;

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('audio').forEach(attach);
});

// CONTINUITY, 2026-07-07: pages that know a transition/crossfade window
// (transitions, longform) tag their play cells with data-wfstart/data-wfend
// (seconds) -- capture-phase click delegation (fires before the cell's own
// onclick) tracks the most recently played clip's window, if any, so the
// popup can shade it. Cleared on any other clip's play cell so a stale
// window doesn't linger onto an unrelated clip.
let curWindow = null;
document.addEventListener('click', (e) => {
  const wfEl = e.target.closest && e.target.closest('[data-wfstart]');
  if (wfEl) { curWindow = { start: parseFloat(wfEl.dataset.wfstart), end: parseFloat(wfEl.dataset.wfend) }; return; }
  const srcEl = e.target.closest && e.target.closest('[data-src]');
  if (srcEl) curWindow = null;
}, true);

let bar, wfBtn, wfLbl;
function ensureBar(){
  if (bar) return;
  bar = document.createElement('div'); bar.id = 'wf-bar';
  wfLbl = document.createElement('span'); wfLbl.className = 'wf-lbl';
  wfBtn = document.createElement('button'); wfBtn.id = 'wf-toggle';
  wfBtn.textContent = '〰'; wfBtn.title = 'open waveform';
  wfBtn.onclick = () => openModal();
  bar.appendChild(wfLbl); bar.appendChild(wfBtn);
  document.body.appendChild(bar);
}
function updateBar(){
  ensureBar();
  const show = !!(tracked && tracked.duration && tracked.duration >= 20 && tracked.src);
  bar.classList.toggle('show', show);
  if (show) wfLbl.textContent = decodeURIComponent(tracked.src.split('/').pop());
}

let modal, canvas, ctx, rangeEl, cursorEl, curLbl, curTimeEl, durTimeEl, fallbackEl;
function ensureModal(){
  if (modal) return;
  modal = document.createElement('div'); modal.id = 'wf-modal';
  modal.innerHTML = '<div class="wf-panel"><div class="wf-hd"><span id="wf-clip-label"></span>'
    + '<button id="wf-close" title="close (Esc)">\\u2715</button></div>'
    + '<div class="wf-wrap"><canvas id="wf-canvas"></canvas>'
    + '<div id="wf-fallback" class="wf-fallback"><input id="wf-range" type="range" min="0" max="1000" value="0"></div>'
    + '<div id="wf-cursor"></div></div>'
    + '<div class="wf-time"><span id="wf-cur">0:00</span><span id="wf-dur">0:00</span></div></div>';
  document.body.appendChild(modal);
  document.getElementById('wf-close').onclick = closeModal;
  modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });
  canvas = document.getElementById('wf-canvas'); ctx = canvas.getContext('2d');
  cursorEl = document.getElementById('wf-cursor');
  curLbl = document.getElementById('wf-clip-label');
  curTimeEl = document.getElementById('wf-cur'); durTimeEl = document.getElementById('wf-dur');
  fallbackEl = document.getElementById('wf-fallback');
  rangeEl = document.getElementById('wf-range');
  canvas.addEventListener('pointerdown', seekFromEvent);
  rangeEl.addEventListener('input', () => {
    if (tracked && tracked.duration) tracked.currentTime = (rangeEl.value / 1000) * tracked.duration;
  });
  document.addEventListener('keydown', (e) => {
    if (!modal.classList.contains('open') || !tracked) return;
    if (e.key === 'Escape') { closeModal(); }
    else if (e.key === ' ') { e.preventDefault(); tracked.paused ? tracked.play() : tracked.pause(); }
    else if (e.key === 'ArrowLeft') { tracked.currentTime = Math.max(0, tracked.currentTime - 5); }
    else if (e.key === 'ArrowRight') { tracked.currentTime = Math.min(tracked.duration || 1e9, tracked.currentTime + 5); }
  });
}
function seekFromEvent(e){
  if (!tracked || !tracked.duration) return;
  const rect = canvas.getBoundingClientRect();
  const frac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  tracked.currentTime = frac * tracked.duration;
}
function fmtTime(s){ s = Math.max(0, s | 0); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); }
function openModal(){
  if (!tracked) return;
  ensureModal();
  curLbl.textContent = decodeURIComponent(tracked.src.split('/').pop());
  modal.classList.add('open');
  drawPeaksFor(tracked.src);
  render();
}
function closeModal(){ if (modal) modal.classList.remove('open'); }
function render(){
  if (!modal || !modal.classList.contains('open') || !tracked) return;
  const dur = tracked.duration || 0;
  curTimeEl.textContent = fmtTime(tracked.currentTime);
  durTimeEl.textContent = fmtTime(dur);
  if (dur) rangeEl.value = Math.round((tracked.currentTime / dur) * 1000);
  cursorEl.style.left = (dur ? (tracked.currentTime / dur) * 100 : 0) + '%';
}
async function drawPeaksFor(src){
  const cached = peakCache.get(src);
  if (cached === null) { showFallback(true); return; }
  if (cached) { showFallback(false); paint(cached); return; }
  showFallback(false);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#9aa7a9'; ctx.font = '11px monospace'; ctx.fillText('decoding…', 8, 16);
  try {
    const resp = await fetch(src);
    const buf = await resp.arrayBuffer();
    const actx = new (window.AudioContext || window.webkitAudioContext)();
    const audioBuf = await actx.decodeAudioData(buf);
    const ch = audioBuf.getChannelData(0);
    const N = 1500;
    const step = Math.max(1, Math.floor(ch.length / N));
    const peaks = new Float32Array(N * 2);
    for (let i = 0; i < N; i++) {
      let mn = 1, mx = -1;
      for (let j = i * step; j < Math.min(ch.length, (i + 1) * step); j++) {
        const v = ch[j]; if (v < mn) mn = v; if (v > mx) mx = v;
      }
      peaks[i * 2] = mn; peaks[i * 2 + 1] = mx;
    }
    peakCache.set(src, peaks);
    if (tracked && tracked.src === src) { showFallback(false); paint(peaks); }
    actx.close();
  } catch (e) {
    peakCache.set(src, null);
    if (tracked && tracked.src === src) showFallback(true);
  }
}
function showFallback(on){
  fallbackEl.style.display = on ? 'flex' : 'none';
  canvas.style.display = on ? 'none' : 'block';
}
function paint(peaks){
  const w = canvas.clientWidth, h = canvas.clientHeight, mid = h / 2;
  canvas.width = w; canvas.height = h;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = '#0f9e99';
  const n = peaks.length / 2;
  const barW = Math.max(1, w / n);
  for (let i = 0; i < n; i++) {
    const x = (i / n) * w;
    const mn = peaks[i * 2], mx = peaks[i * 2 + 1];
    ctx.fillRect(x, mid + mn * mid, barW, Math.max(1, (mx - mn) * mid));
  }
  // shade the transition/crossfade window, if this clip has one (Kim's actual
  // workflow on those clips IS seek-to-the-transition -- a marked region turns
  // scrubbing into one click)
  if (curWindow && tracked && tracked.duration) {
    const x0 = (curWindow.start / tracked.duration) * w;
    const x1 = (curWindow.end / tracked.duration) * w;
    ctx.fillStyle = 'rgba(12,128,124,.18)';
    ctx.fillRect(x0, 0, Math.max(1, x1 - x0), h);
  }
}
})();
</script>"""

PLAYER_JS = """<audio id="pl"></audio><script>
let cur=null,ph=0;const a=document.getElementById('pl');
a.addEventListener('timeupdate',()=>{if(!a.paused)ph=a.currentTime});
a.addEventListener('ended',()=>{if(cur){cur.classList.remove('playing');cur=null}ph=0});
function seekAndPlay(pos){
 // seeking as soon as loadedmetadata fires can land on a not-yet-buffered part
 // of the compressed stream and glitch right at playback start (Kim, 2026-07-07)
 // NB: 'ended' resets ph=0 AND we clamp defensively below — a carried playhead at/past
 // the new clip's end used to seek every clip to its last 50ms: one blip, then silence
 // for every further click (Kim, 2026-07-10, reproduced on Win10 + Linux).
 const go=()=>{try{const d=a.duration||1e9;a.currentTime=(pos>d-1)?0:Math.min(pos,d-0.05)}catch(e){}a.play()};
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
            f'<link rel="stylesheet" href="{css_ref}"></head><body>{WAVEFORM_JS}<div class="wrap">'
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
# One-off aliases for dirs whose clips live in a NAMED SUBFOLDER of their run dir
# (checkpoints + lightning_logs sit alongside the renders) -- lets the staged/
# landing name stay the descriptive run name instead of the generic subfolder name.
RENDERS_SOURCE_ALIASES = {
    "dora16_goa_newstack_8ep": f"{MANTU}/sa3_lora_runs/dora16_goa_newstack_8ep/renders_cpu",
    # staged/landing name avoids the A2A_LADDER_RE auto-routing collision (a
    # literal "a2a_" prefix), but the real source dir keeps CONTINUITY's name.
    "memo_ckpt_a2a_test": f"{MANTU}/sa3_lora_runs/a2a_memo_test",
}

def find_renders_source_dir(name):
    """RENDERS_SOURCE_ALIASES override, else a RENDERS_SOURCE_DIRS entry whose
    basename matches name, else a RENDERS_SOURCE_ROOTS/<name> join, else None."""
    alias = RENDERS_SOURCE_ALIASES.get(name)
    if alias and os.path.isdir(alias):
        return alias
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

def has_kim_feedback(kind, name):
    """Manifest v2 audited-check (Kim DIRECT 2026-07-12, MASTER §4 / eval-tables
    spec §16): a run_meta.json with a non-empty kim_feedback field is audited;
    anything else gets a red exclamation mark on every page it appears on.
    Derived from the manifest at build time -- never hand-toggled."""
    source_dir = find_source_dir(name) if kind == "control_runs" else find_renders_source_dir(name)
    if not source_dir:
        return False
    meta_path = f"{source_dir}/run_meta.json"
    if not os.path.exists(meta_path):
        return False
    try:
        meta = json.load(open(meta_path))
    except Exception:
        return False
    return bool(meta.get("kim_feedback"))


UNAUDITED_MARK = ('<span class="unaudited" title="unaudited -- no kim_feedback in the manifest yet">'
                   '&#10071;</span>')


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

def _fmt_findings(findings):
    """findings may be a string or a list of strings (a run's own run_meta.json
    can accumulate several dated observations) -- normalize to one string."""
    if isinstance(findings, list):
        return " · ".join(str(f) for f in findings if f)
    return findings

def findings_status_for(name):
    """Human-authored 'findings'/'status', preferring the run's OWN staged
    run_meta.json (self-describing sidecar, per MASTER's convention) over the
    separate curated run_purposes.json registry -- a dir can carry its own
    verdict (e.g. chroma_morph_barsnap's run_meta marking itself OBSOLETE/
    superseded) without needing a matching run_purposes.json entry too.
    Returns (findings, status), either may be None. Redacted since these
    strings can quote ckpt/path details."""
    findings = status = None
    meta_path = f"{STAGING}/renders/{name}/run_meta.json"
    if not os.path.exists(meta_path):
        meta_path = f"{STAGING}/control_runs/{name}/run_meta.json"
    if os.path.exists(meta_path):
        try:
            m = json.load(open(meta_path))
            findings, status = _fmt_findings(m.get("findings")), m.get("status")
        except Exception:
            pass
    if findings is None and status is None:
        entry = PURP.get(name)
        if isinstance(entry, dict):
            findings, status = _fmt_findings(entry.get("findings")), entry.get("status")
    return (redact(findings) if findings else None, redact(status) if status else None)

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

def title_for(name, kind):
    """An explicit human-authored 'title' field from run_meta.json, if the run
    author wants a specific landing label instead of the truncated-purpose
    fallback (e.g. CONTINUITY, 2026-07-07: correcting an over-billed label to
    'BONUS variant... not a Kim ask' after a misread). Redacted, or None."""
    meta = f"{STAGING}/{kind}/{name}/run_meta.json"
    if os.path.exists(meta):
        try:
            title = json.load(open(meta)).get("title")
            if title:
                return redact(title).strip()
        except Exception:
            pass
    return None

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

def write_grid_folder(kind, name, label, purpose, date_str, source_dir,
                       findings=None, status=None, known_pages=None):
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

    head_html = head(f"{label} — evals", depth=2)
    head_html += ('<p class="nav"><a href="../../index.html">← all evals</a>'
                  '<a href="https://aavepyora.online/files/">the studio</a></p>')
    footer_html = '<footer>aavepyora.online · evals · same-playhead · gain x density grid</footer></div></body></html>'
    doc = eval_grid.render_grid_page(
        head_html=head_html, css_extra=eval_grid.GRID_CSS, title=label, label=label,
        purpose=redact(purpose), date_str=date_str, records=records, footer_html=footer_html,
        findings=findings, status=status, known_pages=known_pages,
    )
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

def write_table_folder(kind, name, label, purpose, date_str, source_dir,
                        findings=None, status=None, known_pages=None):
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

    head_html = head(f"{label} — evals", depth=2)
    head_html += ('<p class="nav"><a href="../../index.html">← all evals</a>'
                  '<a href="https://aavepyora.online/files/">the studio</a></p>')
    footer_html = '<footer>aavepyora.online · evals · same-playhead · sortable table + checkpoint compare</footer></div></body></html>'
    doc = eval_grid.render_table_compare_page(
        head_html=head_html, title=label, label=label,
        purpose=redact(purpose), date_str=date_str, records=records, footer_html=footer_html,
        findings=findings, status=status, known_pages=known_pages,
    )
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

def write_epoch_progress_folder(kind, name, label, purpose, date_str, source_dir,
                                 findings=None, status=None, known_pages=None):
    """Unscored checkpoint-progression dual-pane (raw `{ck}__p{N}_seed{S}.wav`
    renders, no pq_scores.json). Reads run_meta.json for prompt text + which
    checkpoint tag is the pinned Hall-of-Fame reference (checkpoints.hof
    contains a recognizable substring of one of the parsed tags) and which is
    the newest/last of the progression (highest epoch number wins pane A's
    default). Falls through (returns False) if the dir doesn't match this
    schema, so it's safe to try before the generic flat-grid fallback."""
    staged_dir = f"{OUT}/{kind}/{name}"
    staged_stems = {os.path.relpath(os.path.splitext(f)[0], staged_dir)
                    for f in glob.glob(f"{staged_dir}/**/*.m4a", recursive=True)}

    def clip_lookup(stem):
        return f"{stem}.m4a" if stem in staged_stems else None

    records = eval_grid.load_epoch_progress_data(source_dir, clip_lookup)
    if not records:
        return False

    prompt_text = []
    pinned_tag, default_a = None, None
    meta_path = f"{source_dir}/run_meta.json"
    if os.path.exists(meta_path):
        try:
            meta = json.load(open(meta_path))
            prompt_text = meta.get("gen", {}).get("prompts", [])
            ckpts = meta.get("checkpoints", {})
            tags = {r["checkpoint"] for r in records}
            # find the tag whose run-key (e.g. "hof") names it directly, or
            # whose value mentions a distinctive fragment of the tag
            for key, val in ckpts.items():
                for tag in tags:
                    if key.lower() in tag.lower() or (val and re.search(re.escape(tag.split("_epoch")[0]), val)):
                        if "hof" in key.lower() or "hall" in (val or "").lower():
                            pinned_tag = tag
        except Exception:
            pass
    # last (highest-epoch) non-pinned tag becomes pane A's default -- the
    # natural "does the new run land well by its final checkpoint" comparison
    def epoch_of(tag):
        m = re.search(r"epoch(\d+)", tag)
        return int(m.group(1)) if m else -1
    progression_tags = sorted((r["checkpoint"] for r in records if r["checkpoint"] != pinned_tag),
                               key=epoch_of)
    if progression_tags:
        default_a = progression_tags[-1]

    head_html = head(f"{label} — evals", depth=2)
    head_html += ('<p class="nav"><a href="../../index.html">← all evals</a>'
                  '<a href="https://aavepyora.online/files/">the studio</a></p>')
    footer_html = '<footer>aavepyora.online · evals · same-playhead · epoch-progression compare</footer></div></body></html>'
    doc = eval_grid.render_epoch_progress_page(
        head_html=head_html, title=label, label=label,
        purpose=redact(purpose), date_str=date_str, records=records, footer_html=footer_html,
        prompt_text=prompt_text, pinned_tag=pinned_tag, default_a=default_a,
        findings=findings, status=status, known_pages=known_pages,
    )
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

def write_a2a_ladder_folder(kind, name, label, purpose, date_str, member_names,
                             findings=None, status=None, known_pages=None):
    """Row=noise-level, column=adapter same-playhead table for a full-track
    audio2audio noise ladder split across sibling per-adapter staged dirs
    (a2a_kaikkialla_evr1x / a2a_kaikkialla_newstack) -- CONTINUITY: "it's the
    same song at increasing depths, playhead continuity is the whole point."
    member_names: the sibling staged dir names (their clips are referenced via
    relative ../<member>/ paths, same pattern as write_composed_sweep_folder)."""
    staged_dir = f"{OUT}/{kind}/{name}"
    stem_re = re.compile(r"^a2a_nl(?P<nl>\d+)$")
    by_nl = {}  # nl (int) -> {member: clip_rel_path}
    for member in member_names:
        member_dir = f"{OUT}/{kind}/{member}"
        if not os.path.isdir(member_dir):
            continue
        for f in os.listdir(member_dir):
            if not f.endswith(".m4a"):
                continue
            stem = f[:-4]
            m = stem_re.match(stem)
            if not m:
                continue
            by_nl.setdefault(int(m["nl"]), {})[member] = f"../{member}/{f}"
    if not by_nl:
        return False

    doc = head(f"{label} — evals", depth=2)
    doc += ('<p class="nav"><a href="../../index.html">← all evals</a>'
            '<a href="https://aavepyora.online/files/">the studio</a></p>')
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    doc += eval_grid.provenance_html(findings, status, known_pages)
    doc += (f'<p class="faint">{len(by_nl)} noise levels x {len(member_names)} adapters · same song, same '
            'playhead across every cell -- switching rows/columns keeps position, so you can hear exactly '
            'where it stops being the song and starts being the model</p>')
    doc += '<table class="tc-table"><tr><th>noise level</th>'
    for member in member_names:
        adapter_lbl = re.sub(rf"^{re.escape(name)}_", "", member) if member.startswith(f"{name}_") else member
        doc += f'<th>{html.escape(adapter_lbl)}</th>'
    doc += '</tr>'
    for nl in sorted(by_nl):
        doc += f'<tr><td>{nl/100:.2f}</td>'
        for member in member_names:
            c = by_nl[nl].get(member)
            if c:
                doc += f'<td class="cell tc-play" data-src="{html.escape(c)}" onclick="play(this)">▶</td>'
            else:
                doc += '<td class="tc-blank">·</td>'
        doc += '</tr>'
    doc += '</table>' + PLAYER_JS
    doc += '<footer>aavepyora.online · evals · same-playhead · full-track noise ladder</footer></div></body></html>'
    os.makedirs(staged_dir, exist_ok=True)
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

def write_memo_a2a_folder(kind, name, label, purpose, date_str, clips,
                           findings=None, status=None, known_pages=None):
    """Row=noise-level, column=checkpoint/cfg variant table for the a2a
    memorized-checkpoint hypothesis test (CONTINUITY, 2026-07-09/10): does an
    overtrained late checkpoint make a BETTER a2a/style-transfer tool at low CFG?
    Single staged folder (not sibling dirs like write_a2a_ladder_folder), clips
    named <variant>__a2a_nl<NN>.m4a. Includes the spec-§14 plain-language
    explainer block (Kim, 2026-07-10: every eval page also serves a "what does
    this teach" audience, not just the listening tool + technical-recipe ones)."""
    staged_dir = f"{OUT}/{kind}/{name}"
    stem_re = re.compile(r"^(?P<variant>[a-z0-9]+_cfg\d+)__a2a_nl(?P<nl>\d+)$")
    variants, by_nl = [], {}  # variant order preserved by first sight; nl -> {variant: filename}
    for f in sorted(os.listdir(staged_dir)) if os.path.isdir(staged_dir) else []:
        if not f.endswith(".m4a"):
            continue
        m = stem_re.match(f[:-4])
        if not m:
            continue
        v, nl = m["variant"], int(m["nl"])
        if v not in variants:
            variants.append(v)
        by_nl.setdefault(nl, {})[v] = f
    if not by_nl:
        return False

    doc = head(f"{label} — evals", depth=2)
    doc += ('<p class="nav"><a href="../../index.html">← all evals</a>'
            '<a href="https://aavepyora.online/files/">the studio</a></p>')
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    doc += (
        '<div class="findings-box"><span class="lbl">What this tests</span>'
        'The Underfit-memo prediction: a checkpoint that reads "overtrained" for plain '
        'text-to-audio (it has absorbed a strong style prior) should actually be the '
        '<b>best</b> tool for audio-to-audio / style-transfer, run at <b>low CFG</b> — '
        'low CFG lets that absorbed style dominate over the prompt, pulling the input '
        'track decisively into the trained style. This page compares a late/memorized '
        'checkpoint (ep63) against an early one (ep7), each re-rendering the same '
        'source track at increasing <code>init_noise_level</code> (nl) — higher nl = '
        'more of the model\'s own style, less of the original recording. Listen for '
        'where the source stops being recognizable and starts sounding like the model, '
        'and whether the late checkpoint gets there more gracefully than the early one.</div>'
    )
    doc += eval_grid.provenance_html(findings, status, known_pages)
    doc += (f'<p class="faint">{len(by_nl)} noise levels x {len(variants)} checkpoint/cfg variants · '
            'same source track, same playhead across every cell — switching rows/columns keeps '
            'position, so you can hear the SAME moment in the track at every setting</p>')
    doc += '<table class="tc-table"><tr><th>noise level</th>'
    for v in variants:
        doc += f'<th>{html.escape(v)}</th>'
    doc += '</tr>'
    for nl in sorted(by_nl):
        doc += f'<tr><td>{nl/100:.2f}</td>'
        for v in variants:
            f = by_nl[nl].get(v)
            if f:
                doc += f'<td class="cell tc-play" data-src="{html.escape(f)}" onclick="play(this)">▶</td>'
            else:
                doc += '<td class="tc-blank">·</td>'
        doc += '</tr>'
    doc += '</table>' + PLAYER_JS
    doc += '<footer>aavepyora.online · evals · same-playhead · memorized-checkpoint a2a test</footer></div></body></html>'
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

def write_chroma_morph_folder(kind, name, label, purpose, date_str, clips, source_dir,
                               findings=None, status=None, known_pages=None):
    """Real-track transition compare with chroma-morph LatCH steering vs a plain
    reference, grouped pair -> window -> noise-level (CONTINUITY, 2026-07-07:
    "grouped pair -> window -> nl with chroma/plain adjacent"). Filename
    convention: {A}2{B}__w{window}_nl{NN}_{chroma|plain}.wav."""
    stem_re = re.compile(r"^(?P<pair>\w+2\w+)__w(?P<window>\d+)_nl(?P<nl>\d+)_(?P<variant>chroma|plain)$")
    by_pair = {}  # pair -> window -> nl -> {variant: clip}
    for c in clips:
        stem = re.sub(r"\.m4a$", "", c)
        m = stem_re.match(stem)
        if not m:
            continue
        window = int(m["window"])
        by_pair.setdefault(m["pair"], {}).setdefault(window, {}).setdefault(int(m["nl"]), {})[m["variant"]] = c
    if not by_pair:
        return False

    # preserve run_meta's documented pair order if present, else alphabetical
    pair_order = sorted(by_pair)
    meta_path = f"{source_dir}/run_meta.json" if source_dir else None
    if meta_path and os.path.exists(meta_path):
        try:
            meta = json.load(open(meta_path))
            declared = [f"{a}2{b}" for a, b in meta.get("pairs", [])]
            # preserve declared order for pairs that ARE present, but never
            # silently drop extra undeclared pairs the data actually has
            # (2026-07-07: chroma_morph_barsnap mixes an old kaikki-pair batch
            # with a newer phreaky/angelic/heron batch -- both must show)
            known = [p for p in declared if p in by_pair]
            extra = sorted(p for p in by_pair if p not in declared)
            if known:
                pair_order = known + extra
        except Exception:
            pass

    staged_dir = f"{OUT}/{kind}/{name}"
    doc = head(f"{label} — evals", depth=2)
    doc += ('<p class="nav"><a href="../../index.html">← all evals</a>'
            '<a href="https://aavepyora.online/files/">the studio</a></p>')
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    doc += eval_grid.provenance_html(findings, status, known_pages)
    doc += (f'<p class="faint">{len(clips)} clips, {len(pair_order)} track pairs · same-playhead · '
            'chroma = the stem-chroma LatCH head morphing A-chroma→B-chroma across the window, '
            'plain = the reference without chroma steering</p>')
    for pair in pair_order:
        by_window = by_pair[pair]
        a, _, b = pair.partition("2")
        doc += f'<h2><span class="mark">§</span> {html.escape(a)} → {html.escape(b)}</h2>'
        for window in sorted(by_window):
            by_nl = by_window[window]
            dur = window / _LF_HZ
            doc += f'<h3>{window}-frame ({dur:.0f}s)</h3>'
            doc += '<table class="tc-table"><tr><th>noise level</th><th>chroma</th><th>plain</th></tr>'
            for nl in sorted(by_nl):
                row = by_nl[nl]
                doc += f'<tr><td>{nl/100:.2f}</td>'
                for variant in ("chroma", "plain"):
                    c = row.get(variant)
                    if c:
                        doc += f'<td class="cell tc-play" data-src="{html.escape(c)}" onclick="play(this)">▶</td>'
                    else:
                        doc += '<td class="tc-blank">·</td>'
                doc += '</tr>'
            doc += '</table>'
    doc += PLAYER_JS
    doc += '<footer>aavepyora.online · evals · same-playhead · chroma-morph transition compare</footer></div></body></html>'
    os.makedirs(staged_dir, exist_ok=True)
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

def write_chroma_pure_folder(kind, name, label, purpose, date_str, clips, source_dir,
                              findings=None, status=None, known_pages=None):
    """PURE real-track transition compare: original A/B audio intact outside
    the window, only the bridge is inpaint-generated (chroma-morph guided vs
    plain). Same pair -> window grouping as write_chroma_morph_folder, but
    NO noise-level dimension (CONTINUITY, 2026-07-07) -- one chroma/plain pair
    per window, not an nl-indexed table. Filename convention:
    {A}2{B}__w{window}_{method}_{chroma|plain}.wav."""
    stem_re = re.compile(r"^(?P<pair>\w+2\w+)__w(?P<window>\d+)_(?P<method>\w+?)_(?P<variant>chroma|plain)$")
    by_pair = {}  # pair -> window -> {variant: clip}
    for c in clips:
        stem = re.sub(r"\.m4a$", "", c)
        m = stem_re.match(stem)
        if not m:
            continue
        by_pair.setdefault(m["pair"], {}).setdefault(int(m["window"]), {})[m["variant"]] = c
    if not by_pair:
        return False
    pair_order = sorted(by_pair)
    meta_path = f"{source_dir}/run_meta.json" if source_dir else None
    if meta_path and os.path.exists(meta_path):
        try:
            meta = json.load(open(meta_path))
            declared = [f"{a}2{b}" for a, b in meta.get("pairs", [])]
            # preserve declared order for pairs that ARE present, but never
            # silently drop extra undeclared pairs the data actually has
            # (2026-07-07: chroma_morph_barsnap mixes an old kaikki-pair batch
            # with a newer phreaky/angelic/heron batch -- both must show)
            known = [p for p in declared if p in by_pair]
            extra = sorted(p for p in by_pair if p not in declared)
            if known:
                pair_order = known + extra
        except Exception:
            pass

    staged_dir = f"{OUT}/{kind}/{name}"
    doc = head(f"{label} — evals", depth=2)
    doc += ('<p class="nav"><a href="../../index.html">← all evals</a>'
            '<a href="https://aavepyora.online/files/">the studio</a></p>')
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    doc += eval_grid.provenance_html(findings, status, known_pages)
    doc += (f'<p class="faint">{len(clips)} clips, {len(pair_order)} track pairs · same-playhead · '
            'original A/B audio is bit-intact outside the window; only the bridge is inpaint-generated '
            '(chroma = stem-chroma LatCH morphing A-chroma→B-chroma, plain = same inpaint, no guidance)</p>')
    for pair in pair_order:
        by_window = by_pair[pair]
        a, _, b = pair.partition("2")
        doc += f'<h2><span class="mark">§</span> {html.escape(a)} → {html.escape(b)}</h2>'
        doc += '<table class="tc-table"><tr><th>window</th><th>chroma</th><th>plain</th></tr>'
        for window in sorted(by_window):
            row = by_window[window]
            dur = window / _LF_HZ
            doc += f'<tr><td>{window}f ({dur:.0f}s)</td>'
            for variant in ("chroma", "plain"):
                c = row.get(variant)
                if c:
                    doc += f'<td class="cell tc-play" data-src="{html.escape(c)}" onclick="play(this)">▶</td>'
                else:
                    doc += '<td class="tc-blank">·</td>'
            doc += '</tr>'
        doc += '</table>'
    doc += PLAYER_JS
    doc += '<footer>aavepyora.online · evals · same-playhead · pure chroma transition compare</footer></div></body></html>'
    os.makedirs(staged_dir, exist_ok=True)
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

def write_transitions3_folder(kind, name, label, purpose, date_str, clips,
                               findings=None, status=None, known_pages=None):
    """transitions3 family (Kim's recipe): pure-original basis + follow
    beatmatch + onset-concurrence fine-align + chroma slerp + sine noising,
    with an optional seam-inpaint addendum at 128/256/512 frames. CONTINUITY,
    2026-07-07: "grouping pair -> seam-size (none/128/256/512 columns) so the
    seam contribution reads left-to-right." The 3 source dirs on Mantu1
    (transitions3_sweep/seam128_256/seam512) are transcoded into ONE combined
    staged folder (filenames are unique across all 3 -- no collision risk),
    so this reads run_meta.json from the STAGED dir directly rather than
    taking a source_dir param (there's no single Mantu dir to point at).
    Filename convention: {A}2{B}__w{window}_nl{NN}[_seam{size}]_{chroma|plain}.wav
    (seam absent = the baseline "none" column)."""
    stem_re = re.compile(
        r"^(?P<pair>\w+2\w+)__w(?P<window>\d+)_nl(?P<nl>\d+)(?:_seam(?P<seam>\d+))?_(?P<variant>chroma|plain)$")
    by_pair = {}  # pair -> window -> seam ("none"/"128"/"256"/"512") -> {variant: clip}
    for c in clips:
        stem = re.sub(r"\.m4a$", "", c)
        m = stem_re.match(stem)
        if not m:
            continue
        seam = m["seam"] or "none"
        by_pair.setdefault(m["pair"], {}).setdefault(int(m["window"]), {}).setdefault(seam, {})[m["variant"]] = c
    if not by_pair:
        return False
    # this writer's regex (seam optional) is a strict superset of
    # write_chroma_morph_folder's (no-seam-only) -- only claim the folder if
    # it actually HAS seam variety; a plain nl-based dir with zero seam clips
    # isn't a transitions3 seam-sweep, just a regular chroma_morph dir, and
    # should fall through to that writer instead.
    has_seam = any(seam != "none" for by_window in by_pair.values()
                   for by_seam in by_window.values() for seam in by_seam)
    if not has_seam:
        return False
    pair_order = sorted(by_pair)
    staged_dir = f"{OUT}/{kind}/{name}"
    meta_path = f"{staged_dir}/run_meta.json"
    if os.path.exists(meta_path):
        try:
            meta = json.load(open(meta_path))
            declared = [f"{a}2{b}" for a, b in meta.get("pairs", [])]
            known = [p for p in declared if p in by_pair]
            extra = sorted(p for p in by_pair if p not in declared)
            if known:
                pair_order = known + extra
        except Exception:
            pass

    SEAM_ORDER = ["none", "128", "256", "512"]
    doc = head(f"{label} — evals", depth=2)
    doc += ('<p class="nav"><a href="../../index.html">← all evals</a>'
            '<a href="https://aavepyora.online/files/">the studio</a></p>')
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    doc += eval_grid.provenance_html(findings, status, known_pages)
    doc += (f'<p class="faint">{len(clips)} clips, {len(pair_order)} track pairs · same-playhead · '
            'seam columns read left-to-right (no seam → 128f → 256f → 512f seam-inpaint addendum), '
            'chroma/plain adjacent within each</p>')
    for pair in pair_order:
        by_window = by_pair[pair]
        a, _, b = pair.partition("2")
        doc += f'<h2><span class="mark">§</span> {html.escape(a)} → {html.escape(b)}</h2>'
        doc += '<table class="tc-table"><tr><th>window</th>'
        for seam in SEAM_ORDER:
            seam_lbl = "no seam" if seam == "none" else f"seam {seam}f"
            doc += f'<th colspan="2">{html.escape(seam_lbl)}</th>'
        doc += '</tr><tr><th></th>'
        for _ in SEAM_ORDER:
            doc += '<th>chroma</th><th>plain</th>'
        doc += '</tr>'
        for window in sorted(by_window):
            by_seam = by_window[window]
            dur = window / _LF_HZ
            doc += f'<tr><td>{window}f ({dur:.0f}s)</td>'
            for seam in SEAM_ORDER:
                row = by_seam.get(seam, {})
                for variant in ("chroma", "plain"):
                    c = row.get(variant)
                    if c:
                        doc += f'<td class="cell tc-play" data-src="{html.escape(c)}" onclick="play(this)">▶</td>'
                    else:
                        doc += '<td class="tc-blank">·</td>'
            doc += '</tr>'
        doc += '</table>'
    doc += PLAYER_JS
    doc += '<footer>aavepyora.online · evals · same-playhead · transitions3 seam-sweep compare</footer></div></body></html>'
    os.makedirs(staged_dir, exist_ok=True)
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

# CONTINUITY, 2026-07-08: "Kim asked for ALL avp models on ONE page -- arm x
# epoch grid, prompt selector, same-playhead cells, per-ckpt training params."
# Params pulled directly from each arm's checkpoint (lora_config + optimizer
# param_groups) since none of the training run dirs carry a separate args
# sidecar -- a one-time extraction, baked in here rather than re-loading
# checkpoints on every build_evals.py run.
AVP_BOARD_ARMS = ["r16_plain", "r16_familiarity", "r16_originals", "r128adj", "r128adj_final"]
AVP_BOARD_PARAMS = {
    "r16_plain": "rank 16 · alpha 16 · dora-rows · lr 2e-4 · Fusion (spectral)",
    "r16_familiarity": "rank 16 · alpha 16 · dora-rows · lr 2e-4 · Fusion (spectral) · novelty-gated",
    "r16_originals": "rank 16 · alpha 16 · dora-rows · lr 2e-4 · Fusion (spectral) · originals-only corpus (no augs) — the aug-theory control arm (D')",
    "r128adj": "rank 128 · alpha 45 · dora-rows · lr 2e-4 · Fusion (spectral)",
    "r128adj_final": "rank 128 · alpha 45 · dora-rows · lr 2e-4 · Fusion (spectral) · final checkpoint",
    "armG": "rank 128 · alpha 45 · dora-rows · lr 1e-4 · Fusion (spectral) · aug10 (10% random-augmentation sample)",
    "freeform": "rank 16 · alpha 16 · dora-rows · lr 2e-4 · Fusion (spectral) · single freeform caption (not the trigger word)",
    "everything_r128": "rank 128 · alpha 128 · dora-rows · lr 2e-4 · Fusion (spectral) · trained on the GOA catalogue (in-distribution baseline)",
    "r64": "rank 64 · alpha 32 · dora-rows · Fusion (spectral) · wd 0.01 · tiered Flamingo/Granite captions (conditioning-collapse cure) · LR bracket: 2e-4 (r64_lr2e4 rows) vs 1e-4 (r64_lr1e4 rows)",
}
# other single-arm ckpt-ladder boards (see write_avp_ladder_folder) -> which
# AVP_BOARD_PARAMS key describes their training recipe for the click readout.
AVP_LADDER_BOARDS = {
    "avp_board_armG": "armG",
    "avp_board_freeform": "freeform",
    "goa_everything_board": "everything_r128",
    "avp_board_r64": "r64",
}
# Canonical prompt-key -> full text, shared across every avp board (a board's
# OWN run_meta.json "prompts" dict always wins where present -- avp_board_seeds
# carries the full 7-prompt set incl. kimlong's long-form text -- this is only
# the fallback for boards/keys with no sidecar entry). Kim, 2026-07-09: prompts
# and recipe params must be VISIBLE at a glance while auditioning, not hidden
# behind hover/click -- see _prompt_legend_html()/_recipe_line_html() below.
AVP_PROMPT_TEXT = {
    "trig": "aavepyörä",
    "trig2": "aavepyora",
    "trigdesc": "aavepyörä + a style-descriptor suffix (exact wording not recorded)",
    "upbeat": "upbeat dance music",
    "goa1": "aggressive upbeat goa trance",
    "goa2": "Hypnotic melodic goa trance",
    "psy": "psytrance, 140 bpm",
    "freeform": "freeform upbeat positive dance music",
    "goa": "a goa-trance steerability prompt (exact wording not recorded in this board's sidecar)",
    "empty": "(the empty string — no prompt at all, the absorption-crossover diagnostic)",
}

def _prompt_legend_html(prompt_keys, prompt_text):
    """Always-visible prompt-key -> full-text legend (Kim, 2026-07-09: not
    hover-only -- he needs to read what he's hearing while auditioning)."""
    merged = {**AVP_PROMPT_TEXT, **prompt_text}
    items = "".join(
        f'<li><code>{html.escape(p)}</code>: {html.escape(merged.get(p, "(text not recorded)"))}</li>'
        for p in prompt_keys)
    return f'<div class="prompt-legend"><b>Prompts:</b><ul>{items}</ul></div>'

def _recipe_line_html(label, params_label):
    return f'<p class="faint"><b>Recipe{" — " + html.escape(label) if label else ""}:</b> {html.escape(params_label)}</p>'
AVP_BOARD_JS_TEMPLATE = r"""
(function(){
const D = __DATA__;
const ARMS = __ARMS__;
const PROMPTS = __PROMPTS__;
const PARAMS = __PARAMS__;
const wrap = document.getElementById(__WRAP_ID__);
const audio = new Audio(); let curKey = null;
audio.addEventListener('ended', () => { markPlaying(null); curKey = null; });
function markPlaying(key) {
  document.querySelectorAll('.eg-cell').forEach(el => el.classList.toggle('playing', el.dataset.key === key && key !== null));
}
function seekAndPlay(a, pos) {
  const go = () => { try { a.currentTime = ((a.duration && pos > a.duration - 1) ? 0 : Math.min(pos, (a.duration || 1e9) - 0.05)); } catch (e) {} a.play(); };
  if (a.readyState >= 3) { go(); return; }
  let done = false;
  const fire = () => { if (done) return; done = true; go(); };
  a.addEventListener('canplay', fire, { once: true });
  setTimeout(fire, 1200);
}
function play(el, key, r) {
  if (!r.clip) return;
  if (curKey === key) { audio.pause(); markPlaying(null); curKey = null; return; }
  curKey = key; markPlaying(key);
  audio.pause();
  audio.src = r.clip;
  seekAndPlay(audio, 0);
  const f = v => v == null ? '·' : v.toFixed(3);
  document.getElementById(__INFO_ID__).innerHTML =
    `<b>${r.arm}</b> · epoch${r.epoch} (step${r.step}) · ${r.prompt}<br>`
    + `${PARAMS[r.arm] || ''}<br>`
    + `flux-spike ${f(r.flux_spike)} · clicks/s ${f(r.clicks_per_s)} · silence ${f(r.silence_frac)} · onset density ${f(r.onset_dens)}/s`;
}

let prompt = PROMPTS[0];
const byKey = {};
D.forEach(r => { byKey[r.arm + '|' + r.epoch + '|' + r.prompt] = r; });

function render() {
  wrap.innerHTML = '';
  const bar = document.createElement('div'); bar.className = 'aud-bar';
  const select = document.createElement('select');
  PROMPTS.forEach(p => {
    const opt = document.createElement('option'); opt.value = p; opt.textContent = p;
    if (p === prompt) opt.selected = true;
    select.appendChild(opt);
  });
  select.onchange = () => { prompt = select.value; render(); };
  bar.appendChild(select);
  wrap.appendChild(bar);

  const epochs = [...new Set(D.map(r => r.epoch))].sort((a, b) => a - b);
  const table = document.createElement('table'); table.className = 'tc-table';
  const headRow = document.createElement('tr');
  headRow.appendChild(document.createElement('th'));
  epochs.forEach(e => { const th = document.createElement('th'); th.textContent = 'ep' + e; headRow.appendChild(th); });
  table.appendChild(headRow);
  ARMS.forEach(arm => {
    const tr = document.createElement('tr');
    const armTd = document.createElement('td'); armTd.textContent = arm; tr.appendChild(armTd);
    epochs.forEach(e => {
      const td = document.createElement('td');
      const r = byKey[arm + '|' + e + '|' + prompt];
      if (r && r.clip) {
        const key = arm + '|' + e + '|' + prompt;
        const cell = document.createElement('span');
        cell.className = 'eg-cell'; cell.textContent = '▶'; cell.dataset.key = key;
        cell.onclick = () => play(cell, key, r);
        td.appendChild(cell);
      } else {
        td.textContent = '·'; td.className = 'tc-blank';
      }
      tr.appendChild(td);
    });
    table.appendChild(tr);
  });
  wrap.appendChild(table);
}
render();
})();
"""

def write_avp_board_folder(kind, name, label, purpose, date_str,
                            findings=None, status=None, known_pages=None):
    """ALL avp DoRA arms on one board: arm x epoch grid + a prompt selector,
    per-ckpt training params + per-clip glitch-triage metrics in the click
    readout. Filename convention: {arm}__epoch{E}_step{S}__{prompt}.wav."""
    staged_dir = f"{OUT}/{kind}/{name}"
    stem_re = re.compile(r"^epoch(?P<epoch>\d+)_step(?P<step>\d+)$")
    triage = {}
    triage_path = f"{staged_dir}/glitch_triage.json"
    if os.path.exists(triage_path):
        try:
            for row in json.load(open(triage_path)):
                triage[(row["arm"], row["ckpt"], row["prompt"])] = row
        except Exception:
            pass

    records = []
    for f in sorted(os.listdir(staged_dir)) if os.path.isdir(staged_dir) else []:
        if not f.endswith(".m4a"):
            continue
        stem = f[:-4]
        parts = stem.split("__")
        if len(parts) != 3:
            continue
        arm, ckpt_part, prompt = parts
        m = stem_re.match(ckpt_part)
        if not m:
            continue
        tr = triage.get((arm, ckpt_part, prompt), {})
        records.append({
            "arm": arm, "epoch": int(m["epoch"]), "step": int(m["step"]), "prompt": prompt,
            "clip": f, "flux_spike": tr.get("flux_spike"), "clicks_per_s": tr.get("clicks_per_s"),
            "silence_frac": tr.get("silence_frac"), "onset_dens": tr.get("onset_dens"),
        })
    if not records:
        return False

    arms = [a for a in AVP_BOARD_ARMS if any(r["arm"] == a for r in records)]
    prompts = sorted({r["prompt"] for r in records})

    doc = head(f"{label} — evals", depth=2)
    doc += ('<p class="nav"><a href="../../index.html">← all evals</a>'
            '<a href="https://aavepyora.online/files/">the studio</a></p>')
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    doc += eval_grid.provenance_html(findings, status, known_pages)
    doc += (f'<p class="faint">{len(records)} clips, {len(arms)} arms · pick a prompt, click a cell to play '
            '(shared playhead) · glitch-triage metrics show on click</p>')
    doc += '<div class="prompt-legend"><b>Arms (recipe):</b><ul>' + "".join(
        f'<li><code>{html.escape(a)}</code>: {html.escape(AVP_BOARD_PARAMS.get(a, ""))}</li>' for a in arms
    ) + '</ul></div>'
    doc += _prompt_legend_html(prompts, {})
    doc += '<div class="eg-info" id="avp-info">click a cell for its readout</div>'
    doc += '<div id="avp-wrap"></div>'
    js = (AVP_BOARD_JS_TEMPLATE
          .replace("__DATA__", json.dumps(records))
          .replace("__ARMS__", json.dumps(arms))
          .replace("__PROMPTS__", json.dumps(prompts))
          .replace("__PARAMS__", json.dumps(AVP_BOARD_PARAMS))
          .replace("__WRAP_ID__", "'avp-wrap'")
          .replace("__INFO_ID__", "'avp-info'"))
    doc += f'<script>{js}</script>'
    doc += '<footer>aavepyora.online · evals · same-playhead · avp DoRA board</footer></div></body></html>'
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

# Shared by the whole ckpt-ladder board family (avp_board_seeds / armG /
# freeform / goa_everything_board): {arm}__epoch{E}(_step{S}|_fine|_warm{W})
# __{prompt}__s{seed}[__st{strength}].wav. Row identity is the FULL TAG, not
# epoch alone -- dense re-run windows can share an epoch number under a
# different tag (avp_board_seeds has BOTH epoch31_fine and epoch31_step1152).
LADDER_STEM_RE = re.compile(
    r"^(?P<tag>epoch(?P<epoch>\d+)(?:_step(?P<step>\d+)|(?P<fine>_fine)|_warm(?P<warm>\d+))?)"
    r"__(?P<prompt>\w+)__s(?P<seed>\d+)(?:__st(?P<strength>\d+))?$"
)

def _parse_ladder_records(staged_dir, clip_prefix=""):
    """Parse a ckpt-ladder x prompt x seed [x DoRA strength] board's clips
    (see LADDER_STEM_RE). clip_prefix lets a caller outside staged_dir's own
    page (e.g. the cross-directory master page) point clip paths at the
    sibling directory instead of the same one."""
    records = []
    for f in sorted(os.listdir(staged_dir)) if os.path.isdir(staged_dir) else []:
        if not f.endswith(".m4a"):
            continue
        stem = f[:-4]
        parts = stem.split("__", 1)
        if len(parts) != 2:
            continue
        arm, rest = parts
        m = LADDER_STEM_RE.match(rest)
        if not m:
            continue
        if m["step"] is not None:
            kind, step, warm = "step", int(m["step"]), None
        elif m["fine"]:
            kind, step, warm = "fine", None, None
        elif m["warm"] is not None:
            kind, step, warm = "warm", None, int(m["warm"])
        else:
            kind, step, warm = "step", None, None  # bare "epochN" tag, no step count recorded
        records.append({
            "arm": arm, "tag": m["tag"], "epoch": int(m["epoch"]),
            "kind": kind, "step": step, "warm": warm,
            "prompt": m["prompt"], "seed": int(m["seed"]),
            "strength": int(m["strength"]) if m["strength"] else None,
            "clip": clip_prefix + f,
        })
    # A board only has a genuine DoRA-strength AXIS when 2+ distinct values
    # are actually swept (armG/freeform: {6,10}). A single stray value mixed
    # with un-tagged records (avp_board_seeds has 15 accidental __st10
    # duplicate renders alongside their un-suffixed twins at the same
    # tag/prompt/seed -- redundant renders, not a sweep) is noise: normalize
    # strength away for the whole board so those duplicates fold into their
    # untagged counterpart instead of silently vanishing from every lookup
    # that defaults to "no strength selected" (found via the master-page
    # harness, 2026-07-09 -- the whole ep31 row rendered blank because the
    # lone stray strength=10 became the default while 451/466 records had
    # strength=None).
    if len({r["strength"] for r in records if r["strength"] is not None}) < 2:
        for r in records:
            r["strength"] = None
    return records

AVP_LADDER_JS_TEMPLATE = r"""
(function(){
const D = __DATA__;
const PROMPT_KEYS = __PROMPT_KEYS__;
const PROMPT_TEXT = __PROMPT_TEXT__;
const SEEDS = __SEEDS__;
const STRENGTHS = __STRENGTHS__;
const PARAMS_LABEL = __PARAMS_LABEL__;
const SWEET_EPOCHS = __SWEET_EPOCH__;
const wrap = document.getElementById(__WRAP_ID__);
const audio = new Audio(); let curKey = null;
audio.addEventListener('ended', () => { markPlaying(null); curKey = null; });
function markPlaying(key) {
  document.querySelectorAll('.eg-cell').forEach(el => el.classList.toggle('playing', el.dataset.key === key && key !== null));
}
function seekAndPlay(a, pos) {
  const go = () => { try { a.currentTime = ((a.duration && pos > a.duration - 1) ? 0 : Math.min(pos, (a.duration || 1e9) - 0.05)); } catch (e) {} a.play(); };
  if (a.readyState >= 3) { go(); return; }
  let done = false;
  const fire = () => { if (done) return; done = true; go(); };
  a.addEventListener('canplay', fire, { once: true });
  setTimeout(fire, 1200);
}
// Row identity is (arm, tag), NOT tag alone -- a multi-arm ladder (e.g. two
// LR variants of the same recipe) can have BOTH arms hit the same epoch
// number under the SAME tag shape (both "epoch00"), which would collide if
// keyed by tag alone. Non-"base" arms only get prefixed into the row label
// when more than one is actually present (single-arm boards stay uncluttered).
const NON_BASE_ARMS = [...new Set(D.map(r => r.arm))].filter(a => a !== 'base');
const MULTI_ARM = NON_BASE_ARMS.length > 1;
function rowKey(r) { return r.arm + '|' + r.tag; }
function rowLabel(r) {
  if (r.arm === 'base') return 'base (no adapter)';
  let s = 'ep' + r.epoch;
  if (r.kind === 'fine') s += ' fine';
  else if (r.kind === 'warm') s += ' warm' + r.warm;
  return MULTI_ARM ? r.arm + ' · ' + s : s;
}
function play(el, key, r) {
  if (!r.clip) return;
  if (curKey === key) { audio.pause(); markPlaying(null); curKey = null; return; }
  curKey = key; markPlaying(key);
  audio.pause();
  audio.src = r.clip;
  seekAndPlay(audio, 0);
  const stepBit = r.step != null ? ` (step${r.step})` : '';
  const strBit = r.strength != null ? ` · DoRA ${(r.strength / 10).toFixed(1)}` : '';
  document.getElementById(__INFO_ID__).innerHTML =
    `<b>${rowLabel(r)}</b>${stepBit} · seed ${r.seed}${strBit}<br>`
    + `<b>${r.prompt}</b>: ${PROMPT_TEXT[r.prompt] || ''}<br>`
    + PARAMS_LABEL;
}

let seed = SEEDS[0];
let strength = STRENGTHS.length ? STRENGTHS[0] : null;
const byKey = {};
D.forEach(r => { byKey[rowKey(r) + '|' + r.prompt + '|' + r.seed + '|' + (r.strength ?? '')] = r; });

function render() {
  wrap.innerHTML = '';
  const bar = document.createElement('div'); bar.className = 'aud-bar';
  const seedSel = document.createElement('select');
  SEEDS.forEach(s => {
    const opt = document.createElement('option'); opt.value = s; opt.textContent = 'seed ' + s;
    if (s === seed) opt.selected = true;
    seedSel.appendChild(opt);
  });
  seedSel.onchange = () => { seed = Number(seedSel.value); render(); };
  bar.appendChild(seedSel);
  if (STRENGTHS.length > 1) {
    const stSel = document.createElement('select');
    STRENGTHS.forEach(s => {
      const opt = document.createElement('option'); opt.value = s; opt.textContent = 'DoRA ' + (s / 10).toFixed(1);
      if (s === strength) opt.selected = true;
      stSel.appendChild(opt);
    });
    stSel.onchange = () => { strength = Number(stSel.value); render(); };
    bar.appendChild(stSel);
  }
  wrap.appendChild(bar);

  const kindPri = { step: 0, fine: 1, warm: 2 };
  const rowsMap = new Map();
  D.forEach(r => { if (!rowsMap.has(rowKey(r))) rowsMap.set(rowKey(r), r); });
  const rows = [...rowsMap.values()].sort((a, b) =>
    (MULTI_ARM ? a.arm.localeCompare(b.arm) : 0) ||
    a.epoch - b.epoch || kindPri[a.kind] - kindPri[b.kind] || (a.warm || 0) - (b.warm || 0));

  const table = document.createElement('table'); table.className = 'tc-table';
  const headRow = document.createElement('tr');
  headRow.appendChild(document.createElement('th'));
  PROMPT_KEYS.forEach(p => { const th = document.createElement('th'); th.textContent = p; th.title = PROMPT_TEXT[p] || ''; headRow.appendChild(th); });
  table.appendChild(headRow);
  // Mark the BEST-available row per sweet epoch (rows are already sorted
  // step-before-fine-before-warm within an epoch, so the first match per
  // (arm, epoch) is the best kind) -- an epoch may have no 'step' variant at
  // all (avp_board_seeds' ep8 only exists as 'fine', from the dense window).
  const markedSweet = new Set();
  rows.forEach(row => {
    const tr = document.createElement('tr');
    const sweetKey = row.arm + '|' + row.epoch;
    if (SWEET_EPOCHS.includes(row.epoch) && !markedSweet.has(sweetKey)) {
      tr.className = 'tc-sweet';
      markedSweet.add(sweetKey);
    }
    const rowTd = document.createElement('td'); rowTd.textContent = rowLabel(row); tr.appendChild(rowTd);
    PROMPT_KEYS.forEach(p => {
      const td = document.createElement('td');
      const key = rowKey(row) + '|' + p + '|' + seed + '|' + (strength ?? '');
      const r = byKey[key];
      if (r && r.clip) {
        const cell = document.createElement('span');
        cell.className = 'eg-cell'; cell.textContent = '▶'; cell.dataset.key = key;
        cell.onclick = () => play(cell, key, r);
        td.appendChild(cell);
      } else {
        td.textContent = '·'; td.className = 'tc-blank';
      }
      tr.appendChild(td);
    });
    table.appendChild(tr);
  });
  wrap.appendChild(table);
}
render();
})();
"""

def write_avp_ladder_folder(kind, name, label, purpose, date_str, params_label,
                             sweet_epoch=None, findings=None, status=None, known_pages=None):
    """Ckpt-ladder x prompt-columns board with a seed selector and, where the
    board sweeps DoRA strength, a strength selector. Shared by the whole
    ladder-board family (avp_board_seeds / avp_board_armG / avp_board_freeform
    / goa_everything_board) -- see LADDER_STEM_RE / _parse_ladder_records.
    sweet_epoch, if given (an int or a list of ints), highlights those
    epochs' plain-ladder ('step') rows -- avp_board_seeds' degradation_report_v2
    found TWO candidate sweet-spot islands (ep31: narrow, on the ringing
    shoulder; ep7-9: spectrally healthier), not a single point."""
    sweet_epochs = (sweet_epoch if isinstance(sweet_epoch, list)
                     else ([sweet_epoch] if sweet_epoch is not None else []))
    staged_dir = f"{OUT}/{kind}/{name}"
    records = _parse_ladder_records(staged_dir)
    if not records:
        return False

    prompt_text = {}
    meta_path = f"{staged_dir}/run_meta.json"
    if os.path.exists(meta_path):
        try:
            prompt_text = json.load(open(meta_path)).get("prompts", {})
        except Exception:
            pass
    prompt_keys = list(prompt_text) if prompt_text else sorted({r["prompt"] for r in records})
    prompt_text_merged = {**AVP_PROMPT_TEXT, **prompt_text}
    seeds = sorted({r["seed"] for r in records})
    strengths = sorted({r["strength"] for r in records if r["strength"] is not None})
    n_rows = len({(r["arm"], r["tag"]) for r in records})

    doc = head(f"{label} — evals", depth=2)
    doc += ('<p class="nav"><a href="../../index.html">← all evals</a>'
            '<a href="https://aavepyora.online/files/">the studio</a></p>')
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    doc += eval_grid.provenance_html(findings, status, known_pages)
    extra = f' x {len(strengths)} DoRA strengths' if len(strengths) > 1 else ''
    doc += (f'<p class="faint">{len(records)} clips, {n_rows} checkpoints x {len(prompt_keys)} prompts x '
            f'{len(seeds)} seeds{extra} · pick a seed{" / strength" if len(strengths) > 1 else ""}, '
            'click a cell to play (shared playhead)</p>')
    doc += _recipe_line_html("", params_label)
    doc += _prompt_legend_html(prompt_keys, prompt_text)
    doc += '<div class="eg-info" id="ladder-info">click a cell for its readout</div>'
    doc += '<div id="ladder-wrap"></div>'
    js = (AVP_LADDER_JS_TEMPLATE
          .replace("__DATA__", json.dumps(records))
          .replace("__PROMPT_KEYS__", json.dumps(prompt_keys))
          .replace("__PROMPT_TEXT__", json.dumps(prompt_text_merged))
          .replace("__SEEDS__", json.dumps(seeds))
          .replace("__STRENGTHS__", json.dumps(strengths))
          .replace("__PARAMS_LABEL__", json.dumps(params_label))
          .replace("__SWEET_EPOCH__", json.dumps(sweet_epochs))
          .replace("__WRAP_ID__", "'ladder-wrap'")
          .replace("__INFO_ID__", "'ladder-info'"))
    doc += f'<script>{js}</script>'
    doc += '<footer>aavepyora.online · evals · same-playhead · avp ckpt-ladder board</footer></div></body></html>'
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

def write_avp_seeds_folder(kind, name, label, purpose, date_str,
                            findings=None, status=None, known_pages=None):
    """avp originals arm x 7 prompts x 3 seeds (Kim's prompting-issue probe):
    ckpt-rows x prompt-columns + a seed selector. Thin wrapper over
    write_avp_ladder_folder — kept as its own name for main()'s routing chain,
    marks ep8 and ep31 as the two confirmed sweet-spot islands
    (degradation_report_v2: ep31 is a narrow local spike on the ringing
    shoulder; ep7-9 is a spectrally healthier second island)."""
    return write_avp_ladder_folder(kind, name, label, purpose, date_str,
                                    AVP_BOARD_PARAMS.get("r16_originals", ""),
                                    sweet_epoch=[8, 31], findings=findings, status=status,
                                    known_pages=known_pages)

# Kim's ask (via CONTINUITY, 2026-07-09): ONE page consolidating every avp
# render dir -- arm x epoch grid (avp_board) + the ckpt-ladder boards, all as
# sections on one page with a shared playhead across ALL of them (not per
# section -- this is a genuinely new template, not a reuse of the per-dir
# writers above, because those each instantiate their own Audio()).
AVP_MASTER_JS_TEMPLATE = r"""
(function(){
const SECTIONS = __SECTIONS__;
const audio = new Audio(); let curKey = null;
audio.addEventListener('ended', () => { markPlaying(null); curKey = null; });
function markPlaying(key) {
  document.querySelectorAll('.eg-cell').forEach(el => el.classList.toggle('playing', el.dataset.key === key && key !== null));
}
function seekAndPlay(a, pos) {
  const go = () => { try { a.currentTime = ((a.duration && pos > a.duration - 1) ? 0 : Math.min(pos, (a.duration || 1e9) - 0.05)); } catch (e) {} a.play(); };
  if (a.readyState >= 3) { go(); return; }
  let done = false;
  const fire = () => { if (done) return; done = true; go(); };
  a.addEventListener('canplay', fire, { once: true });
  setTimeout(fire, 1200);
}
function playClip(uniqueKey, clip, infoHtml, infoId) {
  if (!clip) return;
  if (curKey === uniqueKey) { audio.pause(); markPlaying(null); curKey = null; return; }
  curKey = uniqueKey; markPlaying(uniqueKey);
  audio.pause();
  audio.src = clip;
  seekAndPlay(audio, 0);
  document.getElementById(infoId).innerHTML = infoHtml;
}
function rowLabel(r) {
  if (r.arm === 'base') return 'base (no adapter)';
  let s = 'ep' + r.epoch;
  if (r.kind === 'fine') s += ' fine';
  else if (r.kind === 'warm') s += ' warm' + r.warm;
  return s;
}

function renderGridSection(sec) {
  const wrap = document.getElementById(sec.id + '-wrap');
  const infoId = sec.id + '-info';
  let prompt = sec.prompts[0];
  const byKey = {};
  sec.records.forEach(r => { byKey[r.arm + '|' + r.epoch + '|' + r.prompt] = r; });
  function render() {
    wrap.innerHTML = '';
    const bar = document.createElement('div'); bar.className = 'aud-bar';
    const sel = document.createElement('select');
    sec.prompts.forEach(p => {
      const opt = document.createElement('option'); opt.value = p; opt.textContent = p;
      if (p === prompt) opt.selected = true;
      sel.appendChild(opt);
    });
    sel.onchange = () => { prompt = sel.value; render(); };
    bar.appendChild(sel);
    wrap.appendChild(bar);
    const epochs = [...new Set(sec.records.map(r => r.epoch))].sort((a, b) => a - b);
    const table = document.createElement('table'); table.className = 'tc-table';
    const headRow = document.createElement('tr'); headRow.appendChild(document.createElement('th'));
    epochs.forEach(e => { const th = document.createElement('th'); th.textContent = 'ep' + e; headRow.appendChild(th); });
    table.appendChild(headRow);
    sec.arms.forEach(arm => {
      const tr = document.createElement('tr');
      const armTd = document.createElement('td'); armTd.textContent = arm; tr.appendChild(armTd);
      epochs.forEach(e => {
        const td = document.createElement('td');
        const r = byKey[arm + '|' + e + '|' + prompt];
        if (r && r.clip) {
          const key = sec.id + '|' + arm + '|' + e + '|' + prompt;
          const cell = document.createElement('span');
          cell.className = 'eg-cell'; cell.textContent = '▶'; cell.dataset.key = key;
          cell.onclick = () => playClip(key, r.clip,
            `<b>${r.arm}</b> · epoch${r.epoch} (step${r.step}) · ${r.prompt}<br>${sec.params[r.arm] || ''}`, infoId);
          td.appendChild(cell);
        } else {
          td.textContent = '·'; td.className = 'tc-blank';
        }
        tr.appendChild(td);
      });
      table.appendChild(tr);
    });
    wrap.appendChild(table);
  }
  render();
}

function renderLadderSection(sec) {
  const wrap = document.getElementById(sec.id + '-wrap');
  const infoId = sec.id + '-info';
  let seed = sec.seeds[0];
  let strength = sec.strengths.length ? sec.strengths[0] : null;
  const byKey = {};
  sec.records.forEach(r => { byKey[r.tag + '|' + r.prompt + '|' + r.seed + '|' + (r.strength ?? '')] = r; });
  function render() {
    wrap.innerHTML = '';
    const bar = document.createElement('div'); bar.className = 'aud-bar';
    const seedSel = document.createElement('select');
    sec.seeds.forEach(s => {
      const opt = document.createElement('option'); opt.value = s; opt.textContent = 'seed ' + s;
      if (s === seed) opt.selected = true;
      seedSel.appendChild(opt);
    });
    seedSel.onchange = () => { seed = Number(seedSel.value); render(); };
    bar.appendChild(seedSel);
    if (sec.strengths.length > 1) {
      const stSel = document.createElement('select');
      sec.strengths.forEach(s => {
        const opt = document.createElement('option'); opt.value = s; opt.textContent = 'DoRA ' + (s / 10).toFixed(1);
        if (s === strength) opt.selected = true;
        stSel.appendChild(opt);
      });
      stSel.onchange = () => { strength = Number(stSel.value); render(); };
      bar.appendChild(stSel);
    }
    wrap.appendChild(bar);
    const kindPri = { step: 0, fine: 1, warm: 2 };
    const rowsMap = new Map();
    sec.records.forEach(r => { if (!rowsMap.has(r.tag)) rowsMap.set(r.tag, r); });
    const rows = [...rowsMap.values()].sort((a, b) =>
      a.epoch - b.epoch || kindPri[a.kind] - kindPri[b.kind] || (a.warm || 0) - (b.warm || 0));
    const table = document.createElement('table'); table.className = 'tc-table';
    const headRow = document.createElement('tr'); headRow.appendChild(document.createElement('th'));
    sec.promptKeys.forEach(p => { const th = document.createElement('th'); th.textContent = p; th.title = sec.promptText[p] || ''; headRow.appendChild(th); });
    table.appendChild(headRow);
    // Mark the BEST-available row per sweet epoch (see the standalone
    // ladder-page template for why: an epoch may only exist as 'fine').
    const markedSweet = new Set();
    rows.forEach(row => {
      const tr = document.createElement('tr');
      const sweetKey = row.arm + '|' + row.epoch;
      if (sec.sweetEpochs && sec.sweetEpochs.includes(row.epoch) && !markedSweet.has(sweetKey)) {
        tr.className = 'tc-sweet';
        markedSweet.add(sweetKey);
      }
      const rowTd = document.createElement('td'); rowTd.textContent = rowLabel(row); tr.appendChild(rowTd);
      sec.promptKeys.forEach(p => {
        const td = document.createElement('td');
        const rowKey = row.tag + '|' + p + '|' + seed + '|' + (strength ?? '');
        const r = byKey[rowKey];
        if (r && r.clip) {
          const key = sec.id + '|' + rowKey;
          const cell = document.createElement('span');
          cell.className = 'eg-cell'; cell.textContent = '▶'; cell.dataset.key = key;
          const stepBit = r.step != null ? ` (step${r.step})` : '';
          const strBit = r.strength != null ? ` · DoRA ${(r.strength / 10).toFixed(1)}` : '';
          cell.onclick = () => playClip(key, r.clip,
            `<b>${rowLabel(r)}</b>${stepBit} · seed ${r.seed}${strBit}<br>`
            + `<b>${r.prompt}</b>: ${sec.promptText[r.prompt] || ''}<br>${sec.paramsLabel}`, infoId);
          td.appendChild(cell);
        } else {
          td.textContent = '·'; td.className = 'tc-blank';
        }
        tr.appendChild(td);
      });
      table.appendChild(tr);
    });
    wrap.appendChild(table);
  }
  render();
}

SECTIONS.forEach(sec => { if (sec.kind === 'grid') renderGridSection(sec); else renderLadderSection(sec); });
})();
"""

# Underfit-memo CFG-dynamics test (Kim/CONTINUITY, 2026-07-09): training-stage
# rows (a hand-picked cross-arm sequence, NOT an epoch ladder within one arm)
# x cfg-value columns, with a kimlong/empty-prompt toggle -- the empty-prompt
# column is the "absorption" diagnostic (does a late ckpt sound like Kim's
# style with NO prompt at all). Filename convention: {stage}__{prompt}__cfg{v}.wav.
AVP_CFG_SWEEP_STEM_RE = re.compile(r"^(?P<stage>\w+)__(?P<prompt>\w+)__cfg(?P<cfg>[\d.]+)$")
AVP_CFG_SWEEP_STAGE_ORDER = ["early_ep2", "mid_ep7", "sweet_ep31", "late_ep47", "armG_ep5"]
AVP_CFG_SWEEP_STAGE_RECIPE = {
    "early_ep2": "r16_originals, early-epoch focused re-render — " + AVP_BOARD_PARAMS.get("r16_originals", ""),
    "mid_ep7": AVP_BOARD_PARAMS.get("r16_originals", ""),
    "sweet_ep31": AVP_BOARD_PARAMS.get("r16_originals", ""),
    "late_ep47": AVP_BOARD_PARAMS.get("r16_originals", ""),
    "armG_ep5": AVP_BOARD_PARAMS.get("armG", ""),
}

AVP_CFG_SWEEP_JS_TEMPLATE = r"""
(function(){
const D = __DATA__;
const STAGES = __STAGES__;
const CFGS = __CFGS__;
const STAGE_LABEL = __STAGE_LABEL__;
const wrap = document.getElementById(__WRAP_ID__);
const audio = new Audio(); let curKey = null;
audio.addEventListener('ended', () => { markPlaying(null); curKey = null; });
function markPlaying(key) {
  document.querySelectorAll('.eg-cell').forEach(el => el.classList.toggle('playing', el.dataset.key === key && key !== null));
}
function seekAndPlay(a, pos) {
  const go = () => { try { a.currentTime = ((a.duration && pos > a.duration - 1) ? 0 : Math.min(pos, (a.duration || 1e9) - 0.05)); } catch (e) {} a.play(); };
  if (a.readyState >= 3) { go(); return; }
  let done = false;
  const fire = () => { if (done) return; done = true; go(); };
  a.addEventListener('canplay', fire, { once: true });
  setTimeout(fire, 1200);
}
function play(el, key, r) {
  if (!r.clip) return;
  if (curKey === key) { audio.pause(); markPlaying(null); curKey = null; return; }
  curKey = key; markPlaying(key);
  audio.pause();
  audio.src = r.clip;
  seekAndPlay(audio, 0);
  const promptBit = r.prompt === 'empty' ? '(EMPTY prompt — absorption test)' : r.prompt;
  document.getElementById(__INFO_ID__).innerHTML =
    `<b>${STAGE_LABEL[r.stage] || r.stage}</b> · cfg ${r.cfg} · prompt: ${promptBit}`;
}

let prompt = D.some(r => r.prompt === 'kimlong') ? 'kimlong' : D[0].prompt;
const byKey = {};
D.forEach(r => { byKey[r.stage + '|' + r.cfg + '|' + r.prompt] = r; });
const presentPrompts = [...new Set(D.map(r => r.prompt))];
const presentStages = STAGES.filter(s => D.some(r => r.stage === s));

function render() {
  wrap.innerHTML = '';
  const bar = document.createElement('div'); bar.className = 'aud-bar';
  presentPrompts.forEach(p => {
    const btn = document.createElement('button');
    btn.textContent = p === 'empty' ? 'empty prompt (absorption test)' : p;
    if (p === prompt) btn.classList.add('on');
    btn.onclick = () => { prompt = p; render(); };
    bar.appendChild(btn);
  });
  wrap.appendChild(bar);

  const table = document.createElement('table'); table.className = 'tc-table';
  const headRow = document.createElement('tr');
  headRow.appendChild(document.createElement('th'));
  CFGS.forEach(c => { const th = document.createElement('th'); th.textContent = 'cfg ' + c; headRow.appendChild(th); });
  table.appendChild(headRow);
  presentStages.forEach(stage => {
    const tr = document.createElement('tr');
    const stTd = document.createElement('td'); stTd.textContent = STAGE_LABEL[stage] || stage; tr.appendChild(stTd);
    CFGS.forEach(c => {
      const td = document.createElement('td');
      const key = stage + '|' + c + '|' + prompt;
      const r = byKey[key];
      if (r && r.clip) {
        const cell = document.createElement('span');
        cell.className = 'eg-cell'; cell.textContent = '▶'; cell.dataset.key = key;
        cell.onclick = () => play(cell, key, r);
        td.appendChild(cell);
      } else {
        td.textContent = '·'; td.className = 'tc-blank';
      }
      tr.appendChild(td);
    });
    table.appendChild(tr);
  });
  wrap.appendChild(table);
}
render();
})();
"""

def write_avp_cfg_sweep_folder(kind, name, label, purpose, date_str,
                                findings=None, status=None, known_pages=None):
    """Training-stage x cfg-value grid with a kimlong/empty-prompt toggle
    (see AVP_CFG_SWEEP_STEM_RE / AVP_CFG_SWEEP_STAGE_ORDER above)."""
    staged_dir = f"{OUT}/{kind}/{name}"
    records = []
    for f in sorted(os.listdir(staged_dir)) if os.path.isdir(staged_dir) else []:
        if not f.endswith(".m4a"):
            continue
        m = AVP_CFG_SWEEP_STEM_RE.match(f[:-4])
        if not m:
            continue
        records.append({
            "stage": m["stage"], "prompt": m["prompt"], "cfg": float(m["cfg"]), "clip": f,
        })
    if not records:
        return False

    stages = [s for s in AVP_CFG_SWEEP_STAGE_ORDER if any(r["stage"] == s for r in records)]
    stages += sorted({r["stage"] for r in records} - set(stages))
    cfgs = sorted({r["cfg"] for r in records})
    prompts = sorted({r["prompt"] for r in records})
    stage_label = {s: f"{s} — {AVP_CFG_SWEEP_STAGE_RECIPE.get(s, '')}" for s in stages}

    doc = head(f"{label} — evals", depth=2)
    doc += ('<p class="nav"><a href="../../index.html">← all evals</a>'
            '<a href="https://aavepyora.online/files/">the studio</a></p>')
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    doc += eval_grid.provenance_html(findings, status, known_pages)
    doc += (f'<p class="faint">{len(records)} clips, {len(stages)} checkpoints (a hand-picked '
            f'training-stage sequence, not an epoch ladder within one arm) x {len(cfgs)} cfg values · '
            'toggle the prompt, click a cell to play (shared playhead)</p>')
    doc += '<div class="prompt-legend"><b>Checkpoints (stage — recipe):</b><ul>' + "".join(
        f'<li><code>{html.escape(s)}</code>: {html.escape(stage_label[s].split(" — ", 1)[-1])}</li>'
        for s in stages
    ) + '</ul></div>'
    doc += _prompt_legend_html(prompts, {})
    doc += '<div class="eg-info" id="cfgsweep-info">click a cell for its readout</div>'
    doc += '<div id="cfgsweep-wrap"></div>'
    js = (AVP_CFG_SWEEP_JS_TEMPLATE
          .replace("__DATA__", json.dumps(records))
          .replace("__STAGES__", json.dumps(stages))
          .replace("__CFGS__", json.dumps(cfgs))
          .replace("__STAGE_LABEL__", json.dumps(stage_label))
          .replace("__WRAP_ID__", "'cfgsweep-wrap'")
          .replace("__INFO_ID__", "'cfgsweep-info'"))
    doc += f'<script>{js}</script>'
    doc += '<footer>aavepyora.online · evals · same-playhead · CFG x training-stage sweep</footer></div></body></html>'
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

def write_avp_master_folder(kind, name, label, purpose, date_str,
                             findings=None, status=None, known_pages=None):
    """ONE consolidated avp-investigation reference page (Kim's ask via
    CONTINUITY, 2026-07-09): every avp/goa-baseline render dir as a section
    on a single page, ONE shared playhead across all sections (unlike the
    per-dir pages, which each have their own). Clips are referenced via
    relative paths into the sibling staged dirs -- this page's own dir
    carries no clips of its own, so it must be invoked explicitly (it has
    nothing for main()'s clip-driven pass-1 scan to discover)."""
    staged_dir = f"{OUT}/{kind}/{name}"
    os.makedirs(staged_dir, exist_ok=True)
    sections = []

    board_dir = f"{OUT}/renders/avp_board"
    board_stem_re = re.compile(r"^epoch(?P<epoch>\d+)_step(?P<step>\d+)$")
    board_records = []
    for f in sorted(os.listdir(board_dir)) if os.path.isdir(board_dir) else []:
        if not f.endswith(".m4a"):
            continue
        parts = f[:-4].split("__")
        if len(parts) != 3:
            continue
        arm, ckpt_part, prompt = parts
        m = board_stem_re.match(ckpt_part)
        if not m:
            continue
        board_records.append({
            "arm": arm, "epoch": int(m["epoch"]), "step": int(m["step"]),
            "prompt": prompt, "clip": f"../avp_board/{f}",
        })
    if board_records:
        arms = [a for a in AVP_BOARD_ARMS if any(r["arm"] == a for r in board_records)]
        prompts = sorted({r["prompt"] for r in board_records})
        sections.append({
            "id": "sec-board", "kind": "grid",
            "title": "1. All avp DoRA arms — arm x epoch grid",
            "subtitle": f"{len(board_records)} clips, {len(arms)} arms x {len(prompts)} epochs x "
                        f"{len(prompts)} prompts — trigger-word prompts, pick one from the dropdown",
            "records": board_records, "arms": arms, "prompts": prompts, "params": AVP_BOARD_PARAMS,
            "own_page": known_pages.get("avp_board") if known_pages else None,
        })

    for dirname, sec_title, sec_blurb, params_key, sweet in [
        ("avp_board_seeds", "2. avp originals ladder — the main degradation story",
         "base (no adapter) + the full r16_originals epoch ladder x 7 prompts x 3 seeds. TWO "
         "candidate sweet-spot islands (gold rows, degradation_report_v2): ep31 is a narrow local "
         "CE/tempo-lock spike sitting on the shoulder of spectral ringing (usable window ~ep30-31 "
         "only); ep7-9 is a spectrally HEALTHIER second island (best point ep8) with comparable-or-"
         "higher CE and centroid in/near the healthy band rather than ringing. Sweet-spot step count "
         "(~900-1200 steps) is consistent across r16/r128 — an optimization-trajectory property, not "
         "a rank/epoch one. Epochs 24-34 also carry a dense fine/warm-restart re-render window.",
         "r16_originals", [8, 31]),
        ("avp_board_armG", "3. Arm G — r128 lower-LR (does lower LR move the knee?)",
         "Same r128/alpha45 recipe as avp_board's r128adj, at 10x lower LR (1e-4) + aug10. Tempo "
         "(W) AND spectral (C, centroid/ZCR) both confirm ARM G ESCAPES collapse across the whole "
         "3000-step run (0 DULL/0 RING throughout) — but it can still read \"soft\" by ear because "
         "PUNCH (transient clarity, AudioCommons depth/hardness) isn't captured by either meter; a "
         "dedicated punch meter (eval/dancefloor_punch.py) now feeds the ship-picker's third term.",
         "armG", None),
        ("avp_board_freeform", "4. Freeform-caption A/B",
         "Isolated A/B against the r16_originals ladder — same corpus, same recipe, ONLY the "
         "caption differs: one honest descriptive caption instead of the trigger word. RESULT: this "
         "did NOT rescue conditioning — freeform's across-prompt/across-seed ratio (0.22 @1.0 DoRA, "
         "0.12 @0.6) is LOWER than the trigger arm's (0.92), i.e. more collapsed, not less. Read "
         "together with the r64 tiered-caption result (section below): the lesson isn't \"the "
         "trigger token was the problem\" — it's that ANY single caption reused for every crop "
         "collapses conditioning, trigger or descriptive alike. Caption DIVERSITY is the cure.",
         "freeform", None),
        ("goa_everything_board", "5. GOA baseline — in-distribution control",
         "Same r128/dora-rows recipe family trained on the GOA catalogue itself (not the avp "
         "personal corpus) — the healthy-adapter reference the avp arms' degradation is measured "
         "against. Its own CE/tempo sweet spot lands ~9x later (step ~10689) than the avp-OOD arms "
         "(~900-1200) — sweet-spot step count is NOT corpus-invariant; the small avp-OOD corpus "
         "just needs far fewer steps before overfitting than in-distribution GOA training does.",
         "everything_r128", None),
    ]:
        d = f"{OUT}/renders/{dirname}"
        records = _parse_ladder_records(d, clip_prefix=f"../{dirname}/")
        if not records:
            continue
        prompt_text = {}
        meta_path = f"{d}/run_meta.json"
        if os.path.exists(meta_path):
            try:
                prompt_text = json.load(open(meta_path)).get("prompts", {})
            except Exception:
                pass
        prompt_keys = list(prompt_text) if prompt_text else sorted({r["prompt"] for r in records})
        prompt_text_merged = {**AVP_PROMPT_TEXT, **prompt_text}
        seeds = sorted({r["seed"] for r in records})
        strengths = sorted({r["strength"] for r in records if r["strength"] is not None})
        n_rows = len({(r["arm"], r["tag"]) for r in records})
        extra = f' x {len(strengths)} DoRA strengths' if len(strengths) > 1 else ''
        sections.append({
            "id": f"sec-{dirname}", "kind": "ladder", "title": sec_title, "blurb": sec_blurb,
            "subtitle": f"{len(records)} clips, {n_rows} checkpoints x {len(prompt_keys)} prompts x "
                        f"{len(seeds)} seeds{extra}",
            "records": records, "promptKeys": prompt_keys, "promptText": prompt_text_merged,
            "seeds": seeds, "strengths": strengths,
            "paramsLabel": AVP_BOARD_PARAMS.get(params_key, ""),
            "sweetEpochs": sweet if isinstance(sweet, list) else ([sweet] if sweet is not None else []),
            "own_page": known_pages.get(dirname) if known_pages else None,
        })

    if not sections:
        return False

    doc = head(f"{label} — evals", depth=2)
    doc += ('<p class="nav"><a href="../../index.html">← all evals</a>'
            '<a href="https://aavepyora.online/files/">the studio</a></p>')
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    doc += eval_grid.provenance_html(findings, status, known_pages)
    doc += '<p class="faint"><b>Jump to:</b> ' + ' · '.join(
        f'<a href="#{s["id"]}">{html.escape(s["title"])}</a>' for s in sections) + '</p>'
    doc += '<div class="eg-info" id="master-info">click a cell for its readout — shared playhead across every section below</div>'
    for s in sections:
        doc += f'<h2 id="{s["id"]}">{html.escape(s["title"])}</h2>'
        if s.get("blurb"):
            doc += f'<p class="faint">{html.escape(s["blurb"])}</p>'
        doc += f'<p class="faint">{html.escape(s["subtitle"])}'
        if s.get("own_page"):
            doc += f' · <a href="{s["own_page"]}">its own page</a>'
        doc += '</p>'
        if s["kind"] == "grid":
            doc += '<div class="prompt-legend"><b>Arms (recipe):</b><ul>' + "".join(
                f'<li><code>{html.escape(a)}</code>: {html.escape(s["params"].get(a, ""))}</li>'
                for a in s["arms"]
            ) + '</ul></div>'
            doc += _prompt_legend_html(s["prompts"], {})
        else:
            doc += _recipe_line_html("", s["paramsLabel"])
            doc += _prompt_legend_html(s["promptKeys"], s["promptText"])
        doc += f'<div id="{s["id"]}-wrap"></div>'
    js_sections = []
    for s in sections:
        entry = {k: v for k, v in s.items() if k not in ("title", "blurb", "subtitle", "own_page")}
        js_sections.append(entry)
    js = AVP_MASTER_JS_TEMPLATE.replace("__SECTIONS__", json.dumps(js_sections))
    doc += f'<script>{js}</script>'
    doc += '<footer>aavepyora.online · evals · same-playhead across every section · avp master reference</footer></div></body></html>'
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

def write_style_compare_folder(kind, name, label, purpose, date_str, source_dir,
                                findings=None, status=None, known_pages=None):
    """Dual-pane arm compare with plain-vs-styled columns side by side
    (pq_scores.json rows carrying `prompt_key`/`style`). See eval_grid.py's
    load_promptstyle_data()/render_style_compare_page()."""
    staged_dir = f"{OUT}/{kind}/{name}"
    staged_stems = {os.path.relpath(os.path.splitext(f)[0], staged_dir)
                    for f in glob.glob(f"{staged_dir}/**/*.m4a", recursive=True)}

    def clip_lookup(stem):
        return f"{stem}.m4a" if stem in staged_stems else None

    records = eval_grid.load_promptstyle_data(source_dir, clip_lookup, extra_stems=staged_stems)
    if not records:
        return False

    head_html = head(f"{label} — evals", depth=2)
    head_html += ('<p class="nav"><a href="../../index.html">← all evals</a>'
                  '<a href="https://aavepyora.online/files/">the studio</a></p>')
    footer_html = '<footer>aavepyora.online · evals · same-playhead · plain-vs-styled arm compare</footer></div></body></html>'
    doc = eval_grid.render_style_compare_page(
        head_html=head_html, title=label, label=label,
        purpose=redact(purpose), date_str=date_str, records=records, footer_html=footer_html,
        findings=findings, status=status, known_pages=known_pages,
    )
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

def write_density_control_folder(kind, name, label, purpose, date_str, source_dir,
                                  findings=None, status=None, known_pages=None):
    """Density-control grid (arm x prompt x style x seed x condition x density
    -- see eval/density_control_eval.py). Routed here once the source dir
    carries the _onset_measurements.json sidecar
    (eval/measure_density_control_onsets.py's librosa onset-density pass, the
    control-authority readout column Kim asked for)."""
    meas_path = f"{source_dir}/_onset_measurements.json"
    if not os.path.exists(meas_path):
        return False
    try:
        measurements = json.load(open(meas_path))
    except Exception:
        return False
    if not measurements:
        return False

    # This grid's own run_meta.json doesn't carry prompt text (only the
    # uncontrolled newcap8_promptstyle grid it's built on top of does) -- same
    # aggr/hypno/psy prompt-key convention, so reuse rather than duplicate.
    prompt_text = {}
    sibling = find_renders_source_dir("newcap8_promptstyle")
    if sibling and os.path.exists(f"{sibling}/run_meta.json"):
        try:
            prompt_text = json.load(open(f"{sibling}/run_meta.json")).get("prompts", {})
        except Exception:
            pass

    staged_dir = f"{OUT}/{kind}/{name}"
    staged_stems = {os.path.relpath(os.path.splitext(f)[0], staged_dir)
                    for f in glob.glob(f"{staged_dir}/**/*.m4a", recursive=True)}

    def clip_lookup(stem):
        return f"{stem}.m4a" if stem in staged_stems else None

    records = eval_grid.load_density_control_data(measurements, prompt_text, clip_lookup)
    if not records:
        return False

    head_html = head(f"{label} — evals", depth=2)
    head_html += ('<p class="nav"><a href="../../index.html">← all evals</a>'
                  '<a href="https://aavepyora.online/files/">the studio</a></p>')
    footer_html = '<footer>aavepyora.online · evals · same-playhead · density-control grid</footer></div></body></html>'
    doc = eval_grid.render_density_control_page(
        head_html=head_html, title=label, label=label,
        purpose=redact(purpose), date_str=date_str, records=records, footer_html=footer_html,
        findings=findings, status=status, known_pages=known_pages,
    )
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

def write_transitions_folder(kind, name, label, purpose, date_str, clips, source_dir,
                              findings=None, status=None, known_pages=None):
    """Arm x transition-method compare (see eval/transition_lab.py): three
    construction methods (model-native inpaint bridge / beatmatch+audio
    crossfade / sine-masked graded SDEdit) per arm. Filename convention:
    {arm}__v{n}_{method}.wav, or with a length dimension (r2):
    {arm}__{length}f_v{n}_{method}.wav — grouped by length FIRST (Kim's r2
    hypothesis under test: does a shorter total length fix a weak-kick/noisy
    character), then arm, one table per length. Jump-to-transition uses the
    exact window_frames/total_frames RATIO from run_meta.json (the transition
    sits at the same fractional position regardless of total length, so the
    per-length window is frac * that length's own frame count -- not the
    literal frame numbers, which only apply to the documented length)."""
    stem_re = re.compile(r"^(?P<arm>.+)__(?:(?P<length>\d+)f_)?v(?P<vn>\d+)_(?P<method>\w+)$")
    by_length = {}  # length (int frames, or None) -> {arm: {mk: clip}}
    methods = []  # preserve v1/v2/v3 order
    for c in clips:
        stem = re.sub(r"\.m4a$", "", c)
        m = stem_re.match(stem)
        if not m:
            continue
        length = int(m["length"]) if m["length"] else None
        mk = f"v{m['vn']}_{m['method']}"
        if mk not in methods:
            methods.append(mk)
        by_length.setdefault(length, {}).setdefault(m["arm"], {})[mk] = c
    if not by_length:
        return False
    methods.sort()

    frac_start, frac_end = 0.375, 0.625  # LONGFORM_XFADE's own 37.5%-62.5% ratio, as a fallback
    method_desc = {}
    meta_path = f"{source_dir}/run_meta.json" if source_dir else None
    if meta_path and os.path.exists(meta_path):
        try:
            meta = json.load(open(meta_path))
            wf = meta.get("gen", {}).get("window_frames")
            tf = meta.get("gen", {}).get("total_frames")
            if wf and tf:
                frac_start, frac_end = wf[0] / tf, wf[1] / tf
            # purpose string documents each vN in order, "/"-separated
            for part in redact(meta.get("purpose", "")).split("/"):
                mm = re.search(r"\bv(\d+)\s+(.*)", part.strip())
                if mm:
                    method_desc[f"v{mm.group(1)}"] = mm.group(2).strip()
        except Exception:
            pass

    def window_for(length):
        frames = length if length is not None else 2048  # LONGFORM_XFADE's original assumption
        return frac_start * frames / _LF_HZ, (frac_end - frac_start) * frames / _LF_HZ

    staged_dir = f"{OUT}/{kind}/{name}"
    doc = head(f"{label} — evals", depth=2)
    doc += ('<p class="nav"><a href="../../index.html">← all evals</a>'
            '<a href="https://aavepyora.online/files/">the studio</a></p>')
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    doc += eval_grid.provenance_html(findings, status, known_pages)
    n_arms = max(len(by_arm) for by_arm in by_length.values())
    doc += (f'<p class="faint">{len(clips)} clips, {len(by_length)} length(s) x {n_arms} arms x '
            f'{len(methods)} transition methods · click ▶ for the full clip, or ⇥ to jump straight '
            'to the transition window</p>')
    for length in sorted(by_length, key=lambda l: (l is None, l)):
        by_arm = by_length[length]
        xfade_start, xfade_len = window_for(length)
        if length is not None:
            dur = length / _LF_HZ
            doc += (f'<h2><span class="mark">§</span> {length}-frame ({dur:.0f}s) '
                    f'<span class="faint">— transition ≈{xfade_start:.0f}s–{xfade_start+xfade_len:.0f}s in</span></h2>')
        doc += '<table class="tc-table"><tr><th>arm</th>'
        for mk in methods:
            vn, _, rest = mk.partition("_")
            head_lbl = method_desc.get(vn, rest.replace("_", " "))
            doc += f'<th title="{html.escape(head_lbl)}">▶ {html.escape(vn)}</th><th>⇥</th>'
        doc += '</tr>'
        for arm in sorted(by_arm):
            row = by_arm[arm]
            doc += f'<tr><td>{html.escape(arm)}</td>'
            for mk in methods:
                c = row.get(mk)
                if c:
                    lbl = f"{arm} · {mk}" + (f" · {length}f" if length is not None else "")
                    wf_attrs = f'data-wfstart="{xfade_start:.1f}" data-wfend="{xfade_start+xfade_len:.1f}"'
                    doc += (f'<td class="tc-play" data-src="{html.escape(c)}" data-label="{html.escape(lbl)}" '
                            f'{wf_attrs} data-seek="0" onclick="lfPlay(this)">▶</td>'
                            f'<td class="tc-play" data-src="{html.escape(c)}" data-label="{html.escape(lbl)} (transition)" '
                            f'{wf_attrs} data-seek="{xfade_start:.1f}" onclick="lfPlay(this)">⇥</td>')
                else:
                    doc += '<td class="tc-blank">·</td><td class="tc-blank">·</td>'
            doc += '</tr>'
        doc += '</table>'
    if method_desc:
        doc += '<p class="faint">' + ' · '.join(f'<b>{html.escape(vn)}</b>: {html.escape(d)}'
                                                   for vn, d in sorted(method_desc.items())) + '</p>'
    doc += """<audio id="lfpl"></audio><script>
let cur=null,ph=0;const a=document.getElementById('lfpl');
a.addEventListener('timeupdate',()=>{if(!a.paused)ph=a.currentTime});
a.addEventListener('ended',()=>{if(cur){cur.classList.remove('playing');cur=null}});
function seekAndPlay(pos){
 const go=()=>{try{a.currentTime=((a.duration&&pos>a.duration-1)?0:Math.min(pos,(a.duration||1e9)-0.05))}catch(e){}a.play()};
 if(a.readyState>=3){go();return}
 let done=false;const fire=()=>{if(done)return;done=true;go()};
 a.addEventListener('canplay',fire,{once:true});setTimeout(fire,1200)}
function lfPlay(el){const s=el.dataset.src,seek=parseFloat(el.dataset.seek)||0;
 if(cur===el){a.pause();el.classList.remove('playing');cur=null;return}
 if(cur)cur.classList.remove('playing');
 a.pause();a.src=s;seekAndPlay(seek);
 cur=el;el.classList.add('playing')}
</script>"""
    doc += '<footer>aavepyora.online · evals · same-playhead · transition-method compare</footer></div></body></html>'
    os.makedirs(staged_dir, exist_ok=True)
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

def write_longform_folder(kind, name, label, purpose, date_str, clips,
                           findings=None, status=None, known_pages=None):
    """Arm x seed-order compare for longform slerp-crossfade renders (see
    stable_audio_3/inference/longform.py's CrossfadeStitcher). Filename
    convention: {arm}__{prompt}_xfade_s{seedA}to{seedB}.m4a -- one row per arm,
    two play buttons (seed-order A/B), plus a jump-to-crossfade shortcut since
    the crossfade region (not the whole clip) is the interesting bit."""
    stem_re = re.compile(r"^(?P<arm>.+)__(?P<prompt>\w+)_xfade_s(?P<sa>\d+)to(?P<sb>\d+)$")
    by_arm = {}
    for c in clips:
        stem = re.sub(r"\.m4a$", "", c)
        m = stem_re.match(stem)
        if not m:
            continue
        by_arm.setdefault(m["arm"], {})[f"{m['sa']}to{m['sb']}"] = c
    if not by_arm:
        return False

    staged_dir = f"{OUT}/{kind}/{name}"
    doc = head(f"{label} — evals", depth=2)
    doc += ('<p class="nav"><a href="../../index.html">← all evals</a>'
            '<a href="https://aavepyora.online/files/">the studio</a></p>')
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    doc += eval_grid.provenance_html(findings, status, known_pages)
    doc += (f'<p class="faint">{len(clips)} clips, {len(by_arm)} arms x 2 seed-orders each · '
            'click ▶ for the full clip, or the crossfade shortcut to jump straight to the '
            'slerp region -- that\'s the interesting bit here, not the steady-state ends</p>')
    doc += '<table class="tc-table"><tr><th>arm</th><th>▶ s1234→4242</th><th>▶ jump</th>'
    doc += '<th>▶ s4242→1234</th><th>▶ jump</th></tr>'
    for arm in sorted(by_arm):
        row = by_arm[arm]
        doc += f'<tr><td>{html.escape(arm)}</td>'
        for key in ("1234to4242", "4242to1234"):
            c = row.get(key)
            if c:
                lbl = f"{arm} · {key}"
                wf_attrs = (f'data-wfstart="{LONGFORM_XFADE_START:.1f}" '
                            f'data-wfend="{LONGFORM_XFADE_START+LONGFORM_XFADE_LEN:.1f}"')
                doc += (f'<td class="tc-play" data-src="{html.escape(c)}" data-label="{html.escape(lbl)}" '
                        f'{wf_attrs} data-seek="0" onclick="lfPlay(this)">▶</td>'
                        f'<td class="tc-play" data-src="{html.escape(c)}" data-label="{html.escape(lbl)} (crossfade)" '
                        f'{wf_attrs} data-seek="{LONGFORM_XFADE_START:.1f}" onclick="lfPlay(this)">⇥</td>')
            else:
                doc += '<td class="tc-blank">·</td><td class="tc-blank">·</td>'
        doc += '</tr>'
    doc += '</table>'
    doc += ('<p class="faint">crossfade window (2048-frame / 3:10 renders, 512-frame slerp, '
            f'~10.767 Hz SA3 grid): ≈{LONGFORM_XFADE_START:.0f}s–{LONGFORM_XFADE_START+LONGFORM_XFADE_LEN:.0f}s '
            'into the clip, mid-render (approximate -- derived from frame counts, not a per-clip timestamp)</p>')
    doc += """<audio id="lfpl"></audio><script>
let cur=null,ph=0;const a=document.getElementById('lfpl');
a.addEventListener('timeupdate',()=>{if(!a.paused)ph=a.currentTime});
a.addEventListener('ended',()=>{if(cur){cur.classList.remove('playing');cur=null}});
function seekAndPlay(pos){
 const go=()=>{try{a.currentTime=((a.duration&&pos>a.duration-1)?0:Math.min(pos,(a.duration||1e9)-0.05))}catch(e){}a.play()};
 if(a.readyState>=3){go();return}
 let done=false;const fire=()=>{if(done)return;done=true;go()};
 a.addEventListener('canplay',fire,{once:true});setTimeout(fire,1200)}
function lfPlay(el){const s=el.dataset.src,seek=parseFloat(el.dataset.seek)||0;
 if(cur===el){a.pause();el.classList.remove('playing');cur=null;return}
 if(cur)cur.classList.remove('playing');
 a.pause();a.src=s;seekAndPlay(seek);
 cur=el;el.classList.add('playing')}
</script>"""
    doc += '<footer>aavepyora.online · evals · same-playhead · longform crossfade compare</footer></div></body></html>'
    os.makedirs(staged_dir, exist_ok=True)
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
    member_dates = {}  # checkpoint name -> mtime, for the date-fallback dropdown order (spec §15)
    member_audited = {}  # checkpoint name -> has kim_feedback (manifest v2, spec §16)
    for member in member_names:
        source_dir = find_source_dir(member)
        if not source_dir or not os.path.exists(f"{source_dir}/onset_eval.json"):
            continue
        try:
            member_dates[member] = os.path.getmtime(f"{source_dir}/onset_eval.json")
        except OSError:
            pass
        member_audited[member] = has_kim_feedback(kind, member)
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

    head_html = head(f"{label} — evals", depth=2)
    head_html += ('<p class="nav"><a href="../../index.html">← all evals</a>'
                  '<a href="https://aavepyora.online/files/">the studio</a></p>')
    footer_html = '<footer>aavepyora.online · evals · same-playhead · multi-checkpoint audit</footer></div></body></html>'
    doc = eval_grid.render_checkpoint_audit_page(
        head_html=head_html, title=label, label=label,
        purpose=redact(purpose), date_str=date_str, records=all_records, footer_html=footer_html,
        checkpoint_dates=member_dates, checkpoint_audited=member_audited,
    )
    open(f"{staged_dir}/index.html", "w").write(doc)
    return True

# Kim, 2026-07-07: "composed_sweep has NO eval page" -- these 4 stages of one
# sweep (control-DiT adapter, +/- LatCH) were each surfacing as their own
# generically-labeled landing entry (e.g. "Stage 1 cell E re-render..."),
# nothing said "composed sweep" so it was unfindable by name. Unlike the
# unrelated-experiments audit above, these ARE directly comparable -- gets the
# full grid heatmap+corr treatment via a dropdown, per Kim's explicit ask.
COMPOSED_SWEEP_MEMBERS = ["A_cc", "A_cc_v2", "E_fusion", "E_fusion_v2"]
# CONTINUITY, 2026-07-07: full-track a2a noise ladders, one dir per (track,
# adapter) pair -- "one row per nl, N adapter columns, same-playhead". Pattern-
# matched rather than a hardcoded list (2026-07-07, after a2a_angelic_evr1x/
# a2a_vapausvoima_evr1x landed as a "page gap" -- new tracks keep arriving,
# and a hardcoded per-track list means re-discovering this every time).
A2A_LADDER_RE = re.compile(r"^a2a_(?P<track>.+?)_(?P<adapter>[^_]+)$")

def write_composed_sweep_folder(kind, name, label, purpose, date_str, member_names,
                                 findings=None, status=None, known_pages=None):
    """Dropdown-browsable composed_sweep compare -- same member-gathering as
    write_checkpoint_audit_folder, but rendered with the full grid heatmap/table
    view (eval_grid.render_composed_sweep_page) since these stages are directly
    comparable, not independent unrelated experiments."""
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

    head_html = head(f"{label} — evals", depth=2)
    head_html += ('<p class="nav"><a href="../../index.html">← all evals</a>'
                  '<a href="https://aavepyora.online/files/">the studio</a></p>')
    footer_html = '<footer>aavepyora.online · evals · same-playhead · composed control sweep</footer></div></body></html>'
    doc = eval_grid.render_composed_sweep_page(
        head_html=head_html, title=label, label=label,
        purpose=redact(purpose), date_str=date_str, records=all_records, footer_html=footer_html,
        findings=findings, status=status, known_pages=known_pages,
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
    doc = head(f"{label} — evals", depth=2)
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

def write_folder(kind, name, label, purpose, clips, date_str="", verdict=None,
                  findings=None, status=None, known_pages=None):
    doc = head(f"{label} — evals", depth=2)
    doc += ('<p class="nav"><a href="../../index.html">← all evals</a>'
            '<a href="https://aavepyora.online/files/">the studio</a></p>')
    doc += f'<h1>{html.escape(label)}</h1>'
    if date_str:
        doc += f'<p class="faint">{html.escape(date_str)}</p>'
    if purpose:
        doc += f'<p class="lede">{html.escape(purpose)}</p>'
    doc += eval_grid.provenance_html(findings, status, known_pages)
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

# Kim (2026-07-10, via CONTINUITY design, routed to this file since it's actively
# edited here): the flat "All runs" list reads as "a wall of links" -- classify by
# category (curated on top, then by kind) instead of one undifferentiated list.
# Order matters: first matching category wins, so more-specific patterns (rarity,
# LatCH) are checked before the broad "control / FiLM" catch-all.
# Taglines: eval-tables spec §14 (Kim, same session) -- every landing category
# needs a plain-language one-liner (the "learning resource" audience, not just
# the eval-tool/technical-resource ones the per-page prompt legends already serve).
LANDING_CATEGORIES = [
    ("DoRA / avp", re.compile(r"^(avp_|renders_dora|renders_soups|soup|goa_everything)"),
     "Fine-tuning SA3 on a personal/style corpus (DoRA adapters) — rank/LR/caption "
     "sweeps, checkpoint ladders, model-soup averaging."),
    # memo_ckpt_a2a_test is deliberately NOT prefixed "a2a_" (that would collide
    # with A2A_LADDER_RE's sibling-folder auto-grouping, a different mechanism --
    # see RENDERS_SOURCE_ALIASES) -- "_a2a_" substring catches it here too.
    ("a2a & transitions", re.compile(r"(^a2a_|_a2a_|^breathing_|^promptarc_|^dual_lora_|^transitions)"),
     "Audio-to-audio: re-rendering an existing track through the model at varying "
     "noise levels, and stitching/crossfading between generated sections."),
    ("LatCH", re.compile(r"(^latch|_latch)"),
     "Latent-Controlled Heads — small trained probes that steer a specific attribute "
     "(bass energy, onset density, chroma...) during generation, tested for whether "
     "they actually move the output the way they're asked."),
    ("rarity", re.compile(r"^rarity"),
     "How unusual/distinctive a generation is relative to a reference corpus — does "
     "an adapter produce genuinely novel content, or just restyle the same average?"),
    ("long-form", re.compile(r"^longform"),
     "Generating audio well past the model's native window — sliding-window "
     "continuation, drift checks, seam quality."),
    ("mechanism / interpretability", re.compile(r"^(layer_map|hardness|concept_steer)"),
     "How the model works inside, and using that map to steer it: causal layer "
     "maps (which DiT blocks carry each attribute), training-free concept steering, "
     "and the timbral-attribute bracket sweeps."),
    ("control / FiLM", re.compile(
        r"^(onset_eval|gain_knee|opb|fusion|es_conditioner|collapse|disentangle|"
        r"flow.*sep|zerosep|renders_cross|targeted)"),
     "Conditioning adapters that steer a scalar control (onset density, gain) "
     "independent of the text prompt — authority, disentanglement from tempo/genre, "
     "and failure-mode sweeps."),
]


def categorize_eval(name):
    for label, pattern, _tagline in LANDING_CATEGORIES:
        if pattern.search(name):
            return label
    return "other"


# Kim, 2026-07-12 (eval-tables spec §15): "_onset_control_audit"/"_misc_uncurated_runs"
# collect dozens of runs each -- they were landing at the BOTTOM of their category
# (empty date_str sorts last) despite outranking any single run's page. Any future
# "collects many runs" aggregation page gets added here too.
AGGREGATION_PAGE_NAMES = {"_onset_control_audit", "_misc_uncurated_runs"}


def build_landing(control, renders):
    doc = head("Evals — Vibe on The Edg3", depth=0)
    doc += ('<p class="nav"><a href="https://aavepyora.online/files/">← the studio</a>'
            '<a href="https://aavepyora.online/files/AGENT_DIALOGUE.html">dialogue</a></p>')
    doc += ('<h1>Evals</h1><p class="lede">Listening results — what the control heads, adapters, and '
            'renders actually sound like. Each folder is a same-playhead player, not a dump.</p>')
    doc += ('<p class="faint">Bookmark this page: '
            '<a href="https://aavepyora.online/files/evals/">aavepyora.online/files/evals/</a> — '
            'the canonical, always-current entry point for the listening review.</p>')
    # Kim, 2026-07-11: the big cross-model matrix (the "giant table") had no entry
    # point on the landing -- he couldn't find it. Hero it at the very top, above
    # the models index, since it's the current headline build.
    doc += ('<div style="border:2px solid #0f9e99;background:#0d2422;padding:15px 20px;'
            'margin:16px 0;border-radius:7px">'
            '<a href="model_matrix.html" style="font-size:19px;color:#4fe3dd;'
            'text-decoration:none;font-weight:700">&#127899; Model Matrix — the big '
            'cross-model listening table &rarr;</a>'
            '<div style="color:#a9cfcc;font-size:12.5px;margin-top:6px;line-height:1.5">'
            'Every trained model in one place: pick the <b>model</b> (column dropdown) and '
            '<b>checkpoint</b> (row dropdown), sweep <b>CFG &times; adapter-strength</b>, '
            'same-playhead A/B. Checkpoints with rarity renders done are lit up. '
            '<i>In active build &mdash; rendering across all models now.</i></div></div>')
    doc += ('<p class="dim">📇 <a href="models.html"><b>Models index</b></a> — every trained '
            'model and which tests exercised it (the awareness page; barely-tested flagged).</p>')
    doc += ('<p class="dim">📊 <a href="stats.html"><b>Statistics</b></a> — the whole zoo measured '
            '(31k clips × 14 metrics): rank 128 vs 16, the training-length sweet spot, CE/PQ leaderboard.</p>')
    # Kim, 2026-07-12: "I have great trouble finding the new evals" — the categorized
    # list buries recent work in "other". A hand-curated "Recently added" strip at the
    # top surfaces the newest important pages directly (maintain this list as work lands).
    _highlights = [
        ("renders/layer_map_2026-07-10/index.html", "Layer map + steering payoff",
         "Which DiT blocks causally carry each attribute — and training-free concept "
         "steering at those blocks (three-way convergence + the α-ladder A/B)."),
        ("riffer/breathing.html", "a2a transitions — the collection",
         "Every audio-to-audio transition variant: breathing-noise controller, "
         "prompt-arc noise ladders, per-layer interleave."),
    ]
    doc += ('<div style="border:1px solid #2a4a48;background:#0c1c1b;padding:12px 18px;'
            'margin:14px 0;border-radius:7px">'
            '<div style="color:#7ed;font-size:11px;letter-spacing:.1em;text-transform:uppercase;'
            'margin-bottom:6px">Recently added</div>')
    for _href, _t, _d in _highlights:
        doc += (f'<div style="margin:6px 0"><a href="{_href}" style="color:#4fe3dd;font-weight:600;'
                f'text-decoration:none">{html.escape(_t)} &rarr;</a>'
                f'<div style="color:#9ab;font-size:12px;line-height:1.45">{html.escape(_d)}</div></div>')
    doc += '</div>'
    doc += '<h2><span class="mark">§</span> Curated players</h2>'
    doc += ('<p class="dim">The measured, annotated grids — same-playhead, with per-run info boxes:</p>')
    _riffer_labels = {"onset_eval.html": "onset control-authority", "disentangle.html": "disentanglement",
                       "dora_results.html": "DoRA auditions", "chroma_steer.html": "chroma steer",
                       "gain_knee.html": "gain knee", "mp.html": "multiprompt", "traj.html": "trajectories",
                       "latch_sweep.html": "LatCH head sweep", "breathing.html": "breathing-noise controller", "rarity.html": "rarity columns board"}
    _riffer = [(f"riffer/{f}", _riffer_labels[f]) for f in RIFFER_HTML]
    for _href, _lbl in _riffer:
        doc += f'<div class="run"><div class="name"><a href="{_href}">{_lbl}</a></div></div>'

    # Kim, 2026-07-07: "the front page does not make it easy to find runs simply
    # in order of creation" -- fixed then with one flat chronological list. Kim,
    # 2026-07-10 (via CONTINUITY design): that flat list grew into "a wall of
    # links" as the count climbed -- classify into categories instead (curated
    # stays on top, above), newest-first WITHIN each category. Replaces the old
    # flat "All runs" list AND the separate Control-runs/Renders kind-split below
    # (both were just cruder groupings of the same items -- three overlapping
    # listings of 56 things was the opposite of "easy to find").
    all_items = ([("control_runs", it) for it in control] + [("renders", it) for it in renders])
    by_category = {}
    for kind, item in all_items:
        by_category.setdefault(categorize_eval(item[0]), []).append((kind, item))
    category_order = [c for c, _p, _t in LANDING_CATEGORIES] + ["other"]
    category_tagline = {c: t for c, _p, t in LANDING_CATEGORIES}
    for cat in category_order:
        items = by_category.get(cat)
        if not items:
            continue
        items.sort(key=lambda ki: ki[1][4], reverse=True)
        # aggregation pages float to the top of their section (spec §15) -- stable
        # sort, so date-descending order is preserved within each of the two groups.
        items.sort(key=lambda ki: ki[1][0] not in AGGREGATION_PAGE_NAMES)
        doc += f'<h2><span class="mark">§</span> {html.escape(cat)} <span class="faint">({len(items)})</span></h2>'
        if category_tagline.get(cat):
            doc += f'<p class="dim">{html.escape(category_tagline[cat])}</p>'
        for kind, (name, label, purpose, n, date_str, subtitle, verdict) in items:
            mark = "" if has_kim_feedback(kind, name) else f" {UNAUDITED_MARK}"
            doc += (f'<div class="run"><div class="name"><a href="{kind}/{html.escape(name)}/index.html">'
                    f'{html.escape(label)}</a>{mark} <span class="faint">({kind.replace("_"," ")})</span></div>')
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
    open(f"{OUT}/evals.css","w").write(CSS + eval_grid.GRID_CSS + eval_grid.TABLE_CSS + eval_grid.STYLE_CSS
                                        + eval_grid.AUDIT_CSS + eval_grid.PROVENANCE_CSS + WAVEFORM_CSS)
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
    # name -> relative href, for provenance_html()'s "superseded by X" auto-link
    # (every per-folder page lives at kind/name/index.html, so from any other
    # kind/name/index.html the relative path is always ../../kind/name/).
    known_pages = {name: f"../../{kind}/{name}/index.html" for kind, name, _, _ in gathered}
    for fname in RIFFER_HTML:
        known_pages[fname[:-5]] = f"../../riffer/{fname}"
    # pass 1.5: split off uncurated control_runs entries for aggregation (Kim,
    # 2026-07-07: dozens of individually-linked "onset control N" links is
    # "messy AF" -- fold every uncurated control_runs folder into exactly two
    # pages instead: a rich multi-checkpoint audit for the real gain x density
    # grids, and a simple bundle for the structurally-different leftovers).
    # A folder only gets pulled into aggregation if desc_for() found NOTHING
    # for it -- anything with a real curated purpose keeps its own page/link.
    normal, audit_members, misc_members, composed_members = [], [], [], []
    a2a_groups = {}  # track -> [a2a_<track>_<adapter> member names]
    for kind, name, purpose, clips in gathered:
        # composed_sweep members are diverted regardless of purpose (unlike
        # audit/misc below) -- they already have real curated purposes from
        # their own run_meta.json, but Kim wants them under ONE findable
        # "composed sweep" page rather than scattered generic landing links.
        if kind == "control_runs" and name in COMPOSED_SWEEP_MEMBERS:
            composed_members.append(name)
            continue
        # same idea for a2a noise ladders -- one combined row=nl x col=adapter
        # page PER TRACK, not one landing link per (track, adapter) dir.
        a2a_m = kind == "renders" and A2A_LADDER_RE.match(name)
        if a2a_m:
            a2a_groups.setdefault(a2a_m["track"], []).append(name)
            continue
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
        explicit_title = title_for(name, kind)
        if explicit_title:
            label = explicit_title
        elif purpose:
            label = purpose if len(purpose) <= 60 else purpose[:57].rstrip() + "…"
        else:
            counters[cat] = counters.get(cat, 0) + 1
            label = f"{cat} {counters[cat]}"
        desc = purpose if purpose and purpose != label else ""
        date_str, subtitle, verdict = enrich(kind, name, desc, cat)
        if subtitle == label:   # don't repeat the title verbatim as its own subtitle
            subtitle = ""
        findings, status = findings_status_for(name)
        source_dir = find_source_dir(name) if kind == "control_runs" else find_renders_source_dir(name)
        is_grid = source_dir and os.path.exists(f"{source_dir}/onset_eval.json")
        wrote_grid = is_grid and write_grid_folder(kind, name, label, desc or subtitle, date_str, source_dir,
                                                    findings, status, known_pages)
        # table+compare (DoRA auditions, checkpoint x prompt x seed) — tried when the
        # dir isn't a gain/density grid; falls through to the flat player if the source
        # has no checkpoint-tagged pq_scores.json (not every renders/ dir is a DoRA audition).
        wrote_table = (not wrote_grid) and source_dir and write_table_folder(
            kind, name, label, desc or subtitle, date_str, source_dir, findings, status, known_pages)
        # style-compare (plain-vs-styled prompt A/B, pq_scores.json rows with prompt_key/style)
        wrote_style = (not wrote_grid) and (not wrote_table) and source_dir and write_style_compare_folder(
            kind, name, label, desc or subtitle, date_str, source_dir, findings, status, known_pages)
        # density-control grid (arm x prompt x style x seed x condition x density,
        # see eval/density_control_eval.py) -- tried once a source dir carries the
        # _onset_measurements.json sidecar from measure_density_control_onsets.py.
        wrote_density = (not wrote_grid) and (not wrote_table) and (not wrote_style) and source_dir and \
            write_density_control_folder(kind, name, label, desc or subtitle, date_str, source_dir,
                                          findings, status, known_pages)
        # longform slerp-crossfade compare (arm x seed-order, see longform.py's
        # CrossfadeStitcher) -- tried for dirs named *_longform with clip stems
        # matching the xfade convention.
        wrote_longform = (not wrote_grid) and (not wrote_table) and (not wrote_style) and (not wrote_density) and \
            name.endswith("_longform") and write_longform_folder(
                kind, name, label, desc or subtitle, date_str, clips, findings, status, known_pages)
        # transition-method compare (arm x {v1,v2,v3}, see eval/transition_lab.py)
        wrote_transitions = (not wrote_grid) and (not wrote_table) and (not wrote_style) and \
            (not wrote_density) and (not wrote_longform) and write_transitions_folder(
                kind, name, label, desc or subtitle, date_str, clips, source_dir, findings, status, known_pages)
        # unscored epoch-progression compare (checkpoint sweep vs a pinned
        # reference, no pq_scores.json yet -- see write_epoch_progress_folder)
        wrote_epoch = (not wrote_grid) and (not wrote_table) and (not wrote_style) and \
            (not wrote_density) and (not wrote_longform) and (not wrote_transitions) and source_dir and \
            write_epoch_progress_folder(kind, name, label, desc or subtitle, date_str, source_dir,
                                         findings, status, known_pages)
        # transitions3 seam-sweep compare (pair x window x seam-size x
        # chroma/plain, see write_transitions3_folder -- merged from 3
        # sibling Mantu dirs into one staged folder). Tried BEFORE
        # write_chroma_morph_folder: its regex (seam optional) is a strict
        # SUPERSET of chroma_morph's (no-seam-only) -- chroma_morph would
        # otherwise partially match just the no-seam subset of a transitions3
        # folder and claim it with only 12 of 48 clips, silently dropping the
        # rest (caught 2026-07-07 building transitions3 itself).
        wrote_t3 = (not wrote_grid) and (not wrote_table) and (not wrote_style) and \
            (not wrote_density) and (not wrote_longform) and (not wrote_transitions) and (not wrote_epoch) and \
            write_transitions3_folder(kind, name, label, desc or subtitle, date_str, clips,
                                       findings, status, known_pages)
        # chroma-morph real-track transition compare (pair x window x nl x
        # chroma/plain, see write_chroma_morph_folder)
        wrote_chroma = (not wrote_grid) and (not wrote_table) and (not wrote_style) and \
            (not wrote_density) and (not wrote_longform) and (not wrote_transitions) and (not wrote_epoch) and \
            (not wrote_t3) and write_chroma_morph_folder(kind, name, label, desc or subtitle, date_str, clips,
                                                           source_dir, findings, status, known_pages)
        # PURE chroma transitions (pair x window x chroma/plain, no nl axis --
        # see write_chroma_pure_folder)
        wrote_chroma_pure = (not wrote_grid) and (not wrote_table) and (not wrote_style) and \
            (not wrote_density) and (not wrote_longform) and (not wrote_transitions) and (not wrote_epoch) and \
            (not wrote_t3) and (not wrote_chroma) and write_chroma_pure_folder(
                kind, name, label, desc or subtitle, date_str, clips, source_dir, findings, status, known_pages)
        # avp DoRA board (arm x epoch grid + prompt selector, see
        # write_avp_board_folder) -- tried by name since its filename schema
        # (epoch/step/prompt) doesn't overlap any other writer's regex, kept
        # explicit rather than relying purely on regex non-collision.
        wrote_avp = (not wrote_grid) and (not wrote_table) and (not wrote_style) and \
            (not wrote_density) and (not wrote_longform) and (not wrote_transitions) and (not wrote_epoch) and \
            (not wrote_t3) and (not wrote_chroma) and (not wrote_chroma_pure) and name == "avp_board" and \
            write_avp_board_folder(kind, name, label, desc or subtitle, date_str, findings, status, known_pages)
        # avp seeds board (ckpt x prompt grid + seed selector, see
        # write_avp_seeds_folder) -- tried by name, same rationale as avp_board
        wrote_seeds = (not wrote_grid) and (not wrote_table) and (not wrote_style) and \
            (not wrote_density) and (not wrote_longform) and (not wrote_transitions) and (not wrote_epoch) and \
            (not wrote_t3) and (not wrote_chroma) and (not wrote_chroma_pure) and (not wrote_avp) and \
            name == "avp_board_seeds" and write_avp_seeds_folder(
                kind, name, label, desc or subtitle, date_str, findings, status, known_pages)
        # other single-arm ladder boards sharing the same filename grammar
        # (see write_avp_ladder_folder) -- tried by name, same rationale.
        wrote_ladder = (not wrote_grid) and (not wrote_table) and (not wrote_style) and \
            (not wrote_density) and (not wrote_longform) and (not wrote_transitions) and (not wrote_epoch) and \
            (not wrote_t3) and (not wrote_chroma) and (not wrote_chroma_pure) and (not wrote_avp) and \
            (not wrote_seeds) and name in AVP_LADDER_BOARDS and write_avp_ladder_folder(
                kind, name, label, desc or subtitle, date_str, AVP_BOARD_PARAMS.get(AVP_LADDER_BOARDS[name], ""),
                findings=findings, status=status, known_pages=known_pages)
        # cfg x training-stage sweep (see write_avp_cfg_sweep_folder) -- tried by
        # name, same rationale as the other avp writers.
        wrote_cfgsweep = (not wrote_grid) and (not wrote_table) and (not wrote_style) and \
            (not wrote_density) and (not wrote_longform) and (not wrote_transitions) and (not wrote_epoch) and \
            (not wrote_t3) and (not wrote_chroma) and (not wrote_chroma_pure) and (not wrote_avp) and \
            (not wrote_seeds) and (not wrote_ladder) and name == "avp_cfg_sweep" and \
            write_avp_cfg_sweep_folder(kind, name, label, desc or subtitle, date_str,
                                        findings, status, known_pages)
        # memorized-checkpoint a2a test (nl x variant, see write_memo_a2a_folder)
        # -- tried by name, same rationale as the other one-off writers above.
        wrote_memo = (not wrote_grid) and (not wrote_table) and (not wrote_style) and \
            (not wrote_density) and (not wrote_longform) and (not wrote_transitions) and (not wrote_epoch) and \
            (not wrote_t3) and (not wrote_chroma) and (not wrote_chroma_pure) and (not wrote_avp) and \
            (not wrote_seeds) and (not wrote_ladder) and (not wrote_cfgsweep) and name == "memo_ckpt_a2a_test" and \
            write_memo_a2a_folder(kind, name, label, desc or subtitle, date_str, clips,
                                   findings, status, known_pages)
        if not (wrote_grid or wrote_table or wrote_style or wrote_density or wrote_longform
                or wrote_transitions or wrote_epoch or wrote_t3 or wrote_chroma or wrote_chroma_pure
                or wrote_avp or wrote_seeds or wrote_ladder or wrote_cfgsweep or wrote_memo):
            write_folder(kind, name, label, desc or subtitle, clips, date_str, verdict, findings, status, known_pages)
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
    if composed_members:
        name = "composed_sweep"
        label = "Composed control sweep (adapter + LatCH stages)"
        purpose = ("The composed-control staging sweep: A_cc/A_cc_v2 (FusionCC FiLM adapter alone) "
                   "and E_fusion/E_fusion_v2 (Fusion onset-density adapter alone), each a gain × "
                   "density grid with corr-per-gain. Kim's read: E_fusion_v2 is the standout — "
                   "\"really great, good control range.\"")
        findings, status = findings_status_for(name)
        n_clips = sum(len(c) for k, n, p, c in gathered if n in composed_members)
        if write_composed_sweep_folder("control_runs", name, label, purpose, "", composed_members,
                                        findings, status, known_pages):
            out["control_runs"].append((name, label, purpose, n_clips, "", "", ""))
    for track, a2a_members in a2a_groups.items():
        name = f"a2a_{track}"
        a2a_members = sorted(a2a_members)
        # pull the real track name + duration from any member's run_meta.json
        # for a human label, rather than hardcoding one per track
        track_desc, dur = track, None
        for member in a2a_members:
            mp = f"{STAGING}/renders/{member}/run_meta.json"
            if os.path.exists(mp):
                try:
                    mm = json.load(open(mp))
                    track_desc = redact(mm.get("track", track)).rsplit(".", 1)[0]
                    dur = mm.get("duration_sec")
                    break
                except Exception:
                    pass
        label = f"Full-track a2a noise ladder ({track_desc})"
        dur_txt = f", {dur/60:.0f}:{dur%60:02.0f}" if dur else ""
        purpose = (f"{track_desc}{dur_txt}, re-rendered whole through the adapter(s) at increasing "
                   "init_noise_level — where does it stop being the song and start being the model.")
        findings, status = findings_status_for(name)
        n_clips = sum(len(c) for k, n, p, c in gathered if n in a2a_members)
        # earliest member's real_date(), same "when did this run actually start"
        # definition used everywhere else -- a hardcoded "" here always sorted
        # a2a ladder pages to the bottom of "All runs, newest first" regardless
        # of actual recency (caught 2026-07-10 paging a2a_angelic_r64tiered_lr1e4).
        member_dates = [t for t in (real_date("renders", m) for m in a2a_members) if t is not None]
        date_str = fmt_date(min(member_dates)) if member_dates else ""
        if write_a2a_ladder_folder("renders", name, label, purpose, date_str, a2a_members,
                                    findings, status, known_pages):
            out["renders"].append((name, label, purpose, n_clips, date_str, "", ""))

    # avp master reference (Kim's ask via CONTINUITY, 2026-07-09): consolidates
    # avp_board + the 4 ladder boards into one page with a shared playhead --
    # has no clips of its own (all clips live in the sibling dirs above, which
    # must already be written by this point in the loop), so pass-1's
    # clip-driven scan can't discover it; invoked explicitly here instead.
    avp_master_name = "avp_master"
    if os.path.isdir(f"{OUT}/renders/avp_board"):
        label = "avp adapter investigation — MASTER reference"
        purpose = ("Every avp/goa-baseline render + finding in one place: the arm x epoch grid, "
                   "the originals ckpt ladder (the main degradation story, ep31 marked), Arm G "
                   "(lower-LR), the freeform-caption A/B, and the GOA in-distribution baseline — "
                   "one page, one shared playhead, so the whole investigation reads top to bottom.")
        findings, status = findings_status_for(avp_master_name)
        if write_avp_master_folder("renders", avp_master_name, label, purpose, "",
                                    findings, status, known_pages):
            out["renders"].append((avp_master_name, label, purpose, 0, "", "", ""))

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
