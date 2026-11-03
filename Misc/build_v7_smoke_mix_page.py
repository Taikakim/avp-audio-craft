#!/usr/bin/env python3
"""build_v7_smoke_mix_page.py — Generates the v7 4-clip continuous smoke mix evaluation page
with a true sample-accurate, zero-latency instant-flipping audio player.

Features:
- Continuous 4-Clip Full Mixes (10 variants, 146.3s each)
- Isolated 8-bar Transition Renders (3 transitions x 10 variants)
- Instantaneous column flipping via Web Audio API (with seamless HTML5 Audio fallback)
- Transport dock with solo pills and keyboard shortcuts (1-9, 0, Space, Left/Right, Up/Down, Loop)
- Diagnostics and sync metrics from run_meta.json
"""
import os
import sys
import json
import html
import subprocess
from pathlib import Path

RUN_DIR = Path("/home/kim/staging/kone-mixtape/smoke/kuang_smoke_4clips")
RUN_META = RUN_DIR / "run_meta.json"

OUT_DIRS = [
    Path.home() / "evals_aac",
    Path.home() / ".cache" / "evals_aac",
]

# 10 variants in logical evaluation order
VARIANTS = [
    ("skipped", "1. Baseline (Clean DSP)", "Clean DSP baseline (drum crossfade + other crossfade, no AI inpainting)", "#107c41"),
    ("d-xfade_o-slerp", "2. Drums DSP + Other Slerp", "Drums crossfade + Other latent slerp (0ms offset fix)", "#0f9e99"),
    ("d-inpaint2bar_o-skipped", "3. Drums Inpaint 2b + Other DSP", "Drums masked inpaint 2 bars + Other clean DSP crossfade", "#0078d4"),
    ("d-inpaint2bar_o-slerp", "4. Drums Inpaint 2b + Other Slerp", "Drums masked inpaint 2 bars + Other latent slerp", "#5c2d91"),
    ("d-inpaint2bar_o-inpaint2bar", "5. Drums Inpaint 2b + Other Inpaint 2b", "Drums masked inpaint 2 bars + Other masked inpaint 2 bars", "#b4009e"),
    ("d-inpaint2bar_o-inpaint4bar", "6. Drums Inpaint 2b + Other Inpaint 4b", "Drums masked inpaint 2 bars + Other masked inpaint 4 bars", "#d83b01"),
    ("d-inpaint4bar_o-skipped", "7. Drums Inpaint 4b + Other DSP", "Drums masked inpaint 4 bars + Other clean DSP crossfade", "#a80000"),
    ("d-inpaint4bar_o-slerp", "8. Drums Inpaint 4b + Other Slerp", "Drums masked inpaint 4 bars + Other latent slerp", "#ca5010"),
    ("d-inpaint4bar_o-inpaint2bar", "9. Drums Inpaint 4b + Other Inpaint 2b", "Drums masked inpaint 4 bars + Other masked inpaint 2 bars", "#e3008c"),
    ("d-inpaint4bar_o-inpaint4bar", "0. Drums Inpaint 4b + Other Inpaint 4b", "Drums masked inpaint 4 bars + Other masked inpaint 4 bars", "#c239b3"),
]


def transcode_to_m4a(src_wav: Path, dst_m4a: Path) -> bool:
    if not src_wav.exists():
        return False
    if dst_m4a.exists() and dst_m4a.stat().st_mtime >= src_wav.stat().st_mtime:
        return True
    dst_m4a.parent.mkdir(parents=True, exist_ok=True)
    res = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src_wav), "-c:a", "aac", "-b:a", "192k", str(dst_m4a)],
        capture_output=True
    )
    return res.returncode == 0


def fmt(v, nd=2):
    return "—" if v is None else f"{v:.{nd}f}"


def build_page():
    for out_base in OUT_DIRS:
        (out_base / "smoke_mix").mkdir(parents=True, exist_ok=True)

    meta = json.load(open(RUN_META)) if RUN_META.exists() else {}
    transitions = meta.get("transitions", [])
    assembled = {item["variant"]: item for item in meta.get("assembled_mixes", [])}

    # Ensure all m4a files are in place in both evals_aac and .cache/evals_aac
    for v_key, _, _, _ in VARIANTS:
        # Full mix
        mix_wav = RUN_DIR / f"v7_smoke_mix_4clips_{v_key}.wav"
        for out_base in OUT_DIRS:
            dst_m4a = out_base / "smoke_mix" / f"v7_smoke_mix_4clips_{v_key}.m4a"
            transcode_to_m4a(mix_wav, dst_m4a)

        # Transitions
        for t_idx in range(len(transitions)):
            trans_wav = RUN_DIR / f"v7_smoke_trans_FAST_{t_idx}_{v_key}.wav"
            for out_base in OUT_DIRS:
                dst_m4a = out_base / "smoke_mix" / f"v7_smoke_trans_FAST_{t_idx}_{v_key}.m4a"
                transcode_to_m4a(trans_wav, dst_m4a)

    doc = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>v7 4-Clip Smoke Mix · Instant A/B Flip Player</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="evals.css">
