#!/usr/bin/env python3
"""build_latch_evals_page.py — the LatCH eval stream at /files/evals/latch/.

Project guidance 2026-09-16: evals move under THEMATIC folders, and LatCH tests
accumulate on ONE page instead of spawning a new page per experiment. So this is a
stream: each experiment is one ENTRY dict in ENTRIES below, newest first. Adding the
next test means appending a dict and re-running — no new page, no new link to
register, no clutter.

Style: the section's own evals.css (--paper #fafaf7, --ink #2b3538, --edge #0f9e99,
IBM Plex Mono, .wrap 900px), NOT the dark standalone style the older riffer pages
use, because this page lives inside /files/evals/ and should look like it.

Player: build_evals.PLAYER_JS, loaded BY PATH. There are already two same-playhead
players in this tree; a third would be two too many. build_evals.py:21 poisons
sys.path, so it is loaded via importlib from its file location the way
build_sweep_page.py does, not imported as a module.

Redaction (profiles SPEC §4): checkpoint FILENAMES, absolute paths and infra
addresses never reach a public page. Config/hyperparameters/metrics are SHARED on
purpose — "that's how the light gets out". Every free-text field below goes through
build_evals.redact() at render time, so a pasted path cannot leak by forgetting.

Run:  python3 Misc/build_latch_evals_page.py [--out ~/staging/evals-latch]
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
from pathlib import Path

BUILD_EVALS = Path("/home/kim/Projects/SAO/Misc/build_evals.py")


def _load_build_evals():
    """Load build_evals by PATH (its line 21 poisons sys.path if imported normally)."""
    spec = importlib.util.spec_from_file_location("_be", BUILD_EVALS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# THE STREAM. Newest first. Append a dict to add the next experiment.
#
# Required: date, title, question, why, method, clips, findings.
# `kim_feedback: None` renders the ❗ UNAUDITED mark (MANIFEST v2 §5) until a
# listening verdict is recorded here verbatim.
# ---------------------------------------------------------------------------
ENTRIES = [
    {
        "date": "2026-09-16",
        "slug": "guided-sampler",
        "title": "Guidance was silently swapping the model's sampler",
        "question": "Why does the high-frequency (rms_energy_air) LatCH head have no "
                    "audible effect on the post-trained model, at any gain?",
        "why": (
            "The post-trained checkpoint is the one most people actually use — it is "
            "faster and sounds better out of the box. If our steering controls do not "
            "work on it, they are worth much less in practice than the numbers on the "
            "base model suggest. Two listening brackets spanning a 1000x gain range had "
            "already found the head inert there, and the runtime warning pointed at a "
            "schedule mismatch, which suggested retraining the head."),
        "method": (
            "Six renders sharing one seed, prompt, head, target and checkpoint, so every "
            "difference is attributable to one named variable. The load-bearing arm sets "
            "the guidance strength to exactly zero while still routing through the "
            "guidance code path: guidance is then mathematically inert, so whatever that "
            "arm moves is the sampler's doing and cannot be the head's. Distances are "
            "measured on the generated latents rather than by ear, because the thing "
            "being tested is precisely whether ears can tell these apart."),
        "table": {
            "caption": "Relative distance between arms (0 = identical output)",
            "head": ["comparison", "distance", "reading"],
            "rows": [
                ["sampler swap alone — guidance INERT", "1.999727",
                 "the sampler alone, before any head"],
                ["euler: 1000x gain increase", "0.026365", "swamped, inaudible"],
                ["pingpong: 1000x gain increase", "0.246328", "9.4x more responsive"],
                ["fix effect at matched gain", "1.063998", "same gain, correct sampler"],
            ],
        },
        "clips": [
            ("arm0_baseline_pingpong", "baseline — no guidance, native sampler"),
            ("arm1_euler_gain0", "guidance INERT (strength 0) on the wrong sampler"),
            ("arm2_euler_gain2", "wrong sampler, low gain"),
            ("arm3_euler_gain2048", "wrong sampler, 1000x the gain"),
            ("arm4_pingpong_gain2", "FIXED — correct sampler, low gain"),
            ("arm5_pingpong_gain2048", "FIXED — correct sampler, 1000x the gain"),
        ],
        "clip_hint": "Compare arm4/arm5 against arm0. Arms 1-3 are the old behaviour.",
        "findings": [
            ("The sampler, not the head.",
             "A model is sampled by the method it was trained for. The post-trained model "
             "wants a ping-pong sampler; the guidance path used a different one for every "
             "guided render. So asking for guidance at all quietly changed how the audio "
             "was made, before the control was even consulted."),
            ("The internal signal level confirms it.",
             "A healthy render sits near 1.15 on an internal scale; every render on the "
             "wrong sampler sat at 2.15-2.17 and grew as it went, while every render on "
             "the correct one stayed at 1.17-1.18. The inert arm reproduces the 2.0 "
             "distance on its own, which is what makes this attributable."),
            ("\"Gain does nothing\" was swamping, not saturation.",
             "The control's own push was always tiny next to the signal it was pushing "
             "— even at 1000x, under a ten-thousandth of it. A real but small effect "
             "sitting underneath a large artefact is inaudible, which is exactly what "
             "two listening rounds reported."),
            ("The requested fix would have hidden the problem.",
             "Retraining the head for the other schedule produces a numerically identical "
             "head — both settings share one code path — and changes only the label the "
             "warning compares. It would have deleted the warning while fixing nothing."),
        ],
        "limits": [
            "Restored steering is not proof of usefulness: the recovered response is real "
            "but modest, and no one has yet shown the head can audibly tame harsh highs.",
            "The target used here was the head's own corpus average, which is a request to "
            "be AVERAGE, not to reduce anything — so no run so far has actually asked for "
            "less high end.",
            "The weaker of the two guidance mechanisms stayed weak on both samplers; the "
            "recovered responsiveness comes from the other one.",
            "Whether an 8-step model gives guidance enough room to act is only partly "
            "answered: it acts, but how far it can push is unmeasured.",
        ],
        "config": [("steps", "8"), ("cfg", "1.0"), ("duration", "48 s"),
                   ("arms", "6"), ("seed", "fixed across all arms"),
                   ("head", "rms_energy_air (high-frequency energy)"),
                   ("model", "post-trained medium + a DoRA adapter (internal)")],
        "kim_feedback": None,
    },
]

CSS_EXTRA = """
.entry{border-top:1px solid var(--rule);margin:30px 0 0;padding-top:18px}
.q{font-size:15px;color:var(--ink);line-height:1.5;margin:10px 0 4px;font-weight:600}
.why{color:var(--body);line-height:1.6;margin:8px 0 14px}
.meth{color:var(--body);line-height:1.6;margin:8px 0 14px;padding-left:12px;
 border-left:2px solid var(--rule-light)}
