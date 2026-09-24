#!/usr/bin/env python
"""dj_beatmatch.py — beat-aware crop correction + asymmetric DJ-style pre-bending
for a long-overlay mix between two short SA3-generated clips (Kim, 2026-09-16).

WHY: chroma_morph_transitions.py / mixtape_seam_align_test.py already snap a
FIXED-tempo A/B pair together with a single bungee_stretch() call at the seam
(B follows A's BPM, ramped in over the crossfade window). That's a one-shot
correction applied entirely AT the seam. A real DJ doing a long overlay mix
instead does most of the tempo correction BEFORE the mix point, gradually and
inaudibly, so that by the time the two tracks are actually overlapping there
is much less tempo-correction work left to do in the blend itself — nudging
the outgoing track a little faster over many bars, and easing the incoming
track's tempo through whatever break/fill is available near its start, rather
than forcing the whole gap closed in one audible jump at the join. This module
implements that PRE-bending step (applied to each clip's tail/head BEFORE it
reaches the existing seam machinery), not a replacement for the seam itself:

  A (outgoing): prebend_outgoing() — nudges A's tempo toward B in small steps
      (bigger steps allowed at detected quiet points, where a step is less
      audible) so that by the mix point A has already moved up to
      `max_bonus_bpm` of tempo toward B (either direction — A may need to
      slow down, not just speed up, depending on which side of B it's on).
  B (incoming): prebend_incoming() — starts BELOW its own native tempo and
      ramps up to the meeting tempo (typically A's post-prebend tempo),
      with the bulk of that ramp concentrated in a caller-supplied
      break/fill window near B's start, where a bigger tempo move is
      easiest to hide.

Both halves are asymmetric on purpose: A is nudged gently over a long
runway (it's already committed, playing to an audience), B gets a bigger,
faster correction because it hasn't "landed" yet and a break/fill gives
cover for it. After both are pre-bent, whatever machinery does the actual
seam (chroma_morph_transitions.bungee_stretch's own ramp_to, downbeat_near,
fine_align_shift, the crossfade window) still runs on the pre-bent clips —
it just has a smaller residual tempo gap left to close.

Prior-art check (per task instructions): grepped DISCOVERIES.md, ARCHITECTURE.md,
WORKLOG.md and profiles/*.journal.md case-insensitively for "prebend", "pre-bend",
"gradual.*tempo", "dj.*pitch.*bend", "beatmatch". Found ONE-SHOT beatmatch/pitch-bend
work (chroma_morph_transitions.py's bungee_stretch ramp_to/ramp_out_sec — matches
tempo then relaxes back to native OVER the crossfade window, all at the seam; the
2026-06-18 WORKLOG InfiniteAudio-FIFO note's "beatmatch_crossfade_to_wav" is the
same one-shot family) but nothing that pre-bends EITHER clip gradually before the
mix point, and nothing with quiet-point-aware step sizing or an asymmetric
outgoing/incoming schedule. This module is new work, not a duplicate.

Everything here is CPU-only (numpy/scipy/soundfile/librosa + a bungee subprocess
into the mir venv, and a madmom subprocess into the mir venv's OWN python). No
torch, no SA3 model, no GPU. Speed convention throughout matches
chroma_morph_transitions.bungee_stretch: `speed` is a tempo-stretch RATIO fed to
bungee's Bungee.set_speed() — >1 speeds up (raises effective BPM), <1 slows down,
pitch is preserved (bungee time-stretches, it does not resample/vari-pitch).
"""
import os

os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, "/home/kim/Projects/SAO/eval")
from chroma_morph_transitions import MIR_VENV_PY  # noqa: E402  (bungee_python subprocess venv)

# madmom lives ONLY in the mir venv (mir/bin/python) — NOT mir/.venv (numpy 2.x,
# lacks essentia, madmom import silently degrades). Separate constant from
# MIR_VENV_PY above on purpose; the two are different interpreters.
MIR_MADMOM_PY = "/home/kim/Projects/mir/mir/bin/python"
MIR_REPO_ROOT = "/home/kim/Projects/mir"


# --------------------------------------------------------------------------
# downbeat detection (madmom, mir venv) + nearest-neighbor snap
# --------------------------------------------------------------------------

