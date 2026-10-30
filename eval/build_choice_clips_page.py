#!/usr/bin/env python3
"""build_choice_clips_page.py -- builds the interactive comparison dashboard for
the 29 choice clips under 4 conditions:
1. Base (gain 0)
2. C major triad (gain 2048)
3. Eb major triad (gain 2048)
4. Total Eclipse - Aliens HQ excerpt (gain 2048)

Reads manifest from /home/kim/evals_aac/choice_clips_chroma/choice_clips_manifest.json
and generates /home/kim/evals_aac/choice_clips_chroma.html
"""
import json, os, sys
from pathlib import Path

AAC_DIR = Path("/home/kim/evals_aac/choice_clips_chroma")
MANIFEST_FILE = AAC_DIR / "choice_clips_manifest.json"
OUT_HTML = Path("/home/kim/evals_aac/choice_clips_chroma.html")

PLAN_ITEMS_FILE = Path("/home/kim/.gemini/antigravity/brain/62fc5213-e94b-4c13-86bf-69147f02f03c/scratch/render_plan_items.json")

def main():
    if not PLAN_ITEMS_FILE.exists():
        print(f"Error: {PLAN_ITEMS_FILE} not found.")
        sys.exit(1)

    with open(PLAN_ITEMS_FILE) as f:
        items = json.load(f)

    # Group by row_idx
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
        
        # Audio file stems
        base_stem = f"choice_{idx:02d}__{model}__{ckpt}__base__s{seed}.m4a"
        c_stem = f"choice_{idx:02d}__{model}__{ckpt}__C__s{seed}.m4a"
        eb_stem = f"choice_{idx:02d}__{model}__{ckpt}__Eb__s{seed}.m4a"
        aliens_stem = f"choice_{idx:02d}__{model}__{ckpt}__Aliens__s{seed}.m4a"

        # Check existence
        b_exists = (AAC_DIR / base_stem).exists()
        c_exists = (AAC_DIR / c_stem).exists()
        eb_exists = (AAC_DIR / eb_stem).exists()
        a_exists = (AAC_DIR / aliens_stem).exists()

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
            </td>
            <td class="audio-cell">
                <div class="btn-group">
                    <button class="play-btn {'ready' if b_exists else 'pending'}" onclick="playAudio('{base_stem}', this, {idx}, 'base')">
                        <span class="icon">&#9654;</span> Base (g0)
                    </button>
                    <button class="play-btn {'ready' if c_exists else 'pending'}" onclick="playAudio('{c_stem}', this, {idx}, 'C')">
                        <span class="icon">&#9654;</span> C Major (g2048)
                    </button>
                    <button class="play-btn {'ready' if eb_exists else 'pending'}" onclick="playAudio('{eb_stem}', this, {idx}, 'Eb')">
                        <span class="icon">&#9654;</span> Eb Major (g2048)
                    </button>
                    <button class="play-btn {'ready' if a_exists else 'pending'}" onclick="playAudio('{aliens_stem}', this, {idx}, 'Aliens')">
                        <span class="icon">&#9654;</span> Aliens HQ (g2048)
                    </button>
                </div>
            </td>
        </tr>
        """)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Choice Clips Chroma Guidance Matrix (29 Rows × 4 Conditions)</title>
    <style>
        :root {{
            --bg: #0d1117;
            --surface: #161b22;
            --border: #30363d;
            --text: #c9d1d9;
            --text-bright: #f0f6fc;
            --text-muted: #8b949e;
            --accent: #58a6ff;
            --accent-green: #238636;
            --accent-purple: #8957e5;
            --accent-orange: #d29922;
            --accent-hover: #1f6feb;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 24px;
        }}
        .header {{
            max-width: 1400px;
            margin: 0 auto 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }}
        .header h1 {{
            color: var(--text-bright);
            font-size: 24px;
            margin: 0 0 8px 0;
        }}
        .header p {{
            color: var(--text-muted);
            margin: 4px 0;
            font-size: 14px;
        }}
        .transport-bar {{
            position: sticky;
            top: 12px;
            z-index: 100;
            max-width: 1400px;
            margin: 0 auto 20px;
            background: rgba(22, 27, 34, 0.95);
            backdrop-filter: blur(8px);
            border: 1px solid var(--accent);
            border-radius: 8px;
            padding: 12px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 4px 16px rgba(0,0,0,0.4);
        }}
        .transport-info {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        .now-playing-tag {{
            font-size: 11px;
            text-transform: uppercase;
            font-weight: bold;
            padding: 3px 8px;
            border-radius: 4px;
            background: var(--accent);
            color: #000;
        }}
        .now-playing-title {{
            color: var(--text-bright);
            font-weight: 600;
            font-size: 14px;
        }}
        .transport-controls {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        .matrix-table {{
            width: 100%;
            max-width: 1400px;
            margin: 0 auto;
            border-collapse: collapse;
            background: var(--surface);
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid var(--border);
        }}
        .matrix-table th {{
            background: #21262d;
            color: var(--text-bright);
            padding: 12px 16px;
            text-align: left;
            font-size: 13px;
            border-bottom: 1px solid var(--border);
        }}
        .matrix-table td {{
            padding: 14px 16px;
            border-bottom: 1px solid var(--border);
            vertical-align: middle;
        }}
        .clip-row:hover {{
            background: #1c2128;
        }}
        .idx-cell {{
            font-weight: bold;
            color: var(--accent);
            font-size: 16px;
            width: 32px;
            text-align: center;
        }}
        .meta-cell {{
            width: 48%;
        }}
        .model-title {{
            color: var(--text-bright);
            font-weight: 600;
            font-size: 15px;
            margin-bottom: 6px;
        }}
        .meta-badges {{
            display: flex;
            gap: 6px;
            margin-bottom: 6px;
        }}
        .badge {{
            background: #21262d;
            color: var(--text-muted);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 11px;
        }}
        .prompt-text {{
            font-size: 12px;
            color: var(--text-muted);
            line-height: 1.4;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}
        .audio-cell {{
            width: 48%;
        }}
        .btn-group {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
        }}
        .play-btn {{
            background: #21262d;
            border: 1px solid var(--border);
            color: var(--text);
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            transition: all 0.15s ease;
        }}
        .play-btn.ready:hover {{
            background: #30363d;
            color: var(--text-bright);
            border-color: #8b949e;
        }}
        .play-btn.active {{
            background: var(--accent) !important;
            color: #000 !important;
            font-weight: bold;
            border-color: var(--accent) !important;
        }}
        .play-btn.pending {{
            opacity: 0.4;
            cursor: not-allowed;
            border-style: dashed;
        }}
        audio {{
            height: 32px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Curated Choice Clips Chroma Guidance Matrix</h1>
        <p><strong>Audition Set:</strong> 29 Choice Models &times; 4 Conditions (Base g0, C Major g2048, Eb Major g2048, Aliens HQ g2048)</p>
        <p><strong>Steering Head:</strong> <code>same_chroma_e13</code> (C3, lr 1e-3, ep10, latch_sa3_same_chroma_ep10.pt, weight 2048)</p>
        <p><strong>Audio Spec:</strong> 20.0s (280 frames), 24-step Euler, exact original seeds & prompts, 256k AAC.</p>
    </div>

    <div class="transport-bar" id="transport" style="display: none;">
        <div class="transport-info">
            <span class="now-playing-tag" id="now-cond">PLAYING</span>
            <div>
                <div class="now-playing-title" id="now-title">-</div>
                <div style="font-size: 11px; color: var(--text-muted);" id="now-meta">-</div>
            </div>
        </div>
        <div class="transport-controls">
            <audio id="global-audio" controls></audio>
        </div>
    </div>

    <table class="matrix-table">
        <thead>
            <tr>
                <th>#</th>
                <th>Model, Recipe & Prompt Metadata</th>
                <th>Audio Conditions (Click to Play / Compare in Place)</th>
            </tr>
        </thead>
        <tbody>
            {"".join(rows_html)}
        </tbody>
    </table>

    <script>
        const audio = document.getElementById('global-audio');
        const transport = document.getElementById('transport');
        const nowTitle = document.getElementById('now-title');
        const nowMeta = document.getElementById('now-meta');
        const nowCond = document.getElementById('now-cond');
        let currentBtn = null;

        function playAudio(filename, btn, idx, cond) {{
            if (btn.classList.contains('pending')) return;

            // Preserve current playback time for synchronous A/B switching
            const prevTime = audio.currentTime;
            const wasPlaying = !audio.paused;

            if (currentBtn) {{
                currentBtn.classList.remove('active');
            }}

            btn.classList.add('active');
            currentBtn = btn;

            const row = document.getElementById('row-' + idx);
            const title = row.querySelector('.model-title').innerText;
            const meta = row.querySelector('.meta-badges').innerText;

            nowTitle.innerText = `[#${{idx < 10 ? '0' + idx : idx}}] ${{title}}`;
            nowMeta.innerText = meta;
            nowCond.innerText = cond.toUpperCase();

            transport.style.display = 'flex';
            audio.src = 'choice_clips_chroma/' + filename;

            audio.onloadedmetadata = () => {{
                if (prevTime > 0 && prevTime < audio.duration) {{
                    audio.currentTime = prevTime;
                }}
                audio.play();
            }};
        }}

        audio.onended = () => {{
            if (currentBtn) currentBtn.classList.remove('active');
        }};
    </script>
</body>
</html>
"""
    with open(OUT_HTML, "w") as f:
        f.write(html_content)
    print(f"Built interactive evaluation page at {OUT_HTML}")

if __name__ == "__main__":
    main()
