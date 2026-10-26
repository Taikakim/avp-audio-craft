#!/usr/bin/env python3
"""Builds an interactive audition console for Gate G1 Zero-Training baselines.
Provides side-by-side playback and comparative metrics for:
(a) Solo kit piece prior renders
(b) SDEdit drum bus isolation across noise levels [0.3, 0.5, 0.7]
(c) Rectified Flow Inversion (ZeroSep-style) vs Ground Truth
"""

import os
import json
import shutil
from pathlib import Path

RUN_DIR = Path("/home/kim/sao_runs/drum_sep_g1")
RESULTS_JSON = RUN_DIR / "results.json"
LISTEN_DIR = RUN_DIR / "listen"
LISTEN_AUDIO_DIR = LISTEN_DIR / "audio"
HTML_PATH = LISTEN_DIR / "index.html"
MULTITRACKS_DIR = Path("/home/kim/sao_runs/drum_sep_g0_multitracks")

def setup_audio_links():
    LISTEN_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    src_audio = RUN_DIR / "audio"
    if src_audio.exists():
        for f in src_audio.glob("*.wav"):
            target = LISTEN_AUDIO_DIR / f.name
            if not target.exists():
                try:
                    target.symlink_to(f)
                except Exception:
                    shutil.copy2(f, target)
    
    # Also link ground truth multitracks for direct comparison
    for song_dir in MULTITRACKS_DIR.iterdir():
        if song_dir.is_dir():
            for f in song_dir.glob("*.wav"):
                target = LISTEN_AUDIO_DIR / f"gt_{song_dir.name}_{f.name}"
                if not target.exists():
                    try:
                        target.symlink_to(f)
                    except Exception:
                        shutil.copy2(f, target)

