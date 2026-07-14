#!/usr/bin/env python3
"""mf_fill_pass.py — overnight Music-Flamingo caption fill (Kim direct 2026-07-14).

Fills the two caption-coverage holes found while building the longform sidecars:
  * 110 goa flamingo-budget tracks that were selected (stratified over the
    36-cluster division) but never actually MF-captioned;
  * 18 avp parent tracks whose crops all lack a t3 (the 157 'absent' crops in
    lumi/avp_longform_sidecar_provenance.json).

Per track: MF 'full' caption (whole full_mix, trim_frac=0.6 per Kim's 2026-07-08
finding — descriptions don't lose accuracy, big speedup) written into the track's
.INFO (music_flamingo_full [+ genre_mood for avp, which the Granite pass reads]).
Then: granite_avp_pass.py rebuilds captions_tiered.json, the goa fills are
appended to eval/kimlong_pool.json (source-tagged), and
eval/build_longform_sidecars.py regenerates both sidecars + provenance.

Resumable: tracks whose .INFO already carries music_flamingo_full are skipped.
GPU-guarded: aborts if VRAM is busy (>4 GB used) so it never contends.

Run (mir venv — MF wraps llama-mtmd-cli, model Q6_K, GPU offload):
  /home/kim/Projects/mir/mir/bin/python eval/mf_fill_pass.py [--dry-run] [--limit N]
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, "/home/kim/Projects/mir/src")

SAO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOA_ROOT = "/run/media/kim/Mantu/ai-music/Goa_Separated"
AVP_ROOT = "/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d/avp-analyzed"
POOL = os.path.join(SAO, "eval", "kimlong_pool.json")
BUDGET = "/home/kim/Projects/mir/data/feature_tables/flamingo_budget.json"
AVP_PROV = os.path.join(SAO, "lumi", "avp_longform_sidecar_provenance.json")
MIR_PY = "/home/kim/Projects/mir/mir/bin/python"


def vram_used_gb() -> float:
    try:
        out = subprocess.run(["rocm-smi", "--showmeminfo", "vram", "--json"],
                             capture_output=True, text=True, timeout=30).stdout
        j = json.loads(out)
        card = next(iter(j.values()))
        return int(card["VRAM Total Used Memory (B)"]) / 1e9
    except Exception:
        return -1.0


def atomic_write(path: str, obj) -> None:
    tmp = path + ".tmp"
    json.dump(obj, open(tmp, "w"), indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def targets():
    pool_tracks = {e["track"] for e in json.load(open(POOL))}
    budget = [e["track"] for e in json.load(open(BUDGET)) if e["source"] == "goa"]
    goa = [t for t in budget if t not in pool_tracks]
    prov = json.load(open(AVP_PROV))
    avp = sorted({p["parent_track"] for p in prov.values()
                  if p["tier"] is None and p["parent_track"]})
    return goa, avp


def info_path(root: str, track: str):
    d = os.path.join(root, track)
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if f.endswith(".INFO"):
            return os.path.join(d, f)
    return None


def full_mix(root: str, track: str):
    for ext in (".flac", ".wav", ".mp3"):
        p = os.path.join(root, track, f"full_mix{ext}")
        if os.path.exists(p):
            return p
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    goa, avp = targets()
    print(f"[mf-fill] targets: {len(goa)} goa budget tracks + {len(avp)} avp parents")
    if args.dry_run:
        for t in goa[:5]:
            print("  goa:", t, "| mix:", bool(full_mix(GOA_ROOT, t)),
                  "| info:", bool(info_path(GOA_ROOT, t)))
        for t in avp[:5]:
            print("  avp:", t, "| mix:", bool(full_mix(AVP_ROOT, t)),
                  "| info:", bool(info_path(AVP_ROOT, t)))
        return 0

    used = vram_used_gb()
    if used > 4.0:
        print(f"[mf-fill] ABORT: GPU busy ({used:.1f} GB used) — not contending")
        return 2

    from classification.music_flamingo import MusicFlamingoGGUF
    mf = MusicFlamingoGGUF(model="Q6_K", gpu_layers=99, trim_frac=0.6)

    jobs = ([("goa", GOA_ROOT, t, ("full",)) for t in goa]
            + [("avp", AVP_ROOT, t, ("full", "genre_mood")) for t in avp])
    if args.limit:
        jobs = jobs[:args.limit]

    done = skipped = failed = 0
    new_goa_prompts = {}
    for i, (src, root, track, prompt_types) in enumerate(jobs, 1):
        ip = info_path(root, track)
        mix = full_mix(root, track)
        if not ip or not mix:
            print(f"[{i}/{len(jobs)}] {track}: MISSING {'info' if not ip else 'mix'}")
            failed += 1
            continue
        info = json.load(open(ip))
        if info.get("music_flamingo_full"):
            skipped += 1
            if src == "goa":
                new_goa_prompts[track] = info["music_flamingo_full"]
            continue
        t0 = time.time()
        try:
            for pt in prompt_types:
                text = mf.analyze(mix, prompt_type=pt)
                if not text or len(text) < 40:
                    raise RuntimeError(f"suspiciously short '{pt}' output: {text!r}")
                info[f"music_flamingo_{pt}"] = text
            info["music_flamingo_model"] = "gguf_Q6_K_fill_2026-07-14"
            atomic_write(ip, info)
            if src == "goa":
                new_goa_prompts[track] = info["music_flamingo_full"]
            done += 1
            print(f"[{i}/{len(jobs)}] {track}: ok ({time.time()-t0:.0f}s)", flush=True)
        except Exception as e:
            failed += 1
            print(f"[{i}/{len(jobs)}] {track}: FAILED — {e}", flush=True)
    print(f"[mf-fill] MF done: {done} new, {skipped} cached, {failed} failed")

    # goa: append fills to the kimlong pool (track-level store the sidecar reads)
    pool = json.load(open(POOL))
    have = {e["track"] for e in pool}
    added = 0
    for track, prompt in sorted(new_goa_prompts.items()):
        if track in have:
            continue
        artist, _, title = track.partition(" - ")
        pool.append({"track": track, "artist": artist, "title": title,
                     "prompt": prompt, "source": "info_fill_2026-07-14"})
        added += 1
    if added:
        atomic_write(POOL, pool)
    print(f"[mf-fill] kimlong_pool: +{added} entries ({len(pool)} total)")

    # avp: granite revision + captions_tiered rebuild, then sidecar regen
    r1 = subprocess.run([MIR_PY, os.path.join(SAO, "eval", "granite_avp_pass.py")])
    r2 = subprocess.run([sys.executable, os.path.join(SAO, "eval", "build_longform_sidecars.py")])
    print(f"[mf-fill] granite pass rc={r1.returncode}, sidecar rebuild rc={r2.returncode}")
    return 0 if not failed and r1.returncode == 0 and r2.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
