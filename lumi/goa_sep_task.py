#!/usr/bin/env python
"""goa_sep_task.py — LUMI worker: BS-RoFormer stem separation over one shard of the
goa_archive (CONTINUITY 2026-07-29, Kim direct: offload separation to LUMI, stems as
192k m4a). Reuses mir's src/preprocessing/bs_roformer_sep.py wholesale (the proven
separator: chunked overlap-add, AMD SDPA guards, save_audio_smart m4a export) — the
mir src tree must be on PYTHONPATH (staged at ${CODE}/mir-src).

Model: jarredou-BS-ROFO-SW-Fixed-drums (the master_pipeline.yaml operative choice —
the SAME model that produced Goa_Separated, so archive stems match the corpus).
6-stem model ['bass','drums','other','vocals','guitar','piano']; guitar+piano are
DOWNMIXED into 'other' (master_pipeline discard_stems convention) -> 4 saved stems
matching the Goa_Separated layout.

Output: <out>/<relpath-sans-ext>/{bass,drums,other,vocals}.m4a (+ .sep_done marker).
Resumable: skips tracks whose .sep_done exists. Fail-soft per track.
"""
import argparse
import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

# env BEFORE torch import (LUMI: on-disk MIOpen SQLite cache is broken; TunableOp
# results path is read-only /home/kim -> must be off; see profile_encode.py postmortem)
_mio = os.path.join(tempfile.gettempdir(), f"miopen-sep-{os.getpid()}")
os.makedirs(_mio, exist_ok=True)
os.environ.setdefault("MIOPEN_USER_DB_PATH", _mio)
os.environ.setdefault("MIOPEN_CUSTOM_CACHE_DIR", _mio)
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("MIOPEN_DISABLE_CACHE", "1")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")

_LUMI_MODELS = "/project/project_465003186/models"
if os.path.isdir(_LUMI_MODELS):
    os.environ.setdefault("HF_HOME", _LUMI_MODELS)
    os.environ.setdefault("HF_HUB_OFFLINE", "1")

MIR_SRC = os.environ.get("MIR_SRC", "/project/project_465003186/code/mir-src")
sys.path.insert(0, MIR_SRC)

import numpy as np


def load_track(path, sr=44100):
    """(T, C) float32 stereo @ sr — librosa (soundfile -> audioread/ffmpeg fallback),
    NOT bs_roformer_sep.load_audio, so an mp3-less libsndfile in the SIF can't kill us."""
    import librosa
    y, _ = librosa.load(str(path), sr=sr, mono=False)
    if y.ndim == 1:
        y = np.stack([y, y])
    return np.ascontiguousarray(y.T, dtype=np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", required=True, help="text file: one audio path per line (absolute)")
    ap.add_argument("--archive", required=True, help="archive root (for relpath-derived output layout)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model-name", default="jarredou-BS-ROFO-SW-Fixed-drums")
    ap.add_argument("--model-dir", default="/project/project_465003186/models/bs-roformer")
    ap.add_argument("--limit", type=int, default=None, help="probe mode: N tracks then exit")
    a = ap.parse_args()
    archive, out = Path(a.archive), Path(a.out)

    tracks = [Path(l.strip()) for l in open(a.shard) if l.strip()]

    def tdir(p):
        rel = p.relative_to(archive)
        return out / rel.parent / rel.stem

    todo = [p for p in tracks if not (tdir(p) / ".sep_done").exists()]
    if a.limit:
        todo = todo[: a.limit]
    print(f"[sep] shard {Path(a.shard).name}: {len(todo)}/{len(tracks)} to do", flush=True)
    if not todo:
        return

    import torch  # noqa: F401  (venv system-site -> SIF torch)
    from preprocessing.bs_roformer_sep import (load_bs_roformer, separate_audio,
                                               save_audio_smart)

    model, model_cfg, audio_cfg, inf_cfg = load_bs_roformer(a.model_name, a.model_dir, device="cuda")
    names = model_cfg.instruments or ["drums", "bass", "other", "vocals"]
    print(f"[sep] model {a.model_name} loaded; stems={names}", flush=True)
    device = __import__("torch").device("cuda")

    KEEP = ["bass", "drums", "other", "vocals"]
    n_ok = n_fail = 0
    for k, p in enumerate(todo):
        t0 = time.time()
        try:
            audio = load_track(p, audio_cfg.sample_rate)
            stems = separate_audio(model, audio, audio_cfg, model_cfg, inf_cfg, device)  # (S,T,C)
            smap = {names[i]: stems[i] for i in range(min(len(names), stems.shape[0]))}
            # master_pipeline convention: guitar+piano downmix into other, never saved solo
            for extra in ("guitar", "piano"):
                if extra in smap and "other" in smap:
                    smap["other"] = smap["other"] + smap[extra]
            d = tdir(p)
            d.mkdir(parents=True, exist_ok=True)
            for stem in KEEP:
                if stem in smap:
                    save_audio_smart(smap[stem], d / f"{stem}.m4a", audio_cfg.sample_rate,
                                     source_path=p)
            (d / ".sep_done").write_text(json.dumps(
                {"src": str(p), "stems": KEEP, "model": a.model_name,
                 "wall_s": round(time.time() - t0, 1)}))
            n_ok += 1
            print(f"[{k+1}/{len(todo)}] {p.stem}  {time.time()-t0:.1f}s", flush=True)
        except Exception as e:
            n_fail += 1
            print(f"[FAIL] {p} {type(e).__name__}: {str(e)[:160]}\n{traceback.format_exc()[-400:]}",
                  flush=True)
    print(f"[sep] shard done: ok={n_ok} fail={n_fail}", flush=True)


if __name__ == "__main__":
    main()
