#!/usr/bin/env python3
"""
Precision differential-injection A/B  (Gemini deep-research experiment #2)
=========================================================================

Question: does the production fp16 Flash-Attention path distort the DiT's
*velocity-response to a single-note (fifth-jump) change*, versus a strict
fp32 SDPA attention reference?

Mechanism (no model-code change):
  * Both arms load medium-base in **fp32** (model_half=False).
  * Arm A (default env)               -> fp16 CK Flash-Attention (production path;
                                          q/k/v cast fp32->fp16 in transformer.py).
  * Arm B (SA3_DISABLE_FLASH_ATTN=1)  -> attention runs through SDPA at fp32 = the
                                          "strict fp32 reference".
  The env flag is read at *import time* (module-level in transformer.py), so each
  arm MUST run in its own process. This script sets the flag from --arm BEFORE any
  stable_audio_3 import.

Protocol (Gemini's 5 steps):
  1. Build baseline z0_base and perturbed z0_pert latent sequences that differ by
     exactly one note = a fifth jump (+7 semitones), per timbre.
  2. For t in {0.1,0.2,0.35,0.5,0.7}: noise both with the SAME noise -> z_t, run the
     DiT forward v = model(z_t, t, cond) with a fixed neutral prompt, cfg_scale=1.0.
  3. dv = v(pert) - v(base)  per arm, per t, per timbre.
  4. Project dv onto the 15-dim melody eigenbasis (lumi/melody_subspace15_v2.npz).
  5. Cosine(dv_A, dv_B) in the melody subspace, per t / timbre. Plus ||dv|| ratio
     and melody-energy fraction.

Usage:
  compute one arm:   python precision_injection_ab.py --arm A --out <dir>
                     python precision_injection_ab.py --arm B --out <dir>
  compare + report:  python precision_injection_ab.py --compare --out <dir>

Latent construction (documented caveat): the v2 atlas provides only *per-frame slot
vectors* (10 timbres x 73 pitches x 256-d), NOT encoded latent sequences. As the spec
permits, we place the pitch slot-vectors on a frame grid to build an 8-note melody and
change exactly ONE note by a fifth. This is a synthetic-but-faithful latent sequence:
the delta between base/pert in the changed frames equals slot[p+7]-slot[p], the same
quantity stage3_fifthjump_v2 measured. Attention then spreads the response across frames.
"""
import os, sys, json, argparse, time
from pathlib import Path

# ---- parse --arm FIRST and set env before importing torch / stable_audio_3 ----
_pre = argparse.ArgumentParser(add_help=False)
_pre.add_argument("--arm", choices=["A", "B"], default=None)
_pre.add_argument("--compare", action="store_true")
_known, _ = _pre.parse_known_args()

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")  # arm A: real CK FA2
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
if _known.arm == "B":
    os.environ["SA3_DISABLE_FLASH_ATTN"] = "1"     # strict fp32 SDPA reference

REPO = Path(__file__).resolve().parents[1]
ATLAS = REPO / "eval/musicology/latent_melody_analysis_v2/stage1_pitch_atlas_v2.npz"
BASIS = REPO / "lumi/melody_subspace15_v2.npz"

# diffusion times (include low-noise steps where fine detail resolves)
TS = [0.1, 0.2, 0.35, 0.5, 0.7]
NOTE_FRAMES = 16
N_NOTES = 8
T = N_NOTES * NOTE_FRAMES              # 128 frames (~11.9 s at 10.7666 Hz)
BASE_MELODY = [60, 62, 64, 65, 67, 65, 64, 62]   # MIDI, a small phrase around C4
CHANGE_IDX = 4                          # the single note we perturb
FIFTH = 7                               # semitones (perfect fifth)
NEUTRAL_PROMPT = "a clean instrumental melody"
DURATION_SEC = 12.0
SEED = 1234


