#!/usr/bin/env python
"""genre_fusion_shards.py — pre-made shard-list builder for the genre-fusion generalization
probe (GHOST-NOTE 2026-08-21, Kim direct via WINTERMUTE's checkpoint-selection design).

WHY: same reasoning as make_caption_shards.py — the render job runs as 8 GCD-pinned ranks on
ONE node; each rank must read a DISJOINT, pre-computed list of work rather than deriving its own
shard (they would all render the same checkpoints). Unlike the caption/granite shards (one line
per TRACK), here each shard line is one render_matrix_cells.py INVOCATION — i.e. one
(checkpoint, native-length) pair, since render_matrix_cells.py already renders every prompt in
the pool for a given (label, ckpt, frames) in one call.

INPUT: a CHECKPOINTS file, one line per checkpoint: 'label epoch [ptm]' (whitespace-sep). Paths
are NOT hardcoded here — the actual .weights.ckpt is resolved on the LUMI side at shard-build
time via `find $SCRATCH/runs -path "*/<label>/epoch=<N>-*.weights.ckpt"`, since 12 different
training-run families each live under their own differently-named runs/ subfolder and guessing
the exact structure for each from outside LUMI is exactly the kind of thing that silently breaks
(see MASTER's whole "check the sbatch, not memory" thread from tonight).

OUTPUT: <out>/shard_NNN.txt, each line 'LABEL TAG CKPT_PATH FRAMES [--pt-medium --only-cfgs 1]'
ready to be read+exec'd by the sbatch wrapper. 2 lines per checkpoint (T256 + T512 native).

USAGE (on a LUMI login node, checkpoints file has real LUMI paths resolvable):
  python3 lumi/genre_fusion_shards.py --checkpoints lumi/genre_fusion_checkpoints.txt \
      --scratch-runs /scratch/project_465003186/runs --out /scratch/project_465003186/genre_fusion_probe/shards \
      --shards 8
"""
import argparse
import glob
import os
import sys
from pathlib import Path


def resolve_ckpt(scratch_runs, label, epoch):
    # epoch may carry a render-mode suffix from the ratings table (e.g. "90_20s", "153_native")
    # that is NOT part of the checkpoint filename -- that suffix describes which render row was
    # scored, not a distinct checkpoint. Strip to the leading digits before globbing.
    import re
    m = re.match(r"^\d+", epoch)
    epoch_num = m.group(0) if m else epoch
    # "_ptm" is a render/eval-time label (render_matrix_cells.py --pt-medium auto-appends it to
    # the OUTPUT label), not part of the training-run folder name -- the underlying checkpoint
    # is the same adapter, rendered against a different base model. Strip it before searching,
    # but the caller still uses the ORIGINAL label (with _ptm) for --label so the render/board
    # registration stays correctly distinguished from the non-ptm variant of the same run.
    search_label = re.sub(r"_ptm$", "", label)
    candidates = [search_label] + ([label] if label != search_label else [])
    hits = []
    for cand in candidates:
        # checkpoints are saved as plain 'epoch=N-step=M.ckpt' (fat, w/ optimizer state) --
        # a '.weights.ckpt' (stripped, slim) sibling only exists for SOME runs. Glob '*.ckpt'
        # (which also matches '*.weights.ckpt') and prefer the slim one when both exist.
        pattern = os.path.join(scratch_runs, "*", cand, f"epoch={epoch_num}-*.ckpt")
        hits = glob.glob(pattern)
        if hits:
            break
        # some families are one level shallower (RUN=${SCRATCH}/runs/<name> directly, no
        # intermediate family dir) -- try that too before giving up.
        pattern2 = os.path.join(scratch_runs, cand, f"epoch={epoch_num}-*.ckpt")
        hits = glob.glob(pattern2)
        if hits:
            break
    if not hits:
        return None, None
    weights = [h for h in hits if h.endswith(".weights.ckpt")]
    chosen = weights[0] if weights else hits[0]
    if len(hits) > 1 and not weights:
        print(f"[shards] WARNING: {len(hits)} matches for {label} epoch={epoch}, using first: {hits}",
              file=sys.stderr)
    return chosen, search_label