def madmom_downbeats(audio, sr) -> list[float]:
    """Downbeat timestamps (seconds, sorted) for `audio` via madmom, run in the
    mir venv as a subprocess.

    `audio`: numpy array, (channels, samples) or (samples,).

    Reuses the mir repo's `src.rhythm.beat_grid` CLI (`python -m
    src.rhythm.beat_grid <file> --method madmom`, cwd=mir repo root) rather
    than re-deriving a madmom call. KNOWN BUG in that CLI (see CONTEXT):
    single-file mode names its output sidecar after the containing FOLDER,
    not the input file (`<folder>.DOWNBEATS` next to `<folder>.BEATS_GRID`)
    — unsafe with multiple audio files in one directory. Worked around here
    by writing `audio` into its OWN fresh temp directory (exactly one file
    per dir) and reading back `<tempdir-name>.DOWNBEATS` from that same dir.

    Returns an empty list (does not raise) if the clip is too short/quiet for
    madmom to find any downbeats, or if the subprocess fails outright —
    callers (snap_downbeat included) tolerate "no downbeat info" as a no-op.
    """
    a = np.asarray(audio, dtype=np.float32)
    if a.ndim == 1:
        a = a[None, :]

    with tempfile.TemporaryDirectory(prefix="madmom_") as td:
        tdir = Path(td)
        wav_path = tdir / "clip.wav"
        sf.write(str(wav_path), a.T, sr)  # soundfile wants (samples, channels)

        proc = subprocess.run(
            [MIR_MADMOM_PY, "-m", "src.rhythm.beat_grid", str(wav_path), "--method", "madmom"],
            cwd=MIR_REPO_ROOT, capture_output=True, text=True,
        )
        # CLI writes {folder_name}.DOWNBEATS next to the input; folder_name is
        # the temp dir's own basename (tdir.name), not the wav's stem.
        downbeats_path = tdir / f"{tdir.name}.DOWNBEATS"
        if not downbeats_path.exists():
            if proc.returncode != 0:
                print(f"[madmom_downbeats] beat_grid subprocess failed (rc={proc.returncode}): "
                      f"{proc.stderr[-2000:]}", file=sys.stderr)
            return []

        times = np.loadtxt(str(downbeats_path))
        if times.ndim == 0:
            times = np.array([float(times)])
        return sorted(float(t) for t in times)


def snap_downbeat(downbeats, target_sec) -> float:
    """Nearest downbeat timestamp to target_sec (plain nearest-neighbor over
    `downbeats`). Returns target_sec unchanged if `downbeats` is empty."""
    if not downbeats:
        return float(target_sec)
    arr = np.asarray(downbeats, dtype=np.float64)
    idx = int(np.argmin(np.abs(arr - target_sec)))
    return float(arr[idx])


# --------------------------------------------------------------------------
# quiet-point detection (where a bigger pre-bend step is less audible)
# --------------------------------------------------------------------------

def detect_quiet_points(audio, sr, hop_sec=0.5) -> list[float]:
    """Timestamps (seconds, sorted ascending) of local RMS minima, at
    `hop_sec` resolution — candidate spots for a bigger pre-bend step (a
    tempo nudge is less audible where the material is already quiet/sparse).

    Plain windowed RMS (not onset-strength): a pre-bend step is a speed
    discontinuity, which is masked by low ENERGY generally, not specifically
    by onset absence — RMS is the more direct proxy for "how much is there to
    disturb right now". Frame length is 2x hop for a bit of overlap/smoothing
    so single-sample RMS noise doesn't manufacture spurious minima.

    Returns [] if the clip is too short to have any interior local minimum
    (e.g. shorter than ~3 hops) — callers must handle an empty list (no quiet
    points found ⇒ fall back to uniform stepping).
    """
    import librosa
    from scipy.signal import argrelmin

    mono = audio if audio.ndim == 1 else audio.mean(axis=0)
    hop = max(1, int(round(hop_sec * sr)))
    frame_length = 2 * hop
    if len(mono) < 3 * hop:
        return []

    rms = librosa.feature.rms(y=mono, frame_length=frame_length, hop_length=hop)[0]
    times = librosa.times_like(rms, sr=sr, hop_length=hop)
    if len(rms) < 3:
        return []

    (minima_idx,) = argrelmin(rms, order=1)
    return [float(times[i]) for i in minima_idx]


# --------------------------------------------------------------------------
# shared bungee-streaming helper: arbitrary piecewise speed schedule
# --------------------------------------------------------------------------

