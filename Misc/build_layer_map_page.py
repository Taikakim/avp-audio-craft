#!/usr/bin/env python3
"""
build_layer_map_page.py -- readable report page for the layer-mapping run
(layer_map_2026-07-10). Replaces the generic auto-player, which listed 48
cryptic clips with no story (Kim: "can't make head or tails of what should I
read from these").

What the page explains (the honest structure of this run):
  * The RESULT is numeric: per-(block, module) causal impact profiles -- charted
    here as inline SVG (median across pairs x seeds, winsorized +-1.5), one chart
    per concept, three module lines each.
  * The AUDIO is the measurement BASELINES only: for each prompt pair, A = the
    concept prompt, B = the counterfactual. The 1728 patched generations were
    measured and discarded -- so what you can HEAR is whether each concept's
    A/B contrast is real (the denominator of every impact number), not the
    layer effects themselves.

Run: python3 Misc/build_layer_map_page.py   (then rsync the index.html)
"""
import html
import json
from pathlib import Path

import numpy as np

SRC = Path("/run/media/kim/Mantu/sa3_control_runs/layer_map_2026-07-10")
OUT = Path.home() / ".cache/evals_aac/renders/layer_map_2026-07-10/index.html"

# Phase-3 concept-steering A/B (CONTINUITY, 2026-07-11): diff-in-means directions
# extracted at the bottleneck layers this page localizes, injected conditional-branch
# only (the deep-research CFG rule), alpha ladder. This is the causal map's PAYOFF:
# the page says WHERE each concept lives; steering INJECTS a direction there and it
# steers. Clips staged under steer/. run_meta carries layers + held-out AUC; the
# measured Essentia delta is read from run_meta["result"] when CONTINUITY persists it
# (chat-only == lost, per MASTER), else the cell shows AUC + "listen".
STEER_SRC = Path("/run/media/kim/Mantu/sa3_lora_runs/concept_steering")
STEER_FEATURES = ("mt_dark", "mt_uplifting", "mt_relaxing", "onset_density")
STEER_BLURB = {
    "mt_dark": "darkness / minor-key gloom",
    "mt_uplifting": "uplifting / major brightness",
    "mt_relaxing": "relaxed / calm",
    "onset_density": "onset density (events/sec)",
}
# Plain-language "what you should hear" per feature — the listening verdict, so the
# page is evaluable by ear, not just by the metric string (Kim 2026-07-12: "how should
# I evaluate? many of these are just buzzes"). (result, works?) → verdict tag drives color.
STEER_LISTEN = {
    "mt_dark": ("WORKS", "α+2 should sound clearly <b>darker / gloomier</b> than the α0 "
                "baseline while staying musical — this is the strong win (dark-score 19× at +2). "
                "α−2 should feel a touch brighter."),
    "mt_uplifting": ("PARTIAL", "Asymmetric: <b>α+2 does NOT sound more uplifting</b> — it just "
                     "degrades. Only the anti-direction moves (α−2 flatter/darker). A half-result."),
    "mt_relaxing": ("DEAD", "The honest negative: <b>α+2 sounds basically the SAME as α0</b> — no "
                    "calm shift, even though the probe said this concept was highly separable "
                    "(AUC .889). Probe-separable ≠ steerable. Listening confirms it."),
    "onset_density": ("PARTIAL", "α+2 should sound <b>busier — ~20% more note/hit events</b> — than "
                      "α0, still coherent. This is a scalar (density), not a mood."),
}
_VERDICT_COLOR = {"WORKS": "#5d9", "PARTIAL": "#ca7", "DEAD": "#a66"}

MODULES = ("self_attn", "cross_attn", "ff")
MOD_COLOR = {"self_attn": "#5cf", "cross_attn": "#f76", "ff": "#7d6"}
CONCEPT_BLURB = {
    "onset_density": ("dense driving percussion vs sparse ambient",
                      "meter: p95-gated onset rate"),
    "brightness": ("bright sparkling highs vs dark muffled lows",
                   "meter: spectral centroid"),
    "bass_weight": ("massive sub-bass vs thin airy treble",
                    "meter: <150 Hz energy ratio"),
    "noisiness": ("harsh noise textures vs clean tonal pads",
                  "meter: spectral flatness"),
}

