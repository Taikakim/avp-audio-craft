#!/usr/bin/env python3
# Owner: GHOST-NOTE (created 2026-10-15)
"""latch_crosstalk.py -- how much does a band-RMS head's guidance step move the OTHER bands?  (Kim 2026-10-15: make heads that only change their own band; measure the entanglement first.)
Mean guidance in latch_guided.py steps the CLEAN latent z0 along -grad(head loss) with the head queried at t=0, so that is what is measured here: for each head i,
g_i = d mean_t h_i(z) / dz on real training latents (ascending direction = 'raise band i'); then
  A) METER view (heads as meters, circular -- every head is only as trustworthy as its R2): cos(g_i, g_j) and the response ratio  R_ij = d mean h_j / d mean h_i  after the step
     z' = z + f*||z||*g_i/||g_i||  (f = 0.02, 0.05);  responses in dB via each head's std_std.
  B) AUDIT view (decoded audio = the instrument check): decode z and z' with SAME-L for a few crops, save RAW float wavs (no normalisation) as s<k>_<name>.wav in <out>/audit;
     then   mir/mir/bin/python eval/air_realised_levels.py <out>/audit   gives measured band RMS (dB) -> python eval/latch_crosstalk.py report <out>.
Run (GPU free, SAO/.venv):  .venv/bin/python eval/latch_crosstalk.py run      Output: Mantu2/latch_sweep/crosstalk_2026-10-15/ (crosstalk.json, audit/*.wav)
Heads used: production bass/body/mid/air + the retrained air head A2. Latents: every 27th of the 5400 training crops (the heads saw 95% of them: a held-out split would be cleaner).
"""
import glob, json, os, sys
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
OUT = os.environ.get("CT_OUT", "/run/media/kim/Mantu/latch_sweep/crosstalk_2026-10-15")
W = "/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium"
HEADS = {"bass": f"{W}/latch_sa3_rms_energy_bass_best.pt", "body": f"{W}/latch_sa3_rms_energy_body_best.pt", "mid": f"{W}/latch_sa3_rms_energy_mid_best.pt",
         "air_prod": f"{W}/latch_sa3_rms_energy_air_best.pt", "air_A2": f"{W}/latch_sa3_rms_energy_air_a2_best.pt"}
HEADS["bass"] = os.environ.get("CT_BASS", HEADS["bass"])   # 2026-10-16: measure a RETRAINED bass head (e.g. the decorrelation arms) against the production body/mid/air heads
BANDS = {"bass": "bass", "body": "body", "mid": "mid", "air_prod": "air", "air_A2": "air"}
FRACS = [0.02, 0.05]


