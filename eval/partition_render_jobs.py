#!/usr/bin/env python3
"""Partition the length-variant render terminal-checkpoint job list into a LUMI queue (checkpoints
present on LUMI scratch -> 8-GCD sbatch) and a local queue (older local-only checkpoints -> desktop
overnight pass), per the 2026-08-02 length-variant spec (§8). Flags any local-only x T>=2048 job:
those cannot render native locally (display-crash guard) NOR on LUMI (checkpoint absent) -> needs its
ckpt pushed to LUMI or native skipped.

Input:  ~/lumi_ckpt_inventory.txt  (lines "SIZE /scratch/.../runs/<label>/epoch=N-step=M.ckpt")
Output: prints the two queues + emits --only-labels lists to paste into model_matrix_gen.py, and
        writes render_jobs_{lumi,local}.txt next to this script.
Read-only w.r.t. LUMI; no GPU. Reuses model_matrix_gen.build_jobs so the job universe is identical.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import model_matrix_gen as M  # noqa: E402

INV = Path.home() / "lumi_ckpt_inventory.txt"


def epoch_of(tag):
    m = re.search(r"(\d+)$", tag)
    return int(m.group(1)) if m else -1


def ckpt_stem(p):
    """normalize a checkpoint filename to its epoch=N-step=M identity, dropping the
    .weights.ckpt (slim) / .ckpt (fat) / .safetensors suffix so local-slim == LUMI-fat."""
    n = Path(str(p)).name
    return re.sub(r"\.(weights\.ckpt|ckpt|safetensors)$", "", n)


def T_of(label):
    m = re.search(r"t(256|512|1024|2048|4096)", label)
    return int(m.group(1)) if m else 512


def main():
    if not INV.exists():
        raise SystemExit(f"missing {INV} -- run the LUMI inventory command first (spec §12b)")

    # terminal checkpoint per label (medium job universe; the ptm pass reuses the same ckpts).
    # Exclude the xft* families -- hidden from the board (borked) and not rendered, same as
    # build_dora_table_page.HIDE_MODEL_PREFIXES.
    jobs = [j for j in M.build_jobs() if not j[0].startswith("xft")]
    best = {}
    for label, ckpt_path, tag in jobs:
        if label not in best or epoch_of(tag) > epoch_of(best[label][2]):
            best[label] = (label, ckpt_path, tag)
    terminal = sorted(best.values())

    # LUMI inventory indexed by ckpt stem -> the full paths carrying it
    lumi_by_stem = {}
    for ln in INV.read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        path = ln.split(" ", 1)[1] if " " in ln else ln
        lumi_by_stem.setdefault(ckpt_stem(path), []).append(path)

    def on_lumi(label, ckpt_path):
        if ckpt_path is None:            # base model (no adapter) -> render locally
            return False
        stem = ckpt_stem(ckpt_path)
        # a LUMI ckpt matches iff same epoch=N-step=M stem AND the run label is an exact
        # path component (substring would cross-match label-prefixed siblings)
        return any(label in Path(p).parts for p in lumi_by_stem.get(stem, []))

    lumi_q, local_q, flagged = [], [], []
    for label, ckpt_path, tag in terminal:
        T = T_of(label)
        row = (label, tag, T, ckpt_path)
        if on_lumi(label, ckpt_path):
            lumi_q.append(row)
        else:
            local_q.append(row)
            if T >= 2048:
                flagged.append(row)

    def dump(rows, name):
        (HERE / f"render_jobs_{name}.txt").write_text(
            "\n".join(f"{lbl}\t{tag}\tT{T}\t{ck}" for lbl, tag, T, ck in rows) + "\n")

    dump(lumi_q, "lumi")
    dump(local_q, "local")

    print(f"terminal checkpoints: {len(terminal)}  "
          f"(LUMI {len(lumi_q)} | local {len(local_q)})\n")

    from collections import Counter
    for name, q in (("LUMI 8-GCD queue", lumi_q), ("LOCAL overnight queue", local_q)):
        tc = Counter(T for _, _, T, _ in q)
        print(f"== {name}: {len(q)} jobs == T-mix: "
              + ", ".join(f"T{t}:{n}" for t, n in sorted(tc.items())))
        print("   --only-labels " + ",".join(lbl for lbl, _, _, _ in q))
        print()

    if flagged:
        print(f"!! {len(flagged)} LOCAL-ONLY x T>=2048 (cannot native-render locally OR on LUMI):")
        for lbl, tag, T, ck in flagged:
            print(f"     {lbl} {tag} T{T}  -> push ckpt to LUMI, or skip its native")
        print("   (their 20s + ptm-cfg1 still render locally; only the native cell is blocked)")
    else:
        print("no local-only x T>=2048 jobs -- the split is clean (native-safe on both legs)")


if __name__ == "__main__":
    main()
