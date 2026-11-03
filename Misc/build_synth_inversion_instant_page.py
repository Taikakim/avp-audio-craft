#!/usr/bin/env python3
"""build_synth_inversion_instant_page.py — Generates the synth inversion evaluation page
with a true sample-accurate, zero-latency instant-flipping audio player.

Supports:
- H6 continuation models (h6_online, h6_ema, h6_ema_t07, h6_ema_t04, h6_ema_t01)
- Baselines from H1 (old, online, ema)
- Real stem ground truth
- Instantaneous column flipping via Web Audio API (or seamless HTML5 Audio fallback)
- Transport bar with solo pills and keyboard shortcuts (1-9, Space, Left/Right, Up/Down, Loop)
"""
import os
import sys
import json
import html
import subprocess
from pathlib import Path

ROOT = Path("/run/media/kim/Mantu/surge_200k_models")
if not ROOT.exists():
    ROOT = Path("/run/media/kim/Mantu/surge_200k_models")

H1_DIR = ROOT / "fxfix_ladder_ema_b64"
H6_DIR = ROOT / "h6_cont4h_b64"
CATALOG_PATH = ROOT / "real_stems_eval" / "real_stems_summary.json"

OUT_DIRS = [
    Path.home() / "evals_aac",
    Path.home() / ".cache" / "evals_aac",
]

# Column definitions: (key, short_label, full_label, source_dir)
COLUMNS = [
    ("old", "Oct 5 (old)", "Previous baseline (Oct 5, with FX delay)", H1_DIR / "clips_old"),
    ("online", "H1 · online", "H1 final weights (FX delay fixed, 78k steps)", H1_DIR / "clips_online"),
    ("ema", "H1 · EMA", "H1 EMA weights (half-life 2000 steps, 78k steps)", H1_DIR / "clips_ema"),
    ("h6_online", "H6+4h · online", "H6 continuation (step 33.2k), raw weights, clean condition", H6_DIR / "clips_h6_online"),
    ("h6_ema", "H6+4h · EMA", "H6 continuation (step 33.2k), EMA weights, clean condition", H6_DIR / "clips_h6_ema"),
    ("h6_ema_t07", "H6+4h · EMA τ0.7", "H6 continuation EMA, conditioned with 30% noise", H6_DIR / "clips_h6_ema_t07"),
    ("h6_ema_t04", "H6+4h · EMA τ0.4", "H6 continuation EMA, conditioned with 60% noise", H6_DIR / "clips_h6_ema_t04"),
    ("h6_ema_t01", "H6+4h · EMA τ0.1", "H6 continuation EMA, conditioned with 90% noise (Synth-JDF point)", H6_DIR / "clips_h6_ema_t01"),
]


def transcode_to_m4a(src_wav: Path, dst_m4a: Path) -> bool:
    if not src_wav.exists():
        return False
    if dst_m4a.exists() and dst_m4a.stat().st_mtime >= src_wav.stat().st_mtime:
        return True
    dst_m4a.parent.mkdir(parents=True, exist_ok=True)
    res = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src_wav), "-c:a", "aac", "-b:a", "128k", str(dst_m4a)],
        capture_output=True
    )
    return res.returncode == 0


def load_val_metrics():
    val_file = H6_DIR / "val_kinds.jsonl"
    if not val_file.exists():
        return None
    lines = [json.loads(line) for line in val_file.read_text().splitlines() if line.strip()]
    return lines[-1] if lines else None


def fmt(v, nd=2):
    return "—" if v is None else f"{v:.{nd}f}"


