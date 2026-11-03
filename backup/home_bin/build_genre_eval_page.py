#!/usr/bin/env python3
"""build_genre_eval_page.py — edg3-styled genre-steering eval page with same-playhead
playable cells (the familiar eval-GUI behaviour: click a cell to play; switching cells keeps
the playhead position so you compare the same moment; re-click stops). Reads the round-2
genre_eval scores, transcodes clips to AAC .m4a, emits the page, uploads to aavepyora
/files/evals/genre_steering/. Deterministic — zero LLM tokens on re-run.
"""
import html
import json
import os
import subprocess
from pathlib import Path

RUNS = Path("/run/media/kim/Mantu/sa3_control_runs")
STAGE = Path("/home/kim/.cache/genre_eval_page")
KEY = "/home/kim/.ssh/id_ed25519"
HOST = "dh_4txyt6@iad1-shared-b8-25.dreamhost.com"
DEST = "/home/dh_4txyt6/aavepyora.online/files/evals/genre_steering"

ROW_ORDER = ["baseline", "Goa Trance", "Psy-Trance", "Trance", "Progressive Trance", "Acid"]
COLS = [("C", 1234, "fpC · seed A"), ("C", 5678, "fpC · seed B"),
        ("A", 1234, "fpA · seed A"), ("A", 5678, "fpA · seed B")]
FIGLET = ("█▀▀▀ █▀▀▄ █▀▀▀ ▀▀▀█\n█▀▀  █  █ █ ▀█  ▀▀█\n█▄▄▄ █▄▄▀ █▄▄█ ▄▄▄█")


def load(V):
    p = RUNS / f"genre_eval_fp{V}_r2" / "genre_scores.json"
    return json.load(open(p))["results"] if p.exists() else []


def transcode(src: Path, dst: Path):
    if dst.exists() or not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(src),
                    "-c:a", "aac", "-b:a", "128k", str(dst)], check=False)


def cell(r):
    """A playable cell: measured argmax + target confidence + hit marker."""
    if r is None:
        return '<td class="gcell empty">—</td>'
    m4a = r["file"].rsplit(".", 1)[0] + ".m4a"
    am = r["argmax"].split("---")[-1]
    tp = r.get("target_prob")
    is_base = r["genre_idx"] < 0
    hit = (not is_base) and r["argmax"] == r.get("target_label")
    badge = "" if is_base else (
        f'<span class="hit">✓ {tp:.2f}</span>' if hit
        else f'<span class="miss">{am} {r["measured"][r["argmax"]]:.2f}</span>')
    label = am if is_base else (f'{tp:.2f}' if hit else '·')
    cls = "gcell" + (" base" if is_base else (" hit-cell" if hit else ""))
    return (f'<td class="{cls}"><button class="play" data-src="{html.escape(m4a)}" '
            f'onclick="playCell(this)"><span class="tri">▶</span>'
            f'<span class="pl">{html.escape(label)}</span></button>'
            f'<div class="meas">{badge or ("→ " + html.escape(am))}</div></td>')