def _bungee_stretch_schedule(audio, sr, times, speeds) -> np.ndarray:
    """Internal. Generalizes chroma_morph_transitions.bungee_stretch's single
    two-point linear ramp to an arbitrary PIECEWISE-LINEAR speed schedule,
    keeping the exact same streaming pattern: subprocess into the mir venv,
    bungee_python's Bungee(sample_rate, channels).set_speed()/.process() in a
    0.25s-chunked loop, speed re-evaluated every chunk. The only change from
    bungee_stretch is that interpolation is `np.interp(out_sec, times,
    speeds)` instead of a single (speed0 -> ramp_to) lerp.

    `times`: OUTPUT-time breakpoints in seconds (matches bungee_stretch's own
    `out_sec` bookkeeping — cumulative PROCESSED-output duration so far, not
    input-domain time). Must be sorted ascending. `speeds`: the tempo-stretch
    ratio at each breakpoint (same convention as bungee_stretch's `speed`
    arg: >1 speeds up, <1 slows down, pitch preserved). Before the first
    breakpoint / after the last, speed holds constant (numpy's default
    out-of-range behaviour for interp).

    Returns the full re-stretched (channels, samples) array — length changes
    with the aggregate speed applied (see prebend_outgoing/prebend_incoming
    docstrings for the exact convention each uses).
    """
    with tempfile.TemporaryDirectory() as td:
        src, dst = f"{td}/in.npy", f"{td}/out.npy"
        np.save(src, audio.T)  # (N, C) for bungee, matches bungee_stretch
        times_lit = repr([float(t) for t in times])
        speeds_lit = repr([float(s) for s in speeds])
        code = f"""
import numpy as np
from bungee_python import bungee as B
d = np.load({src!r}).astype(np.float32)
sr = {sr}
st = B.Bungee(sample_rate=sr, channels=d.shape[1])
times = np.array({times_lit}, dtype=np.float64)
speeds = np.array({speeds_lit}, dtype=np.float64)
chunk = int(0.25 * sr)
outs, out_sec = [], 0.0
for lo in range(0, d.shape[0], chunk):
    sp = float(np.interp(out_sec, times, speeds))
    st.set_speed(sp)
    y = np.asarray(st.process(d[lo:lo + chunk]), dtype=np.float32)
    if y.ndim == 1:
        y = y.reshape(-1, d.shape[1])
    outs.append(y)
    out_sec += y.shape[0] / sr
np.save({dst!r}, np.concatenate(outs, axis=0))
"""
        subprocess.run([MIR_VENV_PY, "-c", code], check=True, capture_output=True)
        return np.load(dst).T  # back to (C, N)


# --------------------------------------------------------------------------
# outgoing (A) — gradual speed-up in small steps, bigger steps at quiet points
# --------------------------------------------------------------------------

def prebend_outgoing(audio, sr, bpm, mix_point_sec, max_bonus_bpm=2.0,
                      normal_step=0.25, quiet_step=0.5) -> np.ndarray:
    """Track A (already playing, about to be mixed OUT): gradually moves its
    tempo TOWARD `bpm + max_bonus_bpm` via a series of small steps, using
    `normal_step`-sized BPM increments generally but snapping to (and using
    `quiet_step`-sized increments at) any detect_quiet_points() timestamp
    that falls near a nominal step time — a bigger tempo nudge hides better
    where the material is already quiet, so a candidate step is grown and
    moved there instead of firing at its evenly-spaced default time.

    `max_bonus_bpm` MAY BE NEGATIVE (2026-09-22: the caller now derives this
    from a signed gap to B — A can need to slow down, not just speed up, when
    B is the slower of the two). Step sizing/placement uses the MAGNITUDE;
    the sign only decides whether the schedule adds or subtracts from `bpm`.

    Step placement: `n_steps = round(max_bonus_bpm / normal_step)` nominal
    step times are laid out evenly across [0, mix_point_sec]; each is
    snapped to the nearest quiet point within half a nominal step-interval's
    tolerance (using quiet_step instead of normal_step there), otherwise left
    at its nominal time (using normal_step). The schedule is forced
    non-decreasing in time and always reaches exactly `max_bonus_bpm` by
    `mix_point_sec` (a final breakpoint is appended if the step loop
    undershoots, e.g. because normal_step doesn't evenly divide
    max_bonus_bpm).

    LENGTH CONVENTION: because A plays faster than 1x (speed = (bpm+bonus)/
    bpm > 1) on the way to and through the bend, the returned array is
    SHORTER, in samples, than the input by however much wall-clock time the
    speed-up saved overall — audio after `mix_point_sec` continues at the
    final bent tempo to the end of the input. `mix_point_sec` measured
    against the INPUT does not locate the mix point in the OUTPUT; the
    caller should re-run its own downbeat/onset detection on the returned
    audio (e.g. madmom_downbeats + snap_downbeat) rather than assume the
    timestamp carries over.
    """
    if audio.ndim == 1:
        audio = audio[None, :]
    duration = audio.shape[1] / sr
    mix_point_sec = float(min(mix_point_sec, duration))

    mag = abs(max_bonus_bpm)
    direction = 1.0 if max_bonus_bpm >= 0 else -1.0
    if mag <= 1e-9 or mix_point_sec <= 0:
        return audio.copy()

    n_steps = max(1, int(round(mag / normal_step)))
    nominal_times = np.linspace(0.0, mix_point_sec, n_steps + 1)[1:]
    tol = 0.5 * (mix_point_sec / n_steps)

    quiet = np.asarray(detect_quiet_points(audio, sr), dtype=np.float64)
    if quiet.size:
        quiet = quiet[(quiet > 0.0) & (quiet < mix_point_sec)]

    times = [0.0]
    bonus = [0.0]
    acc = 0.0
    for t_nom in nominal_times:
        if acc >= mag - 1e-9:
            break
        step = normal_step
        t_use = float(t_nom)
        if quiet.size:
            j = int(np.argmin(np.abs(quiet - t_nom)))
            if abs(quiet[j] - t_nom) <= tol:
                step, t_use = quiet_step, float(quiet[j])
        acc = min(mag, acc + step)
        t_use = max(t_use, times[-1] + 1e-3)  # keep the schedule monotonic
        times.append(t_use)
        bonus.append(acc)

    if bonus[-1] < mag - 1e-9:
        times.append(mix_point_sec)
        bonus.append(mag)
    if times[-1] < duration:
        times.append(duration)          # hold the fully-bent tempo to the end
        bonus.append(mag)

    speeds = [(bpm + direction * b) / bpm for b in bonus]
    return _bungee_stretch_schedule(audio, sr, times, speeds)


