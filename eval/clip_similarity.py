#!/usr/bin/env python3
"""How similar do checkpoints SOUND? Paired CLAP-embedding similarity over the canonical prompts.

For each requested (label, ckpt) this embeds its standard 20 s clip at cfg7/w100 for every canonical
prompt (same prompt + seed across models, so clips are directly paired), with the same LAION-CLAP
audio encoder the board's CLAP column uses. Model-vs-model similarity = mean over the shared prompts
of the cosine between the two clips' embeddings. Written 2026-09-27 (W) for the goa5k ablation
listening pass ("They have a very similar sound"); CPU is fine.

Run (SAO/.venv has laion_clap):
  .venv/bin/python eval/clip_similarity.py --model base:base --model ablation_goa5k_a00_full:step=1011 ... \
      [--device cpu] [--out report.md]
"""
import argparse
import sys
from pathlib import Path

import numpy as np

RD = Path("/run/media/kim/Mantu/sa3_lora_runs/model_matrix")
ST = Path.home() / "evals_aac/model_matrix"
CANON = ["rb_common_0", "rb_common_1", "rb_common_2", "rb_mid_3", "rb_mid_4", "rb_mid_5",
         "rb_rare_6", "rb_rare_7", "rb_rare_8", "kl_0", "kl_1", "kl_2"]


def find_clip(label, ckpt, pid):
    """Standard (not __dNN native, not __stN) cfg7/w100 clip; wav preferred (lossless), else m4a."""
    stem = f"{label}__{ckpt}__cfg7__w100__{pid}__s"
    for d, ext in ((RD, ".wav"), (RD, ".m4a"), (ST, ".m4a")):
        for f in sorted(d.glob(stem + "*" + ext)):
            rest = f.name[len(stem):-len(ext)]
            if rest.isdigit():
                return f
    return None


def load_clap(device):
    import torch
    _argv = sys.argv[:]
    sys.argv = [_argv[0]]          # laion_clap parses argv at import (see clap_score.py)
    try:
        import laion_clap
    finally:
        sys.argv = _argv
    m = laion_clap.CLAP_Module(enable_fusion=False, amodel="HTSAT-tiny", device=device)
    _l, _lsd = torch.load, m.model.load_state_dict
    torch.load = lambda *a, **k: _l(*a, **{**k, "weights_only": False})
    m.model.load_state_dict = lambda sd, strict=True: _lsd(sd, strict=False)
    try:
        m.load_ckpt(model_id=1)    # same 630k+audioset non-fusion checkpoint as clap_score.py
    finally:
        torch.load, m.model.load_state_dict = _l, _lsd
    m.eval()
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", action="append", required=True, help="label:ckpt (repeatable)")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    import librosa
    import torch
    torch.set_num_threads(8)
    model = load_clap(a.device)

    def emb(path):
        wav, _ = librosa.load(str(path), sr=48000, mono=True)
        with torch.no_grad():
            x = torch.from_numpy(wav).float().unsqueeze(0)
            try:
                e = model.get_audio_embedding_from_data(x=x, use_tensor=True)
            except TypeError:
                e = model.get_audio_embedding_from_data(x=x.numpy())
        e = e.float().cpu().numpy() if hasattr(e, "detach") else np.asarray(e, dtype=np.float32)
        v = e[0]
        return v / (np.linalg.norm(v) + 1e-9)

    names, E = [], {}
    for spec in a.model:
        label, ckpt = spec.rsplit(":", 1)
        got = {}
        for pid in CANON:
            f = find_clip(label, ckpt, pid)
            if f is not None:
                got[pid] = emb(f)
        print(f"[sim] {spec}: {len(got)}/{len(CANON)} clips", flush=True)
        if got:
            names.append(spec)
            E[spec] = got
    n = len(names)
    S = np.full((n, n), np.nan)
    for i in range(n):
        for j in range(n):
            shared = sorted(set(E[names[i]]) & set(E[names[j]]))
            if shared:
                S[i, j] = float(np.mean([E[names[i]][p] @ E[names[j]][p] for p in shared]))
    short = [s.split(":")[0].replace("ablation_goa5k_", "") for s in names]
    lines = ["| | " + " | ".join(short) + " |", "|---|" + "---|" * n]
    for i in range(n):
        lines.append(f"| **{short[i]}** | " + " | ".join(f"{S[i, j]:.3f}" for j in range(n)) + " |")
    nn = []
    for i in range(n):
        row = [(S[i, j], short[j]) for j in range(n) if j != i and not np.isnan(S[i, j])]
        if row:
            best = max(row)
            nn.append(f"- **{short[i]}**: nearest = {best[1]} ({best[0]:.3f})")
    txt = ("# Paired CLAP similarity (cfg7/w1, canonical prompts, same seed per prompt)\n\n"
           "Cosine of LAION-CLAP audio embeddings, averaged over the shared prompts. 1.0 = identical.\n\n"
           + "\n".join(lines) + "\n\n## Nearest neighbour\n\n" + "\n".join(nn) + "\n")
    print(txt)
    if a.out:
        a.out.write_text(txt)


if __name__ == "__main__":
    main()
