#!/usr/bin/env python3
"""build_length_adapter_matrix_page.py -- Evaluation and auditing page for Sequence Length x Adapter Weight x Prompt Matrix.

Features:
- Reads manifest.jsonl from /run/media/kim/Mantu/sa3_lora_runs/length_adapter_matrix/
- 6 Frame lengths: 128, 256, 512, 1024, 2048, 4096 frames
- 3 Adapter conditions: w=0.75 (hot), w=0.30 (mild), w=0.00 (backbone only)
- 2 Contrast Prompts: Acid Driving 145 BPM vs Melodic Dual-Lead 151 BPM
- Auditable on mobile phone with prominent 1-5 score rating buttons.
- Ratings saved to localStorage and synchronized live with /files/ratings.php (pool: length_adapter_matrix).
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

OUT_DIR = "/run/media/kim/Mantu/sa3_lora_runs/length_adapter_matrix"
MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.jsonl")
HTML_OUT = os.path.expanduser("~/evals_aac/length_adapter_matrix.html")
SUB_DIR = "length_adapter_matrix"

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

    # Group by prompt, then length
    by_prompt_len = {}
    for r in records:
        pk = r.get("prompt_key", "acid145")
        fl = r["frames"]
        if pk not in by_prompt_len:
            by_prompt_len[pk] = {}
        if fl not in by_prompt_len[pk]:
            by_prompt_len[pk][fl] = []
        by_prompt_len[pk][fl].append(r)

    sections_html = []

    prompt_titles = {
        "acid145": "Prompt A: Acid Driving Goa (145 BPM, F minor)",
        "melodic151": "Prompt B: Melodic Dual-Lead Goa (151 BPM, JD-800 / Prophecy)"
    }

    for pk in ["acid145", "melodic151"]:
        if pk not in by_prompt_len:
            continue
        p_data = by_prompt_len[pk]
        p_title = prompt_titles.get(pk, pk)

        sec_header = f"""
        <div class="prompt-group" data-prompt="{pk}">
          <h2 class="prompt-title">{escape(p_title)}</h2>
        """
        sec_cards = []

        sorted_lengths = sorted(p_data.keys())
        for f in sorted_lengths:
            items = p_data[f]
            # sort items: healthy dora256 first, then CFG ascending, then adapter_weight descending
            items.sort(key=lambda x: (x.get("adapter_name", "subloss_k24") != "dora256_avp_aug10", x.get("cfg", 6.0), -x["adapter_weight"]))

            dur = items[0]["dur"]
            bars = items[0]["bars"]

            # Tier classification
            if f <= 256:
                tier_badge = '<span class="badge badge-short">Short (&lt;30s)</span>'
            elif f <= 1024:
                tier_badge = '<span class="badge badge-mid">Medium (45s–1.6m)</span>'
            else:
                tier_badge = '<span class="badge badge-long">Long (3.2–6.3m)</span>'

            len_header = f"""
            <div class="len-section" data-len="{f}">
              <div class="len-header">
                <span class="len-title">{f} Frames ({dur:.1f}s / {bars:.1f} bars)</span>
                {tier_badge}
                <span class="dim" style="margin-left:auto">{len(items)} clips rendered</span>
              </div>
              <div class="grid-cards">
            """

            cards = []
            for it in items:
                cid = it["clip_id"]
                w = it["adapter_weight"]
                cfg = it.get("cfg", 6.0)
                ad_name = it.get("adapter_name", "subloss_k24")
                gen_s = it.get("gen_time_s", 0)
                vram = it.get("peak_vram_gb", 0)
                audio_rel = f"{SUB_DIR}/{cid}.m4a"

                if ad_name == "dora256_avp_aug10":
                    ad_badge = '<span class="badge adapter-healthy">dora256 (#1 Matrix)</span>'
                else:
                    ad_badge = '<span class="badge adapter-subloss">subloss_k24</span>'

                if w == 0.75:
                    w_badge = '<span class="badge weight-hot">w=0.75 (Hot)</span>'
                elif w == 0.50:
                    w_badge = '<span class="badge weight-mid50">w=0.50 (Balanced)</span>'
                elif w == 0.30:
                    w_badge = '<span class="badge weight-mild">w=0.30 (Mild)</span>'
                elif w == 0.25:
                    w_badge = '<span class="badge weight-mid25">w=0.25 (Subtle)</span>'
                else:
                    w_badge = '<span class="badge weight-none">Backbone Only (w=0.0)</span>'

                if cfg == 6.0:
                    cfg_badge = '<span class="badge cfg-std">CFG 6</span>'
                elif cfg == 7.0:
                    cfg_badge = '<span class="badge cfg-std">CFG 7</span>'
                elif cfg == 12.0:
                    cfg_badge = '<span class="badge cfg-high">CFG 12</span>'
                elif cfg == 16.0:
                    cfg_badge = '<span class="badge cfg-ext">CFG 16</span>'
                elif cfg == 24.0:
                    cfg_badge = '<span class="badge cfg-hyper">CFG 24</span>'
                elif cfg == 32.0:
                    cfg_badge = '<span class="badge cfg-ultra">CFG 32</span>'
                else:
                    cfg_badge = f'<span class="badge cfg-std">CFG {cfg}</span>'

                card_html = f"""
                <div class="card" id="{cid}" data-len="{f}" data-weight="{w}" data-cfg="{cfg}" data-adapter="{ad_name}" data-prompt="{pk}">
                  <div class="top">
                    <span class="tid">{cid}</span>
                    {ad_badge}
                    {w_badge}
                    {cfg_badge}
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

            len_block = len_header + "\n".join(cards) + "\n</div></div>"
            sec_cards.append(len_block)

        sections_html.append(sec_header + "\n".join(sec_cards) + "\n</div>")

    body_content = "\n".join(sections_html) if sections_html else "<p>Generation in progress...</p>"

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sequence Length x Adapter Gain Matrix · SA3</title>
<link rel="stylesheet" href="evals.css">
<style>
.wrap{{max-width:960px;margin:0 auto;padding:12px 14px 100px;font-family:'IBM Plex Mono',ui-monospace,monospace}}
.ex{{background:#fff;border:1px solid var(--rule);border-left:3px solid var(--edge);padding:10px 12px;font-size:12.5px;margin:10px 0;line-height:1.6}}
#bar{{position:sticky;top:0;background:var(--paper);padding:8px 0;border-bottom:1px solid var(--rule);z-index:10;font-size:13px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}}
#bar select,#bar button{{font:inherit;font-size:12px;padding:6px 10px;border:1px solid var(--rule);border-radius:3px;background:#fff}}
.prompt-group{{margin-top:24px;border-top:2px solid var(--rule);padding-top:12px}}
.prompt-title{{font-size:16px;font-weight:700;margin:8px 0 16px;color:var(--ink)}}
.len-section{{margin-bottom:20px;background:var(--paper);border:1px solid var(--rule);border-radius:6px;padding:12px}}
.len-header{{display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap}}
.len-title{{font-weight:700;font-size:14px;color:var(--ink)}}
.grid-cards{{display:grid;grid-template-columns:repeat(auto-fill, minmax(280px, 1fr));gap:10px}}
.card{{background:#fff;border:1px solid var(--rule);border-radius:4px;padding:10px;display:flex;flex-direction:column;gap:8px}}
.card.playing{{border-color:var(--edge);box-shadow:0 0 0 1px var(--edge)}}
.card.rated{{background:#fbfbfb}}
.card .top{{display:flex;align-items:center;gap:6px;flex-wrap:wrap;font-size:11px}}
.card .tid{{font-weight:600;color:var(--ink)}}
.badge{{font-size:10px;padding:2px 6px;border-radius:3px;font-weight:600}}
.badge-short{{background:#eef6fc;color:#1c6ca1}}
.badge-mid{{background:#f4f0fa;color:#6b3ba6}}
.badge-long{{background:#fdf2e9;color:#b25900}}
.adapter-healthy{{background:#ecfdf5;color:#065f46;border:1px solid #a7f3d0}}
.adapter-subloss{{background:#fef2f2;color:#991b1b;border:1px solid #fecaca}}
.weight-hot{{background:#fbeae5;color:#c0392b}}
.weight-mid50{{background:#eff6ff;color:#1e40af;border:1px solid #bfdbfe}}
.weight-mild{{background:#e8f8f5;color:#16a085}}
.weight-mid25{{background:#f0fdf4;color:#166534;border:1px solid #bbf7d0}}
.weight-none{{background:#eaeded;color:#5d6d7e}}
.cfg-std{{background:#edf2f7;color:#4a5568}}
.cfg-high{{background:#ebf8ff;color:#2b6cb0;border:1px solid #bee3f8}}
.cfg-ext{{background:#fffaf0;color:#c05621;border:1px solid #feebc8}}
.cfg-hyper{{background:#f3e8ff;color:#6b21a8;border:1px solid #e9d5ff}}
.cfg-ultra{{background:#ffe4e6;color:#9f1239;border:1px solid #fecdd3}}
.gen-stats{{margin-left:auto;font-size:10px;color:var(--dim)}}
.clip-controls{{display:flex;flex-direction:column;gap:8px;margin-top:4px}}
button.pl{{font:inherit;font-size:12px;font-weight:600;padding:8px 12px;border:1px solid var(--edge);border-radius:4px;background:var(--edge);color:#fff;cursor:pointer;text-align:left;transition:all .15s ease}}
button.pl:hover{{filter:brightness(1.1)}}
button.pl.playing{{background:#000;border-color:#000}}
.score-group{{display:flex;align-items:center;gap:4px;background:#f9f9f9;padding:4px 6px;border-radius:4px;border:1px solid #eee}}
.score-label{{font-size:11px;color:var(--dim);margin-right:2px}}
.score-btn{{font:inherit;font-size:13px;font-weight:700;width:34px;height:32px;padding:0;border:1px solid #ccc;border-radius:4px;background:#fff;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;touch-action:manipulation;-webkit-tap-highlight-color:transparent;transition:all .1s ease}}
.score-btn:hover{{border-color:#888;background:#f0f0f0}}
.score-btn.active[data-v="1"]{{background:#90a4ae!important;border-color:#607d8b!important;color:#fff!important}}
.score-btn.active[data-v="2"]{{background:#ffb74d!important;border-color:#f57c00!important;color:#fff!important}}
.score-btn.active[data-v="3"]{{background:#ffd54f!important;border-color:#ffa000!important;color:#000!important}}
.score-btn.active[data-v="4"]{{background:#81c784!important;border-color:#388e3c!important;color:#fff!important}}
.score-btn.active[data-v="5"]{{background:#0c807c!important;border-color:#0c807c!important;color:#fff!important;box-shadow:0 0 6px rgba(12,128,124,0.4)!important}}
.score-summary{{font-size:11.5px;color:var(--dim);margin-left:auto}}
@media (max-width:600px){{
  .grid-cards{{grid-template-columns:1fr}}
  .wrap{{padding:8px 8px 110px}}
  .len-header{{flex-direction:column;align-items:flex-start;gap:4px}}
  .card .top{{flex-direction:column;align-items:flex-start;gap:4px}}
  .gen-stats{{margin-left:0}}
  .clip-controls{{flex-direction:column;align-items:stretch;gap:8px}}
  .score-group{{width:100%;justify-content:space-between;margin-top:4px}}
  .score-btn{{flex:1;height:42px;font-size:16px}}
}}
</style>
</head>
<body>
<div class="wrap">
  <header style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px">
    <div style="font-weight:700;font-size:13px;letter-spacing:1px;color:var(--ink)">VIBE ON THE EDG3 · EVALS</div>
    <div class="dim" style="font-size:11px"><a href="index.html" style="color:inherit;text-decoration:none">← all evals</a></div>
  </header>

  <h1 style="font-size:18px;margin:4px 0 10px;color:var(--ink)">Sequence Length x Adapter Gain Matrix</h1>

  <div class="ex">
    <strong>A/B/CFG Matrix Design:</strong> Evaluating sequence length scaling (128 to 4096 frames / 11.9s to 6.3m) across three adapter weight conditions (<strong>w=0.75</strong> hot, <strong>w=0.30</strong> mild, and <strong>w=0.00</strong> backbone only), two contrast prompts, and guidance scales (<strong>CFG 6.0</strong>, <strong>12.0</strong>, <strong>16.0</strong>, <strong>24.0</strong>, and <strong>32.0</strong>).<br>
    <strong>Core Question:</strong> Long latents exhibit a fragile attractor / dipole dynamic (stable driving passages alternating with arrhythmic kick stumble). Does hyper/ultra CFG (24 &amp; 32) permanently lock the trajectory into the rhythmic basin, or induce high-frequency burnout and distortion?
  </div>

  <div id="bar">
    <label>Adapter:
      <select id="sel-adapter">
        <option value="all">All Adapters</option>
        <option value="dora256_avp_aug10">dora256_avp (Rank #1 Healthy)</option>
        <option value="subloss_k24">subloss_k24 (Experimental)</option>
      </select>
    </label>
    <label>Length:
      <select id="sel-len">
        <option value="all">All Lengths (128–4096)</option>
        <option value="128">128 Frames (11.9s)</option>
        <option value="256">256 Frames (23.8s)</option>
        <option value="512">512 Frames (47.6s)</option>
        <option value="1024">1024 Frames (95.1s)</option>
        <option value="2048">2048 Frames (3.2m)</option>
        <option value="4096">4096 Frames (6.3m)</option>
      </select>
    </label>
    <label>CFG Scale:
      <select id="sel-cfg">
        <option value="all">All CFGs</option>
        <option value="6">CFG 6.0 (Baseline)</option>
        <option value="7">CFG 7.0 (Default)</option>
        <option value="12">CFG 12.0 (High Attractor)</option>
        <option value="16">CFG 16.0 (Extreme Attractor)</option>
        <option value="24">CFG 24.0 (Hyper Guidance)</option>
        <option value="32">CFG 32.0 (Ultra Guidance)</option>
      </select>
    </label>
    <label>Adapter Weight:
      <select id="sel-weight">
        <option value="all">All Weights</option>
        <option value="0.75">w=0.75 (Hot)</option>
        <option value="0.5">w=0.50 (Balanced)</option>
        <option value="0.3">w=0.30 (Mild)</option>
        <option value="0.25">w=0.25 (Subtle)</option>
        <option value="0.0">w=0.00 (Backbone only)</option>
      </select>
    </label>
    <label>Prompt:
      <select id="sel-prompt">
        <option value="all">All Prompts</option>
        <option value="acid145">Prompt A (Acid 145 BPM)</option>
        <option value="melodic151">Prompt B (Melodic 151 BPM)</option>
      </select>
    </label>
    <span class="score-summary" id="score-summary">0/{len(records)} scored</span>
  </div>

  {body_content}

  <audio id="au" preload="none"></audio>
</div>

<script>
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

const POOL = 'length_adapter_matrix';
const API = '/files/ratings.php';
let scores = {{}};

try {{
  scores = JSON.parse(localStorage.getItem(POOL + '_scores') || '{{}}');
}} catch(e) {{
  scores = {{}};
}}

function updateScoreUI() {{
  const allCards = document.querySelectorAll('.card');
  let scoredCount = 0;

  allCards.forEach(card => {{
    const cid = card.id;
    const sc = scores[cid] || '';
    const btns = card.querySelectorAll('.score-btn');
    if (sc) {{
      scoredCount++;
      card.classList.add('rated');
      btns.forEach(b => {{
        b.classList.toggle('active', b.getAttribute('data-v') === String(sc));
      }});
    }} else {{
      card.classList.remove('rated');
      btns.forEach(b => b.classList.remove('active'));
    }}
  }});

  const summary = document.getElementById('score-summary');
  if (summary) {{
    summary.textContent = `${{scoredCount}}/${{allCards.length}} scored`;
  }}
}}

async function saveScore(cid, val) {{
  if (val) {{
    scores[cid] = String(val);
  }} else {{
    delete scores[cid];
  }}
  try {{
    localStorage.setItem(POOL + '_scores', JSON.stringify(scores));
  }} catch(e) {{}}
  updateScoreUI();

  try {{
    await fetch(API, {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        type: 'trackpick',
        pool: POOL,
        id: cid,
        pick: val ? String(val) : 'clear',
        source: POOL
      }})
    }});
  }} catch(e) {{
    console.warn('Live rating sync failed, kept in local storage', e);
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
        localStorage.setItem(POOL + '_scores', JSON.stringify(scores));
        updateScoreUI();
      }}
    }}
  }} catch(e) {{
    console.warn("Could not fetch server ratings", e);
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
    const cid = group.getAttribute('data-id');
    const val = sBtn.getAttribute('data-v');
    const curVal = scores[cid];

    if (curVal === val) {{
      saveScore(cid, ''); // toggle off
    }} else {{
      saveScore(cid, val); // set score
    }}
  }}
}});

// Filter controls
function applyFilters() {{
  const lenVal = document.getElementById('sel-len').value;
  const cfgVal = document.getElementById('sel-cfg').value;
  const wVal = document.getElementById('sel-weight').value;
  const pVal = document.getElementById('sel-prompt').value;
  const adVal = document.getElementById('sel-adapter').value;

  document.querySelectorAll('.card').forEach(card => {{
    const cLen = card.getAttribute('data-len');
    const cCfg = card.getAttribute('data-cfg');
    const cW = card.getAttribute('data-weight');
    const cP = card.getAttribute('data-prompt');
    const cAd = card.getAttribute('data-adapter') || 'subloss_k24';

    const matchLen = (lenVal === 'all' || lenVal === cLen);
    const matchCfg = (cfgVal === 'all' || parseFloat(cfgVal) === parseFloat(cCfg));
    const matchW = (wVal === 'all' || parseFloat(wVal) === parseFloat(cW));
    const matchP = (pVal === 'all' || pVal === cP);
    const matchAd = (adVal === 'all' || adVal === cAd);

    if (matchLen && matchCfg && matchW && matchP && matchAd) {{
      card.style.display = 'flex';
    }} else {{
      card.style.display = 'none';
    }}
  }});

  // Hide empty len-sections
  document.querySelectorAll('.len-section').forEach(sec => {{
    const visibleCards = sec.querySelectorAll('.card[style*="display: flex"]');
    if (visibleCards.length === 0 && (lenVal !== 'all' || cfgVal !== 'all' || wVal !== 'all' || pVal !== 'all' || adVal !== 'all')) {{
      sec.style.display = 'none';
    }} else {{
      sec.style.display = 'block';
    }}
  }});

  // Hide empty prompt groups
  document.querySelectorAll('.prompt-group').forEach(grp => {{
    const pk = grp.getAttribute('data-prompt');
    if (pVal !== 'all' && pVal !== pk) {{
      grp.style.display = 'none';
    }} else {{
      grp.style.display = 'block';
    }}
  }});
}}

document.getElementById('sel-adapter').addEventListener('change', applyFilters);
document.getElementById('sel-len').addEventListener('change', applyFilters);
document.getElementById('sel-cfg').addEventListener('change', applyFilters);
document.getElementById('sel-weight').addEventListener('change', applyFilters);
document.getElementById('sel-prompt').addEventListener('change', applyFilters);

updateScoreUI();
loadServerScores();
</script>
</body>
</html>
"""
    os.makedirs(os.path.dirname(HTML_OUT), exist_ok=True)
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(inject(html))
    print(f"Built eval page: {HTML_OUT}")

if __name__ == "__main__":
    build_page()
