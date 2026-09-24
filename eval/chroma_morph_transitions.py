#!/usr/bin/env python
"""chroma_morph_transitions.py — real-track transitions with chroma-morph steering
(Kim 2026-07-07).

Pipeline per A->B pair:
  1. tempo-estimate both (librosa, octave-folded); BUNGEE-stretch B to A's BPM
     (mir/.venv subprocess — B always follows A)
  2. cut segments: A's tail region ending on a beat, B (stretched) from a
     beat-rich point, starting on a beat
  3. SAME-encode both; latent slerp crossfade of W frames at the junction
  4. graded a2a refine of the composite at the requested noise level, WITH the
     PROVEN stem-chroma LatCH head (latch_sa3_chroma_other_best, cosine, gain
     ~2048 — the WORKLOG 2026-06-25 pitch-steering band) guided by a MORPH
     target: A's measured same_chroma -> blend across the window -> B's.
     Guidance stops at 60% of steps (content locks mid-trajectory).

Uses the new model.py support: latch_configs target_raw + guided-path init_latents.
Chroma targets via mir-same-chroma's compute_same_chroma (numpy/scipy, imported).
"""
import os
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

sys.path.insert(0, "/home/kim/Projects/SAO/control")
sys.path.insert(0, "/home/kim/Projects/mir-same-chroma/src")
from sa3_control.audio_io import save_audio  # noqa: E402
from harmonic.same_chroma import compute_same_chroma  # noqa: E402
from stable_audio_3 import StableAudioModel  # noqa: E402
from stable_audio_3.inference.longform import slerp  # noqa: E402

FPS = 44100 / 4096
# NOTE 2026-09-15: "Mantu1" was an old mount label; the drive was consolidated
# into "Mantu" at some point and Mantu1 no longer exists. Paths below fixed to
# match current mounts (verified present under Mantu).
CHROMA_HEAD = ("/run/media/kim/Mantu/sa3_lora_runs/cu_reward_renders/analysis/"
               "chroma_heads/latch_sa3_chroma_other_best.pt")
CHROMA_GAIN = 2048.0
MIR_VENV_PY = "/home/kim/Projects/mir/.venv/bin/python"

TRACKS = {
    "kaikki":  "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/avp-flac/009 goddess guerrilla (2006)/Aavepyora - Goddess Guerilla - Kaikki-Alla.flac",
    "angelic": "/run/media/kim/Mantu/ai-music/Goa Dataset/0934. Hallucinogen - Angelic Particles (Remastered 2024).flac",
    "vapaus":  "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/avp-flac/009 goddess guerrilla (2006)/Aavepyora - Goddess Guerilla - Vapausvoima.flac",
    # 2026-07-07 evening set (Kim): in-dataset goa + the acid-rock experiment
    "phreaky": "/run/media/kim/Mantu/ai-music/Goa Dataset/0818. Phreaky - Techno Prisioners (Rework 2022).flac",
    "heron":   "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/ai-music2/Playlists/Acid Rock/14. Heron Oblivion - Beneath Fields.m4a",
    # 2026-09-15 (Kim, for the Kone portfolio): both tracks are Kim's own.
    "ruoste":   "/run/media/kim/Mantu/avp-stems-original-classified/Kadonneet maat - Ruoste organic techno/full mix 126 BPM.flac",
    "tomorrow": "/run/media/kim/Lehto/avp-analyzed-stems/Aavepyora - Goddess Guerilla - Dance of Tomorrow/full_mix.flac",
}
PAIRS = [("phreaky", "angelic"), ("angelic", "heron"), ("heron", "phreaky")]


def load(track):
    try:
        a, sr = sf.read(track, dtype="float32", always_2d=True)
        if sr != 44100:
            raise ValueError(f"native sr {sr} != 44100, resample via ffmpeg")
    except Exception:
        # m4a etc, or a native rate != 44.1k: decode via ffmpeg to 44.1k stereo wav
        with tempfile.TemporaryDirectory() as td:
            wav = f"{td}/dec.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-i", track, "-ar", "44100",
                            "-ac", "2", wav], check=True)
            a, sr = sf.read(wav, dtype="float32", always_2d=True)
    return a.T, sr  # (C, N)


