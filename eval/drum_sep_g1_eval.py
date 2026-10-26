#!/usr/bin/env python3
"""Gate G1 of the SA3 Drum Separator Plan (audio-tools-avp scripts/synth_inversion/DRUM_SEPARATION_SA3_PLAN.md):
Zero-training baselines on SA3 Medium Base:
(a) Text-only generation of isolated kit pieces ("solo kick drum, 140 BPM", etc.)
(b) SDEdit on the real drum bus with stem prompts across init_noise_level in [0.3, 0.5, 0.7]
(c) ZeroSep-style reverse rectified-flow ODE inversion on the bus + forward steering under stem prompts
"""

import os
import json
import argparse
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
import torchaudio

from stable_audio_3 import StableAudioModel
from scripts.drum_sep.codec_ceiling import lsd_db, mrstft, si_sdr_db, detect_onsets, match_onsets, attack_db, SR

OUT_DIR = Path("/home/kim/sao_runs/drum_sep_g1")
MULTITRACKS_DIR = Path("/home/kim/sao_runs/drum_sep_g0_multitracks")

PROMPTS_G1A = [
    ("solo_kick", "solo kick drum, 140 BPM, punchy goa trance kick, dry isolated hit"),
    ("solo_snare", "solo snare drum, 140 BPM, punchy acoustic snare, dry isolated hit"),
    ("solo_hihats", "solo hi-hats loop, 140 BPM, offbeat open and closed hi-hats, dry"),
    ("solo_cymbals", "solo cymbals crash, 140 BPM, bright hall reverb, isolated"),
    ("solo_percussion", "solo percussion loop, 140 BPM, tribal congas and bongo, dry"),
]

SDEDIT_NOISE_LEVELS = [0.3, 0.5, 0.7]

def run_g1a(model, out_audio_dir, duration=12.0, steps=50, cfg_scale=7.0, seeds=(1234, 77)):
    """(a) Test if the frozen prior can make isolated drum kit pieces."""
    print("\n--- Gate G1(a): Text-to-Audio Solo Kit Pieces ---")
    results = []
    for tag, prompt in PROMPTS_G1A:
        for seed in seeds:
            fname = f"g1a_{tag}_cfg{int(cfg_scale)}_s{seed}.wav"
            fpath = out_audio_dir / fname
            if fpath.exists():
                print(f"Loading existing {fname}...")
                y, _ = sf.read(str(fpath), dtype="float32", always_2d=True)
                y = y.T
            else:
                print(f"Generating {tag} (seed {seed}, cfg {cfg_scale})...")
                audio = model.generate(
                    prompt=prompt,
                    negative_prompt="bassline, melody, synth, music, vocals, harmony, chord, noisy mix",
                    duration=duration,
                    steps=steps,
                    cfg_scale=cfg_scale,
                    seed=seed,
                    batch_size=1
                )
                # audio is (C, T) or (1, C, T)
                y = audio.squeeze(0).cpu().numpy() if audio.ndim == 3 else audio.cpu().numpy()
                sf.write(str(fpath), y.T, SR, subtype="PCM_16")
            
            # Simple activity check: RMS and spectral flatness
            rms = float(np.sqrt(np.mean(y**2)))
            onsets = detect_onsets(y.mean(0), SR)
            results.append({
                "tag": tag,
                "seed": seed,
                "prompt": prompt,
                "file": fname,
                "rms": rms,
                "n_onsets": len(onsets)
            })
            print(f"  -> {fname}: RMS {rms:.4f}, onsets {len(onsets)}")
    return results

