#!/usr/bin/env python
"""goa_caption_task.py — LUMI worker: Music Flamingo (transformers, bf16) captions over one
shard of the goa_archive (CONTINUITY 2026-07-29). GGUF path dropped per Kim ("now that we
have VRAM, we don't need the MF GGUF, quality will also be better") — this uses mir's
src/classification/music_flamingo_transformers.py (MusicFlamingoForConditionalGeneration
from the lashahub transformers fork, staged in the offload venv) with the HF weights
pre-downloaded to $MODELS (HF_HUB_OFFLINE on compute nodes).

Prompts: PROMPT_TYPES env / --prompts, comma-sep keys of DEFAULT_PROMPTS
(full,technical,genre_mood,instrumentation,structure). Default 'full' (~28s/track locally
=> ~24h for 23k across 8 GCDs; each extra prompt type adds ~the same again).

Output: <out>/json/<sha1(relpath)>.json  {key, rel, path, captions{type: text}, wall_s}
— sha1(relpath) keying MATCHES the local goa_archive_features index (same rel layout),
so captions join features/quality/clusters by key. Resumable: skips existing json.
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

_mio = os.path.join(tempfile.gettempdir(), f"miopen-cap-{os.getpid()}")
os.makedirs(_mio, exist_ok=True)
os.environ.setdefault("MIOPEN_USER_DB_PATH", _mio)
os.environ.setdefault("MIOPEN_CUSTOM_CACHE_DIR", _mio)
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("MIOPEN_DISABLE_CACHE", "1")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")

_LUMI_MODELS = "/project/project_465003186/models"
if os.path.isdir(_LUMI_MODELS):
    os.environ.setdefault("HF_HOME", _LUMI_MODELS)
    os.environ.setdefault("HF_HUB_OFFLINE", "1")

MIR_SRC = os.environ.get("MIR_SRC", "/project/project_465003186/code/mir-src")
sys.path.insert(0, MIR_SRC)


def compose_hint(base: str, meta: str):
    """Combine the corpus-level genre hint with a track's own ID3-metadata clause.

    Module level, not a closure, so it is testable without loading Music Flamingo — the composition
    rule is the whole point of the per-track map and it fails silently when wrong (a caption that
    asserts the wrong era looks exactly like a caption that asserts the right one).

    Returns (text, source); source is written into every caption json so an audit can tell hinted
    from unhinted from the artifact alone.
    """
    text = " ".join(x for x in (base or "", meta or "") if x)
    if not text:
        return None, None
    return text, ("per_track+global" if meta and base else "per_track" if meta else "global")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", required=True)
    ap.add_argument("--archive", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--prompts", default=os.environ.get("PROMPT_TYPES", "full"),
                    help="comma-sep DEFAULT_PROMPTS keys")
    ap.add_argument("--genre-hint", default=os.environ.get("GENRE_HINT"),
                    help="known genre to give Music Flamingo as ground truth instead of "
                         "asking it to guess (e.g. a niche/regional tag it wouldn't infer "
                         "on its own) -- prepended to each selected prompt's text")
    ap.add_argument("--genre-hint-map", default=os.environ.get("GENRE_HINT_MAP"),
                    help="JSON {sha1(relpath): hint} for PER-TRACK hints (build with "
                         "eval/build_caption_hint_map.py from mir's ID3 metadata). Falls back to "
                         "--genre-hint per track when a key is absent. A single global hint asserts "
                         "one era and genre for every track, which is fine for a uniform corpus and "
                         "wrong for one spanning 1980s-2020s.")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    archive = Path(a.archive)
    jdir = Path(a.out) / "json"
    jdir.mkdir(parents=True, exist_ok=True)
    ptypes = [p.strip() for p in a.prompts.split(",") if p.strip()]

    tracks = [Path(l.strip()) for l in open(a.shard) if l.strip()]

    def key(p):
        return hashlib.sha1(str(p.relative_to(archive)).encode()).hexdigest()

    todo = [p for p in tracks if not (jdir / f"{key(p)}.json").exists()]
    if a.limit:
        todo = todo[: a.limit]
    print(f"[caption] shard {Path(a.shard).name}: {len(todo)}/{len(tracks)} to do "
          f"(prompts: {ptypes})", flush=True)
    if not todo:
        return

    from classification.music_flamingo_transformers import MusicFlamingoTransformers, DEFAULT_PROMPTS
    for pt in ptypes:
        assert pt in DEFAULT_PROMPTS, f"unknown prompt type {pt!r} (have {list(DEFAULT_PROMPTS)})"
    # genre-hint mode: give the genre as ground truth rather than asking Flamingo to guess
    # it -- built once per prompt type, passed as `prompt=` (overrides `prompt_type=` in
    # .analyze(), per its own docstring), so DEFAULT_PROMPTS itself stays untouched.
    hint_map = {}
    if a.genre_hint_map:
        try:
            hint_map = json.load(open(a.genre_hint_map))
            print(f"[caption] per-track hint map: {len(hint_map)} entries <- {a.genre_hint_map}",
                  flush=True)
        except Exception as e:
            print(f"[caption] FATAL: --genre-hint-map unreadable ({e}). Refusing to fall back to the "
                  f"global hint silently -- that is how a corpus gets captioned with the wrong era.",
                  flush=True)
            raise
    if a.genre_hint:
        print(f"[caption] fallback hint: '{a.genre_hint}'", flush=True)

    # The two hints COMPOSE, they do not replace each other. --genre-hint is the corpus's genre
    # family ("goa trance and psytrance"); the map entry is that track's real ID3 metadata (year,
    # label, tags). Letting the map REPLACE the global hint would silently drop genre grounding for
    # any track whose metadata has a year but no tags -- reintroducing the exact 1.2%-mention failure
    # the hint exists to fix, on the subset that looked best covered.
    base = f"This track's genre is: {a.genre_hint}." if a.genre_hint else ""

    def hint_for(p):
        return compose_hint(base, hint_map.get(key(p)))

    def prompts_for(p):
        h, _src = hint_for(p)
        if not h:
            return None
        return {pt: f"{h} {DEFAULT_PROMPTS[pt]}" for pt in ptypes}

    use_fa2 = os.environ.get("MF_USE_FA2", "0") == "1"   # multitorch-image experiment:
    # flash_attention_2 is a SEPARATE transformers branch from sdpa — may engage where
    # sdpa was ignored. Requires flash-attn in the image (build_offload_venv_mt.sh).
    mf = MusicFlamingoTransformers(torch_dtype="bfloat16", use_flash_attention=use_fa2)
    print(f"[caption] Music Flamingo loaded (bf16 transformers, fa2={use_fa2})", flush=True)

    # Length cap = THE memory lever. The MF audio tower runs its OWN full-sequence
    # attention (ignores attn_implementation — probe-proven: sdpa loaded, allocs identical)
    # with a materialized score matrix, so memory is QUADRATIC in audio length: 600s still
    # tried a single 23.66 GiB alloc (probe 20423145, on the truncated wav itself).
    # 300s -> ~1/4 of that (~6 GiB peak) = fits a 64 GB GCD with lots of headroom.
    # A 5-min excerpt is an adequate basis for a training caption.
    MAX_SEC = float(os.environ.get("CAPTION_MAX_SEC", "300"))

    def caption_source(p):
        """(path_to_analyze, truncated?) — temp-wav truncation for overlong tracks, and
        an unconditional m4a->wav pass: Music Flamingo's own loader needs torchcodec for
        m4a (not in this image) even though librosa/audioread reads these files fine
        (proven by goa_sep_task.py succeeding on the same m4a sources) -- so any m4a is
        routed through librosa+soundfile regardless of duration, not just overlong ones."""
        import librosa
        try:
            dur = librosa.get_duration(path=str(p))
        except Exception:
            return p, False
        # Route every format we have NOT proven MF's own loader handles through librosa+soundfile,
        # not just m4a. flac / wav / mp3 are proven at corpus scale (23k mp3 on the big goa set,
        # 2891 flac in flight 2026-08-18); ogg, opus and aiff are not, and Goa_Separated turns out
        # to hold 474 ogg + 9 aiff. The transcode costs a load+write per track — far less than
        # discovering the gap as 483 failures three hours into a job.
        needs_transcode = p.suffix.lower() in (".m4a", ".ogg", ".opus", ".aiff", ".aif")
        if dur <= MAX_SEC and not needs_transcode:
            return p, False
        import soundfile as sf
        y, sr = librosa.load(str(p), sr=None, mono=False, duration=MAX_SEC)
        tmp = Path(tempfile.gettempdir()) / f"cap-trunc-{os.getpid()}.wav"
        sf.write(str(tmp), y.T if y.ndim > 1 else y, int(sr))
        return tmp, dur > MAX_SEC

    n_ok = n_fail = 0
    for k, p in enumerate(todo):
        t0 = time.time()
        try:
            src, truncated = caption_source(p)
            genre_prompts = prompts_for(p)
            try:
                caps = {pt: mf.analyze(src, prompt=genre_prompts[pt] if genre_prompts else None,
                                        prompt_type=pt) for pt in ptypes}
            finally:
                # clear on FAIL too — an OOM leaves 20+ GiB of fragmented reservations
                # that cascade into the NEXT track's failure (probe: rank 5's 2nd OOM
                # showed 24 GiB reserved-unallocated carried over from the 1st)
                mf.clear_cache()
            (jdir / f"{key(p)}.json").write_text(json.dumps(
                {"key": key(p), "rel": str(p.relative_to(archive)), "path": str(p),
                 "captions": caps, "model": "nvidia/music-flamingo-hf bf16",
                 "genre_hint": hint_for(p)[0], "genre_hint_source": hint_for(p)[1],
                 "truncated_to_s": MAX_SEC if truncated else None,
                 "wall_s": round(time.time() - t0, 1)}))
            n_ok += 1
            first = next(iter(caps.values()), "")[:70]
            print(f"[{k+1}/{len(todo)}] {p.stem}  {time.time()-t0:.1f}s  \"{first}...\"", flush=True)
        except Exception as e:
            n_fail += 1
            print(f"[FAIL] {p} {type(e).__name__}: {str(e)[:160]}\n{traceback.format_exc()[-400:]}",
                  flush=True)
    print(f"[caption] shard done: ok={n_ok} fail={n_fail}", flush=True)


if __name__ == "__main__":
    main()