<style>
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
  font-size: 11px;
  padding: 8px 10px;
  cursor: pointer;
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
.cell-tag {
  display: block;
  font-size: 9.5px;
  opacity: 0.8;
  margin-top: 3px;
}
.clip-badge {
  display: inline-block;
  padding: 1px 5px;
  border-radius: 3px;
  background: #eef2f2;
  border: 1px solid #d2dede;
  font-size: 10.5px;
  font-family: inherit;
  margin: 1px 0;
}
.warn-box {
  background: #fff8f0;
  border: 1px solid #fed7aa;
  border-left: 3px solid #f97316;
  padding: 10px 14px;
  margin: 16px 0;
  font-size: 12px;
  line-height: 1.6;
  border-radius: 3px;
}
.info-box {
  background: #f0fdfa;
  border: 1px solid #99f6e4;
  border-left: 3px solid #0f9e99;
  padding: 10px 14px;
  margin: 16px 0;
  font-size: 12px;
  line-height: 1.6;
  border-radius: 3px;
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
.diag-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11.5px;
  margin: 12px 0 24px;
}
.diag-table th {
  background: #f0f3f3;
  padding: 6px 8px;
  text-align: left;
  border-bottom: 2px solid #c9d2d0;
}
.diag-table td {
  padding: 6px 8px;
  border-bottom: 1px solid #e2e6e2;
}
</style>
</head><body><div class="wrap">
<p class="over">VIBE ON THE EDG3 · MIXTAPE V7 CONTINUOUS ENGINE</p>
<h1>v7 Continuous Smoke Mix (4 Clips) <span class="instant-badge">⚡ Instant A/B Flip</span></h1>

<p><b>What this is:</b> An audition matrix for the first 4 clips of the v7 mixtape sequence, 
assembled into a single seamless continuous journey (<b>146.3 seconds / 2m 26s</b>) across 10 algorithmic transition variants, 
alongside isolated 8-bar transition clips (14.1s each).</p>

<div class="info-box">
<b>Clips in order:</b><br>
<b>Clip 0:</b> <span class="clip-badge">dora16_avp_familiarity_8ep (132.08 BPM)</span> &rarr; stretched via Bungee (1.030x) to 136.06 BPM<br>
<b>Clip 1:</b> <span class="clip-badge">dora16_avp_originals_win7 (136.06 BPM)</span><br>
<b>Clip 2:</b> <span class="clip-badge">dora128adj_avp_8ep_final (136.13 BPM)</span><br>
<b>Clip 3:</b> <span class="clip-badge">dora128adj_avp_aug10_lr1e4 (136.06 BPM)</span>
</div>

<div class="warn-box">
<b>Key Insights from this Run:</b><br>
1. <b>SAME Codec Offset Fixed:</b> Unpadded encode calls previously cropped $N \\pmod{4096}$ samples (up to 93 ms early). Fixed with <code>pad_end_to_frame</code>, locking latents to exact sample boundaries (0 ms offset).<br>
2. <b>2-Bar vs 4-Bar Inpainting:</b> Kuang's <code>inpaint_grid_check</code> confirmed that 4-bar drum inpainting drifts and hallucinates extra kicks (<b>9 kicks in an 8-beat span</b> on Transition 0), confirming that <b>2-bar masked inpainting is significantly tighter and safer</b>.<br>
3. <b>False Desync Protection:</b> Transition 2 contained a fill bar with -64 ms offset; Theil-Sen slope estimation verified that true drift was negligible (-0.21 ms/s), preserving smooth linear kick handover instead of muting.
</div>

