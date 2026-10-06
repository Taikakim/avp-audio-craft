"""H4 side test (CPU): do the knob directions line up with what the trained energy LatCH heads respond to?

The SA3 LatCH heads were trained on SAME-L latents; the H4 gate encoded with SAME-S. So, on the first and last
rung of every ladder (stage 1's ladders.npz):
  1. encode with SAME-L, and report SAME-S vs SAME-L agreement (cosine of time-mean latents, and of the
     per-ladder displacements d = last - first) -- whether SAME-S results speak for the medium model's space;
  2. per energy head h, the head's gradient direction at the first rung, g = d mean h(z, t) / dz summed over
     frames (the direction a uniform latent shift would have to take to raise the head), and its cosine with
     each ladder's SAME-L displacement. Null: cosine of g with displacements of the OTHER knobs' ladders.
Out: <dir>/head_alignment.json. Run: SAO/.venv/bin/python eval/h4_head_alignment.py [--dir ...]
"""
import argparse
import json
import os
import time

os.environ.setdefault("OMP_NUM_THREADS", "8")
import numpy as np
import torch

DIR = "/run/media/kim/Mantu/surge_200k_models/h4_gate"
HEAD_DIR = "/home/kim/Projects/SAO/stable-audio-3/latch_weights_sa3_medium"
HEADS = ("rms_energy_bass", "rms_energy_body", "rms_energy_mid", "rms_energy_air", "hardness", "spectral_flatness")


def unit(v):
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-12)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=DIR)
    ap.add_argument("--batch", type=int, default=8)
    a = ap.parse_args()
    torch.set_num_threads(int(os.environ["OMP_NUM_THREADS"]))
    d = np.load(f"{a.dir}/ladders.npz")
    axes = [str(x) for x in d["axes"]]
    ax_id, anc, rung = d["axis_ids"], d["anchor_ids"], d["rung"]
    S = int(rung.max()) + 1
    ends = np.where((rung == 0) | (rung == S - 1))[0]
    lpath = f"{a.dir}/latents_same_l_ends.npz"
    t0 = time.time()
    if os.path.exists(lpath):
        ZL = np.load(lpath)["z"].astype(np.float32)
    else:
        from stable_audio_3 import AutoencoderModel
        ae = AutoencoderModel.from_pretrained("same-l", device="cpu")
        out = []
        for s in range(0, len(ends), a.batch):
            x = torch.from_numpy(d["audio"][ends[s:s + a.batch]].astype(np.float32))
            out.append(ae.encode(torch.stack([x, x], 1), int(d["sample_rate"])).float().numpy())
            print(f"  same-l {s + len(x)}/{len(ends)}", flush=True)
        ZL = np.concatenate(out)
        np.savez(lpath, z=ZL.astype(np.float16), rows=ends)
    ZS = np.load(f"{a.dir}/latents_same_s.npz")["z"].astype(np.float32)[ends]
    ML, MS = ZL.mean(-1), ZS.mean(-1)
    pos = {int(r): i for i, r in enumerate(ends)}

    lad = []                                                          # (axis, first_row, last_row)
    for k in range(len(axes)):
        for an in np.unique(anc[ax_id == k]):
            idx = np.where((ax_id == k) & (anc == an))[0]
            lad.append((k, pos[int(idx[rung[idx] == 0][0])], pos[int(idx[rung[idx] == S - 1][0])]))
    lad_axis = np.array([l[0] for l in lad])
    DL = np.stack([ML[l2] - ML[l1] for _, l1, l2 in lad])
    DS = np.stack([MS[l2] - MS[l1] for _, l1, l2 in lad])
    res = {"axes": axes, "n_ladders": len(lad), "same_l_encode_seconds": round(time.time() - t0, 1),
           "same_s_vs_l": {"latent_cos_median": round(float(np.median((unit(ML) * unit(MS)).sum(1))), 4),
                           "displacement_cos_by_axis": {axes[k]: round(float(np.median(
                               (unit(DL[lad_axis == k]) * unit(DS[lad_axis == k])).sum(1))), 4)
                               for k in range(len(axes))}},
           "heads": {}}

    from stable_audio_3.models.latch import load_latch_from_checkpoint
    first = torch.from_numpy(ZL[[l[1] for l in lad]])
    for name in HEADS:
        p = f"{HEAD_DIR}/latch_sa3_{name}_best.pt"
        if not os.path.exists(p):
            continue
        h = load_latch_from_checkpoint(p, device="cpu").eval().requires_grad_(False)
        G = []
        for s in range(0, len(first), a.batch):
            z = first[s:s + a.batch].clone().requires_grad_(True)
            t = torch.full((len(z),), 0.001)
            h(z, t).mean().backward()
            G.append(z.grad.sum(-1).numpy())
        G = unit(np.concatenate(G))
        own = (G * unit(DL)).sum(1)
        other = np.array([float(np.mean([G[i] @ unit(DL[j]) for j in np.where(lad_axis != lad_axis[i])[0][:40]]))
                          for i in range(len(lad))])
        res["heads"][name] = {axes[k]: {"cos_median": round(float(np.median(own[lad_axis == k])), 4),
                                        "abs_cos_median": round(float(np.median(np.abs(own[lad_axis == k]))), 4),
                                        "null_other_knobs_cos_median": round(float(np.median(other[lad_axis == k])), 4)}
                              for k in range(len(axes))}
    print(json.dumps(res, indent=1))
    json.dump(res, open(f"{a.dir}/head_alignment.json", "w"), indent=1)


if __name__ == "__main__":
    main()
