#!/usr/bin/env python3
"""build_ep10_vs_ep40_page.py -- builds the interactive head-to-head comparison dashboard
comparing ep10 (loss 0.1345) vs ep40 (loss 0.1034) vs ep40_ema0.25.
Outputs /home/kim/evals_aac/ep10_vs_ep40_chroma.html
"""
import json, sys
from pathlib import Path

AAC_DIR = Path("/home/kim/evals_aac/ep10_vs_ep40_chroma")
OUT_HTML = Path("/home/kim/evals_aac/ep10_vs_ep40_chroma.html")
PLAN_ITEMS_FILE = Path("/home/kim/.gemini/antigravity/brain/62fc5213-e94b-4c13-86bf-69147f02f03c/scratch/render_plan_items.json")

def btn(stem, label, idx, cond, head_tag=""):
    exists = (AAC_DIR / stem).exists()
    status_cls = "ready" if exists else "pending"
    title_attr = f'title="{stem}"'
    sub_span = f'<span class="sub">{head_tag}</span>' if head_tag else ''
    return f"""<button class="play-btn {status_cls}" onclick="playAudio('{stem}', this, {idx}, '{cond}')" {title_attr}>
        <span class="icon">&#9654;</span> <span class="lbl">{label}</span>{sub_span}
    </button>"""

def main():
    with open(PLAN_ITEMS_FILE) as f:
        all_items = json.load(f)

    selected_rows = [2, 5, 7, 11, 22, 28]
    items = [it for it in all_items if it['idx'] in selected_rows]

    rows_html = []
    for item in items:
        idx = item['idx']
        label = item['label']
        model = item['model']
        ckpt = item['ckpt_tag']
        prompt = item['prompt_text']
        seed = item['seed']
        cfg = item['cfg']
        strength = item['strength']

        # Stems
        base_stem = f"ep10vs40_row{idx:02d}__{model}__{ckpt}__base__s{seed}.m4a"

        # Targets & Heads
        targets = ["C", "Eb", "Aliens"]
        heads = [("ep10", "ep10 (0.1345)"), ("ep40", "ep40 (0.1034)"), ("ep40_ema0.25", "ep40 EMA 0.25")]

        target_blocks = []
        for tgt in targets:
            head_cols = []
            for head_id, head_lbl in heads:
                stem_1024 = f"ep10vs40_row{idx:02d}__{model}__{ckpt}__{head_id}__{tgt}_g1024__s{seed}.m4a"
                stem_2048 = f"ep10vs40_row{idx:02d}__{model}__{ckpt}__{head_id}__{tgt}_g2048__s{seed}.m4a"
                head_cols.append(f"""
                <div class="head-col">
                    <div class="head-badge head-{head_id}">{head_lbl}</div>
                    <div class="btn-group">
                        {btn(stem_1024, '0.5x', idx, f'{tgt}_{head_id}_1024', 'g1024')}
                        {btn(stem_2048, '1.0x', idx, f'{tgt}_{head_id}_2048', 'g2048')}
                    </div>
                </div>
                """)

            target_blocks.append(f"""
            <div class="target-section">
                <div class="target-title">{tgt} {'Major' if tgt != 'Aliens' else 'HQ'}</div>
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
                    <span class="badge">Seed {seed}</span>
                    <span class="badge">20.0s</span>
                </div>
                <div class="prompt-text" title="{prompt}">{prompt}</div>
                <div class="base-container">
                    <span class="base-lbl">Unguided Reference:</span>
                    {btn(base_stem, 'Base (g0)', idx, 'base')}
                </div>
            </td>
            <td class="eval-grid-cell">
                <div class="targets-container">
                    {''.join(target_blocks)}
                </div>
            </td>
        </tr>
        """)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Chroma Head Retrain: ep10 vs ep40 vs ep40_ema0.25 (Listening Evaluation)</title>
