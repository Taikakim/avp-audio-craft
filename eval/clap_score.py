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
    """Even-ish spread across (model, prompt_id) so the validation isn't dominated by
    one over-rendered model. Deterministic (index-ordered, no RNG) so reruns match."""
    if n <= 0 or n >= len(entries):
        return entries
    by = {}
    for e in entries:
        by.setdefault((e["model"], str(e.get("prompt_id"))), []).append(e)
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
    a = ap.parse_args()

    import numpy as np
    import librosa
    import torch
    import laion_clap

    entries = [json.loads(l) for l in a.manifest.read_text().splitlines() if l.strip()]
    entries = [e for e in entries if e.get("duration_mode") != "native"]  # natives quarantined
    entries = [e for e in entries if (a.clips_dir / e["file"]).exists()]
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

    def embed_text(txts):
        with torch.no_grad():
            return model.get_text_embedding(txts, use_tensor=True).float().cpu().numpy()

    def embed_audio(path):
        wav, _ = librosa.load(str(path), sr=48000, mono=True)
        with torch.no_grad():
            t = torch.from_numpy(wav).float().unsqueeze(0)
            return model.get_audio_embedding_from_data(x=t, use_tensor=True).float().cpu().numpy()[0]

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

    with a.out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

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
