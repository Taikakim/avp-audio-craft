#!/usr/bin/env python3
"""
build_breathing_page.py -- standalone eval page for the #35 breathing-noise
controller's GPU validations (breathing_kaikkialla_evr1x_nl55/ = v1, and
breathing_kaikkialla_evr1x_v2/ = v2, both kaikkialla x evr1x).

v1 (tonight's first headline result): windowed a2a controller steers per-window
init_noise_level DOWN when output novelty collapses below the source's calibrated
floor (a loop forming), back UP once it recovers -- "breathing". Kim's listening
verdict on v1: the 0.45-0.55 oscillation band is TOO NARROW a mid-range -- too high
to let the source through, too low for real change -- accumulates a noisy/stringy/
pale sound, loses melody+bass (the 07-08 mid-noise-band U-shape finding, confirmed
by ear on the controller). v2 (CONTINUITY's same-day fix): full range 0.30-0.62,
ducks HARD to 0.30 at 4 detected source breaks (intro/breakdown/outro -- source
comes through clean), re-ramps + climbs to 0.62 ceiling, keeps the novelty-feedback
loop-break behavior. Page presents both versions + baselines with a SHARED playhead
so Kim can A/B v2 vs v1 vs baseline directly (CONTINUITY's ask, via W/G DM).

The sibling breathing_kaikkialla_evr1x/ (no suffix, requested_nl=0.7) is the earlier
flat-trajectory attempt the trailing-context fix corrects -- not paged, superseded.

Doesn't fit any existing template (a2a ladder pages are nl x adapter tables; this is
version x {breathing,baseline} clips + per-window trajectories) -- standalone page,
self-contained inline SVG (no external JS/CDN, matches every other page here).

Source track is Kim's own (Aavepyörä - Goddess Guerilla - Kaikki-Alla) -- no rights
question. Checkpoint redacted to "evr1x" (established shorthand, per
eval/mp_checkpoint_recipes.json's evr1x_note) -- never the raw ckpt path/filename.

Run: python3 Misc/build_breathing_page.py
"""
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_evals import WAVEFORM_CSS, WAVEFORM_JS  # noqa: E402 -- the shared floating
# waveform-popup player (eval-tables spec §13), reused verbatim rather than
# re-implemented -- this page predates the fleet-wide rollout across the main
# evals site; riffer-evals generators were explicitly left as a follow-up
# (Kim, 2026-07-10: "remember to use the new fixed one").

VERSIONS = [
    ("v1", Path("/run/media/kim/Mantu/sa3_lora_runs/breathing_kaikkialla_evr1x_nl55"),
     "v1 — tier-1 validation (novelty-floor trigger only)"),
    ("v2", Path("/run/media/kim/Mantu/sa3_lora_runs/breathing_kaikkialla_evr1x_v2"),
     "v2 — full-range + source-break ducking (fixes Kim's v1 verdict)"),
    ("v3", Path("/run/media/kim/Mantu/sa3_lora_runs/breathing_kaikkialla_evr1x_v3"),
     "v3 — deep flush 0.05 + HF-static meter (finding: high nl IS the static; stays source-crisp)"),
]
OUT = Path("/home/kim/riffer-evals/breathing.html")
CLIPS = "clips_breathing"