<style>
:root {{
    --bg: #0b0f19;
    --card-bg: #111827;
    --border: #1f2937;
    --text: #f3f4f6;
    --text-dim: #9ca3af;
    --accent: #38bdf8;
    --accent-glow: rgba(56, 189, 248, 0.2);
    --green: #10b981;
    --purple: #8b5cf6;
    --orange: #f59e0b;
    --amber: #d97706;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    padding: 24px;
    padding-bottom: 120px;
}}
header {{
    max-width: 1500px;
    margin: 0 auto 24px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 16px;
}}
h1 {{
    font-size: 24px;
    font-weight: 700;
    color: var(--text);
    display: flex;
    align-items: center;
    gap: 12px;
}}
.tagline {{
    color: var(--text-dim);
    font-size: 14px;
    margin-top: 6px;
}}
.stats-banner {{
    display: flex;
    gap: 20px;
    margin-top: 14px;
    background: rgba(31, 41, 55, 0.6);
    padding: 12px 18px;
    border-radius: 8px;
    border: 1px solid var(--border);
}}
.stat-item {{
    font-size: 13px;
    color: var(--text-dim);
}}
.stat-item strong {{
    color: var(--accent);
}}
.nav-link {{
    display: inline-block;
    margin-top: 10px;
    color: var(--accent);
    text-decoration: none;
    font-size: 13px;
}}
.nav-link:hover {{
    text-decoration: underline;
}}
.main-table {{
    width: 100%;
    max-width: 1500px;
    margin: 0 auto;
    border-collapse: collapse;
}}
.clip-row {{
    background: var(--card-bg);
    border-bottom: 1px solid var(--border);
}}
.clip-row:hover {{
    background: #162032;
}}
td {{
    padding: 16px;
    vertical-align: top;
}}
.idx-cell {{
    width: 44px;
    font-size: 14px;
    font-weight: 700;
    color: var(--text-dim);
    text-align: center;
    border-right: 1px solid var(--border);
}}
.meta-cell {{
    width: 380px;
    border-right: 1px solid var(--border);
}}
.model-title {{
    font-size: 14px;
    font-weight: 600;
    color: #e2e8f0;
    line-height: 1.4;
    margin-bottom: 6px;
}}
.meta-badges {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 8px;
}}
.badge {{
    background: #1e293b;
    color: #94a3b8;
    font-size: 11px;
    padding: 2px 6px;
    border-radius: 4px;
}}
.prompt-text {{
    font-size: 12px;
    color: #cbd5e1;
    line-height: 1.4;
    background: rgba(0, 0, 0, 0.25);
    padding: 8px;
    border-radius: 4px;
    border-left: 3px solid #475569;
    margin-bottom: 12px;
}}
.base-container {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding-top: 6px;
    border-top: 1px dashed #334155;
}}
.base-lbl {{
    font-size: 12px;
    color: var(--text-dim);
}}
.eval-grid-cell {{
    padding: 12px;
}}
.targets-container {{
    display: flex;
    flex-direction: column;
    gap: 12px;
}}
.target-section {{
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid #1e293b;
    border-radius: 6px;
    padding: 10px 14px;
}}
.target-title {{
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #38bdf8;
    margin-bottom: 8px;
}}
.heads-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
}}
.head-col {{
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid #2d3748;
    border-radius: 4px;
    padding: 6px;
}}
.head-badge {{
    font-size: 11px;
    font-weight: 600;
    padding: 3px 6px;
    border-radius: 3px;
    margin-bottom: 6px;
    text-align: center;
}}
.head-ep10 {{
    background: #334155;
    color: #cbd5e1;
}}
.head-ep40 {{
    background: #065f46;
    color: #6ee7b7;
    border: 1px solid #059669;
}}
.head-ep40_ema0\\.25, .head-ep40_ema0\.25 {{
    background: #4c1d95;
    color: #c4b5fd;
    border: 1px solid #6d28d9;
}}
.btn-group {{
    display: flex;
    gap: 6px;
}}
.play-btn {{
    flex: 1;
    background: #1f2937;
    border: 1px solid #374151;
    color: #e5e7eb;
    padding: 6px 8px;
    font-size: 12px;
    border-radius: 4px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    transition: all 0.15s ease;
}}
.play-btn:hover {{
    background: #374151;
    border-color: #4b5563;
}}
.play-btn.playing {{
    background: #0284c7;
    border-color: #38bdf8;
    color: #ffffff;
    box-shadow: 0 0 10px rgba(56, 189, 248, 0.4);
}}
.play-btn.pending {{
    opacity: 0.4;
    cursor: not-allowed;
}}
.play-btn .sub {{
    font-size: 10px;
    color: #94a3b8;
    margin-left: 2px;
}}
.play-btn.playing .sub {{
    color: #e0f2fe;
}}

