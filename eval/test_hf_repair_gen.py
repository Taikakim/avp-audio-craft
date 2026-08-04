#!/usr/bin/env python
"""test_hf_repair_gen.py — CPU unit tests for the generative HF-repair components (#62).
Validates the architecture is correct + trainable BEFORE it ever touches the GPU.

Run: /home/kim/Projects/SAO/.venv/bin/python eval/test_hf_repair_gen.py
"""
import sys
from pathlib import Path
import torch
torch.set_num_threads(4)
torch.manual_seed(0)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hf_repair_gen import (GenHFRepairNet, MultiPeriodDiscriminator, lsgan_disc_loss,
                           lsgan_gen_loss, feature_matching_loss, anti_wrapping_gd_loss)

B, T, TL = 2, 16000, 4     # small: batch, audio samples, latent frames
ok = True


def chk(name, cond, detail=""):
    global ok
    ok = ok and cond
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}{(' — ' + detail) if detail else ''}")


# (1) identity at init (zero-init output residual) — no-latent net, eval mode
net = GenHFRepairNet(channels=32, n_stacks=2).eval()
x = torch.randn(B, 2, T)
with torch.no_grad():
    y = net(x)
chk("identity at init (no latent)", torch.allclose(y, x, atol=1e-6),
    f"max|y-x|={ (y-x).abs().max():.2e}")

# (2) forward shape + gradient-safety in TRAIN mode (checkpointing active)
net.train()
x = torch.randn(B, 2, T, requires_grad=True)
y = net(x)
chk("train forward shape", y.shape == (B, 2, T), str(tuple(y.shape)))
y.pow(2).mean().backward()
gfin = all(torch.isfinite(p.grad).all() for p in net.parameters() if p.grad is not None)
chk("train grads finite", gfin and torch.isfinite(x.grad).all().item())

# (3) LATENT conditioning: 256-ch SAME latent, upsampled + concatenated
gnet = GenHFRepairNet(channels=32, n_stacks=2, latent_ch=256, latent_proj=16).eval()
lat = torch.randn(B, 256, TL)
with torch.no_grad():
    yl = gnet(torch.randn(B, 2, T), lat)
chk("latent-conditioned forward shape", yl.shape == (B, 2, T), str(tuple(yl.shape)))
# identity still holds at init even with latent (zero-init output)
xl = torch.randn(B, 2, T)
with torch.no_grad():
    chk("identity at init (with latent)", torch.allclose(gnet(xl, lat), xl, atol=1e-6))
# latent path gets gradient
gnet.train()
xl = torch.randn(B, 2, T, requires_grad=True)
gnet(xl, lat).pow(2).mean().backward()
chk("latent_proj receives gradient",
    gnet.latent_proj.weight.grad is not None and torch.isfinite(gnet.latent_proj.weight.grad).all().item())

# (4) multi-period discriminator: structure + gradient
disc = MultiPeriodDiscriminator()
wav = torch.randn(B, 1, T, requires_grad=True)
outs = disc(wav)
chk("MPD returns per-period (score, feats)", len(outs) == 5 and all(len(o) == 2 for o in outs),
    f"{len(outs)} sub-discs")
outs[0][0].pow(2).mean().backward()
chk("MPD grad finite", torch.isfinite(wav.grad).all().item())

# (5) GAN losses: finite scalars + gradients, on synthetic real/fake
disc.zero_grad()
real = torch.randn(B, 1, T)
fake = torch.randn(B, 1, T, requires_grad=True)
r_out, f_out = disc(real), disc(fake)
dl = lsgan_disc_loss(r_out, f_out)
gl = lsgan_gen_loss(f_out)
fm = feature_matching_loss(r_out, f_out)
chk("lsgan/fm losses finite scalars",
    all(torch.isfinite(v).all() and v.dim() == 0 for v in (dl, gl, fm)),
    f"disc={dl.item():.3f} gen={gl.item():.3f} fm={fm.item():.3f}")
(gl + fm).backward()
chk("generator-side GAN loss backprops to fake", torch.isfinite(fake.grad).all().item())

# (6) anti-wrapping group-delay stabiliser: finite, in [0, pi], differentiable
p = torch.randn(B, T, requires_grad=True)
t = torch.randn(B, T)
awgd = anti_wrapping_gd_loss(p, t)
chk("anti-wrapping GD loss finite & bounded", torch.isfinite(awgd) and 0 <= awgd.item() <= 3.1416,
    f"{awgd.item():.3f}")
awgd.backward()
chk("anti-wrapping GD differentiable", torch.isfinite(p.grad).all().item())

# (7) param budget sanity (target 2-5M at production channels=160)
prod = GenHFRepairNet(channels=160, n_stacks=4, latent_ch=256)
n = sum(pp.numel() for pp in prod.parameters())
chk("production param count in 2-6M band", 2e6 <= n <= 6e6, f"{n:,}")

print(f"\n{'ALL PASS — generative #62 architecture is correct + trainable (CPU-verified)' if ok else 'FAILURES — fix before GPU'}")
raise SystemExit(0 if ok else 1)