def run_g1b(model, song_name, bus_wav_path, gt_stems, out_audio_dir, duration=12.0, steps=50):
    """(b) SDEdit on the real drum bus with stem prompts across noise levels."""
    print(f"\n--- Gate G1(b): SDEdit on Drum Bus ({song_name}) ---")
    wav, sr = torchaudio.load(str(bus_wav_path))
    init_audio = (sr, wav)
    
    stem_prompts = [
        ("kick", "solo kick drum, 140 BPM, punchy goa trance kick, dry isolated"),
        ("hihat", "solo hi-hats loop, 140 BPM, offbeat hi-hats, dry isolated"),
        ("snare", "solo snare drum, 140 BPM, punchy snare, dry isolated"),
    ]
    
    results = []
    for stem_tag, prompt in stem_prompts:
        for noise_lvl in SDEDIT_NOISE_LEVELS:
            fname = f"g1b_{song_name}_sdedit_{stem_tag}_nl{int(noise_lvl*100)}_s1234.wav"
            fpath = out_audio_dir / fname
            if fpath.exists():
                print(f"Loading existing {fname}...")
                y_arr, _ = sf.read(str(fpath), dtype="float32", always_2d=True)
                y = y_arr.T
            else:
                print(f"SDEdit {song_name} -> {stem_tag} (noise {noise_lvl})...")
                audio = model.generate(
                    init_audio=init_audio,
                    init_noise_level=noise_lvl,
                    prompt=prompt,
                    negative_prompt="bassline, melody, background synths, harmony, clutter",
                    duration=duration,
                    steps=steps,
                    cfg_scale=5.0,
                    seed=1234,
                    batch_size=1
                )
                y = audio.squeeze(0).cpu().numpy() if audio.ndim == 3 else audio.cpu().numpy()
                sf.write(str(fpath), y.T, SR, subtype="PCM_16")
            
            # Evaluate against GT if matching GT stem exists
            gt_wav = gt_stems.get(stem_tag)
            res_entry = {
                "song": song_name,
                "stem_tag": stem_tag,
                "noise_lvl": noise_lvl,
                "file": fname,
                "rms": float(np.sqrt(np.mean(y**2)))
            }
            if gt_wav is not None:
                n = min(y.shape[1], gt_wav.shape[1])
                est_mono, ref_mono = y.mean(0)[:n], gt_wav.mean(0)[:n]
                res_entry["lsd_db"] = lsd_db(ref_mono, est_mono)
                res_entry["mrstft"] = mrstft(ref_mono, est_mono)
                res_entry["si_sdr_db"] = si_sdr_db(ref_mono, est_mono)
                on_r, on_e = detect_onsets(ref_mono, SR), detect_onsets(est_mono, SR)
                _, _, f1_20, _ = match_onsets(on_r, on_e, 0.020)
                res_entry["onset_f1_20"] = float(f1_20)
                res_entry["attack_db"] = attack_db(ref_mono, est_mono, on_r, SR)
                print(f"  -> {fname}: LSD {res_entry['lsd_db']:.1f} dB, SI-SDR {res_entry['si_sdr_db']:.1f} dB, F1@20 {res_entry['onset_f1_20']:.2f}")
            else:
                print(f"  -> {fname}: RMS {res_entry['rms']:.4f}")
            results.append(res_entry)
    return results

