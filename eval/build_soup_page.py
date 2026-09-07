#!/usr/bin/env python3
"""Audition page for the PT->base soup ladder — CONTINUITY 2026-09-07.

Rows are ARMS along the rewind ladder (base -> a050 -> local000 -> PT), columns are
prompt x step-count, one table PER SAMPLER. Same-playhead player, so switching arms
keeps position -- the only way to hear "how much post-training" as a single dimension.

⚠ One table per sampler is not cosmetic. PT (medium) is diffusion_objective 'rf_denoiser',
native sampler pingpong; base (medium-base) is 'rectified_flow'/euler; and a blend loads
medium-base's CONFIG whatever its alpha. A cross-sampler comparison is a sampler
comparison, so the page refuses to put them in one table.

Reuses Misc/build_evals.py's PLAYER_JS + redact() by path (see _load_build_evals).

  eval/build_soup_page.py --dir ~/evals_aac/soup_rewind --out ~/evals_aac/soup_rewind
"""
import argparse, html, importlib.util, json, re, sys
from collections import defaultdict
from pathlib import Path

PAT = re.compile(r"^(?P<arm>.+?)__(?P<prompt>goa|psy|break)__st(?P<steps>\d+)__cfg(?P<cfg>[\d.]+)\.wav$")

# ladder order + what each arm IS. Anything unlisted sorts last, still shown.
ARMS = [
    ("endpoint_base", "base", "medium-base, alpha=0 — no post-training at all"),
    ("ptm_a050", "alpha 0.5", "W = base + 0.5*(PT-base): half the post-training, every tensor"),
    ("ptm_local000", "alpha 1, biases 0", "full PT EXCEPT the 48 to_local_embed.*bias tensors held at base"),
    ("endpoint_pt", "PT", "medium, alpha=1 — the shipped post-trained model"),
]


def _load_build_evals():
    """Load Misc/build_evals.py BY PATH and restore sys.path.

    build_evals.py:21 prepends Misc/ to sys.path, where a first-party filelock.py shadows
    the pip package huggingface_hub needs -- importing it normally poisons the process.
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


def collect(d: Path):
    cells, unparsed = [], []
    for w in sorted(d.glob("*.wav")):
        m = PAT.match(w.name)
        if not m:
            unparsed.append(w.name)
            continue
        j = w.with_suffix(".json")
        meta = json.loads(j.read_text()) if j.exists() else {}
        arm = m["arm"]
        sampler = meta.get("sampler") or ("pingpong" if arm.endswith("_pingpong") else "euler")
        cells.append(dict(arm=re.sub(r"_(pingpong|euler)$", "", arm), sampler=sampler,
                          prompt=m["prompt"], steps=int(m["steps"]), file=w.name,
                          promptext=meta.get("prompt", ""), seed=meta.get("seed")))
    return cells, unparsed


def build(cells, out: Path, player_js: str) -> Path:
    by = defaultdict(dict)                       # sampler -> (arm,prompt,steps) -> cell
    for c in cells:
        by[c["sampler"]][(c["arm"], c["prompt"], c["steps"])] = c
    prompts = sorted({c["prompt"] for c in cells})
    steps = sorted({c["steps"] for c in cells})
    seeds = sorted({c["seed"] for c in cells if c["seed"] is not None})
    ptext = {c["prompt"]: c["promptext"] for c in cells if c["promptext"]}
    order = {a: i for i, (a, _, _) in enumerate(ARMS)}
    label = {a: (l, d) for a, l, d in ARMS}

    P = [f"""<!doctype html><meta charset="utf-8"><title>Post-training rewind — soup ladder</title>
