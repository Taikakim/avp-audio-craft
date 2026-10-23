import os
import sys
import yaml
import time
import torch
import torchaudio
import soundfile as sf
import numpy as np

ROOT = "/home/kim/Projects/Separate-and-detect"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

from latent_diffusion.util import instantiate_from_config

def crossfade_stems(chunks, chunk_starts, total_samples, sr=16000):
    num_stems = chunks[0].shape[0]
    out = np.zeros((num_stems, total_samples), dtype=np.float32)
    weights = np.zeros((1, total_samples), dtype=np.float32)

    chunk_len = chunks[0].shape[1]
    fade_len = 5760
    taper = np.ones(chunk_len, dtype=np.float32)
    taper[:fade_len] = 0.5 * (1.0 - np.cos(np.pi * np.arange(fade_len) / fade_len))
    taper[-fade_len:] = 0.5 * (1.0 + np.cos(np.pi * np.arange(fade_len) / fade_len))

    for chunk, start in zip(chunks, chunk_starts):
        end = min(start + chunk_len, total_samples)
        valid_len = end - start
        w = taper[:valid_len]
        out[:, start:end] += chunk[:, :valid_len] * w
        weights[:, start:end] += w

    weights = np.maximum(weights, 1e-8)
    out = out / weights
    return out