CSS = """
:root{--paper:#fafaf7;--paper-dim:#f2f3ef;--ink:#2b3538;--body:#3b4649;
--dim:#7a8a8e;--faint:#9aa7a9;--rule:#c9d2d0;--rule-light:#e2e6e2;--edge:#0f9e99;--edge-ink:#0c807c;
--mono:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace}
html{overflow-x:hidden}
body{font:13px system-ui;margin:14px;background:#101012;color:#e0e0e0;max-width:100vw;overflow-x:hidden}
h1{font-size:17px;margin:0 0 4px}h2{font-size:14px;color:#9cf;margin:18px 0 4px}
h3{font-size:13px;color:#cde;margin:16px 0 3px}
a{color:#7cf}.tip{color:#8a8;font-size:12px;margin:4px 0 10px}
.findings-box{border:1px solid #2a2a30;border-left:3px solid #5d9;background:#13181a;
padding:10px 14px;margin:8px 0;font-size:12.5px;color:#ddd;max-width:900px;line-height:1.55;white-space:pre-line}
.findings-box .lbl{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:#7ed;display:block;margin:0 0 6px}
.verdict-box{border:1px solid #4a2a2a;border-left:3px solid #d95;background:#1a1311;
padding:10px 14px;margin:8px 0;font-size:12.5px;color:#fdc;max-width:900px;line-height:1.55}
.verdict-box .lbl{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:#fb7;display:block;margin:0 0 6px}
.recipe{background:#11161c;border:1px solid #243;border-left:3px solid #58a;padding:7px 11px;
font-size:12px;margin:8px 0;max-width:900px;color:#bcd}
.version{border-top:1px solid #2a2a30;padding-top:14px;margin-top:20px}
#hdr{position:sticky;top:0;z-index:9;background:#16181c;padding:7px 12px;margin:-14px -14px 12px;
border-bottom:1px solid #2a2a30;font-size:13px}#np{color:#cde}#pos{color:#888}
.abrow{display:flex;gap:10px;margin:8px 0;flex-wrap:wrap}
.abcell{background:#18181b;border:1px solid #2a2a2e;border-radius:6px;padding:10px 16px;
cursor:pointer;min-width:220px}
.abcell:hover{outline:1px solid #7cf}.abcell.play{outline:2px solid #5d5 !important}
.abcell b{color:#9ec;display:block;font-size:13px;margin-bottom:2px}
.abcell .sub{color:#889;font-size:11px}
svg{background:#0e0e10;border:1px solid #2a2a30;border-radius:6px}
.legend{font-size:11px;color:#9aa;margin:4px 0 10px}
""" + WAVEFORM_CSS


def svg_trajectory(nl, novelty, cal, nl_lo=None, nl_hi=None):
    # auto-range the nl axis (v3 flushes to 0.05 — a fixed 0.25 floor would clip it)
    if nl_lo is None:
        nl_lo = max(0.0, min(nl) - 0.05)
    if nl_hi is None:
        nl_hi = max(nl) + 0.06
    n = len(nl)
    W, H, PAD = 900, 240, 30
    plot_w, plot_h = W - 2 * PAD, H - 2 * PAD

    def x(i):
        return PAD + (i / (n - 1)) * plot_w

    def y_nl(v):
        return PAD + (1 - (v - nl_lo) / (nl_hi - nl_lo)) * plot_h

    nov_lo, nov_hi = 0.0, 1.25

    def y_nov(v):
        return PAD + (1 - (v - nov_lo) / (nov_hi - nov_lo)) * plot_h

    nl_pts = " ".join(f"{x(i):.1f},{y_nl(v):.1f}" for i, v in enumerate(nl))
    nov_pts = " ".join(f"{x(i):.1f},{y_nov(v):.1f}" for i, v in enumerate(novelty))
    floor_y = y_nov(cal["novelty_floor"])
    median_y = y_nov(cal["novelty_median"])

    svg = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    svg.append(f'<line x1="{PAD}" y1="{floor_y:.1f}" x2="{W-PAD}" y2="{floor_y:.1f}" stroke="#666" stroke-dasharray="4,3"/>')
    svg.append(f'<line x1="{PAD}" y1="{median_y:.1f}" x2="{W-PAD}" y2="{median_y:.1f}" stroke="#999" stroke-dasharray="2,4"/>')
    svg.append(f'<polyline points="{nov_pts}" fill="none" stroke="#f95" stroke-width="2"/>')
    svg.append(f'<polyline points="{nl_pts}" fill="none" stroke="#5cf" stroke-width="2"/>')
    for i in range(n):
        svg.append(f'<circle cx="{x(i):.1f}" cy="{y_nl(nl[i]):.1f}" r="2.5" fill="#5cf">'
                    f'<title>window {i}: nl={nl[i]:.2f}</title></circle>')
        svg.append(f'<circle cx="{x(i):.1f}" cy="{y_nov(novelty[i]):.1f}" r="2.5" fill="#f95">'
                    f'<title>window {i}: novelty={novelty[i]:.3f}</title></circle>')
    svg.append(f'<text x="{PAD}" y="{H-8}" fill="#888" font-size="10">window 0</text>')
    svg.append(f'<text x="{W-PAD-60}" y="{H-8}" fill="#888" font-size="10">window {n-1}</text>')
    svg.append("</svg>")
    return "".join(svg)