<style>
:root{{color-scheme:dark}}
body{{background:#0e0f12;color:#dbe;font:14px/1.55 'IBM Plex Sans',system-ui,sans-serif;margin:0;padding:0 0 90px}}
.wrap{{max-width:100%;padding:22px 26px}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:16px;margin:30px 0 8px;color:#9be}}
table{{border-collapse:collapse;width:100%;margin:8px 0 4px}}
th,td{{border:1px solid #263;padding:5px 8px;text-align:center;font-size:13px}}
th{{background:#151821;color:#9be;font-weight:600}}
td.arm,th.arm{{text-align:left;white-space:nowrap}}
td.arm b{{color:#fff}} td.arm span{{color:#8a93a6;font-size:12px}}
td.miss{{color:#555}}
button.clip{{background:#1d2430;border:1px solid #3a4a63;color:#cfe;border-radius:4px;
 padding:3px 11px;cursor:pointer;font-size:13px}}
button.clip:hover{{background:#2a3648}} button.clip.playing{{background:#2f6;color:#000}}
.note{{background:#12151d;border-left:3px solid #9be;padding:12px 16px;margin:14px 0;
 font-size:13px;color:#c3cad8;max-width:88ch}}
.note b{{color:#9be}} .warn{{border-left-color:#e94}} .warn b{{color:#e94}}
code{{background:#1a1e27;padding:1px 5px;border-radius:3px;font-size:12px}}
</style>
<div class="wrap">
<h1>Post-training rewind — the PT&nbsp;&rarr;&nbsp;base soup ladder</h1>

<div class="note">
<b>What this is.</b> Stable Audio 3 ships as two checkpoints: <code>medium-base</code>, the
plain pretrained model, and <code>medium</code>, the same model after a post-training pass.
The post-trained one sounds tighter and punchier, but it also sounds <i>the same every time</i> —
similar kick, similar bass, similar percussion, whatever you ask for. This page asks whether
those two things can be pulled apart.
<br><br>
<b>How.</b> A "soup" is a straight linear blend of two sets of weights:
<code>W = base + &alpha;&middot;(PT &minus; base)</code>. At &alpha;=0 you get base, at &alpha;=1
you get PT, and in between you get a model that has had some fraction of the post-training
applied. Every clip below is the same prompt and the same seed, so the <i>only</i> thing that
changes down a column is how much post-training is in the weights.
<br><br>
<b>How to listen.</b> Play any clip, then click another in the same column — the playhead stays
put, so you hear the same musical moment under different amounts of post-training. Listen for
two things separately: does it get <i>tighter</i> going down, and does it get <i>more
generic</i> going down? If those two turn out to move together at every step, they are one
knob and the trade is unavoidable. If one moves faster than the other, there is a setting
worth having.
</div>

<div class="note warn">
<b>Read each table on its own — never across tables.</b> PT and base do not share a sampler.
PT is <code>diffusion_objective: rf_denoiser</code>, whose native sampler is
<b>pingpong</b>; base is <code>rectified_flow</code>, whose sampler is <b>euler</b>. A blend
loads base's config no matter its &alpha;, so every blend samples as <code>rectified_flow</code>.
Both samplers are therefore rendered for every arm: within one table the sampler is fixed and
differences are purely weights, but a clip compared <i>across</i> tables differs by sampler too,
which is the larger effect. The euler table is the controlled experiment; the pingpong table is
where PT sounds like the model people actually use.
</div>
"""]
    if seeds:
        P.append(f'<div class="note">Seed {", ".join(str(s) for s in seeds)}, cfg 7, 20 s per clip. '
                 f'Prompts: ' + "; ".join(f'<b>{html.escape(k)}</b> — {html.escape(v)}'
                                          for k, v in sorted(ptext.items())) + '</div>')

    for sampler in sorted(by, key=lambda s: (s != "euler", s)):
        tab = by[sampler]
        arms = sorted({a for a, _, _ in tab}, key=lambda a: (order.get(a, 99), a))
        native = {"euler": "base's native sampler", "pingpong": "PT's native sampler"}.get(sampler, "")
        P.append(f'<h2>sampler: {html.escape(sampler)}'
                 + (f' <span style="color:#8a93a6;font-size:13px">— {native}</span>' if native else "")
                 + '</h2>')
        P.append('<table><tr><th class="arm">arm</th>'
                 + "".join(f'<th>{html.escape(p)} · {s} steps</th>' for s in steps for p in prompts)
                 + "</tr>")
        for a in arms:
            lab, desc = label.get(a, (a, ""))
            P.append(f'<tr><td class="arm"><b>{html.escape(lab)}</b><br><span>{html.escape(desc)}</span></td>')
            for s in steps:
                for p in prompts:
                    c = tab.get((a, p, s))
                    P.append(f'<td><button class="clip" data-src="{html.escape(c["file"])}" '
                             f'onclick="play(this)" title="{html.escape(c["file"])}">&#9654;</button></td>'
                             if c else '<td class="miss">&mdash;</td>')
            P.append("</tr>")
        P.append("</table>")

    P.append("</div>\n" + player_js)
    out.mkdir(parents=True, exist_ok=True)
    p = out / "index.html"
    p.write_text("\n".join(P))
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, required=True, help="dir holding the rendered wavs")
    ap.add_argument("--out", type=Path, help="page dir (default: --dir, so hrefs stay relative)")
    ap.add_argument("--public", action="store_true",
                    help="also write index_public.html with build_evals.redact() applied — "
                         "the only page that may go online (spec §4)")
    a = ap.parse_args()
    out = a.out or a.dir
    cells, unparsed = collect(a.dir)
    if not cells:
        sys.exit(f"no parsable wavs in {a.dir}")
    for u in unparsed:
        print(f"  ! unparsed, NOT on page: {u}")
    be = _load_build_evals()
    p = build(cells, out, be.PLAYER_JS)
    print(f"wrote {p}  ({len(cells)} clips, "
          f"{len({c['sampler'] for c in cells})} samplers, {len({c['arm'] for c in cells})} arms)")
    if a.public:
        pub = out / "index_public.html"
        pub.write_text(be.redact(p.read_text()))
        print(f"wrote {pub}")


if __name__ == "__main__":
    main()