CSS = """
body{font:13px system-ui;margin:14px;background:#101012;color:#e0e0e0}
h1{font-size:17px;margin:0 0 4px}h2{font-size:14px;color:#9cf;margin:20px 0 4px}
a{color:#7cf}.tip{color:#8a8;font-size:12px;margin:4px 0 10px;max-width:920px;line-height:1.5}
.findings-box{border:1px solid #2a2a30;border-left:3px solid #5d9;background:#13181a;
padding:10px 14px;margin:8px 0;font-size:12.5px;color:#ddd;max-width:920px;line-height:1.55;white-space:pre-line}
.findings-box .lbl{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:#7ed;display:block;margin:0 0 6px}
#hdr{position:sticky;top:0;z-index:9;background:#16181c;padding:7px 12px;margin:-14px -14px 12px;
border-bottom:1px solid #2a2a30;font-size:13px}#np{color:#cde}#pos{color:#888}
.abrow{display:flex;gap:8px;margin:6px 0;flex-wrap:wrap;align-items:center}
.abrow .pairlbl{color:#889;font-size:11px;min-width:120px}
.abcell{background:#18181b;border:1px solid #2a2a2e;border-radius:6px;padding:7px 12px;
cursor:pointer;min-width:150px}
.abcell:hover{outline:1px solid #7cf}.abcell.playing{outline:2px solid #5d5 !important}
.abcell.loading{outline:2px solid #fa5 !important}
.abcell b{color:#9ec;display:block;font-size:12px}
.abcell .sub{color:#889;font-size:10.5px}
svg{background:#0e0e10;border:1px solid #2a2a30;border-radius:6px;margin:4px 0}
.legend{font-size:11px;color:#9aa;margin:2px 0 8px}
.how{color:#cba;font-size:12px;max-width:920px;line-height:1.5;margin:6px 0}
"""

PLAYER_JS = """<audio id="pl"></audio><script>
let cur=null,ph=0;const a=document.getElementById('pl');
a.loop=true;
a.addEventListener('timeupdate',()=>{if(!a.paused)ph=a.currentTime});
a.addEventListener('ended',()=>{if(cur){cur.classList.remove('playing');cur=null}ph=0});
a.addEventListener('waiting',()=>{const l=document.getElementById('ld');if(l)l.textContent='loading…';if(cur)cur.classList.add('loading')});
a.addEventListener('playing',()=>{const l=document.getElementById('ld');if(l)l.textContent='';if(cur)cur.classList.remove('loading')});
function seekAndPlay(pos){
 const go=()=>{try{const d=a.duration||1e9;a.currentTime=(pos>d-1)?0:Math.min(pos,d-0.05)}catch(e){}a.play()};
 if(a.readyState>=3){go();return}
 let done=false;const fire=()=>{if(done)return;done=true;go()};
 a.addEventListener('canplay',fire,{once:true});setTimeout(fire,1200)}
function startCell(el,s){
 const l=document.getElementById('ld');if(l)l.textContent='loading…';el.classList.add('loading');
 a.pause();a.src=s;seekAndPlay(ph);
 cur=el;el.classList.add('playing')}
function play(el){const s=el.dataset.src;
 if(cur===el){a.pause();el.classList.remove('playing','loading');cur=null;const l=document.getElementById('ld');if(l)l.textContent='';return}
 if(cur)cur.classList.remove('playing','loading');
 startCell(el,s)}
</script>"""