<div class="hotkey-bar">
<b>⚡ Zero-Latency Instant Flip Player:</b> Click any cell to solo it instantly. Switching variants while playing maintains the exact playhead position with <i>sample-accurate synchronization</i> and zero audio gap.<br>
<b>Keyboard Shortcuts:</b>
<kbd>Space</kbd> Play / Pause &nbsp;|&nbsp;
<kbd>1</kbd>–<kbd>9</kbd>, <kbd>0</kbd> Instant Solo Variant &nbsp;|&nbsp;
<kbd>&larr;</kbd> / <kbd>&rarr;</kbd> or <kbd>[</kbd> / <kbd>]</kbd> Cycle Variant &nbsp;|&nbsp;
<kbd>&uarr;</kbd> / <kbd>&darr;</kbd> Switch Row (Full Mix &harr; Trans 0/1/2) &nbsp;|&nbsp;
<kbd>L</kbd> Toggle Seamless Loop
</div>
"""

    # -------------------------------------------------------------
    # Table 1: Full Continuous 4-Clip Mix
    # -------------------------------------------------------------
    doc += """<h2>1. Full Continuous Mix (4 Clips · 146.3 Seconds)</h2>
<p class="faint">Each row represents the entire continuous mix stitched end-to-end: Clip 0 head &rarr; Transition 0 &rarr; Clip 1 body &rarr; Transition 1 &rarr; Clip 2 body &rarr; Transition 2 &rarr; Clip 3 tail.</p>
<table class="t" style="width:100%;" id="fullmix-table">
<tr><th style="width:120px;">Session</th>"""
    for v_idx, (v_key, label, desc, _) in enumerate(VARIANTS):
        num_key = (v_idx + 1) % 10
        doc += f'<th title="{html.escape(desc)}"><kbd>{num_key}</kbd><br>{html.escape(label.split(". ")[-1])}</th>'
    doc += "</tr>\n"

    doc += '<tr data-row="fullmix"><td><b>Continuous Mix</b><br><span class="faint">146.3s · 4 clips</span></td>\n'
    for v_idx, (v_key, label, desc, color) in enumerate(VARIANTS):
        num_key = (v_idx + 1) % 10
        src = f"smoke_mix/v7_smoke_mix_4clips_{v_key}.m4a"
        cell_name = label.split(". ")[-1]
        doc += f'<td class="cell" data-src="{src}" data-row="fullmix" data-col="{v_idx}" data-col-name="{html.escape(cell_name)}" data-title="Continuous Mix (4 Clips)" onclick="playCell(this)">'
        doc += f'&#9654; <b>{html.escape(cell_name)}</b><span class="cell-tag">{v_key}</span></td>\n'
    doc += "</tr></table>\n"

    # -------------------------------------------------------------
    # Table 2: Isolated Transitions (8 Bars each)
    # -------------------------------------------------------------
    doc += """<h2>2. Isolated 8-Bar Transitions (~14.1 Seconds Each)</h2>
<p class="faint">Audition the exact 8-bar crossfade / morph window in isolation to inspect kick phase alignment, bass handover, and hallucination bounds.</p>
<table class="t" style="width:100%;" id="trans-table">
<tr><th style="width:180px;">Transition Window</th>"""
    for v_idx, (v_key, label, desc, _) in enumerate(VARIANTS):
        num_key = (v_idx + 1) % 10
        doc += f'<th title="{html.escape(desc)}"><kbd>{num_key}</kbd><br>{html.escape(label.split(". ")[-1])}</th>'
    doc += "</tr>\n"

    for t_idx, trans in enumerate(transitions):
        t_row_id = f"trans_{t_idx}"
        bpm_info = f"{trans.get('bpm_a', 0):.1f} &rarr; {trans.get('bpm_b', 0):.1f} BPM"
        title_label = f"Trans {t_idx}: Clip {t_idx} &rarr; {t_idx+1}"
        phase_str = f"phase {trans.get('phase_shift_ms', 0):+.1f}ms"
        
        doc += f'<tr data-row="{t_row_id}"><td><b>Transition {t_idx}</b><br><span class="faint">Clip {t_idx} &rarr; {t_idx+1}<br>{bpm_info} · {phase_str}</span></td>\n'
        for v_idx, (v_key, label, desc, color) in enumerate(VARIANTS):
            num_key = (v_idx + 1) % 10
            src = f"smoke_mix/v7_smoke_trans_FAST_{t_idx}_{v_key}.m4a"
            cell_name = label.split(". ")[-1]
            doc += f'<td class="cell" data-src="{src}" data-row="{t_row_id}" data-col="{v_idx}" data-col-name="{html.escape(cell_name)}" data-title="{title_label}" onclick="playCell(this)">'
            doc += f'&#9654; <b>{html.escape(cell_name)}</b><span class="cell-tag">{v_key}</span></td>\n'
        doc += "</tr>\n"
    doc += "</table>\n"

    # -------------------------------------------------------------
    # Table 3: Diagnostics & Sync Metrics
    # -------------------------------------------------------------
    doc += """<h2>3. Transition Sync & Alignment Diagnostics</h2>