# --------------------------------------------------------------------------
# incoming (B) — starts below native tempo, ramps to target through a
# caller-supplied break/fill window
# --------------------------------------------------------------------------

def prebend_incoming(audio, sr, bpm, target_bpm, catch_up_center_sec,
                      catch_up_width_sec=3.0, start_undershoot_frac=0.3) -> np.ndarray:
    """Track B (incoming): STARTS slower than its own native `bpm`, then
    ramps up to `target_bpm` (typically A's post-prebend meeting tempo — see
    prebend_outgoing), with the bulk of the ramp concentrated in a window of
    width `catch_up_width_sec` centered on `catch_up_center_sec` (a detected
    break/fill near B's start — the CALLER locates it, this function only
    shapes the ramp around whatever center it's given).

    ASSUMPTION (the task text specifies "starts slower than native" and "bulk
    of the ramp in the window" but not the exact starting offset — flagging
    the choice made here so it can be overridden if Kim's ear disagrees):
    the flat lead-in speed is
        start_bpm = min(bpm, target_bpm) - start_undershoot_frac * abs(target_bpm - bpm)
    i.e. B is held BELOW *both* its own native tempo and the target tempo
    for the lead-in before the window (so "starts slower than native" holds
    literally regardless of whether target_bpm is above or below native),
    then ramps MONOTONICALLY (raised-cosine ease, so the speed change itself
    starts and ends gently rather than kinking at the window edges) from
    start_bpm up to target_bpm entirely inside the window, and holds at
    target_bpm from the window's end to the clip's end. This keeps the whole
    correction as ONE smooth motion inside the window rather than a two-stage
    undershoot/overshoot the spec doesn't pin down.

    Window degeneracy: if `catch_up_center_sec` is near enough to the start
    or end of the clip that the width-`catch_up_width_sec` window would
    invert, the window is clamped to the clip and made as wide as still fits
    — the ramp still lands at target_bpm by the clip's end.

    LENGTH CONVENTION: same as prebend_outgoing — output length reflects the
    aggregate speed applied and does not preserve input-domain timestamps;
    re-detect landmarks in the result rather than reusing input timestamps.
    """
    if audio.ndim == 1:
        audio = audio[None, :]
    duration = audio.shape[1] / sr

    start_bpm = min(bpm, target_bpm) - start_undershoot_frac * abs(target_bpm - bpm)
    start_speed = start_bpm / bpm
    end_speed = target_bpm / bpm

    half = max(catch_up_width_sec, 1e-3) / 2.0
    w_lo = max(0.0, min(catch_up_center_sec - half, duration))
    w_hi = max(0.0, min(catch_up_center_sec + half, duration))
    if w_hi <= w_lo:
        w_lo = max(0.0, duration - max(catch_up_width_sec, 1e-3))
        w_hi = duration

    n_inner = 9
    inner_t = np.linspace(w_lo, w_hi, n_inner)
    ease = 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, n_inner))
    inner_speed = start_speed + ease * (end_speed - start_speed)

    times = [0.0] + list(inner_t) + [duration]
    speeds = [start_speed] + list(inner_speed) + [end_speed]
    return _bungee_stretch_schedule(audio, sr, times, speeds)
