"""manifest.jsonl -> a sweep results page, per the eval-tables spec.

Spec: docs/superpowers/specs/2026-07-06-eval-tables-human-first.md. Three things
follow from it and shape this file:

* **THREE AUDIENCES (spec section 14).** Every page is simultaneously an eval TOOL
  (same-playhead listening), a technical RESOURCE (the exact payload, the axis
  definitions, the command that reproduces it), and a LEARNING resource (plain
  language: what this sweep tests, why, how to read the result). The third is the
  one that keeps going missing, so `PER_AXIS_HELP` is a literal table and an axis
  with no sentence written SAYS SO on the page rather than rendering nothing.

* **Reuse the player, do not write a third one.** `Misc/build_evals.py` already
  exports `CSS` (the design tokens every eval page's colours come from),
  `WAVEFORM_CSS` and `WAVEFORM_JS` -- the shared waveform-popup, same-playhead
  player that ARCHITECTURE tells you to import for any player page. The clarity
  page's inline players are entangled with its own variants/clips data model, so
  the right reuse is build_evals, not an extraction from there.

* **The table brings its own scroller.** build_evals.CSS sets `overflow-x:hidden`
  on html+body on purpose (a wider-than-viewport element makes mobile expand the
  layout viewport, which throws the popup's `position:fixed;left:50%` centring off
  screen). A wide table must therefore wrap itself in `overflow-x:auto` or it is
  silently clipped.
"""
from __future__ import annotations

import argparse
import html as _html
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _load_build_evals():
    """Load Misc/build_evals.py BY PATH, never by putting Misc/ on sys.path.

    Misc/ contains a first-party `filelock.py`; prepending that directory makes it
    shadow the pip `filelock` package that huggingface_hub imports, and the failure
    surfaces three modules away as `cannot import name 'BaseFileLock'`. Caught by
    the existing test_server_heads suite the moment this module was imported
    alongside it (C, 2026-08-26).
    """
    import importlib.util
    src = Path("/home/kim/Projects/SAO/Misc/build_evals.py")
    spec = importlib.util.spec_from_file_location("_sao_build_evals", src)
    mod = importlib.util.module_from_spec(spec)
    saved = list(sys.path)          # build_evals.py:21 prepends Misc/ to sys.path
    try:                            # itself, which outlives the import -- undo it
        spec.loader.exec_module(mod)
    finally:
        sys.path[:] = saved
    return mod


try:
    _be = _load_build_evals()
    BASE_CSS, WAVEFORM_CSS, WAVEFORM_JS = _be.CSS, _be.WAVEFORM_CSS, _be.WAVEFORM_JS
except Exception:                       # keep the builder usable in a bare checkout
    BASE_CSS = WAVEFORM_CSS = ""
    WAVEFORM_JS = "<!-- build_evals not importable: no waveform player -->"

SCHEMA_VERSION = 1

# Plain-language, per axis. Each says what the axis IS, what the neutral value is,
# and what to listen for. Trap 6 from docs/INFERENCE-SURFACE.md is load-bearing in
# the strength and cfg entries: the extreme cells are DIAGNOSTIC, not mistakes.
PER_AXIS_HELP = {
    "strength": ("Adapter strength. 1.0 is as trained. Below 1 the adapter is diluted "
                 "toward the base model; above ~1.5 models start to break — which is the "
                 "point. The useful discriminator between checkpoints is not which sounds "
                 "best at the safe setting, but which stay musical when pushed."),
    "cfg": ("Classifier-free guidance scale. ~7 is the normal working value. 16 is a "
            "DIAGNOSTIC cell, not a mistake: high cfg exaggerates whatever the model "
            "does wrong, so it separates checkpoints that a comfortable setting hides."),
    "steps": ("Sampling steps. More steps = more denoising iterations. Returns flatten "
              "quickly; if a difference only appears at high step counts it is usually "
              "not the difference you were looking for."),
    "seed": ("The noise the render starts from. Nothing about quality — it is here so "
             "you can tell a real difference between settings from one lucky draw. "
             "Judge an axis only where it holds across seeds."),
    "model": ("Which checkpoint rendered the cell. Same prompt, same seed, same "
              "everything else — so a column-to-column difference is the model."),
    "prompt": ("The text conditioning. Compare down a column to see how much of the "
               "result is the prompt and how much is the checkpoint."),
    "duration": ("Render length in seconds. Longer renders expose structure problems "
                 "(drift, repetition) that a short clip cannot show."),
    "gamma": ("LatCH inner-loop damping, default 0.3. Lower applies the correction more "
              "gently over more iterations (safer, slower to bite); higher converges "
              "faster and can overshoot on heads with a large dataset sigma."),
    "n_iter": ("LatCH guidance iterations per sampling step, default 4. Cost is roughly "
               "linear. Raise it when a target is being ignored and you have already "
               "tried raising the slot gain."),
    "rho": ("LatCH guidance step size. Normally 'auto', which the server sets to slot 1's "
            "gain. Gains are RELATIVE (per-slot weight = slot_gain / slot-1 gain), so a "
            "raw weight from another tool is a different scale."),
    "mu": ("LatCH proximal term, auto-tied to rho. Raising it above rho pulls harder "
           "toward the current latent, i.e. guidance bites less."),
    "latch1_value": ("The target value for LatCH slot 1, in the head's OWN units. The "
                     "useful range is the head's dataset mean ± 2 sigma — the inference "
                     "UI's range meter shows it. Outside that the head still pushes, but "
                     "toward audio it never saw."),
    "latch1_gain": ("How hard LatCH slot 1 pushes. Slot 1's gain also sets rho/mu for the "
                    "whole stack, so changing it moves two things at once."),
    "film_value": ("Onsets per second requested from the FiLM density adapter. Listen for "
                   "whether density changes without the timbre following it."),
}
_NO_HELP = ("(no explainer written for this axis yet — add one to PER_AXIS_HELP in "
            "eval/build_sweep_page.py)")