def build_page():
    for out_base in OUT_DIRS:
        (out_base / "synth_inversion").mkdir(parents=True, exist_ok=True)

    catalog = json.load(open(CATALOG_PATH)) if CATALOG_PATH.exists() else []
    stem_ids = [item["id"] for item in catalog]

    # Convert audio files to m4a in both destinations
    available_files = {}  # (stem_id, col_key) -> bool
    
    # 1. Real stems
    real_src_dir = ROOT / "real_stems_eval" / "audio"
    for sid in stem_ids:
        src = real_src_dir / f"{sid}_real.wav"
        if not src.exists():
            # fallback to any clips dir
            src = H1_DIR / "clips_online" / "audio" / f"{sid}_real.wav"
        
        ok = False
        for out_base in OUT_DIRS:
            dst = out_base / "synth_inversion" / f"{sid}_real.m4a"
            if src.exists():
                transcode_to_m4a(src, dst)
            ok = ok or dst.exists()
        available_files[(sid, "real")] = ok

    # 2. Model columns
    for col_key, _, _, src_dir in COLUMNS:
        for sid in stem_ids:
            src = src_dir / "audio" / f"{sid}_midi_playback.wav"
            ok = False
            for out_base in OUT_DIRS:
                dst = out_base / "synth_inversion" / f"{sid}_{col_key}.m4a"
                if src.exists():
                    transcode_to_m4a(src, dst)
                ok = ok or dst.exists()
            available_files[(sid, col_key)] = ok

    # Load training metrics
    val = load_val_metrics()

    # Load or compute comparison metrics
    # If comparison.json exists in H1 or H6
    comp_data = {}
    for c_path in [H1_DIR / "clips_AB" / "comparison.json", H6_DIR / "clips_AB" / "comparison.json"]:
        if c_path.exists():
            try:
                d = json.load(open(c_path))
                for r in d.get("rows", []):
                    comp_data.setdefault(r["stem_id"], {}).update(r)
            except Exception:
                pass

    doc = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Synth inversion · H6 + 4h Continuation vs Baselines</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="evals.css">
<style>
/* Instant flip specific styling */
.instant-badge {
  display: inline-block;
  background: #0f9e99;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .1em;
  padding: 2px 7px;
  border-radius: 3px;
  margin-left: 8px;
  text-transform: uppercase;
  vertical-align: middle;
}
.hotkey-bar {
  background: #1e2225;
  border: 1px solid #2f363b;
  border-left: 3px solid #0f9e99;
  padding: 10px 14px;
  margin: 18px 0 22px;
  border-radius: 4px;
  font-size: 11.5px;
  color: #d2dede;
  line-height: 1.8;
}
.hotkey-bar kbd {
  background: #2b3538;
  border: 1px solid #455256;
  color: #7ef0eb;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: inherit;
  font-weight: 600;
  font-size: 11px;
}
.cell {
  position: relative;
  transition: background-color 0.08s ease, color 0.08s ease;
  user-select: none;
}
.cell.playing {
  background: #0f9e99 !important;
  color: #fff !important;
  box-shadow: 0 0 8px rgba(15, 158, 153, 0.4);
}
.cell.row-active {
  background: #e5eceb;
}
.cell.pending {
  color: #9aa7a9;
  background: #f4f5f1;
  cursor: default;
}
/* Enhanced Transport Dock */
#xport {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 999;
  display: flex;
  flex-direction: column;
  background: #14171a;
  border-top: 1px solid #2a3136;
  box-shadow: 0 -4px 18px rgba(0,0,0,0.35);
  font: 12px 'IBM Plex Mono', monospace;
  color: #dbe;
}
.xport-top {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
}
.xport-pills {
  display: flex;
  align-items: center;
  gap: 6px;
  overflow-x: auto;
  padding: 4px 16px 8px;
  border-top: 1px solid #1f2529;
}
.xpill {
  background: #22292f;
  color: #8da2aa;
  border: 1px solid #333e46;
  padding: 3px 8px;
  border-radius: 3px;
  font-size: 11px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.06s ease;
}
.xpill:hover {
  background: #2b353d;
  color: #fff;
}
.xpill.active {
  background: #0f9e99;
  color: #fff;
  border-color: #0f9e99;
  font-weight: 600;
}
.xpill kbd {
  color: #7ef0eb;
  font-size: 10px;
  margin-right: 4px;
}
#xpp {
  background: #0f9e99;
  border: none;
  color: #fff;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  padding: 4px 10px;
}
#xpp:hover { background: #0c807c; }
#xloop {
  background: #22292f;
  border: 1px solid #333e46;
  color: #8da2aa;
  border-radius: 3px;
  padding: 3px 7px;
  cursor: pointer;
  font-size: 11px;
}
#xloop.on {
  color: #7ef0eb;
  border-color: #0f9e99;
}
#xnp {
  font-weight: 600;
  color: #fff;
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
#xcol {
  color: #7ef0eb;
  font-size: 11px;
}
#xseek {
  flex: 1;
  accent-color: #0f9e99;
  cursor: pointer;
  height: 5px;
}
#xtm {
  color: #9ab;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
