#!/usr/bin/env python
"""pipeline.py -- GM timbre-pitch atlas: melody-encoding test over ALL pitched General
MIDI programs (0-119; 120-127 SFX skipped; 112-119 percussive flagged quasi-pitched),
REDUCED MIDI set (sweep + pat1 + pat2 + pat5, all frame-locked BPM 161.4990234375).

Reuses eval/musicology/test_midis_v2/gen_test_midis_v2.py (write_midi/write_sweep_midi/
PATTERNS, imported) for MIDI generation, the same fluidsynth invocation convention, the
pretransform-only SAME encoder pattern from latent_melody_analysis/encode_test_midis.py,
and ridge/LDA analysis helpers imported from latent_melody_analysis/analyze_melody_encoding.py.

Stages (--stages gen,render,encode,analyze; default: all in order):
  gen      CPU. Write 4 master MIDIs (no program_change) to midis/.
  render   CPU. For each of 4 patterns x 120 programs, inject program_change + fluidsynth
           render -> renders/. Retries a hung/timed-out render once, then skips+logs.
  encode   GPU. SAME pretransform-encode all renders -> latents/*.z0.npy (fp16). Caller
           must hold SAO/.gpu.lock around this stage (not managed here).
  analyze  CPU. Timbre-pitch atlas: per-program pitch decoder, 120x120 transfer matrix +
           GM-family block structure + hierarchical clustering, universal (LOPO) pitch
           subspace, jump detectability (pat5 vs pat1 control), pat2 E/G d'. Writes
           results.json, transfer_matrix.npz, per_program.csv, REPORT.md.
"""
import argparse
import csv
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

BASE = Path("/home/kim/Projects/SAO/eval/musicology/gm_timbre_pitch")
MIDIS = BASE / "midis"
RENDERS = BASE / "renders"
LATENTS = BASE / "latents"
SF2 = "/usr/share/soundfonts/FluidR3_GM.sf2"
SR = 44100
BPM_LOCK1 = 161.4990234375  # 16th == 1 SAME frame

sys.path.insert(0, "/home/kim/Projects/SAO/eval/musicology/test_midis_v2")
import gen_test_midis_v2 as genv2  # noqa: E402  (write_midi, write_sweep_midi, PATTERNS)
sys.path.insert(0, "/home/kim/Projects/SAO/eval/musicology/latent_melody_analysis")
import analyze_melody_encoding as v1  # noqa: E402  (r2_linear, polyfit_r2, ridge_loo)

