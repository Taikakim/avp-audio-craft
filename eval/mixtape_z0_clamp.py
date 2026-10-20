#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-20)
# Last edited: GHOST-NOTE 2026-10-20 -- --min-std/--out-name/--no-lim for the narrow 1.7->1.6/1.5/1.4 follow-up
"""mixtape_z0_clamp.py -- post-hoc latent-norm clamp for the Kim shortlist (eval/mixtape_audit_kim_shortlist_2026-09-15.json).

WHY (owner ask 2026-10-20): "calculate the norm for all of these, and if it's past 1.4 or so, clamp/compress it". Each model_matrix clip has its z0 beside it
(.z0.npy, (1,256,512)); healthy medium z0 std ~1.13, the runaway family ~5.6, the shortlisted fives run median 1.37. For z0 with std > CAP the whole latent is scaled by
CAP/std (a global ceiling, the same rule as latch_guided._anchor_std applied once to the finished latent; below CAP nothing changes), then decoded with SAME-L.
Writes <out>/<clip>__orig.wav (decode of the unclamped z0, so the pair differs ONLY by the clamp) and __clamp.wav, plus cells.jsonl (std, scale, hf_ratio, crest, raw peak, rms dB).
RUN (GPU lock held): SAO/.venv/bin/python eval/mixtape_z0_clamp.py --caps 1.4,1.15 --only-over --device cuda
"""
import argparse, json, os, sys, time
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
import numpy as np, soundfile as sf, torch
M = "/run/media/kim/Mantu/sa3_lora_runs/model_matrix/"
SHORT = "/home/kim/Projects/SAO/eval/mixtape_audit_kim_shortlist_2026-09-15.json"


def meters(x, sr):
    m = x.mean(0); S = np.abs(np.fft.rfft(m)) ** 2; f = np.fft.rfftfreq(len(m), 1 / sr)
    return dict(hf_ratio=round(float(S[f > 8000].sum() / S.sum()), 4), crest=round(float(np.abs(m).max() / (np.sqrt((m ** 2).mean()) + 1e-12)), 2),
                raw_peak=round(float(np.abs(x).max()), 3), rms_db=round(float(20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-12)), 2))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--caps", default="1.4,1.15"); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--device", default="cpu"); ap.add_argument("--min-std", type=float, default=0.0); ap.add_argument("--out-name", default="mixtape_z0_clamp_2026-10-20"); ap.add_argument("--no-lim", action="store_true"); ap.add_argument("--only-over", action="store_true", help="only clips with std > cap")
    a = ap.parse_args()
    caps = [float(c) for c in a.caps.split(",")]; lo = min(caps)
    out = f"/run/media/kim/Mantu/sa3_lora_runs/{a.out_name}"; os.makedirs(out, exist_ok=True)
    jl = f"{out}/cells.jsonl"; done = {json.loads(l)["id"] for l in open(jl)} if os.path.exists(jl) else set()
    clips = []
    for x in json.load(open(SHORT)):
        st = x["file"].rsplit(".", 1)[0]; p = M + st + ".z0.npy"
        if os.path.exists(p): clips.append((st, p))
    print(f"{len(clips)} clips with z0", flush=True)
    from stable_audio_3 import AutoencoderModel
    ae = AutoencoderModel.from_pretrained("same-l", device=a.device)
    pt = ae.model if hasattr(ae, "model") else ae
    n = 0
    for st, p in clips:
        if st in done: continue
        z = torch.from_numpy(np.load(p).astype(np.float32)); s = float(z.std())
        if (a.only_over and s <= lo) or s <= a.min_std: continue
        if a.limit and n >= a.limit: break
        t0 = time.time(); row = dict(id=st, z0_std=round(s, 4))
        arms = [("orig", z)] + [(f"c{c:g}", z * (c / s)) for c in caps if s > c]
        for tag, zz in arms:
            with torch.no_grad():
                x = ae.decode(zz.to(a.device)).float()[0].cpu().numpy()
            pk = float(np.abs(x).max()) or 1e-9
            sf.write(f"{out}/{st}__{tag}.wav", (x / pk * 0.8913 if pk > 1 else x).T, 44100)
            row[tag] = meters(x, 44100)
            if tag == "orig" and not a.no_lim:   # soft-limited original: knee 0.6 raw, peaks <= 1 BEFORE normalisation -> tests level/overload vs latent std
                k = 0.6; ax = np.abs(x); y = np.where(ax > k, np.sign(x) * (k + (1 - k) * np.tanh((ax - k) / (1 - k))), x)
                sf.write(f"{out}/{st}__lim.wav", (y / (np.abs(y).max() or 1) * 0.8913).T, 44100); row["lim"] = meters(y, 44100)
        row["secs"] = round(time.time() - t0, 1); open(jl, "a").write(json.dumps(row) + "\n"); n += 1
        print(st[:60], row["z0_std"], [t for t, _ in arms], f"{row['secs']}s", flush=True)
    print("CLAMP DONE", n, flush=True); os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
