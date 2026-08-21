#!/usr/bin/env python3
"""One-step update-disappearance test — training-time LEARNABILITY diagnostic for SA3.

Top-ranked diagnostic from two independent precision deep-research reports (Zamirai
"Revisiting BFloat16 Training"; the Gemini + ChatGPT precision briefs). Measures whether
small weight updates DISAPPEAR when the optimizer master is low-precision, on the REAL
training path (one true rectified-flow minibatch + backward through the full 1.4B DiT) —
a bottleneck that forward SQNR misses.

The mechanism (see stable_audio_3/training/stochastic_rounding.py docstring): a bf16
weight w has 7 mantissa bits, so an update w <- w + d where |d| < ~0.5 ULP(w) is
DETERMINISTICALLY truncated back to w — the update vanishes. Stochastic rounding makes
E[stored] == w+d, so sub-ULP updates accumulate in expectation instead of dying.

We isolate the WRITEBACK-precision effect: the SAME fp32 AdamW update Delta_theta (Adam
math always done in fp32) is written back three ways —
  (1) fp32-master  : theta_fp32 + Delta            (our LUMI FusionOpt-SF case; ~0 loss)
  (2) det bf16     : round_bf16(theta_bf16 + Delta) (desktop deterministic bf16 master)
  (3) SR  bf16     : stochastic_round(theta_bf16 + Delta) (our AdamWSR shipped fix)

Outputs a REPORT.md + npz sidecar in a self-describing dir.

Env / mutex handled by the caller wrapper; this script assumes FLASH_ATTENTION_TRITON_AMD_ENABLE
etc. are already exported and the GPU lock is held.
"""
import os, sys, json, time, glob, argparse
import numpy as np

# --- env safety (belt-and-suspenders; wrapper also exports these) ------------------
os.environ.setdefault("FLASH_ATTENTION_TRITON_AMD_ENABLE", "FALSE")
os.environ.setdefault("MIOPEN_FIND_MODE", "2")
os.environ.setdefault("PYTORCH_TUNABLEOP_ENABLED", "0")
for v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(v, "4")

import torch

SAO = "/home/kim/Projects/SAO"
sys.path.insert(0, os.path.join(SAO, "control"))
sys.path.insert(0, os.path.join(SAO, "stable-audio-3"))

from stable_audio_3 import StableAudioModel  # noqa: E402
from stable_audio_3.training.stochastic_rounding import stochastic_round_to_bf16  # noqa: E402
from sa3_control.train import build_train_cond, _sample_t  # noqa: E402

LATENTS_DIR = "/home/kim/Projects/latents_sa3"
MELODY_NPZ = os.path.join(SAO, "lumi", "melody_subspace15_v2.npz")


# =====================================================================================
# helpers
# =====================================================================================
def bf16_round(x_fp32: torch.Tensor) -> torch.Tensor:
    """Deterministic round-to-nearest-even fp32 -> bf16 -> back to fp32."""
    return x_fp32.to(torch.bfloat16).float()


def ulp_bf16(x_fp32: torch.Tensor) -> torch.Tensor:
    """ULP (spacing to next representable bf16) at each entry of x, in fp32.
    bf16 has 7 mantissa bits: for a normal value 1.f * 2^E, ulp = 2^(E-7).
    torch.frexp gives x = m*2^e with m in [0.5,1) => E = e-1 => ulp = 2^(e-8).
    x==0 entries get a tiny sentinel (masked out of ratio stats by caller)."""
    m, e = torch.frexp(x_fp32)
    ulp = torch.pow(torch.tensor(2.0, dtype=torch.float32), (e - 8).to(torch.float32))
    ulp = torch.where(x_fp32 == 0, torch.full_like(ulp, float("nan")), ulp)
    return ulp


def percentiles(a: np.ndarray, ps=(1, 5, 25, 50, 75, 95, 99, 99.9)):
    a = a[np.isfinite(a)]
    if a.size == 0:
        return {p: float("nan") for p in ps}
    return {p: float(np.percentile(a, p)) for p in ps}


