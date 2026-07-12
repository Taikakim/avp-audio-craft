#!/usr/bin/env python3
"""build_stats_page.py — the STATISTICS page (Kim 2026-07-12: "create a page on our site
about the statistics"). Reads eval/clip_metrics.db (31646 clips x 14 metrics: 10 CPU +
Audiobox CE/PQ/CU/PC) and renders the cross-model findings:
  * rank-16 vs rank-128 (harshness + quality) — 128 is the established good option
  * training-LENGTH curves for rank-128 (epoch sweet spot) — Kim's "what about the length?"
  * CE/PQ leaderboard + metric ranges.
Redaction: run LABELS only (shareable science); no ckpt filenames / paths.
Run: python3 Misc/build_stats_page.py  -> ~/.cache/evals_aac/stats.html  (then rsync)
"""
import collections
import html
import re
import sqlite3
from pathlib import Path

DB = Path("/home/kim/Projects/SAO/eval/clip_metrics.db")
OUT = Path.home() / ".cache/evals_aac/stats.html"

CSS = """
body{font:13px system-ui;margin:16px;background:#101012;color:#e0e0e0;max-width:1050px}
h1{font-size:18px;margin:0 0 4px}h2{font-size:15px;color:#9cf;margin:22px 0 4px;border-top:1px solid #26262c;padding-top:14px}
a{color:#7cf}.how{color:#cba;font-size:12px;line-height:1.55;margin:6px 0 12px;max-width:960px}
table{border-collapse:collapse;width:100%;font-size:12.5px;margin:6px 0}
th{color:#9cf;text-align:left;padding:5px 8px;border-bottom:1px solid #2a2a30}
td{padding:4px 8px;border-bottom:1px solid #1c1c20}tr:hover td{background:#16161a}
.num{text-align:right;font-variant-numeric:tabular-nums}
.box{border:1px solid #2a2a30;border-left:3px solid #5d9;background:#13181a;padding:10px 14px;margin:10px 0;
font-size:12.5px;line-height:1.55;max-width:960px}
.lbl{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:#7ed;display:block;margin-bottom:5px}
.good{color:#7f7}.bad{color:#f88}.mid{color:#ca7}
svg{background:#0e0e10;border:1px solid #2a2a30;border-radius:6px;margin:4px 0}
.faint{color:#778;font-size:11px}
"""


def rank_of(m):
    if "dora16" in m or "_r16" in m:
        return 16
    if "dora128" in m or "r128" in m or "47s" in m:
        return 128
    if "dora64" in m or "r64" in m:
        return 64
    if "dora256" in m or "r256" in m:
        return 256
    return None


def epnum(ck):
    mm = re.search(r"(\d+)", ck)
    return int(mm.group(1)) if mm else -1