def impact_chart(concept, med_by_mod, w=920, h=230, pad=34):
    """One chart per concept: 24 layers on x, median impact on y, 3 module lines."""
    lo = min(-0.2, min(v.min() for v in med_by_mod.values()) - 0.05)
    hi = max(1.0, max(v.max() for v in med_by_mod.values()) + 0.05)
    pw, phh = w - 2 * pad, h - 2 * pad
    x = lambda i: pad + i / 23 * pw
    y = lambda v: pad + (1 - (v - lo) / (hi - lo)) * phh
    s = [f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">']
    s.append(f'<line x1="{pad}" y1="{y(0):.1f}" x2="{w-pad}" y2="{y(0):.1f}" stroke="#444"/>')
    s.append(f'<line x1="{pad}" y1="{y(1):.1f}" x2="{w-pad}" y2="{y(1):.1f}" stroke="#333" stroke-dasharray="3,4"/>')
    s.append(f'<text x="{w-pad+2}" y="{y(1)+4:.1f}" fill="#666" font-size="10">1.0 = full recovery</text>')
    s.append(f'<text x="{w-pad+2}" y="{y(0)+4:.1f}" fill="#666" font-size="10">0 = no effect</text>')
    for m, vals in med_by_mod.items():
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
        s.append(f'<polyline points="{pts}" fill="none" stroke="{MOD_COLOR[m]}" stroke-width="2"/>')
        for i, v in enumerate(vals):
            s.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="2.4" fill="{MOD_COLOR[m]}">'
                     f'<title>{m} block {i}: median impact {v:+.2f}</title></circle>')
    for i in (0, 4, 8, 12, 16, 20, 23):
        s.append(f'<text x="{x(i)-6:.1f}" y="{h-6}" fill="#777" font-size="10">{i}</text>')
    s.append(f'<text x="{pad}" y="{pad-8}" fill="#999" font-size="11">DiT block →</text>')
    s.append("</svg>")
    return "".join(s)


def steer_section():
    """Phase-3 steering payoff: playable alpha-ladder A/B per feature, same playhead."""
    out = []
    out.append('<h2>The payoff — training-free concept steering at the mapped layers</h2>')
    out.append('<div class="how" style="border-left:3px solid #5d9;padding-left:10px">'
               '<b>How to evaluate this — the 10-second version:</b><br>'
               'For each concept below, play <b>α 0</b> (the plain baseline) then <b>α +2</b> '
               '(steered). <b>The only question: does α +2 move the sound toward the concept</b> '
               '(darker, busier…) <b>while still sounding like music?</b> The <b>listen-for</b> line '
               'tells you what a win sounds like, and the badge (<span style="color:#5d9">WORKS</span> / '
               '<span style="color:#ca7">PARTIAL</span> / <span style="color:#a66">DEAD</span>) is the '
               'verdict — so you know whether to expect a real shift before you click.<br>'
               '<b style="color:#a66">Ignore the two grey "α ±6 — past safe range" clips for quality.</b> '
               'Those are deliberately pushed way past the working strength; they are <i>supposed</i> to '
               'collapse into buzz/noise, and that they do is the point — it confirms the safe-range limit '
               'the theory predicts. They are not failures to judge; they are the guardrail.</div>')
    any_clip = False
    for feat in STEER_FEATURES:
        meta_p = STEER_SRC / feat / "run_meta.json"
        if not meta_p.exists():
            continue
        meta = json.loads(meta_p.read_text())
        layers = meta.get("layers", [])
        hv = meta.get("held_out_validation", {})
        auc = hv.get("min_auc_across_sigma")
        result = meta.get("result") or meta.get("measured_delta") or ""
        verdict, listen = STEER_LISTEN.get(feat, ("", ""))
        vcol = _VERDICT_COLOR.get(verdict, "#889")
        badge = (f'<span style="background:{vcol};color:#111;border-radius:4px;padding:1px 7px;'
                 f'font-size:11px;font-weight:700;margin-left:8px">{verdict}</span>' if verdict else '')
        out.append(f'<h2 style="font-size:14px;color:#cde;margin-top:18px">{html.escape(feat)} '
                   f'<span style="color:#889;font-weight:normal;font-size:12px">— '
                   f'{html.escape(STEER_BLURB.get(feat, ""))}</span>{badge}</h2>')
        if listen:
            out.append(f'<div class=tip style="color:#cdd"><b>listen for:</b> {listen}</div>')
        # evaluable clips first (baseline, steer-toward, steer-away), prominently
        primary = [("a0", "α 0", "plain baseline"),
                   ("a+2.0", "α +2 →", "steered TOWARD the concept"),
                   ("a-2.0", "α −2", "steered away (anti-concept)")]
        cells = []
        for a, lbl, sub in primary:
            src = f"steer/{feat}_{a}.m4a"
            if not (OUT.parent / src).exists():
                continue
            any_clip = True
            hot = ' style="border-color:#5d9;border-width:2px"' if a == "a+2.0" else ''
            cells.append(f'<div class=abcell{hot} data-src="{src}" onclick="play(this)">'
                         f'<b>{html.escape(lbl)}</b><span class=sub>{html.escape(sub)}</span></div>')
        out.append('<div class=abrow>' + "".join(cells) + '</div>')
        # deliberately-broken breach clips, muted + labeled (not a quality test)
        breach = []
        for a, lbl in (("a-6.0", "α −6"), ("a+6.0", "α +6")):
            src = f"steer/{feat}_{a}.m4a"
            if not (OUT.parent / src).exists():
                continue
            breach.append(f'<div class=abcell data-src="{src}" onclick="play(this)" '
                          f'style="opacity:.5;border-color:#533;min-width:110px">'
                          f'<b style="color:#a66">{html.escape(lbl)}</b>'
                          f'<span class=sub>expected buzz</span></div>')
        if breach:
            out.append('<div class=abrow style="margin-top:2px"><span class=pairlbl '
                       'style="color:#a66;min-width:150px">past safe range (guardrail, not a test):</span>'
                       + "".join(breach) + '</div>')
        if result:
            out.append(f'<div class=tip style="color:#8a9;font-size:11px">measured: {html.escape(str(result))}'
                       + (f' · held-out AUC {auc:.3f}@L{hv.get("layer")}' if auc else '')
                       + f' · inject @ blocks {html.escape(str(layers))}</div>')
    return "".join(out) if any_clip else ""