def render_version(tag, src_dir, version_label):
    findings_raw = (src_dir / "FINDINGS.md").read_text().strip()
    meta = json.load(open(src_dir / "run_meta.json"))
    traj = meta["trajectory"]
    nl, novelty = traj["nl"], traj["novelty"]
    cal = meta["calibration"]

    # split off Kim's verdict section (v1 only) into its own highlighted box so it
    # doesn't read as just more findings prose -- it's a directive, not an observation.
    verdict_html = ""
    findings = findings_raw
    marker = "## KIM'S LISTENING VERDICT"
    if marker in findings_raw:
        findings, verdict = findings_raw.split(marker, 1)
        findings = findings.strip()
        verdict_html = f'<div class=verdict-box><span class=lbl>Kim\'s listening verdict</span>{html.escape(verdict.strip())}</div>'

    parts = [f'<div class=version id="v_{tag}">']
    parts.append(f'<h3>{html.escape(version_label)}</h3>')
    parts.append(f'<div class=findings-box><span class=lbl>Findings</span>{html.escape(findings)}</div>')
    if verdict_html:
        parts.append(verdict_html)

    track = html.escape(meta["track"].rsplit(".", 1)[0])
    parts.append(
        f'<div class=recipe><b>Recipe</b><br>track: {track} (Kim\'s own) · '
        f'prompt: <i>{html.escape(meta["prompt"])}</i> · seed {meta["seed"]} · '
        f'checkpoint: evr1x (a2a workhorse, r128 in-distribution Goa baseline) · '
        f'requested_nl {meta["requested_nl"]} · window {meta["window_sec"]}s / overlap {meta["overlap_sec"]}s · '
        f'nl_step {meta["nl_step"]} · nl_min {meta["nl_min"]}<br>'
        f'calibration (source self-measured): novelty_floor {cal["novelty_floor"]:.3f} · '
        f'novelty_median {cal["novelty_median"]:.3f} · r_max {cal["r_max"]:.3f} · '
        f'r_median {cal["r_median"]:.3f} ({cal["n_patches"]} patches)</div>'
    )

    parts.append('<div class=abrow>')
    sfx = "" if tag == "v1" else f"_{tag}"
    for label, sub, fname in [
        (f"{tag} breathing (controller ON)", f"requested_nl {meta['requested_nl']}", f"breathing{sfx}"),
        (f"{tag} baseline (fixed nl)", f"nl held at {meta['requested_nl']} throughout", f"baseline_fixed_nl{sfx}"),
    ]:
        cell_id = f"ab_{tag}_{fname}"
        parts.append(
            f'<div class=abcell id="{cell_id}" onclick="abPlay(\'{cell_id}\',\'{CLIPS}/{fname}.m4a?v=3\',\'{label}\')">'
            f'<b>{html.escape(label)}</b><span class=sub>{html.escape(sub)}</span></div>'
        )
    parts.append('</div>')

    parts.append('<div class=legend><span style="color:#5cf">■</span> nl &nbsp; '
                  '<span style="color:#f95">■</span> output novelty &nbsp; '
                  f'<span style="color:#666">- - -</span> novelty_floor ({cal["novelty_floor"]:.2f}) &nbsp; '
                  f'<span style="color:#999">- - -</span> novelty_median ({cal["novelty_median"]:.2f})</div>')
    parts.append(svg_trajectory(nl, novelty, cal))
    parts.append('</div>')
    return "".join(parts)


PROMPTARC_DIR = Path("/run/media/kim/Mantu/sa3_lora_runs/promptarc_single_kaikkialla_nl65")
PROMPTARC_NL45_DIR = Path("/run/media/kim/Mantu/sa3_lora_runs/promptarc_single_kaikkialla_nl45")
PROMPTARC_NL05_DIR = Path("/run/media/kim/Mantu/sa3_lora_runs/promptarc_single_kaikkialla_nl05")
PROMPTARC_NL06_DIR = Path("/run/media/kim/Mantu/sa3_lora_runs/promptarc_single_kaikkialla_nl06")


