"""H4 gate, stage 2 (SA3 venv, CPU): does each Surge knob have ONE direction in SAME latent space?

Input: stage 1's ladders.npz (stable-audio-tools/scripts/synth_inversion/h4_render_ladders.py): per knob axis,
N anchor patches each swept along that knob over S rungs, rendered as the same 4 s bass phrase. Each render
is encoded with SAME-S (CPU) and time-mean-pooled to one 256-d vector m. Per ladder, d = m[last] - m[first].

Measures (EXPERIMENTS.md H4), each against its null:
  consistency   mean pairwise cosine of d within a knob, vs (a) random 256-d directions and (b) the same
                statistic with the knob labels shuffled across ladders (keeps any shared "all knobs move
                this way" component, so it is the honest bar); p = share of 2000 shuffles >= observed
  identify      leave-one-out: knob direction u_k = mean unit d of the OTHER ladders; a held-out ladder is
                assigned the knob whose u_k it is most cosine-aligned with (chance 1/n_axes)
  monotone      Spearman(rung, projection of the held-out ladder's rungs onto its own knob's u_k); null =
                |Spearman| onto a random direction
  straightness  |m[last]-m[first]| / sum |m[r+1]-m[r]| (1 = a straight path)
  readout       ridge latent -> knob setting, held-out patches (the melody precedent's linear move), vs
                loudness alone
  by distance   within-knob pair cosine in tertiles of anchor-to-anchor latent distance; falling with
                distance means a tangent field v_k(z), not one vector per knob
Out: <dir>/same_directions.json + latents_same_s.npz; run_meta.json is updated with the result.
Run: SAO/.venv/bin/python eval/h4_same_directions.py [--dir /run/media/kim/Mantu/surge_200k_models/h4_gate]
"""
import argparse
import json
import os
import time

os.environ.setdefault("OMP_NUM_THREADS", "8")
import numpy as np
import torch
from scipy.stats import spearmanr

DIR = "/run/media/kim/Mantu/surge_200k_models/h4_gate"


def encode_all(audio, sr, batch):
    from stable_audio_3 import AutoencoderModel
    ae = AutoencoderModel.from_pretrained("same-s", device="cpu")
    out = []
    for s in range(0, len(audio), batch):
        x = torch.from_numpy(audio[s:s + batch].astype(np.float32))
        x = torch.stack([x, x], dim=1)                           # mono -> identical stereo
        z = ae.encode(x, sr)
        out.append(z.float().cpu().numpy())
        if s % (batch * 20) == 0:
            print(f"  encoded {s + len(x)}/{len(audio)}", flush=True)
    return np.concatenate(out)


def unit(v):
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-12)


