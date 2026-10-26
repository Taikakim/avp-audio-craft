#!/usr/bin/env python3
"""Builds an interactive audition console for Gate G0 SAME-L Codec Ceiling benchmark.
Enables side-by-side A/B switching between original dry studio multitracks and SAME-L decoded stems.
"""

import json
from pathlib import Path

OUT_DIR = Path("/home/kim/sao_runs/drum_sep_g0")
RESULTS_JSON = OUT_DIR / "results.json"
HTML_PATH = OUT_DIR / "listen" / "index.html"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>SA3 Drum Separator — Gate G0 Codec Ceiling Audition Console</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {
      --bg: #090d16;
      --card-bg: #111827;
      --card-hover: #1f2937;
      --border: #1f293d;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --green: #10b981;
      --yellow: #f59e0b;
      --red: #ef4444;
      --purple: #a855f7;
    }
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      margin: 0;
      padding: 24px 20px 100px 20px;
    }
    .container {
      max-width: 1350px;
      margin: 0 auto;
    }
    header {
      margin-bottom: 24px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 20px;
    }
    h1 {
      font-size: 26px;
      font-weight: 800;
      letter-spacing: -0.5px;
      margin: 0 0 8px 0;
      color: #ffffff;
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .subtitle {
      color: var(--text-muted);
      font-size: 14px;
      margin: 0 0 16px 0;
      line-height: 1.5;
    }
    .stat-row {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }
    .stat-pill {
      background: #172033;
      border: 1px solid var(--border);
      padding: 6px 14px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .song-section {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      margin-bottom: 24px;
      overflow: hidden;
    }
    .song-header {
      padding: 16px 20px;
      background: #162032;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
    }
    .song-title {
      font-size: 18px;
      font-weight: 700;
      color: #ffffff;
      text-transform: capitalize;
    }
    .song-additivity {
      font-size: 13px;
      color: var(--text-muted);
    }
    .stem-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
      gap: 16px;
      padding: 20px;
    }
    .stem-card {
      background: #0d131f;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      transition: border-color 0.15s;
    }
    .stem-card:hover {
      border-color: #2e3e5c;
    }
    .stem-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .stem-name {
      font-weight: 700;
      font-size: 15px;
      color: #38bdf8;
      text-transform: capitalize;
    }
    .badge-f1 {
      font-size: 11px;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 4px;
    }
    .badge-pass { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; }
    .badge-fail { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }
    .badge-nan { background: rgba(156, 163, 175, 0.2); color: #9ca3af; border: 1px solid #4b5563; }
    .metrics-row {
      display: flex;
      gap: 10px;
      font-size: 12px;
      color: var(--text-muted);
      flex-wrap: wrap;
    }
    .metric-val {
      color: #ffffff;
      font-weight: 600;
    }
    .player-row {
      display: flex;
      align-items: center;
      gap: 10px;
      background: #151d2c;
      padding: 8px 12px;
      border-radius: 6px;
    }
    .toggle-btn {
      background: #2563eb;
      color: #ffffff;
      border: none;
      padding: 6px 12px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 700;
      cursor: pointer;
      min-width: 90px;
      text-align: center;
      transition: background 0.15s;
    }
    .toggle-btn.orig {
      background: #8b5cf6;
    }
    .toggle-btn:hover {
      opacity: 0.9;
    }
    audio {
      width: 100%;
      height: 32px;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>
        <span>🥁</span> SA3 Drum Separator — Gate G0 Codec Ceiling Console
      </h1>
      <p class="subtitle">
        Evaluating SAME-L (44.1 kHz, 10.77 fps) autoencoder round-trip transient fidelity on Kim's studio multitracks.<br>
        Rule: Onset F1 @ 20 ms &ge; 0.90 and Attack Energy &ge; -3.0 dB. Use the A/B toggle button to switch instantly between Ground Truth and SAME-L Reconstructed audio.
      </p>
      <div class="stat-row">
        <div class="stat-pill"><strong>Verdict:</strong> <span style="color: #34d399;">Kick & All Hats Passed (F1 &ge; 0.98, Atk &ge; -0.7 dB)</span></div>
        <div class="stat-pill"><strong>Kick SI-SDR:</strong> <span style="color: #38bdf8;">+27.0 dB</span></div>
        <div class="stat-pill"><strong>Hi-Hat Onset F1 @ 20ms:</strong> <span style="color: #38bdf8;">0.983 &ndash; 1.00</span></div>
        <div class="stat-pill"><strong>Latent Additivity:</strong> <span style="color: #f59e0b;">Non-linear (34.15 dB LSD) &rarr; Mix conditioning required</span></div>
      </div>
    </header>

    <!-- CONTENT -->
    {SONG_SECTIONS}

  </div>

  <script>
    function toggleTrack(btn, origSrc, reconSrc, audioId) {
      const audio = document.getElementById(audioId);
      const isRecon = btn.classList.contains("recon");
      const curTime = audio.currentTime;
      const isPlaying = !audio.paused;

      if (isRecon) {
        audio.src = origSrc;
        btn.textContent = "ORIG (GT)";
        btn.classList.remove("recon");
        btn.classList.add("orig");
      } else {
        audio.src = reconSrc;
        btn.textContent = "RECON";
        btn.classList.remove("orig");
        btn.classList.add("recon");
      }
      audio.currentTime = curTime;
      if (isPlaying) {
        audio.play();
      }
    }
  </script>
</body>
</html>
"""

def main():
    if not RESULTS_JSON.exists():
        print(f"Error: {RESULTS_JSON} not found!")
        return

    data = json.loads(RESULTS_JSON.read_text())
    songs = data["songs"]

    sections_html = []
    card_idx = 0

    for song_entry in songs:
        song_name = song_entry["song"]
        tracks = song_entry["tracks"]
        add = song_entry.get("additivity", {})

        cards_html = []
        for stem_name, m in tracks.items():
            card_idx += 1
            audio_id = f"audio_{card_idx}"
            orig_file = f"{song_name}__{stem_name}__orig.wav"
            recon_file = f"{song_name}__{stem_name}__recon.wav"

            n_onsets = m.get("n_onsets", 0)
            f1_20 = m.get("onset_f1_20", float("nan"))
            atk_db = m.get("attack_db", float("nan"))
            lsd = m.get("lsd_db", 0.0)
            si_sdr = m.get("si_sdr_db", 0.0)

            # Determine badge
            if n_onsets == 0:
                badge = '<span class="badge-f1 badge-nan">SILENT / 0 ONSETS</span>'
            elif f1_20 >= 0.90 and (atk_db == atk_db and atk_db >= -3.0):
                badge = f'<span class="badge-f1 badge-pass">PASS (F1: {f1_20:.2f})</span>'
            else:
                badge = f'<span class="badge-f1 badge-fail">FAIL (F1: {f1_20:.2f})</span>'

            f1_str = f"{f1_20:.2f}" if f1_20 == f1_20 else "N/A"
            atk_str = f"{atk_db:+.1f} dB" if atk_db == atk_db else "N/A"
            si_sdr_str = f"{si_sdr:.1f} dB" if si_sdr == si_sdr else "N/A"

            cards_html.append(f"""
            <div class="stem-card">
              <div class="stem-top">
                <span class="stem-name">{"Drum Bus" if stem_name == "__bus__" else stem_name}</span>
                {badge}
              </div>
              <div class="metrics-row">
                <span>LSD: <span class="metric-val">{lsd:.1f} dB</span></span>
                <span>F1@20ms: <span class="metric-val">{f1_str}</span></span>
                <span>Attack &Delta;: <span class="metric-val">{atk_str}</span></span>
                <span>SI-SDR: <span class="metric-val">{si_sdr_str}</span></span>
                <span>Onsets: <span class="metric-val">{n_onsets}</span></span>
              </div>
              <div class="player-row">
                <button class="toggle-btn recon" onclick="toggleTrack(this, '{orig_file}', '{recon_file}', '{audio_id}')">RECON</button>
                <audio id="{audio_id}" controls preload="metadata" src="{recon_file}"></audio>
              </div>
            </div>
            """)

        add_str = f"Sum-vs-Bus LSD: {add.get('sum_vs_bus_lsd_db', 0):.2f} dB | Latent Sum LSD: {add.get('latent_sum_lsd_db', 0):.2f} dB" if add else ""
        sections_html.append(f"""
        <div class="song-section">
          <div class="song-header">
            <span class="song-title">{song_name.replace('_', ' ')}</span>
            <span class="song-additivity">{add_str}</span>
          </div>
          <div class="stem-grid">
            {''.join(cards_html)}
          </div>
        </div>
        """)

    final_html = HTML_TEMPLATE.replace("{SONG_SECTIONS}", "\n".join(sections_html))
    HTML_PATH.write_text(final_html, encoding="utf-8")
    print(f"Audition console written successfully to: {HTML_PATH}")

if __name__ == "__main__":
    main()
