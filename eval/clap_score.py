#!/usr/bin/env python3
"""
clap_score.py -- CLAP text<->audio prompt-adherence scorer for the eval stack
(WINTERMUTE 2026-07-22, from Kim's "is stable-audio-metrics useful" call).

THE GAP IT FILLS: clip_metrics.db measures control AUTHORITY (does feature X move),
perceptual QUALITY (Audiobox ce/pq/cu/pc) and DSP -- but NOTHING measures whether a
generated clip actually MATCHES ITS PROMPT. Every model_matrix / eval cell already
carries a prompt_text, so a CLAP cosine(text_emb, audio_emb) is a drop-in
prompt-adherence number. laion_clap is pure torch -> runs on ROCm (or CPU).

WHY THE COSINE MATRIX (not just the matched score): for each sampled clip we score it
against EVERY unique prompt, not only its own. That single matrix yields, for free:
  * matched score      -- cos(audio_i, its own prompt)          -> the metric itself
  * mismatch baseline  -- mean cos(audio_i, all OTHER prompts)  -> is it discriminative?
  * retrieval rank     -- rank of the true prompt among all     -> hard validation
A metric that emits a near-constant (matched ~= mismatched, retrieval at chance) is
useless; this proves adherence is really being measured before we scale to 31k cells.

Run (sat-venv has laion_clap):
  SAO/stable-audio-tools/sat-venv/bin/python eval/clap_score.py \
     --sample 300 --device cpu --out /tmp/clap_proto.csv
Default reads ~/.cache/evals_aac/model_matrix/manifest_live.jsonl + the flat clips there.
--write-db lands a `clap` column in eval/clip_metrics.db for the scored clips.
"""
import argparse
import csv
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")

STAGING = Path.home() / ".cache/evals_aac/model_matrix"
DB = Path("/home/kim/Projects/SAO/eval/clip_metrics.db")