def fuzzy_candidates(scratch_runs, label):
    """Evidence-gathering for a failed resolve: list real run dirs that share a
    significant token with `label`, so the FATAL message shows what's actually on
    disk instead of forcing another blind guess at the family-dir naming."""
    import re
    tokens = [t for t in re.split(r"[_\-]", label) if len(t) >= 4 and not t.isdigit()]
    all_dirs = set()
    try:
        for entry in glob.glob(os.path.join(scratch_runs, "*", "*")):
            if os.path.isdir(entry):
                all_dirs.add(entry)
        for entry in glob.glob(os.path.join(scratch_runs, "*")):
            if os.path.isdir(entry):
                all_dirs.add(entry)
    except OSError:
        pass
    scored = []
    for d in all_dirs:
        base = os.path.basename(d)
        hit_tokens = [t for t in tokens if t in base]
        if hit_tokens:
            ckpts = sorted(glob.glob(os.path.join(d, "epoch=*.ckpt")))
            epochs = [os.path.basename(c).split("-")[0].split("=")[1] for c in ckpts]
            scored.append((len(hit_tokens), base, d, epochs))
    scored.sort(key=lambda x: -x[0])
    return scored[:8]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoints", required=True,
                    help="text file, one 'label epoch [ptm]' per line, blank/# lines skipped")
    ap.add_argument("--scratch-runs", required=True, help="$SCRATCH/runs root to search under")
    ap.add_argument("--out", required=True, help="shard output dir")
    ap.add_argument("--shards", type=int, default=8)
    a = ap.parse_args()

    rows = []
    failed = False
    for line in open(a.checkpoints):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        label, epoch = parts[0], parts[1]
        is_ptm = len(parts) > 2 and parts[2].lower() == "ptm"
        ckpt, matched_dirname = resolve_ckpt(a.scratch_runs, label, epoch)
        if ckpt is None:
            failed = True
            print(f"[shards] FATAL: no checkpoint found for label={label} epoch={epoch} "
                  f"under {a.scratch_runs} -- check the label/epoch against the real run dir "
                  f"name (they don't always match the model_matrix label 1:1)", file=sys.stderr)
            candidates = fuzzy_candidates(a.scratch_runs, label)
            if candidates:
                print(f"[shards]   near-miss run dirs on disk (shared-token match):", file=sys.stderr)
                for n_tok, base, d, epochs in candidates:
                    print(f"[shards]     {base}  epochs={epochs or '(no .weights.ckpt found)'}  ({d})",
                          file=sys.stderr)
            else:
                print(f"[shards]   no run dir under {a.scratch_runs} shares any token with '{label}' "
                      f"-- this family may live under a completely different name/path", file=sys.stderr)
            continue
        rows.append((label, epoch, is_ptm, ckpt))
        print(f"[shards] {label} ep{epoch}{' (ptm)' if is_ptm else ''} -> {ckpt}")

    if failed:
        print(f"[shards] one or more checkpoints failed to resolve (see FATAL lines above) -- "
              f"fix genre_fusion_checkpoints.txt against the near-miss dirs shown, then re-run. "
              f"Not writing any shards.", file=sys.stderr)
        sys.exit(1)

    # one shard-line per (checkpoint, native-length) pair
    lines = []
    for label, epoch, is_ptm, ckpt in rows:
        for frames in (256, 512):
            # always pin to ONE representative cfg -- without --only-cfgs the prompts JSON's
            # full cfgs:[1,7,16] grid renders all three per checkpoint (a 3x blowup never
            # intended here; this probe wants one cell per checkpoint/length, not a cfg sweep).
            # ptm (post-trained) native operating point is cfg1 (higher cfg "cooks" PT output);
            # DoRA-on-base operating point is cfg7 (established convention, matches the local
            # genre-fusion sweep's README).
            extra = "--pt-medium --only-cfgs 1" if is_ptm else "--only-cfgs 7"
            lines.append(f"{label} ep{epoch} {ckpt} {frames} {extra}".strip())

    os.makedirs(a.out, exist_ok=True)
    n = len(lines)
    per = -(-n // a.shards)  # ceil
    for i in range(a.shards):
        chunk = lines[i * per:(i + 1) * per]
        Path(a.out, f"shard_{i:03d}.txt").write_text("\n".join(chunk) + ("\n" if chunk else ""))
    print(f"[shards] {n} render invocations ({len(rows)} checkpoints x 2 lengths) "
          f"-> {a.shards} shards (~{per}/shard) in {a.out}")


if __name__ == "__main__":
    main()