def run_g1c_flow_inversion(model, song_name, bus_wav_path, gt_stems, out_audio_dir, duration=12.0, steps=40):
    """(c) ZeroSep-style reverse ODE inversion along rectified-flow trajectory."""
    print(f"\n--- Gate G1(c): Flow Inversion ({song_name}) ---")
    ae = model.model.pretransform
    device = model.device
    
    y, fs = sf.read(str(bus_wav_path), dtype="float32", always_2d=True)
    if fs != SR:
        y = librosa.resample(y.T, orig_sr=fs, target_sr=SR).T
    model_dtype = next(model.model.parameters()).dtype
    y_crop = y[:int(duration * SR)]
    y_t = torch.as_tensor(y_crop.T, dtype=model_dtype).unsqueeze(0).to(device) # (1, C, T)
    
    with torch.inference_mode():
        z0 = ae.encode(y_t) # (1, D, T_lat)
    
    # Invert z0 -> z1 along the reverse ODE (dt > 0)
    dt = 1.0 / steps
    t_steps = torch.linspace(0.0, 1.0, steps + 1, device=device, dtype=model_dtype)
    
    # Prepare inpaint masks for conditioning
    mask = torch.zeros((1, 1, z0.shape[-1]), device=device, dtype=model_dtype)
    inpaint_input = torch.zeros((1, 256, z0.shape[-1]), device=device, dtype=model_dtype)
    
    cond_neutral = model.model.conditioner(
        [{"prompt": "drums, drum bus, percussive track", "seconds_total": duration}],
        device=device
    )
    cond_neutral["inpaint_mask"] = [mask]
    cond_neutral["inpaint_masked_input"] = [inpaint_input]
    cond_inputs_neutral = model.model.get_conditioning_inputs(cond_neutral)
    
    print("Inverting drum bus latent from t=0.0 to t=1.0...")
    z = z0.clone()
    with torch.inference_mode():
        for i in range(steps):
            t_curr = t_steps[i].repeat(1)
            v = model.model.model(z, t_curr, **cond_inputs_neutral)
            z = z + v * dt
    z_inverted = z.clone()
    
    # Re-integrate forward from z_inverted (t=1.0 -> t=0.0) under stem prompts
    stem_prompts = [
        ("kick", "solo kick drum, 140 BPM, punchy goa trance kick, dry isolated"),
        ("hihat", "solo hi-hats loop, 140 BPM, offbeat hi-hats, dry isolated"),
    ]
    
    results = []
    for stem_tag, prompt in stem_prompts:
        fname = f"g1c_{song_name}_zerosig_{stem_tag}_steps{steps}.wav"
        fpath = out_audio_dir / fname
        if fpath.exists():
            print(f"Loading existing {fname}...")
            y_arr, _ = sf.read(str(fpath), dtype="float32", always_2d=True)
            rec_audio = y_arr.T
        else:
            cond_stem = model.model.conditioner(
                [{"prompt": prompt, "seconds_total": duration}],
                device=device
            )
            cond_stem["inpaint_mask"] = [mask]
            cond_stem["inpaint_masked_input"] = [inpaint_input]
            cond_inputs_stem = model.model.get_conditioning_inputs(cond_stem)
            
            print(f"Re-integrating forward (t=1.0 -> 0.0) under {stem_tag} prompt...")
            z_fwd = z_inverted.clone()
            with torch.inference_mode():
                for i in range(steps, 0, -1):
                    t_curr = t_steps[i].repeat(1)
                    v = model.model.model(z_fwd, t_curr, **cond_inputs_stem)
                    z_fwd = z_fwd - v * dt
                
                # Decode reconstructed stem
                rec_audio = ae.decode(z_fwd).squeeze(0).cpu().float().numpy() # (C, T)
            
            sf.write(str(fpath), rec_audio.T, SR, subtype="PCM_16")
        
        gt_wav = gt_stems.get(stem_tag)
        res_entry = {
            "song": song_name,
            "stem_tag": stem_tag,
            "method": "flow_inversion",
            "file": fname,
            "rms": float(np.sqrt(np.mean(rec_audio**2)))
        }
        if gt_wav is not None:
            n = min(rec_audio.shape[1], gt_wav.shape[1])
            est_mono, ref_mono = rec_audio.mean(0)[:n], gt_wav.mean(0)[:n]
            res_entry["lsd_db"] = lsd_db(ref_mono, est_mono)
            res_entry["mrstft"] = mrstft(ref_mono, est_mono)
            res_entry["si_sdr_db"] = si_sdr_db(ref_mono, est_mono)
            on_r, on_e = detect_onsets(ref_mono, SR), detect_onsets(est_mono, SR)
            _, _, f1_20, _ = match_onsets(on_r, on_e, 0.020)
            res_entry["onset_f1_20"] = float(f1_20)
            res_entry["attack_db"] = attack_db(ref_mono, est_mono, on_r, SR)
            print(f"  -> {fname}: LSD {res_entry['lsd_db']:.1f} dB, SI-SDR {res_entry['si_sdr_db']:.1f} dB, F1@20 {res_entry['onset_f1_20']:.2f}")
        results.append(res_entry)
        
    return results

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    audio_dir = OUT_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    
    print("Loading StableAudioModel ('medium-base') on GPU...")
    model = StableAudioModel.from_pretrained("medium-base")
    print(f"Model ready on {model.device}.")
    
    # 1. Gate G1(a): Text-to-audio solo kit pieces
    g1a_res = run_g1a(model, audio_dir)
    
    # 2. Gate G1(b) and G1(c) on benchmark tracks
    g1b_res, g1c_res = [], []
    for song in ["goddess_guerrilla", "acid_alien"]:
        song_dir = MULTITRACKS_DIR / song
        if not song_dir.exists():
            continue
        
        # Build bus and load GT stems
        stems = {}
        for p in sorted(song_dir.glob("*.wav")):
            y, _ = sf.read(str(p), dtype="float32", always_2d=True)
            stems[p.stem] = y.T # (C, T)
        bus = np.sum(list(stems.values()), axis=0)
        bus_wav_path = audio_dir / f"{song}__bus.wav"
        sf.write(str(bus_wav_path), bus.T, SR, subtype="PCM_16")
        
        # Run SDEdit
        res_b = run_g1b(model, song, bus_wav_path, stems, audio_dir)
        g1b_res.extend(res_b)
        
        # Run Flow Inversion
        res_c = run_g1c_flow_inversion(model, song, bus_wav_path, stems, audio_dir)
        g1c_res.extend(res_c)
        
    # Write summary results
    summary = {
        "g1a_solo_pieces": g1a_res,
        "g1b_sdedit": g1b_res,
        "g1c_flow_inversion": g1c_res
    }
    (OUT_DIR / "results.json").write_text(json.dumps(summary, indent=2))
    
    # Write report.md
    report_lines = [
        "# SA3 Drum Separator — Gate G1 Zero-Training Evaluation Report",
        "",
        "## G1(a): Text-to-Audio Solo Kit Pieces (Prior Quality)",
        "| Tag | Seed | RMS | Onsets | Prompt |",
        "|---|---|---|---|---|"
    ]
    for r in g1a_res:
        report_lines.append(f"| {r['tag']} | {r['seed']} | {r['rms']:.4f} | {r['n_onsets']} | `{r['prompt']}` |")
        
    report_lines.extend([
        "",
        "## G1(b): SDEdit on Real Drum Bus (Partial Noise Denoising)",
        "| Song | Stem Target | Noise Level | LSD (dB) | SI-SDR (dB) | Onset F1 @ 20ms | Attack (dB) |",
        "|---|---|---|---|---|---|---|"
    ])
    for r in g1b_res:
        lsd = f"{r.get('lsd_db', 0):.2f}" if "lsd_db" in r else "N/A"
        si_sdr = f"{r.get('si_sdr_db', 0):.2f}" if "si_sdr_db" in r else "N/A"
        f1 = f"{r.get('onset_f1_20', 0):.2f}" if "onset_f1_20" in r else "N/A"
        atk = f"{r.get('attack_db', 0):+.2f}" if "attack_db" in r else "N/A"
        report_lines.append(f"| {r['song']} | {r['stem_tag']} | {r['noise_lvl']} | {lsd} | {si_sdr} | {f1} | {atk} |")
        
    report_lines.extend([
        "",
        "## G1(c): Rectified Flow Inversion (ZeroSep-Style Reverse ODE)",
        "| Song | Stem Target | Steps | LSD (dB) | SI-SDR (dB) | Onset F1 @ 20ms | Attack (dB) |",
        "|---|---|---|---|---|---|---|"
    ])
    for r in g1c_res:
        lsd = f"{r.get('lsd_db', 0):.2f}" if "lsd_db" in r else "N/A"
        si_sdr = f"{r.get('si_sdr_db', 0):.2f}" if "si_sdr_db" in r else "N/A"
        f1 = f"{r.get('onset_f1_20', 0):.2f}" if "onset_f1_20" in r else "N/A"
        atk = f"{r.get('attack_db', 0):+.2f}" if "attack_db" in r else "N/A"
        report_lines.append(f"| {r['song']} | {r['stem_tag']} | 40 | {lsd} | {si_sdr} | {f1} | {atk} |")
        
    (OUT_DIR / "report.md").write_text("\n".join(report_lines) + "\n")
    print("\nGate G1 Evaluation complete! Report written to:", OUT_DIR / "report.md")

if __name__ == "__main__":
    main()