def main():
    STAGE.mkdir(parents=True, exist_ok=True)
    idx = {}  # (variant, genre, seed) -> result
    for V in ("A", "C"):
        for r in load(V):
            idx[(V, r["genre"], r["seed"])] = r
            transcode(RUNS / f"genre_eval_fp{V}_r2" / r["file"],
                      STAGE / (r["file"].rsplit(".", 1)[0] + ".m4a"))

    rows = []
    for g in ROW_ORDER:
        tds = "".join(cell(idx.get((V, g, s))) for V, s, _ in COLS)
        gl = "null fingerprint" if g == "baseline" else g
        rows.append(f'  <tr><th class="rowh">{html.escape(gl)}</th>{tds}</tr>')
    colh = "".join(f'<th>{html.escape(lbl)}</th>' for _, _, lbl in COLS)

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Genre steering — Vibe on The Edg3</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../../edg3.css">
<style>
  .gtable {{ border-collapse:collapse; width:100%; margin:1.2rem 0; }}
  .gtable th, .gtable td {{ border:1px solid var(--rule,#2a2c33); padding:.4rem; text-align:center; vertical-align:top; }}
  .gtable th {{ font-size:.82rem; color:var(--muted,#8a8d96); font-weight:500; }}
  .rowh {{ text-align:left!important; white-space:nowrap; color:var(--fg,#d7d9de); }}
  .gcell.base {{ background:rgba(255,255,255,.02); }}
  .gcell.hit-cell {{ background:rgba(120,200,120,.10); }}
  .play {{ cursor:pointer; background:transparent; border:0; color:inherit; font:inherit; display:flex; gap:.35rem; align-items:center; margin:0 auto; }}
  .play .tri {{ opacity:.55; }}
  .play.playing .tri {{ opacity:1; color:#8fd18f; }}
  .play.playing {{ text-shadow:0 0 8px rgba(140,210,140,.5); }}
  .pl {{ font-variant-numeric:tabular-nums; }}
  .meas {{ font-size:.72rem; margin-top:.25rem; color:var(--muted,#8a8d96); }}
  .hit {{ color:#8fd18f; }} .miss {{ color:#c98d8d; }}
  .playhead {{ font-size:.8rem; color:var(--muted,#8a8d96); }}
</style>
</head>
<body>
<div class="wrap">
<header class="masthead compact">
  <p class="over">VIBE&nbsp;ON&nbsp;THE</p>
  <pre class="figlet"><a href="../../index.html" style="color:inherit">{FIGLET}</a></pre>
  <nav class="mainnav">
    <a href="../../index.html">index</a>
    <a href="../../dialogue.html">dialogue</a>
    <a href="../index.html">evals</a>
    <a href="../../fusion-optimiser.html">fusion</a>
    <a href="../../reference.html">reference</a>
    <span class="status">genre steering</span>
  </nav>
</header>

<h1>Genre steering — does the fingerprint move the sound?</h1>
<p class="lede">The style adapter is conditioned on a <strong>genre fingerprint</strong>. This
is the test RF loss can't do: hold the text prompt constant (<code>"electronic music"</code>)
and vary <em>only</em> the fingerprint's genre, then <strong>listen</strong> and measure the
output genre with the discogs-400 head. Click a cell to play; switching cells keeps the
playhead position, so you compare the same moment across renders. Re-click to stop.</p>
<p class="dim">Cells show the measured confidence of the <em>requested</em> genre; green = the
output's top genre matched the request. Rows are genres the model has real training data for.
The <strong>null-fingerprint</strong> row is the un-steered baseline. Verdict: <strong>fpC
(style-only) steers; fpA (style+groove) barely does</strong> — the groove dims dilute the
genre signal. Steering strength tracks corpus frequency (Goa ≫ Psy &gt; Trance ≫ tail): the
adapter learned a Goa↔Psy dial, and the sparse tail is data-limited, not architecture-limited.</p>

<p class="playhead">playhead: <span id="ph">0.0s</span> · <span id="now">—</span></p>
<table class="gtable">
  <tr><th class="rowh">conditioned genre</th>{colh}</tr>
{os.linesep.join(rows)}
</table>

<footer class="colophon">
  <span>aavepyora.online</span><span>·</span>
  <span>gain 6 · 15 s · discogs-400 measured</span><span>·</span>
  <span>fpC wins; corpus-frequency-limited</span>
  <span style="margin-left:auto"><span class="edge">▮</span> listen, don't just read</span>
</footer>
</div>
<audio id="au"></audio>
<script>
const au = document.getElementById('au'), ph = document.getElementById('ph'), now = document.getElementById('now');
let active = null;
au.addEventListener('timeupdate', () => {{ ph.textContent = au.currentTime.toFixed(1) + 's'; }});
function playCell(btn) {{
  const src = btn.dataset.src;
  if (active === btn) {{ au.pause(); btn.classList.remove('playing'); active = null; now.textContent='—'; return; }}
  const t = au.currentTime || 0;
  if (active) active.classList.remove('playing');
  au.src = src;
  au.addEventListener('loadedmetadata', function once() {{
    au.removeEventListener('loadedmetadata', once);
    try {{ au.currentTime = Math.min(t, Math.max(0, au.duration - 0.05)); }} catch (e) {{}}
    au.play();
  }});
  btn.classList.add('playing'); active = btn; now.textContent = src.replace('.m4a','');
}}
</script>
</body>
</html>
"""
    (STAGE / "index.html").write_text(doc)
    n = len(list(STAGE.glob("*.m4a")))
    subprocess.run(["ssh", "-o", "BatchMode=yes", "-i", KEY, HOST, f"mkdir -p {DEST}"], check=False)
    subprocess.run(["rsync", "-az", "--chmod=F644", "-e", f"ssh -o BatchMode=yes -i {KEY}",
                    str(STAGE) + "/", f"{HOST}:{DEST}/"], check=False)
    print(f"[genre-page] {n} clips + page -> {DEST}")


if __name__ == "__main__":
    main()
