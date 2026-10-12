#!/usr/bin/env python
# Owner: GHOST-NOTE (created 2026-10-12)
"""make_v7_presets.py — one GUI preset per variant of a v7 stem-transition run (render_v7_smoketest.py), in its own FOLDER.

WHY (project guidance 2026-10-12): the owner wants to tweak the transition variants in the inference GUI. A preset is a /generate
payload (eval/presets.py), so what it can carry is the GENERATION RECIPE of the variant's generated part: prompt, duration of one
transition window, steps, cfg, and the DoRA that rendered it. It CANNOT carry the offline stem pipeline (tempo lock, bass hand-over,
drum crossfade/inpaint masks, assembly); that lives in eval/render_v7_smoketest.py and each preset's notes carry the exact
variant tag and the command to rebuild it. Folders: names are 'folder/variant' (presets.py rel_path).

USAGE  .venv/bin/python eval/make_v7_presets.py --run-meta <dir>/run_meta.json --folder v7-smoke-4clips
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import presets  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-meta", required=True)
    ap.add_argument("--folder", required=True)
    ap.add_argument("--dir", default=None, help="preset dir (default: the repo's eval/presets)")
    a = ap.parse_args()
    m = json.loads(Path(a.run_meta).read_text())
    ar, tr = m["args"], m["transitions"]
    dur = round(tr[0]["L"] / 44100.0, 2)
    tags = ["skipped"] + sorted({o["other_path"] for r in tr for o in r.get("outputs", []) if o.get("other_path") not in (None, "FAILED", "skipped")})
    n_clips = len(tr) + 1
    for tag in dict.fromkeys(tags):
        gen_other = "o-inpaint" in tag or "o-slerp" in tag
        drum_inp = tag.startswith("d-inpaint")
        prompt = ar["a2a_prompt"] if (gen_other or not drum_inp) else ar["drum_prompt"]
        cfg = ar["other_cfg"] if "o-inpaint" in tag else (ar["drum_cfg"] if drum_inp else ar["cfg_scale"])
        payload = {"prompt": prompt, "duration": dur, "steps": ar["steps"], "cfg_scale": cfg,
                   "dora": {"ckpt_path": ar["ckpt_b"], "strength": 1.0}}
        notes = (f"v7 transition variant '{tag}' ({n_clips} clips, {len(tr)} transitions, window {dur} s = {ar['w_bars']} bars). "
                 f"Recipe of the GENERATED part only: prompt/cfg/steps/DoRA as rendered. The offline stem pipeline (tempo lock via bungee, "
                 f"kick-phase alignment, LR4 bass hand-over, drum crossfade or masked drum inpaint, other-stem slerp/inpaint, sample-exact assembly) "
                 f"is NOT a GUI knob: rebuild with eval/render_v7_smoketest.py "
                 f"--drum-inpaint-bars {' '.join(map(str, ar.get('drum_inpaint_bars', [])))} --other-inpaint-bars {' '.join(map(str, ar.get('other_inpaint_bars', [])))}"
                 f"{' --other-slerp' if ar.get('other_slerp') else ''}. Source run: {Path(a.run_meta).parent.name}. Drum prompt: {ar['drum_prompt']!r}; other prompt: {ar['a2a_prompt']!r}.")
        p = presets.save(f"{a.folder}/{tag}", payload, notes=notes, dir=a.dir)
        print("wrote", p)


if __name__ == "__main__":
    main()