# =====================================================================================
# one training minibatch -> fp32 gradients on the DiT
# =====================================================================================
def load_batch(paths, T, device):
    xs = []
    prompts = []
    for p in paths:
        x = np.load(p).astype(np.float32)          # (256, 4096)
        xs.append(x[:, :T])
        meta = json.load(open(os.path.splitext(p)[0] + ".json"))
        prompts.append(meta.get("prompt", ""))
    clean = torch.from_numpy(np.stack(xs, 0)).to(device)  # (B,256,T)
    return clean, prompts


def rf_grads(dit, sam, clean, prompts, crop_seconds, T, device, melody_basis=None, seed=0):
    """One rectified-flow forward+backward; returns {name: grad_fp32_cpu}.
    melody_basis: if given (15,256) tensor, weight the residual by its projection onto
    the melody subspace (energy of basis @ (v-target) over the 15 melody coords)."""
    g = torch.Generator(device=device).manual_seed(seed)
    B = clean.shape[0]
    t = torch.sigmoid(torch.randn(B, device=device, generator=g)).clamp(1e-4, 1 - 1e-4)
    tb = t.view(B, 1, 1)
    noise = torch.randn(clean.shape, device=device, generator=g)
    noised = clean * (1 - tb) + noise * tb
    target = noise - clean                                   # RF velocity

    cond = build_train_cond(sam, prompts, crop_seconds, T, device, torch.float32, use_cache=False)

    dit.zero_grad(set_to_none=True)
    # gradient checkpointing keeps activation memory in-budget on the 16GB card (fp32 1.4B)
    v = dit(noised, t, **cond, cfg_scale=1.0, cfg_dropout_prob=0.0, use_checkpointing=True)
    resid = v.float() - target.float()                       # (B,256,T)
    if melody_basis is None:
        loss = (resid ** 2).mean()
    else:
        # basis (15,256) @ residual over the channel axis -> (B,15,T); energy = melody-weighted loss
        mel = torch.einsum("kc,bct->bkt", melody_basis, resid)
        loss = (mel ** 2).mean()
    loss.backward()
    lval = float(loss.detach())
    grads = {}
    for n, p in dit.named_parameters():
        if p.grad is not None:
            grads[n] = p.grad.detach().float().cpu().clone()
    # free GPU state before the next pass (grads persist as p.grad otherwise -> 5.6GB leak)
    dit.zero_grad(set_to_none=True)
    del v, resid, loss, noised, noise, target, cond
    if device == "cuda":
        torch.cuda.empty_cache()
    return grads, lval


# =====================================================================================
# cold/warm AdamW moment state (kept on CPU, fp32) and the update Delta_theta
# =====================================================================================
class AdamState:
    """fp32 AdamW moments on CPU. Warm by accumulating gradient statistics at fixed theta
    (moments = the checkpoint's gradient 1st/2nd moment estimates), no weight step; then
    ask for the update Delta_theta the optimizer WOULD apply this step."""
    def __init__(self, names, lr=8e-5, betas=(0.9, 0.999), eps=1e-8, wd=0.0):
        self.lr, self.b1, self.b2, self.eps, self.wd = lr, betas[0], betas[1], eps, wd
        self.step = 0
        self.m = {n: None for n in names}
        self.v = {n: None for n in names}

    def observe(self, grads):
        self.step += 1
        for n, g in grads.items():
            if self.m[n] is None:
                self.m[n] = torch.zeros_like(g)
                self.v[n] = torch.zeros_like(g)
            self.m[n].mul_(self.b1).add_(g, alpha=1 - self.b1)
            self.v[n].mul_(self.b2).addcmul_(g, g, value=1 - self.b2)

    def delta(self, name, theta_fp32):
        """Delta_theta for one param (decoupled weight decay optional). Uses current moments
        and step count for bias correction (matches torch AdamW)."""
        m_hat = self.m[name] / (1 - self.b1 ** self.step)
        v_hat = self.v[name] / (1 - self.b2 ** self.step)
        d = -self.lr * m_hat / (v_hat.sqrt() + self.eps)
        if self.wd != 0.0:
            d = d - self.lr * self.wd * theta_fp32
        return d


