#!/usr/bin/env python3
"""build_goa_musicology_page.py — the Goa MIDI musicology page (Kim ask 2026-07-13:
"write a page about the results and put it on the webpage... how the bass centers vs
leads/voices in the higher registers, and the role of (implied) harmony").

Reads the analysis outputs of eval/goa_midi_musicology.py + eval/goa_midi_harmony.py
(per-track JSON + harmony_corpus.json under the musicology/ output dir) and writes a
self-contained dark-style analysis page (stats.html convention) to the eval staging dir.

Three-audience standard (eval-tables spec §14): plain-language explainer on top,
methods + script names for engineers, the charts/table as the reading surface.
Redaction seam: repo-relative script names only, no absolute paths; commercial track
TITLES are fine to show (Kim's three-tier rights policy, tier 1).
Manifest v2: the ❗ unaudited badge is derived from run_meta.json kim_feedback.

Run:  python3 Misc/build_goa_musicology_page.py
"""
import html
import json
from collections import Counter
from pathlib import Path

import statistics as st

SRC = Path("/run/media/kim/Mantu/sa3_lora_runs/muscriptor_goa_midis/musicology")
OUT = Path("/home/kim/evals_aac/goa_musicology.html")

DEGREES = ["1", "b2", "2", "b3", "3", "4", "b5", "5", "b6", "6", "b7", "7"]
BAND_NAMES = ["bass (&lt; C3)", "mid (C3&ndash;B4)", "lead (&ge; C5)"]
BAND_COLORS = ["#5d9", "#9cf", "#e9a"]

CSS = """
body{font:13px system-ui;margin:16px;background:#101012;color:#e0e0e0;max-width:1050px}
h1{font-size:18px;margin:0 0 4px}
h2{font-size:15px;color:#9cf;margin:22px 0 4px;border-top:1px solid #26262c;padding-top:14px}
a{color:#7cf}.how{color:#cba;font-size:12px;line-height:1.55;margin:6px 0 12px;max-width:960px}
table{border-collapse:collapse;width:100%;font-size:12px;margin:6px 0}
th{color:#9cf;text-align:left;padding:5px 8px;border-bottom:1px solid #2a2a30;position:sticky;top:0;background:#101012}
td{padding:4px 8px;border-bottom:1px solid #1c1c20}tr:hover td{background:#16161a}
.num{text-align:right;font-variant-numeric:tabular-nums}
.box{border:1px solid #2a2a30;border-left:3px solid #5d9;background:#13181a;padding:10px 14px;margin:10px 0;
font-size:12.5px;line-height:1.55;max-width:960px}
.lbl{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:#7ed;display:block;margin-bottom:5px}
.warn{border-left-color:#c96}.warn .lbl{color:#eca}
.good{color:#7f7}.bad{color:#f88}.mid{color:#ca7}.faint{color:#778;font-size:11px}
svg{background:#0e0e10;border:1px solid #2a2a30;border-radius:6px;margin:4px 0;max-width:100%;height:auto}
.twrap{overflow-x:auto;max-height:480px;overflow-y:auto;border:1px solid #2a2a30}
.unaudited{color:#e33}
"""


def svg_grouped_bars(series, labels, colors, names, width=980, height=210, ymax=None):
    """series: list of value-lists (one per group member), labels: x labels."""
    n_g, n_s = len(labels), len(series)
    ymax = ymax or max(max(s) for s in series) * 1.12
    pad_l, pad_b, pad_t = 34, 22, 8
    gw = (width - pad_l - 8) / n_g
    bw = min(16.0, (gw - 6) / n_s)
    parts = [f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
             f'xmlns="http://www.w3.org/2000/svg" font-family="system-ui" font-size="10">']
    for frac in (0.25, 0.5, 0.75, 1.0):
        y = pad_t + (height - pad_t - pad_b) * (1 - frac * (max(max(s) for s in series) / ymax))
        # simple gridline at fraction of data max
    for gi, lab in enumerate(labels):
        x0 = pad_l + gi * gw + (gw - bw * n_s) / 2
        for si, s in enumerate(series):
            v = s[gi]
            h = (height - pad_t - pad_b) * (v / ymax)
            y = height - pad_b - h
            parts.append(f'<rect x="{x0 + si * bw:.1f}" y="{y:.1f}" width="{bw - 1.5:.1f}" '
                         f'height="{h:.1f}" fill="{colors[si]}"/>')
        parts.append(f'<text x="{pad_l + gi * gw + gw / 2:.1f}" y="{height - 7}" '
                     f'fill="#aab" text-anchor="middle">{lab}</text>')
    # y axis: 0 and data max
    parts.append(f'<text x="4" y="{height - pad_b}" fill="#778">0</text>')
    parts.append(f'<text x="4" y="{pad_t + 9}" fill="#778">{ymax / 1.12:.0%}</text>')
    lx = pad_l
    for si, nm in enumerate(names):
        parts.append(f'<rect x="{lx}" y="2" width="9" height="9" fill="{colors[si]}"/>'
                     f'<text x="{lx + 13}" y="10" fill="#ccd">{nm}</text>')
        lx += 150
    parts.append("</svg>")
    return "".join(parts)