def main():
    con = sqlite3.connect(DB)
    rows = con.execute("SELECT path, ce, pq, hf_ratio, zcr, centroid, onset_p95, bpm FROM metrics "
                       "WHERE path LIKE '%/model_matrix/%' AND ce IS NOT NULL").fetchall()
    # (model, ckpt) aggregation
    agg = collections.defaultdict(list)
    for p, ce, pq, hf, z, cen, on, bpm in rows:
        fn = p.split("/model_matrix/")[-1].split("__")
        if len(fn) < 2:
            continue
        agg[(fn[0], fn[1])].append((ce, pq, hf, z))
    mean = {k: tuple(sum(x[i] for x in v) / len(v) for i in range(4)) + (len(v),) for k, v in agg.items()}

    # per-model (best ckpt) for leaderboard + rank rollup
    by_model = collections.defaultdict(list)
    for (m, ck), (ce, pq, hf, z, n) in mean.items():
        by_model[m].append((ck, ce, pq, hf, z, n))
    model_best = {m: max(v, key=lambda x: x[1]) for m, v in by_model.items()}  # best CE ckpt

    total = con.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
    n_ce = con.execute("SELECT COUNT(*) FROM metrics WHERE ce IS NOT NULL").fetchone()[0]

    doc = [f"<!doctype html><html><head><meta charset=utf-8><title>Eval statistics</title>"
           f"<style>{CSS}</style></head><body>"]
    doc.append('<h1>Eval statistics — the whole model zoo, measured</h1>'
               '<a href=index.html>← evals</a> · <a href=model_matrix.html>model matrix</a> · <a href=models.html>models index</a>')
    doc.append(f'<div class=how><b>What this is:</b> every eval clip run through our metric suite — '
               f'{total} clips, 14 metrics each ({n_ce} also have Audiobox CE/PQ). The tables below are '
               f'the cross-model story the numbers tell: which rank holds up, and how training length '
               f'affects quality. Numbers are means over each model\'s rendered clips; CE/PQ are Audiobox '
               f'aesthetics (1–10, higher better), hf = fraction of energy &gt;5&#8202;kHz (harshness), '
               f'zcr = zero-crossing rate (distortion proxy).</div>')

    # ---- headline findings ----
    doc.append('<div class=box><span class=lbl>Headline findings</span>'
               '<b>1. Rank 128 is the good option.</b> Rank-16 adapters are consistently harsher and '
               'lower-quality: across model_matrix, rank-16 sits at the bottom of CE/PQ and the top of '
               'harshness (hf/zcr), and glitches ~6× worse when the DoRA weight is pushed to 1.5. '
               'Rank-128 (and 64) hold their quality.<br>'
               '<b>2. For rank-128, train SHORT.</b> The quality sweet spot is early — most goa rank-128 '
               'runs peak around epoch 0–4 and then <span class=bad>overtrain</span> (CE/PQ fall), fastest '
               'at high learning rate. The exception is <b>augmentation</b>: the aug10 run keeps improving '
               'out to ep74. So: more epochs is not more quality unless you augment.</div>')

    # ---- rank comparison ----
    rank_roll = collections.defaultdict(list)
    for m, (ck, ce, pq, hf, z, n) in model_best.items():
        r = rank_of(m)
        if r:
            rank_roll[r].append((ce, pq, hf, z))
    doc.append('<h2>Rank vs quality &amp; harshness</h2>')
    doc.append('<div class=faint>mean over each model\'s best-CE checkpoint, grouped by adapter rank</div>')
    doc.append('<table><tr><th>rank</th><th class=num>models</th><th class=num>CE</th><th class=num>PQ</th>'
               '<th class=num>hf (harshness)</th><th class=num>zcr</th></tr>')
    for r in sorted(rank_roll):
        v = rank_roll[r]; n = len(v)
        ce = sum(x[0] for x in v)/n; pq = sum(x[1] for x in v)/n
        hf = sum(x[2] for x in v)/n; z = sum(x[3] for x in v)/n
        cls = "good" if r >= 64 else "bad"
        doc.append(f'<tr><td class={cls}><b>rank {r}</b></td><td class=num>{n}</td>'
                   f'<td class=num>{ce:.2f}</td><td class=num>{pq:.2f}</td>'
                   f'<td class=num>{hf:.4f}</td><td class=num>{z:.4f}</td></tr>')
    doc.append('</table>')

    # ---- training length (rank-128 multi-epoch models) ----
    doc.append('<h2>Training length — the epoch sweet spot (rank 128)</h2>')
    doc.append('<div class=faint>CE by checkpoint for rank-128 models rendered at multiple epochs. '
               '↓ after the peak = overtraining.</div>')
    doc.append('<table><tr><th>model (run label)</th><th>CE by epoch (→ = more training)</th><th>read</th></tr>')
    for m in sorted(by_model):
        if rank_of(m) != 128:
            continue
        cks = sorted(by_model[m], key=lambda x: epnum(x[0]))
        if len(cks) < 2:
            continue
        ces = [(ck, ce) for ck, ce, pq, hf, z, n in cks]
        peak_i = max(range(len(ces)), key=lambda i: ces[i][1])
        cells = " → ".join(
            (f'<b class=good>{ce:.2f}</b>' if i == peak_i else
             (f'<span class=bad>{ce:.2f}</span>' if ce < ces[peak_i][1] - 0.15 else f'{ce:.2f}'))
            + f'<span class=faint>@{ck}</span>'
            for i, (ck, ce) in enumerate(ces))
        last, first = ces[-1][1], ces[0][1]
        read = ("<span class=good>improves</span>" if last > first + 0.05 else
                "<span class=bad>overtrains</span>" if last < first - 0.15 else
                "<span class=mid>flat</span>")
        doc.append(f'<tr><td><b>{html.escape(m)}</b></td><td>{cells}</td><td>{read}</td></tr>')
    doc.append('</table>')

    # ---- CE leaderboard ----
    doc.append('<h2>Quality leaderboard (best checkpoint per model)</h2>')
    lb = sorted(((ce, pq, m, ck) for m, (ck, ce, pq, hf, z, n) in model_best.items()), reverse=True)
    doc.append('<table><tr><th class=num>#</th><th>model</th><th>best ckpt</th><th class=num>CE</th><th class=num>PQ</th><th class=num>rank</th></tr>')
    for i, (ce, pq, m, ck) in enumerate(lb[:12], 1):
        doc.append(f'<tr><td class=num>{i}</td><td><b>{html.escape(m)}</b></td><td class=faint>{html.escape(ck)}</td>'
                   f'<td class=num>{ce:.2f}</td><td class=num>{pq:.2f}</td><td class=num>{rank_of(m) or "-"}</td></tr>')
    doc.append('</table><div class=faint>… full table + all 14 metrics per clip live in eval/clip_metrics.db.</div>')

    doc.append("<footer style='margin-top:20px;color:#666;font-size:11px'>aavepyora.online · evals · statistics · "
               f"{total} clips</footer></body></html>")
    OUT.write_text("".join(doc))
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