<table class="diag-table">
<tr>
  <th>Trans</th>
  <th>Incoming &rarr; Outgoing Clips</th>
  <th>Tempo Shift</th>
  <th>Kick Phase Align</th>
  <th>Drift Rate</th>
  <th>Linear Ramp</th>
  <th>Inpaint Grid Verdict</th>
</tr>"""
    for t_idx, trans in enumerate(transitions):
        cA_short = trans.get("a", "")[:28] + "…"
        cB_short = trans.get("b", "")[:28] + "…"
        speed = trans.get("bungee_speed", 1.0)
        tempo_txt = f"{trans.get('bpm_a', 0):.1f} &rarr; {trans.get('bpm_b', 0):.1f} BPM"
        if speed != 1.0:
            tempo_txt += f"<br><small>(bungee {speed:.3f}x)</small>"
        
        shift_ms = trans.get("phase_shift_ms", 0)
        ncc0 = trans.get("ncc_zero", 0)
        nccB = trans.get("ncc_best", 0)
        phase_txt = f"{shift_ms:+.1f} ms<br><small>NCC {ncc0:.2f}&rarr;{nccB:.2f}</small>"
        
        drift = trans.get("ab_drift_ms_per_s", 0)
        drift_txt = f"{drift:+.2f} ms/s"
        
        ramp_txt = f"<b style='color:#107c41;'>{trans.get('kick_ramp_used', 'auto')}</b>"
        
        # Grid checks across outputs
        grid_findings = []
        for out in trans.get("outputs", []):
            ig = out.get("inpaint_grid")
            if ig and not ig.get("ok", True):
                grid_findings.append(f"{out.get('drums')}: {ig.get('kicks_in_span')} kicks in span (exp {ig.get('expected_kicks')})")
        if grid_findings:
            grid_txt = "<b style='color:#d83b01;'>⚠️ Jitter/Drift</b><br><small>" + "<br>".join(set(grid_findings)) + "</small>"
        else:
            grid_txt = "<span style='color:#107c41;'>✓ On-Grid</span>"

        doc += f"""<tr>
  <td><b>#{t_idx}</b></td>
  <td><span class="clip-badge">{cA_short}</span> &rarr;<br><span class="clip-badge">{cB_short}</span></td>
  <td>{tempo_txt}</td>
  <td>{phase_txt}</td>
  <td>{drift_txt}</td>
  <td>{ramp_txt}</td>
  <td>{grid_txt}</td>
</tr>"""
    doc += """</table>

<div id="xport">
  <div class="xport-top">
    <button id="xpp" title="Play / Pause (Space)">&#9208;</button>
    <button id="xloop" class="on" title="Toggle Loop (L)">&#128257; Loop: ON</button>
    <div style="display:flex; flex-direction:column; min-width:220px;">
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
"""
    for v_idx, (v_key, label, desc, _) in enumerate(VARIANTS):
        num_key = (v_idx + 1) % 10
        doc += f"  {{ idx: {v_idx}, numKey: '{num_key}', key: '{v_key}', label: '{html.escape(label.split('. ')[-1])}' }},\n"

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
let isDraggingSeek = false;

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
  const colName = targetCell.dataset.colName || 'Variant';
  
  document.getElementById('xnp').textContent = phraseTitle;
  document.getElementById('xcol').textContent = colName;
  document.getElementById('xdl').href = targetCell.dataset.src;
  document.getElementById('xdl').setAttribute('download', targetCell.dataset.src.split('/').pop());

  // Try Web Audio loading
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
      
      // Solo selected column
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
    // Fallback for file:// CORS block
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
    rowDuration = (rowId === 'fullmix') ? 146.3 : 14.1;
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
      togglePlay();
      return;
    } else {
      flipToCol(colIdx);
      return;
    }
  }
  
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
    pill.innerHTML = `<kbd>${def.numKey}</kbd> ${def.label}`;
    pill.onclick = () => flipToCol(def.idx);
    container.appendChild(pill);
  });
}

function fmtTime(s) {
  s = Math.max(0, s | 0);
  return (s / 60 | 0) + ':' + String(s % 60).padStart(2, '0');
}

// Animation loop
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

// Keyboard shortcuts
window.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  
  if (e.code === 'Space') {
    e.preventDefault();
    togglePlay();
  } else if (e.key >= '1' && e.key <= '9') {
    const colTarget = parseInt(e.key, 10) - 1;
    if (activeRow) flipToCol(colTarget);
  } else if (e.key === '0') {
    if (activeRow) flipToCol(9);
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
        page_path = out_base / "v7_smoke_mix.html"
        page_path.write_text(doc)
        print(f"Wrote {page_path}")


if __name__ == "__main__":
    build_page()
