#!/usr/bin/env python
# Owner: GHOST-NOTE (created 2026-10-13)
"""fp8_linear.py -- FP8 (E4M3 forward, E5M2 gradient) drop-in for the FROZEN linears of the SA3 DiT, via torch._scaled_mm.

WHY (GHOST-NOTE 2026-10-13, the owner's question: "the CK flags show BF8 -- would FP8/BF8 make sense for SA3 finetunes?"). RDNA4 (gfx1201)
has FP8/BF8 matrix instructions and torch._scaled_mm runs them (measured 1.8-2.1x bf16 on DiT-shaped matmuls). A finetune of a LoRA/DoRA
adapter never needs the base weights' own gradient, only the gradient w.r.t. the INPUT, which is what the backward below computes
(E5M2 gradient x E4M3 weight). Trainable linears (adapters, anything with requires_grad) are left untouched.

Scaling is dynamic per tensor (amax/448 for E4M3, amax/57344 for E5M2) -- the simplest scheme, and the one whose error this module
exists to measure, not to hide. Weight scales are static (computed once at swap time).

    n = swap_fp8(model)          # in place; returns (n_layers, params_covered, params_total)
    restore_fp8(model)           # back to the original nn.Linear modules
"""
import torch
import torch.nn as nn

E4M3_MAX = 448.0
E5M2_MAX = 57344.0


class _Fp8Matmul(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x, w8, w8t, sw, bias):
        shp = x.shape
        x2 = x.reshape(-1, shp[-1])
        sx = (x2.detach().abs().amax().float() / E4M3_MAX).clamp(min=1e-12)
        x8 = (x2.float() / sx).clamp(-E4M3_MAX, E4M3_MAX).to(torch.float8_e4m3fn).contiguous()   # row-major: a permuted x kept its strides
        y = torch._scaled_mm(x8, w8.t(), scale_a=sx, scale_b=sw, out_dtype=torch.bfloat16)   # (M,K) @ (K,N), w8 is (N,K) contiguous
        if bias is not None:
            y = y + bias.to(y.dtype)
        ctx.save_for_backward(w8t, sw)
        ctx.x_dtype = x.dtype
        y = y.to(x.dtype)                                    # the stock model may be fp16 (model_half); bf16 out broke its convs
        return y.reshape(*shp[:-1], y.shape[-1])

    @staticmethod
    def backward(ctx, g):
        w8t, sw = ctx.saved_tensors                          # w8t: (K,N) contiguous = the weight transposed
        shp = g.shape
        g2 = g.reshape(-1, shp[-1])
        sg = (g2.detach().abs().amax().float() / E5M2_MAX).clamp(min=1e-12)
        g8 = (g2.float() / sg).clamp(-E5M2_MAX, E5M2_MAX).to(torch.float8_e5m2).contiguous()
        gx = torch._scaled_mm(g8, w8t.t(), scale_a=sg, scale_b=sw, out_dtype=torch.bfloat16)   # (M,N) @ (N,K)
        return gx.reshape(*shp[:-1], gx.shape[-1]).to(ctx.x_dtype), None, None, None, None


class Fp8Linear(nn.Module):
    """Frozen linear in FP8. Keeps the original module (`orig`) so restore_fp8 can put it back."""

    def __init__(self, lin: nn.Linear):
        super().__init__()
        w = lin.weight.detach().float()
        sw = (w.abs().amax() / E4M3_MAX).clamp(min=1e-12)
        self.register_buffer("w8", (w / sw).clamp(-E4M3_MAX, E4M3_MAX).to(torch.float8_e4m3fn).contiguous(), persistent=False)
        self.register_buffer("w8t", self.w8.t().contiguous(), persistent=False)
        self.register_buffer("sw", sw.reshape(()).float(), persistent=False)
        self.bias = None if lin.bias is None else nn.Parameter(lin.bias.detach(), requires_grad=False)
        self.orig = [lin]                                     # a list: not registered, so its weight is not counted twice
        self.in_features, self.out_features = lin.in_features, lin.out_features

    def forward(self, x):
        return _Fp8Matmul.apply(x, self.w8, self.w8t, self.sw, self.bias)


def _eligible(m):
    return (type(m) is nn.Linear and not m.weight.requires_grad and m.in_features % 16 == 0 and m.out_features % 16 == 0
            and (m.bias is None or not m.bias.requires_grad))


def swap_fp8(model, min_params=0):
    """Replace every eligible frozen nn.Linear below `model` by an Fp8Linear. Returns (n, params_covered, params_total_linear)."""
    n = cov = tot = 0
    for parent in list(model.modules()):
        for name, child in list(parent.named_children()):
            if type(child) is nn.Linear:
                tot += child.weight.numel()
                if _eligible(child) and child.weight.numel() >= min_params:
                    setattr(parent, name, Fp8Linear(child))
                    n += 1
                    cov += child.weight.numel()
    return n, cov, tot


def restore_fp8(model):
    for parent in list(model.modules()):
        for name, child in list(parent.named_children()):
            if isinstance(child, Fp8Linear):
                setattr(parent, name, child.orig[0])
