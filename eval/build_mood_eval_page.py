#!/usr/bin/env python3
"""build_mood_eval_page.py -- builds the interactive listening evaluation dashboard
for the 56-dim continuous Mood LatCH conditioning head (ep40 & ep40_ema0.25).
Outputs /home/kim/evals_aac/choice_clips_mood.html
"""
import json, sys
from pathlib import Path

AAC_DIR = Path("/home/kim/evals_aac/choice_clips_mood")
OUT_HTML = Path("/home/kim/evals_aac/choice_clips_mood.html")
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

    # Core representative choice models
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

        # Base stem
        base_stem = f"mood_row{idx:02d}__{model}__{ckpt}__base__s{seed}.m4a"

        # Targets & Heads
        targets = [
            ("Space", "Space (Atmospheric / Cosmic)", "#38bdf8"),
            ("Dark", "Dark (Heavy / Night-time Psy)", "#f43f5e"),
            ("Melodic", "Melodic (Euphoric / Uplifting)", "#a855f7"),
            ("Aliens", "Aliens HQ (Dynamic Excerpt)", "#10b981")
        ]
        heads = [("ep40", "ep40 (0.0598)"), ("ep40_ema0.25", "ep40 EMA 0.25")]

        target_blocks = []
        for tgt_id, tgt_title, tgt_color in targets:
            head_cols = []
            for head_id, head_lbl in heads:
                head_cls = head_id.replace('.', '_')
                stem_1024 = f"mood_row{idx:02d}__{model}__{ckpt}__{head_id}__{tgt_id}_g1024__s{seed}.m4a"
                stem_2048 = f"mood_row{idx:02d}__{model}__{ckpt}__{head_id}__{tgt_id}_g2048__s{seed}.m4a"
                head_cols.append(f"""
                <div class="head-col">
                    <div class="head-badge head-{head_cls}">{head_lbl}</div>
                    <div class="btn-group">
                        {btn(stem_1024, 'g1024', idx, f'{tgt_id}_{head_id}_1024', 'Standard')}
                        {btn(stem_2048, 'g2048', idx, f'{tgt_id}_{head_id}_2048', 'High')}
                    </div>
                </div>
                """)

            target_blocks.append(f"""
            <div class="target-section">
                <div class="target-title" style="border-left: 3px solid {tgt_color};">{tgt_title}</div>
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

    table_rows = "".join(rows_html)

    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>56-dim Mood LatCH Conditioning Head Evaluation (ep40 & ep40_ema0.25)</title>
<style>
:root {
    --bg-main: #0c0e12;
    --bg-card: #151921;
    --bg-hover: #1c222e;
    --border: #232a38;
    --text-primary: #e2e8f0;
    --text-muted: #8b9bb4;
    --accent-blue: #3b82f6;
    --accent-green: #10b981;
    --accent-purple: #8b5cf6;
    --accent-rose: #f43f5e;
    --accent-cyan: #06b6d4;
    --gold: #f59e0b;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    background: var(--bg-main);
    color: var(--text-primary);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    padding: 24px;
    line-height: 1.5;
    padding-bottom: 120px;
}
header {
    max-width: 1700px;
    margin: 0 auto 24px auto;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px 28px;
    position: relative;
    box-shadow: 0 4px 20px rgba(0,0,0,0.4);
}
.header-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 12px;
}
h1 {
    font-size: 24px;
    font-weight: 700;
    color: #fff;
    letter-spacing: -0.02em;
    display: flex;
    align-items: center;
    gap: 12px;
}
.tag-badge {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    background: rgba(16, 185, 129, 0.2);
    color: var(--accent-green);
    border: 1px solid var(--accent-green);
    padding: 2px 8px;
    border-radius: 20px;
}
.subtitle {
    font-size: 14px;
    color: var(--text-muted);
    max-width: 1200px;
}
.nav-link {
    color: var(--accent-blue);
    text-decoration: none;
    font-size: 13px;
    font-weight: 500;
}
.nav-link:hover { text-decoration: underline; }
.stat-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 16px;
}
.chip {
    background: #0f131a;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.chip-val {
    font-weight: 700;
    color: #fff;
}

.table-container {
    max-width: 1700px;
    margin: 0 auto;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 20px rgba(0,0,0,0.4);
}
table {
    width: 100%;
    border-collapse: collapse;
    text-align: left;
}
th {
    background: #11151c;
    padding: 12px 16px;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--text-muted);
    border-bottom: 1px solid var(--border);
    letter-spacing: 0.05em;
}
.clip-row {
    border-bottom: 1px solid var(--border);
    transition: background 0.15s ease;
}
.clip-row:hover {
    background: rgba(255,255,255,0.015);
}
.idx-cell {
    padding: 16px;
    font-size: 16px;
    font-weight: 800;
    color: var(--text-muted);
    vertical-align: top;
    width: 50px;
    text-align: center;
}
.meta-cell {
    padding: 16px 20px 16px 0;
    width: 380px;
    vertical-align: top;
    border-right: 1px solid var(--border);
}
.model-title {
    font-size: 14px;
    font-weight: 700;
    color: #fff;
    margin-bottom: 6px;
    line-height: 1.3;
}
.meta-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 10px;
}
.badge {
    font-size: 11px;
    background: #0f131a;
    border: 1px solid #2d3748;
    color: #94a3b8;
    padding: 1px 6px;
    border-radius: 4px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.prompt-text {
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.4;
    margin-bottom: 14px;
    background: #0b0e14;
    padding: 8px 10px;
    border-radius: 6px;
    border: 1px solid rgba(255,255,255,0.05);
}
.base-container {
    display: flex;
    align-items: center;
    gap: 12px;
    background: rgba(255,255,255,0.02);
    padding: 8px 10px;
    border-radius: 6px;
    border: 1px solid var(--border);
}
.base-lbl {
    font-size: 11px;
    font-weight: 600;
    color: #cbd5e1;
    text-transform: uppercase;
}

.eval-grid-cell {
    padding: 14px 16px;
    vertical-align: top;
}
.targets-container {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
}
.target-section {
    background: #11141c;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 14px;
}
.target-title {
    font-size: 13px;
    font-weight: 700;
    color: #fff;
    padding-left: 8px;
    margin-bottom: 12px;
    line-height: 1.2;
}
.heads-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
}
.head-col {
    background: #0d1017;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 6px;
    padding: 8px;
}
.head-badge {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    text-align: center;
    padding: 3px 6px;
    border-radius: 4px;
    margin-bottom: 8px;
    letter-spacing: 0.03em;
}
.head-ep40 {
    background: rgba(59, 130, 246, 0.2);
    color: #60a5fa;
    border: 1px solid #3b82f6;
}
.head-ep40_ema0_25 {
    background: rgba(168, 85, 247, 0.2);
    color: #c084fc;
    border: 1px solid #a855f7;
}
.btn-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.play-btn {
    background: #1e2634;
    border: 1px solid #334155;
    color: #cbd5e1;
    padding: 6px 8px;
    border-radius: 5px;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: space-between;
    transition: all 0.12s ease;
    user-select: none;
}
.play-btn:hover:not(.pending) {
    background: #2b3548;
    color: #fff;
    border-color: #475569;
}
.play-btn .icon {
    font-size: 9px;
    margin-right: 4px;
    opacity: 0.8;
}
.play-btn .lbl {
    font-weight: 700;
}
.play-btn .sub {
    font-size: 9px;
    font-weight: 500;
    color: #94a3b8;
    background: rgba(0,0,0,0.3);
    padding: 1px 4px;
    border-radius: 3px;
    margin-left: 4px;
}
.play-btn.playing {
    background: #10b981 !important;
    border-color: #059669 !important;
    color: #fff !important;
    box-shadow: 0 0 10px rgba(16,185,129,0.5);
}
.play-btn.playing .sub {
    color: #d1fae5;
    background: rgba(0,0,0,0.2);
}
.play-btn.pending {
    opacity: 0.35;
    cursor: not-allowed;
    border-style: dashed;
}

#player-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: rgba(15, 19, 27, 0.96);
    backdrop-filter: blur(12px);
    border-top: 1px solid #232a38;
    padding: 12px 24px;
    display: flex;
    align-items: center;
    gap: 20px;
    z-index: 1000;
    box-shadow: 0 -4px 25px rgba(0,0,0,0.6);
}
.bar-controls {
    display: flex;
    align-items: center;
    gap: 12px;
}
.main-play-btn {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: var(--accent-green);
    border: none;
    color: #000;
    font-size: 16px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    transition: transform 0.1s ease;
}
.main-play-btn:hover { transform: scale(1.05); }
.track-info {
    min-width: 280px;
}
.track-title {
    font-size: 13px;
    font-weight: 700;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 400px;
}
.track-cond {
    font-size: 11px;
    color: var(--text-muted);
}
.progress-container {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 12px;
}
.progress-bar-bg {
    flex: 1;
    height: 6px;
    background: #1e2634;
    border-radius: 3px;
    cursor: pointer;
    position: relative;
    overflow: hidden;
}
.progress-bar-fill {
    height: 100%;
    background: var(--accent-green);
    width: 0%;
    border-radius: 3px;
    transition: width 0.05s linear;
}
.time-disp {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12px;
    color: var(--text-muted);
    min-width: 80px;
}
</style>
</head>
<body>

<header>
    <div class="header-top">
        <div>
            <h1>56-dim Mood LatCH Conditioning Evaluation <span class="tag-badge">Best 40ep Head</span></h1>
            <div class="subtitle">Auditioning test-time guidance steering with the continuous 56-class MTG Jamendo mood head (ep40 val loss 0.0598) across curated choice prompts and diverse model families.</div>
        </div>
        <div>
            <a href="index.html" class="nav-link">&larr; Back to Evals Index</a>
        </div>
    </div>
    <div class="stat-chips">
        <div class="chip">Heads: <span class="chip-val">ep40 (val loss 0.0598) · ep40_ema0.25</span></div>
        <div class="chip">Targets: <span class="chip-val">Space · Dark · Melodic · Aliens HQ</span></div>
        <div class="chip">Weights: <span class="chip-val">g=1024 · g=2048</span></div>
        <div class="chip">Clips: <span class="chip-val">20.0s (280 frames @ 10.77 Hz, 24 Euler steps, 256k AAC)</span></div>
        <div class="chip">Audio Context: <span class="chip-val">Synchronized same-clock Web Audio player</span></div>
    </div>
</header>

<div class="table-container">
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>Model & Curated Prompt</th>
                <th>Mood Guidance Matrix (Space · Dark · Melodic · Aliens HQ)</th>
            </tr>
        </thead>
        <tbody>
""" + table_rows + """
        </tbody>
    </table>
</div>

<div id="player-bar">
    <div class="bar-controls">
        <button class="main-play-btn" id="bar-play-toggle" onclick="togglePlayPause()">&#9654;</button>
    </div>
    <div class="track-info">
        <div class="track-title" id="bar-track-title">Select a clip to play</div>
        <div class="track-cond" id="bar-track-cond">Hotkeys: Space (Play/Pause), Esc (Stop)</div>
    </div>
    <div class="progress-container">
        <span class="time-disp" id="bar-cur-time">0:00</span>
        <div class="progress-bar-bg" id="progress-bar" onclick="seekAudio(event)">
            <div class="progress-bar-fill" id="progress-fill"></div>
        </div>
        <span class="time-disp" id="bar-dur-time">0:20</span>
    </div>
</div>

<script>
let currentAudio = null;
let currentBtn = null;
let currentStem = null;
let currentRowIdx = null;

const barPlayBtn = document.getElementById('bar-play-toggle');
const barTitle = document.getElementById('bar-track-title');
const barCond = document.getElementById('bar-track-cond');
const barFill = document.getElementById('progress-fill');
const barCurTime = document.getElementById('bar-cur-time');
const barDurTime = document.getElementById('bar-dur-time');

function formatTime(sec) {
    if (isNaN(sec)) return "0:00";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return m + ":" + (s < 10 ? '0' : '') + s;
}

function playAudio(stem, btnEl, rowIdx, condLabel) {
    if (btnEl.classList.contains('pending')) return;

    let targetTime = 0;
    if (currentAudio && !currentAudio.paused) {
        targetTime = currentAudio.currentTime;
    }

    if (currentBtn === btnEl && currentAudio) {
        togglePlayPause();
        return;
    }

    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }
    if (currentBtn) {
        currentBtn.classList.remove('playing');
        currentBtn.querySelector('.icon').innerHTML = '&#9654;';
    }

    currentBtn = btnEl;
    currentStem = stem;
    currentRowIdx = rowIdx;

    currentAudio = new Audio('choice_clips_mood/' + stem);
    currentAudio.currentTime = targetTime;
    currentAudio.play().catch(e => console.error(e));

    btnEl.classList.add('playing');
    btnEl.querySelector('.icon').innerHTML = '&#10074;&#10074;';
    barPlayBtn.innerHTML = '&#10074;&#10074;';

    const rowEl = document.getElementById('row-' + rowIdx);
    const modelTitle = rowEl ? rowEl.querySelector('.model-title').textContent : ('Row ' + rowIdx);
    barTitle.textContent = modelTitle + ' — [' + condLabel + ']';
    barCond.textContent = stem;

    currentAudio.ontimeupdate = () => {
        if (!currentAudio) return;
        const cur = currentAudio.currentTime;
        const dur = currentAudio.duration || 20.0;
        const pct = (cur / dur) * 100;
        barFill.style.width = pct + '%';
        barCurTime.textContent = formatTime(cur);
        barDurTime.textContent = formatTime(dur);
    };

    currentAudio.onended = () => {
        if (currentBtn) {
            currentBtn.classList.remove('playing');
            currentBtn.querySelector('.icon').innerHTML = '&#9654;';
        }
        barPlayBtn.innerHTML = '&#9654;';
        barFill.style.width = '0%';
        barCurTime.textContent = '0:00';
    };
}

function togglePlayPause() {
    if (!currentAudio) return;
    if (currentAudio.paused) {
        currentAudio.play();
        if (currentBtn) {
            currentBtn.classList.add('playing');
            currentBtn.querySelector('.icon').innerHTML = '&#10074;&#10074;';
        }
        barPlayBtn.innerHTML = '&#10074;&#10074;';
    } else {
        currentAudio.pause();
        if (currentBtn) {
            currentBtn.classList.remove('playing');
            currentBtn.querySelector('.icon').innerHTML = '&#9654;';
        }
        barPlayBtn.innerHTML = '&#9654;';
    }
}

function seekAudio(e) {
    if (!currentAudio) return;
    const bar = document.getElementById('progress-bar');
    const rect = bar.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const width = rect.width;
    const dur = currentAudio.duration || 20.0;
    const seekTime = (clickX / width) * dur;
    currentAudio.currentTime = seekTime;
}

document.addEventListener('keydown', e => {
    if (e.code === 'Space') {
        e.preventDefault();
        togglePlayPause();
    } else if (e.code === 'Escape') {
        if (currentAudio) {
            currentAudio.pause();
            currentAudio.currentTime = 0;
            if (currentBtn) {
                currentBtn.classList.remove('playing');
                currentBtn.querySelector('.icon').innerHTML = '&#9654;';
            }
            barPlayBtn.innerHTML = '&#9654;';
            barFill.style.width = '0%';
            barCurTime.textContent = '0:00';
        }
    }
});
</script>
</body>
</html>
"""
    OUT_HTML.write_text(html)
    print(f"Generated dashboard: {OUT_HTML} ({len(html)} bytes)")

if __name__ == "__main__":
    main()
