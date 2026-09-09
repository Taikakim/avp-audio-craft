#!/usr/bin/env python3
"""D17 morph-conditioner TRAINING-LADDER audition page — same-playhead.

WHY A SEPARATE PAGE AND NOT THE MODEL MATRIX (project direction, 2026-09-09): this is a
CONTROL-ADAPTER arm (riffer_step*.pt), which model_matrix_gen.py can neither render nor
load, and its axes do not correspond to the board's. The board is cfg x strength x
prompt-id; this set is CHECKPOINT x source-stem x {off, gain 1.0, gain 2.0}. Flattening it
onto the matrix would destroy the only comparison it exists for -- control off vs on --
because the board has no null-vs-conditioned axis at all.

HOW IT DIFFERS FROM ITS SIBLING eval/build_morph_page.py (the D12 16-arm grid): there the
row axis is vocabulary x backbone, a GRID of independent arms. Here every row is the SAME
run at a different training step, so the rows are a TRAJECTORY and must be read down the
column: does adherence grow with training? That question -- capacity-limited or at the
ceiling of the Head-B path -- is the run's stated hypothesis and its kill criterion.

Reuses Misc/build_evals.py's PLAYER_JS (the same-playhead player ARCHITECTURE says to
import for any player page) and redact(), same rule as build_morph_page.py.

  eval/build_morph_step_page.py --public   # -> ~/evals_aac/morph_d17_lion_r128/index.html
"""
import argparse, glob, html, importlib.util, json, os, re, sys
from collections import defaultdict
from pathlib import Path

RUN = ("/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/sa3_control_runs/"
       "morph_L3_lion_r128_bs32_2026-09-09")
OUT_DIR = Path.home() / "evals_aac" / "morph_d17_lion_r128"
# Rendered from checkpoints only up to 12000. 14000/16000/riffer_final exist as weights but
# were deliberately not rendered: that arm went into a weight-norm runaway (median loss
# 0.993 -> 1.929, gnorm 0.294 -> 1.639 between the 12-15k and 15-18k bins), and an
# unlabelled degraded checkpoint on a listening page invites an A/B nobody can interpret.
DEGRADED = ("step14000", "step16000", "riffer_final")