# ---------------------------------------------------------------- GM program list (hardcoded, standard)
GM_NAMES = [
    "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano", "Honky-tonk Piano",
    "Electric Piano 1", "Electric Piano 2", "Harpsichord", "Clavinet",
    "Celesta", "Glockenspiel", "Music Box", "Vibraphone", "Marimba", "Xylophone", "Tubular Bells", "Dulcimer",
    "Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ", "Reed Organ", "Accordion", "Harmonica", "Tango Accordion",
    "Acoustic Guitar (nylon)", "Acoustic Guitar (steel)", "Electric Guitar (jazz)", "Electric Guitar (clean)",
    "Electric Guitar (muted)", "Overdriven Guitar", "Distortion Guitar", "Guitar Harmonics",
    "Acoustic Bass", "Electric Bass (finger)", "Electric Bass (pick)", "Fretless Bass",
    "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2",
    "Violin", "Viola", "Cello", "Contrabass", "Tremolo Strings", "Pizzicato Strings", "Orchestral Harp", "Timpani",
    "String Ensemble 1", "String Ensemble 2", "Synth Strings 1", "Synth Strings 2",
    "Choir Aahs", "Voice Oohs", "Synth Voice", "Orchestra Hit",
    "Trumpet", "Trombone", "Tuba", "Muted Trumpet", "French Horn", "Brass Section", "Synth Brass 1", "Synth Brass 2",
    "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax", "Oboe", "English Horn", "Bassoon", "Clarinet",
    "Piccolo", "Flute", "Recorder", "Pan Flute", "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina",
    "Lead 1 (square)", "Lead 2 (sawtooth)", "Lead 3 (calliope)", "Lead 4 (chiff)",
    "Lead 5 (charang)", "Lead 6 (voice)", "Lead 7 (fifths)", "Lead 8 (bass+lead)",
    "Pad 1 (new age)", "Pad 2 (warm)", "Pad 3 (polysynth)", "Pad 4 (choir)",
    "Pad 5 (bowed)", "Pad 6 (metallic)", "Pad 7 (halo)", "Pad 8 (sweep)",
    "FX 1 (rain)", "FX 2 (soundtrack)", "FX 3 (crystal)", "FX 4 (atmosphere)",
    "FX 5 (brightness)", "FX 6 (goblins)", "FX 7 (echoes)", "FX 8 (sci-fi)",
    "Sitar", "Banjo", "Shamisen", "Koto", "Kalimba", "Bag pipe", "Fiddle", "Shanai",
    "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock", "Taiko Drum", "Melodic Tom", "Synth Drum", "Reverse Cymbal",
]
assert len(GM_NAMES) == 120  # pitched + quasi-pitched block only (120-127 SFX intentionally omitted)
GM_FAMILIES = [
    "Piano", "Chromatic Percussion", "Organ", "Guitar", "Bass", "Strings", "Ensemble", "Brass",
    "Reed", "Pipe", "Synth Lead", "Synth Pad", "Synth Effects", "Ethnic", "Percussive",
]  # 15 families x 8 programs = 0..119
PROGRAMS = list(range(120))  # 0-119, pitched + quasi-pitched (skip 120-127 SFX)


def family_of(pp):
    return pp // 8


def family_name(pp):
    return GM_FAMILIES[family_of(pp)]


def is_quasi_pitched(pp):
    return 112 <= pp <= 119


# ---------------------------------------------------------------- gen
PAT_KEYS = {"pat1": "pat1_const16_1pitch", "pat2": "pat2_const16_2pitch", "pat5": "pat5_const8_fifthjump"}
NBARS = 16  # -> 256 frames at BPM_LOCK1


def stage_gen():
    MIDIS.mkdir(parents=True, exist_ok=True)
    genv2.write_sweep_midi(MIDIS / "sweep.mid", BPM_LOCK1)
    for tag, key in PAT_KEYS.items():
        steps = genv2.PATTERNS[key]["steps"]
        genv2.write_midi(MIDIS / f"{tag}.mid", steps, NBARS, BPM_LOCK1)
    man = {"bpm": BPM_LOCK1, "sweep_notes": 73, "sweep_frames_per_note": 2, "sweep_frames": 146,
           "pat_bars": NBARS, "pat_frames": 256, "programs": PROGRAMS,
           "quasi_pitched_range": [112, 119], "skipped_sfx_range": [120, 127]}
    json.dump(man, open(BASE / "manifest.json", "w"), indent=1)
    print(f"[gen] 4 master MIDIs written to {MIDIS}")


# ---------------------------------------------------------------- render
def render_one(task):
    midi_path, pp, out = task
    if out.exists():
        return "skip", out.name
    import mido
    for attempt in (1, 2):
        mid = mido.MidiFile(midi_path)
        tr = mid.tracks[0]
        tr.insert(1, mido.Message("program_change", program=pp, channel=0, time=0))
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as tf:
            tmp = Path(tf.name)
        mid.save(tmp)
        try:
            r = subprocess.run(
                ["fluidsynth", "-ni", "-g", "0.5", "-r", str(SR), "-F", str(out), SF2, str(tmp)],
                capture_output=True, text=True, timeout=90)
            ok = r.returncode == 0 and out.exists()
        except subprocess.TimeoutExpired:
            ok = False
            err = "TIMEOUT"
        else:
            err = r.stderr[-200:] if not ok else ""
        finally:
            tmp.unlink(missing_ok=True)
        if ok:
            return "ok", out.name
        if attempt == 2:
            out.unlink(missing_ok=True)
            return "SKIP", f"{out.name}: {err}"
    return "SKIP", out.name