/* Fixed Footer Audio Player */
#player-bar {{
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: #0f172a;
    border-top: 1px solid #334155;
    padding: 12px 24px;
    display: flex;
    align-items: center;
    gap: 20px;
    z-index: 1000;
    box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.5);
}}
.player-controls {{
    display: flex;
    align-items: center;
    gap: 12px;
}}
.p-btn {{
    background: #1e293b;
    border: 1px solid #475569;
    color: #fff;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    cursor: pointer;
    font-size: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
}}
.p-btn:hover {{ background: #334155; }}
.track-info {{
    min-width: 280px;
    font-size: 12px;
}}
.track-name {{ font-weight: 600; color: #38bdf8; }}
.track-details {{ color: #94a3b8; font-size: 11px; }}
.scrub-container {{
    flex: 1;
    display: flex;
    align-items: center;
    gap: 10px;
}}
.time-txt {{
    font-size: 11px;
    font-variant-numeric: tabular-nums;
    color: #94a3b8;
    width: 36px;
}}
.scrub-slider {{
    flex: 1;
    height: 6px;
    -webkit-appearance: none;
    appearance: none;
    background: #334155;
    border-radius: 3px;
    outline: none;
}}
.scrub-slider::-webkit-slider-thumb {{
    -webkit-appearance: none;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #38bdf8;
    cursor: pointer;
}}
</style>
</head>
<body>

<header>
    <h1>
        <span>🎵</span> LatCH Head Retrain: ep10 vs ep40 vs ep40_ema0.25
    </h1>
    <div class="tagline">
        Evaluating the winning SAME-chroma head retrained for 40 epochs with cosine decay, 0.8x LR (8e-4), and effective batch 64.
    </div>
    <div class="stats-banner">
        <div class="stat-item">Historical Head (ep10): <strong>val loss 0.1345</strong></div>
        <div class="stat-item">40-Epoch Retrain (ep40): <strong>val loss 0.1034 (-23.1%)</strong></div>
        <div class="stat-item">Fast-Reacting Iterate: <strong>ep40_ema0.25</strong></div>
        <div class="stat-item">Models: <strong>6 representative choice checkpoints</strong></div>
        <div class="stat-item">Targets: <strong>C Major, Eb Major, Aliens HQ</strong></div>
    </div>
    <a href="/choice_clips_chroma.html" class="nav-link">&larr; Return to Choice Clips Matrix (ep10 290-clip full matrix)</a>
    &bull; <a href="/index.html" class="nav-link">Evaluation Index</a>
</header>

<table class="main-table">
    <tbody>
        {''.join(rows_html)}
    </tbody>
</table>

<div id="player-bar">
    <div class="player-controls">
        <button class="p-btn" id="play-pause-btn" onclick="togglePlay()">&#9654;</button>
    </div>
    <div class="track-info">
        <div class="track-name" id="p-title">No track selected</div>
        <div class="track-details" id="p-meta">Click any 0.5x, 1.0x or Base button above to play</div>
    </div>
    <div class="scrub-container">
        <span class="time-txt" id="curr-time">0:00</span>
        <input type="range" class="scrub-slider" id="scrub-bar" min="0" max="100" value="0" step="0.1" oninput="onSeek(this.value)">
        <span class="time-txt" id="total-time">0:20</span>
    </div>
</div>

<audio id="audio-elem"></audio>

<script>
const audio = document.getElementById('audio-elem');
const ppBtn = document.getElementById('play-pause-btn');
const pTitle = document.getElementById('p-title');
const pMeta = document.getElementById('p-meta');
const scrubBar = document.getElementById('scrub-bar');
const currTime = document.getElementById('curr-time');
const totalTime = document.getElementById('total-time');

let activeBtn = null;

function playAudio(stem, btnEl, rowIdx, cond) {{
    const url = '/choice_clips_chroma/' + stem.replace('ep10vs40_row', 'ep10vs40_row'); // points to evals_aac root
    const actualUrl = '/ep10_vs_ep40_chroma/' + stem;

    if (activeBtn) {{
        activeBtn.classList.remove('playing');
        activeBtn.querySelector('.icon').innerHTML = '&#9654;';
    }}

    if (audio.src.endsWith(actualUrl) && !audio.paused) {{
        audio.pause();
        ppBtn.innerHTML = '&#9654;';
        activeBtn = null;
        return;
    }}

    audio.src = actualUrl;
    audio.play().then(() => {{
        ppBtn.innerHTML = '&#10074;&#10074;';
        btnEl.classList.add('playing');
        btnEl.querySelector('.icon').innerHTML = '&#10074;&#10074;';
        activeBtn = btnEl;
        pTitle.textContent = stem;
        pMeta.textContent = `Row ${{rowIdx.toString().padStart(2, '0')}} | Condition: ${{cond}}`;
    }}).catch(e => {{
        console.error("Playback failed:", e);
        pTitle.textContent = "Error loading: " + stem;
    }});
}}

function togglePlay() {{
    if (audio.paused) {{
        if (audio.src) {{
            audio.play();
            ppBtn.innerHTML = '&#10074;&#10074;';
            if (activeBtn) activeBtn.classList.add('playing');
        }}
    }} else {{
        audio.pause();
        ppBtn.innerHTML = '&#9654;';
        if (activeBtn) activeBtn.classList.remove('playing');
    }}
}}

audio.ontimeupdate = () => {{
    if (!audio.duration) return;
    const pct = (audio.currentTime / audio.duration) * 100;
    scrubBar.value = pct;
    currTime.textContent = formatTime(audio.currentTime);
    totalTime.textContent = formatTime(audio.duration);
}};

audio.onended = () => {{
    ppBtn.innerHTML = '&#9654;';
    if (activeBtn) {{
        activeBtn.classList.remove('playing');
        activeBtn.querySelector('.icon').innerHTML = '&#9654;';
    }}
}};

function onSeek(val) {{
    if (!audio.duration) return;
    audio.currentTime = (val / 100) * audio.duration;
}}

function formatTime(sec) {{
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${{m}}:${{s.toString().padStart(2, '0')}}`;
}}

window.addEventListener('keydown', e => {{
    if (e.code === 'Space' && e.target.tagName !== 'INPUT') {{
        e.preventDefault();
        togglePlay();
    }}
}});
</script>
</body>
</html>
"""
    OUT_HTML.write_text(html)
    print(f"Built interactive evaluation page at {OUT_HTML}")

if __name__ == "__main__":
    main()
