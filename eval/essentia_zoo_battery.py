#!/usr/bin/env python
# Owner: GHOST-NOTE (created 2026-10-14)
"""essentia_zoo_battery.py -- run (almost) the whole Essentia model zoo on a handful of clips and keep every output. MIR venv, CPU, JSON out only.

WHY (Kim 2026-10-14): "run everything in mir/models/essentia-zoo ... the first result we have which could help with sometimes underwhelming performance of my
finetunes (overgrown gradients, a trainer that squashed punch)". The point is to find WHICH descriptor moves when a render goes from underwhelming to better,
so every model's output is stored per clip and a separate step ranks the descriptors.

Families (driven by each model's own .json metadata, as in eval/essentia_heads.py -- nothing is hard-coded per model):
  classifiers          end-to-end MusiCNN / VGGish classifiers (mood_*, danceability, genre_*, voice/instrumental, tonal, ...)       -> class probabilities
  heads                TensorflowPredict2D heads on effnet-discogs / musicnn / vggish / yamnet embeddings (280 json; OpenL3-backbone ones skipped: no Essentia extractor)
  autotag / events     MSD+MTT MusiCNN tags, FSD-SINet (200 sound-event classes), YAMNet (521)
  maest                MAEST genre_discogs400/519 predictions (all window/size variants)
  tempo                TempoCNN -> global BPM (+ the mean of the local-BPM track)
  pitch                CREPE (every size) -> confident fraction, median f0, f0 percentiles
  embeddings           pooled backbone embeddings per clip (effnet, musicnn, vggish, yamnet, maest) so embedding DISTANCES can be computed afterwards
SKIPPED ON PURPOSE: legacy/ (older copies of classifiers/ + autotagging/), source-separation/ (not a score), OpenL3 heads.
Every model that fails is recorded with its error in out["_failures"] -- a silent gap would read as 'did not move'.

RUN: /home/kim/Projects/mir/mir/bin/python eval/essentia_zoo_battery.py --clips clips.json --out zoo.json [--families classifiers,heads,...] [--seconds 45]
     clips.json = {"name": "/path/clip.wav", ...}
"""
import argparse
import json
import subprocess
import sys
import time
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
ZOO = Path("/home/kim/Projects/mir/models/essentia-zoo")


def decode(path, seconds, sr, offset=0.0):
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-nostdin", "-ss", str(offset), "-i", str(path), "-t", str(seconds), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, timeout=300).stdout
    a = np.frombuffer(raw, dtype=np.float32).copy()
    if a.size < sr * 2:
        raise RuntimeError("decode failed")
    return a


class Audio:
    def __init__(self, clips, seconds, offset=0.0):
        self.clips, self.seconds, self.offset, self.cache = clips, seconds, offset, {}

    def get(self, name, sr):
        k = (name, sr)
        if k not in self.cache:
            self.cache[k] = decode(self.clips[name], self.seconds, sr, self.offset)
        return self.cache[k]


def meta(j):
    m = json.load(open(j))
    s = m.get("schema", {})
    ins, outs = s.get("inputs", []), s.get("outputs", [])
    pred = next((o for o in outs if o.get("output_purpose") == "predictions"), outs[0] if outs else None)
    emb = next((o for o in outs if o.get("output_purpose") == "embeddings"), None)
    return m, (ins[0]["name"] if ins else None), (pred["name"] if pred else None), (emb["name"] if emb else None)


def mean_rows(x):
    x = np.asarray(x)
    return x.reshape(-1, x.shape[-1]).mean(0) if x.ndim > 1 else x      # MAEST returns (patches,1,1,C)


def find_pb(name):
    for p in ZOO.glob("**/" + name + ".pb"):
        if not str(p.relative_to(ZOO)).startswith("legacy"):
            return p
    return None


