#!/usr/bin/env python3
"""build_mood_oppose_page.py -- Builds listening evaluation page for mood reinforcement & opposition study.
Follows docs/eval-page-standard.md and site/reference.html (evals.css + Misc/float_player.py + Misc/comment_notes_block.py).
Outputs: /home/kim/evals_aac/mood_oppose.html and /home/kim/evals_aac/mood_oppose/run_meta.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/kim/Projects/SAO/Misc")
from comment_notes_block import notes_block  # noqa: E402
from float_player import inject  # noqa: E402

AAC_DIR = Path("/home/kim/evals_aac/mood_oppose")
JSON_PATH = AAC_DIR / "mood_56d_predictions.json"
OUT_HTML = Path("/home/kim/evals_aac/mood_oppose.html")
RUN_META_JSON = AAC_DIR / "run_meta.json"


def write_run_meta(n_clips):
    existing_feedback = None
    if RUN_META_JSON.exists():
        try:
            existing_feedback = json.loads(RUN_META_JSON.read_text()).get("kim_feedback")
        except Exception:
            existing_feedback = None
    meta = {
        "purpose": "Compare positive mood reinforcement, cross-mood opposition, and negated gradient (-grad) steering across all 56 Essentia mtg_jamendo_moodtheme dimensions on 2 prompts (Prompt A: Melodic Goa, Prompt B: Dark Psytrance).",
        "hypothesis": "Test how sparse 3-tag reinforcement vs cross-mood opposition vs negative gradient steering shifts all 56 Essentia mood dimensions on Stable Audio 3 Medium Base.",
        "recipe": {
            "script": "eval/build_mood_oppose_page.py",
            "n_prompts": 2,
            "n_seeds_per_prompt": 1,
            "n_clips": n_clips,
            "backbone": "sa3_medium_base",
            "head": "56-dim Essentia mtg_jamendo_moodtheme LatCH ep40 (val loss 0.0598)",
            "baseline_g0_source": "unguided generate() (NOT guided sampler at gain=0; carries MASTER section 5 baseline confound)",
            "disintegration_gate": "not run on this page"
        },
        "result": f"{n_clips} clips rendered across 2 prompts (1 seed per prompt; n=1 per cell, not established). Full 56-dim Essentia predictions recorded in mood_56d_predictions.json.",
        "kim_feedback": existing_feedback
    }
    RUN_META_JSON.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def main():
    with open(JSON_PATH) as f:
        data = json.load(f)

    classes = data["classes"]
    clips = data["clips"]

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

    write_run_meta(len(clips))
    notes_html = notes_block("mood_oppose", levels=[("clip", "this clip"), ("page", "page")],
                             hint="click a card to play, then record a listening note")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LatCH Mood Steering: Reinforcement &amp; Opposition — Evals</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="evals.css">
<style>
  .wrap {{ max-width: 1360px; }}
  .caveat-box {{
    background: #fff8f6; border: 1px solid var(--rule); border-left: 3px solid #b42318;
    padding: 10px 14px; margin: 10px 0 16px 0; font-size: 12px; line-height: 1.6; color: var(--body);
  }}
  .caveat-box b {{ color: var(--ink); }}
  .meta-strip {{
    display: flex; flex-wrap: wrap; gap: 16px;
    padding: 8px 12px; background: var(--paper-dim); border: 1px solid var(--rule);
    font-size: 11px; color: var(--dim); margin: 12px 0 16px 0;
  }}
  .meta-strip b {{ color: var(--ink); }}
  .tabs {{ display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }}
  .tab-btn {{
    padding: 8px 14px; background: var(--paper-dim); border: 1px solid var(--rule);
    color: var(--ink); font-family: var(--mono); font-size: 11px; font-weight: 500;
    cursor: pointer;
  }}
  .tab-btn:hover {{ border-color: var(--edge); }}
  .tab-btn.active {{
    background: #e6f4f3; color: var(--edge-ink);
    border-color: var(--edge); border-top: 2px solid var(--edge); font-weight: 600;
  }}
  .card-grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: 12px; margin-bottom: 24px;
  }}
  .cell.card {{
    background: var(--paper-dim); border: 1px solid var(--rule);
    padding: 12px 14px; display: flex; flex-direction: column; gap: 8px; cursor: pointer; text-align: left;
  }}
  .card-header {{ display: flex; justify-content: space-between; align-items: flex-start; }}
  .card-title {{ font-size: 12px; font-weight: 600; color: var(--ink); }}
  .card-tag {{
    font-size: 10px; font-weight: 600; padding: 1px 6px;
    border: 1px solid var(--rule); background: var(--paper); color: var(--dim);
  }}
  .card-tag.reinforce {{ border-color: var(--edge); color: var(--edge-ink); }}
  .card-tag.oppose {{ border-color: #9e2a2b; color: #9e2a2b; }}

  .shifts-container {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
    font-size: 10px; background: var(--paper); padding: 8px; border: 1px solid var(--rule-light);
  }}
  .shift-col h4 {{
    font-size: 9px; text-transform: uppercase; letter-spacing: 0.06em; margin: 0 0 4px 0; color: var(--dim);
  }}
  .shift-row {{
    display: flex; justify-content: space-between; padding: 2px 0;
    border-bottom: 1px solid var(--rule-light); font-variant-numeric: tabular-nums;
  }}
  .shift-row:last-child {{ border-bottom: none; }}
  .shift-val.up {{ color: var(--edge-ink); font-weight: 600; }}
  .shift-val.down {{ color: #9e2a2b; font-weight: 600; }}

  .table-section {{
    margin-top: 22px; border: 1px solid var(--rule); padding: 12px 14px;
  }}
  .table-controls {{ margin-bottom: 10px; }}
  .table-controls input {{
    background: var(--paper-dim); border: 1px solid var(--rule); padding: 6px 10px;
    color: var(--ink); font-family: var(--mono); font-size: 11px; width: 280px;
  }}
  .table-scroll {{ overflow-x: auto; max-height: 480px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 11px; text-align: left; }}
  th, td {{ padding: 6px 8px; border-bottom: 1px solid var(--rule-light); border-right: 1px solid var(--rule-light); white-space: nowrap; }}
  th {{
    background: var(--paper-dim); position: sticky; top: 0; z-index: 10;
    font-size: 10px; font-weight: 600; text-transform: uppercase; color: var(--dim); border-bottom: 1px solid var(--rule);
  }}
  .num-cell {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .val-up {{ color: var(--edge-ink); }}
  .val-down {{ color: #9e2a2b; }}
</style>
</head>
<body>
<div class="wrap">
  <p class="over">VIBE ON THE EDG3 · EVALS</p>
  <p class="nav"><a href="index.html">← all evals</a></p>

  <h1>LatCH Mood Steering: Reinforcement, Opposition &amp; 56-Dim Predictions <span class="unaudited" title="No listening verdict recorded yet (unaudited).">&#10071;</span></h1>
  <p>
    <b>What this tests and why.</b> This page inspects how positive reinforcement, cross-mood opposition, and negative gradient steering (<code>-grad</code>) move all 56 Essentia <code>mtg_jamendo_moodtheme</code> dimensions on 2 contrasting prompts (Prompt A: Melodic Goa; Prompt B: Dark Psytrance). Related pages: <a href="mood_finegrained.html">mood_finegrained.html</a> tests an 8-model &times; 9-target weight ladder, and <a href="choice_clips_mood.html">choice_clips_mood.html</a> tests the 56-dim mood probe across 6 choice models.
  </p>

  <div class="caveat-box">
    <b>Scope, Baseline &amp; Disintegration Gate Disclosures (Not Established):</b>
    <ul style="margin:5px 0 0 18px;">
      <li><b>Sample size (not established):</b> This diagnostic uses 2 prompts &times; 1 seed each (<code>n = 1</code> per card). Single-seed observations on 2 prompts are <b>not established</b>.</li>
      <li><b>Disintegration gate not run on this page:</b> <code>control_head_disintegration_eval.gate()</code> has not been run on these clips, so this page does <b>not</b> establish a usable gain range.</li>
      <li><b>Unguided <code>g=0</code> baseline confound (MASTER &sect;5):</b> The <code>base (g=0)</code> clips were generated with unguided <code>generate()</code> rather than the guided sampler at <code>gain=0</code>.</li>
    </ul>
  </div>

  <div class="meta-strip">
    <span>Prompts: <b>2 (n=1 seed per prompt)</b></span>
    <span>Classifier: <b>Essentia Discogs-EffNet &rarr; MTG-Jamendo MoodTheme (56 dims)</b></span>
    <span>Backbone: <b>Stable Audio 3 Medium Base</b></span>
    <span>Head: <b>ep40 (val loss 0.0598)</b></span>
    <span>Playhead: <b>Preserved across clip switches · Re-click pauses</b></span>
  </div>

  <div class="tabs">
    <button class="tab-btn active" onclick="switchPrompt('prompt_melodic')">Prompt A: Melodic Goa (n=1 seed)</button>
    <button class="tab-btn" onclick="switchPrompt('prompt_dark')">Prompt B: Dark Psytrance (n=1 seed)</button>
  </div>

  <div id="cardsPromptA" class="card-grid"></div>
  <div id="cardsPromptB" class="card-grid" style="display: none;"></div>

  <div class="table-section">
    <h2><span class="mark">&sect;</span> Complete 56-Dimensional Predictions &amp; Delta Matrix (n=1 seed per prompt)</h2>
    <p class="dim">Measured Essentia classifier scores (%) and delta vs. unguided <code>g=0</code> baseline.</p>
    <div class="table-controls">
      <input type="text" id="filterInput" placeholder="Filter channel (e.g. dark, melodic, space)..." onkeyup="filterTable()">
    </div>
    <div class="table-scroll">
      <table id="moodTable">
        <thead id="moodTableHead"></thead>
        <tbody id="moodTableBody"></tbody>
      </table>
    </div>
  </div>

  {notes_html}
</div>

<audio id="globalPlayer" preload="auto" style="display:none"></audio>

<script>
const DATA = {json.dumps(data)};
let currentPrompt = "prompt_melodic";
let currentAac = null;
let lastKnownTime = 0;
const player = document.getElementById("globalPlayer");

player.addEventListener("timeupdate", () => {{
  if (player.currentTime > 0 && !player.ended) lastKnownTime = player.currentTime;
}});
player.addEventListener("ended", () => {{
  lastKnownTime = 0;
  document.querySelectorAll(".cell.card").forEach(el => el.classList.remove("playing"));
}});

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
    card.className = "cell card";
    card.id = "card_" + c.prompt_id + "_" + c.cond_id;
    card.dataset.src = "mood_oppose/" + c.aac_file;
    card.onclick = () => playClip(c);

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
            <h4>Elevated</h4>
            ${{topUp.map(x => `
              <div class="shift-row">
                <span class="shift-name">${{x.name}}</span>
                <span class="shift-val up">+${{(x.delta * 100).toFixed(1)}}%</span>
              </div>
            `).join("")}}
          </div>
          <div class="shift-col down">
            <h4>Suppressed</h4>
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
            <h4>Baseline Top Channels (g=0)</h4>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px;">
              ${{topBase.map(x => `
                <div class="shift-row">
                  <span class="shift-name">${{x[0]}}</span>
                  <span class="shift-val up">${{(x[1] * 100).toFixed(1)}}%</span>
                </div>
              `).join("")}}
            </div>
          </div>
        </div>
      `;
    }}

    card.innerHTML = `
      <div class="card-header">
        <div class="card-title">&#9654; ${{c.action}}</div>
        <span class="card-tag ${{tagType}}">${{c.cond_id}}</span>
      </div>
      <div style="font-size: 10px; color: var(--dim);">
        Weight: <b>${{c.weight}}</b> · File: ${{c.aac_file}}
      </div>
      ${{shiftsHtml}}
    `;
    container.appendChild(card);
  }});
}}

function playClip(clip) {{
  if (window.noteSet) noteSet({{model: clip.prompt_id, ckpt: clip.cond_id, clip: clip.aac_file}});
  const card = document.getElementById("card_" + clip.prompt_id + "_" + clip.cond_id);
  if (currentAac === clip.aac_file) {{
    if (player.paused) {{
      player.play();
      if (card) card.classList.add("playing");
    }} else {{
      player.pause();
      if (card) card.classList.remove("playing");
    }}
    return;
  }}

  const curTime = (player.currentTime > 0 && !player.ended) ? player.currentTime : lastKnownTime;

  document.querySelectorAll(".cell.card").forEach(el => el.classList.remove("playing"));
  if (card) card.classList.add("playing");

  player.src = "mood_oppose/" + clip.aac_file;
  const go = () => {{
    if (curTime > 0) {{
      try {{ player.currentTime = Math.min(curTime, (player.duration || 20.0) - 0.05); }} catch(e) {{}}
    }}
    player.play().catch(e => console.log(e));
  }};
  if (player.readyState >= 1) go();
  else player.addEventListener("loadedmetadata", go, {{ once: true }});
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

  let hHtml = "<tr><th>Channel</th>";
  clips.forEach(c => {{
    hHtml += `<th>${{c.cond_id}}<br><span style="font-weight: 400; font-size: 9px; color: var(--dim);">g=${{c.weight}}</span></th>`;
  }});
  hHtml += "</tr>";
  thead.innerHTML = hHtml;

  let bHtml = "";
  DATA.classes.forEach(cls => {{
    bHtml += `<tr data-class="${{cls}}"><td><b>${{cls}}</b></td>`;
    clips.forEach(c => {{
      const val = c.predictions[cls];
      const baseVal = baseClip.predictions[cls];
      const delta = val - baseVal;
      let dStr = "";
      if (c.cond_id !== "base") {{
        const sign = delta >= 0 ? "+" : "";
        const cl = delta >= 0 ? "val-up" : "val-down";
        dStr = `<br><span class="${{cl}}" style="font-size: 9px;">${{sign}}${{(delta * 100).toFixed(1)}}%</span>`;
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

renderCards("prompt_melodic", "cardsPromptA");
renderCards("prompt_dark", "cardsPromptB");
renderTable();
</script>
</body>
</html>
"""
    html_content = inject(html_content)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Interactive dashboard written to: {OUT_HTML} ({OUT_HTML.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
