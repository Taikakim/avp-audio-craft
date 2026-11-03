#!/usr/bin/env python3
"""build_choice_clips_page.py -- builds the listening page for
the 29 choice clips across Base (g0) and 3 chroma targets (C Major, Eb Major, Aliens HQ)
at three guidance weights (g1024, g2048, g3072).
Follows docs/eval-page-standard.md and site/reference.html (evals.css + Misc/float_player.py + Misc/comment_notes_block.py).
Outputs: /home/kim/evals_aac/choice_clips_chroma.html and /home/kim/evals_aac/choice_clips_chroma/run_meta.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/kim/Projects/SAO/Misc")
from comment_notes_block import notes_block  # noqa: E402
from float_player import inject  # noqa: E402

AAC_DIR = Path("/home/kim/evals_aac/choice_clips_chroma")
OUT_HTML = Path("/home/kim/evals_aac/choice_clips_chroma.html")
RUN_META_JSON = AAC_DIR / "run_meta.json"
PLAN_ITEMS_FILE = Path(__file__).resolve().parent / "choice_clips_plan_items.json"


def btn(stem, label, idx, model, ckpt, cond, sublabel=""):
    exists = (AAC_DIR / stem).exists()
    status_cls = "ready" if exists else "pending"
    url = f"choice_clips_chroma/{stem}"
    title_attr = f'title="{stem}"'
    sub_span = f'<span class="sub">({sublabel})</span>' if sublabel else ''
    return f"""<button class="cell play-btn {status_cls}" data-src="{url}" onclick="playAudio('{stem}', this, {idx}, '{model}', '{ckpt}', '{cond}')" {title_attr}>
        <span class="icon">&#9654;</span> <span class="lbl">{label}</span> {sub_span}
    </button>"""


def write_run_meta(n_rows):
    existing_feedback = None
    if RUN_META_JSON.exists():
        try:
            existing_feedback = json.loads(RUN_META_JSON.read_text()).get("kim_feedback")
        except Exception:
            existing_feedback = None
    meta = {
        "purpose": "Evaluate the 24-dim SAME-chroma LatCH probe (ep10, C3 lr 1e-3) across all 29 curated choice clip model/prompt configurations at g=1024 (0.5x), g=2048 (1.0x), and g=3072 (1.5x) on C Major, Eb Major, and Aliens HQ chroma targets.",
        "hypothesis": "Test how the 24-dim chroma probe steers chord roots and dynamic reference chroma across 29 diverse LoRA, DoRA, and Full-FT checkpoints.",
        "recipe": {
            "script": "eval/build_choice_clips_page.py",
            "n_rows": n_rows,
            "n_seeds_per_row": 1,
            "weights": [0, 1024, 2048, 3072],
            "head": "same_chroma_e13 (ep10, val loss 0.1345)",
            "targets": ["C Major", "Eb Major", "Aliens HQ"],
            "sampler": "euler (24 steps, 20.0s)",
            "baseline_g0_source": "unguided generate() (NOT guided sampler at gain=0; carries MASTER section 5 baseline confound)",
            "disintegration_gate": "not run on this page"
        },
        "result": f"{n_rows * 10} clips rendered across {n_rows} model/prompt rows (1 seed per row; n=1 per cell, not established). Ready for listening.",
        "kim_feedback": existing_feedback
    }
    RUN_META_JSON.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def main():
    AAC_DIR.mkdir(parents=True, exist_ok=True)
    if not PLAN_ITEMS_FILE.exists():
        print(f"Error: {PLAN_ITEMS_FILE} not found.")
        sys.exit(1)

    with open(PLAN_ITEMS_FILE) as f:
        items = json.load(f)

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

        base_stem = f"choice_{idx:02d}__{model}__{ckpt}__base__s{seed}.m4a"

        c_1024 = f"choice_{idx:02d}__{model}__{ckpt}__C_g1024__s{seed}.m4a"
        c_2048 = f"choice_{idx:02d}__{model}__{ckpt}__C__s{seed}.m4a"
        c_3072 = f"choice_{idx:02d}__{model}__{ckpt}__C_g3072__s{seed}.m4a"

        eb_1024 = f"choice_{idx:02d}__{model}__{ckpt}__Eb_g1024__s{seed}.m4a"
        eb_2048 = f"choice_{idx:02d}__{model}__{ckpt}__Eb__s{seed}.m4a"
        eb_3072 = f"choice_{idx:02d}__{model}__{ckpt}__Eb_g3072__s{seed}.m4a"

        aliens_1024 = f"choice_{idx:02d}__{model}__{ckpt}__Aliens_g1024__s{seed}.m4a"
        aliens_2048 = f"choice_{idx:02d}__{model}__{ckpt}__Aliens__s{seed}.m4a"
        aliens_3072 = f"choice_{idx:02d}__{model}__{ckpt}__Aliens_g3072__s{seed}.m4a"

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
            </td>
            <td class="audio-cell">
                <div class="target-grid">
                    <div class="target-row base-row">
                        <span class="target-tag base-tag">Unguided</span>
                        <div class="btn-ladder">
                            {btn(base_stem, 'Base (g=0, unguided gen)', idx, model, ckpt, 'base')}
                        </div>
                    </div>
                    <div class="target-row">
                        <span class="target-tag">C Major</span>
                        <div class="btn-ladder">
                            {btn(c_1024, '0.5x', idx, model, ckpt, 'C_1024', 'g1024')}
                            {btn(c_2048, '1.0x', idx, model, ckpt, 'C_2048', 'g2048')}
                            {btn(c_3072, '1.5x', idx, model, ckpt, 'C_3072', 'g3072')}
                        </div>
                    </div>
                    <div class="target-row">
                        <span class="target-tag">Eb Major</span>
                        <div class="btn-ladder">
                            {btn(eb_1024, '0.5x', idx, model, ckpt, 'Eb_1024', 'g1024')}
                            {btn(eb_2048, '1.0x', idx, model, ckpt, 'Eb_2048', 'g2048')}
                            {btn(eb_3072, '1.5x', idx, model, ckpt, 'Eb_3072', 'g3072')}
                        </div>
                    </div>
                    <div class="target-row">
                        <span class="target-tag">Aliens HQ</span>
                        <div class="btn-ladder">
                            {btn(aliens_1024, '0.5x', idx, model, ckpt, 'Aliens_1024', 'g1024')}
                            {btn(aliens_2048, '1.0x', idx, model, ckpt, 'Aliens_2048', 'g2048')}
                            {btn(aliens_3072, '1.5x', idx, model, ckpt, 'Aliens_3072', 'g3072')}
                        </div>
                    </div>
                </div>
            </td>
        </tr>
        """)

    write_run_meta(len(items))
    notes_html = notes_block("choice_clips_chroma", levels=[("clip", "this clip"), ("page", "page")],
                             hint="click a clip, then record a listening note")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Curated Choice Clips Chroma Guidance Matrix — Evals</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="evals.css">
    <style>
        .wrap {{ max-width: 1420px; }}
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
        .matrix-table {{
            width: 100%; border-collapse: collapse;
            border: 1px solid var(--rule); font-size: 11px; margin-bottom: 20px;
        }}
        .matrix-table th {{
            background: var(--paper-dim); color: var(--dim); padding: 8px 12px;
            text-align: left; font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em;
            border-bottom: 1px solid var(--rule);
        }}
        .matrix-table td {{
            padding: 10px 12px; border-bottom: 1px solid var(--rule-light); vertical-align: top;
        }}
        .idx-cell {{
            font-weight: 600; color: var(--edge-ink); font-size: 13px; width: 38px;
            text-align: center; background: var(--paper-dim); border-right: 1px solid var(--rule-light);
        }}
        .meta-cell {{ width: 44%; background: var(--paper-dim); border-right: 1px solid var(--rule); }}
        .model-title {{ color: var(--ink); font-weight: 600; font-size: 12px; margin-bottom: 4px; }}
        .meta-badges {{ display: flex; gap: 4px; margin-bottom: 6px; flex-wrap: wrap; }}
        .badge {{
            background: var(--paper); color: var(--dim); border: 1px solid var(--rule);
            padding: 1px 5px; font-size: 10px;
        }}
        .prompt-text {{
            font-size: 11px; color: var(--body); line-height: 1.4;
            background: var(--paper); padding: 6px 8px; border: 1px solid var(--rule-light);
        }}
        .audio-cell {{ width: 52%; }}
        .target-grid {{ display: flex; flex-direction: column; gap: 5px; }}
        .target-row {{
            display: flex; align-items: center; gap: 8px;
            background: var(--paper-dim); border: 1px solid var(--rule-light); padding: 4px 8px;
        }}
        .target-row.base-row {{ border-color: var(--rule); }}
        .target-tag {{
            font-size: 10px; font-weight: 600; color: var(--ink);
            width: 78px; flex-shrink: 0; text-transform: uppercase; letter-spacing: 0.04em;
        }}
        .target-tag.base-tag {{ color: var(--edge-ink); }}
        .btn-ladder {{ display: flex; gap: 6px; flex-grow: 1; }}
        .cell.play-btn {{
            font-family: var(--mono); padding: 4px 8px; font-size: 11px; font-weight: 500;
            display: flex; align-items: center; justify-content: center;
            gap: 4px; flex: 1;
        }}
        .cell.play-btn .sub {{ font-size: 9px; color: var(--dim); display: inline; margin: 0; }}
        .cell.play-btn.pending {{ opacity: 0.35; cursor: not-allowed; border-style: dashed; }}
    </style>
