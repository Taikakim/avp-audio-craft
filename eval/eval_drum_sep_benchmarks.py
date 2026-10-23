import os
import soundfile as sf
import numpy as np
import librosa

def calc_sdr_metrics(est_wav, ref_wav, sr):
    min_len = min(len(est_wav), len(ref_wav))
    est = est_wav[:min_len]
    ref = ref_wav[:min_len]

    max_lag = int(0.2 * sr)
    corr = np.correlate(est[:min(len(est), 10*sr)], ref[:min(len(ref), 10*sr)], mode='full')
    lag = np.argmax(corr) - (min(len(ref), 10*sr) - 1)
    if abs(lag) < max_lag and lag != 0:
        if lag > 0:
            est = est[lag:]
            ref = ref[:-lag]
        elif lag < 0:
            lag = abs(lag)
            est = est[:-lag]
            ref = ref[lag:]

    min_len = min(len(est), len(ref))
    est = est[:min_len]
    ref = ref[:min_len]

    alpha = np.dot(est, ref) / (np.dot(ref, ref) + 1e-8)
    e_target = alpha * ref
    e_res = est - e_target
    si_sdr = 10 * np.log10(np.sum(e_target**2) / (np.sum(e_res**2) + 1e-8))

    s_err = est - ref
    sdr = 10 * np.log10(np.sum(ref**2) / (np.sum(s_err**2) + 1e-8))
    return sdr, si_sdr

def eval_track(track_name, audio_dir):
    tdir = os.path.join(audio_dir, track_name)
    gt_file = os.path.join(tdir, "studio_ground_truth.wav")
    if not os.path.exists(gt_file):
        print(f"Skipping {track_name}: no studio GT")
        return None

    ref_gt, sr_gt = sf.read(gt_file, dtype='float32')
    if ref_gt.ndim > 1: ref_gt = np.mean(ref_gt, axis=1)
    ref_gt_16k = librosa.resample(ref_gt, orig_sr=sr_gt, target_sr=16000)

    models = {
        "BS-RoFormer SW (MIR)": ("bs_roformer_sw_drums.wav", 44100),
        "BS-RoFormer MUSDB18HQ": ("bs_roformer_zfturbo_drums.wav", 44100),
        "IDM Recombined": ("idm_recombined.wav", 44100),
        "MSG-LD Recombined": ("msgld_recombined.wav", 16000),
    }

    results = {}
    for mname, (fname, fsr) in models.items():
        fpath = os.path.join(tdir, fname)
        if not os.path.exists(fpath):
            continue
        est, esr = sf.read(fpath, dtype='float32')
        if est.ndim > 1: est = np.mean(est, axis=1)
        est_16k = librosa.resample(est, orig_sr=esr, target_sr=16000) if esr != 16000 else est
        sdr, si_sdr = calc_sdr_metrics(est_16k, ref_gt_16k, 16000)
        results[mname] = (sdr, si_sdr)

    # Kick sub-stem evaluation if studio_kick exists
    kick_file = os.path.join(tdir, "studio_kick.wav")
    if os.path.exists(kick_file):
        ref_k, sr_k = sf.read(kick_file, dtype='float32')
        if ref_k.ndim > 1: ref_k = np.mean(ref_k, axis=1)
        ref_k_16k = librosa.resample(ref_k, orig_sr=sr_k, target_sr=16000)

        idm_k_file = os.path.join(tdir, "idm_KD.wav")
        msgld_k_file = os.path.join(tdir, "msgld_kick.wav")

        if os.path.exists(idm_k_file):
            idm_k, sr_ik = sf.read(idm_k_file, dtype='float32')
            if idm_k.ndim > 1: idm_k = np.mean(idm_k, axis=1)
            idm_k_16k = librosa.resample(idm_k, orig_sr=sr_ik, target_sr=16000)
            results["IDM Kick"] = calc_sdr_metrics(idm_k_16k, ref_k_16k, 16000)

        if os.path.exists(msgld_k_file):
            msgld_k, sr_mk = sf.read(msgld_k_file, dtype='float32')
            if msgld_k.ndim > 1: msgld_k = np.mean(msgld_k, axis=1)
            results["MSG-LD Kick"] = calc_sdr_metrics(msgld_k, ref_k_16k, 16000)

    return results

def main():
    audio_base = "/home/kim/sao_runs/drum_sep_comparison/listen/audio"
    tracks = ["acid_alien", "black_moon", "goddess_guerrilla"]
    all_results = {}
    for t in tracks:
        res = eval_track(t, audio_base)
        if res:
            all_results[t] = res

    print("\n" + "="*80)
    print("COMPREHENSIVE SDR / SI-SDR BENCHMARK (Evaluated against Studio Ground Truth Multitracks)")
    print("="*80)
    print(f"{'Track':<20} | {'Model / Stem':<25} | {'SDR (dB)':<10} | {'SI-SDR (dB)':<12}")
    print("-" * 80)
    for track, mres in all_results.items():
        for mname, (sdr, si_sdr) in mres.items():
            print(f"{track:<20} | {mname:<25} | {sdr:>8.2f} dB | {si_sdr:>10.2f} dB")
        print("-" * 80)

if __name__ == "__main__":
    main()
