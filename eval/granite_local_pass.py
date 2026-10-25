#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-25)
# Last edited: WINTERMUTE 2026-10-25 -- per-set fallback genre hint + measured tempo from the track's .BEATS_GRID in the prompt
"""granite_local_pass.py -- the LUMI Granite caption-revision pass (lumi/goa_granite_task.py) run locally on a GGUF model.

Same prompt, genre hint, XML-tag contract and output schema as goa_granite_task.py (imported from it, so the two cannot
drift): per Music Flamingo caption json, N sampled revisions pooled into short_genremood / short_technical / short_mood
variant lists plus one medium_review. The model is a llama.cpp GGUF (default: granite-3.3-8b-instruct Q8_0, the LUMI
model quantised; granite-4.0-h-tiny ignored the genre hint on mislabelled captions) instead of transformers, so it runs on
this box without LUMI. CPU by default; --gpu-layers -1 puts the whole model on the GPU (take the GPU lock).

First use (2026-10-25): the 1,148 Flamingo captions of the four ai-music sets (Chill Dataset, organic dance, Prog &
Psytechno, Progressive Trance & Melodic Techno) in Kosmos/captions/aimusic_captions, which had Flamingo but no Granite.
Resumable: skips captions whose output json exists.

Two additions over the LUMI task, from a 10-caption trial on granite-4.0-h-tiny (2026-10-25):
  - captions with no genre_hint get SET_HINTS[<set folder>] instead of the goa default (which would mislabel chill);
  - with --tracks-root, the prompt carries the tempo measured from the track's .BEATS_GRID (mean beat interval, the
    mixtape_madmom_bpm_v2.py method), because the model otherwise copies Flamingo's guessed BPM. Tracks whose beat
    grid is unsteady (beat-interval MAD > 5%, or < 8 beats) get no tempo line rather than a wrong one.

  mir/mir/bin/python eval/granite_local_pass.py --captions /run/media/kim/Kosmos/captions/aimusic_captions/json \
      --sets "Chill Dataset" "organic dance" --out /run/media/kim/Kosmos/captions/aimusic_captions/granite --limit 10
"""
import argparse
import glob
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
from goa_granite_task import REVISIONS, SHORT_TAGS, SYS, build_user, genre_hint, parse, read_mf  # noqa: E402

GGUF = "/home/kim/Projects/mir/models/LMM/granite-3.3-8b-instruct-GGUF/granite-3.3-8b-instruct-Q8_0.gguf"

# fallback for captions without their own genre_hint (17 Prog & Psytechno, 14 Chill, 2 Prog Trance of 1,148)
SET_HINTS = {
    "Chill Dataset": "ambient / downtempo / psychill (NOT techno, trance or hardstyle)",
    "organic dance": "organic house / downtempo",
    "Prog & Psytechno Dataset": "progressive psytrance / psytechno",
    "Progressive Trance & Melodic Techno": "progressive trance / melodic techno / progressive house",
}


def track_dir(rel, root):
    """<root>/<set>/<track>/ for both caption kinds: '<set>/<track>.flac' and '<set>/<track>/full_mix.flac'."""
    top, rest = rel.split("/", 1)
    name = os.path.dirname(rest) if os.path.basename(rest).startswith("full_mix.") else os.path.splitext(rest)[0]
    return os.path.join(root, top, name)


def grid_bpm(tdir):
    """Tempo from the track's .BEATS_GRID: mean beat interval after dropping intervals >20% off the median."""
    g = glob.glob(os.path.join(glob.escape(tdir), "*.BEATS_GRID"))
    if not g:
        return None
    b = np.loadtxt(g[0], ndmin=1)
    if len(b) < 8:
        return None
    iv = np.diff(b)
    med = np.median(iv)
    if np.median(np.abs(iv - med)) / med > 0.05:
        return None
    return 60.0 / float(np.mean(iv[np.abs(iv - med) < 0.2 * med]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--captions", required=True, help="dir of Music Flamingo caption json")
    ap.add_argument("--sets", nargs="*", default=None, help="only captions whose rel starts with one of these folder names")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=GGUF)
    ap.add_argument("--n-samples", type=int, default=3)
    ap.add_argument("--temperature", type=float, default=0.85)
    ap.add_argument("--threads", type=int, default=12)
    ap.add_argument("--gpu-layers", type=int, default=0)
    ap.add_argument("--tracks-root", default=None, help="analysed track folders (<root>/<set>/<track>/*.BEATS_GRID)")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    paths = []
    for p in sorted(glob.glob(os.path.join(a.captions, "*.json"))):
        if a.sets:
            rel = json.load(open(p)).get("rel", "")
            if rel.split("/")[0] not in a.sets:
                continue
        paths.append(p)
    if a.limit:
        paths = paths[:a.limit]
    todo = [p for p in paths if not os.path.exists(os.path.join(a.out, os.path.basename(p)))]
    print(f"[granite-local] {len(todo)}/{len(paths)} to do; model={os.path.basename(a.model)} n_samples={a.n_samples}",
          flush=True)

    from llama_cpp import Llama
    llm = Llama(model_path=a.model, n_ctx=4096, n_threads=a.threads, n_gpu_layers=a.gpu_layers, verbose=False)
    t0 = time.time()
    for i, p in enumerate(todo, 1):
        d = json.load(open(p))
        mf = read_mf(d)
        if not mf:
            print(f"[granite-local] {os.path.basename(p)}: no caption text", flush=True)
            continue
        hint = genre_hint(d, SET_HINTS.get(d.get("rel", "").split("/")[0]) if not d.get("genre_hint") else None)
        bpm = grid_bpm(track_dir(d["rel"], a.tracks_root)) if a.tracks_root else None
        user = build_user(mf, hint)
        if bpm:
            user += (f"\n\nMeasured tempo: {bpm:.0f} BPM. Use this tempo; ignore any other BPM in the source "
                     f"description.")
        msgs = [{"role": "system", "content": SYS}, {"role": "user", "content": user}]
        pool = {k: [] for k in REVISIONS}
        for _ in range(a.n_samples):
            llm.reset()  # Granite-4 hybrid: reusing the cache across calls fails with llama_decode -1 (as in mir granite_revision.py)
            r = llm.create_chat_completion(messages=msgs, max_tokens=256, temperature=a.temperature, top_p=0.95)
            for k, v in parse(r["choices"][0]["message"]["content"]).items():
                if v not in pool[k]:
                    pool[k].append(v)
        rec = {k: pool[k] for k in SHORT_TAGS}
        rec["medium_review"] = pool["medium_review"][0] if pool["medium_review"] else None
        rec["_source"] = {"rel": d.get("rel"), "genre_hint": hint, "bpm_grid": round(bpm, 1) if bpm else None, "model": os.path.basename(a.model),
                          "script": "eval/granite_local_pass.py"}
        tmp = os.path.join(a.out, os.path.basename(p) + ".tmp")
        with open(tmp, "w") as f:
            json.dump(rec, f, ensure_ascii=False)
        os.replace(tmp, os.path.join(a.out, os.path.basename(p)))
        if i % 25 == 0 or i == len(todo):
            el = time.time() - t0
            print(f"[granite-local] {i}/{len(todo)}  ({el / i:.1f} s each, eta {el / i * (len(todo) - i) / 60:.0f} min)",
                  flush=True)
    print("[granite-local] done", flush=True)


if __name__ == "__main__":
    sys.exit(main())