# =====================================================================================
# per-tensor disappearance measurement
# =====================================================================================
def measure(theta_fp32, delta, sr_draws=8, gen=None):
    """All inputs fp32 CPU tensors of identical shape. Returns a dict of counts + samples."""
    theta = theta_fp32
    d = delta
    nz = d != 0                                               # entries with a real fp32 update
    n_all = d.numel()
    n_nz = int(nz.sum())

    # (1) fp32-master control
    applied_fp32 = (theta + d) - theta
    dis_fp32 = int(((applied_fp32 == 0) & nz).sum())

    # (2) deterministic bf16-master
    base_bf = bf16_round(theta)
    applied_det = bf16_round(base_bf + d) - base_bf
    dis_det = int(((applied_det == 0) & nz).sum())

    # (3) SR bf16-master: several draws
    if gen is None:
        gen = torch.Generator().manual_seed(1234)
    mean_applied_sr = torch.zeros_like(d)
    dis_sr_perdraw = 0
    for _ in range(sr_draws):
        new_sr = stochastic_round_to_bf16(base_bf + d).float()
        applied_sr = new_sr - base_bf
        mean_applied_sr += applied_sr
        dis_sr_perdraw += int(((applied_sr == 0) & nz).sum())
    mean_applied_sr /= sr_draws
    # over entries the deterministic path KILLED, does SR recover them in expectation?
    killed = (applied_det == 0) & nz
    n_killed = int(killed.sum())
    sr_recover_ratio = float("nan")
    if n_killed > 0:
        num = mean_applied_sr[killed].abs().mean().item()
        den = d[killed].abs().mean().item()
        sr_recover_ratio = num / den if den > 0 else float("nan")

    # cosine(fp32 update, applied update) over the flattened tensor
    def cos(a, b):
        na, nb = a.norm().item(), b.norm().item()
        if na == 0 or nb == 0:
            return float("nan")
        return float((a.flatten() @ b.flatten()).item() / (na * nb))
    cos_det = cos(d, applied_det)
    cos_fp32 = cos(d, applied_fp32)
    cos_sr = cos(d, mean_applied_sr)

    # |Delta|/|theta| and |Delta|/ULP samples (subsample for global percentiles)
    ulp = ulp_bf16(theta)
    rel = (d.abs() / theta.abs().clamp_min(1e-30))
    rulp = (d.abs() / ulp)
    idx = nz.flatten().nonzero(as_tuple=True)[0]
    if idx.numel() > 20000:
        sel = idx[torch.randperm(idx.numel(), generator=torch.Generator().manual_seed(7))[:20000]]
    else:
        sel = idx
    rel_s = rel.flatten()[sel].numpy()
    rulp_s = rulp.flatten()[sel].numpy()

    # exact global histogram of disappearance vs log2(|Delta|/ULP), det path
    # bins over log2(ratio) from -14..8
    log2r = torch.log2(rulp.flatten()[nz.flatten()])
    disflat = (applied_det == 0).flatten()[nz.flatten()]
    bins = torch.arange(-14, 9, 1.0)
    binidx = torch.bucketize(log2r, bins)
    hist_tot = torch.zeros(len(bins) + 1)
    hist_dis = torch.zeros(len(bins) + 1)
    hist_tot.index_add_(0, binidx, torch.ones_like(log2r))
    hist_dis.index_add_(0, binidx, disflat.float())

    return dict(n_all=n_all, n_nz=n_nz, dis_fp32=dis_fp32, dis_det=dis_det,
                dis_sr_perdraw=dis_sr_perdraw / sr_draws, n_killed=n_killed,
                sr_recover_ratio=sr_recover_ratio, cos_det=cos_det, cos_fp32=cos_fp32,
                cos_sr=cos_sr, rel_s=rel_s, rulp_s=rulp_s,
                hist_tot=hist_tot.numpy(), hist_dis=hist_dis.numpy(), bins=bins.numpy())