table.m{border-collapse:collapse;font-size:12px;margin:10px 0 6px;width:100%}
table.m td,table.m th{border:1px solid var(--rule-light);padding:5px 9px;text-align:left}
table.m th{background:var(--paper-dim);color:var(--ink);font-weight:600}
table.m td.n{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.cap{color:var(--dim);font-size:11px;margin:2px 0 10px}
.cells{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 6px}
.cell{cursor:pointer;border:1px solid var(--rule);background:var(--paper-dim);
 padding:7px 11px;font:12px 'IBM Plex Mono',monospace;color:var(--ink);border-radius:3px}
.cell:hover{border-color:var(--edge)}
.cell.playing{border-color:var(--edge);background:#e6f5f4;box-shadow:inset 0 0 0 1px var(--edge)}
.cell .sub{display:block;color:var(--dim);font-size:10px;margin-top:2px}
.find{margin:6px 0 0;padding:0;list-style:none}
.find li{margin:0 0 10px;line-height:1.6;color:var(--body)}
.find b{color:var(--ink)}
.lim{background:var(--paper-dim);border-left:3px solid var(--faint);padding:10px 14px;margin:14px 0}
.lim li{margin:0 0 6px;line-height:1.55;color:var(--body)}
.cfg{color:var(--dim);font-size:11px;margin:10px 0 0;line-height:1.7}
.cfg b{color:var(--body);font-weight:500}
.unaud{color:#b23;font-weight:600}
.verdict{background:#eef7ee;border-left:3px solid #4a4;padding:10px 14px;margin:12px 0;
 line-height:1.6;color:var(--body)}
"""


def build(out_dir: Path) -> Path:
    be = _load_build_evals()
    R = be.redact
    e = html.escape

    doc = be.head("LatCH steering — eval stream", depth=1)
    doc += f"<style>{CSS_EXTRA}</style>"
    doc += "<h1>LatCH steering — eval stream</h1>"

    # Spec §14: one line on what this FAMILY is for, then a plain-language explainer
    # written so someone with moderate experience learns from it.
    doc += ('<p class="dim">What this family of evals is for: measuring whether a '
            'trained control head actually steers the model, and by how much.</p>')
    doc += ('<p class="why">A LatCH head is a small trained probe that reads what the '
            'model is about to produce and nudges it toward a requested value — more '
            'high end, denser onsets, a particular chord. "Does it work?" is harder to '
            'answer than it sounds: a control can move a meter while making the audio '
            'worse, and it can be genuinely working while something else drowns it out. '
            'These tests therefore pair measurements taken on the model\'s own internal '
            'output with clips you can listen to, and each entry states what it does '
            '<em>not</em> establish alongside what it does. Newest first; this page '
            'accumulates rather than spawning a page per test.</p>')

    for en in ENTRIES:
        doc += '<div class="entry">'
        mark = ('<span class="unaud" title="no listening verdict recorded yet">&#10071; '
                'UNAUDITED</span> ') if not en.get("kim_feedback") else ""
        doc += f'<h2><span class="mark">§</span> {e(en["date"])} — {e(R(en["title"]))}</h2>'
        doc += f'<p class="q">{mark}{e(R(en["question"]))}</p>'
        doc += f'<p class="why">{e(R(en["why"]))}</p>'
        doc += f'<p class="meth"><b>How it was tested.</b> {e(R(en["method"]))}</p>'

        t = en.get("table")
        if t:
            doc += '<table class="m"><tr>' + "".join(
                f"<th>{e(c)}</th>" for c in t["head"]) + "</tr>"
            for row in t["rows"]:
                doc += ("<tr><td>" + e(R(row[0])) + '</td><td class="n">' + e(row[1])
                        + "</td><td>" + e(R(row[2])) + "</td></tr>")
            doc += "</table>"
            doc += f'<p class="cap">{e(t["caption"])}</p>'

        if en.get("clips"):
            doc += '<div class="cells">'
            for name, label in en["clips"]:
                src = f'clips/{name}.m4a'
                doc += (f'<div class="cell" data-src="{e(src)}" onclick="play(this)">'
                        f'{e(name)}<span class="sub">{e(R(label))}</span></div>')
            doc += "</div>"
            if en.get("clip_hint"):
                doc += f'<p class="cap">{e(R(en["clip_hint"]))}</p>'

        doc += '<ul class="find">'
        for hd, body in en["findings"]:
            doc += f"<li><b>{e(R(hd))}</b> {e(R(body))}</li>"
        doc += "</ul>"

        if en.get("limits"):
            doc += '<div class="lim"><b>What this does not establish</b><ul>'
            for l in en["limits"]:
                doc += f"<li>{e(R(l))}</li>"
            doc += "</ul></div>"

        if en.get("kim_feedback"):
            doc += f'<div class="verdict"><b>Listening verdict.</b> {e(R(en["kim_feedback"]))}</div>'

        if en.get("config"):
            doc += ('<p class="cfg">' + " · ".join(
                f"<b>{e(k)}</b> {e(R(v))}" for k, v in en["config"]) + "</p>")
        doc += "</div>"

    doc += be.PLAYER_JS
    doc += "</div></body></html>"

    out_dir.mkdir(parents=True, exist_ok=True)
    page = out_dir / "index.html"
    page.write_text(doc, encoding="utf-8")
    (out_dir / "entries.json").write_text(
        json.dumps([{k: v for k, v in en.items()} for en in ENTRIES], indent=2),
        encoding="utf-8")
    return page


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path.home() / "staging/evals-latch")
    a = ap.parse_args()
    page = build(a.out)
    print(f"[built] {page}  ({page.stat().st_size} bytes, {len(ENTRIES)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