</head>
<body>
<div class="wrap">
    <p class="over">VIBE ON THE EDG3 · EVALS</p>
    <p class="nav"><a href="index.html">← all evals</a></p>

    <h1>Curated Choice Clips Chroma Guidance Matrix (29 Models &times; 10 Conditions) <span class="unaudited" title="No listening verdict recorded yet (unaudited).">&#10071;</span></h1>
    <p>
        <b>What this tests and why.</b> This page auditions 29 choice models across Base (<code>g=0</code>) and 3 chroma targets (<code>C Major</code>, <code>Eb Major</code>, <code>Aliens HQ</code>) at <code>0.5x (g=1024)</code>, <code>1.0x (g=2048)</code>, and <code>1.5x (g=3072)</code> using the <code>same_chroma_e13</code> probe (<code>ep10</code>). Related pages: <a href="ep10_vs_ep40_chroma.html">ep10_vs_ep40_chroma.html</a> compares <code>ep10</code> against the 40-epoch retrain (<code>ep40</code>) on 6 of these rows, and <a href="choice_clips_mood.html">choice_clips_mood.html</a> / <a href="mood_finegrained.html">mood_finegrained.html</a> test the 56-dim mood probe.
    </p>

    <div class="caveat-box">
        <b>Scope, Baseline &amp; Disintegration Gate Disclosures (Not Established):</b>
        <ul style="margin:5px 0 0 18px;">
            <li><b>Sample size (not established per row):</b> Each of the 29 rows below uses 1 prompt and 1 seed (<code>n = 1</code> per row &times; condition cell). Single-seed rows do not establish per-adapter or per-prompt performance.</li>
            <li><b>Disintegration gate not run on this page:</b> <code>control_head_disintegration_eval.gate()</code> has not been run on these clips, so this page does <b>not</b> establish a usable gain range. Informally, useful guidance weight varies depending on the adapter and source material.</li>
            <li><b>Unguided <code>g=0</code> baseline confound (MASTER &sect;5):</b> The <code>Base (g=0)</code> clips were generated with unguided <code>generate()</code> rather than the guided sampler at <code>gain=0</code>.</li>
        </ul>
    </div>

    <div class="meta-strip">
        <span>Rows: <b>29 models (n=1 prompt/seed per row)</b></span>
        <span>Head: <b>same_chroma_e13 (C3, lr 1e-3, ep10)</b></span>
        <span>Clips: <b>20.0s (280 frames, 24 Euler steps, 256k AAC)</b></span>
        <span>Playhead: <b>Preserved across clip switches · Re-click pauses</b></span>
    </div>

    <table class="matrix-table">
        <thead>
            <tr>
                <th>#</th>
                <th>Model, Recipe &amp; Prompt (n=1 seed per row)</th>
                <th>Audio Conditions &amp; Guidance Ladders (0.5x g1024 · 1.0x g2048 · 1.5x g3072)</th>
            </tr>
        </thead>
        <tbody>
            {"".join(rows_html)}
        </tbody>
    </table>

    {notes_html}
