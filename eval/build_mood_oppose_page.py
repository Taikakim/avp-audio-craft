#!/usr/bin/env python3
"""build_mood_oppose_page.py -- Builds interactive web dashboard for mood reinforcement & opposition study.

Outputs:
- /home/kim/evals_aac/mood_oppose.html
"""
import json
from pathlib import Path

AAC_DIR = Path("/home/kim/evals_aac/mood_oppose")
JSON_PATH = AAC_DIR / "mood_56d_predictions.json"
OUT_HTML = Path("/home/kim/evals_aac/mood_oppose.html")

def main():
    with open(JSON_PATH) as f:
        data = json.load(f)

    classes = data["classes"]
    clips = data["clips"]

    # Precompute deltas
    by_prompt = {}
    for c in clips:
        by_prompt.setdefault(c["prompt_id"], []).append(c)

    for pid, plist in by_prompt.items():
        base_clip = next(x for x in plist if x["cond_id"] == "base")
        base_preds = base_clip["predictions"]
        for c in plist:
            deltas = {}
            for k in classes:
                deltas[k] = c["predictions"][k] - base_preds[k]
            c["deltas"] = deltas

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LatCH Mood Steering: Reinforcement, Opposition & 56-Dim Manifold Dynamics</title>
<style>
  :root {{
    --bg: #0c0e14;
    --panel: #161b26;
    --panel-border: #232b3e;
    --accent: #6366f1;
    --accent-hover: #4f46e5;
    --text: #e2e8f0;
    --text-muted: #94a3b8;
    --green: #10b981;
    --red: #ef4444;
    --cyan: #06b6d4;
    --orange: #f59e0b;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    line-height: 1.5;
    padding: 24px;
    max-width: 1400px;
    margin: 0 auto;
  }}
  header {{
    margin-bottom: 24px;
    border-bottom: 1px solid var(--panel-border);
    padding-bottom: 16px;
  }}
  h1 {{
    font-size: 1.8rem;
    font-weight: 700;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .badge {{
    font-size: 0.75rem;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 9999px;
    background: rgba(99, 102, 241, 0.2);
    color: #a5b4fc;
    border: 1px solid rgba(99, 102, 241, 0.4);
  }}
  .meta-bar {{
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    margin-top: 12px;
    font-size: 0.9rem;
    color: var(--text-muted);
  }}
  .meta-bar strong {{ color: var(--text); }}
  
  /* Tabs */
  .tabs {{
    display: flex;
    gap: 8px;
    margin-bottom: 20px;
  }}
  .tab-btn {{
    padding: 10px 20px;
    background: var(--panel);
    border: 1px solid var(--panel-border);
    color: var(--text-muted);
    font-size: 0.95rem;
    font-weight: 600;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.15s;
  }}
  .tab-btn.active {{
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
  }}

  /* Audio player panel */
  .player-fixed {{
    position: sticky;
    top: 12px;
    z-index: 100;
    background: rgba(22, 27, 38, 0.95);
    backdrop-filter: blur(10px);
    border: 1px solid var(--panel-border);
    border-radius: 12px;
    padding: 14px 20px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
  }}
  .player-info {{
    font-size: 0.95rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .player-info .current-track {{
    font-weight: 700;
    color: #fff;
  }}
  .player-info .current-action {{
    color: var(--cyan);
    margin-left: 8px;
    font-size: 0.85rem;
  }}
  audio {{
    height: 38px;
    outline: none;
    flex: 1;
    max-width: 600px;
  }}

  /* Grid of cards */
  .card-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
    gap: 20px;
    margin-bottom: 32px;
  }}
  .card {{
    background: var(--panel);
    border: 1px solid var(--panel-border);
    border-radius: 12px;
    padding: 18px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    cursor: pointer;
    transition: border-color 0.15s, transform 0.15s;
  }}
  .card:hover {{
    border-color: #3b82f6;
    transform: translateY(-2px);
  }}
  .card.active {{
    border-color: var(--accent);
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.3);
  }}
  .card-header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }}
  .card-title {{
    font-size: 1.05rem;
    font-weight: 700;
    color: #fff;
  }}
  .card-tag {{
    font-size: 0.75rem;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 6px;
    background: #1e293b;
    color: #cbd5e1;
  }}
  .card-tag.reinforce {{ background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }}
  .card-tag.oppose {{ background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }}
  .card-tag.neutral {{ background: rgba(148, 163, 184, 0.2); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.3); }}

  /* Top shifts bars */
  .shifts-container {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    font-size: 0.8rem;
    background: #0f131c;
    padding: 10px;
    border-radius: 8px;
  }}
  .shift-col h4 {{
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 6px;
  }}
  .shift-col.up h4 {{ color: var(--green); }}
  .shift-col.down h4 {{ color: var(--red); }}
  .shift-row {{
    display: flex;
    justify-content: space-between;
    padding: 2px 0;
    border-bottom: 1px solid #1a2234;
  }}
  .shift-row:last-child {{ border-bottom: none; }}
  .shift-name {{ font-weight: 500; }}
  .shift-val.up {{ color: var(--green); font-weight: 600; }}
  .shift-val.down {{ color: var(--red); font-weight: 600; }}

  /* Table section */
  .table-section {{
    margin-top: 40px;
    background: var(--panel);
    border: 1px solid var(--panel-border);
    border-radius: 12px;
    padding: 20px;
  }}
  .table-section h3 {{
    font-size: 1.2rem;
    margin-bottom: 14px;
    color: #fff;
  }}
  .table-controls {{
    margin-bottom: 14px;
    display: flex;
    gap: 12px;
    align-items: center;
  }}
  .table-controls input {{
    background: #0f131c;
    border: 1px solid var(--panel-border);
    border-radius: 6px;
    padding: 8px 12px;
    color: #fff;
    font-size: 0.9rem;
    width: 260px;
  }}
  .table-scroll {{
    overflow-x: auto;
    max-height: 500px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
    text-align: left;
  }}
  th, td {{
    padding: 8px 12px;
    border-bottom: 1px solid var(--panel-border);
    white-space: nowrap;
  }}
  th {{
    background: #111520;
    position: sticky;
    top: 0;
    z-index: 10;
    font-weight: 600;
    color: var(--text-muted);
  }}
  tr:hover td {{
    background: rgba(255, 255, 255, 0.03);
  }}
  .num-cell {{
    font-family: monospace;
    text-align: right;
  }}
  .val-up {{ color: var(--green); }}
  .val-down {{ color: var(--red); }}