PAGE_CSS = """
.wrap{max-width:none;width:100%;padding:18px 22px}
.sw-scroll{overflow-x:auto;max-width:100%;margin:10px 0 18px}
.sw-table{border-collapse:collapse;width:max-content;min-width:100%;font-size:12px}
.sw-table th,.sw-table td{border:1px solid var(--rule);padding:6px 8px;vertical-align:top}
.sw-table th{background:var(--paper-dim);text-align:left;white-space:nowrap}
.sw-cell{min-width:210px}
.sw-cell audio{width:200px;display:block;margin:2px 0}
/* nowrap ONLY inside a table cell, which has its own overflow-x:auto scroller.
   Precaution, not an observed failure: build_evals.CSS sets overflow-x:hidden on
   html+body on purpose (so the waveform popup's position:fixed centring is not
   thrown off by an expanded layout viewport on mobile), which means any nowrap
   element wider than the viewport would be CLIPPED rather than scrolled. The
   header carries a full manifest path, so it is the obvious candidate. Verified
   at a 1862px viewport that nothing currently overflows; the narrow case was not
   reproducible with the tooling to hand, so this is belt-and-braces. */
.sw-meta{font-size:10.5px;color:var(--faint);overflow-wrap:anywhere}
.sw-cell .sw-meta{white-space:nowrap}
.sw-err{color:#b00;font-size:11px}
.sw-warn{color:#c60;font-size:10.5px}
.sw-box{border:1px solid var(--rule);border-left:3px solid var(--edge);background:#fff;
padding:10px 14px;margin:10px 0}
.sw-box h3{margin:0 0 6px;font-size:12px;letter-spacing:.12em;text-transform:uppercase;
color:var(--edge-ink)}
.sw-box li{margin:3px 0;font-size:12.5px;line-height:1.45}
.sw-pre{background:var(--paper-dim);border:1px solid var(--rule);padding:8px 10px;
font-family:var(--mono);font-size:11px;overflow-x:auto;max-width:100%;
white-space:pre-wrap;overflow-wrap:anywhere}
.sw-unheard{color:#b00;font-weight:bold;cursor:pointer;margin-left:4px}
"""

# Spec section 16: an unaudited cell carries the red marker until it is clicked; the
# state is per-viewer and lives in the page's own localStorage, like the other pages.
HEARD_JS = """<script>
(function(){
  var KEY='sweep-heard:'+location.pathname;
  var heard={};
  try{heard=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){heard={}}
  function paint(){
    document.querySelectorAll('[data-cell]').forEach(function(el){
      var m=el.querySelector('.sw-unheard'); if(!m) return;
      m.style.display = heard[el.dataset.cell] ? 'none' : 'inline';
    });
  }
  document.addEventListener('click',function(e){
    var el=e.target.closest && e.target.closest('[data-cell]');
    if(!el) return;
    heard[el.dataset.cell]=1;
    try{localStorage.setItem(KEY,JSON.stringify(heard))}catch(e){}
    paint();
  });
  document.addEventListener('play',function(e){
    var el=e.target.closest && e.target.closest('[data-cell]');
    if(!el) return;
    heard[el.dataset.cell]=1;
    try{localStorage.setItem(KEY,JSON.stringify(heard))}catch(e){}
    paint();
  },true);
  paint();
})();
</script>"""


