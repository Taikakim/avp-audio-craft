#!/usr/bin/env python3
# Last edited: WINTERMUTE 2026-11-03 -- chroma head is 384-dim; link to the finished 15-prompt run
"""build_mood_eval_page.py -- builds the listening evaluation page
for the 56-dim continuous Mood LatCH conditioning head (ep40 & ep40_ema0.25) across 6 representative models.
Follows docs/eval-page-standard.md and site/reference.html (evals.css + Misc/float_player.py + Misc/comment_notes_block.py).
Outputs: /home/kim/evals_aac/choice_clips_mood.html and /home/kim/evals_aac/choice_clips_mood/run_meta.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/kim/Projects/SAO/Misc")
from comment_notes_block import notes_block  # noqa: E402
from float_player import inject  # noqa: E402

AAC_DIR = Path("/home/kim/evals_aac/choice_clips_mood")
OUT_HTML = Path("/home/kim/evals_aac/choice_clips_mood.html")
RUN_META_JSON = AAC_DIR / "run_meta.json"
PLAN_ITEMS_FILE = Path(__file__).resolve().parent / "choice_clips_plan_items.json"


def btn(stem, label, idx, model, ckpt, cond, head_tag=""):
    exists = (AAC_DIR / stem).exists()
    status_cls = "ready" if exists else "pending"
    url = f"choice_clips_mood/{stem}"
    title_attr = f'title="{stem}"'
    sub_span = f'<span class="sub">{head_tag}</span>' if head_tag else ''
    return f"""<button class="cell play-btn {status_cls}" data-src="{url}" onclick="playAudio('{stem}', this, {idx}, '{model}', '{ckpt}', '{cond}')" {title_attr}>
        <span class="icon">&#9654;</span> <span class="lbl">{label}</span>{sub_span}
    </button>"""


def write_run_meta():
    existing_feedback = None
    if RUN_META_JSON.exists():
        try:
            existing_feedback = json.loads(RUN_META_JSON.read_text()).get("kim_feedback")
        except Exception:
            existing_feedback = None
    meta = {
        "purpose": "Compare the 56-dim Essentia mtg_jamendo_moodtheme LatCH probe at ep40 (val loss 0.0598) vs ep40_ema0.25 across 6 representative model families (rows 02, 05, 07, 11, 22, 28 of the choice clips table) at g=1024 and g=2048.",
        "hypothesis": "Test whether the 56-dim mood probe steers Space, Dark, Melodic, and Aliens HQ time-series targets across different LoRA/DoRA/Full-FT models, and compare standard EMA vs fast EMA (0.25).",
        "recipe": {
            "script": "eval/build_mood_eval_page.py",
            "n_rows": 6,
            "n_seeds_per_cell": 1,
            "weights": [0, 1024, 2048],
            "heads": ["ep40 (val 0.0598)", "ep40_ema0.25"],
            "targets": ["Space", "Dark", "Melodic", "Aliens"],
            "sampler": "euler (24 steps, 20.0s)",
            "baseline_g0_source": "unguided generate() (NOT guided sampler at gain=0; carries MASTER section 5 baseline confound)",
            "disintegration_gate": "not run on this page"
        },
        "result": "102 clips rendered across 6 model rows (1 prompt and 1 seed per row; per-row comparisons are n=1 and not established). Ready for listening.",
        "kim_feedback": existing_feedback
    }
    RUN_META_JSON.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def main():
    AAC_DIR.mkdir(parents=True, exist_ok=True)
    with open(PLAN_ITEMS_FILE) as f:
        all_items = json.load(f)

    selected_rows = [2, 5, 7, 11, 22, 28]
    items = [it for it in all_items if it["idx"] in selected_rows]

    rows_html = []
    for item in items:
        idx = item["idx"]
        label = item["label"]
        model = item["model"]
        ckpt = item["ckpt_tag"]
        prompt = item["prompt_text"]
        seed = item["seed"]
        cfg = item["cfg"]
        strength = item["strength"]

        base_stem = f"mood_row{idx:02d}__{model}__{ckpt}__base__s{seed}.m4a"

        targets = [
            ("Space", "Space (space=1.0, soundscape=0.3, dream=0.3)"),
            ("Dark", "Dark (dark=1.0, heavy=0.4, deep=0.3)"),
            ("Melodic", "Melodic (melodic=1.0, uplifting=0.4, happy=0.3)"),
            ("Aliens", "Aliens HQ (20s Essentia TS, sample 6073122)")
        ]
        heads = [("ep40", "ep40 (val 0.0598)"), ("ep40_ema0.25", "ep40 EMA 0.25")]

        target_blocks = []
        for tgt_id, tgt_title in targets:
            head_cols = []
            for head_id, head_lbl in heads:
                stem_1024 = f"mood_row{idx:02d}__{model}__{ckpt}__{head_id}__{tgt_id}_g1024__s{seed}.m4a"
                stem_2048 = f"mood_row{idx:02d}__{model}__{ckpt}__{head_id}__{tgt_id}_g2048__s{seed}.m4a"
                head_cols.append(f"""
                <div class="head-col">
                    <div class="head-badge">{head_lbl}</div>
                    <div class="btn-group">
                        {btn(stem_1024, 'g=1024', idx, model, ckpt, f'{tgt_id}_{head_id}_1024')}
                        {btn(stem_2048, 'g=2048', idx, model, ckpt, f'{tgt_id}_{head_id}_2048')}
                    </div>
                </div>
                """)

            target_blocks.append(f"""
            <div class="target-section">
                <div class="target-title">{tgt_title}</div>
                <div class="heads-grid">
                    {''.join(head_cols)}
                </div>
            </div>
            """)

        rows_html.append(f"""
        <tr class="clip-row" id="row-{idx}">
            <td class="idx-cell">{idx:02d}</td>
            <td class="meta-cell">
                <div class="model-title">{label}</div>
                <div class="meta-badges">
                    <span class="badge">CFG {cfg}</span>
                    <span class="badge">w {strength}</span>
                    <span class="badge">Seed {seed} (n=1)</span>
                    <span class="badge">20.0s</span>
                </div>
                <div class="prompt-text" title="{prompt}">{prompt}</div>
                <div class="base-container">
                    <span class="base-lbl">Unguided gen() (g=0):</span>
                    {btn(base_stem, 'Base (g=0)', idx, model, ckpt, 'base')}
                </div>
            </td>
            <td class="eval-grid-cell">
                <div class="targets-container">
                    {''.join(target_blocks)}
                </div>
            </td>
        </tr>
        """)

    write_run_meta()
    notes_html = notes_block("choice_clips_mood", levels=[("clip", "this clip"), ("page", "page")],
                             hint="click a clip, then record a listening note")

    table_rows = "".join(rows_html)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>56-dim Mood LatCH Choice Clips — Evals</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="evals.css">
<style>
.wrap {{ max-width: 1460px; }}
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
.table-container {{ border: 1px solid var(--rule); overflow-x: auto; margin-bottom: 20px; }}
table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 11px; }}
th {{
    background: var(--paper-dim); padding: 8px 12px; font-size: 10px; font-weight: 600;
    text-transform: uppercase; color: var(--dim); border-bottom: 1px solid var(--rule); letter-spacing: 0.05em;
}}
.clip-row {{ border-bottom: 1px solid var(--rule); }}
.idx-cell {{
    padding: 12px; font-size: 13px; font-weight: 600; color: var(--edge-ink);
    vertical-align: top; width: 44px; text-align: center; border-right: 1px solid var(--rule-light);
    background: var(--paper-dim);
}}
.meta-cell {{
    padding: 12px 14px; width: 340px; vertical-align: top;
    border-right: 1px solid var(--rule); background: var(--paper-dim);
}}
.model-title {{ font-size: 12px; font-weight: 600; color: var(--ink); margin-bottom: 6px; }}
.meta-badges {{ display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }}
.badge {{
    font-size: 10px; background: var(--paper); border: 1px solid var(--rule);
    color: var(--dim); padding: 1px 5px;
}}
.prompt-text {{
    font-size: 11px; color: var(--body); line-height: 1.45; margin-bottom: 10px;
    background: var(--paper); padding: 6px 8px; border: 1px solid var(--rule-light);
}}
.base-container {{
    display: flex; align-items: center; gap: 8px;
    background: var(--paper); padding: 6px 8px; border: 1px solid var(--rule);
}}
.base-lbl {{ font-size: 10px; font-weight: 600; color: var(--dim); text-transform: uppercase; }}
.eval-grid-cell {{ padding: 10px 12px; vertical-align: top; }}
.targets-container {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }}
.target-section {{
    background: var(--paper-dim); border: 1px solid var(--rule);
    padding: 8px 10px;
}}
.target-title {{
    font-size: 11px; font-weight: 600; color: var(--ink);
    margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid var(--rule-light);
}}
.heads-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }}
.head-col {{ background: var(--paper); border: 1px solid var(--rule-light); padding: 6px; }}
.head-badge {{
    font-size: 9px; font-weight: 600; text-transform: uppercase; text-align: center;
    padding: 2px 4px; margin-bottom: 6px; color: var(--dim); background: var(--paper-dim);
    border: 1px solid var(--rule-light);
}}
.btn-group {{ display: flex; flex-direction: column; gap: 4px; }}
.cell.play-btn {{
    font-family: var(--mono); padding: 5px 8px; font-size: 11px; font-weight: 500;
    display: flex; align-items: center; justify-content: center; gap: 4px;
}}
.cell.play-btn.pending {{ opacity: 0.35; cursor: not-allowed; border-style: dashed; }}
</style>
</head>
<body>
<div class="wrap">
<p class="over">VIBE ON THE EDG3 · EVALS</p>
<p class="nav"><a href="index.html">← all evals</a></p>

<h1>56-dim Mood LatCH Conditioning across 6 Choice Models (ep40 &amp; ep40_ema0.25) <span class="unaudited" title="No listening verdict recorded yet (unaudited).">&#10071;</span></h1>

<p>
  <b>What this tests and why.</b> This page auditions test-time guidance with the 56-class Essentia <code>mtg_jamendo_moodtheme</code> LatCH probe (<code>ep40</code> validation loss <code>0.0598</code> vs. fast iterate <code>ep40_ema0.25</code>) across 6 representative model families from the choice clips set at <code>g=1024</code> and <code>g=2048</code>. For a finer gain sweep (<code>g=0..8192</code>) and de-confounded targets on a single prompt, see <a href="mood_finegrained.html">mood_finegrained.html</a>; for mood reinforcement vs. opposition see <a href="mood_oppose.html">mood_oppose.html</a>; for the 384-dim chroma head on the same 6 models see <a href="ep10_vs_ep40_chroma.html">ep10_vs_ep40_chroma.html</a>.
</p>

<div class="caveat-box">
  <b>Scope, Baseline &amp; Disintegration Gate Disclosures (Not Established):</b>
  <ul style="margin:5px 0 0 18px;">
    <li><b>Sample size (not established per row):</b> Each of the 6 model rows below is rendered on 1 prompt and 1 seed (<code>n = 1</code> per row &times; condition cell). Single-seed rows do not establish per-adapter or per-prompt performance.</li>
    <li><b>Disintegration gate not run on this page:</b> <code>control_head_disintegration_eval.gate()</code> has not been run on these clips, so this page does <b>not</b> establish a usable gain range. Informally, the range of useful weight varies across adapters and source material, and <code>Aliens HQ</code> produces very small changes on Goa tracks whose unguided mood profile is already nearly collinear with the target.</li>
    <li><b>Unguided <code>g=0</code> baseline confound (MASTER &sect;5):</b> The <code>Base (g=0)</code> clips were generated with unguided <code>generate()</code> rather than the guided sampler at <code>gain=0</code>.</li>
  </ul>
</div>

<div class="meta-strip">
  <span>Rows: <b>6 models (n=1 prompt/seed per row)</b></span>
  <span>Heads: <b>ep40 (val 0.0598) · ep40_ema0.25</b></span>
  <span>Targets: <b>Space · Dark · Melodic · Aliens HQ</b></span>
  <span>Weights: <b>g=1024 · g=2048</b></span>
  <span>Clips: <b>20.0s (24 Euler steps, 256k AAC)</b></span>
  <span>Playhead: <b>Preserved across clip switches · Re-click pauses</b></span>
</div>

<div class="table-container">
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Model &amp; Prompt (n=1 seed per row)</th>
        <th>Mood Guidance Matrix (Space · Dark · Melodic · Aliens HQ)</th>
      </tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>
</div>

{notes_html}
</div>

<audio id="audio-player" preload="auto" style="display:none"></audio>

<script>
const audio = document.getElementById('audio-player');
let currentBtn = null;
let currentStem = null;
let lastKnownTime = 0;

function playAudio(stem, btnEl, rowIdx, model, ckpt, condLabel) {{
    if (btnEl.classList.contains('pending')) return;
    if (window.noteSet) noteSet({{model: model, ckpt: ckpt, clip: stem}});

    if (currentBtn === btnEl) {{
        if (audio.paused) {{
            audio.play();
            btnEl.classList.add('playing');
            btnEl.querySelector('.icon').innerHTML = '||';
        }} else {{
            audio.pause();
            btnEl.classList.remove('playing');
            btnEl.querySelector('.icon').innerHTML = '&#9654;';
        }}
        return;
    }}

    const targetTime = (audio.currentTime > 0 && !audio.ended) ? audio.currentTime : lastKnownTime;

    if (currentBtn) {{
        currentBtn.classList.remove('playing');
        currentBtn.querySelector('.icon').innerHTML = '&#9654;';
    }}

    currentBtn = btnEl;
    currentStem = stem;

    audio.src = 'choice_clips_mood/' + stem;
    const go = () => {{
        if (targetTime > 0) {{
            try {{ audio.currentTime = Math.min(targetTime, (audio.duration || 20.0) - 0.05); }} catch (e) {{}}
        }}
        audio.play().catch(e => console.error(e));
    }};
    if (audio.readyState >= 1) go();
    else audio.addEventListener('loadedmetadata', go, {{ once: true }});

    btnEl.classList.add('playing');
    btnEl.querySelector('.icon').innerHTML = '||';
}}

audio.addEventListener('timeupdate', () => {{
    if (audio.currentTime > 0 && !audio.ended) lastKnownTime = audio.currentTime;
}});

audio.addEventListener('ended', () => {{
    lastKnownTime = 0;
    if (currentBtn) {{
        currentBtn.classList.remove('playing');
        currentBtn.querySelector('.icon').innerHTML = '&#9654;';
    }}
}});
</script>
</body>
</html>
"""
    html = inject(html)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"Built {OUT_HTML} ({len(html)} bytes)")


if __name__ == "__main__":
    main()