def run(args):
    import essentia.standard as es
    clips = json.load(open(args.clips))
    A = Audio(clips, args.seconds, args.offset)
    fam = set(args.families.split(","))
    out = {n: {} for n in clips}
    fails = {}
    emb_store = {n: {} for n in clips}

    def put(name, key, vals):
        out[name][key] = vals

    def fail(key, e):
        fails[key] = str(e)[:160]
        print("  FAIL", key, str(e)[:100], flush=True)

    t0 = time.time()
    # ---- end-to-end classifiers + autotagging + events (single model per json)
    if fam & {"classifiers", "autotag", "events"}:
        jobs = []
        if "classifiers" in fam: jobs += sorted(ZOO.glob("classifiers/**/*.json"))
        if "autotag" in fam: jobs += sorted(ZOO.glob("autotagging/**/*.json"))
        if "events" in fam: jobs += sorted(ZOO.glob("audio-event-recognition/**/*.json"))
        for j in jobs:
            pb = j.with_suffix(".pb")
            if not pb.exists() or "tfjs" in str(j) or args.only not in str(j): continue
            try:
                m, inn, pr, _ = meta(j)
                alg = m["inference"]["algorithm"]; sr = m["inference"].get("sample_rate", 16000)
                cls = m.get("classes") or [f"o{i}" for i in range(9999)]
                if alg == "TensorflowPredictMusiCNN": A_ = es.TensorflowPredictMusiCNN(graphFilename=str(pb), input=inn, output=pr)
                elif alg == "TensorflowPredictVGGish": A_ = es.TensorflowPredictVGGish(graphFilename=str(pb), input=inn, output=pr)
                elif alg == "TensorflowPredictFSDSINet": A_ = es.TensorflowPredictFSDSINet(graphFilename=str(pb), input=inn, output=pr)
                else: raise RuntimeError("unhandled alg " + str(alg))
                for n in clips:
                    v = mean_rows(A_(A.get(n, sr)))
                    for c, x in zip(cls, v): put(n, f"{j.relative_to(ZOO).parent}/{j.stem}::{c}", float(x))
            except Exception as e:
                fail(str(j.relative_to(ZOO)), e)
        print(f"classifiers/autotag/events done {time.time()-t0:.0f}s", flush=True)

    # ---- heads on shared backbone embeddings
    if "heads" in fam:
        bb = {}                                              # model_name -> {clip: (patches,dim)}

        def backbone(name_):
            if name_ in bb: return bb[name_]
            pb = find_pb(name_)
            if pb is None: raise RuntimeError("backbone not found " + name_)
            mm, inn, pr, em = meta(pb.with_suffix(".json"))
            alg = mm["inference"]["algorithm"]; sr = mm["inference"].get("sample_rate", 16000)
            if alg == "TensorflowPredictEffnetDiscogs": X = es.TensorflowPredictEffnetDiscogs(graphFilename=str(pb), output=em or "PartitionedCall:1")
            elif alg == "TensorflowPredictMusiCNN": X = es.TensorflowPredictMusiCNN(graphFilename=str(pb), output=em or "model/dense/BiasAdd")
            elif alg == "TensorflowPredictVGGish": X = es.TensorflowPredictVGGish(graphFilename=str(pb), output=em or "model/vggish/embeddings", **({"input": inn} if "yamnet" in name_ else {}))
            else: raise RuntimeError("backbone alg " + str(alg))
            bb[name_] = {n: np.asarray(X(A.get(n, sr))) for n in clips}
            for n in clips: emb_store[n][name_] = bb[name_][n].mean(0)
            return bb[name_]
        for j in sorted(ZOO.glob("classification-heads/**/*.json")):
            pb = j.with_suffix(".pb")
            if not pb.exists() or "tfjs" in str(j) or args.only not in str(j): continue
            try:
                m, inn, pr, _ = meta(j)
                em = (m["inference"].get("embedding_model") or {})
                if m["inference"]["algorithm"] != "TensorflowPredict2D" or "openl3" in str(em.get("model_name")): continue
                H = es.TensorflowPredict2D(graphFilename=str(pb), input=inn, output=pr)
                E = backbone(em["model_name"])
                cls = m.get("classes") or [f"o{i}" for i in range(9999)]
                for n in clips:
                    v = mean_rows(H(E[n].astype(np.float32)))
                    for c, x in zip(cls, v): put(n, f"{j.relative_to(ZOO).parent}/{j.stem}::{c}", float(x))
            except Exception as e:
                fail(str(j.relative_to(ZOO)), e)
        print(f"heads done {time.time()-t0:.0f}s", flush=True)

    # ---- MAEST
    if "maest" in fam:
        for j in sorted(ZOO.glob("feature-extractors/maest/*-2.json")):          # the '-1' MAEST files are the old export (input 'melspectrogram' does not exist)
            pb = j.with_suffix(".pb")
            try:
                m, inn, pr, em = meta(j)
                M = es.TensorflowPredictMAEST(graphFilename=str(pb), output=pr)
                cls = m.get("classes") or []
                for n in clips:
                    v = mean_rows(M(A.get(n, 16000)))
                    for c, x in zip(cls, v): put(n, f"maest/{j.stem}::{c}", float(x))
            except Exception as e:
                fail(str(j.relative_to(ZOO)), e)
        print(f"maest done {time.time()-t0:.0f}s", flush=True)

    # ---- tempo
    if "tempo" in fam:
        for j in sorted(ZOO.glob("tempo/tempocnn/*.json")):
            try:
                T = es.TempoCNN(graphFilename=str(j.with_suffix(".pb")))
                for n in clips:
                    g, loc, _p = T(A.get(n, 11025))
                    put(n, f"tempo/{j.stem}::global_bpm", float(g)); put(n, f"tempo/{j.stem}::local_bpm_mean", float(np.mean(loc)))
                    put(n, f"tempo/{j.stem}::local_bpm_std", float(np.std(loc)))
            except Exception as e:
                fail(str(j.relative_to(ZOO)), e)
        print(f"tempo done {time.time()-t0:.0f}s", flush=True)

    # ---- pitch
    if "pitch" in fam:
        for j in sorted(ZOO.glob("pitch/crepe/*.json")):
            try:
                P = es.PitchCREPE(graphFilename=str(j.with_suffix(".pb")))
                for n in clips:
                    _t, f, c, _a = P(A.get(n, 16000))
                    ok = c > 0.5
                    put(n, f"pitch/{j.stem}::confident_frac", float(ok.mean()))
                    if ok.any():
                        for q in (10, 50, 90): put(n, f"pitch/{j.stem}::f0_p{q}", float(np.percentile(f[ok], q)))
            except Exception as e:
                fail(str(j.relative_to(ZOO)), e)
        print(f"pitch done {time.time()-t0:.0f}s", flush=True)

    # ---- pooled embeddings from the standalone extractors (for distances)
    if "embeddings" in fam:
        for nm, alg, kw in (("discogs-effnet-bs64-1", "TensorflowPredictEffnetDiscogs", {}), ("msd-musicnn-1", "TensorflowPredictMusiCNN", {}),
                            ("audioset-vggish-3", "TensorflowPredictVGGish", {}), ("audioset-yamnet-1", "TensorflowPredictVGGish", {})):
            try:
                pb = next(ZOO.glob("**/" + nm + ".pb"))
                mm, inn, pr, em = meta(pb.with_suffix(".json"))
                X = getattr(es, alg)(graphFilename=str(pb), output=em, **({"input": inn} if "yamnet" in nm else {}))
                for n in clips: emb_store[n][nm] = np.asarray(X(A.get(n, 16000))).mean(0)
            except Exception as e:
                fail("embedding/" + nm, e)
        print(f"embeddings done {time.time()-t0:.0f}s", flush=True)

    for n in clips:
        for k, v in emb_store[n].items():
            out[n]["_emb::" + k] = [float(x) for x in np.asarray(v).ravel()]
    out["_failures"] = fails
    out["_meta"] = {"seconds": args.seconds, "families": sorted(fam), "wall_s": time.time() - t0, "n_failures": len(fails)}
    json.dump(out, open(args.out, "w"))
    print("ZOO_DONE", {k: len(v) for k, v in list(out.items())[:3] if isinstance(v, dict)}, "failures", len(fails), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--families", default="classifiers,autotag,events,heads,maest,tempo,pitch,embeddings")
    ap.add_argument("--seconds", type=float, default=45.0)
    ap.add_argument("--only", default="", help="substring filter on the model path, e.g. gender")
    ap.add_argument("--offset", type=float, default=0.0, help="start decoding at this many seconds")
    run(ap.parse_args())
