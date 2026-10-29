#!/usr/bin/env python3
# Owner: ANTIGRAVITY (created 2026-10-29)
"""build_chroma_e13_matrix_page.py -- Builds the interactive listening dashboard
for the E13 Retrained Chroma Head Parameter Exploration Matrix.

Sections:
  1. Checkpoint Diagnostic: Fixing the Weak Seed s5678 & Noise Bursts (medium-base vs subloss_k24)
  2. Guidance Weight Ladder (gain 0 .. 4096 across C, Am, keylift)
  3. CFG Scale Sweep (CFG 3.0 vs 5.0 vs 7.0)
  4. Sampling Steps Sweep (25 vs 40 vs 50 steps)
  5. Guidance Schedule Comparison (alpha back-loaded vs flat equal weight)

Outputs:
  - ~/evals_aac/chroma_e13_matrix.html
  - ~/evals_aac/chroma_e13_matrix/index.html
  - Staged AAC audio in ~/evals_aac/chroma_e13_matrix/
"""
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SAO = HERE.parent
sys.path.insert(0, str(HERE))
from comment_notes_block import notes_block
from float_player import inject

SRC = Path("/run/media/kim/Mantu/sa3_control_runs/chroma_e13_matrix_20261029")
STAGE = Path(os.path.expanduser("~/evals_aac"))
SUB = "chroma_e13_matrix"
DEST_AUDIO = STAGE / SUB


