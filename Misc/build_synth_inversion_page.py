"""Eval page: synth inversion of 24 real bass phrases — old model vs the FX-fixed rerun (online and EMA weights).

Reads the run's CPU clip step (stable-audio-tools/scripts/synth_inversion/run_fxfix_ladder_ema.sh):
  <RUN>/clips_{old,online,ema}/audio/<id>_{real,midi_playback}.wav   (same phrase slicing for every set)
  <RUN>/clips_AB/comparison.json                                       (MSS / wMFCC / RMS-envelope cos per stem)
  <RUN>/val_kinds.jsonl                                                (held-out validation, online vs EMA)
and writes ~/.cache/evals_aac/synth_inversion.html + synth_inversion/*.m4a (AAC 128k), same-playhead cells.
Missing clips render as "pending" cells, so the page can go up before the clips exist and be rebuilt after.
Public page: no checkpoint filenames or local paths (MASTER section 4 redaction rule).
Run (any python with numpy/soundfile not needed; ffmpeg on PATH): python3 Misc/build_synth_inversion_page.py
"""
import html
import importlib.util
import json
import os
import subprocess
from pathlib import Path

RUN = Path("/run/media/kim/Mantu/surge_200k_models/fxfix_ladder_ema_b64")
CATALOG = Path("/run/media/kim/Mantu/surge_200k_models/real_stems_eval/real_stems_summary.json")
OUT = Path.home() / ".cache/evals_aac"
PAGE, CLIPS = OUT / "synth_inversion.html", OUT / "synth_inversion"
SETS = [("old", "Old model", "the previous run, trained before the FX-state fix"),
        ("online", "New · online", "this run's final weights"),
        ("ema", "New · EMA", "this run's exponential moving average of the weights (half-life 2000 steps)")]
BUILD_EVALS = Path(__file__).parent / "build_evals.py"


def load_build_evals():
    spec = importlib.util.spec_from_file_location("_be", BUILD_EVALS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def to_m4a(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return True
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-c:a", "aac", "-b:a", "128k",
                        str(dst)], capture_output=True)
    return r.returncode == 0


def last_val():
    p = RUN / "val_kinds.jsonl"
    if not p.exists():
        return None
    rows = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    return rows[-1] if rows else None


def fmt(v, nd=2):
    return "—" if v is None else f"{v:.{nd}f}"