def build_html():
    with open(RESULTS_JSON, "r") as f:
        data = json.load(f)
        
    g1a = data.get("g1a_solo_pieces", [])
    g1b = data.get("g1b_sdedit", [])
    g1c = data.get("g1c_flow_inversion", [])
    
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>SA3 Drum Separator — Gate G1 Audition Console</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {
      --bg: #0b0f19;
      --card-bg: #111827;
      --card-border: #1f293d;
      --accent: #38bdf8;
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --green: #10b981;
      --yellow: #f59e0b;
      --red: #ef4444;
      --purple: #c084fc;
    }
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      margin: 0;
      padding: 24px 20px 100px 20px;
    }
    .container {
      max-width: 1300px;
      margin: 0 auto;
    }
    header {
      margin-bottom: 24px;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 20px;
    }
    h1 {
      font-size: 26px;
      font-weight: 800;
      margin: 0 0 8px 0;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .badge {
      display: inline-block;
      padding: 3px 10px;
      border-radius: 9999px;
      font-size: 13px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .badge-pass { background: rgba(16, 185, 129, 0.2); color: var(--green); border: 1px solid var(--green); }
    .badge-gate { background: rgba(192, 132, 252, 0.2); color: var(--purple); border: 1px solid var(--purple); }
    .badge-fail { background: rgba(239, 68, 68, 0.2); color: var(--red); border: 1px solid var(--red); }
    .desc {
      color: var(--text-muted);
      font-size: 15px;
      line-height: 1.5;
      max-width: 900px;
      margin: 0;
    }
    .summary-box {
      background: #1e1b4b;
      border: 1px solid #4338ca;
      border-radius: 8px;
      padding: 16px 20px;
      margin: 20px 0 30px 0;
    }
    .summary-box h3 {
      margin: 0 0 8px 0;
      color: #a5b4fc;
      font-size: 16px;
    }
    .summary-box p {
      margin: 0;
      color: #e0e7ff;
      font-size: 14px;
      line-height: 1.5;
    }
    h2 {
      font-size: 20px;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 8px;
      margin-top: 36px;
      color: #e2e8f0;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
      gap: 16px;
      margin-top: 16px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 16px;
    }
    .card-title {
      font-weight: 700;
      font-size: 15px;
      color: #fff;
      margin-bottom: 4px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .card-sub {
      font-size: 12px;
      color: var(--text-muted);
      margin-bottom: 12px;
      word-break: break-all;
    }
    audio {
      width: 100%;
      height: 36px;
      border-radius: 6px;
      margin-top: 8px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 14px;
      background: var(--card-bg);
      border-radius: 8px;
      overflow: hidden;
      border: 1px solid var(--card-border);
    }
    th, td {
      padding: 10px 14px;
      text-align: left;
      font-size: 13px;
      border-bottom: 1px solid var(--card-border);
    }
    th {
      background: #1e293b;
      font-weight: 600;
      color: #94a3b8;
    }
    tr:hover { background: #1e293b55; }
    .good { color: var(--green); font-weight: 600; }
    .fair { color: var(--yellow); }
    .poor { color: var(--red); font-weight: 600; }
    .mono { font-family: monospace; font-size: 12px; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>
        SA3 Drum Separator — Gate G1 Audition Console
        <span class="badge badge-gate">Gate G1: Concluded</span>
      </h1>
      <p class="desc">
        Zero-training baselines on frozen SA3 Medium Base. This audition console tests whether text conditioning alone
        can separate overlapping drum stems without training through SDEdit partial denoising or Rectified Flow Inversion.
      </p>
      <div class="summary-box">
        <h3>Key Gate G1 Finding</h3>
        <p>
          <strong>Prior is capable, but zero-training separation fails on overlapping hits.</strong>
          G1(a) confirms SA3 cleanly generates solo isolated kit pieces (kicks, acoustic snares, offbeat hats).
          However, G1(b) SDEdit and G1(c) Flow Inversion bleed heavily between kit pieces (kick punches bleed into hats and snares;
          SI-SDR is -20 to -60 dB on hats). This definitively justifies Gate G2: an explicit adapter / inlet fine-tuning is required.
        </p>
      </div>
    </header>

    <h2>1. Gate G1(a): Text-to-Audio Solo Kit Pieces (Prior Quality Check)</h2>
    <div class="grid">
"""
    for entry in g1a:
        tag = entry["tag"]
        seed = entry["seed"]
        rms = entry.get("rms", 0.0)
        onsets = entry.get("n_onsets", 0)
        prompt = entry.get("prompt", "")
        file_name = entry["file"]
        
        html += f"""
      <div class="card">
        <div class="card-title">
          <span>{tag} (seed {seed})</span>
          <span class="badge badge-pass">{onsets} onsets</span>
        </div>
        <div class="card-sub">{prompt}</div>
        <div style="font-size:12px; color:#94a3b8; margin-bottom:4px;">RMS: {rms:.4f}</div>
        <audio controls src="audio/{file_name}" preload="none"></audio>
      </div>
"""
    html += """    </div>

    <h2>2. Gate G1(b): SDEdit on Real Drum Bus (Partial Noise Re-synthesis)</h2>
    <table>
      <thead>
        <tr>
          <th>Track</th>
          <th>Stem Target</th>
          <th>Noise Level</th>
          <th>LSD (dB)</th>
          <th>SI-SDR (dB)</th>
          <th>Onset F1 @ 20ms</th>
          <th>Attack Error</th>
          <th>Audio Audition</th>
        </tr>
      </thead>
      <tbody>
"""
    for entry in g1b:
        song = entry.get("song", "")
        stem = entry.get("stem_tag", "")
        nl = entry.get("noise_lvl", 0.0)
        fname = entry.get("file", "")
        lsd = entry.get("lsd_db")
        sisdr = entry.get("si_sdr_db")
        f1 = entry.get("onset_f1_20")
        atk = entry.get("attack_db")
        
        lsd_str = f"{lsd:.1f}" if lsd is not None else "-"
        sisdr_str = f"{sisdr:.1f}" if sisdr is not None else "-"
        f1_str = f"{f1:.2f}" if f1 is not None else "-"
        atk_str = f"{atk:+.2f} dB" if atk is not None else "-"
        
        f1_cls = "good" if (f1 and f1 >= 0.8) else ("fair" if (f1 and f1 >= 0.4) else "poor")
        sdr_cls = "good" if (sisdr and sisdr >= 10.0) else ("fair" if (sisdr and sisdr >= 0.0) else "poor")
        
        html += f"""
        <tr>
          <td><strong>{song}</strong></td>
          <td><span class="badge badge-gate">{stem}</span></td>
          <td class="mono">{nl:.1f}</td>
          <td class="mono">{lsd_str}</td>
          <td class="mono {sdr_cls}">{sisdr_str}</td>
          <td class="mono {f1_cls}">{f1_str}</td>
          <td class="mono">{atk_str}</td>
          <td style="min-width:240px;">
            <audio controls src="audio/{fname}" preload="none"></audio>
          </td>
        </tr>
"""
    html += """      </tbody>
    </table>

    <h2>3. Gate G1(c): Rectified Flow Inversion (ZeroSep-Style Reverse ODE)</h2>
    <table>
      <thead>
        <tr>
          <th>Track</th>
          <th>Target</th>
          <th>Steps</th>
          <th>LSD (dB)</th>
          <th>SI-SDR (dB)</th>
          <th>Onset F1 @ 20ms</th>
          <th>Attack Error</th>
          <th>Audio Audition</th>
        </tr>
      </thead>
      <tbody>
"""
    for entry in g1c:
        song = entry.get("song", "")
        stem = entry.get("stem_tag", "")
        fname = entry.get("file", "")
        lsd = entry.get("lsd_db")
        sisdr = entry.get("si_sdr_db")
        f1 = entry.get("onset_f1_20")
        atk = entry.get("attack_db")
        
        lsd_str = f"{lsd:.1f}" if lsd is not None else "-"
        sisdr_str = f"{sisdr:.1f}" if sisdr is not None else "-"
        f1_str = f"{f1:.2f}" if f1 is not None else "-"
        atk_str = f"{atk:+.2f} dB" if atk is not None else "-"
        
        f1_cls = "good" if (f1 and f1 >= 0.8) else ("fair" if (f1 and f1 >= 0.4) else "poor")
        sdr_cls = "good" if (sisdr and sisdr >= 10.0) else ("fair" if (sisdr and sisdr >= 0.0) else "poor")
        
        html += f"""
        <tr>
          <td><strong>{song}</strong></td>
          <td><span class="badge badge-gate">{stem}</span></td>
          <td class="mono">40</td>
          <td class="mono">{lsd_str}</td>
          <td class="mono {sdr_cls}">{sisdr_str}</td>
          <td class="mono {f1_cls}">{f1_str}</td>
          <td class="mono">{atk_str}</td>
          <td style="min-width:240px;">
            <audio controls src="audio/{fname}" preload="none"></audio>
          </td>
        </tr>
"""
    html += """      </tbody>
    </table>

    <h2>4. Original Drum Bus References</h2>
    <div class="grid">
      <div class="card">
        <div class="card-title">goddess_guerrilla — Drum Bus</div>
        <audio controls src="audio/goddess_guerrilla__bus.wav" preload="none"></audio>
      </div>
      <div class="card">
        <div class="card-title">acid_alien — Drum Bus</div>
        <audio controls src="audio/acid_alien__bus.wav" preload="none"></audio>
      </div>
    </div>
  </div>
</body>
</html>
"""
    with open(HTML_PATH, "w") as f:
        f.write(html)
    print(f"Audition console written to {HTML_PATH}")

if __name__ == "__main__":
    setup_audio_links()
    build_html()