def render_promptarc():
    """CONTINUITY's #35 breakthrough (2026-07-10): high-nl static turned out to be a
    CONDITIONING problem, not a noise problem -- fixed nl 0.65, single adapter (evr1x),
    but an 8-section rich prompt-arc instead of one static prompt. Directly comparable
    to v3's existing baseline_fixed_nl_v3 clip (single-adapter, single generic prompt,
    nl 0.70 -- the 'overshoot' row in FINDINGS' own comparison table), so it's presented
    as an explicit A/B against that already-staged clip rather than duplicating it.

    UPDATE (same day, later): Kim's ear FALSISED the nl0.65 arc as incoherent despite its
    good HF-variance score (the metric measured dynamism, not usability). CONTINUITY
    re-rendered the same 8-section arc at nl 0.45 for coherence-via-lower-noise -- added
    as a third A/B cell rather than replacing nl0.65 (both stay comparable). Per Kim's
    keep-collecting directive, CONTINUITY then filled in the sweep with nl 0.5 and nl 0.6
    (same track/seed/prompts) so the full 0.45/0.5/0.6/0.65 ladder is A/B-able for the
    coherence sweet spot."""
    findings = (PROMPTARC_DIR / "FINDINGS.md").read_text().strip()
    meta = json.load(open(PROMPTARC_DIR / "run_meta.json"))
    meta45 = json.load(open(PROMPTARC_NL45_DIR / "run_meta.json"))

    parts = ['<div class=version id="v_promptarc">']
    parts.append('<h3>The conditioning lever — prompt-arc beats adapter tricks (2026-07-10)</h3>')
    parts.append(f'<div class=findings-box><span class=lbl>Findings</span>{html.escape(findings)}</div>')
    parts.append(
        '<div class=findings-box><span class=lbl>Update — Kim\'s ear</span>'
        'The nl0.65 arc below scored best on the HF-variance metric (least static) but Kim '
        'heard it as incoherent — the metric was measuring dynamism, not usability. '
        'CONTINUITY filled in the 0.45/0.5/0.6 ladder below (same arc, lower noise) as a '
        'coherence sweep; A/B all four to find the sweet spot.</div>'
    )

    track = html.escape(meta["track"].rsplit(".", 1)[0])
    prompts_preview = " → ".join(html.escape(p.split(",")[0]) for p in meta["prompts"])
    parts.append(
        f'<div class=recipe><b>Recipe</b><br>track: {track} (Kim\'s own) · seed {meta["seed"]} · '
        f'checkpoint: evr1x (single adapter, no blend) · 8-section prompt arc (first clause of '
        f'each): {prompts_preview}<br>fixed nl swept {meta45["nl"]} / 0.5 / 0.6 / {meta["nl"]} '
        f'(same seed/prompts/track throughout)</div>'
    )

    parts.append('<div class=abrow>')
    cells = [
        ("promptarc @ nl0.45 (toned down)", "lowest noise in the sweep — coherence-via-lower-noise re-render (Kim's ask)", "promptarc_nl45"),
        ("promptarc @ nl0.5", "sweep step", "promptarc_nl05"),
        ("promptarc @ nl0.6", "sweep step", "promptarc_nl06"),
        ("promptarc @ nl0.65 (8-section arc)", "least static measured (HF-var 0.364, 10x the generic-prompt baseline) — but Kim heard it as incoherent", "promptarc_nl65"),
        ("v3 baseline @ nl0.70 (generic prompt)", "the comparison point — single prompt, most static (HF-var 0.035)", "baseline_fixed_nl_v3"),
    ]
    for label, sub, fname in cells:
        cell_id = f"ab_promptarc_{fname}"
        parts.append(
            f'<div class=abcell id="{cell_id}" onclick="abPlay(\'{cell_id}\',\'{CLIPS}/{fname}.m4a?v=3\',\'{label}\')">'
            f'<b>{html.escape(label)}</b><span class=sub>{html.escape(sub)}</span></div>'
        )
    parts.append('</div>')
    parts.append('</div>')
    return "".join(parts)