def stage_render(jobs=12):
    RENDERS.mkdir(parents=True, exist_ok=True)
    tasks = []
    for tag in ["sweep", "pat1", "pat2", "pat5"]:
        midi_path = MIDIS / f"{tag}.mid"
        for pp in PROGRAMS:
            out = RENDERS / f"{tag}__p{pp:03d}.wav"
            tasks.append((midi_path, pp, out))
    print(f"[render] {len(tasks)} fluidsynth renders, {jobs} workers")
    skips = []
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        futs = {ex.submit(render_one, t): t for t in tasks}
        for i, f in enumerate(as_completed(futs)):
            status, msg = f.result()
            if status == "SKIP":
                skips.append(msg)
                print(f"[SKIP] {msg}", flush=True)
            if (i + 1) % 100 == 0:
                print(f"  {i+1}/{len(tasks)}  {time.time()-t0:.0f}s", flush=True)
    n = len(list(RENDERS.glob("*.wav")))
    print(f"[render] done: {n} wavs present in {time.time()-t0:.0f}s, {len(skips)} skipped: {skips}")
    json.dump(skips, open(BASE / "render_skips.json", "w"), indent=1)


# ---------------------------------------------------------------- encode
def stage_encode():
    import torch
    import soundfile as sf
    from safetensors.torch import load_file
    from stable_audio_3.model_configs import all_models
    from stable_audio_3.factory import create_pretransform_from_config
    from stable_audio_3.loading_utils import copy_state_dict

    LATENTS.mkdir(parents=True, exist_ok=True)
    wavs = sorted(RENDERS.glob("*.wav"))
    todo = [w for w in wavs if not (LATENTS / f"{w.stem}.z0.npy").exists()]
    print(f"[encode] {len(todo)}/{len(wavs)} to do", flush=True)
    if not todo:
        return

    cfg_path, ckpt_path = all_models["medium-base"].resolve()
    _cfg = json.load(open(cfg_path))
    sr = _cfg["sample_rate"]
    pt = create_pretransform_from_config(_cfg.get("model", _cfg), sr).to("cuda").half().eval().requires_grad_(False)
    _sd = load_file(ckpt_path)
    copy_state_dict(pt, {k[len("pretransform."):]: v for k, v in _sd.items() if k.startswith("pretransform.")})
    ds = int(pt.downsampling_ratio)
    print(f"[encode] pretransform up: sr={sr} ds={ds}", flush=True)

    t0 = time.time()
    for i, w in enumerate(todo):
        y, in_sr = sf.read(w, dtype="float32", always_2d=True)
        assert in_sr == sr, f"{w.name}: sr {in_sr} != {sr}"
        x = torch.from_numpy(y.T)
        if x.shape[0] == 1:
            x = x.repeat(2, 1)
        n = x.shape[-1]
        pad = (ds - n % ds) % ds
        if pad:
            x = torch.nn.functional.pad(x, (0, pad))
        x = x.unsqueeze(0).cuda().half()
        with torch.no_grad():
            z = pt.encode(x)
        z = z[0].float().cpu().numpy().astype(np.float16)
        np.save(LATENTS / f"{w.stem}.z0.npy", z)
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(todo)}  {time.time()-t0:.0f}s", flush=True)
    print(f"[encode] done {len(todo)} in {time.time()-t0:.0f}s", flush=True)


# ---------------------------------------------------------------- analyze
def zload(tag, pp):
    return np.load(LATENTS / f"{tag}__p{pp:03d}.z0.npy").astype(np.float32)