def build_latents():
    """Return (z0_base, z0_pert) float32 arrays (n_timbre, 256, T) + meta."""
    import numpy as np
    d = np.load(ATLAS, allow_pickle=True)
    slot = d["slot_vectors"].astype(np.float32)   # (10,73,256)
    pitches = d["pitches"].astype(int)            # MIDI, 36..108
    timbres = [str(x) for x in d["timbres"]]
    p2i = {int(p): i for i, p in enumerate(pitches)}
    nT = slot.shape[0]
    C = slot.shape[2]
    base = np.zeros((nT, C, T), dtype=np.float32)
    pert = np.zeros((nT, C, T), dtype=np.float32)
    base_pitches = list(BASE_MELODY)
    pert_pitches = list(BASE_MELODY)
    pert_pitches[CHANGE_IDX] = BASE_MELODY[CHANGE_IDX] + FIFTH
    for ti in range(nT):
        for n in range(N_NOTES):
            fr = slice(n * NOTE_FRAMES, (n + 1) * NOTE_FRAMES)
            base[ti, :, fr] = slot[ti, p2i[base_pitches[n]], :][:, None]
            pert[ti, :, fr] = slot[ti, p2i[pert_pitches[n]], :][:, None]
    meta = dict(timbres=timbres, base_pitches=base_pitches, pert_pitches=pert_pitches,
                change_idx=CHANGE_IDX, changed_frames=[CHANGE_IDX * NOTE_FRAMES,
                (CHANGE_IDX + 1) * NOTE_FRAMES], n_channels=int(C), T=int(T),
                note_frames=NOTE_FRAMES)
    return base, pert, meta


def compute_arm(arm, out):
    import numpy as np
    import torch
    from stable_audio_3.model import StableAudioModel
    from stable_audio_3.models.transformer import _SA3_DISABLE_FLASH_ATTN

    dev = "cuda"
    print(f"[arm {arm}] SA3_DISABLE_FLASH_ATTN(module)={_SA3_DISABLE_FLASH_ATTN} "
          f"env={os.environ.get('SA3_DISABLE_FLASH_ATTN')}")
    base, pert, meta = build_latents()
    nT, C, Tt = base.shape
    assert C == 256, f"expected 256 latent channels, got {C}"

    print(f"[arm {arm}] loading medium-base fp32 ...")
    sam = StableAudioModel.from_pretrained("medium-base", model_half=False)
    dit = sam.model.model            # DiTWrapper (cfg_scale=1.0 -> plain conditional fwd)
    model_dtype = next(sam.model.model.parameters()).dtype
    print(f"[arm {arm}] model_dtype={model_dtype}  io_channels={sam.model.io_channels}")

    # ---- conditioning (fixed neutral prompt, identical for base & pert) ----
    cond, neg = sam._build_conditioning_dicts(NEUTRAL_PROMPT, None, DURATION_SEC, nT)
    ct = sam.model.conditioner(cond, dev)
    # report which conditioner id-lists are populated (for provenance / inpaint check)
    ids = dict(cross=list(sam.model.cross_attn_cond_ids),
               global_=list(sam.model.global_cond_ids),
               input_concat=list(sam.model.input_concat_ids),
               local_add=list(sam.model.local_add_cond_ids),
               prepend=list(sam.model.prepend_cond_ids))
    print(f"[arm {arm}] conditioner ids: {ids}")
    # medium-base carries inpaint local-add conditioning; supply the neutral
    # (no-inpaint) all-zero mask + masked-input exactly as generate() does. These
    # are zeros and identical for base & pert, so they cancel in dv.
    io_ch = sam.model.io_channels
    ct["inpaint_mask"] = [torch.zeros((nT, 1, Tt), device=dev)]
    ct["inpaint_masked_input"] = [torch.zeros((nT, io_ch, Tt), device=dev)]
    cond_inputs = sam.model.get_conditioning_inputs(ct)
    # cast conditioning to model dtype (mirror generate())
    cond_inputs = {k: (v.type(model_dtype) if torch.is_tensor(v) else v)
                   for k, v in cond_inputs.items()}

    # ---- fixed shared noise ----
    torch.manual_seed(SEED)
    eps = torch.randn((nT, C, Tt), device=dev, dtype=torch.float32)
    z0b = torch.from_numpy(base).to(dev)
    z0p = torch.from_numpy(pert).to(dev)

    dv = np.zeros((len(TS), nT, C, Tt), dtype=np.float32)   # dv per (t, timbre)
    vb_norm = np.zeros((len(TS), nT), dtype=np.float32)
    with torch.no_grad():
        for ci, tval in enumerate(TS):
            tt = torch.full((nT,), float(tval), device=dev, dtype=torch.float32)
            ztb = ((1.0 - tval) * z0b + tval * eps).type(model_dtype)
            ztp = ((1.0 - tval) * z0p + tval * eps).type(model_dtype)
            vb = dit(ztb, tt, cfg_scale=1.0, **cond_inputs).float()
            vp = dit(ztp, tt, cfg_scale=1.0, **cond_inputs).float()
            d = (vp - vb).cpu().numpy()
            dv[ci] = d
            vb_norm[ci] = np.linalg.norm(vb.cpu().numpy().reshape(nT, -1), axis=1)
            print(f"[arm {arm}] t={tval}: ||dv||_fro(mean over timbre)="
                  f"{np.linalg.norm(d.reshape(nT,-1),axis=1).mean():.4f}")

    outp = Path(out) / f"deltav_arm{arm}.npz"
    np.savez_compressed(outp, dv=dv, vb_norm=vb_norm, ts=np.array(TS),
                        timbres=np.array(meta["timbres"]),
                        arm=arm, module_disable_flash=bool(_SA3_DISABLE_FLASH_ATTN))
    (Path(out) / f"meta_arm{arm}.json").write_text(json.dumps(
        dict(arm=arm, module_disable_flash=bool(_SA3_DISABLE_FLASH_ATTN),
             model_dtype=str(model_dtype), conditioner_ids=ids, meta=meta,
             ts=TS, seed=SEED, prompt=NEUTRAL_PROMPT, duration_sec=DURATION_SEC), indent=2))
    print(f"[arm {arm}] saved {outp}")


