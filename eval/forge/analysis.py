"""Tempo, beats and downbeats for a clip (spec §6.3 POST /forge/analyze).

Downbeat phase = the loudest of the four candidate beat phases (peak RMS around each beat) —
the same idea as chroma_morph_transitions.downbeat_near, over the whole clip. No genre
tempo folding: the client offers bpm_candidates (t, 2t, t/2) instead.
"""
import numpy as np


def analyze_audio(audio, sr, bpm_hint=None) -> dict:
    import librosa

    y = np.asarray(audio, dtype=np.float32)
    mono = y.mean(axis=0) if y.ndim == 2 else y
    duration = mono.shape[0] / float(sr)
    beats = np.zeros(0)
    tempo_val = 120.0
    if np.any(mono):
        tempo, beats = librosa.beat.beat_track(y=mono, sr=sr, units="time", trim=False)
        beats = np.asarray(beats, dtype=np.float64)
        if len(beats) >= 8:
            # Beat times sit on librosa's 512-sample hop grid (23 ms at 22.05 kHz), so single-beat
            # gaps alternate between neighbouring frame counts and their median can be ~2% off the
            # true period (117.5 BPM for a 120 click track, found 2026-10-01). A span of k beats
            # divided by k shrinks that quantisation by k, and taking the MEDIAN of all such spans
            # keeps it robust to an occasional missed or doubled beat (a plain mean would not be).
            k = 8 if len(beats) >= 24 else 4
            spans = (beats[k:] - beats[:-k]) / k
            tempo_val = 60.0 / float(np.median(spans))
        elif np.size(tempo):
            tempo_val = float(np.atleast_1d(tempo)[0]) or 120.0
    downbeats = beats
    if len(beats) >= 8:
        # Downbeat = the phase (of four) whose beats are LOUDEST. Measured as peak RMS in a +-40 ms
        # window around each beat, in LINEAR amplitude. The earlier version sampled
        # librosa.onset.onset_strength at the beat, but that envelope is log-compressed, so a 3x
        # accent became a few dB and the four phase means sat within ~12% of each other (a click
        # track picked the wrong half-bar; found 2026-10-01). A heuristic either way -- the client
        # offers bpm_candidates and MATCH DOWNBEATS exists because this can be wrong on real music.
        hop = 256
        rms = librosa.feature.rms(y=mono, frame_length=1024, hop_length=hop)[0]
        rt = librosa.times_like(rms, sr=sr, hop_length=hop)

        def accent(b: float) -> float:
            sel = (rt >= b - 0.04) & (rt <= b + 0.04)
            return float(rms[sel].max()) if sel.any() else 0.0

        strength = np.array([accent(b) for b in beats])
        phase = int(np.argmax([strength[p::4].mean() for p in range(4)]))
        downbeats = beats[phase::4]
    bpm = float(bpm_hint) if bpm_hint else float(tempo_val)
    return {"bpm": round(bpm, 3),
            "bpm_candidates": [round(tempo_val, 3), round(2 * tempo_val, 3), round(tempo_val / 2, 3)],
            "beats_sec": [round(float(b), 4) for b in beats],
            "downbeats_sec": [round(float(b), 4) for b in downbeats],
            "duration_sec": round(duration, 3),
            "source": "sidecar" if bpm_hint else "librosa"}