</div>

<audio id="global-audio" preload="auto" style="display:none"></audio>

<script>
    const audio = document.getElementById('global-audio');
    let currentBtn = null;
    let currentFile = null;
    let lastKnownTime = 0;

    audio.addEventListener('timeupdate', () => {{
        if (audio.currentTime > 0 && !audio.ended) lastKnownTime = audio.currentTime;
    }});

    function playAudio(filename, btn, idx, model, ckpt, cond) {{
        if (btn.classList.contains('pending')) return;
        if (window.noteSet) noteSet({{model: model, ckpt: ckpt, clip: filename}});

        if (currentBtn === btn) {{
            if (audio.paused) {{
                audio.play();
                btn.classList.add('playing');
                btn.querySelector('.icon').innerHTML = '||';
            }} else {{
                audio.pause();
                btn.classList.remove('playing');
                btn.querySelector('.icon').innerHTML = '&#9654;';
            }}
            return;
        }}

        const prevTime = (audio.currentTime > 0 && !audio.ended) ? audio.currentTime : lastKnownTime;

        if (currentBtn) {{
            currentBtn.classList.remove('playing');
            currentBtn.querySelector('.icon').innerHTML = '&#9654;';
        }}

        btn.classList.add('playing');
        btn.querySelector('.icon').innerHTML = '||';
        currentBtn = btn;
        currentFile = filename;

        audio.src = 'choice_clips_chroma/' + filename;
        const go = () => {{
            if (prevTime > 0) {{
                try {{ audio.currentTime = Math.min(prevTime, (audio.duration || 20.0) - 0.05); }} catch (e) {{}}
            }}
            audio.play().catch(e => console.error(e));
        }};
        if (audio.readyState >= 1) go();
        else audio.addEventListener('loadedmetadata', go, {{ once: true }});
    }}

    audio.onended = () => {{
        lastKnownTime = 0;
        if (currentBtn) {{
            currentBtn.classList.remove('playing');
            currentBtn.querySelector('.icon').innerHTML = '&#9654;';
        }}
    }};
</script>
</body>
</html>
"""
    html_content = inject(html_content)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Built interactive evaluation page at {OUT_HTML}")


if __name__ == "__main__":
    main()