def render_layered():
    """Per-LAYER staggered LoRA interleave (Kim's 'slowly interleave the crossfade so the
    different layers of the LoRAs are applied not at a uniform rate' idea, 2026-07-11).

    Instead of applying the adapter at one uniform strength, the a2a re-render ramps adapter
    strength 0->full ACROSS the track; the 'staggered' version ramps each DiT block at a
    DIFFERENT rate (shallow blocks = structure/rhythm adopt the style first, deep blocks =
    surface timbre lag) so the style emerges as a gradual morph, not a uniform switch. The
    third clip stacks the same interleave on top of the 8-section prompt arc at higher noise
    (nl0.75) to hear whether the slow layer-crossfade smooths the morph even when the prompts
    themselves differ across sections (Kim's follow-up ask)."""
    parts = ['<div class=version id="v_layered">']
    parts.append('<h3>The per-layer interleave — staggered vs uniform adapter onset (2026-07-11)</h3>')
    parts.append(
        '<div class=findings-box><span class=lbl>What this tests / how to read it</span>'
        'The LoRA adapter is normally applied at one <b>uniform</b> strength. Here the a2a '
        're-render instead ramps adapter strength from 0 to full <b>across the whole track</b>, '
        'turning the style on gradually. The <b>staggered</b> version ramps <i>each DiT block at '
        'a different rate</i> — shallow blocks (structure / rhythm) adopt the style first, deep '
        'blocks (surface timbre) lag — so the style should <i>morph in</i> rather than switch on. '
        'A/B <b>staggered vs uniform</b> (both single-prompt, nl0.55): the question is whether the '
        'layer-staggered onset <i>feels</i> smoother/more gradual than an even fade-in. The third '
        'clip puts the staggered interleave <b>on top of the 8-section prompt arc at nl0.75</b> — '
        'Kim suspected the per-layer trick "won\'t help for the differences in prompts"; this lets '
        'you hear that case directly (does the slow layer-crossfade smooth the morph even as the '
        'section prompts change under it?).</div>'
    )
    parts.append(
        '<div class=recipe><b>Recipe</b><br>track: Aavepyora - Goddess Guerilla - Kaikki-Alla '
        '(Kim\'s own) · seed 1234 · checkpoint: evr1x (single adapter) · adapter strength ramped '
        '0→1 across the track over 24 DiT depths · <b>staggered</b> = spread 1.0 (shallow leads, '
        'deep lags), <b>uniform</b> = spread 0.0 (all layers together) · A/B pair at nl0.55; the '
        'arc clip at nl0.75 adds the 8-section prompt arc on top of the staggered onset</div>'
    )
    parts.append('<div class=abrow>')
    cells = [
        ("staggered onset (shallow→deep)", "single prompt · nl0.55 · per-layer ramp, shallow DiT blocks lead", "layered_staggered"),
        ("uniform onset (baseline)", "single prompt · nl0.55 · all layers ramp together", "layered_uniform"),
        ("staggered + 8-section prompt arc", "nl0.75 · the interleave stacked on the prompt arc — does it smooth the morph across differing prompts?", "layered_arc_nl75"),
    ]
    for label, sub, fname in cells:
        cell_id = f"ab_layered_{fname}"
        parts.append(
            f'<div class=abcell id="{cell_id}" onclick="abPlay(\'{cell_id}\',\'{CLIPS}/{fname}.m4a?v=3\',\'{label}\')">'
            f'<b>{html.escape(label)}</b><span class=sub>{html.escape(sub)}</span></div>'
        )
    parts.append('</div>')
    parts.append('</div>')
    return "".join(parts)


