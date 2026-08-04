#!/usr/bin/env python
"""muscriptor_decode_task.py -- single-GCD worker for the MuScriptor full-corpus batch
(spec: docs/superpowers/specs/2026-07-17-muscriptor-lumi-batch.md; local gate GREEN on
section metrics 2026-07-17: pc .9955 / nps .97 / F1 .74-vs-ceiling).

Per crop id in --shard: load latent -> SAME-decode -> MuScriptor transcribe ->
<id>.mid + <id>.stats.json with the INTEGRITY SCREEN: decode-MIDI pitch-class
profile vs the encode-time chroma reference profile (--profiles json, built
locally by eval/build_muscriptor_ref_profiles.py). Low cosine flags crops where
codec+transcriber degrade (the 'Passage' 200bpm failure mode, 1/12 in the gate)
so labels are excluded rather than silently wrong. Resumable (skips existing .mid).
"""
import argparse, json, os, time
from pathlib import Path
import numpy as np

# Force the HF cache to the one that actually holds SA3 medium-base (training's cache), and
# offline — belt-and-suspenders so a stale sbatch HF_HOME can't send us to the empty hf_cache.
# Guarded on the LUMI path existing so local runs (the tryout) are unaffected.
_LUMI_MODELS = "/project/project_465003186/models"
if os.path.isdir(_LUMI_MODELS):
    os.environ["HF_HOME"] = _LUMI_MODELS
    os.environ["HF_HUB_OFFLINE"] = "1"
    # MIOpen's USER perf-db defaults to a path baked into the read-only SIF
    # (/home/.../pytorch-tunings/miopen/db) -> "Read-only file system" on the compute node,
    # which surfaces as miopenStatusUnknownError on the first GPU kernel (the decode conv).
    # MIOPEN_DISABLE_CACHE=1 only disables the kernel cache, not this user-db write. Redirect
    # the writable user-db + kernel-cache to node-local /tmp, per-process so the 8 GCDs on a
    # node don't collide; the tuned SYSTEM db in the SIF is still read for its perf entries.
    import tempfile
    _mio = os.path.join(tempfile.gettempdir(), f"miopen-{os.getpid()}")
    os.makedirs(_mio, exist_ok=True)
    os.environ["MIOPEN_USER_DB_PATH"] = _mio
    os.environ["MIOPEN_CUSTOM_CACHE_DIR"] = _mio

def pc_profile(notes):
    h = np.zeros(12)
    for _, p in notes: h[p % 12] += 1
    return (h / max(h.sum(), 1)).tolist()

def midi_notes_bytes(b):
    import io, mido
    mid = mido.MidiFile(file=io.BytesIO(b))
    out, now = [], 0.0
    for msg in mid:
        now += msg.time
        if msg.type == "note_on" and msg.velocity > 0: out.append((now, msg.note))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", required=True)
    ap.add_argument("--latents", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--profiles", required=True)
    ap.add_argument("--model", default="medium")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    ids = [l.strip() for l in open(a.shard) if l.strip()]
    todo = [i for i in ids if not (out / f"{i}.mid").exists()]
    print(f"[task] shard {Path(a.shard).name}: {len(todo)}/{len(ids)} to do", flush=True)
    if not todo: return
    ref = json.load(open(a.profiles))
    import torch
    from safetensors.torch import load_file
    from stable_audio_3.model_configs import all_models
    from stable_audio_3.factory import create_pretransform_from_config
    from stable_audio_3.loading_utils import copy_state_dict
    from muscriptor import TranscriptionModel
    # DECODER-ONLY: build just the SAME pretransform + load its weights from the medium-base
    # ckpt. Avoids the DiT and the T5-Gemma text conditioner entirely — t5gemma was never
    # cached (training used pre-encoded latents), so the full from_pretrained() dies offline.
    # This task only needs latent -> audio, which is the pretransform's decode.
    cfg_path, ckpt_path = all_models["medium-base"].resolve()
    _cfg = json.load(open(cfg_path)); sr = _cfg["sample_rate"]
    pt = create_pretransform_from_config(_cfg.get("model", _cfg), sr).to("cuda").half().eval().requires_grad_(False)
    _sd = load_file(ckpt_path)
    copy_state_dict(pt, {k[len("pretransform."):]: v for k, v in _sd.items() if k.startswith("pretransform.")})
    tm = TranscriptionModel.load_model(a.model, device="cuda")
    import soundfile as sf
    wav = out / f"_work_{Path(a.shard).stem}.wav"
    for i in todo:
        t0 = time.time()
        try:
            z = torch.from_numpy(np.load(Path(a.latents) / f"{i}.npy").astype(np.float32)).unsqueeze(0).cuda()
            with torch.no_grad():
                y = pt.decode(z.to(next(pt.parameters()).dtype))[0].float().cpu().numpy()
            sf.write(wav, y.T, sr)
            midi = tm.transcribe_to_midi(wav)
            notes = midi_notes_bytes(midi)
            prof = pc_profile(notes)
            r = ref.get(i)
            integ = float(np.corrcoef(prof, r)[0, 1]) if r and np.std(prof) > 0 else None
            (out / f"{i}.mid").write_bytes(midi)
            (out / f"{i}.stats.json").write_text(json.dumps({
                "id": i, "n_notes": len(notes), "notes_per_sec": round(len(notes) / 380.4, 3),
                "pc_profile": [round(v, 4) for v in prof],
                "integrity_pc_corr": None if integ is None else round(integ, 3),
                "integrity_flag": bool(integ is not None and integ < 0.7),
                "wall_s": round(time.time() - t0, 1)}))
            print(f"[ok] {i} {len(notes)}n {time.time()-t0:.0f}s integ={integ}", flush=True)
        except Exception as e:
            print(f"[FAIL] {i} {type(e).__name__}: {str(e)[:120]}", flush=True)
    wav.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