def mean_pair_cos(D):
    U = unit(D)
    C = U @ U.T
    n = len(U)
    return float((C.sum() - n) / (n * (n - 1)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=DIR)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--perms", type=int, default=2000)
    a = ap.parse_args()
    torch.set_num_threads(int(os.environ["OMP_NUM_THREADS"]))
    d = np.load(f"{a.dir}/ladders.npz")
    axes = [str(x) for x in d["axes"]]
    lat_path = f"{a.dir}/latents_same_s.npz"
    t0 = time.time()
    if os.path.exists(lat_path):
        Z = np.load(lat_path)["z"]
    else:
        Z = encode_all(d["audio"], int(d["sample_rate"]), a.batch)
        np.savez(lat_path, z=Z.astype(np.float16))
    enc_sec = time.time() - t0
    M = Z.astype(np.float32).mean(axis=-1)                         # [N, 256]
    ax_id, anc, rung = d["axis_ids"], d["anchor_ids"], d["rung"]
    S = int(rung.max()) + 1

    ladders, lad_axis = [], []                                     # [L, S, 256]
    for k in range(len(axes)):
        for an in np.unique(anc[ax_id == k]):
            idx = np.where((ax_id == k) & (anc == an))[0]
            ladders.append(M[idx[np.argsort(rung[idx])]])
            lad_axis.append(k)
    L, lad_axis = np.stack(ladders), np.array(lad_axis)
    D = L[:, -1] - L[:, 0]
    rng = np.random.default_rng(0)

    res = {"axes": axes, "n_ladders": int(len(L)), "rungs": S, "latent_frames": int(Z.shape[-1]),
           "encode_seconds": round(enc_sec, 1), "per_axis": {}}
    rand_cos = mean_pair_cos(rng.standard_normal((50, D.shape[1])))
    res["null_random_pair_cos"] = round(rand_cos, 4)
    res["cross_axis_pair_cos"] = round(float(np.mean([
        unit(D[i]) @ unit(D[j]) for i in range(len(D)) for j in range(len(D)) if lad_axis[i] != lad_axis[j]])), 4)

    within = {k: mean_pair_cos(D[lad_axis == k]) for k in range(len(axes))}
    perm = {k: [] for k in range(len(axes))}
    for _ in range(a.perms):
        lab = rng.permutation(lad_axis)
        for k in range(len(axes)):
            perm[k].append(mean_pair_cos(D[lab == k]))

    # Leave-one-out directions: identification and monotonicity.
    Ud = unit(D)
    hits, rhos, rho_null = np.zeros(len(L), bool), np.zeros(len(L)), np.zeros(len(L))
    for i in range(len(L)):
        keep = np.arange(len(L)) != i
        U = np.stack([unit(Ud[keep & (lad_axis == k)].mean(0)) for k in range(len(axes))])
        hits[i] = int(np.argmax(U @ Ud[i])) == lad_axis[i]
        rhos[i] = spearmanr(np.arange(S), L[i] @ U[lad_axis[i]]).statistic
        rho_null[i] = abs(spearmanr(np.arange(S), L[i] @ unit(rng.standard_normal(L.shape[-1]))).statistic)
    steps = np.linalg.norm(np.diff(L, axis=1), axis=-1).sum(1)
    straight = np.linalg.norm(D, axis=-1) / (steps + 1e-12)

    for k, name in enumerate(axes):
        sel = lad_axis == k
        Dk, A0 = Ud[sel], L[sel, 0]
        iu = np.triu_indices(len(Dk), 1)
        cos_pairs = (Dk @ Dk.T)[iu]
        dist = np.linalg.norm(A0[:, None] - A0[None], axis=-1)[iu]
        q = np.quantile(dist, [1 / 3, 2 / 3])
        bins = [cos_pairs[dist <= q[0]], cos_pairs[(dist > q[0]) & (dist <= q[1])], cos_pairs[dist > q[1]]]
        pk = np.array(perm[k])
        res["per_axis"][name] = {
            "consistency": round(within[k], 4),
            "shuffled_mean": round(float(pk.mean()), 4), "shuffled_p95": round(float(np.quantile(pk, 0.95)), 4),
            "p_shuffle": round(float((pk >= within[k]).mean()), 4),
            "identify_acc": round(float(hits[sel].mean()), 3), "identify_chance": round(1 / len(axes), 3),
            "monotone_spearman_median": round(float(np.median(rhos[sel])), 3),
            "monotone_share_rho_gt_0.8": round(float((rhos[sel] > 0.8).mean()), 3),
            "monotone_null_random_dir_abs_median": round(float(np.median(rho_null[sel])), 3),
            "straightness_median": round(float(np.median(straight[sel])), 3),
            "pair_cos_by_anchor_distance_tertile": [round(float(b.mean()), 4) for b in bins],
            "displacement_norm_median": round(float(np.median(np.linalg.norm(D[sel], axis=-1))), 3),
        }
    res["identify_acc_overall"] = round(float(hits.mean()), 3)

    # Is a knob direction just LOUDNESS? r = the latent direction that tracks render RMS (dB) across all
    # renders; then re-measure each knob with the r component projected out of every displacement.
    aud = d["audio"].astype(np.float32)
    rms_db = 20 * np.log10(np.sqrt((aud ** 2).mean(axis=1)) + 1e-9)
    Mc, rc = M - M.mean(0), rms_db - rms_db.mean()
    r = unit(rc @ Mc / (rc @ rc))
    res["rms_direction_r2"] = round(float(1 - ((Mc - np.outer(rc, rc @ Mc / (rc @ rc))) ** 2).sum() / (Mc ** 2).sum()), 4)
    Dr = D - np.outer(D @ r, r)
    lad_rms = np.array([rms_db[(ax_id == lad_axis[i]) & (anc == an)] for i, an in enumerate(
        [an for k in range(len(axes)) for an in np.unique(anc[ax_id == k])])])
    perm_r = {k: [] for k in range(len(axes))}
    for _ in range(a.perms):
        lab = rng.permutation(lad_axis)
        for k in range(len(axes)):
            perm_r[k].append(mean_pair_cos(Dr[lab == k]))
    Udr, hits_r = unit(Dr), np.zeros(len(L), bool)
    for i in range(len(L)):
        keep = np.arange(len(L)) != i
        U = np.stack([unit(Udr[keep & (lad_axis == k)].mean(0)) for k in range(len(axes))])
        hits_r[i] = int(np.argmax(U @ Udr[i])) == lad_axis[i]
    for k, name in enumerate(axes):
        sel = lad_axis == k
        c = mean_pair_cos(Dr[sel])
        pk = np.array(perm_r[k])
        res["per_axis"][name]["loudness_removed"] = {
            "rms_share_of_displacement_median": round(float(np.median((D[sel] @ r) ** 2 / (D[sel] ** 2).sum(1))), 4),
            "cos_mean_direction_vs_rms_direction": round(float(unit(Ud[sel].mean(0)) @ r), 4),
            "rms_change_db_median": round(float(np.median(lad_rms[sel, -1] - lad_rms[sel, 0])), 2),
            "consistency": round(c, 4), "shuffled_p95": round(float(np.quantile(pk, 0.95)), 4),
            "p_shuffle": round(float((pk >= c).mean()), 4), "identify_acc": round(float(hits_r[sel].mean()), 3)}
    # Readout (the melody precedent's move): ridge from the pooled latent to the knob setting, fitted across
    # patches and scored on held-out PATCHES (5 folds by anchor). Baseline: render loudness alone.
    def ridge_cv(X, y, groups, alpha=1000.0, folds=5):
        ug = np.unique(groups)
        fold_of = {g: i % folds for i, g in enumerate(rng.permutation(ug))}
        f = np.array([fold_of[g] for g in groups])
        pred = np.zeros_like(y)
        for i in range(folds):
            tr, te = f != i, f == i
            mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-6
            Xt = (X[tr] - mu) / sd
            w = np.linalg.solve(Xt.T @ Xt + alpha * np.eye(X.shape[1]), Xt.T @ (y[tr] - y[tr].mean()))
            pred[te] = ((X[te] - mu) / sd) @ w + y[tr].mean()
        return pred
    for k, name in enumerate(axes):
        rows = ax_id == k
        y, g = rung[rows].astype(np.float64), anc[rows]
        out = {}
        for tag, X in (("latent", M[rows].astype(np.float64)), ("loudness_only", rms_db[rows, None].astype(np.float64))):
            pr = ridge_cv(X, y, g)
            r2 = 1 - ((pr - y) ** 2).sum() / ((y - y.mean()) ** 2).sum()
            rho = [spearmanr(np.arange(S), pr[g == an][np.argsort(y[g == an])]).statistic for an in np.unique(g)]
            out[tag] = {"r2_heldout_patches": round(float(r2), 3), "ladder_spearman_median": round(float(np.nanmedian(rho)), 3)}
        res["per_axis"][name]["readout"] = out
    print(json.dumps(res, indent=1))
    json.dump(res, open(f"{a.dir}/same_directions.json", "w"), indent=1)
    meta_p = f"{a.dir}/run_meta.json"
    meta = json.load(open(meta_p)) if os.path.exists(meta_p) else {}
    meta.update({"stage2_script": "SAO/eval/h4_same_directions.py", "encoder": "SAME-S (CPU), time-mean pooled",
                 "hypothesis": "Each Surge knob moves SAME latents along one direction shared across patches "
                               "(within-knob displacement cosine above the label-shuffled null).",
                 "result": res})
    json.dump(meta, open(meta_p, "w"), indent=1)


if __name__ == "__main__":
    main()