def stratified_sample(entries, n):
    """Even-ish spread across (model, prompt_id, cfg, strength) so the validation isn't
    dominated by one over-rendered model OR one cfg/strength setting (an earlier
    (model,prompt)-only key drew 96% cfg1/w0.6 because that's first in manifest order,
    biasing the degeneration read). Deterministic (index-ordered, no RNG) so reruns match."""
    if n <= 0 or n >= len(entries):
        return entries
    by = {}
    for e in entries:
        key = (e["model"], str(e.get("prompt_id")), str(e.get("cfg")), str(e.get("strength")))
        by.setdefault(key, []).append(e)
    groups = list(by.values())
    out, i = [], 0
    while len(out) < n:
        added = False
        for g in groups:
            if i < len(g):
                out.append(g[i]); added = True
                if len(out) >= n:
                    break
        if not added:
            break
        i += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=STAGING / "manifest_live.jsonl")
    ap.add_argument("--clips-dir", type=Path, default=STAGING)
    ap.add_argument("--sample", type=int, default=300, help="0 = all clips")
    ap.add_argument("--device", default="cpu", help="cpu | cuda")
    ap.add_argument("--music-ckpt", type=Path, default=None,
                    help="path to the music_audioset HTSAT-base checkpoint (manual download); "
                         "omitted => general 630k+audioset non-fusion (HTSAT-tiny, auto-download)")
    ap.add_argument("--out", type=Path, default=Path("/tmp/clap_proto.csv"))
    ap.add_argument("--write-db", action="store_true", help="land a `clap` column in clip_metrics.db")
    ap.add_argument("--include-native", action="store_true",
                    help="also score duration_mode=native cells (long clips) -- off by default")
    ap.add_argument("--append", action="store_true",
                    help="incremental: skip files already in --out and APPEND new rows (for metering "
                         "a fresh LUMI batch without a 48-min full rescan)")
    a = ap.parse_args()

    import numpy as np
    import librosa
    import torch
    # laion_clap parses sys.argv AT IMPORT (its training CLI runs at module scope), so any flag
    # of ours that it doesn't recognise makes the import die with argparse rc=2 -- it prints
    # laion_clap's own usage, which reads like OUR arg is wrong. Hide argv across the import.
    # (Bit a scoped catch-up run 2026-08-05; only shows up when flags are passed, which is why
    # default-arg invocations never tripped it.)
    _argv = sys.argv[:]
    sys.argv = [_argv[0]]
    try:
        import laion_clap
    finally:
        sys.argv = _argv

    entries = [json.loads(l) for l in a.manifest.read_text().splitlines() if l.strip()]
    if not a.include_native:
        entries = [e for e in entries if e.get("duration_mode") != "native"]
    entries = [e for e in entries if (a.clips_dir / e["file"]).exists()]
    already = set()
    if a.append and a.out.exists():
        import csv as _csv
        already = {r["file"] for r in _csv.DictReader(a.out.open())}
        entries = [e for e in entries if e["file"] not in already]
        print(f"[clap] append mode: {len(already)} already scored, {len(entries)} new to score")
    if not entries:
        sys.exit(f"[clap] no clips found under {a.clips_dir} from {a.manifest}")
    entries = stratified_sample(entries, a.sample)
    prompts = sorted({e.get("prompt_text", str(e.get("prompt_id"))) for e in entries})
    pidx = {p: i for i, p in enumerate(prompts)}
    print(f"[clap] {len(entries)} clips, {len(prompts)} unique prompts, device={a.device}")

    amodel = "HTSAT-base" if a.music_ckpt else "HTSAT-tiny"
    model = laion_clap.CLAP_Module(enable_fusion=False, amodel=amodel, device=a.device)
    # torch 2.6+ flipped torch.load(weights_only) to True; the OFFICIAL laion CLAP
    # checkpoint carries a numpy scalar global that the safe-unpickler blocks. The file
    # is the trusted laion release we just downloaded -> load full. Patch only around
    # load_ckpt, then restore, so nothing else in-process is affected.
    _orig_load = torch.load
    torch.load = lambda *aa, **kk: _orig_load(*aa, **{**kk, "weights_only": False})
    # newer transformers dropped the `text_branch.embeddings.position_ids` buffer the
    # checkpoint still carries -> a strict load_state_dict rejects it. Relax to
    # strict=False just for load_ckpt (the missing/unexpected keys are benign buffers).
    _orig_lsd = model.model.load_state_dict
    model.model.load_state_dict = lambda sd, strict=True: _orig_lsd(sd, strict=False)
    try:
        if a.music_ckpt:
            model.load_ckpt(ckpt=str(a.music_ckpt))       # manual music_audioset checkpoint
        else:
            model.load_ckpt(model_id=1)                   # 630k+audioset non-fusion (auto-download)
    finally:
        torch.load = _orig_load
        model.model.load_state_dict = _orig_lsd
    model.eval()

    # laion_clap's API changed under us: the build in SAO/.venv (rebuilt 2026-08-02 for ROCm 7.14)
    # has get_text_embedding(x, tokenizer) with NO use_tensor kwarg, and returns numpy. Older
    # builds took use_tensor=True and returned a torch tensor. Call one way, fall back to the
    # other, and normalise the result -- so this scores identically on either version.
    def _emb(fn, **kw):
        try:
            out = fn(use_tensor=True, **kw)
        except TypeError:
            # This build also wants NUMPY input where the old one took a torch tensor
            # (it calls .astype internally) -- convert on the fallback path too.
            kw = {k: (v.detach().cpu().numpy() if hasattr(v, "detach") else v)
                  for k, v in kw.items()}
            out = fn(**kw)
        if hasattr(out, "detach"):
            out = out.float().cpu().numpy()
        return np.asarray(out, dtype=np.float32)

    def embed_text(txts):
        # laion_clap's text encoder errors on a single-item list (batch-shape bug) --
        # duplicate then slice back when only one prompt (e.g. a native-only batch)
        single = len(txts) == 1
        q = txts + txts if single else txts
        with torch.no_grad():
            e = _emb(model.get_text_embedding, x=q)
        return e[:1] if single else e

    def embed_audio(path):
        wav, _ = librosa.load(str(path), sr=48000, mono=True)
        with torch.no_grad():
            t = torch.from_numpy(wav).float().unsqueeze(0)
            return _emb(model.get_audio_embedding_from_data, x=t)[0]

    # FAR controls: deliberately out-of-genre prompts. The in-set prompts are all
    # near-synonym electronic-music descriptions (they cluster in CLAP text-space), so
    # intra-set retrieval is hard BY CONSTRUCTION and a low intra-set margin is not a
    # failure. The real question is whether a clip's true prompt beats a SEMANTICALLY
    # DISTANT prompt -- that is what proves CLAP is measuring adherence, not emitting a
    # near-constant. matched-vs-far margin is the headline validation number.
    FAR = ["a solo classical violin recital", "a spoken-word podcast, two people talking",
           "gentle acoustic fingerstyle guitar", "heavy death metal with screamed vocals",
           "ambient field recording of ocean waves"]
    temb = embed_text(prompts)                    # (P, D)
    temb /= (np.linalg.norm(temb, axis=1, keepdims=True) + 1e-8)
    femb = embed_text(FAR)                         # (F, D)
    femb /= (np.linalg.norm(femb, axis=1, keepdims=True) + 1e-8)

    rows, matched, mism, far, ranks, beats_far = [], [], [], [], [], []
    for n, e in enumerate(entries):
        try:
            aemb = embed_audio(a.clips_dir / e["file"])
        except Exception as ex:
            print(f"[clap] skip {e['file']}: {ex}")
            continue
        aemb /= (np.linalg.norm(aemb) + 1e-8)
        sims = temb @ aemb                        # (P,) cosine vs every in-set prompt
        fsims = femb @ aemb                       # (F,) cosine vs the far controls
        pt = e.get("prompt_text", str(e.get("prompt_id")))
        j = pidx[pt]
        s_match = float(sims[j])
        s_other = float((sims.sum() - sims[j]) / (len(prompts) - 1)) if len(prompts) > 1 else float("nan")
        s_far = float(fsims.mean())
        rank = int((sims > sims[j]).sum()) + 1    # 1 = true prompt is the best in-set match
        bf = bool(s_match > fsims.max())          # true prompt beats EVERY far control
        rows.append({"file": e["file"], "model": e["model"], "ckpt": e.get("ckpt"),
                     "prompt_id": e.get("prompt_id"), "cfg": e.get("cfg"), "strength": e.get("strength"),
                     "clap_matched": round(s_match, 4), "clap_mismatch_mean": round(s_other, 4),
                     "clap_far_mean": round(s_far, 4), "clap_margin_far": round(s_match - s_far, 4),
                     "retrieval_rank": rank, "beats_all_far": int(bf)})
        matched.append(s_match); mism.append(s_other); far.append(s_far)
        ranks.append(rank); beats_far.append(bf)
        if (n + 1) % 25 == 0:
            print(f"[clap] {n+1}/{len(entries)}  running matched={np.mean(matched):.3f} margin_far={np.mean(matched)-np.mean(far):.3f}")

    if not rows:
        print("[clap] nothing new to score.")
        return
    append = a.append and a.out.exists()
    with a.out.open("a" if append else "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if not append:
            w.writeheader()
        w.writerows(rows)
    print(f"[clap] {'appended' if append else 'wrote'} {len(rows)} rows -> {a.out}")

    matched, mism, far, ranks, beats_far = map(np.array, (matched, mism, far, ranks, beats_far))
    top1 = float((ranks == 1).mean()); top3 = float((ranks <= 3).mean())
    chance = 1.0 / len(prompts)
    print("\n=== CLAP prototype summary ===")
    print(f"clips scored             : {len(matched)}")
    print(f"matched  cos (mean±sd)   : {matched.mean():.3f} ± {matched.std():.3f}")
    print(f"in-set mismatch (mean)   : {mism.mean():.3f}   (near-synonym prompts -> expected close)")
    print(f"FAR-control cos (mean)   : {far.mean():.3f}   (out-of-genre prompts)")
    print(f"MARGIN vs far (headline) : {(matched-far).mean():.3f}   (>0 => CLAP tracks adherence)")
    print(f"true prompt beats ALL far: {beats_far.mean():.1%}   (adherence hit-rate)")
    print(f"in-set retrieval t1 / t3 : {top1:.1%} / {top3:.1%}   (chance t1 = {chance:.1%}; hard: prompts cluster)")
    print(f"csv                      : {a.out}")

    if a.write_db and DB.exists():
        import sqlite3
        con = sqlite3.connect(DB)
        cols = [r[1] for r in con.execute("PRAGMA table_info(metrics)")]
        if "clap" not in cols:
            con.execute("ALTER TABLE metrics ADD COLUMN clap REAL")
        wrote = 0
        for r in rows:
            # clip_metrics paths are absolute '.../model_matrix/<file>'; match on the LIKE tail
            cur = con.execute("UPDATE metrics SET clap=? WHERE path LIKE ?",
                              (r["clap_matched"], f"%/model_matrix/{r['file']}"))
            wrote += cur.rowcount
        con.commit(); con.close()
        print(f"db                     : wrote clap for {wrote}/{len(rows)} rows in {DB.name}")


if __name__ == "__main__":
    main()
