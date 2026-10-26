#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-21)
# Last edited: GHOST-NOTE 2026-10-21 -- run_meta purpose as f-string (a % in it crashed the first run after all renders)
# Last edited: GHOST-NOTE 2026-10-26 -- --extra-scales: add flat arms (e.g. x0.75, x0.65) to an existing run's cells.jsonl
"""mixtape_z0_relcut.py -- RELATIVE latent-norm cuts for the clips above std MIN_STD (default 1.7), follow-up to mixtape_z0_clamp (EXPERIMENTS M1).

WHY (owner verdict 2026-10-21 on mixtape_clamp_1p7, relayed by W): the timbre shift is not on every clip, so the target should not be a fixed std cap but relative to how much it
changes the HF ratio (or e.g. a flat ~15% reduction). Arms per clip: orig; x0.92 and x0.85 (flat relative cut of the whole latent); and per-clip scale chosen so hf_ratio (>8 kHz energy
share, mono) falls by 5 / 10 / 15 % (equal timbre cost per clip). The hf-vs-scale curve is sampled on a grid of scales and interpolated, then the chosen scale is decoded and its
hf drop re-measured. Output Mantu/sa3_lora_runs/<out-name>/<clip>__{orig,x0.92,x0.85,hf5,hf10,hf15}.wav + cells.jsonl (scales, achieved hf drop, crest, rms).
RUN (GPU lock held): SAO/.venv/bin/python eval/mixtape_z0_relcut.py --device cuda
"""
import argparse, json, os, sys, time
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
import numpy as np, soundfile as sf, torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mixtape_z0_clamp import meters, M, SHORT

GRID = [1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.6, 0.5]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--device", default="cuda"); ap.add_argument("--min-std", type=float, default=1.7)
    ap.add_argument("--out-name", default="mixtape_z0_relcut_2026-10-21"); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--extra-scales", default="", help="comma list, e.g. 0.75,0.65: add flat arms xS to the existing cells.jsonl and exit")
    a = ap.parse_args()
    out = f"/run/media/kim/Mantu/sa3_lora_runs/{a.out_name}"; os.makedirs(out, exist_ok=True)
    jl = f"{out}/cells.jsonl"; done = {json.loads(l)["id"] for l in open(jl)} if os.path.exists(jl) else set()
    clips = []
    for x in json.load(open(SHORT)):
        st = x["file"].rsplit(".", 1)[0]; p = M + st + ".z0.npy"
        if os.path.exists(p): clips.append((st, p))
    from stable_audio_3 import AutoencoderModel
    ae = AutoencoderModel.from_pretrained("same-l", device=a.device)

    def dec(z):
        with torch.no_grad():
            return ae.decode((z).to(a.device)).float()[0].cpu().numpy()

    def save(x, path):
        pk = float(np.abs(x).max()) or 1e-9
        sf.write(path, (x / pk * 0.8913 if pk > 1 else x).T, 44100)

    if a.extra_scales:
        scs = [float(v) for v in a.extra_scales.split(",")]; rows = [json.loads(l) for l in open(jl)]
        for row in rows:
            st = row["id"]; z = torch.from_numpy(np.load(M + st + ".z0.npy").astype(np.float32)); m0 = row["orig"]
            for g in scs:
                tag = f"x{g:g}"
                if tag in row: continue
                x = dec(z * g); mt = meters(x, 44100); save(x, f"{out}/{st}__{tag}.wav")
                mt.update(scale=g, hf_drop_pct=round(100 * (1 - mt["hf_ratio"] / m0["hf_ratio"]), 1), std=round(row["z0_std"] * g, 3)); row[tag] = mt
            print(st[:55], {f"x{g:g}": row[f"x{g:g}"]["hf_drop_pct"] for g in scs}, flush=True)
        open(jl, "w").write("".join(json.dumps(r) + "\n" for r in rows)); print("RELCUT EXTRA DONE", flush=True); os._exit(0)

    n = 0
    for st, p in clips:
        if st in done: continue
        z = torch.from_numpy(np.load(p).astype(np.float32)); s = float(z.std())
        if s <= a.min_std: continue
        if a.limit and n >= a.limit: break
        t0 = time.time(); row = dict(id=st, z0_std=round(s, 4))
        x0 = dec(z); m0 = meters(x0, 44100); save(x0, f"{out}/{st}__orig.wav"); row["orig"] = m0
        curve = [(1.0, m0["hf_ratio"])] + [(g, meters(dec(z * g), 44100)["hf_ratio"]) for g in GRID[1:]]
        sc, hf = np.array([c[0] for c in curve]), np.array([c[1] for c in curve])
        order = np.argsort(hf); row["curve"] = [(round(float(g), 3), float(h)) for g, h in curve]
        targets = [("x0.92", 0.92), ("x0.85", 0.85)]
        for pct in (5, 10, 15):
            want = m0["hf_ratio"] * (1 - pct / 100); g = float(np.interp(want, hf[order], sc[order])); targets.append((f"hf{pct}", g))
        for tag, g in targets:
            x = dec(z * g); mt = meters(x, 44100); save(x, f"{out}/{st}__{tag}.wav")
            mt.update(scale=round(g, 4), hf_drop_pct=round(100 * (1 - mt["hf_ratio"] / m0["hf_ratio"]), 1), std=round(s * g, 3)); row[tag] = mt
        row["secs"] = round(time.time() - t0, 1); open(jl, "a").write(json.dumps(row) + "\n"); n += 1
        print(st[:55], round(s, 2), {t: row[t]["scale"] for t, _ in targets}, f"{row['secs']}s", flush=True)
    json.dump({"purpose": f"Relative z0 cuts (flat x0.92/x0.85 and per-clip hf_ratio -5/-10/-15 percent) on clips above std {a.min_std}; follow-up to mixtape_z0_clamp, owner verdict 2026-10-21.",
               "script": "eval/mixtape_z0_relcut.py", "result": None, "kim_feedback": None}, open(f"{out}/run_meta.json", "w"), indent=1)
    print("RELCUT DONE", n, flush=True); os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
