#!/usr/bin/env python3
"""Prepares clean 12-second dry drum stem multitracks from Kim's 40 classified multitrack projects
for the SA3 drum separator Gate G0 codec ceiling benchmark.
"""

import os
from pathlib import Path
import soundfile as sf
import numpy as np
import librosa

ROOT_CLASSIFIED = Path("/run/media/kim/Mantu/avp-stems-original-classified")
OUT_ROOT = Path("/home/kim/sao_runs/drum_sep_g0_multitracks")
SR = 44100
CROP_DUR_S = 12.0

SONGS = {
    "goddess_guerrilla": {
        "dir": "Aavepyörä - Goddess Guerrilla  goa morning bright energetic trance",
        "offset_s": 72.0,
        "stems": {
            "kick": "kick/KICK_downmix.flac",
            "snare": "punchy noisy snare hard medium bright room reverb 141 BPM.flac",
            "hihat": "offbeat hihat percussion dry 141 BPM.flac",
            "shaker": "percussion shaker various dry 141 BPM.flac",
            "perc_sampler": "phaser low feedback slow sweep percussion sampler dry 141 BPM.flac",
            "cowbell": "mild flanger positive feedback gated octave pads cowbell dry F phrygian F minor 141 BPM.flac",
        }
    },
    "acid_alien": {
        "dir": "Summamutikka - Acid Alien aggressive powerful psychedelic melodic goa trance",
        "offset_s": 48.0,
        "stems": {
            "kick": "kick/KICK_downmix.flac",
            "hihat_snare": "trance percussion offbeat open hihat, closed hihat, quiet snare 136 BPM.flac",
            "anvil_snare": "percussion amp distortion snare and anvil 136 BPM.flac",
            "breakbeat": "breakbeat and fx amp distortion 136 BPM.flac",
        }
    },
    "dance_of_tomorrow": {
        "dir": "Aavepyörä - Dance of Tomorrow driving rhythmic hypnotic  goatrance",
        "offset_s": 60.0,
        "stems": {
            "kick": "kick/KICK_downmix.flac",
            "cymbals_crash": "cymbals crash hall reverb.flac",
            "hihats_snare": "percussion hihats and snare room reverb 138 BPM.flac",
            "phaser_perc": "phaser percussion delay 138 BPM.flac",
        }
    },
    "kaapiosaaren_salaisuus": {
        "dir": "Aavepyörä - Kääpiösaaren Salaisuus electro upbeat electro trance",
        "offset_s": 84.0,
        "stems": {
            "kick": "kick/KICK_downmix.flac",
            "synthetic_clap": "synthetic clap dry 142 BPM.flac",
            "synthetic_hihat": "synthetic hihat silent slapback delay 142 BPM.flac",
            "open_hihat": "synthetic open hihat noisy small room reverb 142 BPM.flac",
            "cutup_breakbeat": "cut up breakbeat dry 142 BPM.flac",
        }
    },
    "kevahuuto": {
        "dir": "Aavepyörä - keväthuuto upbeat happy positive offbeat trance",
        "offset_s": 60.0,
        "stems": {
            "kick": "kick/KICK_downmix.flac",
            "closed_hihat": "closed hihat135 shuffle BPM.flac",
            "open_hihat": "offbeat open hihat slapback delay and reverb135 shuffle BPM.flac",
            "ride": "ride cymbal tiny room reverb135 shuffle BPM.flac",
            "pedal_crash": "pedal hihat and crash wet bright reverb135 shuffle BPM.flac",
            "toms": "sampler tom fills bright metallic reverb135 shuffle BPM.flac",
            "cowbell": "sampled cowbell bright medium room reverb135 shuffle BPM.flac",
            "breakbeat": "breakbeat flanger tweak heavy negatibe feedback bright reverb135 shuffle BPM.flac",
        }
    },
    "increase_the_dose": {
        "dir": "Summamutikka - Increase The Dose or Drop The Poison driving groovy upbeat goa trance",
        "offset_s": 24.0,
        "stems": {
            "kick": "kick/KICK_downmix.flac",
            "acoustic_snare": "acoustic snare and tambourine 142 BPM.flac",
            "flanged_perc": "flangered percussion tambourine and reverse snare 142 BPM.flac",
            "offbeat_hihat": "offbeat hihat trance pattern dry 142 BPM.flac",
            "phaser_perc": "phaser percussion 142 BPM.flac",
        }
    }
}

def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    crop_samples = int(CROP_DUR_S * SR)

    for song_name, meta in SONGS.items():
        song_dir = ROOT_CLASSIFIED / meta["dir"]
        song_out = OUT_ROOT / song_name
        song_out.mkdir(parents=True, exist_ok=True)
        offset_s = meta["offset_s"]
        start_samp = int(offset_s * SR)

        print(f"\nProcessing {song_name} (offset {offset_s}s)...")
        for stem_name, rel_path in meta["stems"].items():
            src_file = song_dir / rel_path
            if not src_file.exists():
                # check inside drums/ or kick/ if it was in parent
                if (song_dir / "drums" / rel_path).exists():
                    src_file = song_dir / "drums" / rel_path
                elif (song_dir / "kick" / rel_path).exists():
                    src_file = song_dir / "kick" / rel_path
                else:
                    print(f"  WARNING: {src_file} does not exist!")
                    continue

            y, fs = sf.read(str(src_file), dtype="float32", always_2d=True)
            if fs != SR:
                y = librosa.resample(y.T, orig_sr=fs, target_sr=SR).T

            # Crop
            end_samp = start_samp + crop_samples
            if len(y) < end_samp:
                crop = y[start_samp:]
                # pad if short
                if len(crop) < crop_samples:
                    crop = np.pad(crop, ((0, crop_samples - len(crop)), (0, 0)))
            else:
                crop = y[start_samp:end_samp]

            # Write stereo WAV (PCM 16)
            dst_wav = song_out / f"{stem_name}.wav"
            sf.write(str(dst_wav), crop, SR, subtype="PCM_16")
            rms = np.sqrt(np.mean(crop**2))
            print(f"  -> wrote {dst_wav.name:<18} (RMS: {rms:.4f}, shape: {crop.shape})")

    print("\nDataset staging complete at:", OUT_ROOT)

if __name__ == "__main__":
    main()