def sweep_slot(pp):
    z = zload("sweep", pp)
    assert z.shape[0] == 256 and z.shape[1] >= 146, (pp, z.shape)
    return z[:, :146][:, 1::2].T  # [73,256] 2nd frame of each 2


def pat_frames(tag, pp, n=256):
    z = zload(tag, pp)
    assert z.shape[0] == 256 and z.shape[1] >= n, (tag, pp, z.shape)
    return z[:, :n]  # [256,n]


def jump_metrics(Z, phase, pedal_ph, jump_ph):
    pedal_mask = np.isin(phase, pedal_ph)
    jump_mask = np.isin(phase, jump_ph)
    mu_p, sd_p = Z[pedal_mask].mean(0), Z[pedal_mask].std(0) + 1e-6
    mu_j, sd_j = Z[jump_mask].mean(0), Z[jump_mask].std(0)
    pooled = np.sqrt(0.5 * (sd_p ** 2 + sd_j ** 2)) + 1e-6
    delta = mu_j - mu_p
    w = delta / (pooled ** 2)
    s_j, s_p = Z[jump_mask] @ w, Z[pedal_mask] @ w
    thr = 0.5 * (s_j.mean() + s_p.mean())
    acc = 0.5 * (np.mean(s_j > thr) + np.mean(s_p < thr))
    return float(acc), delta


def dprime_binary(Z, mask_a, mask_b):
    mu_a, sd_a = Z[mask_a].mean(0), Z[mask_a].std(0) + 1e-6
    mu_b, sd_b = Z[mask_b].mean(0), Z[mask_b].std(0) + 1e-6
    pooled = np.sqrt(0.5 * (sd_a ** 2 + sd_b ** 2)) + 1e-6
    w = (mu_b - mu_a) / pooled ** 2
    sa, sb = Z[mask_a] @ w, Z[mask_b] @ w
    denom = 0.5 * (sa.std() + sb.std()) + 1e-9
    return float((sb.mean() - sa.mean()) / denom)