def render_blockbuild_v2():
    """Kim's v2 design (2026-07-12): shared-prefix block-building prompt arc + measure-aligned
    windows/crossfades. UNAUDITED (red-! per MANIFEST v2 / eval-tables spec §16) until Kim
    comments — clearing the mark = writing his verdict into the run_meta kim_feedback field."""
    parts = ['<div class=version id="v_blockbuild2">']
    parts.append('<h3><span style="color:#e33;font-weight:900">&#10071;</span> '
                 'Block-build v2 — measure-aligned windows + shared-prefix prompt arc (2026-07-12, unaudited)</h3>')
    parts.append(
        '<div class=findings-box><span class=lbl>What this tests / how to read it</span>'
        'Kim heard two faults in the v1 interleave: <b>galloping beats</b> (each window is an '
        'independent a2a re-render that can settle on its own rhythm phase — the model '
        're-synthesizes the beat grid rather than reading it from the noised input — and '
        'wall-clock crossfades overlap two misaligned kick grids) and <b>abrupt section changes</b> '
        '(a coarse strength staircase plus prompts with no shared spine). v2 fixes both: windows '
        'and crossfades sit on <b>measure boundaries</b> from the track\'s beat grid (12-bar '
        'windows, 4-bar equal-power crossfades on downbeats), and every prompt opens with the '
        '<b>identical mood/genre/production prefix</b> while the section suffixes build the '
        'arrangement out of <b>shared elements</b> — the bassline persists through all eight '
        'sections, the kick appears over already-established strings, the outro removes elements '
        'one by one. Listen for: no gallop at seams, and section changes that read as arrangement, '
        'not channel-switching. A/B the two noise levels — nl0.6 stays closer to the source, '
        'nl0.75 gives the prompts more authority.</div>'
    )
    parts.append(
        '<div class=recipe><b>Recipe</b><br>track: Aavepyora - Goddess Guerilla - Kaikki-Alla '
        '(Kim\'s own) · seed 1234 everywhere · checkpoint: evr1x ep7 (mixed goa+avp corpus, 8ep) · '
        'per-layer staggered strength 0→1 (spread 1.0) · 12-measure windows, 8-measure hop, '
        'equal-power 4-measure crossfades on downbeats · 8-section block-building prompt arc, '
        'constant prefix "early 90s hypnotic goa trance, dynamic but crisp production, analog '
        'synthesizers, professional sound" · steps 24 · cfg 6</div>'
    )
    parts.append('<div class=abrow>')
    cells = [
        ("block-build v2 @ nl0.6", "measure-aligned · shared-prefix arc · closer to source", "blockbuild_nl06"),
        ("block-build v2 @ nl0.75", "measure-aligned · shared-prefix arc · more prompt authority", "blockbuild_nl075"),
    ]
    for label, sub, fname in cells:
        cell_id = f"ab_bb2_{fname}"
        parts.append(
            f'<div class=abcell id="{cell_id}" onclick="abPlay(\'{cell_id}\',\'{CLIPS}/{fname}.m4a?v=3\',\'{label}\')">'
            f'<b>{html.escape(label)}</b><span class=sub>{html.escape(sub)}</span></div>'
        )
    parts.append('</div>')
    parts.append('</div>')
    return "".join(parts)