def tempo_of(a, sr, around_sec=None):
    """Precise tempo: median inter-beat interval over a 60s excerpt (librosa's
    reported tempo value is too coarse — 0.3 BPM error = ~100ms grid drift over
    a 47s blend = audible gallop even with bar-snapped entries)."""
    import librosa
    c = int(around_sec * sr) if around_sec is not None else a.shape[1] // 2
    lo = max(0, c - 30 * sr)
    ex = a[:, lo:lo + 60 * sr].mean(0)
    _, beats = librosa.beat.beat_track(y=ex, sr=sr, units="time")
    if len(beats) < 16:
        return 140.0
    t = float(60.0 / np.median(np.diff(beats)))
    # fold octave/subdivision locks (x2, /2, x1.5, /1.5 = the 2/3 lock) into the
    # plausible goa band — the tracker regularly locks onto 2/3 subdivisions
    cands = [t * f for f in (1.0, 2.0, 0.5, 1.5, 2.0 / 3.0, 3.0, 1.0 / 3.0)]
    inband = [c for c in cands if 110.0 <= c <= 185.0]
    return min(inband, key=lambda c: abs(c - 145.0)) if inband else t


def bungee_stretch(audio, sr, speed, ramp_to=None, ramp_out_sec=0.0):
    """Time-stretch via bungee (streaming, mir venv). speed applies from the start;
    if ramp_to is given, speed ramps linearly (in tempo domain) from `speed` to
    `ramp_to` over the first `ramp_out_sec` seconds of OUTPUT — the DJ pitch-bend:
    matched at the transition, native afterwards."""
    with tempfile.TemporaryDirectory() as td:
        src, dst = f"{td}/in.npy", f"{td}/out.npy"
        np.save(src, audio.T)  # (N, C) for bungee
        code = f"""
import numpy as np
from bungee_python import bungee as B
d = np.load({src!r}).astype(np.float32)
sr = {sr}
st = B.Bungee(sample_rate=sr, channels=d.shape[1])
speed0, ramp_to, ramp_out = {speed}, {ramp_to if ramp_to is not None else 'None'}, {ramp_out_sec}
chunk = int(0.25 * sr)
outs, out_sec = [], 0.0
for lo in range(0, d.shape[0], chunk):
    if ramp_to is None or out_sec >= ramp_out:
        sp = speed0 if ramp_to is None else ramp_to
    else:
        f = out_sec / ramp_out
        sp = speed0 + f * (ramp_to - speed0)
    st.set_speed(float(sp))
    y = np.asarray(st.process(d[lo:lo + chunk]), dtype=np.float32)
    if y.ndim == 1:
        y = y.reshape(-1, d.shape[1])
    outs.append(y)
    out_sec += y.shape[0] / sr
np.save({dst!r}, np.concatenate(outs, axis=0))
"""
        subprocess.run([MIR_VENV_PY, "-c", code], check=True, capture_output=True)
        return np.load(dst).T  # back to (C, N)


def downbeat_near(a, sr, target_sec):
    """Nearest DOWNBEAT (bar start): librosa beats, phase = strongest mean onset
    energy among the 4 candidate phases (Kim: snap to positions divisible by 4)."""
    import librosa
    lo = max(0, int((target_sec - 30) * sr))
    ex = a[:, lo:lo + int(60 * sr)].mean(0)
    _, beats = librosa.beat.beat_track(y=ex, sr=sr, units="time")
    if len(beats) < 8:
        return target_sec
    env = librosa.onset.onset_strength(y=ex, sr=sr)
    et = librosa.times_like(env, sr=sr)
    strength = np.interp(beats, et, env)
    phase = int(np.argmax([strength[p::4].mean() for p in range(4)]))
    downs = beats[phase::4] + lo / sr
    return float(downs[np.argmin(np.abs(downs - target_sec))])