</style>
</head>
<body>

<header>
  <h1>
    LatCH Mood Steering: Reinforcement, Opposition & Manifold Dynamics
    <span class="badge">56 Continuous Dimensions</span>
  </h1>
  <div class="meta-bar">
    <div><strong>Evaluator:</strong> Essentia Discogs-EffNet → MTG-Jamendo MoodTheme (Ground Truth Classifier)</div>
    <div><strong>Diffusion Backbone:</strong> Stable Audio 3 Medium Base</div>
    <div><strong>Continuous LatCH Head:</strong> ep40 held-out val loss 0.0598</div>
    <div><strong>Index:</strong> <a href="index.html" style="color: var(--accent); text-decoration: none;">← Back to Evals Portal</a></div>
  </div>
</header>

<div class="player-fixed">
  <div class="player-info">
    <span class="current-track" id="pTrack">Select a clip below to audition</span>
    <span class="current-action" id="pAction"></span>
  </div>
  <audio id="globalPlayer" controls></audio>
</div>

<div class="tabs">
  <button class="tab-btn active" onclick="switchPrompt('prompt_melodic')">Prompt A: Melodic Goa (Reinforce Melodic vs Oppose Dark vs Negative)</button>
  <button class="tab-btn" onclick="switchPrompt('prompt_dark')">Prompt B: Dark Psytrance (Reinforce Dark vs Oppose Melodic vs Negative)</button>