def _load_build_evals():
    """Load Misc/build_evals.py BY PATH and restore sys.path.

    build_evals.py prepends Misc/ to sys.path, where a first-party filelock.py shadows the
    pip package huggingface_hub needs -- importing it normally poisons the whole process.
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


def step_of(label: str) -> int:
    """Training step from the checkpoint label; sorts the ladder numerically.

    Lexical sort would order step10000 before step2000 and silently present the trajectory
    out of order -- on a page whose entire claim is 'watch this grow', that is not cosmetic.
    """
    m = re.search(r"step(\d+)", label)
    return int(m.group(1)) if m else -1


def collect(clips_dir: str):
    cells, refs = [], {}
    for f in sorted(glob.glob(os.path.join(clips_dir, "*.json"))):
        base = os.path.basename(f)[:-5]
        if base == "run_meta":
            continue
        if any(d in base for d in DEGRADED):
            continue
        d = json.load(open(f))
        if base.startswith("morph__"):
            base = base[len("morph__"):]
        cells.append({
            "label": d.get("label", ""), "audio": base + ".m4a",
            "stem": str(d.get("stem", "")),
            "gain": None if not d.get("conditioned") else float(d.get("gain", 1.0)),
            "seed": d.get("seed"), "prompt": d.get("prompt", ""),
            "cfg": d.get("cfg"), "steps": d.get("steps"), "frames": d.get("frames"),
            "vocab": d.get("vocab"), "coverage": d.get("coverage"),
        })
    for w in sorted(glob.glob(os.path.join(clips_dir, "refs", "*.wav"))):
        stem = re.sub(r"^ref__", "", os.path.basename(w)[:-4])
        refs[stem] = f"ref__{stem}.m4a"
    return cells, refs


def build(cells, refs, meta, out_dir: Path, player_js: str) -> Path:
    by_stem = defaultdict(lambda: defaultdict(dict))
    lab_meta = {}
    for c in cells:
        key = "null" if c["gain"] is None else f"g{c['gain']:g}"
        by_stem[c["stem"]][c["label"]][key] = c
        lab_meta.setdefault(c["label"], c)
    labels = sorted(lab_meta, key=step_of)
    stems = sorted(by_stem)
    one = cells[0]
    rec = meta.get("recipe", {})
    ds = meta.get("dataset", {})
    audited = bool(meta.get("kim_feedback"))

    def cell(c):
        if not c:
            return '<td class="miss">—</td>'
        return (f'<td><button class="clip" data-src="{html.escape(c["audio"])}" '
                f'onclick="play(this)" title="{html.escape(c["audio"])}">▶</button></td>')

    flag = ("" if audited else
            '<p class="warn"><b>❗ UNAUDITED</b> — no listening verdict recorded for this set yet. '
            'The mark clears when a verdict is written into the run sidecar.</p>')

    parts = [f"""<!doctype html><meta charset="utf-8"><title>Morph conditioner — training ladder (D17)</title>
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
.ctl{{color:#6fa}} .warn{{color:#fb7}} .step{{color:#cbd}}
</style>
<div class="wrap">
<h1>Morph conditioner — training ladder</h1>
<p class="sub">{len(cells)} cells · {len(labels)} checkpoints × {len(stems)} source stems × 3 conditions
· cfg {one.get('cfg')} · {one.get('steps')} steps · T{one.get('frames')} · AAC 192k.</p>
{flag}
<div class="box">
<h3>WHAT THIS IS — read this first</h3>
<p>The model normally writes whatever melody it likes. The <b>morph conditioner</b> hands it a
<i>contour stream</i> instead — a symbolic sketch of how a melody MOVES (up a little, down a lot,
hold), taken from a real track rather than its actual notes. The question this page answers by ear:
<b>does the model follow the sketch, and does it follow it MORE as training goes on?</b></p>
<p>Each row is the same run at a later training step. The three buttons are the SAME model on the
SAME source with the control <b>off</b>, at <b>gain 1.0</b>, and at <b>gain 2.0</b>. Off is a true
control, not a different model — it is the trained null stream, and the seed and prompt are
identical across all three, so any difference you hear is the control and nothing else.</p>
<p><b>How to listen.</b> Play the <span class="ctl">reference</span>, then off, then 1.0, then 2.0;
the player holds its position so you stay at the same moment while switching. Listen for melodic
<i>movement</i> matching the reference — rises where it rises, falls where it falls. <b>Not</b> the
same notes and <b>not</b> the same key: the alphabet encodes relative motion, so matching pitch
would be coincidence and matching shape is the result. Timbre changing is not adherence.</p>
<p><b>Then read DOWN the column.</b> This is a trajectory, not a grid of rivals. If adherence grows
from the earliest checkpoint to the latest, the earlier weak-but-real result was capacity-limited.
If it is flat, the run's own kill criterion says this conditioning path is at its ceiling and the
next move is a different inlet, not a bigger adapter.</p>
<p class="warn">Not a quality ranking. One prompt, one cfg, one seed per source; it isolates the
control and nothing else. Expect subtlety — the result this set is trying to beat was itself weak.</p>
</div>

<div class="box">
<h3>FOR ENGINEERS — recipe and reproduction</h3>
<p><b>Ladder.</b> checkpoints {", ".join(str(step_of(l)) for l in labels)} of one run ×
{len(stems)} source stems × {{off, gain 1.0, gain 2.0}}. Coverage {one.get('coverage')},
cfg {one.get('cfg')}, {one.get('steps')} steps, T{one.get('frames')} windows.</p>
<p><b>Recipe.</b> {html.escape(rec.get('control_mode',''))} · alphabet
<code>{html.escape(str(rec.get('alphabet','')))}</code> (vocab {one.get('vocab')}) · backbone
<code>{html.escape(str(rec.get('backbone','')))}</code> · DoRA rank {rec.get('dora_rank')}
alpha {rec.get('dora_alpha')} · {html.escape(str(rec.get('optimizer','')))} ·
{html.escape(str(rec.get('precision','')))} · batch {rec.get('batch')} × grad-accum
{rec.get('grad_accum')} = effective {rec.get('effective_batch')} · crop
{rec.get('crop_frames')} frames · EMA {rec.get('ema')} · seed {rec.get('seed')}.</p>
<p><b>Corpus.</b> {html.escape(", ".join(ds.get('corpora', [])))} — {ds.get('crops_total')} crops
over {ds.get('tracks')} tracks ({ds.get('crops_goa')} goa + {ds.get('crops_avp')} AVP);
weighting: {html.escape(str(ds.get('weighting','')))}.</p>
<p><b>Hypothesis.</b> {html.escape(meta.get('hypothesis',''))}</p>
<p><b>Kill criterion.</b> {html.escape(meta.get('kill_criterion',''))}</p>
<p><b>Prompt (identical for every cell).</b> <code>{html.escape(one.get('prompt','')[:400])}</code></p>
<p><b>Not on the ladder, on purpose.</b> Three later checkpoints exist as weights but were not
rendered: that arm went into a weight-norm runaway (median loss 0.993 → 1.929, median grad-norm
0.294 → 1.639 across the following bins). An unlabelled degraded checkpoint beside healthy ones
invites an A/B whose conclusion would be about the collapse, not about capacity.</p>
<p><b>Streams and latents.</b> Every cell keeps its contour stream (<code>*.stream.npy</code>) and
its latent (<code>*.z0.npy</code>) beside the original WAV, so any cell can be re-decoded or
re-scored without re-rendering. All 76 files here verified at peak 0.8913 (the −1 dBFS render
target) with zero non-finite latents.</p>
<p class="warn"><b>Not measured.</b> Listening surface only. No objective adherence number exists
for contour streams — the transcription note-cell F1 that settled the pianoroll control was never
ported to them. Treat any impression here as a hypothesis, not a result.</p>
</div>
{player_js}
"""]

    for st in stems:
        parts.append(f'<h2>Source stem <code>{html.escape(st)}</code></h2>')
        parts.append('<table><thead><tr><th style="width:22%">training step</th><th>seed</th>'
                     '<th>control off</th><th>gain 1.0</th><th>gain 2.0</th>'
                     '</tr></thead><tbody>')
        r = refs.get(st)
        if r:
            parts.append(f'<tr class="refrow"><td colspan="2"><span class="ctl">▲ REFERENCE</span> '
                         f'<span class="tag">the track the contour was taken from</span></td>'
                         f'<td colspan="3"><button class="clip" data-src="{html.escape(r)}" '
                         f'onclick="play(this)">▶ reference</button></td></tr>')
        for lab in labels:
            m = lab_meta[lab]
            g = by_stem[st].get(lab, {})
            parts.append(
                f'<tr><td class="step">step <b>{step_of(lab):,}</b></td>'
                f'<td>{html.escape(str(m["seed"]))}</td>'
                + cell(g.get("null")) + cell(g.get("g1")) + cell(g.get("g2")) + '</tr>')
        parts.append('</tbody></table>')

    parts.append('<p class="sub" style="margin-top:26px">Built by '
                 '<code>eval/build_morph_step_page.py</code>. Clips are AAC 192k transcodes; the '
                 'WAVs, contour streams and z0 latents stay on the run drive.</p></div>')

    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "index.html"
    p.write_text("\n".join(parts))
    return p


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default=RUN, help="run dir holding clips/ and run_meta.json")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--public", action="store_true",
                    help="also write index_public.html with build_evals.redact() applied; that "
                         "is the file that goes online (spec §4).")
    args = ap.parse_args()

    clips = os.path.join(args.run, "clips")
    if not os.path.isdir(clips):
        sys.exit(f"clips dir not found (drive unmounted?): {clips}")
    meta_p = os.path.join(args.run, "run_meta.json")
    meta = json.loads(Path(meta_p).read_text()) if os.path.exists(meta_p) else {}
    cells, refs = collect(clips)
    if not cells:
        sys.exit("no cells parsed — check the run path")
    if not refs:
        sys.exit("no reference decodes found — the page's whole comparison is missing; refusing "
                 "to write a version that silently drops it")
    missing = [c["audio"] for c in cells if not (args.out / c["audio"]).exists()]
    if missing:
        print(f"[warn] {len(missing)} cells have no transcoded m4a "
              f"(first: {missing[0]}) — they will render as dead buttons", file=sys.stderr)

    reg = Path(__file__).resolve().parent / "eval_boards.json"
    boards = json.loads(reg.read_text()) if reg.exists() else {"boards": []}
    entry = {
        "id": "morph_d17_lion_r128",
        "title": "Morph conditioner — training ladder (D17)",
        "kind": "control-response trajectory (checkpoint x source stem x {off, g1.0, g2.0}; "
                "control arm = same model, trained null stream)",
        "url": "file://" + str(args.out / "index.html"),
        "public": "morph_d17_lion_r128/index_public.html",
        "cells": len(cells),
        "note": ("NOT VALIDATED: no objective adherence metric exists for contour streams. "
                 "Listening surface only. NOT on the model matrix by design -- a control "
                 "adapter the matrix cannot load, whose null-vs-conditioned axis the board "
                 "cannot express."),
        "builder": "eval/build_morph_step_page.py",
        "arms": [f"morph_d17/{meta.get('run', 'morph_L3_lion_r128_bs32')}"],
        "arms_note": "full census arm paths — never bare leaves; see apply_boards docstring",
    }
    boards["boards"] = [b for b in boards.get("boards", []) if b.get("id") != entry["id"]]
    boards["boards"].append(entry)
    reg.write_text(json.dumps(boards, indent=1, ensure_ascii=False) + "\n")
    print(f"registered board '{entry['id']}' -> {reg}")

    be = _load_build_evals()
    p = build(cells, refs, meta, args.out, be.PLAYER_JS)
    print(f"cells {len(cells)} · refs {len(refs)} · checkpoints "
          f"{len({c['label'] for c in cells})} · stems {len({c['stem'] for c in cells})}")
    print(f"wrote {p}")
    if args.public:
        pub = args.out / "index_public.html"
        red = be.redact(p.read_text())
        pub.write_text(red)
        leaked = re.findall(r"/run/media/\S+|/scratch/\S+|/home/kim/\S+", red)
        print(f"wrote {pub}" + (f"  ⚠ {len(leaked)} paths still present: {leaked[:2]}"
                                if leaked else "  (no absolute paths remain)"))


if __name__ == "__main__":
    main()