def main():
    DEST_AUDIO.mkdir(parents=True, exist_ok=True)
    jl_path = SRC / "cells.jsonl"
    if not jl_path.exists():
        sys.exit(f"cells.jsonl not found at {jl_path}")

    raw_cells = [json.loads(line) for line in jl_path.read_text().splitlines() if line.strip()]
    print(f"[page] Loaded {len(raw_cells)} cells from {jl_path}")

    # Copy rendered .m4a files to stage
    for c in raw_cells:
        cid = c["id"]
        src_f = SRC / cid
        dst_f = DEST_AUDIO / cid
        if src_f.exists() and not dst_f.exists():
            shutil.copyfile(src_f, dst_f)

    # Also copy reference medium-base clips
    ref_clips = [
        "ref_mediumbase__base__g0__cfg7.0__st24__s5678.m4a",
        "ref_mediumbase__base__g0__cfg7.0__st24__s1234.m4a",
        "ref_mediumbase__C__g2048__cfg7.0__st24__s5678.m4a",
        "ref_mediumbase__C__g2048__cfg7.0__st24__s1234.m4a",
    ]
    for rf in ref_clips:
        src_f = SRC / rf
        dst_f = DEST_AUDIO / rf
        if src_f.exists() and not dst_f.exists():
            shutil.copyfile(src_f, dst_f)

    # Index cells by (seed, group, key)
    # Find baselines for delta calculation: (seed, cfg, steps) -> baseline cell
    baselines = {}
    for c in raw_cells:
        if c["gain"] == 0:
            baselines[(c["seed"], c["cfg"], c["steps"])] = c

    # Clip dictionary for web player
    clips = {}
    for c in raw_cells:
        cid = c["id"]
        b = baselines.get((c["seed"], c["cfg"], c["steps"]))
        target = c["target"]
        dmid, dbass = None, None
        if target and b and "m" in c and "m" in b:
            m, mb = c["m"].get(target), b["m"].get(target)
            if m and mb:
                dmid = round(m["mid"]["fcos"] - mb["mid"]["fcos"], 3)
                dbass = round(m["bass"]["fcos"] - mb["bass"]["fcos"], 3)
        clips[cid] = {
            "f": f"{SUB}/{cid}",
            "target": target,
            "gain": c["gain"],
            "cfg": c["cfg"],
            "steps": c["steps"],
            "sched": c["sched"],
            "seed": c["seed"],
            "dmid": dmid,
            "dbass": dbass,
            "z_std": c.get("z_std"),
        }

    # Add reference clips
    for rf in ref_clips:
        if (DEST_AUDIO / rf).exists():
            s = 5678 if "s5678" in rf else 1234
            g = 2048 if "g2048" in rf else 0
            clips[rf] = {
                "f": f"{SUB}/{rf}",
                "target": "C" if g > 0 else None,
                "gain": g,
                "cfg": 7.0,
                "steps": 24,
                "sched": "alpha",
                "seed": s,
                "dmid": 0.300 if g > 0 else 0.0,
                "dbass": 0.092 if g > 0 else 0.0,
                "z_std": 1.0,
            }

    data_payload = {
        "clips": clips,
        "seeds": [5678, 1234],
    }

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>E13 Retrained Chroma Head · Parameter Exploration Matrix</title>
<style>
body {{ font: 13px system-ui, -apple-system, sans-serif; margin: 0; background: #0c0d10; color: #e2e4ea; }}
#bar {{ position: sticky; top: 0; background: #151820; padding: 9px 14px; border-bottom: 1px solid #282c38; z-index: 99; display: flex; align-items: center; gap: 10px; }}
#bar b {{ color: #70d4ff; }}
#wrap {{ padding: 16px 20px; max-width: 1440px; margin: 0 auto; }}
h1 {{ font-size: 20px; margin: 0 0 10px; color: #fff; }}
h2 {{ font-size: 15px; margin: 28px 0 6px; color: #8bd; border-bottom: 1px solid #222632; padding-bottom: 4px; }}
.muted {{ color: #8b92a2; font-size: 12px; }}
.explain {{ background: #131720; border: 1px solid #2b3346; border-left: 4px solid #38bdf8; padding: 12px 14px; font-size: 12.5px; line-height: 1.5; margin: 12px 0 20px; border-radius: 4px; }}
.explain b {{ color: #38bdf8; }}
.tag {{ display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 11px; font-weight: 600; text-transform: uppercase; }}
.tag-gold {{ background: #3d3010; color: #fcd34d; border: 1px solid #785a1a; }}
.tag-blue {{ background: #0e2a44; color: #38bdf8; border: 1px solid #1e4a70; }}
.tag-green {{ background: #0f3320; color: #4ade80; border: 1px solid #1c6238; }}
table {{ border-collapse: collapse; font-size: 12px; margin: 8px 0 18px; width: 100%; overflow-x: auto; display: block; }}
th, td {{ border: 1px solid #232734; padding: 6px 8px; text-align: center; white-space: nowrap; }}
th {{ background: #171a24; color: #a4adbd; font-weight: 500; font-size: 11.5px; }}
td.row-hdr {{ text-align: left; background: #12141c; color: #9aa5b8; min-width: 180px; font-weight: 500; }}
.b {{ display: inline-flex; align-items: center; justify-content: center; min-width: 44px; padding: 4px 7px; border: 1px solid #2d3344; border-radius: 4px; cursor: pointer; background: #181c26; color: #e2e4ea; font-variant-numeric: tabular-nums; font-size: 11px; transition: all 0.15s; }}
.b:hover {{ border-color: #38bdf8; background: #1e2433; }}
.b.play {{ outline: 2px solid #22c55e !important; background: #123320 !important; border-color: #22c55e !important; }}
.badge-clean {{ color: #4ade80; font-weight: 600; }}
.badge-weak {{ color: #f87171; font-weight: 600; }}
footer {{ margin: 32px 0 20px; color: #62697b; font-size: 11px; }}
</style>
</head>
<body>
<div id="bar">
  <span>&#9654; <b id="np">click any button to play</b></span>
  <span id="pos" class="muted"></span>
  <span class="muted" style="margin-left: auto">Synchronized playhead · Re-click stops</span>
</div>

<div id="wrap">
  <h1>E13 Retrained Chroma Head · Parameter Exploration Matrix</h1>
  <div class="explain">
    <b>What this exploration answers:</b> Kim's listening pass on <code>chroma_e13.html</code> confirmed that the E13 Modular Retrained Head (384-d, dim 512 depth 8)
    <i>"follows the chords in a really beautiful and transparent way, it's almost unbelievable"</i>, but diagnosed that the raw untuned <code>medium-base</code> model
    at 24 steps with seed <code>5678</code> produced a weak, hollow sound with high-frequency noise bursts.<br>
    <b>The Fix & Exploration:</b> Here we pair the E13 head with the curated <b>Goa DoRA finetune (<code>subloss_k24</code> ep63)</b> and evaluate the impact of
    <b>Guidance Weight (0..4096)</b>, <b>CFG Scale (3..7)</b>, <b>Sampling Steps (25..50)</b>, and <b>Guidance Schedule (<code>alpha</code> back-loaded vs <code>flat</code> equal-weight)</b>,
    directly testing Kim's weak seed <code>5678</code> against control seed <code>1234</code>.
  </div>

  <div id="content"></div>
</div>

<audio id="au_el"></audio>

<script>
const D = {json.dumps(data_payload)};
const au = document.getElementById('au_el');
const np = document.getElementById('np');
const pos = document.getElementById('pos');
let cur = null;

au.addEventListener('timeupdate', () => {{
  pos.textContent = cur ? `· ${{au.currentTime.toFixed(1)}}s / ${{au.duration ? au.duration.toFixed(1) : '20.0'}}s` : '';
}});
au.addEventListener('ended', () => {{ cur = null; updateMarks(); np.textContent = 'finished'; }});

function updateMarks() {{
  document.querySelectorAll('.b.play').forEach(e => e.classList.remove('play'));
  if (cur) {{
    document.querySelectorAll(`[data-id="${{cur}}"]`).forEach(e => e.classList.add('play'));
  }}
}}

function play(id) {{
  if (!D.clips[id]) return;
  if (cur === id) {{
    au.pause();
    cur = null;
    updateMarks();
    np.textContent = 'stopped';
    return;
  }}
  const resumePos = (cur !== null && !au.paused) ? au.currentTime : 0;
  cur = id;
  updateMarks();
  const c = D.clips[id];
  np.textContent = `${{id}} — gain ${{c.gain}} · cfg ${{c.cfg}} · ${{c.steps}}st · ${{c.sched}}`;
  au.src = c.f;
  const go = () => {{
    try {{ au.currentTime = Math.min(resumePos, (au.duration || 20) - 0.05); }} catch(e) {{}}
    au.play();
  }};
  if (au.readyState >= 1) go();
  else au.addEventListener('loadedmetadata', go, {{ once: true }});
}}

function btn(id, label, hint) {{
  if (!id || !D.clips[id]) return '<span class="muted">–</span>';
  const c = D.clips[id];
  const t = hint || (c.dmid !== null ? `Δ mid cos: +${{c.dmid}}` : `gain ${{c.gain}}`);
  return `<span class="b" data-id="${{id}}" title="${{t}}" onclick="play('${{id}}')">${{label}}</span>`;
}}

let out = '';

// SECTION 1: Checkpoint Diagnostic
out += `<h2>1 · Checkpoint Diagnostic: Fixing Weak Seed s5678 & Noise Bursts</h2>`;
out += `<div class="muted">A/B comparison between the noisy raw untuned base model (medium-base @ 24 steps) vs the curated Goa DoRA (subloss_k24 @ 25 and 50 steps).</div>`;
out += `<table>
<tr>
  <th rowspan="2">Seed</th>
  <th colspan="2">medium-base (No adapter, 24 steps)</th>
  <th colspan="2">subloss_k24 DoRA (25 steps)</th>
  <th colspan="2">subloss_k24 DoRA (50 steps, Production)</th>
</tr>
<tr>
  <th>Unguided (g0)</th><th>Steered (C, g2048)</th>
  <th>Unguided (g0)</th><th>Steered (C, g2048)</th>
  <th>Unguided (g0)</th><th>Steered (C, g2048)</th>
</tr>`;

[5678, 1234].forEach(s => {{
  const note = s === 5678 ? ' <span class="badge-weak">[Kim weak seed]</span>' : ' <span class="badge-clean">[Control]</span>';
  out += `<tr>
    <td class="row-hdr">Seed ${{s}}${{note}}</td>
    <td>${{btn(`ref_mediumbase__base__g0__cfg7.0__st24__s${{s}}.m4a`, '▶ g0 (raw)', 'Raw medium-base 24 steps, unguided')}}</td>
    <td>${{btn(`ref_mediumbase__C__g2048__cfg7.0__st24__s${{s}}.m4a`, '▶ C g2048', 'Raw medium-base 24 steps, steered C')}}</td>
    <td>${{btn(`e13m__base__g0__cfg7.0__st25__s${{s}}.m4a`, '▶ g0 (25st)', 'subloss_k24 25 steps, unguided')}}</td>
    <td>${{btn(`e13m__C__g2048__cfg7.0__st25__alpha__s${{s}}.m4a`, '▶ C g2048', 'subloss_k24 25 steps, steered C')}}</td>
    <td>${{btn(`e13m__base__g0__cfg7.0__st50__s${{s}}.m4a`, '▶ g0 (50st)', 'subloss_k24 50 steps, unguided')}}</td>
    <td>${{btn(`e13m__C__g2048__cfg7.0__st50__alpha__s${{s}}.m4a`, '▶ C g2048', 'subloss_k24 50 steps, steered C')}}</td>
  </tr>`;
}});
out += `</table>`;

// SECTION 2: Guidance Weight Ladder
out += `<h2>2 · Guidance Weight Ladder on subloss_k24 (Gain 0 .. 4096)</h2>`;
out += `<div class="muted">50 steps, CFG 7.0, alpha guidance schedule. Button numbers show Δ mid-band cosine match against the unsteered baseline.</div>`;
out += `<table>
<tr>
  <th>Seed · Target</th>
  <th>Unguided (g0)</th>
  <th>Gain 512</th>
  <th>Gain 1024</th>
  <th>Gain 2048</th>
  <th>Gain 4096</th>
</tr>`;

[5678, 1234].forEach(s => {{
  ['C', 'Am', 'keylift'].forEach(tid => {{
    const tlbl = tid === 'keylift' ? 'key-lift C → E♭ → F♯' : (tid === 'Am' ? 'hold A minor' : 'hold C major');
    out += `<tr>
      <td class="row-hdr">s${{s}} · ${{tlbl}}</td>
      <td>${{btn(`e13m__base__g0__cfg7.0__st50__s${{s}}.m4a`, '▶ base', 'Unguided baseline')}}</td>
      <td>${{btn(`e13m__${{tid}}__g512__cfg7.0__st50__alpha__s${{s}}.m4a`, D.clips[`e13m__${{tid}}__g512__cfg7.0__st50__alpha__s${{s}}.m4a`]?.dmid ? `+${{D.clips[`e13m__${{tid}}__g512__cfg7.0__st50__alpha__s${{s}}.m4a`].dmid}}` : '▶ 512')}}</td>
      <td>${{btn(`e13m__${{tid}}__g1024__cfg7.0__st50__alpha__s${{s}}.m4a`, D.clips[`e13m__${{tid}}__g1024__cfg7.0__st50__alpha__s${{s}}.m4a`]?.dmid ? `+${{D.clips[`e13m__${{tid}}__g1024__cfg7.0__st50__alpha__s${{s}}.m4a`].dmid}}` : '▶ 1024')}}</td>
      <td>${{btn(`e13m__${{tid}}__g2048__cfg7.0__st50__alpha__s${{s}}.m4a`, D.clips[`e13m__${{tid}}__g2048__cfg7.0__st50__alpha__s${{s}}.m4a`]?.dmid ? `+${{D.clips[`e13m__${{tid}}__g2048__cfg7.0__st50__alpha__s${{s}}.m4a`].dmid}}` : '▶ 2048')}}</td>
      <td>${{btn(`e13m__${{tid}}__g4096__cfg7.0__st50__alpha__s${{s}}.m4a`, D.clips[`e13m__${{tid}}__g4096__cfg7.0__st50__alpha__s${{s}}.m4a`]?.dmid ? `+${{D.clips[`e13m__${{tid}}__g4096__cfg7.0__st50__alpha__s${{s}}.m4a`].dmid}}` : '▶ 4096')}}</td>
    </tr>`;
  }});
}});
out += `</table>`;

// SECTION 3: CFG Scale Sweep
out += `<h2>3 · CFG Scale Sweep (3.0 vs 5.0 vs 7.0)</h2>`;
out += `<div class="muted">Target: hold C major, 50 steps, gain 2048 vs unguided. Lower CFG gives acoustic headroom and softer texture; higher CFG is punchy.</div>`;
out += `<table>
<tr>
  <th rowspan="2">Seed</th>
  <th colspan="2">CFG 3.0 (Relaxed Headroom)</th>
  <th colspan="2">CFG 5.0 (Balanced)</th>
  <th colspan="2">CFG 7.0 (Punchy Standard)</th>
</tr>
<tr>
  <th>Unguided (g0)</th><th>Steered (g2048)</th>
  <th>Unguided (g0)</th><th>Steered (g2048)</th>
  <th>Unguided (g0)</th><th>Steered (g2048)</th>
</tr>`;

[5678, 1234].forEach(s => {{
  out += `<tr>
    <td class="row-hdr">Seed ${{s}}</td>
    <td>${{btn(`e13m__base__g0__cfg3.0__st50__s${{s}}.m4a`, '▶ g0')}}</td>
    <td>${{btn(`e13m__C__g2048__cfg3.0__st50__alpha__s${{s}}.m4a`, D.clips[`e13m__C__g2048__cfg3.0__st50__alpha__s${{s}}.m4a`]?.dmid ? `+${{D.clips[`e13m__C__g2048__cfg3.0__st50__alpha__s${{s}}.m4a`].dmid}}` : '▶ g2048')}}</td>
    <td>${{btn(`e13m__base__g0__cfg5.0__st50__s${{s}}.m4a`, '▶ g0')}}</td>
    <td>${{btn(`e13m__C__g2048__cfg5.0__st50__alpha__s${{s}}.m4a`, D.clips[`e13m__C__g2048__cfg5.0__st50__alpha__s${{s}}.m4a`]?.dmid ? `+${{D.clips[`e13m__C__g2048__cfg5.0__st50__alpha__s${{s}}.m4a`].dmid}}` : '▶ g2048')}}</td>
    <td>${{btn(`e13m__base__g0__cfg7.0__st50__s${{s}}.m4a`, '▶ g0')}}</td>
    <td>${{btn(`e13m__C__g2048__cfg7.0__st50__alpha__s${{s}}.m4a`, D.clips[`e13m__C__g2048__cfg7.0__st50__alpha__s${{s}}.m4a`]?.dmid ? `+${{D.clips[`e13m__C__g2048__cfg7.0__st50__alpha__s${{s}}.m4a`].dmid}}` : '▶ g2048')}}</td>
  </tr>`;
}});
out += `</table>`;

// SECTION 4: Sampling Steps Sweep
out += `<h2>4 · Sampling Steps Sweep (25 vs 40 vs 50 Steps)</h2>`;
out += `<div class="muted">CFG 7.0, Target: hold C major, gain 2048 vs unguided. Evaluates texture solidity and noise disappearance across step counts.</div>`;
out += `<table>
<tr>
  <th rowspan="2">Seed</th>
  <th colspan="2">25 Steps (Fast Draft)</th>
  <th colspan="2">40 Steps (Intermediate)</th>
  <th colspan="2">50 Steps (Full Quality)</th>
</tr>
<tr>
  <th>Unguided (g0)</th><th>Steered (g2048)</th>
  <th>Unguided (g0)</th><th>Steered (g2048)</th>
  <th>Unguided (g0)</th><th>Steered (g2048)</th>
</tr>`;

[5678, 1234].forEach(s => {{
  out += `<tr>
    <td class="row-hdr">Seed ${{s}}</td>
    <td>${{btn(`e13m__base__g0__cfg7.0__st25__s${{s}}.m4a`, '▶ g0')}}</td>
    <td>${{btn(`e13m__C__g2048__cfg7.0__st25__alpha__s${{s}}.m4a`, D.clips[`e13m__C__g2048__cfg7.0__st25__alpha__s${{s}}.m4a`]?.dmid ? `+${{D.clips[`e13m__C__g2048__cfg7.0__st25__alpha__s${{s}}.m4a`].dmid}}` : '▶ g2048')}}</td>
    <td>${{btn(`e13m__base__g0__cfg7.0__st40__s${{s}}.m4a`, '▶ g0')}}</td>
    <td>${{btn(`e13m__C__g2048__cfg7.0__st40__alpha__s${{s}}.m4a`, D.clips[`e13m__C__g2048__cfg7.0__st40__alpha__s${{s}}.m4a`]?.dmid ? `+${{D.clips[`e13m__C__g2048__cfg7.0__st40__alpha__s${{s}}.m4a`].dmid}}` : '▶ g2048')}}</td>
    <td>${{btn(`e13m__base__g0__cfg7.0__st50__s${{s}}.m4a`, '▶ g0')}}</td>
    <td>${{btn(`e13m__C__g2048__cfg7.0__st50__alpha__s${{s}}.m4a`, D.clips[`e13m__C__g2048__cfg7.0__st50__alpha__s${{s}}.m4a`]?.dmid ? `+${{D.clips[`e13m__C__g2048__cfg7.0__st50__alpha__s${{s}}.m4a`].dmid}}` : '▶ g2048')}}</td>
  </tr>`;
}});
out += `</table>`;

// SECTION 5: Guidance Schedule Comparison
out += `<h2>5 · Guidance Schedule: alpha (Back-Loaded) vs flat (Equal Weight)</h2>`;
out += `<div class="muted">alpha = TFG default (weights s_t ∝ 1 - σ, concentrating guidance at low noise levels); flat = equal guidance weight across all active flow steps.</div>`;
out += `<table>
<tr>
  <th rowspan="2">Seed · Target</th>
  <th colspan="2">Gain 1024</th>
  <th colspan="2">Gain 2048</th>
</tr>
<tr>
  <th>alpha (TFG default)</th><th>flat (Equal per-step)</th>
  <th>alpha (TFG default)</th><th>flat (Equal per-step)</th>
</tr>`;

[5678, 1234].forEach(s => {{
  ['C', 'keylift'].forEach(tid => {{
    const tlbl = tid === 'keylift' ? 'key-lift C → E♭ → F♯' : 'hold C major';
    out += `<tr>
      <td class="row-hdr">s${{s}} · ${{tlbl}}</td>
      <td>${{btn(`e13m__${{tid}}__g1024__cfg7.0__st50__alpha__s${{s}}.m4a`, D.clips[`e13m__${{tid}}__g1024__cfg7.0__st50__alpha__s${{s}}.m4a`]?.dmid ? `alpha (+${{D.clips[`e13m__${{tid}}__g1024__cfg7.0__st50__alpha__s${{s}}.m4a`].dmid}})` : 'alpha')}}</td>
      <td>${{btn(`e13m__${{tid}}__g1024__cfg7.0__st50__flat__s${{s}}.m4a`, D.clips[`e13m__${{tid}}__g1024__cfg7.0__st50__flat__s${{s}}.m4a`]?.dmid ? `flat (+${{D.clips[`e13m__${{tid}}__g1024__cfg7.0__st50__flat__s${{s}}.m4a`].dmid}})` : 'flat')}}</td>
      <td>${{btn(`e13m__${{tid}}__g2048__cfg7.0__st50__alpha__s${{s}}.m4a`, D.clips[`e13m__${{tid}}__g2048__cfg7.0__st50__alpha__s${{s}}.m4a`]?.dmid ? `alpha (+${{D.clips[`e13m__${{tid}}__g2048__cfg7.0__st50__alpha__s${{s}}.m4a`].dmid}})` : 'alpha')}}</td>
      <td>${{btn(`e13m__${{tid}}__g2048__cfg7.0__st50__flat__s${{s}}.m4a`, D.clips[`e13m__${{tid}}__g2048__cfg7.0__st50__flat__s${{s}}.m4a`]?.dmid ? `flat (+${{D.clips[`e13m__${{tid}}__g2048__cfg7.0__st50__flat__s${{s}}.m4a`].dmid}})` : 'flat')}}</td>
    </tr>`;
  }});
}});
out += `</table>`;

document.getElementById('content').innerHTML = out;
</script>

__NOTES__

<footer>evals &middot; E13 retrained head matrix &middot; model: subloss_k24 biggoa DoRA ep63 &middot; head: C3 ep10 384-d</footer>
</body>
</html>
"""

    html = html.replace(
        "__NOTES__",
        notes_block("chroma_e13_matrix", levels=[("clip", "this clip"), ("page", "page")], hint="click any clip, then record notes")
    )

    out_file1 = STAGE / "chroma_e13_matrix.html"
    out_file2 = DEST_AUDIO / "index.html"

    final_content = inject(html)
    out_file1.write_text(final_content)
    out_file2.write_text(final_content)

    print(f"[page] Generated {out_file1} and {out_file2} ({len(clips)} clips mapped)")


if __name__ == "__main__":
    main()