</div>

<div id="cardsPromptA" class="card-grid"></div>
<div id="cardsPromptB" class="card-grid" style="display: none;"></div>

<div class="table-section">
  <h3>Complete 56-Dimensional Predictions & Delta Matrix</h3>
  <div class="table-controls">
    <input type="text" id="filterInput" placeholder="Filter emotion tag (e.g. dark, melodic, space)..." onkeyup="filterTable()">
  </div>
  <div class="table-scroll">
    <table id="moodTable">
      <thead id="moodTableHead"></thead>
      <tbody id="moodTableBody"></tbody>
    </table>
  </div>
</div>

<script>
const DATA = {json.dumps(data)};
let currentPrompt = "prompt_melodic";
let currentAac = null;
const player = document.getElementById("globalPlayer");
const pTrack = document.getElementById("pTrack");
const pAction = document.getElementById("pAction");

function getTagType(action) {{
  if (action.includes("Reinforce")) return "reinforce";
  if (action.includes("Oppose")) return "oppose";
  return "neutral";
}}

function renderCards(promptId, containerId) {{
  const container = document.getElementById(containerId);
  container.innerHTML = "";
  const clips = DATA.clips.filter(c => c.prompt_id === promptId);
  const baseClip = clips.find(c => c.cond_id === "base");

  clips.forEach(c => {{
    const card = document.createElement("div");
    card.className = "card";
    card.id = "card_" + c.cond_id;
    card.onclick = () => playClip(c);

    // Calc top 4 up / down
    const deltas = Object.entries(c.predictions).map(([k, v]) => ({{
      name: k,
      val: v,
      base: baseClip.predictions[k],
      delta: v - baseClip.predictions[k]
    }}));
    deltas.sort((a, b) => b.delta - a.delta);
    const topUp = deltas.slice(0, 4).filter(x => x.delta > 0.0001);
    const topDown = deltas.slice(-4).reverse().filter(x => x.delta < -0.0001);

    const tagType = getTagType(c.action);

    let shiftsHtml = "";
    if (c.cond_id !== "base") {{
      shiftsHtml = `
        <div class="shifts-container">
          <div class="shift-col up">
            <h4>Surging (Elevated)</h4>
            ${{topUp.map(x => `
              <div class="shift-row">
                <span class="shift-name">${{x.name}}</span>
                <span class="shift-val up">+${{(x.delta * 100).toFixed(1)}}%</span>
              </div>
            `).join("")}}
          </div>
          <div class="shift-col down">
            <h4>Collapsing (Suppressed)</h4>
            ${{topDown.map(x => `
              <div class="shift-row">
                <span class="shift-name">${{x.name}}</span>
                <span class="shift-val down">${{(x.delta * 100).toFixed(1)}}%</span>
              </div>
            `).join("")}}
          </div>
        </div>
      `;
    }} else {{
      const topBase = Object.entries(c.predictions).sort((a,b) => b[1] - a[1]).slice(0, 8);
      shiftsHtml = `
        <div class="shifts-container" style="grid-template-columns: 1fr;">
          <div class="shift-col">
            <h4 style="color: var(--text-muted)">Baseline Prominent Moods</h4>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px;">
              ${{topBase.map(x => `
                <div class="shift-row">
                  <span class="shift-name">${{x[0]}}</span>
                  <span class="shift-val" style="color: var(--cyan);">${{(x[1] * 100).toFixed(1)}}%</span>
                </div>
              `).join("")}}
            </div>
          </div>
        </div>
      `;
    }}

    card.innerHTML = `
      <div class="card-header">
        <div class="card-title">${{c.action}}</div>
        <span class="card-tag ${{tagType}}">${{c.cond_id}}</span>
      </div>
      <div style="font-size: 0.85rem; color: var(--text-muted);">
        Weight: <strong>${{c.weight}}</strong> &bull; File: ${{c.aac_file}}
      </div>
      ${{shiftsHtml}}
    `;
    container.appendChild(card);
  }});
}}

