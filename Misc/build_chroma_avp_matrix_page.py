#!/usr/bin/env python3
# Owner: ANTIGRAVITY (created 2026-10-29)
"""build_chroma_avp_matrix_page.py -- Builds the interactive listening dashboard
comparing the retrained 384-d SAME-chroma head on the AVP augmented dataset against
the Goa-trained E13 baseline and combined Goa+AVP head.

Sections:
  1. Progression Tracking: Am -> F -> C -> G (4-chord harmonic turn)
  2. Static Harmonic Anchors: Hold C Major vs Hold A Minor
  3. Modulating Keylift: C -> Eb -> F# (rising minor-thirds)
  4. Prompt Sensitivity: Melodic Goa vs Suomisoundi Psytrance

Outputs:
  - ~/evals_aac/chroma_avp_matrix.html
  - ~/evals_aac/chroma_avp_matrix/index.html
  - Staged AAC audio in ~/evals_aac/chroma_avp_matrix/
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

SRC = Path("/run/media/kim/Mantu/sa3_control_runs/chroma_avp_matrix_20261029")
STAGE = Path(os.path.expanduser("~/evals_aac"))
SUB = "chroma_avp_matrix"
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
        fn = c["fn"]
        src_f = SRC / fn
        dst_f = DEST_AUDIO / fn
        if src_f.exists() and not dst_f.exists():
            shutil.copyfile(src_f, dst_f)

    # Index baselines: (prompt_id, seed) -> cell
    baselines = {}
    for c in raw_cells:
        if c["gain"] == 0 or c["head"] == "base":
            baselines[(c["prompt_id"], c["seed"])] = c

    # Index cells: (head, target, gain, prompt_id, seed) -> cell
    by_key = {}
    for c in raw_cells:
        k = (c["head"], c["target"], c["gain"], c["prompt_id"], c["seed"])
        by_key[k] = c

    # Build web clips dictionary
    clips = {}
    for c in raw_cells:
        fn = c["fn"]
        b = baselines.get((c["prompt_id"], c["seed"]))
        target = c["target"]
        dmid, dbass = None, None
        if target and b:
            m = c.get("fcos_mid")
            mb = b.get("measured_all", {}).get(target, {}).get("mid", {}).get("fcos", 0.0)
            if m is not None and mb is not None:
                dmid = round(m - mb, 3)
            m_b = c.get("fcos_bass")
            mb_b = b.get("measured_all", {}).get(target, {}).get("bass", {}).get("fcos", 0.0)
            if m_b is not None and mb_b is not None:
                dbass = round(m_b - mb_b, 3)

        clips[fn] = {
            "f": f"{SUB}/{fn}",
            "head": c["head"],
            "target": target,
            "gain": c["gain"],
            "pid": c["prompt_id"],
            "seed": c["seed"],
            "fcos_mid": c.get("fcos_mid"),
            "fcos_bass": c.get("fcos_bass"),
            "hit_mid": c.get("hit_mid"),
            "hit_bass": c.get("hit_bass"),
            "dmid": dmid,
            "dbass": dbass,
            "z_std": c.get("z_std"),
        }

    # Helper to render a cell button
    def render_btn(head, tid, gain, pid, seed, label=""):
        k = (head, tid, gain, pid, seed)
        cell = by_key.get(k)
        if not cell:
            return '<span class="cell cell-missing">—</span>'
        fn = cell["fn"]
        meta = clips[fn]
        dmid = meta.get("dmid")
        hit = meta.get("hit_mid")
        badge = ""
        if dmid is not None and hit is not None:
            badge = f'<div class="cell-sub">Δm:{dmid:+.2f} hit:{hit:.2f}</div>'
        elif cell["gain"] == 0:
            badge = '<div class="cell-sub">base</div>'

        disp = label if label else (f"g{gain}" if gain > 0 else "unguided")
        return f'''<button class="cell play-btn" data-clip="{fn}" data-sub="{SUB}" onclick="play('{fn}')">
            <div class="cell-title">{disp}</div>
            {badge}
        </button>'''

    # Build sections
    pids = [("goa", "Melodic Goa Trance"), ("suomi", "Suomisoundi Psytrance")]
    seeds = [5678, 1234]

    # Section 1: Progression i-VI-III-VII (Am-F-C-G)
    rows_s1 = []
    for pid, ptitle in pids:
        for s in seeds:
            base_btn = render_btn("base", "", 0, pid, s, "Base (g0)")
            goa_512 = render_btn("goa_e13", "i-VI-III-VII", 512, pid, s, "Goa (g512)")
            goa_2048 = render_btn("goa_e13", "i-VI-III-VII", 2048, pid, s, "Goa (g2048)")
            avp_512 = render_btn("avp_aug", "i-VI-III-VII", 512, pid, s, "AVP (g512)")
            avp_2048 = render_btn("avp_aug", "i-VI-III-VII", 2048, pid, s, "AVP (g2048)")
            comb_512 = render_btn("goa_avp", "i-VI-III-VII", 512, pid, s, "Comb (g512)")
            comb_2048 = render_btn("goa_avp", "i-VI-III-VII", 2048, pid, s, "Comb (g2048)")

            rows_s1.append(f'''<tr>
                <td class="p-cell"><strong>{ptitle}</strong><br><span class="meta">seed {s}</span></td>
                <td>{base_btn}</td>
                <td><div class="pair-cell">{goa_512}{goa_2048}</div></td>
                <td><div class="pair-cell">{avp_512}{avp_2048}</div></td>
                <td><div class="pair-cell">{comb_512}{comb_2048}</div></td>
            </tr>''')

    # Section 2: Static Keys (C major vs Am minor)
    rows_s2 = []
    for pid, ptitle in pids:
        for s in seeds:
            base_btn = render_btn("base", "", 0, pid, s, "Base (g0)")
            c_goa = render_btn("goa_e13", "C", 2048, pid, s, "Goa (C)")
            c_avp = render_btn("avp_aug", "C", 2048, pid, s, "AVP (C)")
            c_comb = render_btn("goa_avp", "C", 2048, pid, s, "Comb (C)")

            am_goa = render_btn("goa_e13", "Am", 2048, pid, s, "Goa (Am)")
            am_avp = render_btn("avp_aug", "Am", 2048, pid, s, "AVP (Am)")
            am_comb = render_btn("goa_avp", "Am", 2048, pid, s, "Comb (Am)")

            rows_s2.append(f'''<tr>
                <td class="p-cell"><strong>{ptitle}</strong><br><span class="meta">seed {s}</span></td>
                <td>{base_btn}</td>
                <td><div class="triple-cell">{c_goa}{c_avp}{c_comb}</div></td>
                <td><div class="triple-cell">{am_goa}{am_avp}{am_comb}</div></td>
            </tr>''')

    # Section 3: Modulating Keylift (C -> Eb -> F#)
    rows_s3 = []
    for pid, ptitle in pids:
        for s in seeds:
            base_btn = render_btn("base", "", 0, pid, s, "Base (g0)")
            kl_goa = render_btn("goa_e13", "keylift", 2048, pid, s, "Goa C3 (g2048)")
            kl_avp = render_btn("avp_aug", "keylift", 2048, pid, s, "AVP Aug (g2048)")
            kl_comb = render_btn("goa_avp", "keylift", 2048, pid, s, "Goa+AVP Comb (g2048)")

            rows_s3.append(f'''<tr>
                <td class="p-cell"><strong>{ptitle}</strong><br><span class="meta">seed {s}</span></td>
                <td>{base_btn}</td>
                <td>{kl_goa}</td>
                <td>{kl_avp}</td>
                <td>{kl_comb}</td>
            </tr>''')

    # Section 0: gain ladder (built from the gains present in the data)
    HEAD_LABEL = {"goa_e13": "Goa E13", "avp_aug": "AVP only", "goa_avp": "Goa+AVP"}
    TGT_LABEL = {"i-VI-III-VII": "Am → F → C → G", "C": "C major", "keylift": "C → Eb → F#", "Am": "A minor"}
    ladder_gains = sorted({c["gain"] for c in raw_cells if c["gain"] > 0})
    ladder_html = []
    for tid in ["i-VI-III-VII", "C", "keylift"]:
        if not any(c["target"] == tid and c["gain"] > 2048 for c in raw_cells):
            continue
        rows = []
        for pid, ptitle in pids:
            for s in seeds:
                for hi, hid in enumerate(HEAD_LABEL):
                    cells_html = "".join(
                        f"<td>{render_btn(hid, tid, g, pid, s, f'g{g}')}</td>" for g in ladder_gains)
                    first = (f'<td class="p-cell" rowspan="3"><strong>{ptitle}</strong><br>'
                             f'<span class="meta">seed {s}</span></td>'
                             f'<td rowspan="3">{render_btn("base", "", 0, pid, s, "Base (g0)")}</td>') if hi == 0 else ""
                    rows.append(f'<tr>{first}<td><strong>{HEAD_LABEL[hid]}</strong></td>{cells_html}</tr>')
        head_cols = "".join(f"<th>g{g}</th>" for g in ladder_gains)
        ladder_html.append(f'''<h3 style="margin:18px 0 8px">{TGT_LABEL[tid]}</h3>
    <table class="matrix"><thead><tr><th>Prompt &amp; Seed</th><th>Unguided</th><th>Head</th>{head_cols}</tr></thead>
    <tbody>{"".join(rows)}</tbody></table>''')

    # Measured lift summary: mean Δ mid-band chroma cosine / Δ hit vs same-seed unguided
    lift_rows = []
    for hid in HEAD_LABEL:
        tds = []
        for g in ladder_gains:
            dm = [clips[c["fn"]]["dmid"] for c in raw_cells
                  if c["head"] == hid and c["gain"] == g and clips[c["fn"]]["dmid"] is not None]
            tds.append(f"<td>{sum(dm) / len(dm):+.3f} <span class='meta'>(n={len(dm)})</span></td>" if dm else "<td class='meta'>—</td>")
        lift_rows.append(f"<tr><td><strong>{HEAD_LABEL[hid]}</strong></td>{''.join(tds)}</tr>")
    lift_table = (f'<table class="matrix"><thead><tr><th>Head</th>'
                  f'{"".join(f"<th>g{g}</th>" for g in ladder_gains)}</tr></thead>'
                  f'<tbody>{"".join(lift_rows)}</tbody></table>')

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chroma Steering: Retrained Head on AVP Augmented Dataset</title>
<style>
:root {{
  --bg: #0d1117;
  --surface: #161b22;
  --surface-hover: #21262d;
  --border: #30363d;
  --text: #c9d1d9;
  --text-dim: #8b949e;
  --accent: #58a6ff;
  --accent-green: #3fb950;
  --accent-purple: #bc8cff;
  --accent-orange: #d29922;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  padding: 0 0 140px 0;
  line-height: 1.5;
}}
#bar {{
  position: sticky;
  top: 0;
  z-index: 1000;
  background: rgba(22, 27, 34, 0.96);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--border);
  padding: 10px 24px;
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 0.85rem;
  box-shadow: 0 4px 16px rgba(0,0,0,0.5);
}}
#bar_pp {{
  background: #21262d;
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--accent);
  cursor: pointer;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: all 0.15s ease;
}}
#bar_pp:hover {{ background: #30363d; border-color: var(--accent); }}
#np {{ color: #f0f6fc; font-family: monospace; font-size: 0.82rem; }}
.muted {{ color: var(--text-dim); }}
.bar-right {{ margin-left: auto; font-size: 0.78rem; color: var(--text-dim); }}

.wrap {{ max-width: 1300px; margin: 0 auto; padding: 24px 20px 0 20px; }}
a.back-nav {{ color: var(--accent); text-decoration: none; font-size: 0.9rem; margin-bottom: 12px; display: inline-block; }}
a.back-nav:hover {{ text-decoration: underline; }}
h1 {{ font-size: 1.8rem; font-weight: 600; margin-bottom: 8px; color: #f0f6fc; }}
p.lead {{ color: var(--text-dim); margin-bottom: 24px; font-size: 1rem; max-width: 950px; }}

.badge-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 24px; }}
.badge {{ background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 4px 10px; font-size: 0.8rem; color: var(--text-dim); }}
.badge strong {{ color: var(--text); }}
.badge.accent {{ border-color: rgba(88,166,255,0.4); background: rgba(88,166,255,0.08); color: var(--accent); }}

.section {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 28px; }}
.section h2 {{ font-size: 1.25rem; font-weight: 600; margin-bottom: 6px; color: #f0f6fc; }}
.section p.desc {{ color: var(--text-dim); font-size: 0.9rem; margin-bottom: 16px; }}

table.matrix {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 0.88rem; }}
table.matrix th {{ background: #1c2128; color: var(--text-dim); font-weight: 600; text-align: left; padding: 10px 12px; border: 1px solid var(--border); }}
table.matrix td {{ padding: 10px 12px; border: 1px solid var(--border); vertical-align: middle; }}
td.p-cell {{ width: 220px; }}
span.meta {{ font-size: 0.78rem; color: var(--text-dim); }}

.pair-cell {{ display: flex; gap: 8px; }}
.triple-cell {{ display: flex; gap: 8px; }}

button.cell {{
  background: #21262d;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  padding: 8px 12px;
  cursor: pointer;
  text-align: center;
  transition: all 0.15s ease;
  font-family: inherit;
  flex: 1;
  min-width: 95px;
}}
button.cell:hover {{
  background: #30363d;
  border-color: var(--accent);
  color: #fff;
}}
button.cell.active, button.cell.playing {{
  background: rgba(63, 185, 80, 0.22) !important;
  border-color: #3fb950 !important;
  color: #fff !important;
  box-shadow: 0 0 10px rgba(63, 185, 80, 0.4);
}}
.cell-title {{ font-size: 0.82rem; font-weight: 600; }}
.cell-sub {{ font-size: 0.72rem; color: var(--accent-green); margin-top: 2px; font-family: monospace; }}
.cell-missing {{ color: var(--text-dim); font-size: 0.8rem; display: inline-block; padding: 6px 12px; }}

.notes-card {{ margin-top: 32px; }}
</style>
</head>
<body>
<div id="bar">
  <button id="bar_pp" title="Play / Pause (Space)">&#9654;</button>
  <span style="font-size:12px;color:var(--text-dim)">&#9654; <b id="np">Click any cell to audition</b></span>
  <span id="pos" class="muted" style="font-size:12px"></span>
  <span class="bar-right muted">Synchronized playhead · Space: play/pause · Esc: stop</span>
</div>

<audio id="au_el" preload="auto"></audio>

<div class="wrap">
  <a href="index.html" class="back-nav">← Back to Master Catalog</a>
  <h1>Chroma Steering: Retrained Head on AVP Augmented Dataset</h1>
  <p class="lead">
    Investigating how training the 384-d SAME-chroma conditioning head on Kim's <strong>AVP augmented dataset</strong> (<code>latents_avp</code>, 2,393 crops) alters chord following accuracy, harmonic timbre, and prompt reactivity compared to the Goa-trained E13 baseline and combined Goa+AVP model.
  </p>

  <div class="badge-row">
    <div class="badge accent"><strong>Architecture:</strong> DiT Conditioning Head (dim=512, depth=8, heads=8)</div>
    <div class="badge"><strong>Optimizer:</strong> ModularOptimizer (SF, Shampoo, Muon, lr 1e-3, radial brake 0.8)</div>
    <div class="badge"><strong>Adapter:</strong> subloss_k24 Biggoa DoRA (epoch 63, str 1.0)</div>
    <div class="badge"><strong>Sampling:</strong> 50 Euler steps, CFG 7.0, alpha schedule</div>
    <div class="badge"><strong>Audio:</strong> 256 kbps AAC (SAME 44.1 kHz)</div>
  </div>

  <!-- SECTION 0 -->
  <div class="section">
    <h2>0. Gain Ladder: how hard each head actually steers</h2>
    <p class="desc">
      Same seed, same prompt, one head per row, gain rising left to right. At g512/g2048 the guidance is real but mild (and the AVP-only head pushes roughly half as hard per unit gain), so the higher rungs are where chord changes should become clearly audible. Table below: mean Δ mid-band chroma cosine vs the same-seed unguided clip, over all targets/prompts/seeds rendered at that gain.
      Every clip from g4096 up was decoded twice and checked for a matching result (guard against the GPU decode glitch that caused the 0:12 noise burst on the old Goa s5678 baseline, now replaced with a clean decode).
    </p>
    {lift_table}
    {"".join(ladder_html)}
  </div>

  <!-- SECTION 1 -->
  <div class="section">
    <h2>1. Progression Tracking: Am → F → C → G (Classic 4-Chord Turn)</h2>
    <p class="desc">
      Comparing how each head guides the generation across a dynamic chord sequence at the original two rungs (g512 mild, g2048 moderate).
    </p>
    <table class="matrix">
      <thead>
        <tr>
          <th>Prompt & Seed</th>
          <th>Unguided Base</th>
          <th>Goa-trained E13 Head</th>
          <th>AVP-trained Head</th>
          <th>Combined Goa+AVP Head</th>
        </tr>
      </thead>
      <tbody>
        {"".join(rows_s1)}
      </tbody>
    </table>
  </div>

  <!-- SECTION 2 -->
  <div class="section">
    <h2>2. Static Harmonic Anchors: C Major vs A Minor (Gain 2048)</h2>
    <p class="desc">
      Tests sustained tonal grounding in both major and minor keys. Audition whether the AVP corpus preserves richer melodic improvisations or locks tighter to the root triad.
    </p>
    <table class="matrix">
      <thead>
        <tr>
          <th>Prompt & Seed</th>
          <th>Unguided Base</th>
          <th>Hold C Major (Goa vs AVP vs Comb)</th>
          <th>Hold A Minor (Goa vs AVP vs Comb)</th>
        </tr>
      </thead>
      <tbody>
        {"".join(rows_s2)}
      </tbody>
    </table>
  </div>

  <!-- SECTION 3 -->
  <div class="section">
    <h2>3. Modulating Keylift: C → Eb → F# (Rising Minor-Thirds)</h2>
    <p class="desc">
      Tests chromatic transposition and modulating energy lift across distinct musical keys.
    </p>
    <table class="matrix">
      <thead>
        <tr>
          <th>Prompt & Seed</th>
          <th>Unguided Base</th>
          <th>Goa-trained Head (g2048)</th>
          <th>AVP-trained Head (g2048)</th>
          <th>Goa+AVP Combined (g2048)</th>
        </tr>
      </thead>
      <tbody>
        {"".join(rows_s3)}
      </tbody>
    </table>
  </div>

  <div class="notes-card">
    {notes_block("chroma_avp_matrix_20261029")}
  </div>
</div>

<script>
window.CLIPS_DATA = {json.dumps(clips)};

const au = document.getElementById('au_el');
const np = document.getElementById('np');
const pos = document.getElementById('pos');
const barPp = document.getElementById('bar_pp');
let curClip = null;

function resolveAudioSrc(fn) {{
  const p = window.location.pathname || '';
  if (p.endsWith('/chroma_avp_matrix/index.html') || p.endsWith('/chroma_avp_matrix/')) {{
    return fn;
  }}
  return '{SUB}/' + fn;
}}

function updateActiveMarks() {{
  document.querySelectorAll('button.cell').forEach(b => {{
    if (curClip && b.dataset.clip === curClip) {{
      b.classList.add('active', 'playing');
    }} else {{
      b.classList.remove('active', 'playing');
    }}
  }});
  if (barPp) {{
    barPp.innerHTML = (au && !au.paused) ? '&#9208;' : '&#9654;';
  }}
}}

au.addEventListener('timeupdate', () => {{
  if (!curClip) {{
    pos.textContent = '';
    return;
  }}
  const t = au.currentTime.toFixed(1);
  const d = (au.duration && isFinite(au.duration)) ? au.duration.toFixed(1) : '20.0';
  pos.textContent = `· ${{t}}s / ${{d}}s`;
}});

au.addEventListener('play', updateActiveMarks);
au.addEventListener('pause', updateActiveMarks);
au.addEventListener('ended', () => {{
  curClip = null;
  updateActiveMarks();
  np.textContent = 'finished';
  pos.textContent = '';
}});

function play(fn) {{
  const clip = window.CLIPS_DATA[fn];
  if (!clip) {{
    console.warn('Clip not found:', fn);
    return;
  }}
  if (curClip === fn) {{
    if (au.paused) {{
      au.play();
    }} else {{
      au.pause();
      curClip = null;
      updateActiveMarks();
      np.textContent = 'paused';
    }}
    return;
  }}
  const resumePos = (curClip !== null && !au.paused) ? au.currentTime : 0;
  curClip = fn;
  updateActiveMarks();

  const src = resolveAudioSrc(fn);
  np.textContent = `${{fn}} [${{clip.head}} | ${{clip.target || 'base'}} | g${{clip.gain}}]`;
  au.src = src;

  const onReady = () => {{
    try {{
      if (resumePos > 0) {{
        au.currentTime = Math.min(resumePos, (au.duration || 20) - 0.05);
      }}
    }} catch(e) {{}}
    au.play().catch(err => {{
      console.error('Play error on', src, err);
      np.textContent = `Error playing: ${{err.message}}`;
    }});
  }};

  if (au.readyState >= 1) {{
    onReady();
  }} else {{
    au.addEventListener('loadedmetadata', onReady, {{ once: true }});
  }}

  if (window.noteSet) {{
    window.noteSet({{ model: clip.head, clip: fn }});
  }}
}}

if (barPp) {{
  barPp.addEventListener('click', () => {{
    if (!au.src) return;
    au.paused ? au.play() : au.pause();
  }});
}}

window.addEventListener('keydown', (e) => {{
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.code === 'Space') {{
    e.preventDefault();
    if (!au.src) return;
    au.paused ? au.play() : au.pause();
  }} else if (e.code === 'Escape') {{
    au.pause();
    curClip = null;
    updateActiveMarks();
    np.textContent = 'stopped';
  }}
}});

document.addEventListener('DOMContentLoaded', () => {{
  document.querySelectorAll('button.cell.play-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
      const fn = btn.dataset.clip;
      if (fn) play(fn);
    }});
  }});
}});
</script>
</body>
</html>
'''

    # Inject floating persistent player
    html_with_player = inject(html)

    # Save to staging and dir index
    out_file = STAGE / "chroma_avp_matrix.html"
    out_file.write_text(html_with_player)
    (DEST_AUDIO / "index.html").write_text(html_with_player)
    print(f"[page] Generated dashboard at {out_file}")
    print(f"[page] Staged directory index at {DEST_AUDIO / 'index.html'}")


if __name__ == "__main__":
    main()