def fine_align_shift(A_seg, B_seg, sr, span_sec, max_shift_sec):
    """Kim's downbeat-concurrence alignment: cross-correlate onset envelopes of
    A's tail and B's head over the blend span; return B shift (sec) maximizing
    concurrence, constrained to +/- max_shift."""
    import librosa
    hop = 512
    span = int(span_sec * sr)
    oa = librosa.onset.onset_strength(y=A_seg[:, -span:].mean(0), sr=sr, hop_length=hop)
    ob = librosa.onset.onset_strength(y=B_seg[:, :span].mean(0), sr=sr, hop_length=hop)
    n = min(len(oa), len(ob))
    oa, ob = oa[:n] - oa[:n].mean(), ob[:n] - ob[:n].mean()
    max_lag = int(max_shift_sec * sr / hop)
    lags = list(range(-max_lag, max_lag + 1))
    scores = [float(np.dot(oa[max(0, -l):n - max(0, l)], ob[max(0, l):n - max(0, -l)]))
              for l in lags]
    best = lags[int(np.argmax(scores))]
    return best * hop / sr   # positive => delay B


def encode(model, audio, sr):
    pre = model.model.pretransform
    p = next(pre.parameters())
    a = torch.tensor(audio, device=p.device, dtype=p.dtype).unsqueeze(0)
    with torch.inference_mode():
        return pre.encode(a).clone()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--ckpt", default="/run/media/kim/Mantu/sa3_lora_runs/dora128_everything_8ep_lr1x/epoch=7-step=12216.ckpt")
    ap.add_argument("--windows", default="512,1024", help="crossfade lengths (latent frames)")
    ap.add_argument("--noise-levels", default="0.35,0.42,0.5,0.55")
    ap.add_argument("--seg-sec", type=float, default=75.0, help="audio per side of the junction")
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--cfg-scale", type=float, default=6.0)
    ap.add_argument("--prompt", default="aggressive upbeat goa trance")
    ap.add_argument("--a-frac", type=float, default=0.62,
                    help="A's transition point as a fraction of its length (segment ENDS here)")
    ap.add_argument("--b-frac", type=float, default=0.40,
                    help="B's entry point as a fraction of its length")
    ap.add_argument("--pairs", default=None,
                    help="comma list like kaikki:angelic to override the default cycle")
    ap.add_argument("--seam-inpaint", type=int, default=0,
                    help="sinesweep mode: inpaint strips of this many frames centred on "
                         "the crossfade START and END seams after the sweep (Kim's addenda; "
                         "128/256/512)")
    ap.add_argument("--fine-align", action="store_true", default=True,
                    help="onset-concurrence xcorr alignment of B within +/- half bar")
    ap.add_argument("--seam-nl", type=float, default=0.35,
                    help="inpaint mode: peak depth of the 512-frame sine a2a masks centred "
                         "on the inpaint region's entry/exit seams (Kim: smooth the abrupt "
                         "512f bridges in and out); 0 disables")
    ap.add_argument("--tempo-mode", choices=("ramp", "follow"), default="ramp",
                    help="ramp = B matched to A's tempo AT the transition, bending to its "
                         "NATIVE tempo by window end (DJ pitch-bend, default); "
                         "follow = B stays at A's tempo throughout (the first batch's behaviour)")
    ap.add_argument("--no-chroma-ref", action="store_true",
                    help="ALSO render a chroma-guidance-OFF reference per config")
    ap.add_argument("--mode", choices=("refine", "inpaint", "sinesweep"), default="refine",
                    help="refine = whole-composite a2a at each nl (the 07-07 first batch); "
                         "inpaint = PURE transition: original audio outside the window, "
                         "chroma-guided inpaint generation of the bridge (no nl dimension); "
                         "sinesweep = Kim's per-frame DEPTH sweep: a2a strength 0 at window "
                         "edges -> nl (peak) at centre -> 0, via a release-schedule callback")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    wins = [int(x) for x in args.windows.split(",")]
    nls = [float(x) for x in args.noise_levels.split(",")]
    # segments must comfortably contain the largest crossfade window
    args.seg_sec = max(args.seg_sec, 1.6 * max(wins) / FPS)

    mode_desc = {
        "refine": "whole-composite a2a at each nl (remix-hybrid transition)",
        "inpaint": "PURE transition: originals intact, bridge inpaint-generated",
        "sinesweep": ("recipe3: pure-original basis, follow beatmatch, onset-concurrence "
                      "fine-align, chroma slerp + sine noising (peak at listed nl)"
                      + (f", seam-inpaint {args.seam_inpaint}f strips" if args.seam_inpaint else "")),
    }[args.mode]
    meta = {"purpose": (f"real-track chroma-morph transitions [{args.mode}] — {mode_desc}; "
                        f"tempo-mode {args.tempo_mode}, stem-chroma LatCH head gain {CHROMA_GAIN:g}"),
            "mode": args.mode,
            "pairs": PAIRS, "tracks": TRACKS,
            "gen": {"windows": wins, "noise_levels": nls, "seg_sec": args.seg_sec,
                    "steps": args.steps, "cfg": args.cfg_scale,
                    "chroma_head": CHROMA_HEAD, "chroma_gain": CHROMA_GAIN,
                    "guidance_end_pct": 0.6, "prompt": args.prompt},
            "checkpoints": {"adapter": args.ckpt}}
    (args.out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2))

    print("[load] model", flush=True)
    model = StableAudioModel.from_pretrained("medium-base", device="cuda")
    model.load_lora([args.ckpt])
    sr = model.model.sample_rate

    pairs = ([tuple(p.split(":")) for p in args.pairs.split(",")] if args.pairs else PAIRS)
    # load only the tracks the requested pairs need — a stale/moved path for an
    # unrelated track (e.g. a renamed album dir) shouldn't fail every run.
    needed = {k for pair in pairs for k in pair}
    audio_cache = {k: load(TRACKS[k]) for k in needed}
    for a_key, b_key in pairs:
        A, sra = audio_cache[a_key]
        B, srb = audio_cache[b_key]
        assert sra == sr and srb == sr
        # measure tempo AT the material actually used
        ta = tempo_of(A, sr, around_sec=args.a_frac * A.shape[1] / sr)
        tb = tempo_of(B, sr, around_sec=args.b_frac * B.shape[1] / sr)
        speed = ta / tb            # playback speed multiplies tempo: tb*speed = ta
        if not (0.85 <= speed <= 1.18):
            print(f"  [warn] match ratio {speed:.3f} outside sane band — check tempo folds", flush=True)
        print(f"[{a_key}->{b_key}] tempo A={ta:.1f} B={tb:.1f} match speed={speed:.4f} "
              f"mode={args.tempo_mode}", flush=True)

        # segments anchored on DOWNBEATS (bar starts); B anchored on the RAW track
        a_end = downbeat_near(A, sr, max(args.a_frac * A.shape[1] / sr, args.seg_sec))
        b_start0 = downbeat_near(B, sr, args.b_frac * B.shape[1] / sr)
        bar_sec = 4 * 60.0 / ta   # A's bar length (B is matched to it at the window)
        A_seg = A[:, int((a_end - args.seg_sec) * sr):int(a_end * sr)]

        zA = encode(model, A_seg, sr)
        cA = compute_same_chroma(A_seg.T, sr).reshape(384, -1)   # (3,128,T) -> (384,T)

        for W_req in wins:
            # quantize the window to WHOLE BARS; compensate the sub-frame residual
            # by shifting B's cut so kicks align exactly inside the blend
            bars = max(1, round((W_req / FPS) / bar_sec))
            W = int(round(bars * bar_sec * FPS))
            residual = W / FPS - bars * bar_sec          # seconds, |r| < 1 frame
            cut = b_start0 + residual
            raw_seg = B[:, int(cut * sr):int((cut + args.seg_sec * 1.5) * sr)]
            if abs(speed - 1.0) > 0.0005:
                # ramp: matched to A's tempo at the window, bending to NATIVE by
                # window end (DJ pitch-bend); follow: matched throughout
                ramp_to = 1.0 if args.tempo_mode == "ramp" else None
                Bseg_s = bungee_stretch(raw_seg, sr, speed,
                                        ramp_to=ramp_to, ramp_out_sec=W / FPS)
            else:
                Bseg_s = raw_seg
            B_seg = Bseg_s[:, :int(args.seg_sec * sr)]
            if args.fine_align:
                sh = fine_align_shift(A_seg, B_seg, sr,
                                      span_sec=W / FPS, max_shift_sec=bar_sec / 2)
                if abs(sh) > 0.004:
                    print(f"  [align] B shifted {sh*1000:+.0f}ms (onset concurrence)", flush=True)
                    if sh < 0:
                        B_seg = Bseg_s[:, int(-sh*sr):int(-sh*sr) + int(args.seg_sec * sr)]
                    else:
                        pad = np.zeros((B_seg.shape[0], int(sh * sr)), dtype=B_seg.dtype)
                        B_seg = np.concatenate([pad, B_seg], axis=1)[:, :int(args.seg_sec * sr)]
            zB = encode(model, B_seg, sr)
            cB = compute_same_chroma(B_seg.T, sr).reshape(384, -1)
            print(f"  [win] req {W_req}f -> {W}f = {bars} bars (residual {residual*1000:+.1f}ms)", flush=True)
            # composite: zA + slerp window + zB
            t = torch.linspace(0, 1, W, device=zA.device, dtype=torch.float32).view(1, 1, -1)
            mid = slerp(zA[..., -W:].float(), zB[..., :W].float(), t).to(zA.dtype)
            z = torch.cat([zA[..., :-W], mid, zB[..., W:]], dim=-1)
            Tz = z.shape[-1]
            # chroma morph target on the same grid
            TA = zA.shape[-1]
            ramp = np.linspace(0, 1, W, dtype=np.float32)[None, :]
            cA_r = cA[:, :TA] if cA.shape[1] >= TA else np.pad(cA, ((0, 0), (0, TA - cA.shape[1])), mode="edge")
            cB_r = cB[:, :zB.shape[-1]] if cB.shape[1] >= zB.shape[-1] else np.pad(cB, ((0, 0), (0, zB.shape[-1] - cB.shape[1])), mode="edge")
            morph = cA_r[:, -W:] * (1 - ramp) + cB_r[:, :W] * ramp
            target = np.concatenate([cA_r[:, :-W], morph, cB_r[:, W:]], axis=1)[:, :Tz]

            dur = Tz / FPS
            audio_ref = None  # decode lazily only if needed
            if args.mode == "sinesweep":
                # per-frame depth: 0 outside the window, sine bump peaking at nl
                Wlo, Whi = zA.shape[-1] - W, zA.shape[-1]
                depth_shape = torch.zeros(Tz)
                depth_shape[Wlo:Whi] = torch.sin(torch.linspace(0, torch.pi, W))
                nls_eff = nls
            elif args.mode == "inpaint":
                nls_eff = [None]
                # window bounds in the composite (frames -> seconds)
                w_lo = (zA.shape[-1] - W) / FPS
                w_hi = zA.shape[-1] / FPS
            else:
                nls_eff = nls
            for nl in nls_eff:
                for chroma_on in ([True, False] if args.no_chroma_ref else [True]):
                    tag = "chroma" if chroma_on else "plain"
                    nl_tag = "inpaint" if nl is None else f"nl{int(nl*100):02d}"
                    if args.mode == "sinesweep" and args.seam_inpaint > 0:
                        nl_tag += f"_seam{args.seam_inpaint}"
                    out = args.out_dir / f"{a_key}2{b_key}__w{W}_{nl_tag}_{tag}.wav"
                    if out.exists():
                        print(f"[skip] {out.name}", flush=True)
                        continue
                    t0 = time.time()
                    if audio_ref is None:  # decode composite once per window
                        pre = model.model.pretransform
                        with torch.inference_mode():
                            audio_ref = pre.decode(z.to(next(pre.parameters()).dtype))[0]
                    kw = dict(prompt=args.prompt, duration=dur, steps=args.steps,
                              cfg_scale=args.cfg_scale, seed=1234, batch_size=1,
                              sample_size=int((dur + 8) * sr))
                    if nl is None:  # pure-transition inpaint of the window
                        kw["inpaint_audio"] = (sr, audio_ref.float())
                        kw["inpaint_mask_start_seconds"] = w_lo
                        kw["inpaint_mask_end_seconds"] = w_hi
                    elif args.mode == "sinesweep":
                        # start at peak depth; frames stay clamped to the reference
                        # trajectory until global t falls to their own sine depth
                        kw["init_audio"] = (sr, audio_ref.float())
                        kw["init_noise_level"] = nl
                        z_ref = z.float().cpu()
                        torch.manual_seed(4242)
                        eps_ref = torch.randn_like(z_ref)
                        depth = (depth_shape * nl).view(1, 1, -1)

                        def cb(d, _z=z_ref, _e=eps_ref, _d=depth):
                            x, tt = d["x"], float(d["t"][0])
                            n = min(x.shape[-1], _z.shape[-1])
                            hold = (_d[..., :n] < tt)  # not yet released
                            ref_t = ((1 - tt) * _z[..., :n] + tt * _e[..., :n]).to(x.device, x.dtype)
                            xs = x[..., :n]
                            x[..., :n].copy_(torch.where(hold.to(x.device), ref_t, xs))

                        kw["callback"] = cb
                    else:
                        kw["init_audio"] = (sr, audio_ref.float())
                        kw["init_noise_level"] = nl
                    if chroma_on:
                        kw["latch_configs"] = [{"model_path": CHROMA_HEAD,
                                                "target_raw": target,
                                                "weight": 1.0, "end_pct": 0.6}]
                        kw["latch_hparams"] = {"rho": CHROMA_GAIN, "mu": CHROMA_GAIN}
                    outa = model.generate(**kw)
                    y = outa[0].float().cpu().numpy()
                    if args.mode == "sinesweep" and args.seam_inpaint > 0:
                        S = args.seam_inpaint / FPS   # strip length in seconds
                        w_lo_s = (zA.shape[-1] - W) / FPS
                        w_hi_s = zA.shape[-1] / FPS
                        starts = [max(w_lo_s - S / 2, 0), w_hi_s - S / 2]
                        ends = [w_lo_s + S / 2, min(w_hi_s + S / 2, y.shape[1] / sr)]
                        kw3 = dict(prompt=args.prompt, duration=y.shape[1] / sr,
                                   steps=args.steps, cfg_scale=args.cfg_scale,
                                   seed=1234, batch_size=1,
                                   sample_size=int((y.shape[1] / sr + 8) * sr),
                                   inpaint_audio=(sr, torch.tensor(y)),
                                   inpaint_mask_start_seconds=starts,
                                   inpaint_mask_end_seconds=ends)
                        if chroma_on:
                            kw3["latch_configs"] = [{"model_path": CHROMA_HEAD,
                                                     "target_raw": target,
                                                     "weight": 1.0, "end_pct": 0.6}]
                            kw3["latch_hparams"] = {"rho": CHROMA_GAIN, "mu": CHROMA_GAIN}
                        y = model.generate(**kw3)[0].float().cpu().numpy()
                    if args.mode == "sinesweep":
                        # PURE BASIS (Kim): original audio outside the transition
                        # (+seam strips) — no a2a/codec touch on the tracks themselves
                        S = args.seam_inpaint / FPS if args.seam_inpaint > 0 else 0.0
                        w_lo_s = (zA.shape[-1] - W) / FPS
                        w_hi_s = zA.shape[-1] / FPS
                        lo_n = int(max(w_lo_s - S / 2, 0) * sr)
                        hi_n = int(min((w_hi_s + S / 2) * sr, y.shape[1] * 1.0))
                        f2 = int(0.5 * sr)
                        rmp = np.linspace(0, 1, f2, dtype=np.float32)
                        origA = A_seg[:, :lo_n + f2]
                        # B's original timeline in the composite starts at (TA - W)
                        offB = int((zA.shape[-1] - W) / FPS * sr)
                        origB = B_seg[:, hi_n - offB - f2:]
                        out_full = y.copy()
                        n0 = min(lo_n, origA.shape[1], out_full.shape[1])
                        out_full[:, :n0 - f2] = origA[:, :n0 - f2]
                        out_full[:, n0 - f2:n0] = (origA[:, n0 - f2:n0] * (1 - rmp)
                                                   + y[:, n0 - f2:n0] * rmp)
                        tailN = out_full.shape[1] - hi_n
                        ba = origB[:, f2:f2 + tailN]
                        m2 = min(ba.shape[1], tailN)
                        out_full[:, hi_n:hi_n + f2] = (y[:, hi_n:hi_n + f2] * (1 - rmp)
                                                       + origB[:, :f2][:, :f2] * rmp)
                        out_full[:, hi_n + f2:hi_n + f2 + m2 - f2] = ba[:, :m2 - f2]
                        y = out_full
                    if nl is None:
                        # splice ORIGINAL audio back outside the window (1s fades)
                        ref = audio_ref.float().cpu().numpy()
                        n = min(y.shape[1], ref.shape[1])
                        y, ref = y[:, :n], ref[:, :n]
                        lo_n, hi_n = int(w_lo * sr), min(int(w_hi * sr), n)
                        f = int(1.0 * sr)
                        outy = ref.copy()
                        outy[:, lo_n:hi_n] = y[:, lo_n:hi_n]
                        r = np.linspace(0, 1, f, dtype=np.float32)
                        if lo_n - f >= 0:
                            outy[:, lo_n - f:lo_n] = ref[:, lo_n - f:lo_n] * (1 - r) + y[:, lo_n - f:lo_n] * r
                        if hi_n + f <= n:
                            outy[:, hi_n:hi_n + f] = y[:, hi_n:hi_n + f] * (1 - r) + ref[:, hi_n:hi_n + f] * r
                        y = outy
                        if args.seam_nl > 0:
                            # Kim's seam smoothing: two 512-frame sine-depth a2a masks
                            # centred on the inpaint entry/exit seams (release schedule)
                            seam_w = 512
                            Tz2 = int(np.ceil(y.shape[1] / sr * FPS))
                            dshape = torch.zeros(Tz2)
                            for centre in (int(w_lo * FPS), int(w_hi * FPS)):
                                lo2 = max(centre - seam_w // 2, 0)
                                hi2 = min(centre + seam_w // 2, Tz2)
                                bump = torch.sin(torch.linspace(0, torch.pi, hi2 - lo2))
                                dshape[lo2:hi2] = torch.maximum(dshape[lo2:hi2], bump)
                            pre2 = model.model.pretransform
                            pp = next(pre2.parameters())
                            with torch.inference_mode():
                                z_ref2 = pre2.encode(torch.tensor(y, device=pp.device,
                                                                  dtype=pp.dtype).unsqueeze(0)).float().cpu()
                            torch.manual_seed(2424)
                            eps2 = torch.randn_like(z_ref2)
                            depth2 = (dshape * args.seam_nl).view(1, 1, -1)

                            def cb2(d, _z=z_ref2, _e=eps2, _d=depth2):
                                x, tt = d["x"], float(d["t"][0])
                                nn = min(x.shape[-1], _z.shape[-1], _d.shape[-1])
                                hold = (_d[..., :nn] < tt)
                                ref_t = ((1 - tt) * _z[..., :nn] + tt * _e[..., :nn]).to(x.device, x.dtype)
                                x[..., :nn].copy_(torch.where(hold.to(x.device), ref_t, x[..., :nn]))

                            kw2 = dict(prompt=args.prompt, duration=y.shape[1] / sr,
                                       steps=args.steps, cfg_scale=args.cfg_scale,
                                       seed=1234, batch_size=1,
                                       sample_size=int((y.shape[1] / sr + 8) * sr),
                                       init_audio=(sr, torch.tensor(y)),
                                       init_noise_level=args.seam_nl, callback=cb2)
                            if chroma_on:
                                kw2["latch_configs"] = [{"model_path": CHROMA_HEAD,
                                                         "target_raw": target,
                                                         "weight": 1.0, "end_pct": 0.6}]
                                kw2["latch_hparams"] = {"rho": CHROMA_GAIN, "mu": CHROMA_GAIN}
                            y = model.generate(**kw2)[0].float().cpu().numpy()
                    save_audio(out, torch.tensor(y), sr, normalize=True)
                    print(f"[clip] {out.name}  {time.time()-t0:5.1f}s", flush=True)
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