def read_manifest(path) -> list[dict]:
    """One record per line; a torn or hand-edited line is skipped, not fatal."""
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _axis_names(records) -> list[str]:
    names = []
    for r in records:
        for k in (r.get("coords") or {}):
            if k not in names:
                names.append(k)
    # seed is a coordinate but not a table axis unless it is the only one -- it
    # multiplies everything, so it belongs inside the cell.
    axes = [n for n in names if n != "seed"]
    return axes or (["seed"] if "seed" in names else [])


def _uniq(values):
    seen, out = set(), []
    for v in values:
        k = json.dumps(v, default=str)
        if k not in seen:
            seen.add(k)
            out.append(v)
    try:
        return sorted(out)
    except TypeError:
        return out


def pivot(records) -> dict:
    """{"rows","cols","cells","axes","row_axes","col_axis"}.

    One axis -> a single row. Two -> rows x cols. Three or more -> rows are the
    cross-product of all but the column axis. `model`, when present, is ALWAYS the
    column axis: comparing models side by side is the point of a model sweep.
    """
    axes = _axis_names(records)
    if not axes:
        return {"rows": [], "cols": [], "cells": {}, "axes": [],
                "row_axes": [], "col_axis": None}
    col_axis = "model" if "model" in axes else axes[-1]
    row_axes = [a for a in axes if a != col_axis]
    cols = _uniq([r["coords"].get(col_axis) for r in records])
    if row_axes:
        rows = _uniq([tuple(r["coords"].get(a) for a in row_axes) for r in records])
    else:
        rows = [()]
    cells: dict = {}
    for r in records:
        c = r.get("coords") or {}
        key = (tuple(c.get(a) for a in row_axes), c.get(col_axis))
        cells.setdefault(key, []).append(r)
    if row_axes and len(row_axes) == 1:
        rows = [t[0] for t in rows]
        cells = {((k[0][0],) if isinstance(k[0], tuple) else k[0], k[1]): v
                 for k, v in cells.items()}
        cells = {(k[0][0] if isinstance(k[0], tuple) else k[0], k[1]): v
                 for k, v in cells.items()}
    return {"rows": rows, "cols": cols, "cells": cells, "axes": axes,
            "row_axes": row_axes, "col_axis": col_axis}


def explainer_html(spec_meta) -> str:
    axes = spec_meta.get("axes") or []
    items = "".join(
        f"<li><b>{_html.escape(str(a))}</b> — {_html.escape(PER_AXIS_HELP.get(a, _NO_HELP))}</li>"
        for a in axes)
    return (
        '<div class="sw-box"><h3>What this sweep tests, and how to read it</h3>'
        "<p>Every cell below is the <b>same render recipe</b> with one thing changed. "
        "Everything not listed as an axis is held fixed, so a difference you hear "
        "between two cells is caused by the axis that separates them — nothing else. "
        "Play cells across a row to hear one axis move; play down a column to hear "
        "another. The player keeps the same playhead position when you switch clips, "
        "so you are comparing the same moment of the music.</p>"
        f"<ul>{items}</ul>"
        "<p class=\"sw-meta\">A red <b>!</b> marks a cell nobody has listened to yet. "
        "It clears when you play it, and the state is remembered in this browser.</p>"
        "</div>")


def _cell_html(recs) -> str:
    if not recs:
        return '<td class="sw-cell"><span class="sw-meta">—</span></td>'
    bits = []
    for r in recs:
        cid = _html.escape(str(r.get("cell_id", "")))
        if r.get("status") != "ok":
            bits.append(f'<div class="sw-err">ERROR: '
                        f'{_html.escape(str(r.get("error") or "unknown"))}</div>'
                        f'<div class="sw-meta">{cid}</div>')
            continue
        files = r.get("files") or []
        src = _html.escape(files[0]) if files else ""
        audio = (f'<audio preload="none" controls src="file://{src}"></audio>'
                 if src else '<div class="sw-err">no file</div>')
        warn = ('<div class="sw-warn">no z0 saved — this render cannot be '
                'continued or re-decoded</div>') if r.get("z0_missing") else ""
        bits.append(
            f'<div data-cell="{cid}">{audio}{warn}'
            f'<span class="sw-meta">seed {r.get("seed")} · {cid}</span>'
            f'<span class="sw-unheard" title="not yet listened to">!</span></div>')
    return '<td class="sw-cell">' + "".join(bits) + "</td>"