CONVERGENCE = (
    "Three independent methods now localize acoustic/mood concepts to the SAME mid-stack "
    "band (~blocks 8–18), and none of them share machinery:\n"
    "• THIS PAGE — causal activation patching: patch one (block, module) and measure how much "
    "of the A→B attribute shift it recovers. Acoustic attributes concentrate in mid/late blocks "
    "via self_attn + ff (see the charts below).\n"
    "• TADA (arXiv 2602.11910, external) — the same causal-tracing lineage on other text-to-music "
    "DiTs finds a 2–4-block 'semantic bottleneck' at mid depth (e.g. blocks {12,13}).\n"
    "• CONTINUITY's diff-in-means mood probes — held-out split-half AUC peaks at L8–15 "
    "(meditative .925@L14, relaxing .889@L10, dark .789@L18).\n"
    "And SHIFT's timestep-invariant-direction claim replicates on SA3 (cross-σ direction "
    "stability .93–.99) — an external prediction that held, not just internal consistency. "
    "The steering section below is the operational proof: inject a direction at these blocks and "
    "the output moves."
)


def main():
    rows = [json.loads(l) for l in (SRC / "layer_map_results.jsonl").read_text().splitlines()]
    findings = (SRC / "FINDINGS.md").read_text().strip()
    agg = {}
    for r in rows:
        agg.setdefault((r["concept"], r["module"]), {}).setdefault(r["layer"], []).append(
            float(np.clip(r["impact"], -1.5, 1.5)))
    concepts = sorted({r["concept"] for r in rows})
    pairs = sorted({(r["concept"], r["pair"], r["seed"]) for r in rows})

    doc = [f"<!doctype html><html><head><meta charset=utf-8>"
           f"<title>Layer map — which DiT blocks carry each attribute</title><style>{CSS}</style></head><body>"]
    doc.append('<div id=hdr>&#9654; <b id=np>click a clip to play</b> <span id=pos></span>'
               ' <span id=ld style="color:#fa5"></span>'
               ' &nbsp;·&nbsp; <span style="color:#888">switching keeps the playhead; loops until stopped; re-click stops; amber outline = loading</span></div>')
    doc.append('<h1>Layer map — which DiT blocks causally carry each acoustic attribute</h1>'
               '<a href=../../index.html>← evals</a>')
    doc.append('<div class=how><b>How to read this page:</b> the RESULT of this run is the '
               'charts below — for each attribute, how much of the A→B attribute shift a single '
               'patched (block, module) causally recovers (median over 6 prompt-pair×seed runs; '
               '1728 patched generations measured, not kept). The AUDIO at the bottom is only the '
               'measurement <i>baselines</i>: A = concept prompt, B = counterfactual — listen to '
               'them to judge whether each concept\'s contrast was real (it\'s the denominator of '
               'every impact value). You cannot hear the layer effects themselves here; they were '
               'measured and discarded.</div>')
    doc.append(f'<div class=findings-box><span class=lbl>Findings (from the run record)</span>'
               f'{html.escape(findings)}</div>')

    doc.append(f'<div class=findings-box style="border-left-color:#c9a"><span class=lbl '
               f'style="color:#eca">Three-way convergence + the steering payoff</span>'
               f'{html.escape(CONVERGENCE)}</div>')

    steer_html = steer_section()
    if steer_html:
        doc.append(steer_html)

    doc.append('<h2>Impact profiles — the actual result</h2>')
    doc.append('<div class=legend>'
               + " &nbsp; ".join(f'<span style="color:{MOD_COLOR[m]}">■</span> {m}' for m in MODULES)
               + ' &nbsp;·&nbsp; y: fraction of the attribute shift recovered by patching that single site</div>')
    for c in concepts:
        blurb, meter = CONCEPT_BLURB.get(c, ("", ""))
        med = {m: np.array([float(np.median(agg[(c, m)].get(li, [np.nan]))) for li in range(24)])
               for m in MODULES if (c, m) in agg}
        doc.append(f'<h2>{html.escape(c)}</h2><div class=tip>{html.escape(blurb)} · {html.escape(meter)}</div>')
        doc.append(impact_chart(c, med))

    doc.append('<h2>Measurement baselines (A = concept, B = counterfactual)</h2>')
    doc.append('<div class=tip>Each pair below fed 72 patched generations. If A and B sound '
               'clearly different in the named attribute, that pair\'s impact numbers stand on '
               'solid ground; if they sound alike, discount that pair.</div>')
    by_c = {}
    for (c, p, s) in pairs:
        by_c.setdefault(c, set()).add((p, s))
    for c in concepts:
        doc.append(f'<h2 style="font-size:13px;color:#cde">{html.escape(c)}</h2>')
        for (p, s) in sorted(by_c[c]):
            a_f = f"{c}_p{p}_s{s}_A.m4a"
            b_f = f"{c}_p{p}_s{s}_B.m4a"
            doc.append('<div class=abrow>'
                       f'<span class=pairlbl>pair {p} · seed {s}</span>'
                       f'<div class=abcell data-src="{a_f}" onclick="play(this)"><b>A — concept</b>'
                       f'<span class=sub>{html.escape(CONCEPT_BLURB[c][0].split(" vs ")[0])}</span></div>'
                       f'<div class=abcell data-src="{b_f}" onclick="play(this)"><b>B — counterfactual</b>'
                       f'<span class=sub>{html.escape(CONCEPT_BLURB[c][0].split(" vs ")[1])}</span></div>'
                       '</div>')
    doc.append(PLAYER_JS)
    doc.append("<footer style='margin-top:20px;color:#666;font-size:11px'>aavepyora.online · evals · layer map</footer>")
    doc.append("</body></html>")
    OUT.write_text("".join(doc))
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes), {len(concepts)} concepts, {len(pairs)} A/B pairs")


if __name__ == "__main__":
    main()