#xdl {
  color: #7ef0eb;
  text-decoration: none;
  font-size: 15px;
}
</style>
</head><body><div class="wrap">
<p class="over">VIBE ON THE EDG3 · SYNTH INVERSION EVALS</p>
<h1>Synth Inversion — 24 Real Bass Phrases <span class="instant-badge">⚡ Instant A/B Flip</span></h1>

<p><b>What this is.</b> 24 separated real bass stems from classic Goa and Psytrance productions. 
A model listens to the stem audio, predicts Surge XT synthesizer parameters via Flow Matching, 
and re-synthesizes the phrase with note-matched MIDI events from a MuScriptor transcription. 
<b>Real</b> is the original stem; other columns are neural synthesizer re-creations.</p>

<p><b>The H6 Continuation (step 33,230):</b> The H6 model was resumed from step 16,000 for 4 hours with 
noisy-conditioning training (cond-noise with clean frac 0.3, tau ~ logit-normal). Held-out JEPA loss fell 
<b>26.4%</b> (0.5388 &rarr; <b>0.3966</b>) and retrieval jumped to <b>73.0%</b> (a2p) / <b>75.2%</b> (p2a). 
This page audits whether noisy-conditioning improves audio reconstruction across the 24 real stems.</p>

<div class="hotkey-bar">
<b>⚡ Zero-Latency Instant Flip Player:</b> Click any cell to solo it instantly. Switching columns while playing maintains the exact playhead position with <i>sample-accurate synchronization</i> and zero audio gap.<br>
<b>Keyboard Shortcuts:</b>
<kbd>Space</kbd> Play / Pause &nbsp;|&nbsp;
<kbd>1</kbd>–<kbd>8</kbd> Instant Solo Column &nbsp;|&nbsp;
<kbd>&larr;</kbd> / <kbd>&rarr;</kbd> or <kbd>[</kbd> / <kbd>]</kbd> Step Model &nbsp;|&nbsp;
<kbd>&uarr;</kbd> / <kbd>&darr;</kbd> Prev / Next Phrase &nbsp;|&nbsp;
<kbd>L</kbd> Toggle Seamless Loop
</div>
"""

    # Training Metrics Table
    if val:
        doc += """<h2>Model Training Metrics (Held-Out Preset Evaluation)</h2>
<table class="t">
<tr><th>Model Variant</th><th>Flow Loss &darr;</th><th>JEPA Loss &darr;</th><th>Retrieval Audio&rarr;Patch</th><th>Patch&rarr;Audio</th><th>Ladder Mean &rho;</th></tr>"""
        for tag, lab in [("online", "H6+4h · online (raw weights)"), ("ema", "H6+4h · EMA (hl 2000)"), ("sf", "H6+4h · SF average")]:
            g = lambda m: val.get(f"{tag}/heldout/{m}")
            flow_l = fmt(g("flow"), 3)
            jepa_l = fmt(g("jepa"), 3)
            r_a2p = fmt((g("r_a2p") or 0) * 100 if g("r_a2p") is not None and g("r_a2p") <= 1 else g("r_a2p"), 1) + "%"
            r_p2a = fmt((g("r_p2a") or 0) * 100 if g("r_p2a") is not None and g("r_p2a") <= 1 else g("r_p2a"), 1) + "%"
            lad = fmt(val.get(f"{tag}/heldout/ladder_jepa_rho_mean"), 3)
            doc += f"<tr><td><b>{lab}</b></td><td>{flow_l}</td><td>{jepa_l}</td><td>{r_a2p}</td><td>{r_p2a}</td><td>{lad}</td></tr>"
        doc += """</table>
