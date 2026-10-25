#!/usr/bin/env python3
# Owner: WINTERMUTE (created 2026-10-25)
"""granite_local_pass.py -- the LUMI Granite caption-revision pass (lumi/goa_granite_task.py) run locally on a GGUF model.

Same prompt, genre hint, XML-tag contract and output schema as goa_granite_task.py (imported from it, so the two cannot
drift): per Music Flamingo caption json, N sampled revisions pooled into short_genremood / short_technical / short_mood
variant lists plus one medium_review. The model is a llama.cpp GGUF (default: mir's granite-4.0-h-tiny Q8_0) instead of
granite-3.3-8b-instruct via transformers, so it runs on this box without LUMI, on the CPU by default.

First use (2026-10-25): the 1,148 Flamingo captions of the four ai-music sets (Chill Dataset, organic dance, Prog &
Psytechno, Progressive Trance & Melodic Techno) in Kosmos/captions/aimusic_captions, which had Flamingo but no Granite.
Resumable: skips captions whose output json exists.

  mir/mir/bin/python eval/granite_local_pass.py --captions /run/media/kim/Kosmos/captions/aimusic_captions/json \
      --sets "Chill Dataset" "organic dance" --out /run/media/kim/Kosmos/captions/aimusic_captions/granite --limit 10
"""
import argparse
import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lumi"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
from goa_granite_task import REVISIONS, SHORT_TAGS, SYS, build_user, genre_hint, parse, read_mf  # noqa: E402

GGUF = "/home/kim/Projects/mir/models/LMM/granite-4.0-h-tiny-GGUF/granite-4.0-h-tiny-Q8_0.gguf"


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
        msgs = [{"role": "system", "content": SYS}, {"role": "user", "content": build_user(mf, genre_hint(d))}]
        pool = {k: [] for k in REVISIONS}
        for _ in range(a.n_samples):
            llm.reset()  # Granite-4 hybrid: reusing the cache across calls fails with llama_decode -1 (as in mir granite_revision.py)
            r = llm.create_chat_completion(messages=msgs, max_tokens=256, temperature=a.temperature, top_p=0.95)
            for k, v in parse(r["choices"][0]["message"]["content"]).items():
                if v not in pool[k]:
                    pool[k].append(v)
        rec = {k: pool[k] for k in SHORT_TAGS}
        rec["medium_review"] = pool["medium_review"][0] if pool["medium_review"] else None
        rec["_source"] = {"rel": d.get("rel"), "genre_hint": genre_hint(d), "model": os.path.basename(a.model),
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