# =====================================================================================
def run_loss(dit, sam, batches, meas_batch, crop_seconds, T, device, warmup, lr,
             melody_basis=None, tag="plain"):
    names = [n for n, p in dit.named_parameters() if p.requires_grad]
    st = AdamState(names, lr=lr)

    def grads_finite(cl, pr, seed):
        """rf_grads with a NaN-retry: bump the seed until the forward loss is finite."""
        for k in range(6):
            g, l = rf_grads(dit, sam, cl, pr, crop_seconds, T, device, melody_basis, seed=seed + 1000 * k)
            if np.isfinite(l):
                return g, l, seed + 1000 * k
            print(f"[{tag}] non-finite loss at seed={seed + 1000 * k}, retrying", flush=True)
        raise RuntimeError(f"{tag}: forward stayed non-finite after retries")

    # warm the moments on `warmup` prior batches at fixed theta
    for i in range(warmup):
        cl, pr = batches[i]
        g, l, _ = grads_finite(cl, pr, 100 + i)
        st.observe(g)
        print(f"[{tag}] warmup {i+1}/{warmup} loss={l:.5f}", flush=True)
    # measurement batch -> final moment observation + Delta
    cl, pr = meas_batch
    gm, lm, _ = grads_finite(cl, pr, 999)
    st.observe(gm)
    print(f"[{tag}] measurement loss={lm:.5f} (adam step={st.step})", flush=True)

    # aggregate per-tensor measurements
    agg = dict(n_all=0, n_nz=0, dis_fp32=0, dis_det=0, dis_sr=0.0, n_killed=0,
               sr_num=0.0, sr_den=0.0)
    rel_all, rulp_all = [], []
    hist_tot = hist_dis = None
    bins = None
    cos_det_w = 0.0; cos_fp32_w = 0.0; cos_sr_w = 0.0; cos_wsum = 0.0
    per_tensor = []
    sd = {n: p.detach().float().cpu() for n, p in dit.named_parameters()}
    for n in names:
        if st.m[n] is None:
            continue
        d = st.delta(n, sd[n])
        r = measure(sd[n], d)
        for k in ("n_all", "n_nz", "dis_fp32", "dis_det", "n_killed"):
            agg[k] += r[k]
        agg["dis_sr"] += r["dis_sr_perdraw"]
        rel_all.append(r["rel_s"]); rulp_all.append(r["rulp_s"])
        if hist_tot is None:
            hist_tot = r["hist_tot"].copy(); hist_dis = r["hist_dis"].copy(); bins = r["bins"]
        else:
            hist_tot += r["hist_tot"]; hist_dis += r["hist_dis"]
        w = r["n_nz"]
        if np.isfinite(r["cos_det"]):
            cos_det_w += r["cos_det"] * w; cos_fp32_w += r["cos_fp32"] * w
            cos_sr_w += r["cos_sr"] * w; cos_wsum += w
        if r["n_killed"] > 0 and np.isfinite(r["sr_recover_ratio"]):
            agg["sr_num"] += r["sr_recover_ratio"] * r["n_killed"]; agg["sr_den"] += r["n_killed"]
        per_tensor.append(dict(name=n, n_nz=r["n_nz"],
                               dis_det_frac=(r["dis_det"] / max(1, r["n_nz"])),
                               dis_fp32_frac=(r["dis_fp32"] / max(1, r["n_nz"])),
                               cos_det=r["cos_det"]))
    rel_all = np.concatenate(rel_all); rulp_all = np.concatenate(rulp_all)
    out = dict(
        tag=tag, meas_loss=lm, adam_step=st.step, lr=lr,
        n_nz=agg["n_nz"], n_all=agg["n_all"],
        frac_dis_fp32=agg["dis_fp32"] / max(1, agg["n_nz"]),
        frac_dis_det=agg["dis_det"] / max(1, agg["n_nz"]),
        frac_dis_sr=agg["dis_sr"] / max(1, agg["n_nz"]),
        sr_recover_ratio=(agg["sr_num"] / agg["sr_den"]) if agg["sr_den"] > 0 else float("nan"),
        cos_det=cos_det_w / max(1e-9, cos_wsum),
        cos_fp32=cos_fp32_w / max(1e-9, cos_wsum),
        cos_sr=cos_sr_w / max(1e-9, cos_wsum),
        rel_pct=percentiles(rel_all), rulp_pct=percentiles(rulp_all),
        hist_bins=bins.tolist(), hist_tot=hist_tot.tolist(), hist_dis=hist_dis.tolist(),
        per_tensor=per_tensor,
    )
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="medium-base")
    ap.add_argument("--T", type=int, default=256)
    ap.add_argument("--batch", type=int, default=2)
    ap.add_argument("--warmup", type=int, default=4, help="prior batches to warm Adam moments")
    ap.add_argument("--lr", type=float, default=8e-5)
    ap.add_argument("--melody", action="store_true", help="also run the melody-subspace-weighted loss")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[load] {args.model} fp32 on {device}", flush=True)
    sam = StableAudioModel.from_pretrained(args.model, device=device, model_half=False)
    dit = sam.model.model
    dit.eval()   # deterministic forward (no dropout) — the writeback-disappearance mechanism
                 # is independent of dropout; eval() makes plain vs melody use an identical
                 # forward and removes stochastic-dropout NaNs at extreme noise levels.
    for p in dit.parameters():
        p.requires_grad_(True)
    latent_rate = float(sam.model.sample_rate) / float(sam.model.pretransform.downsampling_ratio)
    crop_seconds = args.T / latent_rate
    n_params = sum(p.numel() for p in dit.parameters())
    print(f"[info] DiT params={n_params/1e6:.1f}M  latent_rate={latent_rate:.4f}  crop_s={crop_seconds:.2f}", flush=True)

    # data batches: warmup + 1 measurement, each of size `batch`, distinct latents
    npy = sorted(glob.glob(os.path.join(LATENTS_DIR, "0000*.npy")))
    need = (args.warmup + 1) * args.batch
    npy = npy[:need]
    assert len(npy) >= need, f"need {need} latents, have {len(npy)}"
    batches = []
    for i in range(args.warmup + 1):
        paths = npy[i * args.batch:(i + 1) * args.batch]
        batches.append(load_batch(paths, args.T, device))
    meas_batch = batches[-1]
    warm_batches = batches[:-1]

    t0 = time.time()
    plain = run_loss(dit, sam, warm_batches, meas_batch, crop_seconds, args.T, device,
                     args.warmup, args.lr, melody_basis=None, tag="plain")
    print(f"[done] plain in {time.time()-t0:.1f}s", flush=True)

    mel_out = None
    if args.melody:
        md = np.load(MELODY_NPZ)
        basis = torch.from_numpy(md["basis15"].astype(np.float32)).to(device)  # (15,256)
        # normalize rows to unit norm so the projection is a clean subspace weighting
        basis = basis / basis.norm(dim=1, keepdim=True).clamp_min(1e-12)
        t1 = time.time()
        mel_out = run_loss(dit, sam, warm_batches, meas_batch, crop_seconds, args.T, device,
                           args.warmup, args.lr, melody_basis=basis, tag="melody")
        print(f"[done] melody in {time.time()-t1:.1f}s", flush=True)

    result = dict(model=args.model, T=args.T, batch=args.batch, warmup=args.warmup,
                  lr=args.lr, n_params=n_params, plain=plain, melody=mel_out)
    with open(os.path.join(args.out, "result.json"), "w") as f:
        json.dump(result, f, indent=2, default=float)
    np.savez(os.path.join(args.out, "histograms.npz"),
             plain_bins=np.array(plain["hist_bins"]), plain_tot=np.array(plain["hist_tot"]),
             plain_dis=np.array(plain["hist_dis"]),
             **({"mel_bins": np.array(mel_out["hist_bins"]), "mel_tot": np.array(mel_out["hist_tot"]),
                 "mel_dis": np.array(mel_out["hist_dis"])} if mel_out else {}))
    print("[written]", os.path.join(args.out, "result.json"), flush=True)
    # brief stdout summary
    print("\n==== SUMMARY ====")
    for o in [plain] + ([mel_out] if mel_out else []):
        print(f"[{o['tag']}] disappeared-frac: fp32={o['frac_dis_fp32']:.3e}  "
              f"det-bf16={o['frac_dis_det']*100:.3f}%  SR={o['frac_dis_sr']*100:.4f}%  "
              f"| cos(det)={o['cos_det']:.4f} cos(fp32)={o['cos_fp32']:.5f} cos(SR)={o['cos_sr']:.4f}  "
              f"| SR-recover-ratio(killed)={o['sr_recover_ratio']:.3f}")


if __name__ == "__main__":
    main()