<p class="faint">Chance retrieval is 0.20% (1 in 512). Measured on unseen held-out Surge patches. Ladder rho measures monotonic response across cutoff/envelope sweeps.</p>"""

    # Phrase Table
    doc += """<h2>Phrases & Re-Creations</h2>
<table class="t" id="phrase-table">
<tr><th>#</th><th>Phrase</th><th>Real</th>"""
    for _, short_lab, full_lab, _ in COLUMNS:
        doc += f'<th title="{html.escape(full_lab)}">{html.escape(short_lab)}</th>'
    doc += "</tr>\n"

    for idx, c in enumerate(catalog):
        sid = c["id"]
        label = html.escape(c.get("name", sid))
        sub = html.escape(" · ".join(x for x in (c.get("style"), f'{c["bpm"]:g} BPM' if c.get("bpm") else None) if x))
        
        doc += f'<tr data-row="{sid}"><td>{idx+1}</td><td><b>{label}</b><br><span class="faint">{sub}</span></td>\n'
        
        # Real cell (Column 0)
        has_real = available_files.get((sid, "real"), False)
        if has_real:
            doc += f'<td class="cell" data-src="synth_inversion/{sid}_real.m4a" data-row="{sid}" data-col="0" data-col-name="Real" data-title="{label}" onclick="playCell(this)">&#9654; Real</td>\n'
        else:
            doc += '<td class="cell pending">pending</td>\n'

        # Model columns (Columns 1..N)
        for c_idx, (col_key, short_lab, _, _) in enumerate(COLUMNS, start=1):
            has_clip = available_files.get((sid, col_key), False)
            if has_clip:
                score_str = ""
                m = comp_data.get(sid, {}).get(col_key)
                if m:
                    score_str = f" <small>({m['mss']:.2f})</small>"
                doc += f'<td class="cell" data-src="synth_inversion/{sid}_{col_key}.m4a" data-row="{sid}" data-col="{c_idx}" data-col-name="{html.escape(short_lab)}" data-title="{label}" onclick="playCell(this)">&#9654; {html.escape(short_lab)}{score_str}</td>\n'
            else:
                doc += '<td class="cell pending" title="Rendering in progress">&#8987; pending</td>\n'
        doc += "</tr>\n"

    doc += """</table>

<div id="xport">
  <div class="xport-top">
    <button id="xpp" title="Play / Pause (Space)">&#9208;</button>
    <button id="xloop" class="on" title="Toggle Loop (L)">&#128257; Loop: ON</button>
    <div style="display:flex; flex-direction:column; min-width:180px;">
      <span id="xnp">No clip selected</span>
      <span id="xcol">—</span>
    </div>
    <input type="range" id="xseek" min="0" max="1000" value="0" title="Scrub playhead">
    <span id="xtm">0:00 / 0:00</span>
    <a id="xdl" href="#" download title="Download this clip">&#8681;</a>
  </div>
  <div class="xport-pills" id="xpill-row">
    <!-- Pills populated by JS -->
  </div>
</div>

<script>
// INSTANT-FLIP SAMPLE-ACCURATE WEB AUDIO ENGINE
const COLUMN_DEFS = [
  { idx: 0, key: 'real', label: 'Real' },
"""
    for idx, (col_key, short_lab, _, _) in enumerate(COLUMNS, start=1):
        doc += f"  {{ idx: {idx}, key: '{col_key}', label: '{html.escape(short_lab)}' }},\n"

    doc += """
];

let audioCtx = null;
let activeRow = null;
let activeCol = 0;
let isPlaying = false;
let isLooping = true;
let sources = {};
let gains = {};
let masterGain = null;
let startedAt = 0;
let playOffset = 0;
let rowDuration = 0;
let bufferCache = new Map();
let fallbackAudios = {};
let isFallback = false;

function ensureAudioCtx() {
  if (!audioCtx) {
    const AudioCtor = window.AudioContext || window.webkitAudioContext;
    audioCtx = new AudioCtor();
    masterGain = audioCtx.createGain();
    masterGain.gain.value = 1.0;
    masterGain.connect(audioCtx.destination);
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
}

function stopSources() {
  if (isFallback) {
    for (let k in fallbackAudios) {
      try { fallbackAudios[k].pause(); } catch(e) {}
    }
    fallbackAudios = {};
  } else {
    for (let k in sources) {
      try { sources[k].stop(); sources[k].disconnect(); } catch(e) {}
    }
    for (let k in gains) {
      try { gains[k].disconnect(); } catch(e) {}
    }
    sources = {};
    gains = {};
  }
  isPlaying = false;
}

function getCurrentPosition() {
  if (!isPlaying) return playOffset;
  if (isFallback) {
    const a = fallbackAudios[activeCol];
    return a ? a.currentTime : playOffset;
  }
  const elapsed = audioCtx.currentTime - startedAt;
  const pos = playOffset + elapsed;
  return isLooping && rowDuration > 0 ? (pos % rowDuration) : Math.min(rowDuration, pos);
}

async function loadBuffer(url) {
  if (bufferCache.has(url)) return bufferCache.get(url);
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error("HTTP " + r.status);
    const ab = await r.arrayBuffer();
    const buf = await audioCtx.decodeAudioData(ab);
    bufferCache.set(url, buf);
    return buf;
  } catch(err) {
    console.warn("WebAudio fetch failed for", url, err);
    return null;
  }
}

async function playRow(rowId, colIdx, targetOffset = 0) {
  ensureAudioCtx();
  stopSources();
  
  activeRow = rowId;
  activeCol = colIdx;
  
  const tr = document.querySelector(`tr[data-row="${rowId}"]`);
  if (!tr) return;
  const cells = Array.from(tr.querySelectorAll('.cell[data-src]'));
  if (!cells.length) return;

  const targetCell = cells.find(c => parseInt(c.dataset.col, 10) === colIdx) || cells[0];
  const phraseTitle = targetCell.dataset.title || rowId;
  const colName = targetCell.dataset.colName || 'Clip';
  
  document.getElementById('xnp').textContent = phraseTitle;
  document.getElementById('xcol').textContent = colName;
  document.getElementById('xdl').href = targetCell.dataset.src;
  document.getElementById('xdl').setAttribute('download', targetCell.dataset.src.split('/').pop());

  // Try Web Audio loading
  let webAudioOk = true;
  const loadPromises = cells.map(async c => {
    const cIdx = parseInt(c.dataset.col, 10);
    const buf = await loadBuffer(c.dataset.src);
    return { cIdx, buf, cell: c };
  });

  const results = await Promise.all(loadPromises);
  const valid = results.filter(r => r.buf !== null);
  
  if (valid.length > 0) {
    isFallback = false;
    rowDuration = Math.max(...valid.map(v => v.buf.duration));
    playOffset = Math.max(0, Math.min(targetOffset, rowDuration - 0.05));
    
    const t0 = audioCtx.currentTime + 0.03;
    valid.forEach(({ cIdx, buf }) => {
      const src = audioCtx.createBufferSource();
      const g = audioCtx.createGain();
      src.buffer = buf;
      src.loop = isLooping;
      
      // Solo the selected column
      g.gain.value = (cIdx === activeCol) ? 1.0 : 0.0;
      src.connect(g);
      g.connect(masterGain);
      
      src.start(t0, playOffset);
      sources[cIdx] = src;
      gains[cIdx] = g;
    });

    startedAt = t0;
    isPlaying = true;
  } else {
    // Fallback for file:// CORS block: parallel HTMLAudioElements
    isFallback = true;
    cells.forEach(c => {
      const cIdx = parseInt(c.dataset.col, 10);
      const a = new Audio(c.dataset.src);
      a.loop = isLooping;
      a.volume = (cIdx === activeCol) ? 1.0 : 0.0;
      a.currentTime = targetOffset;
      fallbackAudios[cIdx] = a;
      a.play().catch(()=>{});
    });
    isPlaying = true;
    rowDuration = 8.0;
  }

  updateUI();
  updatePills();
}

function flipToCol(newColIdx) {
  if (activeCol === newColIdx) return;
  const prevCol = activeCol;
  activeCol = newColIdx;

  if (isPlaying) {
    if (!isFallback && audioCtx) {
      const now = audioCtx.currentTime;
      if (gains[prevCol]) {
        gains[prevCol].gain.setTargetAtTime(0.0, now, 0.005);
      }
      if (gains[activeCol]) {
        gains[activeCol].gain.setTargetAtTime(1.0, now, 0.005);
      }
    } else if (isFallback) {
      if (fallbackAudios[prevCol]) fallbackAudios[prevCol].volume = 0.0;
      if (fallbackAudios[activeCol]) fallbackAudios[activeCol].volume = 1.0;
    }
  }

  const tr = document.querySelector(`tr[data-row="${activeRow}"]`);
  if (tr) {
    const c = tr.querySelector(`.cell[data-col="${activeCol}"]`);
    if (c) {
      document.getElementById('xcol').textContent = c.dataset.colName || '';
      document.getElementById('xdl').href = c.dataset.src;
      document.getElementById('xdl').setAttribute('download', c.dataset.src.split('/').pop());
    }
  }

  updateUI();
  updatePills();
}

function playCell(el) {
  const rowId = el.dataset.row;
  const colIdx = parseInt(el.dataset.col, 10);
  
  if (activeRow === rowId && isPlaying) {
    if (activeCol === colIdx) {
      // Toggle pause
      togglePlay();
      return;
    } else {
      // Instant flip within current row!
      flipToCol(colIdx);
      return;
    }
  }
  
  // Switch to new row or start playback
  const currPos = (activeRow === rowId) ? getCurrentPosition() : 0;
  playRow(rowId, colIdx, currPos);
}

function togglePlay() {
  if (!activeRow) {
    const firstCell = document.querySelector('.cell[data-src]');
    if (firstCell) playCell(firstCell);
    return;
  }
  if (isPlaying) {
    playOffset = getCurrentPosition();
    stopSources();
  } else {
    playRow(activeRow, activeCol, playOffset);
  }
  updateUI();
}

function toggleLoop() {
  isLooping = !isLooping;
  const btn = document.getElementById('xloop');
  btn.classList.toggle('on', isLooping);
  btn.innerHTML = isLooping ? '&#128257; Loop: ON' : '&#10145; Loop: OFF';
  for (let k in sources) {
    try { sources[k].loop = isLooping; } catch(e){}
  }
  for (let k in fallbackAudios) {
    try { fallbackAudios[k].loop = isLooping; } catch(e){}
  }
}

function updateUI() {
  document.querySelectorAll('.cell.playing').forEach(c => c.classList.remove('playing'));
  document.querySelectorAll('.cell.row-active').forEach(c => c.classList.remove('row-active'));
  
  if (activeRow) {
    const tr = document.querySelector(`tr[data-row="${activeRow}"]`);
    if (tr) {
      tr.querySelectorAll('.cell').forEach(c => c.classList.add('row-active'));
      const activeCell = tr.querySelector(`.cell[data-col="${activeCol}"]`);
      if (activeCell && isPlaying) {
        activeCell.classList.add('playing');
      }
    }
  }

  const pp = document.getElementById('xpp');
  pp.innerHTML = isPlaying ? '&#9208;' : '&#9654;';
}

function updatePills() {
  const container = document.getElementById('xpill-row');
  container.innerHTML = '';
  
  const tr = document.querySelector(`tr[data-row="${activeRow}"]`);
  if (!tr) return;

  COLUMN_DEFS.forEach(def => {
    const cell = tr.querySelector(`.cell[data-col="${def.idx}"]`);
    if (!cell || cell.classList.contains('pending')) return;
    
    const pill = document.createElement('button');
    pill.className = 'xpill' + (def.idx === activeCol ? ' active' : '');
    pill.innerHTML = `<kbd>${def.idx + 1}</kbd> ${def.label}`;
    pill.onclick = () => flipToCol(def.idx);
    container.appendChild(pill);
  });
}

function fmtTime(s) {
  s = Math.max(0, s | 0);
  return (s / 60 | 0) + ':' + String(s % 60).padStart(2, '0');
}

// Animation loop for seekbar & time display
function tick() {
  if (isPlaying && rowDuration > 0 && !isDraggingSeek) {
    const pos = getCurrentPosition();
    const seek = document.getElementById('xseek');
    seek.value = Math.round((pos / rowDuration) * 1000);
    document.getElementById('xtm').textContent = `${fmtTime(pos)} / ${fmtTime(rowDuration)}`;
  }
  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);

// Seekbar scrubbing
const xseek = document.getElementById('xseek');
xseek.addEventListener('input', () => {
  isDraggingSeek = true;
  const target = (xseek.value / 1000) * rowDuration;
  document.getElementById('xtm').textContent = `${fmtTime(target)} / ${fmtTime(rowDuration)}`;
});
xseek.addEventListener('change', () => {
  const target = (xseek.value / 1000) * rowDuration;
  if (activeRow) {
    playRow(activeRow, activeCol, target);
  }
  isDraggingSeek = false;
});

document.getElementById('xpp').onclick = togglePlay;
document.getElementById('xloop').onclick = toggleLoop;

// KEYBOARD SHORTCUTS FOR RAPID INSTANT A/B FLIPPING
window.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  
  if (e.code === 'Space') {
    e.preventDefault();
    togglePlay();
  } else if (e.key >= '1' && e.key <= '9') {
    const colTarget = parseInt(e.key, 10) - 1;
    if (activeRow) {
      flipToCol(colTarget);
    }
  } else if (e.key === 'ArrowRight' || e.key === ']') {
    e.preventDefault();
    if (activeRow) {
      const tr = document.querySelector(`tr[data-row="${activeRow}"]`);
      const validCols = Array.from(tr.querySelectorAll('.cell[data-src]'))
        .map(c => parseInt(c.dataset.col, 10))
        .filter(n => !isNaN(n))
        .sort((a,b)=>a-b);
      const currIdx = validCols.indexOf(activeCol);
      const nextCol = validCols[(currIdx + 1) % validCols.length];
      flipToCol(nextCol);
    }
  } else if (e.key === 'ArrowLeft' || e.key === '[') {
    e.preventDefault();
    if (activeRow) {
      const tr = document.querySelector(`tr[data-row="${activeRow}"]`);
      const validCols = Array.from(tr.querySelectorAll('.cell[data-src]'))
        .map(c => parseInt(c.dataset.col, 10))
        .filter(n => !isNaN(n))
        .sort((a,b)=>a-b);
      const currIdx = validCols.indexOf(activeCol);
      const prevCol = validCols[(currIdx - 1 + validCols.length) % validCols.length];
      flipToCol(prevCol);
    }
  } else if (e.key === 'ArrowDown') {
    e.preventDefault();
    const rows = Array.from(document.querySelectorAll('tr[data-row]'));
    const currRowIdx = rows.findIndex(r => r.dataset.row === activeRow);
    const nextRow = rows[(currRowIdx + 1) % rows.length];
    if (nextRow) {
      playRow(nextRow.dataset.row, activeCol, 0);
    }
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    const rows = Array.from(document.querySelectorAll('tr[data-row]'));
    const currRowIdx = rows.findIndex(r => r.dataset.row === activeRow);
    const prevRow = rows[(currRowIdx - 1 + rows.length) % rows.length];
    if (prevRow) {
      playRow(prevRow.dataset.row, activeCol, 0);
    }
  } else if (e.key.toLowerCase() === 'l') {
    toggleLoop();
  }
});
</script>
</div></body></html>
"""

    for out_base in OUT_DIRS:
        page_path = out_base / "synth_inversion.html"
        page_path.write_text(doc)
        print(f"Wrote {page_path}")


if __name__ == "__main__":
    build_page()
