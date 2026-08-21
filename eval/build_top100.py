#!/usr/bin/env python3
"""build_top100.py — select the top-100 clips per frame-length class by PQ ALONE, with MERT-cosine
near-duplicate disqualification, and emit the data file the page builder renders.

WHY PQ ALONE (W, 2026-08-21, fitted on Kim's 668 real A/B votes): PQ alone predicts Kim's preference
at 77.6 %; every added feature made it worse. So the ranking here is PQ, full stop.
WHY DEDUP (Kim direct, 2026-08-21): the raw top of the board is the same model+prompt+seed at three
guidance weights — "almost similar versions of higher scoring tracks" must be disqualified, keeping
only the highest-PQ member. Similarity = MERT embeddings (the working MERT-sim machinery:
MERT-v1-330M, mid layers 3-6 = rhythm space, layer 23 = melody space, per mert_selector.py), cosine
on the concatenated (mid ‖ upper) time-mean embedding. Greedy: walk candidates in PQ-descending
order, keep a clip iff max cosine to every already-kept clip is below the threshold.
THRESHOLD is CALIBRATED, not guessed: clips sharing (model, prompt, seed) — guidance-weight/cfg
siblings — are known near-duplicates; different prompts on different models are known non-duplicates.
The threshold is placed between those two measured distributions and reported.

STAGES (each resumable, state under --work):
  candidates  DB query -> per-class PQ-top pool (file-existence checked)  -> candidates.json
  embed       MERT embeddings (mir venv; CPU-safe, GPU if free)           -> emb.npy (aligned)
  select      calibrate threshold + greedy dedup -> top100.json (the page builder's input)
Run:  mir/bin/python eval/build_top100.py --stage candidates|embed|select   (in order)
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import time

DB = "/home/kim/Projects/SAO/eval/clip_metrics.db"
# frame-length classes: (label, seconds_lo, seconds_hi, candidate_pool)
CLASSES = [
    ("T256_20s", 17, 32, 450),      # 20 s grid + 23.79 s cells; big pool -> survives dedup to 100
    ("T512_47s", 40, 60, 400),
    ("T1024_95s", 80, 120, 400),    # tiny population today; takes what exists
    ("T2048_190s", 160, 240, 400),
    ("T4096_380s", 330, 420, 400),
]


def stem_key(path):
    """(model, epoch, prompt, seed) — the SAME TAKE up to sampler knobs (cfg / guidance weight).
    Used for the HARD name-level dedup (knob variants of one take collapse to its best-PQ member)
    and for threshold calibration (knob-sibling pairs are certain near-duplicates)."""
    b = os.path.basename(path)
    b = re.sub(r"\.(m4a|wav|flac|mp3)$", "", b)
    parts = b.split("__")
    if len(parts) >= 5:
        model = parts[0]
        ep = next((x for x in parts[1:3] if x.startswith("ep")), "")
        prompt = "__".join(p for p in parts[2:-1] if not (p.startswith(("w", "cfg", "ep")) and p[-1].isdigit()))
        seed = parts[-1]
        return model, ep, prompt, seed
    return b, "", "", ""


def stage_candidates(a):
    c = sqlite3.connect(DB)
    out = {}
    for label, lo, hi, pool in CLASSES:
        rows = c.execute(
            "SELECT path, pq, dur, ce, crest, flatness FROM metrics "
            "WHERE pq IS NOT NULL AND dur BETWEEN ? AND ? ORDER BY pq DESC", (lo, hi)).fetchall()
        kept, missing = [], 0
        for p, pq, dur, ce, crest, flat in rows:
            if len(kept) >= pool:
                break
            if not os.path.exists(p):
                missing += 1
                continue
            kept.append({"path": p, "pq": pq, "dur": dur, "ce": ce, "crest": crest, "flatness": flat})
        out[label] = kept
        print(f"[cand] {label}: population {len(rows)}, pool {len(kept)} (missing files skipped: {missing})")
    json.dump(out, open(os.path.join(a.work, "candidates.json"), "w"))
    print(f"-> {a.work}/candidates.json")


def stage_embed(a):
    import numpy as np
    import torch
    torch.set_num_threads(a.threads)
    sys.path.insert(0, "/home/kim/Projects/SAO/control")
    from sa3_control.mert_selector import MERT_ID, MERT_SR   # constants only; embed inline
    import torchaudio  # mir venv has working torchaudio/ffmpeg wrapper
    from transformers import AutoModel, Wav2Vec2FeatureExtractor
    dev = "cuda" if (a.gpu and torch.cuda.is_available()) else "cpu"
    print(f"[embed] MERT {MERT_ID} on {dev}, {a.threads} threads")
    model = AutoModel.from_pretrained(MERT_ID, trust_remote_code=True).to(dev).eval()
    fe = Wav2Vec2FeatureExtractor.from_pretrained(MERT_ID, trust_remote_code=True)

    cands = json.load(open(os.path.join(a.work, "candidates.json")))
    items = [(lbl, i, e["path"]) for lbl, es in cands.items() for i, e in enumerate(es)]
    embp = os.path.join(a.work, "emb.npy")
    donep = os.path.join(a.work, "emb_done.json")
    done = json.load(open(donep)) if os.path.exists(donep) else {}
    E = None
    if os.path.exists(embp):
        E = np.load(embp)
    t0 = time.time()
    for n, (lbl, i, path) in enumerate(items):
        key = f"{lbl}:{i}"
        if key in done:
            continue
        try:
            wav, sr = torchaudio.load(path)
            wav = wav.mean(0, keepdim=True)
            if sr != MERT_SR:
                wav = torchaudio.functional.resample(wav, sr, MERT_SR)
            # centre 30 s window — enough for identity, keeps long classes cheap
            T = wav.shape[1]
            span = 30 * MERT_SR
            if T > span:
                s0 = (T - span) // 2
                wav = wav[:, s0:s0 + span]
            with torch.no_grad():
                inp = fe(wav.squeeze(0).numpy(), sampling_rate=MERT_SR, return_tensors="pt").to(dev)
                hs = model(**inp, output_hidden_states=True).hidden_states
                mid = torch.stack([hs[l] for l in (3, 4, 5, 6)]).mean(0).mean(1)   # rhythm space
                up = hs[23].mean(1)                                                 # melody space
                v = torch.cat([mid, up], dim=-1).squeeze(0).float().cpu().numpy()
                v /= (np.linalg.norm(v) + 1e-9)
        except Exception as ex:
            print(f"[embed] FAIL {path}: {type(ex).__name__} {str(ex)[:80]}")
            v = None
        if E is None and v is not None:
            E = np.zeros((len(items), v.shape[0]), dtype=np.float32)
        if v is not None:
            E[n] = v
        done[key] = (v is not None)
        if (len(done)) % 25 == 0:
            np.save(embp, E); json.dump(done, open(donep, "w"))
            r = (time.time() - t0) / max(1, len([k for k in done if k not in ()]))
            print(f"[embed] {len(done)}/{len(items)}  ({time.time()-t0:.0f}s)", flush=True)
    np.save(embp, E); json.dump(done, open(donep, "w"))
    json.dump([f"{l}:{i}" for l, i, _ in items], open(os.path.join(a.work, "emb_index.json"), "w"))
    print(f"[embed] done {len(done)}/{len(items)} -> {embp}")


def stage_select(a):
    import numpy as np
    cands = json.load(open(os.path.join(a.work, "candidates.json")))
    E = np.load(os.path.join(a.work, "emb.npy"))
    idx = json.load(open(os.path.join(a.work, "emb_index.json")))
    done = json.load(open(os.path.join(a.work, "emb_done.json")))
    row = {k: n for n, k in enumerate(idx)}

    # ---- calibrate: same (model,prompt,seed) = known dupes; cross-model+prompt = known distinct
    import random
    rng = random.Random(0)
    dup_sims, dist_sims = [], []
    for lbl, es in cands.items():
        groups = {}
        for i, e in enumerate(es):
            k = f"{lbl}:{i}"
            if not done.get(k):
                continue
            groups.setdefault(stem_key(e["path"]), []).append(row[k])
        gs = [g for g in groups.values() if len(g) > 1]
        for g in gs[:200]:
            for x in range(len(g) - 1):
                dup_sims.append(float(E[g[x]] @ E[g[x + 1]]))
        keys = list(groups.keys())
        for _ in range(min(400, len(keys))):
            k1, k2 = rng.sample(keys, 2)
            if k1[0] != k2[0] and k1[1] != k2[1]:
                dist_sims.append(float(E[groups[k1][0]] @ E[groups[k2][0]]))
    if dup_sims and dist_sims:
        dup_med = float(np.median(dup_sims)); dup_p10 = float(np.percentile(dup_sims, 10))
        dist_p95 = float(np.percentile(dist_sims, 95))
        # In a homogeneous corpus the two distributions overlap near 1.0 (MERT cosine saturates),
        # so the threshold is CAPPED — the hard name-dedup and the family cap carry most of the work.
        thr = a.threshold if a.threshold else min(0.993, max(dist_p95 + 0.005, dup_p10))
        print(f"[cal] dupes med {dup_med:.4f} p10 {dup_p10:.4f} | distinct p95 {dist_p95:.4f} -> threshold {thr:.4f}")
    else:
        thr = a.threshold or 0.97
        print(f"[cal] insufficient calibration pairs; threshold {thr}")

    out = {"threshold": thr, "generated": time.strftime("%Y-%m-%d %H:%M"),
           "hard_dedup": "one clip per (model, epoch, prompt, seed) knob-group + max 3 per (model, prompt, seed) take-family (epochs are versions too), BEFORE the MERT pass",
           "ranking": "PQ alone (W 2026-08-21: best single proxy of Kim's preference, 77.6% on 668 A/B votes)",
           "dedup": "MERT-v1-330M (mid 3-6 + layer 23), cosine, greedy from top PQ", "classes": {}}
    for lbl, es in cands.items():
        kept, dropped = [], 0
        kept_rows = []
        seen_takes = set()
        fam_count = {}
        for i, e in enumerate(es):
            k = f"{lbl}:{i}"
            if not done.get(k):
                continue
            take = stem_key(e["path"])
            if take in seen_takes:            # knob variant of an already-kept take: hard-disqualified
                dropped += 1
                continue
            fam = (take[0], take[2], take[3])  # model+prompt+seed, ANY epoch = one take family
            if fam_count.get(fam, 0) >= 3:     # cap: epochs of one take are versions too
                dropped += 1
                continue
            v = E[row[k]]
            if kept_rows and float(np.max(np.stack(kept_rows) @ v)) >= thr:
                dropped += 1
                continue
            kept_rows.append(v)
            seen_takes.add(take)
            fam_count[fam] = fam_count.get(fam, 0) + 1
            e2 = dict(e); e2["rank"] = len(kept) + 1
            kept.append(e2)
            if len(kept) >= 100:
                break
        out["classes"][lbl] = {"clips": kept, "near_dup_disqualified": dropped,
                               "pool_scanned": min(len(es), (kept[-1]["rank"] if kept else 0) + dropped)}
        print(f"[select] {lbl}: kept {len(kept)}, disqualified {dropped} near-dups")
    json.dump(out, open(os.path.join(a.work, "top100.json"), "w"), indent=1)
    print(f"-> {a.work}/top100.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=("candidates", "embed", "select"))
    ap.add_argument("--work", default="/home/kim/Projects/SAO/eval/top100_work")
    ap.add_argument("--threads", type=int, default=12)
    ap.add_argument("--gpu", action="store_true")
    ap.add_argument("--threshold", type=float, default=None, help="override calibrated dup threshold")
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    {"candidates": stage_candidates, "embed": stage_embed, "select": stage_select}[a.stage](a)


if __name__ == "__main__":
    main()