def process_track(model, track_dir, config, device, ddim_steps=50):
    drum_file = os.path.join(track_dir, "bs_roformer_sw_drums.wav")
    if not os.path.exists(drum_file):
        print(f"Skipping {track_dir}, no bs_roformer_sw_drums.wav")
        return

    track_id = os.path.basename(track_dir)
    print(f"\n==========================================")
    print(f"Processing track: {track_id}")
    print(f"==========================================")

    data, orig_sr = sf.read(drum_file, dtype='float32')
    if data.ndim > 1:
        data = np.mean(data, axis=1)

    tensor_data = torch.from_numpy(data).unsqueeze(0)
    if orig_sr != 16000:
        resampler = torchaudio.transforms.Resample(orig_sr, 16000)
        tensor_data = resampler(tensor_data)
    audio_16k = tensor_data.squeeze(0).numpy()
    total_samples = len(audio_16k)

    chunk_len = 163840
    chunk_starts = [0, 158080, total_samples - chunk_len]

    mel_config = config["data"]["params"]["preprocessing"]["mel"]
    stft_config = config["data"]["params"]["preprocessing"]["stft"]

    mel_transform = torchaudio.transforms.MelSpectrogram(
        sample_rate=16000,
        n_fft=stft_config['filter_length'],
        hop_length=stft_config['hop_length'],
        win_length=stft_config['win_length'],
        n_mels=mel_config['n_mel_channels'],
        f_min=mel_config['mel_fmin'],
        f_max=mel_config['mel_fmax']
    )

    chunks = []
    with torch.no_grad():
        for i, start in enumerate(chunk_starts):
            chunk_wav = audio_16k[start:start+chunk_len]
            if len(chunk_wav) < chunk_len:
                chunk_wav = np.pad(chunk_wav, (0, chunk_len - len(chunk_wav)))
            
            chunk_tensor = torch.from_numpy(chunk_wav).float()
            mel_spec = mel_transform(chunk_tensor)
            mel_spec = torch.log(mel_spec + 1e-9)
            if mel_spec.shape[1] > mel_config['target_length']:
                mel_spec = mel_spec[:, :mel_config['target_length']]
            elif mel_spec.shape[1] < mel_config['target_length']:
                mel_spec = torch.nn.functional.pad(mel_spec, (0, mel_config['target_length'] - mel_spec.shape[1]))
            fbank = mel_spec.transpose(0, 1).numpy()

            fbank_stems = np.zeros((5, fbank.shape[0], fbank.shape[1]), dtype=np.float32)
            waveform_stems = np.zeros((5, chunk_len), dtype=np.float32)

            chunk_batch = {
                "fbank": torch.from_numpy(fbank).unsqueeze(0).to(device),
                "fbank_stems": torch.from_numpy(fbank_stems).unsqueeze(0).to(device),
                "waveform": torch.from_numpy(chunk_wav).unsqueeze(0).to(device),
                "waveform_stems": torch.from_numpy(waveform_stems).unsqueeze(0).to(device),
                "fname": [f"{track_id}_chunk_{i}"]
            }

            inputs = model.get_input(
                chunk_batch,
                model.first_stage_key,
                return_first_stage_encode=True,
                return_first_stage_outputs=False,
                force_c_encode=True,
                return_original_cond=False,
                bs=1
            )
            c = inputs[1]

            t0 = time.time()
            samples, _ = model.sample_log(
                cond=c,
                batch_size=1,
                ddim=True,
                ddim_steps=ddim_steps,
                eta=1.0,
                unconditional_guidance_scale=1.0,
                unconditional_conditioning=None,
                use_plms=False
            )
            samples_adapted = model.adapt_latent_for_VAE_decoder(samples)
            mel = model.decode_first_stage(samples_adapted)
            waveform = model.mel_spectrogram_to_waveform(
                mel, savepath="/tmp", bs=None, name=chunk_batch["fname"], save=False
            )
            chunk_stems = waveform[:, 0, :chunk_len]
            chunks.append(chunk_stems)
            torch.cuda.empty_cache()
            print(f"  Chunk {i+1}/3 finished in {time.time()-t0:.2f}s")

    print(f"Stitching full 30s stems for {track_id}...")
    full_stems = crossfade_stems(chunks, chunk_starts, total_samples, sr=16000)

    stem_names = ['kick', 'snare', 'toms', 'hi_hats', 'cymbals']
    recombined = np.zeros(total_samples, dtype=np.float32)

    for i, sname in enumerate(stem_names):
        swav = full_stems[i]
        out_file = os.path.join(track_dir, f"msgld_{sname}.wav")
        sf.write(out_file, swav, 16000)
        rms = np.sqrt(np.mean(swav**2))
        print(f"  Saved {sname}.wav: RMS = {rms:.4f}")
        recombined += swav

    recomb_file = os.path.join(track_dir, "msgld_recombined.wav")
    sf.write(recomb_file, recombined, 16000)
    print(f"  Saved msgld_recombined.wav: RMS = {np.sqrt(np.mean(recombined**2)):.4f}")

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    config_path = os.path.join(ROOT, "config/MSG-LD/integrated_musicldm_test_inference.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    ckpt_dir = "/run/media/kim/Mantu/checkpoints/separate_and_detect"
    config["model"]["params"]["first_stage_config"]["params"]["reload_from_ckpt"] = os.path.join(ckpt_dir, "vae-ckpt.ckpt")
    config["model"]["params"]["first_stage_config"]["params"]["ddconfig"]["hifigan_ckpt"] = os.path.join(ckpt_dir, "hifigan-ckpt.ckpt")

    print("Instantiating MusicLDM_multitask...")
    model = instantiate_from_config(config["model"])
    msgld_path = os.path.join(ckpt_dir, "msgld_obtb.ckpt")
    model.init_from_ckpt(msgld_path)
    model.to(device)
    model.eval()

    tracks = [
        "astral_mahadeva",
        "black_moon",
        "cosmosis_alien_disco",
        "goddess_guerrilla",
        "mfg_shape_future"
    ]
    base_audio_dir = "/home/kim/sao_runs/drum_sep_comparison/listen/audio"

    t_start = time.time()
    for track_id in tracks:
        track_dir = os.path.join(base_audio_dir, track_id)
        process_track(model, track_dir, config, device, ddim_steps=50)

    print(f"\n==========================================")
    print(f"ALL TRACKS COMPLETED IN {time.time()-t_start:.2f}s!")
    print(f"==========================================")

if __name__ == "__main__":
    main()