def main():
    be = load_build_evals()
    CLIPS.mkdir(parents=True, exist_ok=True)
    catalog = {d["id"]: d for d in json.load(open(CATALOG))} if CATALOG.exists() else {}
    comp_p = RUN / "clips_AB" / "comparison.json"
    comp = json.load(open(comp_p)) if comp_p.exists() else {"summary": {}, "rows": []}
    rows_by = {r["stem_id"]: r for r in comp["rows"]}
    ids = sorted(catalog) or sorted(rows_by)
    meta_p = RUN / "clips_AB" / "run_meta.json"
    feedback = json.load(open(meta_p)).get("kim_feedback") if meta_p.exists() else None

    have = {}
    for sid in ids:
        real_src = next((RUN / f"clips_{k}" / "audio" / f"{sid}_real.wav" for k, _, _ in SETS
                         if (RUN / f"clips_{k}" / "audio" / f"{sid}_real.wav").exists()), None)
        have[(sid, "real")] = bool(real_src) and to_m4a(real_src, CLIPS / f"{sid}_real.m4a")
        for k, _, _ in SETS:
            have[(sid, k)] = to_m4a(RUN / f"clips_{k}" / "audio" / f"{sid}_midi_playback.wav", CLIPS / f"{sid}_{k}.m4a")
    n_ready = sum(have[(s, k)] for s in ids for k, _, _ in SETS)
    complete = n_ready == len(ids) * len(SETS)

    v = last_val()
    doc = be.head("Synth inversion · real bass stems · FX-fixed rerun", 0)
    doc += ('<h1>Synth inversion — 24 real bass phrases, old model vs the FX-fixed rerun'
            + ('' if feedback else ' <span title="not yet audited by ear" style="color:#f44">&#10071;</span>') + '</h1>')
    doc += ('<p><b>What this is.</b> Each row is a bass phrase taken from a separated stem of a real track. A model '
            'listens to it and proposes Surge XT synth settings; the phrase is then re-played with those settings '
            '(notes from a MuScriptor transcription), after a short render-in-the-loop refinement fitted on the first '
            'half of the phrase. <b>Real</b> is the original; the other cells are re-creations. Click a cell to play; '
            'switching cells keeps the playhead, clicking again stops.</p>')
    doc += ('<p><b>Why this run.</b> The previous model looked fine in training but failed to generalise. The cause '
            'was a rendering bug: Surge kept hidden chorus/delay state between renders, so training audio leaked '
            'the previous patch. This run fixes the renderer and adds: one-knob "ladder" batches with an ordering '
            'loss, optimal-transport coupling for the flow, an EMA of the weights, 1.5× the initial learning rate, '
            'same number of steps (78,416). Question: do the re-creations get closer to the real phrases, and do '
            'the averaged (EMA) weights beat the final ones?</p>')
    if v:
        doc += ('<h2>Training result (held-out synth presets)</h2><table class="t"><tr><th></th><th>flow loss ↓</th>'
                '<th>JEPA loss ↓</th><th>retrieval audio→patch</th><th>patch→audio</th></tr>')
        for tag, lab in (("online", "online (raw weights)"), ("ema", "EMA"), ("sf", "schedule-free average")):
            g = lambda m: v.get(f"{tag}/heldout/{m}")   # noqa: E731
            doc += (f'<tr><td>{lab}</td><td>{fmt(g("flow"), 3)}</td><td>{fmt(g("jepa"), 3)}</td>'
                    f'<td>{fmt((g("r_a2p") or 0) * 100 if g("r_a2p") is not None and g("r_a2p") <= 1 else g("r_a2p"), 1)}%</td>'
                    f'<td>{fmt((g("r_p2a") or 0) * 100 if g("r_p2a") is not None and g("r_p2a") <= 1 else g("r_p2a"), 1)}%</td></tr>')
        doc += ('</table><p class="faint">Retrieval chance 0.2%. Held-out presets are synth patches never seen in '
                'training; the real stems below are a harder, different test. Online and EMA are tied on held-out '
                'presets; the schedule-free average is weaker on the flow. Only online and EMA are re-created below.</p>')
    summ = comp.get("summary", {})
    doc += '<h2>Re-creation quality (24 phrases, mean)</h2>'
    if summ:
        doc += ('<table class="t"><tr><th>model</th><th>MSS ↓</th><th>warped MFCC ↓</th><th>envelope cos ↑</th>'
                '<th>best MSS on</th></tr>')
        for k, lab, _ in SETS:
            s = summ.get(k)
            if s:
                doc += (f'<tr><td>{lab}</td><td>{fmt(s["mss"])}</td><td>{fmt(s["wmfcc"])}</td>'
                        f'<td>{fmt(s["env_cos"], 3)}</td><td>{s.get("best_mss_stems", "—")} / {len(rows_by)}</td></tr>')
        doc += ('</table><p class="faint">Metrics follow Hayes et al. (ISMIR 2025): MSS = multi-scale log-mel '
                'distance, warped MFCC = DTW-aligned MFCC distance, envelope cos = similarity of loudness envelopes. '
                'Measured on the whole phrase, refinement saw only the first half.</p>')
    else:
        doc += '<p><i>Pending — the clips are still rendering. This page rebuilds itself when they are done.</i></p>'
    doc += ('<p class="faint">' + " · ".join(f"<b>{lab}</b>: {html.escape(d)}" for _, lab, d in SETS) + '</p>')

    doc += ('<h2>The phrases</h2><table class="t"><tr><th>phrase</th><th>Real</th>'
            + "".join(f"<th>{lab}</th>" for _, lab, _ in SETS) + '</tr>')
    for sid in ids:
        c = catalog.get(sid, {})
        label = html.escape(c.get("name", sid))
        sub = html.escape(" · ".join(x for x in (c.get("style"), f'{c["bpm"]:g} BPM' if c.get("bpm") else None) if x))
        row = rows_by.get(sid, {})
        best = min((k for k, _, _ in SETS if k in row), key=lambda k: row[k]["mss"], default=None)
        doc += f'<tr><td>{label}<br><span class="faint">{sub}</span></td>'
        cell = (lambda f, txt: f'<td class="cell" data-src="synth_inversion/{f}" onclick="play(this)">{txt}</td>'
                if (CLIPS / f).exists() else '<td class="faint">pending</td>')
        doc += cell(f"{sid}_real.m4a", "&#9654; real")
        for k, lab, _ in SETS:
            m = row.get(k)
            txt = "&#9654; " + (f"MSS {m['mss']:.2f}" if m else lab)
            if m and k == best:
                txt = f"<b>{txt}</b>"
            doc += cell(f"{sid}_{k}.m4a", txt) if have[(sid, k)] else '<td class="faint">pending</td>'
        doc += '</tr>'
    doc += '</table>'
    doc += (f'<p class="faint">Status: {n_ready} / {len(ids) * len(SETS)} re-creations rendered'
            + ('' if complete else ' (page rebuilds when the rest are done)') + '. Built '
            + __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M") + '. Model weights are not published.</p>')
    if feedback:
        doc += f'<h2>Listening verdict</h2><p>{html.escape(str(feedback))}</p>'
    doc += be.PLAYER_JS + '</div></body></html>'
    PAGE.write_text(doc)
    print(f"wrote {PAGE} ({n_ready}/{len(ids) * len(SETS)} clips){' COMPLETE' if complete else ''}")


if __name__ == "__main__":
    main()