def main():
    doc = [f"<!doctype html><html><head><meta charset=utf-8><title>a2a transitions — the collection</title><style>{CSS}</style></head><body>{WAVEFORM_JS}"]
    doc.append('<div id=hdr>&#9654; <b id=np>click a clip to play</b> <span id=pos></span> '
                '&nbsp;·&nbsp; <span style="color:#888">switching keeps the playhead; re-click stops</span></div>')
    doc.append('<h1>a2a transitions — the collection (breathing v1–v3, prompt-arc, and every variant to come)</h1>'
                '<a href=index.html>← compare</a> · <a href=mp.html>multiprompt board</a>')
    doc.append(
        '<div class=findings-box><span class=lbl>What this tests / how to read it</span>'
        '<b>Audio-to-audio (a2a)</b> re-renders an existing track through the model at some '
        '<code>init_noise_level</code> (nl): low nl keeps most of the original signal, high nl '
        'lets the model regenerate more of it (more "creative", but past a point it starts '
        'looping/repeating instead of following the source — the "loop-attractor" problem). '
        'The FIX under test here is a <b>controller</b> that watches the output as it generates '
        'and adjusts nl window-by-window instead of holding it fixed: it measures how different '
        'each new window sounds from what came before ("novelty") and ducks nl down when novelty '
        'collapses (a loop forming), letting it climb back up once the output diversifies again — '
        '"breathing". <b>v1</b> found the fix works but picked too narrow an nl range (sounded '
        'muddy). <b>v2</b> widened it and added ducking at the track\'s own natural pauses. '
        '<b>v3</b> pushed further and found the actual ceiling: past a point, MORE noise just '
        'means more static for this checkpoint, not more creativity — which is why the fourth '
        'section below (the conditioning lever) matters: it turned out the real fix isn\'t a '
        'better noise schedule at all. The line charts plot nl (blue) and measured novelty '
        '(orange) per time-window — nl dipping and novelty recovering right after is the '
        'controller working as designed.</div>'
    )
    doc.append('<div class=tip>All three versions on kaikkialla x evr1x, same seed. v1 oscillated a narrow '
                '0.45–0.55 mid-band and Kim heard it as noisy/stringy/pale, losing melody+bass. v2 uses '
                'the full 0.30–0.62 range, ducking hard at 4 detected source breaks so the original comes '
                'through clean. v3 pushes deeper (flush to 0.05 on breaks/HF-static) and finds the real '
                'limit: an HF-static meter confirms higher nl IS more static for this checkpoint, so '
                'nl-scheduling alone can stay source-crisp but can\'t reach creative-AND-crisp — that '
                'needs dual-LoRA oscillation or chroma constraint (T2), not just a better schedule. Switch '
                'between any clip below (including across versions) without losing your place.</div>')

    for tag, src_dir, label in VERSIONS:
        doc.append(render_version(tag, src_dir, label))

    doc.append(render_promptarc())
    doc.append(render_blockbuild_v2())
    doc.append(render_layered())

    js = (
        "let abCur=null,abAu=new Audio();"
        "function abPlay(id,f,lbl){"
        "document.querySelectorAll('.abcell').forEach(e=>e.classList.remove('play'));"
        "if(abCur===id){abAu.pause();abCur=null;document.getElementById('np').textContent='stopped';return;}"
        "const pos=(abCur!==null&&!abAu.paused)?abAu.currentTime:0;"
        "abCur=id;document.getElementById(id).classList.add('play');"
        "document.getElementById('np').textContent='▶ '+lbl;"
        "abAu.src=f;const go=()=>{try{abAu.currentTime=((abAu.duration&&pos>abAu.duration-1)?0:Math.min(pos,(abAu.duration||1e9)-0.05));}catch(e){}abAu.play();};"
        "if(abAu.readyState>=1)go();else abAu.addEventListener('loadedmetadata',go,{once:true});"
        "}"
        "setInterval(()=>{if(abCur&&!abAu.paused)document.getElementById('pos').textContent="
        "Math.floor(abAu.currentTime/60)+':'+String(Math.floor(abAu.currentTime%60)).padStart(2,'0');},500);"
    )
    doc.append(f"<script>{js}</script>")
    doc.append("<footer style='margin-top:20px;color:#666;font-size:11px'>aavepyora.online · evals · same-playhead A/B</footer>")
    doc.append("</body></html>")

    html_str = "".join(doc)

    # Guard against the silent-404 bug (2026-07-11): a cell can be emitted with no
    # clip on disk (clips are transcoded/deployed by a separate step; if that step
    # lags the cell being added, the cell 404s and Kim only finds out by ear). Assert
    # every emitted clip exists in the output clips dir; fail the build loudly if not.
    clip_dir = OUT.parent / CLIPS
    refs = sorted(set(re.findall(rf'{re.escape(CLIPS)}/([^"\'?]+\.m4a)', html_str)))
    missing = [c for c in refs if not (clip_dir / c).exists()]
    if missing:
        raise SystemExit(
            f"[build_breathing_page] {len(missing)}/{len(refs)} emitted clip(s) MISSING from "
            f"{clip_dir}: {missing}\nA cell was emitted with no clip on disk (the silent-404 bug). "
            "Transcode the source wav(s) into the clips dir before shipping this page.")

    OUT.write_text(html_str)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes); verified {len(refs)} clips present in {clip_dir}")


if __name__ == "__main__":
    main()
