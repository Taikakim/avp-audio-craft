#!/usr/bin/env python3
"""Morph-conditioner audition page — the 16-arm melody/morph grid, same-playhead.

WHY (Kim 2026-09-03): the morphcond grid was TRAINED and RENDERED weeks ago and never
auditioned — 384 cells sitting on the UUID drive with no way to listen to them side by
side. Kim: "create the clips and an eval site." The clips already existed; this builds the
site over them (transcoded to the serving codec, AAC 192k, matching headb_bracket).

WHAT THE GRID IS: 16 arms = 4 contour vocabularies (L2=5, L3/IOI3=15, L4=77 symbols) x
{medium-base backbone, full-FT backbone} x seeds. Each arm is rendered against 8 source
stems, at three conditions: UNCONDITIONED (the control — the projection is zero-init, so
this is the plain model), gain 1.0, and gain 2.0. Every stem also has its REFERENCE clip,
the track the contour stream was extracted from. cfg 7, 24 steps throughout.

READ IT AS A/B/C, NOT AS QUALITY: the question is whether the conditioned renders follow
the reference's melodic movement MORE than the unconditioned one does. The unconditioned
column is the same model with the control switched off, so any difference is the control.

Reuses Misc/build_evals.py's PLAYER_JS (the same-playhead player ARCHITECTURE says to
import for any player page) rather than writing a third one -- same reuse rule as
eval/build_sweep_page.py.

  eval/build_morph_page.py            # -> ~/evals_aac/morph_conditioner/index.html
"""
import argparse, glob, html, importlib.util, json, os, re, sys
from collections import defaultdict
from pathlib import Path

RENDERS = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/lumi_runs/renders/morph"
OUT_DIR = Path.home() / "evals_aac" / "morph_conditioner"
VOCAB_NAME = {5: "L2 (5 symbols)", 15: "L3 / IOI3 (15)", 77: "L4 (77)", 9: "headb (9)"}


def _load_build_evals():
    """Load Misc/build_evals.py BY PATH and restore sys.path.

    build_evals.py:21 prepends Misc/ to sys.path, where a first-party filelock.py shadows
    the pip package huggingface_hub needs -- importing it normally poisons the whole
    process (found 2026-08-26, three unrelated server tests started failing).
    """
    src = Path("/home/kim/Projects/SAO/Misc/build_evals.py")
    spec = importlib.util.spec_from_file_location("_sao_build_evals", src)
    mod = importlib.util.module_from_spec(spec)
    saved = list(sys.path)
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path[:] = saved
    return mod


def collect(renders: str) -> tuple[list[dict], dict]:
    cells, refs = [], {}
    for f in sorted(glob.glob(f"{renders}/*/*.json")):
        d = json.load(open(f))
        base = os.path.basename(f)[:-5]
        if base.startswith("morph__"):
            base = base[len("morph__"):]
        arm = os.path.basename(os.path.dirname(f))
        bk = str(d.get("backbone", ""))
        cells.append({
            "arm": arm, "audio": base + ".m4a", "stem": str(d.get("stem", "")),
            "gain": None if not d.get("conditioned") else float(d.get("gain", 1.0)),
            "vocab": int(d.get("vocab", 0)), "seed": d.get("seed"),
            "window": d.get("window"), "prompt": d.get("prompt", ""),
            "ckpt": d.get("ckpt", ""),
            "backbone": "full-FT" if bk.startswith("/scratch") else (bk or "?"),
        })
    # References live in a refs/ SUBDIR of each arm dir (the same 8 files repeated per
    # arm), not beside the cells -- globbing one level too high silently yields zero refs
    # and the page loses its whole point of comparison, with no error.
    for w in sorted(glob.glob(f"{renders}/*/refs/*.wav")):
        stem = re.sub(r"^ref__", "", os.path.basename(w)[:-4])
        refs.setdefault(stem, f"ref__{stem}.m4a")
    return cells, refs


