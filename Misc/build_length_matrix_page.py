#!/usr/bin/env python3
"""build_length_matrix_page.py -- Evaluation and auditing page for sequence length scaling matrix.

Features:
- Reads manifest.jsonl from /run/media/kim/Mantu/sa3_lora_runs/length_matrix_p07/
- 16 Frame lengths: 256 to 4096 (23.8s to 380.5s / 6m20s)
- 4 conditions per length: CFG 6.0 and CFG 12.0 across 2 seeds (1391676905, 1391676906)
- Auditable on mobile phone with prominent 1-5 score rating buttons.
- Ratings saved to localStorage and synchronized live with /files/ratings.php (pool: length_matrix_p07).
- Follows docs/eval-page-standard.md:
  - Header: VIBE ON THE EDG3 · EVALS
  - Nav: <a href="index.html">← all evals</a>
  - Float player injection
  - Audio playhead preservation on switch, auto-looping, restart on pause
"""

import os
import sys
import json
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from float_player import inject

OUT_DIR = "/run/media/kim/Mantu/sa3_lora_runs/length_matrix_p07"
MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.jsonl")
HTML_OUT = os.path.expanduser("~/evals_aac/length_matrix_p07.html")
SUB_DIR = "length_matrix_p07"

def fmt_dur(s):
    m = int(s) // 60
    sec = int(s) % 60
    frac = int(round((s - int(s)) * 10))
    if m > 0:
        return f"{m}m {sec:02d}s"
    return f"{sec}.{frac}s"