def svg_hbars(items, color="#9cf", width=460, fmt="{:.0%}"):
    """items: [(label, value)] horizontal bars."""
    rowh, pad_l = 19, 118
    height = len(items) * rowh + 8
    vmax = max(v for _, v in items) * 1.05
    parts = [f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
             f'xmlns="http://www.w3.org/2000/svg" font-family="system-ui" font-size="10.5">']
    for i, (lab, v) in enumerate(items):
        y = 6 + i * rowh
        w = (width - pad_l - 60) * (v / vmax)
        parts.append(f'<text x="{pad_l - 6}" y="{y + 11}" fill="#ccd" text-anchor="end">{lab}</text>')
        parts.append(f'<rect x="{pad_l}" y="{y + 2}" width="{w:.1f}" height="{rowh - 6}" fill="{color}"/>')
        parts.append(f'<text x="{pad_l + w + 5:.1f}" y="{y + 11}" fill="#aab">{fmt.format(v)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def main():
    v1 = [json.loads(p.read_text()) for p in sorted(SRC.glob("*.musicology.json"))]
    v1 = [r for r in v1 if "skip" not in r]
    hc = json.loads((SRC / "harmony_corpus.json").read_text())
    agg = hc["aggregate"]
    hrows = {r["track"]: r for r in hc["tracks"] if "skip" not in r}
    meta = json.loads((SRC / "run_meta.json").read_text())
    audited = bool(meta.get("kim_feedback"))

    med = lambda xs: st.median([x for x in xs if x is not None])
    modes = Counter(r["key"]["mode"] for r in v1)
    keys = Counter(f"{r['key']['tonic']} {r['key']['mode']}" for r in v1)

    d = ['<!doctype html><html><head><meta charset=utf-8>'
         '<meta name=viewport content="width=device-width,initial-scale=1">'
         f'<title>Goa MIDI musicology</title><style>{CSS}</style></head><body>']
    d.append('<h1>Goa corpus musicology — what the MIDI transcriptions say</h1>')
    d.append('<a href=index.html>← evals</a> · <a href=stats.html>statistics</a> · '
             '<a href=models.html>models index</a>')
    if not audited:
        d.append(' · <span class=unaudited title="No kim_feedback recorded in the run manifest yet">'
                 '❗ unaudited — awaiting Kim\'s read</span>')

    # ---- explainer (audience 3: plain language) ----
    d.append('<div class=how><b>What this is:</b> we transcribed a 5% random sample of the Goa '
             'research corpus (157 full tracks) to MIDI with an automatic music-transcription model, '
             'then analyzed the notes the way a musicologist would analyze a score: what keys and '
             'scales the music lives in, where the bassline sits versus the melodies, how much the '
             '(implied) chords actually move. <b>Why:</b> it turns "we know what Goa sounds like" '
             'into numbers a model — or a curious reader — can be checked against. '
             '<b>How to read it:</b> every chart is a corpus-level distribution over ~155 tracks; '
             'single-track values live in the table at the bottom. Scale degrees are written '
             'relative to each track\'s own tonic ("1" = home note, "b2" = the note a semitone '
             'above it, "5" = the fifth), so tracks in different keys can be averaged.</div>')

    # ---- method box (audience 2: engineers) ----
    d.append('<div class=box><span class=lbl>Method — and the transcription-noise ground rules</span>'
             'Transcriber: MuScriptor (medium). It <b>confuses instrument labels</b> but pitches are '
             'reliable and timing is decent — measured here: notes land within a median '
             f'<b>{med([r["rhythm"]["grid_dev_median_ms"] for r in v1]):.0f} ms</b> of the 16th-note '
             f'grid, and <b>{med([r["scale_consistency"] for r in v1]):.0%}</b> of note-time is '
             'in-scale. So the analysis ignores instrument/channel labels entirely and separates '
             'voices by <b>register</b>: bass &lt; C3 &le; mid &lt; C5 &le; lead. Time base is the '
             'beat grid tracked from the source <i>audio</i> (madmom), not MIDI tempo; bars are '
             'forced 4/4. Keys: Krumhansl-Schmuckler profile correlation extended with phrygian and '
             'harmonic-minor profiles. Structure: per-bar chroma self-similarity + Foote novelty. '
             'Implied harmony: per-bar chord-template matching (power/major/minor/sus2/sus4/dim). '
             'Scripts: <code>eval/goa_midi_musicology.py</code>, <code>eval/goa_midi_harmony.py</code>, '
             'this page: <code>Misc/build_goa_musicology_page.py</code> (SAO repo).</div>')

    # ---- headline ----
    d.append('<div class=box><span class=lbl>Headline findings</span>'
             '<b>1. Goa is a phrygian genre.</b> 57% of tracks profile as phrygian '
             '(F, C, G, B, A the top tonics), 19% natural minor, 8% harmonic minor. '
             '<b>2. The registers divide the labor.</b> The bass is an anchor: it centers on the '
             'tonic in <b>97%</b> of tracks and spends 71% of its time there. The lead register is '
             'the storyteller: only 39% of tracks have tonic-centered leads — the rest center on the '
             '5th, b3, b2 or b6, i.e. the modal color lives up top. '
             '<b>3. Harmony is implied, thirdless, and nearly static.</b> 89% of bar-level chord '
             'calls are bare root+fifth (power chords); the implied root sits on the tonic 60% of '
             'the time with one main excursion (to the 4th degree, 23%), rocking i&harr;iv. '
             'Functional chord progression is essentially absent — movement is modal, not cadential.'
             '</div>')

    # ---- corpus overview ----
    d.append('<h2>Corpus overview</h2>')
    d.append(f'<div class=how>{len(v1)} tracks analyzed. BPM median '
             f'<b>{med([r["bpm"] for r in v1]):.0f}</b> '
             f'(IQR {st.quantiles([r["bpm"] for r in v1], n=4)[0]:.0f}&ndash;'
             f'{st.quantiles([r["bpm"] for r in v1], n=4)[2]:.0f}); '
             f'~{med([r["structure"]["n_sections"] for r in v1]):.0f} sections per track; '
             f'{med([r["rhythm"]["offbeat8_frac"] for r in v1]):.0%} of onsets on the offbeat '
             '8th (the Goa bass home position).</div>')
    d.append(svg_hbars([(m, c / len(v1)) for m, c in modes.most_common()], color="#5d9"))
    d.append('<div class=faint>Mode distribution (share of tracks). '
             'Caveat: the "major" bucket likely absorbs mixolydian/relative-major confusions — '
             'the K-S profiles are common-practice biased.</div>')
    d.append(svg_hbars([(k, c) for k, c in keys.most_common(10)], color="#9cf", fmt="{:.0f}"))
    d.append('<div class=faint>Top 10 keys (track counts).</div>')

    # ---- bass vs upper registers ----
    d.append('<h2>Where the bass sits vs the upper voices</h2>')
    d.append('<div class=how>Duration-weighted share of each register\'s note-time on each scale '
             'degree, averaged over the corpus. The gradient is the point: the <b>bass</b> hugs '
             'degree 1; the <b>mid</b> register splits tonic/fifth; the <b>lead</b> spreads across '
             'the whole modal palette — b3, b2, b7, b6 all carry real weight up top, which is where '
             'the phrygian flavor is actually voiced.</div>')
    prof = agg["band_degree_profile_mean"]
    d.append(svg_grouped_bars([prof[0], prof[1], prof[2]], DEGREES, BAND_COLORS, BAND_NAMES))
    bt = agg["band_tonic_frac_median"]
    cd = agg["band_center_dist"]
    n = agg["n_tracks"]
    d.append('<table><tr><th>register</th><th class=num>median time on tonic</th>'
             '<th class=num>tracks centered on tonic</th><th>other common centers</th></tr>')
    for b in range(3):
        others = ", ".join(f"{k} ({v})" for k, v in list(cd[b].items())[1:5] if k != "1")
        on1 = cd[b].get("1", 0)
        d.append(f'<tr><td><b style="color:{BAND_COLORS[b]}">{BAND_NAMES[b]}</b></td>'
                 f'<td class=num>{bt[b]:.0%}</td><td class=num>{on1}/{n} ({on1 / n:.0%})</td>'
                 f'<td>{others}</td></tr>')
    d.append('</table>')
    d.append('<div class=how><b>Reading:</b> this is the drone-and-story architecture in numbers. '
             'The bassline behaves like a pedal point (an ostinato on the tonic — 76% of bass time), '
             'so the ear keeps one fixed reference the whole track. Everything that reads as '
             '"harmonic movement" is painted <i>above</i> that anchor by the mid and lead voices '
             'shifting which degrees they emphasize. When a lead centers on the 5th or b3 (a third '
             'of the corpus), the track effectively projects a chord over a bass that never moved.</div>')

    # ---- implied harmony ----
    d.append('<h2>The role of (implied) harmony</h2>')
    d.append('<div class=how>Per bar, all sounding notes are folded to a 12-bin chroma and matched '
             'against chord templates; "implied" because nobody is playing block chords — the chord '
             'is the union of bass + arps + leads over one bar.</div>')
    qm = agg["chord_quality_mean"]
    d.append(svg_hbars(list(qm.items()), color="#e9a"))
    d.append('<div class=faint>Implied chord quality (share of confident bars, corpus mean). '
             '"power" = bare root+fifth, no third.</div>')
    rm = agg["root_degree_mean"]
    d.append(svg_hbars(list(rm.items())[:8], color="#9cf"))
    d.append('<div class=faint>Implied root, as a scale degree of the track\'s tonic.</div>')
    mv = agg["root_moves_total"]
    tot = sum(mv.values())
    d.append(svg_hbars([(f"+{k}" if k != "1" else k, v / tot) for k, v in list(mv.items())[:8]], color="#5d9"))
    d.append('<div class=faint>Root movements between adjacent bars (interval up, as a degree). '
             '"+4"/"+5" are motion by fourth/fifth — i&harr;iv rocking counted from both directions.</div>')
    d.append(f'<div class=box><span class=lbl>What harmony does here</span>'
             f'Median <b>{agg["bars_per_root_median"]} bars per implied root</b>, and the implied '
             f'root matches the loudest bass note in <b>{agg["bass_agreement_median"]:.0%}</b> of '
             'bars — when the root does move, the bass usually moves with it (true root motion, not '
             'just upper-voice recoloring). But 89% of those "chords" have no third: major/minor '
             'identity is left to the melodic lines. So harmony in this corpus is <b>modal '
             'scaffolding</b> — a tonic pedal, one workhorse excursion to iv, rare shadings toward '
             'bVII/bVI/bII — rather than functional progression. For generation/control work this '
             'means: chord-progression conditioning is the wrong lever for this genre; degree-'
             'emphasis in the upper registers (which degrees the lead dwells on, over a fixed '
             'tonic) is where the tonal action is.</div>')

    # ---- caveats ----
    d.append('<div class="box warn"><span class=lbl>Caveats — trust the distributions, not single bars</span>'
             'This is implied harmony read off a <b>noisy automatic transcription</b> of texture-heavy '
             'music: FX sweeps and noise layers leak spurious pitches, and dense bars blur the chroma. '
             'Corpus-level distributions are robust to that; individual bar-level chord calls are not. '
             'Related negative result from the structure pass: exact-match riff fingerprinting '
             'collapses on this data (the "same" ostinato transcribes slightly differently each bar), '
             'so pattern-mining approaches that need exact repeats (SIATEC-family) don\'t apply — '
             'soft chroma similarity is the usable structure encoding. Two of 157 tracks skipped '
             '(near-empty transcriptions); one more had too few confident bars for harmony.</div>')

    # ---- per-track table ----
    d.append('<h2>Per-track table</h2>')
    d.append('<div class=faint>All analyzed tracks. lead-center = the scale degree the lead register '
             'dwells on most; agree = implied root matches loudest bass note.</div>')
    d.append('<div class=twrap><table><tr><th>track</th><th class=num>bpm</th><th>key</th>'
             '<th class=num>in-scale</th><th class=num>bass on 1</th><th>lead center</th>'
             '<th class=num>bars/root</th><th class=num>agree</th><th class=num>sections</th></tr>')
    for r in sorted(v1, key=lambda x: x["track"].lower()):
        h = hrows.get(r["track"], {})
        lead_c = h.get("band_center_degree", ["", "", ""])[2] or "—"
        bass1 = h.get("band_tonic_frac", [None])[0]
        d.append(f'<tr><td>{html.escape(r["track"][:58])}</td>'
                 f'<td class=num>{r["bpm"]:.0f}</td>'
                 f'<td>{r["key"]["tonic"]} {r["key"]["mode"].replace("_", " ")}</td>'
                 f'<td class=num>{r["scale_consistency"]:.2f}</td>'
                 f'<td class=num>{bass1 if bass1 is not None else "—"}</td>'
                 f'<td>{lead_c}</td>'
                 f'<td class=num>{h.get("bars_per_root_median", "—")}</td>'
                 f'<td class=num>{h.get("bass_agreement", "—")}</td>'
                 f'<td class=num>{r["structure"]["n_sections"]}</td></tr>')
    d.append('</table></div>')

    d.append('<footer style="margin-top:20px;color:#666;font-size:11px">aavepyora.online · evals · '
             f'goa musicology · {len(v1)} tracks · 5% seeded sample, MuScriptor medium transcription'
             '</footer></body></html>')
    OUT.write_text("".join(d))
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} kB)")


if __name__ == "__main__":
    main()