def build(cells, refs, out_dir: Path, player_js: str) -> Path:
    by_stem = defaultdict(lambda: defaultdict(dict))     # stem -> arm -> gainkey -> cell
    arm_meta = {}
    for c in cells:
        key = "null" if c["gain"] is None else f"g{c['gain']:g}"
        by_stem[c["stem"]][c["arm"]][key] = c
        arm_meta.setdefault(c["arm"], c)
    arms = sorted(arm_meta, key=lambda a: (arm_meta[a]["vocab"], arm_meta[a]["backbone"], a))
    stems = sorted(by_stem)
    prompt = next((c["prompt"] for c in cells if c["prompt"]), "")

    def cell(c):
        if not c:
            return '<td class="miss">—</td>'
        return (f'<td><button class="clip" data-src="{html.escape(c["audio"])}" '
                f'onclick="play(this)" title="{html.escape(c["audio"])}">▶</button></td>')

    parts = [f"""<!doctype html><meta charset="utf-8"><title>Morph conditioner — audition</title>
<style>
:root{{color-scheme:dark}}
body{{background:#0e0f12;color:#dbe;font:14px/1.55 'IBM Plex Sans',system-ui,sans-serif;margin:0;padding:0 0 90px}}
.wrap{{max-width:100%;padding:22px 26px}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:16px;margin:30px 0 8px;color:#9be}}
.sub{{color:#8a93a6;margin:0 0 20px}}
.box{{background:#16181c;border:1px solid #24262c;border-radius:8px;padding:14px 16px;margin:0 0 16px}}
.box h3{{margin:0 0 6px;font-size:14px;color:#7cf;letter-spacing:.02em}}
.box p{{margin:6px 0}} code{{background:#1d2026;padding:1px 5px;border-radius:3px;font-size:12.5px}}
table{{border-collapse:collapse;width:100%;margin:6px 0 4px;font-size:13px}}
th,td{{border-bottom:1px solid #21232a;padding:5px 8px;text-align:left}}
th{{color:#8fa;font-weight:600;position:sticky;top:0;background:#0e0f12}}
td.miss{{color:#555}}
button.clip{{background:#1d2733;border:1px solid #2c3a4a;color:#7cf;border-radius:4px;
  cursor:pointer;padding:2px 10px;font-size:13px}}
button.clip:hover{{background:#26374a}}
button.clip.playing{{background:#7cf;color:#0e0f12;border-color:#7cf}}
.refrow{{background:#141a20}} .tag{{color:#8a93a6;font-size:12px}}
.ctl{{color:#6fa}} .warn{{color:#fb7}}
</style>
<div class="wrap">
<h1>Morph conditioner — 16-arm audition</h1>
<p class="sub">Contour-stream conditioning on SA3. {len(cells)} rendered cells · {len(arms)} arms ×
{len(stems)} source stems × 3 conditions · cfg 7 · 24 steps · AAC 192k.</p>

<div class="box">
<h3>WHAT THIS IS — read this first if you have not seen the morph conditioner</h3>
<p>The model normally writes whatever melody it likes. The <b>morph conditioner</b> is an extra
input that hands it a <i>contour stream</i> — a symbolic sketch of how a melody MOVES (up a little,
down a lot, hold) taken from a real track, rather than the actual notes. The question this page
answers by ear is simple: <b>does the model follow that sketch?</b></p>
<p>Each row is one trained arm. The three buttons are the SAME model on the SAME source, with the
control turned <b>off</b>, on at <b>gain 1.0</b>, and on at <b>gain 2.0</b>. The
<span class="ctl">reference</span> row at the top of each block is the real track the sketch came
from. Off is a true control, not a different model: the control projection is zero-initialised, so
with it off the render is the plain model.</p>
<p><b>How to listen.</b> Play the reference, then off, then 1.0, then 2.0 — the player keeps its
position, so you stay at the same moment in the music while switching. You are listening for
melodic <i>movement</i> matching the reference, not for the same notes and not for better audio.
Higher gain pushing harder is expected; whether it stays musical is the actual question.</p>
<p class="warn">Do not read this page as a quality ranking. Every arm shares one prompt and one
cfg; it isolates the control, nothing else.</p>
</div>

<div class="box">
<h3>FOR ENGINEERS — recipe and reproduction</h3>
<p><b>Grid.</b> 4 contour vocabularies (L2 = 5 symbols, L3/IOI3 = 15, L4 = 77) × backbone
(<code>medium-base</code> vs a full-FT backbone) × seeds = {len(arms)} arms. Each rendered against
{len(stems)} source stems at gain {{off, 1.0, 2.0}}. Coverage 1.0, cfg 7.0, 24 steps, T512 windows.</p>
<p><b>Prompt (identical for every cell).</b> <code>{html.escape(prompt[:400])}</code></p>
<p><b>Streams.</b> Each cell has its contour stream saved next to the render as
<code>*.stream.npy</code>, and its latent as <code>*.z0.npy</code> — so any cell can be re-decoded
or re-scored without re-rendering.</p>
<p><b>Sources.</b> renders <code>{html.escape(RENDERS)}</code> · builder
<code>eval/build_morph_page.py</code> · conditioner code
<code>mir/src/conditioners/{{morph_grids,contour_codes,contour_streams}}.py</code> ·
experiment registry <code>EXPERIMENTS.md</code> D12 (contour-token stack) and the morph head sweep.</p>
<p class="warn"><b>Not yet measured.</b> This page is the listening surface only. There is no
objective adherence number for these cells yet — the transcription-based note-cell F1 used for the
pianoroll control (D15) has not been run against the contour streams. Treat any impression from
this page as a hypothesis until that exists.</p>
</div>
{player_js}
"""]

    for st in stems:
        parts.append(f'<h2>Source stem <code>{html.escape(st)}</code></h2>')
        parts.append('<table><thead><tr><th style="width:30%">arm</th><th>vocab</th>'
                     '<th>backbone</th><th>seed</th><th>control off</th><th>gain 1.0</th>'
                     '<th>gain 2.0</th></tr></thead><tbody>')
        r = refs.get(st)
        if r:
            parts.append(f'<tr class="refrow"><td colspan="4"><span class="ctl">▲ REFERENCE</span> '
                         f'<span class="tag">the track the contour was taken from</span></td>'
                         f'<td colspan="3"><button class="clip" data-src="{html.escape(r)}" '
                         f'onclick="play(this)">▶ reference</button></td></tr>')
        for a in arms:
            m = arm_meta[a]
            g = by_stem[st].get(a, {})
            parts.append(
                f'<tr><td><code>{html.escape(a)}</code></td>'
                f'<td>{html.escape(VOCAB_NAME.get(m["vocab"], str(m["vocab"])))}</td>'
                f'<td>{html.escape(m["backbone"])}</td><td>{html.escape(str(m["seed"]))}</td>'
                + cell(g.get("null")) + cell(g.get("g1")) + cell(g.get("g2")) + '</tr>')
        parts.append('</tbody></table>')

    parts.append('<p class="sub" style="margin-top:26px">Built by <code>eval/build_morph_page.py</code>'
                 ' — CONTINUITY, 2026-09-03. Clips are AAC 192k transcodes of the original WAVs on the'
                 ' UUID drive; the WAVs, contour streams and z0 latents stay there.</p></div>')

    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "index.html"
    p.write_text("\n".join(parts))
    return p


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--renders", default=RENDERS)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--public", action="store_true",
                    help="also write index_public.html with build_evals.redact() applied: "
                         "absolute paths -> '…', checkpoint names -> '[checkpoint]', addrs/venvs "
                         "stripped. WINTERMUTE rsyncs the staging dir to the public server, so the "
                         "page that goes online must be the redacted one (spec §4; precedent: "
                         "dora_table.html vs dora_table_public.html).")
    args = ap.parse_args()

    if not os.path.isdir(args.renders):
        sys.exit(f"renders dir not found (drive unmounted?): {args.renders}")
    cells, refs = collect(args.renders)
    if not cells:
        sys.exit("no cells parsed — check the renders path")
    missing = [c["audio"] for c in cells if not (args.out / c["audio"]).exists()]
    if missing:
        print(f"[warn] {len(missing)} cells have no transcoded m4a "
              f"(first: {missing[0]}) — they will render as dead buttons", file=sys.stderr)
    # Register the board so the census stops reporting these arms as clips='-'. Written
    # HERE, by the builder, so the registry cannot drift from what was actually built --
    # a registry claiming coverage that does not exist is the same false signal pointed
    # the other way (GHOST-NOTE's check, 2026-09-03).
    reg = Path(__file__).resolve().parent / "eval_boards.json"
    boards = json.loads(reg.read_text()) if reg.exists() else {"boards": []}
    boards.setdefault("_doc",
        "Eval boards that are NOT the standard model matrix. The census reads this so arms "
        "auditioned elsewhere are not reported as having zero clips -- see "
        "eval/build_model_census.py::load_boards. REGISTER, DON'T MERGE: these grids have "
        "different axes and their own control arms; folding them onto the standard board "
        "destroys the A/B.")
    entry = {
        "id": "morph_conditioner",
        "title": "Morph conditioner audition",
        "kind": "control-response grid (gain x source stem; control arm = same model, "
                "projection zeroed)",
        "url": "file://" + str(args.out / "index.html"),
        "public": "morph_conditioner/index_public.html",
        "cells": len(cells),
        "note": ("NOT VALIDATED: no objective adherence metric exists for these cells. The "
                 "transcription note-cell F1 that gave D15 its verdict (+0.100, 6/6, p=0.016) "
                 "has never been ported to contour streams. Listening surface only."),
        "builder": "eval/build_morph_page.py",
        # FULL census arm paths, not leaves: 12 leaves collide in the live census and a
        # leaf entry can credit an arm nobody auditioned (GHOST-NOTE 2026-09-03).
        "arms": sorted({f"morphcond/{c['arm']}" for c in cells}),
        "arms_note": "full census arm paths — never bare leaves; see apply_boards docstring",
    }
    boards["boards"] = [b for b in boards.get("boards", []) if b.get("id") != entry["id"]]
    boards["boards"].append(entry)
    reg.write_text(json.dumps(boards, indent=1, ensure_ascii=False) + "\n")
    print(f"registered board 'morph_conditioner' ({len(entry['arms'])} arms) -> {reg}")

    be = _load_build_evals()
    p = build(cells, refs, args.out, be.PLAYER_JS)
    if args.public:
        pub = args.out / "index_public.html"
        # redact() is line-safe: it only rewrites paths/ckpt names, never the audio
        # basenames the player needs (those are relative, so _ABS cannot match them).
        red = be.redact(p.read_text())
        pub.write_text(red)
        import re as _re
        leaked = _re.findall(r"/run/media/\S+|/scratch/\S+|/home/kim/\S+", red)
        print(f"wrote {pub}" + (f"  ⚠ {len(leaked)} paths still present: {leaked[:2]}"
                                if leaked else "  (no absolute paths remain)"))
    print(f"cells {len(cells)} · refs {len(refs)} · arms "
          f"{len({c['arm'] for c in cells})} · stems {len({c['stem'] for c in cells})}")
    print(f"wrote {p}")


if __name__ == "__main__":
    main()