def build_page():
    records = []
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        pass

    # Group by frame length
    by_len = {}
    for r in records:
        f = r["frames"]
        if f not in by_len:
            by_len[f] = []
        by_len[f].append(r)

    # Sort lengths
    sorted_lengths = sorted(by_len.keys())

    # Build sections
    sections_html = []
    for f in sorted_lengths:
        items = by_len[f]
        # sort items by cfg ascending, seed ascending
        items.sort(key=lambda x: (x["cfg"], x["seed"]))

        dur = items[0]["dur"]
        bars = items[0]["bars"]

        # Tier classification
        if f <= 512:
            tier_badge = '<span class="badge badge-short">Short (&lt;1 min)</span>'
        elif f <= 1792:
            tier_badge = '<span class="badge badge-mid">Medium (1–3 min)</span>'
        else:
            tier_badge = '<span class="badge badge-long">Long (3–6.3 min)</span>'

        sec_header = f"""
        <div class="len-section" data-len="{f}">
          <div class="len-header">
            <span class="len-title">{f} Frames ({dur:.1f}s / {bars:.1f} bars)</span>
            {tier_badge}
            <span class="dim" style="margin-left:auto">{len(items)}/4 renders completed</span>
          </div>
          <div class="grid-cards">
        """

        cards = []
        for it in items:
            cid = it["id"]
            cfg = it["cfg"]
            seed = it["seed"]
            seed_label = "Seed 1" if seed == 1391676905 else "Seed 2"
            gen_s = it.get("gen_time_s", 0)
            vram = it.get("vram_gb", 0)
            audio_rel = f"{SUB_DIR}/{cid}.m4a"

            card_html = f"""
            <div class="card" id="{cid}" data-len="{f}" data-cfg="{cfg}" data-seed="{seed}">
              <div class="top">
                <span class="tid">{cid}</span>
                <span class="badge cfg">CFG {cfg:.1f}</span>
                <span class="badge seed">{seed_label} ({seed})</span>
                <span class="dim gen-stats">{gen_s:.1f}s gen · {vram:.1f}G VRAM</span>
              </div>
              <div class="clip-controls">
                <button class="cell pl" data-f="{audio_rel}">▶ Play ({fmt_dur(dur)})</button>
                <div class="score-group" data-id="{cid}">
                  <span class="score-label">Score:</span>
                  <button class="score-btn" data-v="1" title="1 - Disintegrated">1</button>
                  <button class="score-btn" data-v="2" title="2 - Flawed">2</button>
                  <button class="score-btn" data-v="3" title="3 - Neutral">3</button>
                  <button class="score-btn" data-v="4" title="4 - Solid">4</button>
                  <button class="score-btn" data-v="5" title="5 - Peak Goa">5</button>
                </div>
              </div>
            </div>
            """
            cards.append(card_html)

        sec_html = sec_header + "\n".join(cards) + "\n</div></div>"
        sections_html.append(sec_html)

    body_content = "\n".join(sections_html) if sections_html else "<p>No clips generated yet. Generation in progress...</p>"

    # Build full HTML
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sequence Length Scaling Matrix · p07 Goa Trance</title>
<link rel="stylesheet" href="evals.css">
<style>
.wrap{{max-width:960px;margin:0 auto;padding:12px 14px 100px;font-family:'IBM Plex Mono',ui-monospace,monospace}}
.ex{{background:#fff;border:1px solid var(--rule);border-left:3px solid var(--edge);padding:10px 12px;font-size:12.5px;margin:10px 0;line-height:1.6}}
#bar{{position:sticky;top:0;background:var(--paper);padding:8px 0;border-bottom:1px solid var(--rule);z-index:10;font-size:13px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}}
#bar select,#bar button{{font:inherit;font-size:12px;padding:6px 10px;border:1px solid var(--rule);border-radius:3px;background:#fff}}
#bar b{{color:var(--ink)}}
.len-section{{margin:20px 0 10px;border-top:2px solid var(--rule);padding-top:12px}}
.len-header{{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:8px}}
.len-title{{font-size:14px;font-weight:700;color:var(--ink)}}
.badge{{font-size:11px;padding:2px 6px;border-radius:3px;font-weight:500;border:1px solid var(--rule)}}
.badge.badge-short{{background:#e8f5e9;color:#1b5e20;border-color:#c8e6c9}}
.badge.badge-mid{{background:#e1f5fe;color:#01579b;border-color:#b3e5fc}}
.badge.badge-long{{background:#f3e5f5;color:#4a148c;border-color:#e1bee7}}
.badge.cfg{{background:#fff3e0;color:#e65100;border-color:#ffe0b2}}
.badge.seed{{background:#ede7f6;color:#311b92;border-color:#d1c4e9}}
.dim{{color:var(--muted);font-size:11px}}
.grid-cards{{display:flex;flex-direction:column;gap:8px}}
.card{{border:1px solid var(--rule);background:#fff;padding:10px 12px;border-left:4px solid var(--rule);border-radius:4px}}
.card.scored{{border-left-color:var(--edge)}}
.card.now{{outline:2px solid var(--edge)}}
.top{{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:6px}}
.tid{{font-weight:600;color:var(--ink);font-size:12.5px}}
.clip-controls{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
.cell{{background:#fff;border:1px solid var(--rule);padding:8px 12px;border-radius:3px;cursor:pointer;font:inherit;font-size:12px;color:var(--ink);touch-action:manipulation;-webkit-tap-highlight-color:transparent}}
.cell:hover{{border-color:var(--edge);color:var(--edge)}}
.cell.pl{{background:var(--edge);color:#fff;border-color:var(--edge);font-weight:600;min-width:140px;text-align:center}}
.cell.pl:hover{{opacity:.9}}
.cell.playing{{background:#000!important;color:#fff!important;border-color:#000!important}}
.score-group{{display:inline-flex;align-items:center;gap:4px;margin-left:auto}}
.score-label{{font-size:11.5px;color:var(--muted);font-weight:600;margin-right:2px}}
.score-btn{{border:1px solid var(--rule);background:#fff;width:34px;height:34px;border-radius:4px;cursor:pointer;font:inherit;font-size:13px;font-weight:700;color:var(--ink);display:inline-flex;align-items:center;justify-content:center;touch-action:manipulation;-webkit-tap-highlight-color:transparent;transition:all 0.1s ease}}
.score-btn:hover{{border-color:var(--edge);color:var(--edge)}}
.score-btn.on[data-v="1"]{{background:#90a4ae;border-color:#607d8b;color:#fff}}
.score-btn.on[data-v="2"]{{background:#ffb74d;border-color:#f57c00;color:#fff}}
.score-btn.on[data-v="3"]{{background:#ffd54f;border-color:#ffa000;color:#000}}
.score-btn.on[data-v="4"]{{background:#81c784;border-color:#388e3c;color:#fff}}
.score-btn.on[data-v="5"]{{background:#0c807c;border-color:#0c807c;color:#fff;box-shadow:0 0 6px rgba(12,128,124,0.4)}}

@media (max-width: 640px) {{
  .wrap{{padding:8px 8px 110px}}
  .card{{padding:10px}}
  .clip-controls{{flex-direction:column;align-items:stretch;gap:8px}}
  .cell.pl{{width:100%;padding:12px;font-size:13.5px}}
  .score-group{{width:100%;justify-content:space-between;margin-left:0}}
  .score-btn{{flex:1;height:44px;font-size:16px}}
}}
</style>
</head>
<body>
<div class="wrap">
<p class="over">VIBE ON THE EDG3 · EVALS</p>
<p class="nav"><a href="index.html">&larr; all evals</a></p>
<h1>Sequence Length Scaling Matrix (256 &rarr; 4096 frames) <span class="un" title="Not audited yet">❗</span></h1>

<div class="ex">
  <b>Purpose & Recipe:</b> Systematic audit of sequence length scaling from 256 to 4096 frames (23.8s to 380.5s / 6m20s) in increments of 256 frames.<br>
  <b>Settings:</b> Based on <code>p07_islands_v2_direct_bridge</code> (BPM: 145.0, Key: F minor, 24 steps).<br>
  <b>Prompt:</b> <code>"early 2000s goa trance, melodic dark mood, 145 bpm, driving acid lead, energetic mood, F minor, steady 145 bpm"</code><br>
  <b>Model Stack:</b> Full-FT backbone (<code>fullft_avp_t256_ep80</code>, w=1.0) + AVP subloss adapter (<code>subloss_k24_avpaug_t512_bf16_s1</code>, PQ 7.50, w=0.75).<br>
  <b>Auditing Instructions:</b> Tap <b>Play</b> to listen. Score 1 to 5 (1=Disintegrated/Garbled, 3=Passable, 5=Peak Driving Goa). Ratings sync automatically across devices.
</div>

<div id="bar">
  <label>Length: 
    <select id="filter-tier">
      <option value="">All Lengths (256–4096)</option>
      <option value="short">Short (&lt;1 min: 256–512)</option>
      <option value="mid">Medium (1–3 min: 768–1792)</option>
      <option value="long">Long (3–6.3 min: 2048–4096)</option>
    </select>
  </label>
  <label>CFG: 
    <select id="filter-cfg">
      <option value="">All CFGs</option>
      <option value="6.0">CFG 6.0</option>
      <option value="12.0">CFG 12.0</option>
    </select>
  </label>
  <label>Filter: 
    <select id="filter-score">
      <option value="">All Clips</option>
      <option value="rated">Rated</option>
      <option value="unrated">Unrated</option>
      <option value="5">Score 5 (Peak)</option>
      <option value="4+">Score 4 or 5</option>
      <option value="1">Score 1 (Fails)</option>
    </select>
  </label>
  <span style="margin-left:auto"><b>Progress:</b> <span id="cnt-rated">0</span> / <span id="cnt-tot">{len(records)}</span> scored (Avg: <span id="cnt-avg">-</span>)</span>
</div>

<div id="sections-container">
{body_content}
</div>

<audio id="au" preload="none" loop playsinline webkit-playsinline></audio>
</div>

<script>
const NAME = 'length_matrix_p07';
const POOL = 'length_matrix_p07';
const API = '/files/ratings.php';
let scores = JSON.parse(localStorage.getItem(NAME + '_scores') || '{{}}');

const a = document.getElementById('au');
a.loop = true;
window.a = a;
if (window.__fp_attach) window.__fp_attach(a);

let cur = null;
let isSwitching = false;
let wasPaused = false;
let manualSeek = false;

function card(el) {{ return el ? el.closest('.card') : null; }}

function start(b) {{
  const f = b.dataset.f;
  const c = card(b);
  const same = a.src && a.src.endsWith('/' + f);

  if (cur && cur !== b) {{
    cur.classList.remove('playing');
    const oldC = card(cur);
    if (oldC) oldC.classList.remove('now');
  }}

  cur = b;
  b.classList.add('playing');
  if (c) c.classList.add('now');

  if (same) {{
    if (a.paused) {{
      a.play().catch(e => console.log('play err', e));
    }} else {{
      a.pause();
      b.classList.remove('playing');
      if (c) c.classList.remove('now');
      cur = null;
    }}
    return;
  }}

  const isCurrentlyPlaying = !a.paused && a.currentTime > 0;
  const prevTime = a.currentTime;

  if (isCurrentlyPlaying) {{
    // Continuous playhead across clip switching
    isSwitching = true;
    wasPaused = false;
    manualSeek = false;
    a.src = f;

    let seekDone = false;
    const applySeek = () => {{
      if (seekDone) return;
      const d = a.duration;
      if (d && isFinite(d) && d > 0) {{
        a.currentTime = (prevTime < d) ? prevTime : (prevTime % d);
        seekDone = true;
      }}
    }};

    a.addEventListener('loadedmetadata', applySeek, {{ once: true }});
    a.addEventListener('canplay', applySeek, {{ once: true }});

    // Call play() synchronously in the user touch event stack (vital for mobile browsers!)
    const p = a.play();
    if (p !== undefined) {{
      p.then(() => {{
        applySeek();
        setTimeout(() => {{ isSwitching = false; }}, 80);
      }}).catch(err => {{
        console.error("Audio playback error:", err);
        isSwitching = false;
      }});
    }} else {{
      setTimeout(() => {{ isSwitching = false; }}, 80);
    }}
  }} else {{
    // Was paused or stopped: restart clip from the beginning (0:00)
    isSwitching = false;
    wasPaused = false;
    manualSeek = false;
    a.src = f;
    a.currentTime = 0;

    a.addEventListener('loadedmetadata', () => {{
      a.currentTime = 0;
    }}, {{ once: true }});

    const p = a.play();
    if (p !== undefined) {{
      p.then(() => {{
        a.currentTime = 0;
      }}).catch(err => console.error("Playback error:", err));
    }}
  }}
}}

document.addEventListener('click', e => {{
  const plBtn = e.target.closest('.cell.pl');
  if (plBtn) {{
    start(plBtn);
    return;
  }}

  const sBtn = e.target.closest('.score-btn');
  if (sBtn) {{
    const group = sBtn.closest('.score-group');
    const cid = group.dataset.id;
    const val = sBtn.dataset.v;
    const curVal = scores[cid];

    if (curVal === val) {{
      delete scores[cid];
      saveScore(cid, '');
    }} else {{
      scores[cid] = val;
      saveScore(cid, val);
    }}
    paint();
  }}
}});

a.addEventListener('pause', () => {{
  if (!isSwitching) {{
    wasPaused = true;
  }}
  if (cur) {{
    cur.classList.remove('playing');
    if (card(cur)) card(cur).classList.remove('now');
    cur = null;
  }}
}});

a.addEventListener('play', () => {{
  if (wasPaused) {{
    if (!manualSeek) a.currentTime = 0;
    wasPaused = false;
    manualSeek = false;
  }}
  if (cur) {{
    cur.classList.add('playing');
    if (card(cur)) card(cur).classList.add('now');
  }}
}});

function paint() {{
  let ratedCount = 0;
  let scoreSum = 0;
  const allCards = document.querySelectorAll('.card');

  allCards.forEach(c => {{
    const cid = c.id;
    const sc = scores[cid] || '';
    if (sc) {{
      ratedCount++;
      scoreSum += parseInt(sc, 10);
      c.classList.add('scored');
    }} else {{
      c.classList.remove('scored');
    }}

    c.querySelectorAll('.score-btn').forEach(btn => {{
      btn.classList.toggle('on', btn.dataset.v === sc);
    }});
  }});

  const total = allCards.length;
  document.getElementById('cnt-rated').textContent = ratedCount;
  document.getElementById('cnt-tot').textContent = total;
  document.getElementById('cnt-avg').textContent = ratedCount > 0 ? (scoreSum / ratedCount).toFixed(1) : '-';

  filt();
}}

function filt() {{
  const selTier = document.getElementById('filter-tier').value;
  const selCfg = document.getElementById('filter-cfg').value;
  const selScore = document.getElementById('filter-score').value;

  document.querySelectorAll('.len-section').forEach(sec => {{
    const flen = parseInt(sec.dataset.len, 10);
    let matchTier = true;
    if (selTier === 'short') matchTier = (flen <= 512);
    else if (selTier === 'mid') matchTier = (flen > 512 && flen <= 1792);
    else if (selTier === 'long') matchTier = (flen > 1792);

    let secVisibleCount = 0;
    sec.querySelectorAll('.card').forEach(c => {{
      const cfg = c.dataset.cfg;
      const sc = scores[c.id] || '';

      const matchCfg = (!selCfg || cfg === selCfg);
      let matchScore = true;
      if (selScore === 'rated') matchScore = !!sc;
      else if (selScore === 'unrated') matchScore = !sc;
      else if (selScore === '5') matchScore = (sc === '5');
      else if (selScore === '4+') matchScore = (sc === '4' || sc === '5');
      else if (selScore === '1') matchScore = (sc === '1');

      const isVis = matchTier && matchCfg && matchScore;
      c.style.display = isVis ? '' : 'none';
      if (isVis) secVisibleCount++;
    }});

    sec.style.display = secVisibleCount > 0 ? '' : 'none';
  }});
}}

document.getElementById('filter-tier').onchange = filt;
document.getElementById('filter-cfg').onchange = filt;
document.getElementById('filter-score').onchange = filt;

async function saveScore(id, val) {{
  localStorage.setItem(NAME + '_scores', JSON.stringify(scores));
  const payload = {{
    type: 'trackpick',
    pool: POOL,
    id: id,
    pick: val || 'clear',
    source: 'length_matrix'
  }};
  try {{
    await fetch(API, {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify(payload)
    }});
  }} catch(e) {{
    console.warn("Could not sync rating", e);
  }}
}}

async function loadServerScores() {{
  try {{
    const r = await fetch(API + '?trackpicks=' + encodeURIComponent(POOL), {{ cache: 'no-store' }});
    if (r.ok) {{
      const d = await r.json();
      if (d.picks) {{
        for (const [k, v] of Object.entries(d.picks)) {{
          if (v && v !== 'clear') scores[k] = v;
          else if (v === 'clear') delete scores[k];
        }}
        localStorage.setItem(NAME + '_scores', JSON.stringify(scores));
        paint();
      }}
    }}
  }} catch(e) {{
    console.warn("Could not fetch server ratings", e);
  }}
}}

paint();
loadServerScores();
</script>
</body>
</html>
"""

    injected = inject(html)
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(injected)

    print(f"Built {HTML_OUT} with {len(records)} records.")

if __name__ == "__main__":
    build_page()