def _table_html(piv) -> str:
    if not piv["cols"]:
        return "<p>no cells in this manifest yet.</p>"
    col_axis = piv["col_axis"]
    head = "".join(f"<th>{_html.escape(f'{col_axis}={c}')}</th>" for c in piv["cols"])
    row_label = ", ".join(piv["row_axes"]) or "all"
    body = []
    for r in piv["rows"]:
        vals = r if isinstance(r, tuple) else (r,)
        label = ", ".join(f"{a}={v}" for a, v in zip(piv["row_axes"], vals)) or "—"
        tds = "".join(_cell_html(piv["cells"].get((r, c), [])) for c in piv["cols"])
        body.append(f"<tr><th>{_html.escape(label)}</th>{tds}</tr>")
    return ('<div class="sw-scroll"><table class="sw-table">'
            f"<tr><th>{_html.escape(row_label)}</th>{head}</tr>"
            + "".join(body) + "</table></div>")


def build(manifest_path, out_html, *, title=None, public=False) -> Path:
    recs = read_manifest(manifest_path)
    mpath = Path(manifest_path)
    out = Path(out_html)
    sweep = (recs[0].get("sweep") if recs else {}) or {}
    name = sweep.get("name") or mpath.parent.name
    piv = pivot(recs)

    n_ok = sum(1 for r in recs if r.get("status") == "ok")
    n_err = sum(1 for r in recs if r.get("status") != "ok")
    n_noz0 = sum(1 for r in recs if r.get("z0_missing"))
    payload = (recs[0].get("payload") if recs else {}) or {}
    if public:
        try:
            import importlib.util
            _s = importlib.util.spec_from_file_location(
                "_sao_dora_page", "/home/kim/Projects/SAO/Misc/build_dora_table_page.py")
            _m = importlib.util.module_from_spec(_s)
            _saved = list(sys.path)
            try:
                _s.loader.exec_module(_m)
            finally:
                sys.path[:] = _saved
            payload = _m.redact_public(payload)
        except Exception:
            payload = {k: v for k, v in payload.items() if k != "ckpt_path"}

    repro = (".venv/bin/python eval/sweep_run.py "
             f"--spec <spec>.json --out {mpath.parent}")
    page_title = title or f"sweep · {name}"

    header = (
        f"<h1>{_html.escape(page_title)}</h1>"
        f'<p class="sw-meta">{len(recs)} cells · {n_ok} ok · {n_err} error'
        + (f" · {n_noz0} with no z0" if n_noz0 else "")
        + f' · manifest <code>{_html.escape(str(mpath))}</code>'
        f' · built {time.strftime("%Y-%m-%d %H:%M")}</p>')

    resource = (
        '<div class="sw-box"><h3>Reproduce this exactly</h3>'
        f'<div class="sw-pre">{_html.escape(repro)}</div>'
        f'<p class="sw-meta">preset: <b>{_html.escape(str(sweep.get("preset") or "inline payload"))}</b>'
        f' · axes: {_html.escape(", ".join(piv["axes"]) or "none")}</p>'
        "<p>The payload every cell started from (one axis value replaced per cell):</p>"
        f'<div class="sw-pre">{_html.escape(json.dumps(payload, indent=2, sort_keys=True))}</div>'
        f'<p class="sw-meta">manifest: <a href="file://{_html.escape(str(mpath))}">'
        "manifest.jsonl</a> — one line per cell, carrying the exact payload that "
        "was POSTed, so this page can be rebuilt even if the preset is edited later.</p>"
        "</div>")

    body = ("<p>no cells in this manifest yet — run the sweep, then rebuild this page.</p>"
            if not recs else _table_html(piv))

    doc = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{_html.escape(page_title)}</title>"
        f"<style>{BASE_CSS}{WAVEFORM_CSS}{PAGE_CSS}</style></head><body>"
        f"{WAVEFORM_JS}<div class='wrap'>"
        f"{header}{explainer_html({'axes': piv['axes']})}{body}{resource}"
        "</div>" + HEARD_JS + "</body></html>")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build a sweep results page from a manifest.")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", default=None, help="default: <manifest dir>/index.html")
    ap.add_argument("--title", default=None)
    ap.add_argument("--public", action="store_true",
                    help="apply the public redaction rules to the payload block")
    a = ap.parse_args(argv)
    out = a.out or (Path(a.manifest).parent / "index.html")
    p = build(a.manifest, out, title=a.title, public=a.public)
    print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