function playClip(clip) {{
  const curTime = player.currentTime;
  const isPlaying = !player.paused;
  
  document.querySelectorAll(".card").forEach(el => el.classList.remove("active"));
  const card = document.getElementById("card_" + clip.cond_id);
  if (card) card.classList.add("active");

  pTrack.innerText = clip.aac_file;
  pAction.innerText = "(" + clip.action + ")";

  player.src = "mood_oppose/" + clip.aac_file;
  player.onloadedmetadata = () => {{
    player.currentTime = curTime;
    if (isPlaying || curTime > 0) player.play();
  }};
  currentAac = clip.aac_file;
}}

function switchPrompt(pid) {{
  currentPrompt = pid;
  document.querySelectorAll(".tab-btn").forEach((b, idx) => {{
    b.classList.toggle("active", (idx === 0 && pid === "prompt_melodic") || (idx === 1 && pid === "prompt_dark"));
  }});
  document.getElementById("cardsPromptA").style.display = pid === "prompt_melodic" ? "grid" : "none";
  document.getElementById("cardsPromptB").style.display = pid === "prompt_dark" ? "grid" : "none";
  renderTable();
}}

function renderTable() {{
  const thead = document.getElementById("moodTableHead");
  const tbody = document.getElementById("moodTableBody");
  const clips = DATA.clips.filter(c => c.prompt_id === currentPrompt);
  const baseClip = clips.find(c => c.cond_id === "base");

  let hHtml = "<tr><th>Emotion Tag</th>";
  clips.forEach(c => {{
    hHtml += `<th>${{c.cond_id}}<br><span style="font-weight: 400; font-size: 0.75rem; color: var(--text-muted);">${{c.weight >= 0 ? 'g=' + c.weight : 'g=' + c.weight}}</span></th>`;
  }});
  hHtml += "</tr>";
  thead.innerHTML = hHtml;

  let bHtml = "";
  DATA.classes.forEach(cls => {{
    bHtml += `<tr data-class="${{cls}}"><td><strong>${{cls}}</strong></td>`;
    clips.forEach(c => {{
      const val = c.predictions[cls];
      const baseVal = baseClip.predictions[cls];
      const delta = val - baseVal;
      let dStr = "";
      if (c.cond_id !== "base") {{
        const sign = delta >= 0 ? "+" : "";
        const cl = delta >= 0 ? "val-up" : "val-down";
        dStr = `<br><span class="${{cl}}" style="font-size: 0.75rem;">${{sign}}${{(delta * 100).toFixed(1)}}%</span>`;
      }}
      bHtml += `<td class="num-cell">${{(val * 100).toFixed(1)}}%${{dStr}}</td>`;
    }});
    bHtml += "</tr>";
  }});
  tbody.innerHTML = bHtml;
}}

function filterTable() {{
  const q = document.getElementById("filterInput").value.toLowerCase();
  document.querySelectorAll("#moodTableBody tr").forEach(tr => {{
    const cls = tr.getAttribute("data-class").toLowerCase();
    tr.style.display = cls.includes(q) ? "" : "none";
  }});
}}

// Init
renderCards("prompt_melodic", "cardsPromptA");
renderCards("prompt_dark", "cardsPromptB");
renderTable();

// Auto-select first clip
const firstClip = DATA.clips.find(c => c.prompt_id === "prompt_melodic");
if (firstClip) {{
  player.src = "mood_oppose/" + firstClip.aac_file;
  pTrack.innerText = firstClip.aac_file;
  pAction.innerText = "(" + firstClip.action + ")";
}}
</script>

</body>
</html>
"""
    with open(OUT_HTML, "w") as f:
        f.write(html_content)
    print(f"Interactive dashboard written to: {OUT_HTML} ({OUT_HTML.stat().st_size / 1024:.1f} KB)")

if __name__ == "__main__":
    main()