def run():
    import numpy as np, torch, soundfile as sf
    sys.path.insert(0, "/home/kim/Projects/SAO/stable-audio-3")
    from stable_audio_3.models.latch import load_latch_from_checkpoint
    os.makedirs(f"{OUT}/audit", exist_ok=True)
    dev = os.environ.get("CT_DEV", "cuda")
    heads = {k: load_latch_from_checkpoint(p, dev).float().eval() for k, p in HEADS.items()}
    for h in heads.values():
        for p in h.parameters(): p.requires_grad_(False)
    std = {k: float(np.mean(np.asarray(getattr(h, "metadata", {}).get("std_std", [1.0])))) for k, h in heads.items()}
    files = sorted(glob.glob("/run/media/kim/Kosmos/latents/latents_sa3/*.npy"))[::27][:int(os.environ.get("CT_N", 200))]
    names = list(heads)
    cos_acc = {(i, j): [] for i in names for j in names}
    resp = {(f, i, j): [] for f in FRACS for i in names for j in names}
    t0 = lambda b: torch.zeros(b, device=dev)

    def level(k, z):
        return heads[k](z, t0(z.shape[0])).mean(dim=(1, 2))       # (B,) standardised mean prediction

    for b0 in range(0, len(files), 4):
        z = torch.from_numpy(np.stack([(lambda a: a[0] if a.ndim == 3 else a)(np.load(f).astype(np.float32)) for f in files[b0:b0 + 4]])).to(dev)
        B = z.shape[0]
        base = {k: level(k, z).detach() for k in names}
        g = {}
        for k in names:
            zz = z.clone().requires_grad_(True)
            g[k] = torch.autograd.grad(level(k, zz).sum(), zz)[0].detach()
        zn = z.flatten(1).norm(dim=1)
        for i in names:
            gi = g[i].flatten(1); gin = gi / (gi.norm(dim=1, keepdim=True) + 1e-12)
            for j in names:
                gj = g[j].flatten(1); cos_acc[(i, j)] += (gin * gj / (gj.norm(dim=1, keepdim=True) + 1e-12)).sum(1).cpu().tolist()
            for f in FRACS:
                zp = z + (f * zn).view(-1, 1, 1) * gin.view_as(z)
                with torch.no_grad():
                    for j in names:
                        resp[(f, i, j)] += ((level(j, zp) - base[j]) * std[j]).cpu().tolist()    # dB-ish: standardised delta x std_std
        print("batch", b0, flush=True)
    res = {"std_std": std, "n": len(files), "cos": {f"{i}|{j}": float(np.mean(v)) for (i, j), v in cos_acc.items()},
           "resp_db": {f"{f}|{i}|{j}": float(np.mean(v)) for (f, i, j), v in resp.items()}}
    json.dump(res, open(f"{OUT}/crosstalk.json", "w"), indent=1)
    names_s = names
    print("cos(g_i, g_j) mean over crops (row i, col j):")
    print(" " * 10 + "".join(f"{j:>10s}" for j in names_s))
    for i in names_s: print(f"{i:10s}" + "".join(f"{res['cos'][f'{i}|{j}']:10.2f}" for j in names_s))
    for f in FRACS:
        print(f"response of head j (cols), dB, to a step raising head i (rows), f={f}:")
        for i in names_s: print(f"{i:10s}" + "".join(f"{res['resp_db'][f'{f}|{i}|{j}']:10.2f}" for j in names_s))
    if os.environ.get("CT_SKIP_AUDIT"): return
    # ---- B) audit: decode z and z' for 12 crops, per head i at f=0.05 ----
    from stable_audio_3 import AutoencoderModel
    ae = AutoencoderModel.from_pretrained("same-l", device=dev)
    adt = next(ae.autoencoder.parameters()).dtype
    for k, fn in enumerate(files[: 12 * 27: 27][:12]):
        z = torch.from_numpy(np.load(fn).astype(np.float32)).to(dev)
        if z.ndim == 2: z = z[None]
        zn = float(z.norm())
        def dec(zz):
            with torch.inference_mode():
                a = ae.decode(zz.to(adt), chunked=True, chunk_size=128, overlap=32)
            return a.squeeze(0).float().cpu().numpy().T
        sf.write(f"{OUT}/audit/s{k}_orig.wav", dec(z), 44100, subtype="FLOAT")
        for i in names:
            zz = z.clone().requires_grad_(True)
            gi = torch.autograd.grad(level(i, zz).sum(), zz)[0]
            zp = (z + 0.05 * zn * gi / (gi.norm() + 1e-12)).detach()
            sf.write(f"{OUT}/audit/s{k}_up_{i}.wav", dec(zp), 44100, subtype="FLOAT")
        print("audit", k, flush=True)
    print("RUN DONE")


def report():
    import numpy as np
    R = json.load(open(f"{OUT}/audit/realised.json"))
    ks = sorted({k.split("_")[0] for k in R})
    bands = ["bass", "body", "mid", "air"]
    print("MEASURED (decoded audio) mean change in band RMS (dB) when head i's step is applied (f=0.05), over crops; row = head raised, col = band measured")
    print(" " * 10 + "".join(f"{b:>9s}" for b in bands))
    for i in ["bass", "body", "mid", "air_prod", "air_A2"]:
        d = [[R[f"{k}_up_{i}"][b] - R[f"{k}_orig"][b] for b in bands] for k in ks if f"{k}_up_{i}" in R and f"{k}_orig" in R]
        print(f"{i:10s}" + "".join(f"{x:9.2f}" for x in np.mean(d, 0)))


if __name__ == "__main__":
    {"run": run, "report": report}[sys.argv[1]]()