def compare(out):
    import numpy as np
    out = Path(out)
    A = np.load(out / "deltav_armA.npz", allow_pickle=True)
    B = np.load(out / "deltav_armB.npz", allow_pickle=True)
    bd = np.load(BASIS, allow_pickle=True)
    basis = bd["basis15"].astype(np.float64)     # (15,256)
    assert np.abs(basis @ basis.T - np.eye(15)).max() < 1e-4, "basis not orthonormal"

    dvA = A["dv"].astype(np.float64)   # (nt, ntimbre, 256, T)
    dvB = B["dv"].astype(np.float64)
    ts = list(A["ts"])
    timbres = [str(x) for x in A["timbres"]]
    nt, ntb, C, Tt = dvA.shape

    def melody_coeffs(dv):
        # project each frame's 256-vector onto basis15 -> (nt,ntimbre,15,T)
        return np.einsum("kc,ntcf->ntkf", basis, dv)

    cA = melody_coeffs(dvA)
    cB = melody_coeffs(dvB)

    rows = []              # per (t, timbre)
    for i, tval in enumerate(ts):
        for j in range(ntb):
            a = dvA[i, j].reshape(-1)          # full-space
            b = dvB[i, j].reshape(-1)
            ca = cA[i, j].reshape(-1)          # melody-subspace
            cb = cB[i, j].reshape(-1)
            cos_full = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-30))
            cos_mel = float(ca @ cb / (np.linalg.norm(ca) * np.linalg.norm(cb) + 1e-30))
            nA = float(np.linalg.norm(a)); nB = float(np.linalg.norm(b))
            mfracA = float((ca @ ca) / (a @ a + 1e-30))
            mfracB = float((cb @ cb) / (b @ b + 1e-30))
            rows.append(dict(t=tval, timbre=timbres[j], cos_melody=cos_mel,
                             cos_full=cos_full, dvA_norm=nA, dvB_norm=nB,
                             norm_ratio_A_over_B=nA / (nB + 1e-30),
                             mel_energy_frac_A=mfracA, mel_energy_frac_B=mfracB))

    # aggregate per t
    per_t = {}
    for tval in ts:
        r = [x for x in rows if x["t"] == tval]
        per_t[tval] = dict(
            cos_melody_mean=float(np.mean([x["cos_melody"] for x in r])),
            cos_melody_min=float(np.min([x["cos_melody"] for x in r])),
            cos_full_mean=float(np.mean([x["cos_full"] for x in r])),
            cos_full_min=float(np.min([x["cos_full"] for x in r])),
            norm_ratio_mean=float(np.mean([x["norm_ratio_A_over_B"] for x in r])),
            mel_frac_A_mean=float(np.mean([x["mel_energy_frac_A"] for x in r])),
            mel_frac_B_mean=float(np.mean([x["mel_energy_frac_B"] for x in r])),
        )
    overall = dict(
        cos_melody_mean=float(np.mean([x["cos_melody"] for x in rows])),
        cos_melody_min=float(np.min([x["cos_melody"] for x in rows])),
        cos_full_mean=float(np.mean([x["cos_full"] for x in rows])),
        norm_ratio_mean=float(np.mean([x["norm_ratio_A_over_B"] for x in rows])),
        mel_frac_A_mean=float(np.mean([x["mel_energy_frac_A"] for x in rows])),
        mel_frac_B_mean=float(np.mean([x["mel_energy_frac_B"] for x in rows])),
    )
    result = dict(per_t=per_t, overall=overall, rows=rows, ts=ts, timbres=timbres)
    (out / "result.json").write_text(json.dumps(result, indent=2))

    # ---- REPORT.md ----
    L = []
    L.append("# Precision differential-injection A/B — fp16 Flash vs fp32 SDPA\n")
    L.append("Cosine similarity of the **melody-subspace-projected** single-note (fifth-jump)")
    L.append("velocity-response between arm A (production fp16 CK Flash-Attention) and arm B")
    L.append("(strict fp32 SDPA, `SA3_DISABLE_FLASH_ATTN=1`). Both load medium-base in fp32.\n")
    L.append("cosine ~1 => fp16 attention preserves the melody-direction response; "
             "cosine << 1 => it distorts it.\n")
    L.append("## Per diffusion-time t (mean / min over 10 timbres)\n")
    L.append("| t | cos_melody mean | cos_melody min | cos_full mean | ||dvA||/||dvB|| | mel-frac A | mel-frac B |")
    L.append("|---|---|---|---|---|---|---|")
    for tval in ts:
        p = per_t[tval]
        L.append(f"| {tval} | {p['cos_melody_mean']:.5f} | {p['cos_melody_min']:.5f} | "
                 f"{p['cos_full_mean']:.5f} | {p['norm_ratio_mean']:.4f} | "
                 f"{p['mel_frac_A_mean']:.4f} | {p['mel_frac_B_mean']:.4f} |")
    L.append("")
    L.append(f"**Overall melody-subspace cosine: mean {overall['cos_melody_mean']:.5f}, "
             f"min {overall['cos_melody_min']:.5f}**")
    L.append(f"Overall full-space cosine mean {overall['cos_full_mean']:.5f}.")
    L.append(f"Overall ||dv_fp16||/||dv_fp32|| = {overall['norm_ratio_mean']:.4f}.")
    L.append(f"Melody-energy fraction of dv: fp16 {overall['mel_frac_A_mean']:.4f}, "
             f"fp32 {overall['mel_frac_B_mean']:.4f}.\n")
    verdict = ("NO distortion — fp16 Flash preserves the melody-direction response"
               if overall["cos_melody_min"] > 0.98 else
               "DISTORTION — fp16 Flash measurably alters the melody-direction response")
    L.append(f"## Verdict\n{verdict} (min melody cosine "
             f"{overall['cos_melody_min']:.4f}, threshold 0.98).\n")
    L.append("### Confounds (honest)\n")
    L.append("- Arm A = fp16 CK Flash-Attention kernel; arm B = fp32 SDPA (math) kernel. "
             "This is a **kernel + precision** difference, not pure precision — the two "
             "attention implementations differ in reduction order/algorithm as well as dtype. "
             "A pure-precision isolate would need fp16-vs-fp32 within the SAME kernel.")
    L.append("- Latents are synthetic (pitch slot-vectors placed on a frame grid), not "
             "VAE-encoded audio sequences (see script docstring). The *differential* signal "
             "(slot[p+7]-slot[p]) is the real encoded fifth-jump delta; absolute latent "
             "realism is not required for a differential-response probe.")
    L.append("- cfg_scale=1.0 (no guidance batching): raw conditional velocity.")
    (out / "REPORT.md").write_text("\n".join(L))
    print("\n".join(L))
    print(f"\n[compare] wrote {out/'REPORT.md'} and {out/'result.json'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["A", "B"], default=None)
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    if a.compare:
        compare(a.out)
    elif a.arm:
        t0 = time.time()
        compute_arm(a.arm, a.out)
        print(f"[arm {a.arm}] done in {time.time()-t0:.1f}s")
    else:
        ap.error("need --arm A|B or --compare")
