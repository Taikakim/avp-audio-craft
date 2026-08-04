#!/usr/bin/env python
"""eval_hf_repair.py — evaluate a trained HF-repair post-net on the MP3-clarity ladder
(part 3/3 of the SA3 HF-repair pipeline).

Loads a post-net checkpoint (train_hf_repair.py) and reports the SAME hf_clarity metrics
(env_corr / crest_ret / flatness_delta per band, after envelope-xcorr alignment — REUSED
verbatim from eval/hf_clarity_diagnosis.py, not reinvented) for four versions, so the
post-net lands on the exact axes the MP3 ladder uses:

    SAME        : codec round-trip only            (the deficit; baseline to beat)
    SAME+postnet: codec round-trip -> post-net     (our repair)
    mp3_128     : 128 kbps MP3                      (the ladder rung we want to reach)
    mp3_320     : 320 kbps MP3                      (near-transparent reference)

Two eval populations:
  (1) held-out cached PAIRS (from build_hf_repair_pairs.py) — the in-distribution test.
  (2) GENERATED clips (glob sa3_control_runs/**/*.wav) — the distribution-shift test:
      does a post-net trained on real audio still help on SA3's own output?

HEADLINE printed: air-band (8-16 kHz) env_corr, SAME-only vs SAME+postnet vs mp3_128.

Run (SA3 venv, GPU for the SAME leg on generated clips; ffmpeg needed for mp3 anchors):
  FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE \
    stable-audio-3/.venv/bin/python eval/eval_hf_repair.py \
      --ckpt /run/media/kim/Mantu/sa3_lora_runs/hf_repair_runs/v1/best.pt
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
import argparse
import json
import subprocess
import sys
import tempfile
from glob import glob
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from train_hf_repair import HFRepairNet  # noqa: E402  (torch-only, safe on CPU)

SR = 44100
DEFAULT_PAIRS = "/run/media/kim/Mantu/sa3_lora_runs/hf_repair_pairs"
DEFAULT_GEN_GLOB = "/run/media/kim/Mantu/sa3_control_runs/**/*.wav"


def load_postnet(ckpt_path, device):
    ck = torch.load(ckpt_path, map_location=device)
    a = ck.get("args", {})
    net = HFRepairNet(channels=a.get("channels", 160), n_stacks=a.get("n_stacks", 4)).to(device)
    net.load_state_dict(ck["model"])
    net.eval()
    return net


def apply_postnet(net, wav, device):
    """wav: [2, T] float32 -> [2, T] float32 refined."""
    with torch.no_grad():
        y = net(torch.from_numpy(wav).float()[None].to(device))
    return y[0].cpu().numpy().astype(np.float32)


def hf_phase_coh(orig, recon, sr=SR, hf_hz=7000):
    """>hf_hz magnitude-weighted phase coherence, recon vs orig (metric validated in
    eval/test_phase_coherence_metric.py: 1=aligned, ~0=random). This is the #64
    regression-ceiling diagnostic: if postnet output phase-coh ~= degraded input phase-coh
    (both near-random) while env_corr/magnitude improve, the regression post-net has hit the
    phase ceiling -> HF phase must be GENERATED, not regressed (Track A pivot)."""
    from scipy.signal import stft as _stft
    f, _, So = _stft(orig, fs=sr, nperseg=2048, noverlap=1536)
    _, _, Sr = _stft(recon, fs=sr, nperseg=2048, noverlap=1536)
    n = min(So.shape[1], Sr.shape[1])
    So, Sr = So[:, :n], Sr[:, :n]
    hf = f > hf_hz
    mag_o = np.abs(So[hf])
    dphi = np.angle(Sr[hf]) - np.angle(So[hf])
    w = mag_o / (mag_o.sum() + 1e-9)
    return float(np.abs((w * np.exp(1j * dphi)).sum()))


def agg_metrics(o_list, versions_list, band_metrics, align, rolloff, BANDS):
    """o_list: list of mono originals; versions_list: list of {name: mono array}."""
    agg = {}
    for o, versions in zip(o_list, versions_list):
        for vname, v in versions.items():
            oa, va = align(o, v.astype(np.float32))
            for bname, (lo, hi) in BANDS.items():
                agg.setdefault((vname, bname), []).append(band_metrics(oa, va, lo, hi))
            agg.setdefault((vname, "rolloff_hz"), []).append(rolloff(va))
    summary = {}
    for (vname, bname), lst in agg.items():
        if bname == "rolloff_hz":
            summary.setdefault(vname, {})["rolloff_hz"] = round(float(np.mean(lst)), 0)
        else:
            summary.setdefault(vname, {})[bname] = {
                k: round(float(np.mean([r[k] for r in lst])), 3) for k in lst[0]}
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ckpt", required=True, help="trained post-net checkpoint (.pt)")
    ap.add_argument("--pairs-dir", default=DEFAULT_PAIRS, help="cached held-out pairs dir")
    ap.add_argument("--gen-glob", default=DEFAULT_GEN_GLOB,
                    help="glob for generated clips (distribution-shift test)")
    ap.add_argument("--n-pairs", type=int, default=40, help="max held-out pairs to eval")
    ap.add_argument("--n-gen", type=int, default=20, help="max generated clips to eval")
    ap.add_argument("--gen-crop-seconds", type=float, default=4.0)
    ap.add_argument("--out", default="/run/media/kim/Mantu/sa3_lora_runs/hf_repair_runs/eval_results.json")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--no-mp3", action="store_true", help="skip mp3 anchors (no ffmpeg)")
    args = ap.parse_args()

    device = args.device if (args.device != "cuda" or torch.cuda.is_available()) else "cpu"

    # Reuse the exact metric + mp3 machinery from hf_clarity_diagnosis (deferred import so
    # --help stays CPU-fast and doesn't pull stable_audio_3).
    import soundfile as sf
    import hf_clarity_diagnosis as hc
    from hf_clarity_diagnosis import band_metrics, align, rolloff, BANDS, mp3

    have_ffmpeg = (not args.no_mp3) and \
        subprocess.run(["which", "ffmpeg"], capture_output=True).returncode == 0
    net = load_postnet(args.ckpt, device)

    results = {}

    # ---- (1) held-out cached pairs (in-distribution) --------------------------------
    manifest = json.loads((Path(args.pairs_dir) / "manifest.json").read_text())
    val = [m for m in manifest["pairs"] if m["is_val"]][:args.n_pairs]
    o_list, ver_list = [], []
    phase_coh = {"SAME": [], "SAME+postnet": []}   # #64 regression-ceiling diagnostic
    for m in val:
        d = np.load(Path(args.pairs_dir) / m["file"])
        target, degraded = d["target"], d["degraded"]  # [2, T]
        o = target.mean(0).astype(np.float32)
        same = degraded.mean(0).astype(np.float32)
        refined = apply_postnet(net, degraded, device).mean(0).astype(np.float32)
        versions = {"SAME": same[:len(o)], "SAME+postnet": refined[:len(o)]}
        # >7kHz phase coherence vs the clean target (aligned by env-xcorr like the band metrics)
        oa_s, va_s = align(o, versions["SAME"]); phase_coh["SAME"].append(hf_phase_coh(oa_s, va_s))
        oa_p, va_p = align(o, versions["SAME+postnet"]); phase_coh["SAME+postnet"].append(hf_phase_coh(oa_p, va_p))
        if have_ffmpeg:
            with tempfile.TemporaryDirectory() as td:
                for k in (128, 320):
                    versions[f"mp3_{k}"] = mp3(o, k, Path(td))
        o_list.append(o)
        ver_list.append(versions)
    if o_list:
        results["heldout_pairs"] = {"n": len(o_list),
                                    "summary": agg_metrics(o_list, ver_list, band_metrics,
                                                           align, rolloff, BANDS),
                                    "phase_ceiling_diag": {
                                        "hf_phase_coh_SAME": round(float(np.mean(phase_coh["SAME"])), 4),
                                        "hf_phase_coh_SAME_postnet": round(float(np.mean(phase_coh["SAME+postnet"])), 4),
                                        "note": ("if postnet ~= SAME (both near-random) while air env_corr "
                                                 "improves => regression phase ceiling confirmed (#64) => "
                                                 "Track A generative pivot justified")}}

    # ---- (2) generated clips (distribution-shift) -----------------------------------
    # These are NOT paired with a clean target -> the SAME round-trip's "target" is the
    # generated clip itself; env_corr then measures how faithfully SAME (and SAME+postnet)
    # reproduce the model's own output. We SAME-encode/decode them here on the GPU.
    gen_files = sorted(glob(args.gen_glob, recursive=True))[:args.n_gen]
    if gen_files:
        from stable_audio_3 import StableAudioModel
        model = StableAudioModel.from_pretrained("medium-base", device=device)
        cdm = model.model
        mdev = next(cdm.model.parameters()).device
        mdtype = next(cdm.model.parameters()).dtype
        clip_n = int(SR * args.gen_crop_seconds)
        go_list, gver_list = [], []
        for gf in gen_files:
            try:
                a, sr = sf.read(gf, dtype="float32", always_2d=True)
            except Exception:  # noqa: BLE001
                continue
            if sr != SR or a.shape[0] < clip_n:
                continue
            if a.shape[1] == 1:
                a = np.repeat(a, 2, axis=1)
            crop = a[:clip_n, :2].T.astype(np.float32)  # [2, clip_n]
            o = crop.mean(0).astype(np.float32)
            with torch.no_grad():
                rec = cdm.pretransform.decode(cdm.pretransform.encode(
                    torch.tensor(crop[None]).to(mdev, mdtype)))
            degraded = rec[0].float().cpu().numpy()[:, :clip_n].astype(np.float32)
            same = degraded.mean(0)[:len(o)]
            refined = apply_postnet(net, degraded, device).mean(0)[:len(o)]
            versions = {"SAME": same, "SAME+postnet": refined}
            if have_ffmpeg:
                with tempfile.TemporaryDirectory() as td:
                    for k in (128, 320):
                        versions[f"mp3_{k}"] = mp3(o, k, Path(td))
            go_list.append(o)
            gver_list.append(versions)
        if go_list:
            results["generated_clips"] = {"n": len(go_list),
                                          "summary": agg_metrics(go_list, gver_list,
                                                                 band_metrics, align,
                                                                 rolloff, BANDS)}

    results["ckpt"] = str(args.ckpt)
    results["have_mp3_anchors"] = have_ffmpeg
    results["reading"] = ("air-band env_corr: SAME-only is the deficit (~0.54 measured), "
                          "target is mp3_128 (~0.97). SAME+postnet closing that gap = success.")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, indent=2))

    # ---- headline ------------------------------------------------------------------
    print("\n=== HF-repair eval (air 8-16k env_corr; higher=better) ===")
    for pop in ("heldout_pairs", "generated_clips"):
        if pop not in results:
            continue
        s = results[pop]["summary"]
        print(f"\n[{pop}] n={results[pop]['n']}")
        for v in ("SAME", "SAME+postnet", "mp3_128", "mp3_320"):
            if v not in s:
                continue
            air = s[v].get("air_8-16k", {})
            pres = s[v].get("presence_4-8k", {})
            print(f"  {v:<13} air env_corr {air.get('env_corr','-'):<6} "
                  f"presence env_corr {pres.get('env_corr','-'):<6} "
                  f"crest {air.get('crest_ret','-')} rolloff {s[v].get('rolloff_hz','-')}Hz")
        same_air = s.get("SAME", {}).get("air_8-16k", {}).get("env_corr")
        post_air = s.get("SAME+postnet", {}).get("air_8-16k", {}).get("env_corr")
        mp3_air = s.get("mp3_128", {}).get("air_8-16k", {}).get("env_corr")
        print(f"  HEADLINE air env_corr: SAME {same_air} -> SAME+postnet {post_air} "
              f"(mp3_128 {mp3_air})")
        diag = results[pop].get("phase_ceiling_diag")
        if diag:
            cs, cp = diag["hf_phase_coh_SAME"], diag["hf_phase_coh_SAME_postnet"]
            env_up = bool(post_air and same_air and post_air > same_air + 0.01)
            phase_up = cp > cs + 0.05                        # phase-coh meaningfully improved
            if not env_up and not phase_up:
                verdict = "[no effect — net changed neither env_corr nor phase-coh (undertrained/identity)]"
            elif env_up and not phase_up:
                verdict = "[CEILING HIT: env_corr up but phase-coh flat => regression ceiling => need generative]"
            else:
                verdict = "[phase-coh moved up => regression is recovering phase]"
            print(f"  #64 PHASE-CEILING: >7k phase-coh SAME {cs} -> postnet {cp} "
                  f"(air {same_air}->{post_air}) {verdict}")
    print(f"\n[done] -> {args.out}")


if __name__ == "__main__":
    main()