def stage_analyze():
    pitches = np.arange(36, 109).astype(float)
    valid = [pp for pp in PROGRAMS if (LATENTS / f"sweep__p{pp:03d}.z0.npy").exists()
              and (LATENTS / f"pat1__p{pp:03d}.z0.npy").exists()
              and (LATENTS / f"pat2__p{pp:03d}.z0.npy").exists()
              and (LATENTS / f"pat5__p{pp:03d}.z0.npy").exists()]
    missing = [pp for pp in PROGRAMS if pp not in valid]
    print(f"[analyze] {len(valid)}/120 programs with complete latents; missing: {missing}")

    # ---- (a) per-program sweep pitch decoder ----
    S = {}
    weight = {}
    per_program = {}
    for pp in valid:
        Spp = sweep_slot(pp)
        S[pp] = Spp
        r2ch = np.array([v1.r2_linear(pitches, Spp[:, c]) for c in range(256)])
        top = np.argsort(r2ch)[::-1][:10]
        quad_delta = float(np.mean([v1.polyfit_r2(pitches, Spp[:, c], 2) - r2ch[c] for c in top]))
        w, Xm, ym, r2_loo = v1.ridge_loo(Spp, pitches)
        weight[pp] = w
        per_program[pp] = {
            "program": pp, "name": GM_NAMES[pp], "family": family_name(pp),
            "quasi_pitched": is_quasi_pitched(pp),
            "top1_r2": round(float(r2ch[top[0]]), 4),
            "n_channels_r2_ge_0.5": int((r2ch >= 0.5).sum()),
            "ridge_loo_r2": round(float(r2_loo), 4),
            "lin_quad_delta_top10": round(quad_delta, 4),
        }
    print(f"[a] per-program sweep decoder done, mean ridge_loo_r2={np.mean([p['ridge_loo_r2'] for p in per_program.values()]):.3f}")

    # ---- (b) 120x120 transfer matrix + family blocks + clustering ----
    n = len(valid)
    transfer = np.full((n, n), np.nan)
    for i, a in enumerate(valid):
        w, Xm, ym, _ = v1.ridge_loo(S[a], pitches)
        for j, b in enumerate(valid):
            yh = (S[b] - Xm) @ w + ym
            transfer[i, j] = 1 - np.sum((pitches - yh) ** 2) / np.sum((pitches - pitches.mean()) ** 2)
    fam = np.array([family_of(pp) for pp in valid])
    same_fam = (fam[:, None] == fam[None, :]) & ~np.eye(n, dtype=bool)
    diff_fam = (fam[:, None] != fam[None, :])
    mean_within = float(np.nanmean(transfer[same_fam])) if same_fam.any() else float("nan")
    mean_cross = float(np.nanmean(transfer[diff_fam]))

    cos_w = np.zeros((n, n))
    for i, a in enumerate(valid):
        for j, b in enumerate(valid):
            cos_w[i, j] = weight[a] @ weight[b] / (np.linalg.norm(weight[a]) * np.linalg.norm(weight[b]) + 1e-12)
    from scipy.cluster.hierarchy import linkage, fcluster
    from scipy.spatial.distance import squareform
    dist = np.clip(1 - cos_w, 0, 2)
    np.fill_diagonal(dist, 0)
    dist = (dist + dist.T) / 2
    Z_link = linkage(squareform(dist, checks=False), method="average")
    K = 12
    clusters = fcluster(Z_link, K, criterion="maxclust")
    cluster_report = {}
    for k in sorted(set(clusters)):
        members = [valid[i] for i in range(n) if clusters[i] == k]
        fams = [family_name(pp) for pp in members]
        maj_fam = max(set(fams), key=fams.count)
        purity = fams.count(maj_fam) / len(fams)
        cluster_report[int(k)] = {
            "n": len(members),
            "majority_family": maj_fam, "purity": round(purity, 2),
            "members": [f"{GM_NAMES[pp]}({pp})" for pp in members],
        }
    print(f"[b] transfer matrix: mean within-family={mean_within:.3f} vs cross-family={mean_cross:.3f}")

    # ---- (c) universal (LOPO) pitch subspace ----
    lopo_r2 = {}
    for hold in valid:
        others = [pp for pp in valid if pp != hold]
        Xtr = np.concatenate([S[pp] for pp in others], 0)
        ytr = np.tile(pitches, len(others))
        w, Xm, ym, _ = v1.ridge_loo(Xtr, ytr, lam=50.0)
        yh = (S[hold] - Xm) @ w + ym
        lopo_r2[hold] = float(1 - np.sum((pitches - yh) ** 2) / np.sum((pitches - pitches.mean()) ** 2))
    vals = np.array(list(lopo_r2.values()))
    deciles = {f"p{d}": round(float(np.percentile(vals, d)), 4) for d in range(10, 100, 10)}
    worst10 = sorted(lopo_r2, key=lambda pp: lopo_r2[pp])[:10]
    worst10_report = [{"program": pp, "name": GM_NAMES[pp], "family": family_name(pp),
                        "lopo_r2": round(lopo_r2[pp], 4)} for pp in worst10]
    Sall = np.concatenate([S[pp] for pp in valid], 0)
    Sc = Sall - Sall.mean(0)
    sv = np.linalg.svd(Sc, compute_uv=False)
    cum = np.cumsum(sv ** 2 / (sv ** 2).sum())
    pooled_dim_n90 = int(np.searchsorted(cum, 0.90) + 1)
    print(f"[c] LOPO r2 deciles={deciles} pooled_subspace_dim(n90)={pooled_dim_n90}")
    print(f"    worst10: {[(w['name'], w['lopo_r2']) for w in worst10_report]}")

    # ---- (d) jump detectability pat5 vs pat1 control ----
    phase = np.arange(256) % 16
    jump_ph, pedal_ph = [8, 9], [2, 3, 4, 5, 6, 7]
    jump_acc, ctrl_acc = {}, {}
    for pp in valid:
        Z5 = pat_frames("pat5", pp).T
        acc5, _ = jump_metrics(Z5, phase, pedal_ph, jump_ph)
        jump_acc[pp] = acc5
        Z1 = pat_frames("pat1", pp).T
        acc1, _ = jump_metrics(Z1, phase, pedal_ph, jump_ph)
        ctrl_acc[pp] = acc1
        per_program[pp]["jump_lda_acc"] = round(acc5, 4)
        per_program[pp]["pat1_control_acc"] = round(acc1, 4)
    corr_jump_vs_r2 = float(np.corrcoef([jump_acc[pp] for pp in valid],
                                        [per_program[pp]["ridge_loo_r2"] for pp in valid])[0, 1])
    print(f"[d] jump acc range [{min(jump_acc.values()):.3f},{max(jump_acc.values()):.3f}] "
          f"control range [{min(ctrl_acc.values()):.3f},{max(ctrl_acc.values()):.3f}] "
          f"corr(jump_acc,pitch_r2)={corr_jump_vs_r2:.3f}")

    # ---- (e) pat2 E/G separation d' ----
    dprime = {}
    for pp in valid:
        Z2 = pat_frames("pat2", pp).T
        ph2 = np.arange(256) % 2
        d = dprime_binary(Z2, ph2 == 0, ph2 == 1)
        dprime[pp] = d
        per_program[pp]["pat2_dprime"] = round(d, 4)
    print(f"[e] pat2 d' range [{min(dprime.values()):.2f},{max(dprime.values()):.2f}] "
          f"mean={np.mean(list(dprime.values())):.2f}")

    for pp in valid:
        per_program[pp]["lopo_r2"] = round(lopo_r2[pp], 4)

    results = {
        "n_programs": n, "missing_programs": missing,
        "per_program": per_program,
        "cross_program": {
            "mean_within_family_transfer_r2": round(mean_within, 4),
            "mean_cross_family_transfer_r2": round(mean_cross, 4),
            "clusters_k12": cluster_report,
        },
        "universal_subspace": {
            "lopo_r2_deciles": deciles, "lopo_r2_mean": round(float(vals.mean()), 4),
            "worst10": worst10_report, "pooled_pitch_subspace_dim_n90": pooled_dim_n90,
        },
        "jump_detect": {
            "corr_jump_acc_vs_pitch_r2": round(corr_jump_vs_r2, 4),
            "jump_acc_min": round(min(jump_acc.values()), 4), "jump_acc_max": round(max(jump_acc.values()), 4),
            "pat1_control_acc_mean": round(float(np.mean(list(ctrl_acc.values()))), 4),
        },
        "interleave_pat2": {
            "dprime_min": round(min(dprime.values()), 3), "dprime_max": round(max(dprime.values()), 3),
            "dprime_mean": round(float(np.mean(list(dprime.values()))), 3),
        },
    }
    json.dump(results, open(BASE / "results.json", "w"), indent=1)
    np.savez(BASE / "transfer_matrix.npz", transfer=transfer, cos_w=cos_w, programs=np.array(valid),
              clusters=clusters)

    # CSV
    cols = ["program", "name", "family", "quasi_pitched", "top1_r2", "n_channels_r2_ge_0.5",
            "ridge_loo_r2", "lin_quad_delta_top10", "lopo_r2", "jump_lda_acc", "pat1_control_acc", "pat2_dprime"]
    with open(BASE / "per_program.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=cols)
        wr.writeheader()
        for pp in valid:
            wr.writerow({c: per_program[pp][c] for c in cols})

    write_report(results, valid)
    print(f"[analyze] wrote results.json, transfer_matrix.npz, per_program.csv, REPORT.md in {BASE}")
    return results


def write_report(res, valid):
    d = res["universal_subspace"]["lopo_r2_deciles"]
    worst = res["universal_subspace"]["worst10"]
    cl = res["cross_program"]["clusters_k12"]
    lines = []
    lines.append("# GM Timbre-Pitch Atlas — REPORT\n")
    lines.append(f"Reduced melody-encoding test over {res['n_programs']}/120 pitched General MIDI "
                 "programs (0-119; SFX 120-127 skipped; 112-119 percussive flagged quasi-pitched), "
                 "4 frame-locked MIDIs (sweep, pat1, pat2, pat5) per program.\n")
    if res["missing_programs"]:
        lines.append(f"**Missing/skipped programs (render or encode failure):** {res['missing_programs']}\n")
    lines.append("## Universal pitch subspace (LOPO, pooled ridge decoder)\n")
    lines.append(f"Leave-one-program-out R² deciles: {d}\n")
    lines.append(f"Mean LOPO R² = {res['universal_subspace']['lopo_r2_mean']}. "
                 f"Pooled pitch subspace dimension (PCA n90 of pooled sweep vectors) = "
                 f"{res['universal_subspace']['pooled_pitch_subspace_dim_n90']}.\n")
    lines.append("**10 worst-transferring programs:**\n")
    for w in worst:
        lines.append(f"- {w['name']} (#{w['program']}, {w['family']}): LOPO R² = {w['lopo_r2']}")
    lines.append("")
    lines.append("## Cross-program transfer / GM-family block structure\n")
    lines.append(f"Mean within-family transfer R² = {res['cross_program']['mean_within_family_transfer_r2']} "
                 f"vs mean cross-family transfer R² = {res['cross_program']['mean_cross_family_transfer_r2']}.\n")
    lines.append("### Hierarchical clusters (k=12, cosine of pitch-decoder weight vectors)\n")
    for k, c in cl.items():
        lines.append(f"- Cluster {k} (n={c['n']}, majority family {c['majority_family']}, "
                     f"purity {c['purity']}): {', '.join(c['members'][:8])}"
                     + (" ..." if len(c['members']) > 8 else ""))
    lines.append("")
    lines.append("## Jump detectability (pat5 vs pat1 control)\n")
    jd = res["jump_detect"]
    lines.append(f"Jump-detect balanced LDA acc range [{jd['jump_acc_min']}, {jd['jump_acc_max']}]. "
                 f"pat1 no-jump control mean acc = {jd['pat1_control_acc_mean']} (should be ~0.5). "
                 f"Correlation of jump-detect acc with per-program pitch-decoder R² = "
                 f"{jd['corr_jump_acc_vs_pitch_r2']}.\n")
    lines.append("## Interleave (pat2 E/G) separation\n")
    il = res["interleave_pat2"]
    lines.append(f"d' range [{il['dprime_min']}, {il['dprime_max']}], mean {il['dprime_mean']}.\n")
    lines.append("## Implications for melody LatCH multi-timbre training set\n")
    lines.append("(fill in after inspecting the numbers above: how many/which timbre clusters "
                 "must be sampled for coverage, worst-case instrument families to over-sample, "
                 "whether a single universal pitch readout is trainable at what R².)\n")
    lines.append("## Per-program table\n\nSee `per_program.csv` in this directory.\n")
    (BASE / "REPORT.md").write_text("\n".join(lines))


STAGES = {"gen": stage_gen, "render": stage_render, "encode": stage_encode, "analyze": stage_analyze}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="gen,render,encode,analyze")
    ap.add_argument("--jobs", type=int, default=12)
    a = ap.parse_args()
    for s in a.stages.split(","):
        s = s.strip()
        if not s:
            continue
        print(f"===== STAGE {s} =====", flush=True)
        if s == "render":
            stage_render(a.jobs)
        else:
            STAGES[s]()
