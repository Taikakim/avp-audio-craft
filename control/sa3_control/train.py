"""Train the audio-reference (riffer) control adapter on pre-encoded SA3 latents.

Loads medium-base (fp32, model_half=False), installs decoupled cross-attn adapters
(base frozen), and trains the adapter + audio-ref conditioner with the rectified-flow
loss, conditioning each step on a DIFFERENT crop of the same track (the riffer pairing
from LatentControlDataset). Control tokens are injected via the ContextVar around our
own DiT forward (cfg_scale=1.0 -> no CFG batch-doubling).

Run with the consolidated SAO/.venv (CK flash-attn; set the flag before import):
    PYTORCH_TUNABLEOP_ENABLED=0 FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE \
        /home/kim/Projects/SAO/.venv/bin/python \
        -m sa3_control.train --encoded_dir /home/kim/Projects/latents_sa3 --smoke
"""

import argparse
import copy
import json
import os
import subprocess
import sys
import time

# append (not insert(0)) so site-packages resolves first — a wandb run-data dir that
# wandb writes under the package root must not shadow the real `wandb` package on reimport.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import torch
from torch.utils.data import DataLoader

from sa3_control.adapters import ControlContext, use_control_context
from sa3_control.conditioner import (AudioRefEncoder, ScalarAttributeEncoder, AttributeEncoder,
                                     MelodyContourEncoder, MetricalEncoder)
from sa3_control.dataset import LatentControlDataset, CONTROL_FIELDS, CONTROL_DIMS
from sa3_control.inject import (adapter_state_dict, freeze_base_train_adapters,
                                install_adapters)


class EMA:
    """Exponential moving average of the trainable params (standing recipe: EMA + grad-accum + early-stop)."""
    def __init__(self, params, decay: float):
        self.decay = float(decay)
        self.params = list(params)
        self.shadow = [p.detach().float().clone() for p in self.params]
        self.backup = None

    @torch.no_grad()
    def update(self):
        for s, p in zip(self.shadow, self.params):
            s.mul_(self.decay).add_(p.detach().float(), alpha=1.0 - self.decay)

    @torch.no_grad()
    def copy_to(self):
        self.backup = [p.detach().clone() for p in self.params]
        for s, p in zip(self.shadow, self.params):
            p.data.copy_(s.to(p.dtype))

    @torch.no_grad()
    def restore(self):
        for b, p in zip(self.backup, self.params):
            p.data.copy_(b)
        self.backup = None


def collate(batch):
    out = {
        "latent": torch.stack([b["latent"] for b in batch]),
        "prompt": [b["prompt"] for b in batch],
    }
    if "ref_latent" in batch[0]:
        out["ref_latent"] = torch.stack([b["ref_latent"] for b in batch])
    if "scalar" in batch[0]:
        out["scalar"] = torch.stack([b["scalar"] for b in batch])
    if "melody_cls" in batch[0]:                    # (B, T) int64 contour classes (Head B)
        out["melody_cls"] = torch.stack([b["melody_cls"] for b in batch])
    if "metrical_cls" in batch[0]:                  # (B, 5, T) int64 tree classes + (B, T) conf (E3)
        out["metrical_cls"] = torch.stack([b["metrical_cls"] for b in batch])
        out["metrical_conf"] = torch.stack([b["metrical_conf"] for b in batch])
    if "dual_scalar" in batch[0]:                   # (B, 2) {feature, bpm} — json-scalar dual path
        out["dual_scalar"] = torch.stack([b["dual_scalar"] for b in batch])
    if "dual_bpm" in batch[0]:                      # (B,) std bpm — ts-window dual path (feature assembled in loop)
        out["dual_bpm"] = torch.stack([b["dual_bpm"] for b in batch])
    if batch[0].get("controls"):                # time-varying attribute features {name: (C,T)}
        out["controls"] = {k: torch.stack([b["controls"][k] for b in batch]) for k in batch[0]["controls"]}
    if "fingerprint" in batch[0]:
        out["fingerprint"] = torch.stack([b["fingerprint"] for b in batch])
    return out


# The prompt is fixed per crop, so the frozen text encoder gives the same output every
# epoch — re-running it every step was the per-step bottleneck (GPU starved between DiT
# bursts). Encode each unique prompt ONCE and reuse. Cached output is on `device`.
_TEXT_COND_CACHE = {}   # prompt -> conditioner output dict


def _sample_t(sampler, B, device):
    """Diffusion timestep sampler (ported from underfit/SAT). 'logit_normal' is our
    original (= sigmoid(randn)); 'log_snr' samples Gaussian on logSNR (mean -1.2, std 2.0)
    -> t=sigmoid(-logsnr), biasing toward the informative band instead of pure mid-noise."""
    if sampler == "uniform":
        return torch.rand(B, device=device)
    if sampler == "logit_normal":
        return torch.sigmoid(torch.randn(B, device=device)).clamp(1e-4, 1 - 1e-4)
    if sampler == "log_snr":
        ls = torch.randn(B, device=device) * 2.0 - 1.2
        return torch.sigmoid(-ls).clamp(1e-4, 1 - 1e-4)
    if sampler == "log_snr_uniform":
        ls = torch.rand(B, device=device) * 11.0 - 6.0
        return torch.sigmoid(-ls).clamp(1e-4, 1 - 1e-4)
    raise ValueError(f"unknown timestep_sampler: {sampler}")


def _encode_text(sam, prompt, seconds, device):
    """Run the frozen text conditioner for ONE prompt. no_grad: the encoder is frozen,
    so no graph is built and the cached tensors act as constants in the train forward."""
    with torch.no_grad():
        return sam.model.conditioner([{"prompt": prompt, "seconds_total": float(seconds)}], device)


def preencode_text(sam, prompts, seconds, device):
    """Encode every unique prompt once into the cache, so no training step pays the
    text-encoder cost."""
    uniq = sorted(set(prompts))
    for i, p in enumerate(uniq):
        if p not in _TEXT_COND_CACHE:
            _TEXT_COND_CACHE[p] = _encode_text(sam, p, seconds, device)
        if (i + 1) % 200 == 0:
            print(f"[preencode] {i + 1}/{len(uniq)} prompts", flush=True)
    print(f"[preencode] cached {len(uniq)} unique prompts", flush=True)


def build_train_cond(sam, prompts, seconds, latent_T, device, dtype, use_cache=True):
    """cond_inputs for a training batch (cfg_scale=1.0 path), mirroring generate(). The
    frozen text-encoder output is cached per prompt (batch==1 path)."""
    B = len(prompts)
    io = sam.model.io_channels
    if use_cache and B == 1:
        ct = _TEXT_COND_CACHE.get(prompts[0])
        if ct is None:
            ct = _encode_text(sam, prompts[0], seconds, device)
            _TEXT_COND_CACHE[prompts[0]] = ct
        ct = dict(ct)                                   # shallow copy: don't mutate the cached dict
    else:
        conditioning = [{"prompt": p, "seconds_total": float(seconds)} for p in prompts]
        ct = dict(sam.model.conditioner(conditioning, device))
    ct["inpaint_mask"] = [torch.zeros((B, 1, latent_T), device=device)]
    ct["inpaint_masked_input"] = [torch.zeros((B, io, latent_T), device=device)]
    ci = sam.model.get_conditioning_inputs(ct)
    return {k: (v.type(dtype) if torch.is_tensor(v) else v) for k, v in ci.items()}


def export_control_onnx_on_finish(ckpt_path, save_dir, frames, field):
    """ADDITIVE, non-fatal: after the final checkpoint is saved, shell out to the SA3
    control-DiT ONNX exporter (forward-only adapter bake-in). Runs under sys.executable
    (the SA3 .venv the trainer already uses, which has the exporter's deps). Returns the
    subprocess returncode; never raises (check=False). `field` is informational only."""
    out_path = os.path.join(save_dir, f"dit_medium-base_L{frames}_ctrl.onnx")
    _exporter = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "onnx", "export_dit_control_onnx.py")  # SAO/onnx/export_dit_control_onnx.py
    cmd = [sys.executable,
           _exporter,
           "--ckpt", ckpt_path, "--model", "medium-base", "--frames", str(frames),
           "--text-seq", "128", "--fp16", "--out", out_path]
    # The exporter does `from sa3_control...`; when sys.executable is a venv without the
    # sao_tooling editable install (e.g. stable-audio-3/.venv), put control/ (this file's
    # package parent) on PYTHONPATH so the import resolves. (Fixes the post-train export.)
    _control_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../control
    env = {**os.environ, "FLASH_ATTENTION_TRITON_AMD_ENABLE": "FALSE",
           "PYTHONPATH": _control_dir + os.pathsep + os.environ.get("PYTHONPATH", "")}
    print(f"[export] start: control-DiT ONNX -> {out_path} (field={field})", flush=True)
    rc = subprocess.run(cmd, env=env, check=False).returncode
    if rc == 0:
        print(f"[export] done: {out_path}", flush=True)
    else:
        print(f"[export] failed (returncode {rc}); training already saved, continuing", flush=True)
    return rc


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--encoded_dir", default="/home/kim/Projects/latents_sa3",
                    help="pre-encoded latent dir; ALSO accepts a comma-separated list of dirs "
                         "(goa,avp) for a combined multi-root dataset (full-path lists concatenated, "
                         "so the 000000.* stem collision between corpora is sidestepped).")
    ap.add_argument("--encoded-dirs", nargs="+", default=None,
                    help="explicit multi-root form of --encoded_dir: one or more latent dirs "
                         "(space-separated). Overrides --encoded_dir when given.")
    ap.add_argument("--model", default="medium-base")
    ap.add_argument("--base-state-ckpt", default=None,
                    help="B9 (Kim 2026-08-21): overlay a FULL-FINETUNE checkpoint's weights onto "
                         "the loaded base DiT before attaching/training controls — 'train the "
                         "heads on top of our best full finetune instead of the base model'. "
                         "Path to the fat Lightning ckpt; EMA shadow weights are preferred "
                         "(diffusion_ema.ema_model.*, what deploys) with online fallback.")
    ap.add_argument("--base-state-online", action="store_true",
                    help="with --base-state-ckpt: load the ONLINE weights (diffusion.model.*) "
                         "instead of the EMA shadow")
    ap.add_argument("--adapter-layers", default="",
                    help="restrict TRAINING to these cross-attn tap indices, e.g. '8-15' or "
                         "'13,14,15' (default: all 24). Adapters are still INSTALLED at every "
                         "layer and saved 24-indexed (untrained ones stay zero-init = exact "
                         "no-op, so checkpoints load in every existing eval tool unchanged). "
                         "Motivated by the 2026-07-21 single-tap ablation: L14 alone ~= full "
                         "adapter authority, cleaner spectrum (ablate_layers2 run).")
    ap.add_argument("--steps", type=int, default=20000)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--control-dim", type=int, default=768)
    ap.add_argument("--n-tokens", type=int, default=256)
    ap.add_argument("--crop-frames", type=int, default=1024,
                    help="train on the first N latent frames (memory; full=4096)")
    ap.add_argument("--random-crop", action="store_true",
                    help="train on a RANDOM beat-aligned crop-frames window of each latent (vs always the "
                         "first N) — more crop variety per track so the trainer stops seeing only the first "
                         "~47s of each crop; snaps the offset to beat_activation_ts peaks.")
    ap.add_argument("--cfg-dropout", type=float, default=0.1,
                    help="per-item probability of dropping the control tokens")
    ap.add_argument("--save-dir", default="/run/media/kim/Mantu/sa3_control_runs/riffer")
    ap.add_argument("--save-every", type=int, default=1000)
    ap.add_argument("--save-cooldown", type=float, default=60,
                    help="seconds to idle the GPU after each checkpoint save (thermal relief; 0 disables)")
    ap.add_argument("--log-every", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--num-workers", type=int, default=4)
    ap.add_argument("--subset-tracks", type=float, default=None,
                    help="train on a random fraction (0.2 = 20%% of tracks, all their crops; "
                         "preserves the riffer pairing) or count (>1) of tracks. None = all.")
    ap.add_argument("--wandb", action="store_true", help="log to Weights & Biases")
    ap.add_argument("--wandb-project", default="sa3-riffer")
    ap.add_argument("--run-name", default=None)
    ap.add_argument("--profile", action="store_true",
                    help="log a per-step timing breakdown (data/text/ref/fwd/bwd/opt)")
    ap.add_argument("--no-preencode-text", action="store_false", dest="preencode_text",
                    help="skip the upfront unique-prompt text pre-encode (cache lazily instead)")
    ap.add_argument("--no-checkpoint", action="store_false", dest="use_checkpointing",
                    help="disable DiT gradient checkpointing — much faster backward if VRAM fits "
                         "(only the 116M adapter trains, but checkpointing recomputes the whole "
                         "2.4B forward in backward; the bwd was ~90%% of step time)")
    ap.add_argument("--max-hours", type=float, default=None,
                    help="wall-clock stop after this many hours (saves riffer_final.pt)")
    ap.add_argument("--warmup-steps", type=int, default=0,
                    help="linear LR warmup over this many steps (0 = none). Best practice for "
                         "higher LRs — prevents the early gradient explosion seen at lr 1e-3.")
    ap.add_argument("--weight-decay", type=float, default=0.01,
                    help="decoupled weight decay. NOTE Lion's update is a unit-sign step, so "
                         "the paper wants wd 3-10x LARGER than AdamW's at a 3-10x smaller lr; "
                         "0.01 is the AdamW-shaped default, not a tuned Lion value.")
    ap.add_argument("--lion-betas", type=float, nargs=2, default=(0.9, 0.99),
                    help="LionSR (beta1 = update interpolation, beta2 = momentum EMA)")
    ap.add_argument("--fusion-autoscale", action="store_true",
                    help="D-Adaptation/Prodigy step-size estimator: d starts tiny and only "
                         "grows, driven by dot(grad, p0 - p) against an EMA of gradient "
                         "magnitude; folded in as a pure lr multiplier. Works with --optimizer "
                         "fusion* (a FusionOpt component) AND with lion (dadapt_scale). "
                         "⚠ On lion the OCO bound does NOT hold — Lion's step magnitude is lr "
                         "regardless of the gradient — so it is an adaptive-lr heuristic there.")
    ap.add_argument("--fusion-autoscale-slice-p", type=int, default=16,
                    help="keep every Nth coordinate of the per-param init clone + accumulator "
                         "(state cost O(numel/N)). No effect unless --fusion-autoscale.")
    ap.add_argument("--fusion-autoscale-growth-rate", type=float, default=float("inf"),
                    help="cap on how fast d may grow per step, multiplicative. Does NOT bound "
                         "the FIRST estimate, which is taken outright (d0 is a placeholder).")
    ap.add_argument("--hyperball", action="store_true",
                    help="constrain each weight to the sphere of radius ‖W0‖_F (arXiv "
                         "2606.16899); weight decay is ignored, and 'sf' is dropped from the "
                         "components (incompatible). ⚠ MOSTLY INERT ON AN ADAPTER RECIPE: "
                         "every adapter tensor we train is zero-init (LoRA/DoRA lora_B, the "
                         "cross-attn to_out), and ‖W0‖=0 would pin them at zero forever — "
                         "FusionOpt detects that and falls back to the ordinary update for "
                         "those params, so hyperball only really binds a --base-state-ckpt's "
                         "own weights if you ever unfreeze them.")
    ap.add_argument("--optimizer", choices=["adamw", "fusion", "sfadamw", "fusion_nm", "fusion_full", "lion"], default="adamw",
                    help="adamw (default); fusion (SF-NorMuon = ns5+normuon+sf); sfadamw (sf-only = "
                         "ScheduleFree-AdamW); fusion_nm (mona+ns5+normuon+sf — everything EXCEPT KL-Shampoo, "
                         "now viable on large adapters thanks to component-gated state alloc); fusion_full "
                         "(all 5 incl. Shampoo — heavy, may OOM on large adapters).")
    ap.add_argument("--cautious", action="store_true",
                    help="add cautious masking (C-Muon) to the FusionOpt components: zero update "
                         "coords that fight the gradient, rescale survivors. Otherwise identical to "
                         "the chosen --optimizer. No effect for adamw.")
    ap.add_argument("--cc-probe", default="",
                    help="path to a trained control-consistency probe (train_cc_probe.py). Enables "
                         "L = L_RF + lambda_cc * MSE(probe(z0_hat), requested) for t < cc-t-max — "
                         "puts the control target INTO the gradient (RF loss is blind to it). "
                         "Scalar control mode only. Spec: docs/superpowers/specs/"
                         "2026-07-02-perceptual-signal-optimizer-directions.md")
    ap.add_argument("--lambda-cc", type=float, default=0.1,
                    help="weight of the control-consistency term (start small: a strong weight "
                         "lets the head game the probe instead of doing RF).")
    ap.add_argument("--cc-t-max", type=float, default=0.5,
                    help="apply the cc term only when t < this (z0_hat is biased at high noise).")
    # --- genre-consistency probe (fingerprint mode; sibling of --cc-probe) ---
    ap.add_argument("--fp-probe", default="",
                    help="path to a genre-consistency probe (cc_probe_genre.pt). FINGERPRINT mode "
                         "only: adds lambda_fp * MSE(probe(z0_hat), requested genre block) over "
                         "SUPERVISED dims for t < fp-t-max. Puts the genre meter INTO the gradient "
                         "(RF loss is blind to it). Probe out-order is target_keys, reindexed here.")
    ap.add_argument("--lambda-fp", type=float, default=0.1, help="weight of the genre-consistency term")
    ap.add_argument("--fp-t-max", type=float, default=0.5,
                    help="apply the genre-consistency term only when t < this (z0_hat biased at high t).")
    ap.add_argument("--fp-supervise", default="0,1,2,4",
                    help="VOCAB indices to supervise with the genre probe (default the strong-r dims: "
                         "0=Goa,1=Psy,2=Trance,4=Prog). The rest are held out and MONITORED for "
                         "probe-hacking (supervised authority up while held-out drifts = gaming the meter).")
    ap.add_argument("--resume", default="", help="warm-start: load adapter+conditioner weights from a "
                    "checkpoint .pt (optimizer restarts fresh; not an exact-state resume).")
    ap.add_argument("--resume-exact", default="", help="EXACT-state resume: restore adapter weights + "
                    "optimizer state + step counter from a checkpoint saved with the 'opt' key (continues "
                    "the run as if never interrupted). Errors on pre-opt-state checkpoints.")
    ap.add_argument("--timestep-sampler",
                    choices=["logit_normal", "log_snr", "log_snr_uniform", "uniform"], default="logit_normal",
                    help="diffusion t sampler (underfit borrow). logit_normal = original; "
                         "log_snr biases toward the informative sigma band (may de-noise the loss).")
    ap.add_argument("--control-mode",
                    choices=["audio_ref", "scalar", "attribute", "fingerprint", "dual_scalar",
                             "melody_contour", "metrical_position"],
                    default="audio_ref",
                    help="audio_ref = the riffer (opaque reference latent); scalar = a per-crop scalar "
                         "(e.g. onset_density); attribute = a TIME-VARYING per-frame feature "
                         "(dynamics/rhythm/melody curve) via the time-aligned AttributeEncoder; "
                         "fingerprint = style/genre vector via FingerprintEncoder; "
                         "dual_scalar = joint {feature, bpm_madmom} 2-vector via FingerprintEncoder(in_dim=2) "
                         "— conditions on the feature AND tempo so the adapter can't cheat the feature by "
                         "shifting bpm; "
                         "melody_contour = Head B (spec 2026-07-22-melodic-latch-film §2): per-frame "
                         "folded contour class stream (prep_melody_conditioning sidecars) via "
                         "MelodyContourEncoder — teacher-forced (crop, its own lead stream) pairs; "
                         "metrical_position = E3 (spec 2026-07-31-metrical-tree-pe-design.md): "
                         "4-level metrical tree (subdiv/beat/bar/phrase) hard-class streams + "
                         "coverage, via MetricalEncoder.")
    # --- melody_contour (Head B) args ---
    ap.add_argument("--melody-dir", default="/home/kim/Projects/latents_sa3_melody",
                    help="sidecar dir of <stem>.melody8.npy class streams (melody_contour mode)")
    ap.add_argument("--melody-dirs", nargs="+", default=None,
                    help="per-root form of --melody-dir, for a MULTI-CORPUS run: one contour "
                         "sidecar dir per --encoded-dirs root, in the SAME ORDER. Required "
                         "whenever the corpora have colliding crop stems (goa and avp both "
                         "start at 000000.npy) — a single --melody-dir would resolve both to "
                         "the same stream file and condition one corpus on the other's "
                         "contours. A single --melody-dir still applies to every root.")
    ap.add_argument("--melody-vocab", type=int, default=9,
                    help="melody_contour embedding vocab (default 9 = Head-B's 8 classes + "
                         "reserved null). Morph-contour streams (build_morph_streams.py): "
                         "L2=5, L3=15, L4=77 (0=undefined, symbols+1, +reserved).")
    ap.add_argument("--melody-dropout", type=float, default=0.1,
                    help="melody_contour mode: per-item probability of zeroing the MELODY control "
                         "tokens, drawn INDEPENDENTLY of text dropout (--cfg-dropout doubles as the "
                         "TEXT cfg_dropout_prob in this mode) — the StemGen multi-source-CFG POOL "
                         "item (docs/todos.md '[POOL, C] 2026-07-22 StemGen 2312.08723'): independent "
                         "draws expose all four {text, melody} on/off states so per-source guidance "
                         "scales are calibratable at inference.")
    # --- metrical_position (E3) args ---
    ap.add_argument("--metrical-dir", default="/home/kim/Projects/latents_sa3_metrical",
                    help="sidecar dir of <stem>.metrical.npy (5,4096) tree-position streams + "
                         "<stem>.metrical_conf.npy confidences (metrical_position mode)")
    ap.add_argument("--metrical-dropout", type=float, default=0.15,
                    help="metrical_position mode: per-item probability of zeroing the metrical "
                         "condition to the null token during training (all 5 class rows + conf -> 0, "
                         "AT THE INPUT — the null IS the all-zero input, design doc §2), drawn "
                         "INDEPENDENTLY of text cfg dropout (--cfg-dropout doubles as the TEXT "
                         "cfg_dropout_prob in this mode): independent draws expose all four "
                         "{text, metrical} on/off states for per-source guidance at inference.")
    ap.add_argument("--dora-rank", type=int, default=0,
                    help="also train a fresh dora-rows adapter of this rank on the DiT Linears/Conv1ds "
                         "(0 = off). The Head B pilot recipe: r128 dora-rows learns the corpus idiom "
                         "jointly while the cross-attn adapters learn the melody conditioning.")
    ap.add_argument("--dora-alpha", type=float, default=None,
                    help="dora alpha (default = rank, the s=1 convention per the alpha audit)")
    ap.add_argument("--scalar-field", default="onset_density",
                    help="which per-crop .json scalar to condition on when --control-mode scalar")
    ap.add_argument("--control-feature", default="melody",
                    help="which .TIMESERIES.npz feature for --control-mode attribute: "
                         "dynamics(4) | rhythm(3) | melody(12, =hpcp). (chroma384 once that data exists.)")
    ap.add_argument("--attr-downsample", type=int, default=8,
                    help="time downsample for the AttributeEncoder (T -> T/this control tokens)")
    ap.add_argument("--scalar-from-timeseries", default="",
                    help="scalar mode: derive the scalar as the WINDOW-MEAN of this .TIMESERIES feature "
                         "(e.g. density_ts) over the trained crop [:T] instead of the full-crop .json value "
                         "— fixes the crop-length label mismatch (the .json scalar describes all 4096 frames).")
    ap.set_defaults(preencode_text=True, use_checkpointing=True)
    ap.add_argument("--precision", choices=["bf16", "fp32"], default="bf16",
                    help="bf16 = base+adapters in bfloat16 (the supported ROCm path, ~2x "
                         "less memory); fp32 for max numerical stability")
    ap.add_argument("--smoke", action="store_true", help="3 steps, tiny, sanity only")
    ap.add_argument("--export-onnx-on-finish", action=argparse.BooleanOptionalAction, default=True,
                    help="after the final checkpoint is saved, shell out to the SA3 control-DiT ONNX "
                         "exporter to bake the trained adapter into a forward-only ONNX graph "
                         "(additive, non-fatal; --no-export-onnx-on-finish to disable)")
    ap.add_argument("--export-onnx-frames", type=int, default=256,
                    help="latent frame length (rung) for the on-finish ONNX export")
    # --- fingerprint variant + training schedule args ---
    ap.add_argument("--fp-variant", choices=["A", "B", "C"], default="A",
                    help="fingerprint scope: A=style+groove (genre+year+bpm+sync); "
                         "B=maximal (+window onset+energy); C=style-only (genre+year)")
    ap.add_argument("--genre-vocab", default=os.path.join(os.path.dirname(__file__), "genre_vocab.json"))
    ap.add_argument("--ema", type=float, default=0.999, help="EMA decay (0 disables)")
    ap.add_argument("--grad-accum", type=int, default=2,
                    help="accumulate this many microbatches per opt.step (standing recipe)")
    ap.add_argument("--max-epochs", type=int, default=20,
                    help="early-stop epoch cap (standing recipe ~20 ep)")
    ap.add_argument("--val-frac", type=float, default=0.05,
                    help="held-out track fraction for early-stop RF loss (fingerprint mode)")
    ap.add_argument("--early-stop-patience", type=int, default=4,
                    help="stop after N epochs w/o val-loss improvement")
    args = ap.parse_args()

    if args.smoke:
        args.steps, args.batch, args.crop_frames, args.num_workers = 3, 1, 512, 0
        args.precision = "fp32"
        args.preencode_text = False   # smoke: skip caching 5K+ prompts (OOMs w/ fp32 DiT)

    dtype = {"bf16": torch.bfloat16, "fp32": torch.float32}[args.precision]

    # Resolve the (possibly multi-root) encoded latent dir. --encoded-dirs (list) wins; else split
    # --encoded_dir on commas. Returns a str for a single dir (byte-identical single-root path) or a
    # list for several — LatentControlDataset accepts either.
    if args.encoded_dirs:
        encoded_dir = args.encoded_dirs if len(args.encoded_dirs) > 1 else args.encoded_dirs[0]
    else:
        _parts = [s for s in args.encoded_dir.split(",") if s]
        encoded_dir = _parts if len(_parts) > 1 else args.encoded_dir
    if isinstance(encoded_dir, list):
        print(f"[data] multi-root dataset: {len(encoded_dir)} corpora {encoded_dir}", flush=True)
    # --melody-dirs (list) wins over --melody-dir; the dataset checks it lines up with the roots
    melody_dir = args.melody_dirs if args.melody_dirs else args.melody_dir
    if isinstance(melody_dir, list):
        print(f"[data] per-root contour sidecars: {melody_dir}", flush=True)

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    from stable_audio_3 import StableAudioModel
    print(f"[load] {args.model} ({args.precision})", flush=True)
    sam = StableAudioModel.from_pretrained(args.model, device=device, model_half=False)
    if getattr(args, "base_state_ckpt", None):
        # Same proven prefix-strip loader as lumi/render_matrix_cells.py:113 (the
        # 2026-07-21 cov-assert bug lives in naive "model."-stripping — try both).
        ck = torch.load(args.base_state_ckpt, map_location="cpu", weights_only=False)
        sd_raw = ck.get("state_dict", ck)
        tgt = sam.model.model
        want = set(dict(tgt.named_parameters())) | set(dict(tgt.named_buffers()))
        prefixes = (("diffusion.model.", "model.") if args.base_state_online
                    else ("diffusion_ema.ema_model.",))
        sd = max(
            ({(k[len(pfx):] if k.startswith(pfx) else k): v for k, v in sd_raw.items()}
             for pfx in prefixes),
            key=lambda d: sum(1 for k in d if k in want))
        missing, _ = tgt.load_state_dict(
            {k: v.to(next(tgt.parameters()).dtype) for k, v in sd.items() if k in want},
            strict=False)
        cov = 1 - len(missing) / max(1, len(list(tgt.state_dict())))
        assert cov > 0.99, (f"[base-state] ckpt covers only {cov:.1%} of the DiT "
                            f"({len(missing)} missing) — wrong ckpt, or EMA keys absent "
                            f"(try --base-state-online)")
        print(f"[base-state] overlaid {args.base_state_ckpt} "
              f"({'online' if args.base_state_online else 'EMA'} weights, cov {cov:.1%})")
        del ck, sd_raw, sd
    if dtype != torch.float32:
        sam.model.to(dtype)                                 # base in bf16
    dit = sam.model.model                                    # DiTWrapper -> DiffusionTransformer
    latent_rate = float(sam.model.sample_rate) / float(sam.model.pretransform.downsampling_ratio)
    crop_seconds = args.crop_frames / latent_rate

    # optional joint dora-rows on the DiT (Head B pilot recipe). MUST run BEFORE
    # install_adapters, so the control-adapter Linears are NOT parametrized — dora
    # covers the base DiT only. Conditioner (T5-Gemma) deliberately excluded: its
    # output is pre-encoded/cached per prompt, so parametrizing it would silently
    # train against a stale cache.
    _lora_params = []
    if args.dora_rank > 0:
        from functools import partial
        from stable_audio_3.models.lora import (add_lora, get_lora_params,
                                                LoRAParametrization)
        _alpha = args.dora_alpha if args.dora_alpha is not None else float(args.dora_rank)
        _lcfg = {
            torch.nn.Linear: {"weight": partial(LoRAParametrization.from_linear,
                                                rank=args.dora_rank, lora_alpha=_alpha,
                                                adapter_type="dora-rows")},
            torch.nn.Conv1d: {"weight": partial(LoRAParametrization.from_conv1d,
                                                rank=args.dora_rank, lora_alpha=_alpha,
                                                adapter_type="dora-rows")},
        }
        add_lora(dit, _lcfg)
        _lora_params = list(get_lora_params(dit))
        n_lora = sum(p.numel() for p in _lora_params)
        print(f"[dora] fresh dora-rows r={args.dora_rank} alpha={_alpha:g} on the DiT: "
              f"{len(_lora_params)} tensors, {n_lora/1e6:.1f}M params (joint-trained)", flush=True)

    # adapters + conditioner
    _fp_vocab = None   # set in fingerprint branch; referenced by checkpoint saves
    wrappers = install_adapters(sam, control_dim=args.control_dim)
    if args.control_mode == "scalar":
        cond_enc = ScalarAttributeEncoder(control_dim=args.control_dim,
                                          n_tokens=min(args.n_tokens, 16)).to(device=device, dtype=dtype)
        print(f"[control] scalar attribute '{args.scalar_field}' -> ScalarAttributeEncoder", flush=True)
    elif args.control_mode == "dual_scalar":
        from sa3_control.conditioner import FingerprintEncoder
        cond_enc = FingerprintEncoder(in_dim=2, control_dim=args.control_dim,
                                      n_tokens=min(args.n_tokens, 16)).to(device=device, dtype=dtype)
        _feat1 = args.scalar_from_timeseries or args.scalar_field
        print(f"[control] dual_scalar {{{_feat1}, bpm_madmom}} in_dim=2 -> FingerprintEncoder", flush=True)
    elif args.control_mode == "attribute":
        in_ch = CONTROL_DIMS[args.control_feature]
        if args.control_feature == "chroma384":                # chroma-aware (pitch-circular, 3 bands)
            from sa3_control.conditioner import ChromaAttributeEncoder
            cond_enc = ChromaAttributeEncoder(control_dim=args.control_dim,
                                              downsample=args.attr_downsample).to(device=device, dtype=dtype)
            print(f"[control] attribute 'chroma384' (3x128, pitch-circular, /{cond_enc.downsample}) "
                  f"-> ChromaAttributeEncoder", flush=True)
        else:
            cond_enc = AttributeEncoder(in_channels=in_ch, control_dim=args.control_dim,
                                        downsample=args.attr_downsample).to(device=device, dtype=dtype)
            print(f"[control] attribute '{args.control_feature}' ({in_ch}ch, /{cond_enc.downsample}) "
                  f"-> time-aligned AttributeEncoder", flush=True)
    elif args.control_mode == "melody_contour":
        cond_enc = MelodyContourEncoder(control_dim=args.control_dim,
                                        n_classes=args.melody_vocab).to(device=device, dtype=dtype)
        print(f"[control] melody_contour (Head B): Embedding({args.melody_vocab}, {args.control_dim}) per-frame "
              f"lookup, melody-dropout {args.melody_dropout} (independent of text "
              f"cfg-dropout {args.cfg_dropout})", flush=True)
    elif args.control_mode == "metrical_position":
        cond_enc = MetricalEncoder(control_dim=args.control_dim).to(device=device, dtype=dtype)
        print(f"[control] metrical_position (E3): 4-level tree embeddings "
              f"({'/'.join(str(n) for n in cond_enc.level_sizes)}) + (coverage,conf) -> "
              f"MetricalEncoder, metrical-dropout {args.metrical_dropout} (independent of text "
              f"cfg-dropout {args.cfg_dropout})", flush=True)
    elif args.control_mode == "fingerprint":
        from sa3_control.conditioner import FingerprintEncoder
        from sa3_control.dataset import fingerprint_in_dim
        _fp_vocab = json.load(open(args.genre_vocab))["vocab"]
        in_dim = fingerprint_in_dim(args.fp_variant, len(_fp_vocab))
        cond_enc = FingerprintEncoder(in_dim=in_dim, control_dim=args.control_dim,
                                      n_tokens=min(args.n_tokens, 16)).to(device=device, dtype=dtype)
        print(f"[control] fingerprint V-{args.fp_variant} in_dim={in_dim} (K={len(_fp_vocab)}) "
              f"-> FingerprintEncoder", flush=True)
    else:
        cond_enc = AudioRefEncoder(latent_dim=256, control_dim=args.control_dim,
                                   n_tokens=args.n_tokens).to(device=device, dtype=dtype)
    if dtype != torch.float32:
        for w in wrappers:
            w.adapter.to(dtype)
    # optional layer restriction: unfreeze only the selected taps' adapters. The rest stay
    # frozen at zero-init (= exact no-op at inference); saves keep the full 24-index keying.
    if args.adapter_layers:
        sel = set()
        for part in args.adapter_layers.split(","):
            part = part.strip()
            if "-" in part:
                lo, hi = part.split("-")
                sel.update(range(int(lo), int(hi) + 1))
            elif part:
                sel.add(int(part))
        bad = sel - set(range(len(wrappers)))
        assert not bad, f"--adapter-layers out of range {sorted(bad)} (have {len(wrappers)} taps)"
        train_wrappers = [wrappers[i] for i in sorted(sel)]
        print(f"[adapters] LAYER-RESTRICTED training: taps {sorted(sel)} "
              f"({len(train_wrappers)}/{len(wrappers)})", flush=True)
    else:
        train_wrappers = wrappers
    params = freeze_base_train_adapters(sam, train_wrappers, extra_trainable=[cond_enc])
    if _lora_params:                    # re-enable the dora params (freeze above swept them)
        for p in _lora_params:
            p.requires_grad_(True)
        params = params + _lora_params
    n_train = sum(p.numel() for p in params)
    n_base = sum(p.numel() for p in sam.model.parameters())
    print(f"[adapters] wrapped {len(wrappers)} cross-attn ({len(train_wrappers)} trainable); "
          f"trainable {n_train/1e6:.1f}M of {n_base/1e6:.0f}M base ({100*n_train/n_base:.2f}%)", flush=True)
    if args.resume:                                          # warm-start (weights only; optimizer fresh)
        from sa3_control.generate import load_adapter_state
        load_adapter_state(torch.load(args.resume, map_location="cpu")["state"], wrappers, cond_enc)
        print(f"[resume] warm-started adapter+conditioner from {args.resume}", flush=True)

    _smoke_adapter_g, _smoke_dora_g = [], []   # filled per-step under --smoke

    if args.optimizer in ("fusion", "sfadamw", "fusion_nm", "fusion_full"):
        # stable_audio_tools is editable-installed in SAO/.venv; no path hack needed.
        from stable_audio_tools.training.fusion_opt import FusionOpt
        from stable_audio_tools.training.fusion_groups import build_fusion_param_groups
        # ⚠ `dit` MUST be in here when --dora-rank > 0. The fusion path used to route only
        # the control adapters + conditioner, so a `--optimizer fusion --dora-rank 128` run
        # allocated no optimizer state for the DoRA tensors and never stepped them: the rank
        # was paid for in memory and compute and learned NOTHING, while the AdamW path (which
        # optimises `params`, dora included) did the obvious thing. named_parameters() dedupes
        # by identity, so listing dit alongside adapters that live inside it is safe, and the
        # requires_grad filter keeps the frozen base out. (CONTINUITY 2026-09-09)
        trainable_mod = torch.nn.ModuleList(
            [w.adapter for w in wrappers] + [cond_enc] + ([dit] if _lora_params else []))
        groups = build_fusion_param_groups(trainable_mod, spectral_wd=0.01, scalar_wd=0.0)
        comps = ({"sf"} if args.optimizer == "sfadamw"
                 else None if args.optimizer == "fusion_full"        # None = all 5 (mona+shampoo+ns5+normuon+sf)
                 else {"mona", "ns5", "normuon", "sf"} if args.optimizer == "fusion_nm"  # all but KL-Shampoo
                 else {"ns5", "normuon", "sf"})                      # fusion = SF-NorMuon
        if args.cautious:                                            # C-Muon: same recipe + cautious mask
            comps = ({"mona", "shampoo", "ns5", "normuon", "sf"} if comps is None else set(comps)) | {"cautious"}
        if args.hyperball:            # SF averaging and the norm constraint are incompatible
            comps = ({"mona", "shampoo", "ns5", "normuon"} if comps is None else set(comps)) - {"sf"}
        if args.fusion_autoscale:
            comps = ({"mona", "shampoo", "ns5", "normuon", "sf"} if comps is None else set(comps)) | {"autoscale"}
        opt = FusionOpt(groups, lr=args.lr, warmup_steps=args.warmup_steps, hot_dtype="bf16",
                        components=comps, hyperball=args.hyperball,
                        autoscale_slice_p=args.fusion_autoscale_slice_p,
                        autoscale_growth_rate=args.fusion_autoscale_growth_rate)
        _sf = bool(getattr(opt, "uses_sf_averaging", False))
        if _sf:
            opt.train()
        print(f"[opt] {args.optimizer} (components={sorted(comps)}, SF={_sf})", flush=True)
    elif args.optimizer == "lion":
        from stable_audio_3.training.lion_optimizer import LionSR
        opt = LionSR(params, lr=args.lr, betas=tuple(args.lion_betas),
                     weight_decay=args.weight_decay,
                     autoscale=args.fusion_autoscale,
                     autoscale_slice_p=args.fusion_autoscale_slice_p,
                     autoscale_growth_rate=args.fusion_autoscale_growth_rate)
        _sf = False
        _n = sum(p.numel() for p in params)
        print(f"[opt] LionSR lr={args.lr:g} betas={tuple(args.lion_betas)} "
              f"wd={args.weight_decay:g} autoscale={args.fusion_autoscale} "
              f"over {_n/1e6:.1f}M params", flush=True)
        if args.hyperball:
            print("[opt] ⚠ --hyperball is a FusionOpt feature and is IGNORED by lion", flush=True)
    else:
        opt = torch.optim.AdamW(params, lr=args.lr, weight_decay=args.weight_decay)
        _sf = False

    ema = EMA(params, args.ema) if args.ema and args.ema > 0 else None
    if ema is not None:
        print(f"[ema] decay={args.ema} over {n_train/1e6:.1f}M params", flush=True)

    start_step = 0
    if args.resume_exact:                                    # exact-state resume (weights + optimizer + step)
        from sa3_control.generate import load_adapter_state
        _ck = torch.load(args.resume_exact, map_location="cpu")
        if "opt" not in _ck:
            raise SystemExit(f"--resume-exact: {args.resume_exact} has no optimizer state "
                             "(saved before opt-state support); use --resume for warm-start instead.")
        load_adapter_state(_ck.get("model_train", _ck["state"]), wrappers, cond_enc)   # train-mode (y) iterate
        opt.load_state_dict(_ck["opt"])
        start_step = int(_ck.get("step", 0))
        if "torch_rng" in _ck:
            torch.set_rng_state(_ck["torch_rng"])            # main-process RNG (dataloader workers re-seed)
        print(f"[resume-exact] restored weights+optimizer+step from {args.resume_exact} "
              f"@ step {start_step} -> continues to {args.steps}", flush=True)

    def _corpus_scalar_stats(ds, field):
        """Corpus (mean,std) of a per-crop .json scalar, computed the same way the scalar path does."""
        vals = np.array([m[field] for m in ds.meta.values() if field in m], dtype=np.float32)
        return float(vals.mean()), float(vals.std())

    def _corpus_ts_window_stats(ds, ts_field, T0):
        """Corpus (mean,std) of the window-mean of a timeseries feature over [:T0] (crop-correct)."""
        samp = ds.paths[:: max(1, len(ds.paths) // 600)][:600]    # ~600-crop sample for stats
        wm = []
        for p in samp:
            try:
                z = np.load(p[:-4] + ".TIMESERIES.npz")
                arr = np.concatenate([z[f][None] if z[f].ndim == 1 else z[f].T for f in CONTROL_FIELDS[ts_field]], 0)
                wm.append(float(arr[:, :T0].mean()))
            except Exception:
                pass
        wm = np.array(wm, dtype=np.float32)
        return float(wm.mean()), float(wm.std() + 1e-8), len(wm)

    if args.control_mode == "scalar" and args.scalar_from_timeseries:
        # scalar = window-mean of a timeseries feature over the trained crop [:T] (crop-correct).
        sf = args.scalar_from_timeseries
        ds = LatentControlDataset(encoded_dir, controls=(sf,), audio_ref=None,
                                  seed=args.seed, subset_tracks=args.subset_tracks)
        ds.scalar_mean, ds.scalar_std, _nwm = _corpus_ts_window_stats(ds, sf, args.crop_frames)
        print(f"[control] scalar from '{sf}' window-mean over [:{args.crop_frames}]: mean {ds.scalar_mean:.4f} "
              f"std {ds.scalar_std:.4f} (n={_nwm}); crop-correct", flush=True)
    elif args.control_mode == "scalar":
        ds = LatentControlDataset(encoded_dir, controls=(), audio_ref=None,
                                  seed=args.seed, subset_tracks=args.subset_tracks,
                                  scalar_field=args.scalar_field,
                                  random_crop_frames=(args.crop_frames if args.random_crop else None))
        ds.scalar_mean, ds.scalar_std = _corpus_scalar_stats(ds, args.scalar_field)
        print(f"[control] {args.scalar_field}: mean {ds.scalar_mean:.3f} std {ds.scalar_std:.3f} "
              f"standardized at train time", flush=True)
    elif args.control_mode == "dual_scalar":
        # Joint {feature, bpm_madmom}. Feature 1 = scalar_from_timeseries window-mean (crop-correct) OR the
        # json scalar_field; feature 2 = bpm_madmom. Both standardized with corpus (mean,std) pairs saved
        # into the checkpoint (scalar_norm + bpm_norm). Crops lacking bpm_madmom are skipped in the dataset.
        sf_ts = args.scalar_from_timeseries
        if sf_ts:
            ds = LatentControlDataset(encoded_dir, controls=(sf_ts,), audio_ref=None,
                                      seed=args.seed, subset_tracks=args.subset_tracks,
                                      dual_scalar=True,
                                      random_crop_frames=(args.crop_frames if args.random_crop else None))
            ds.scalar_mean, ds.scalar_std, _nwm = _corpus_ts_window_stats(ds, sf_ts, args.crop_frames)
            _feat1_desc = f"'{sf_ts}' window-mean over [:{args.crop_frames}] (n={_nwm})"
        else:
            ds = LatentControlDataset(encoded_dir, controls=(), audio_ref=None,
                                      seed=args.seed, subset_tracks=args.subset_tracks,
                                      scalar_field=args.scalar_field, dual_scalar=True,
                                      random_crop_frames=(args.crop_frames if args.random_crop else None))
            ds.scalar_mean, ds.scalar_std = _corpus_scalar_stats(ds, args.scalar_field)
            _feat1_desc = f"'{args.scalar_field}' json scalar"
        ds.bpm_mean, ds.bpm_std = _corpus_scalar_stats(ds, "bpm_madmom")   # feature 2, same corpus method
        print(f"[control] dual_scalar feature1 {_feat1_desc}: mean {ds.scalar_mean:.4f} std {ds.scalar_std:.4f}; "
              f"feature2 bpm_madmom: mean {ds.bpm_mean:.3f} std {ds.bpm_std:.3f}; both standardized", flush=True)
    elif args.control_mode == "attribute":
        ds = LatentControlDataset(encoded_dir, controls=(args.control_feature,), audio_ref=None,
                                  seed=args.seed, subset_tracks=args.subset_tracks)
    elif args.control_mode == "melody_contour":
        ds = LatentControlDataset(encoded_dir, controls=(), audio_ref=None,
                                  seed=args.seed, subset_tracks=args.subset_tracks,
                                  melody_dir=melody_dir,
                                  random_crop_frames=(args.crop_frames if args.random_crop else None))
    elif args.control_mode == "metrical_position":
        ds = LatentControlDataset(encoded_dir, controls=(), audio_ref=None,
                                  seed=args.seed, subset_tracks=args.subset_tracks,
                                  metrical_dir=args.metrical_dir,
                                  random_crop_frames=(args.crop_frames if args.random_crop else None))
    elif args.control_mode == "fingerprint":
        ds = LatentControlDataset(encoded_dir, controls=(), audio_ref=None,
                                  seed=args.seed, subset_tracks=args.subset_tracks,
                                  fingerprint=True, genre_vocab=_fp_vocab, fp_variant=args.fp_variant,
                                  random_crop_frames=args.crop_frames)
    else:
        ds = LatentControlDataset(encoded_dir, controls=(), audio_ref="same_track",
                                  seed=args.seed, subset_tracks=args.subset_tracks)
    # track-level train/val split for fingerprint early-stop (val_frac>0, not smoke)
    val_dl = None
    if args.control_mode == "fingerprint" and args.val_frac > 0 and not args.smoke:
        from sa3_control.dataset import track_key as _tk
        all_keys = sorted(ds.by_track.keys())
        _val_rng = np.random.default_rng(args.seed + 999)
        _val_rng.shuffle(all_keys)
        n_val = max(1, int(len(all_keys) * args.val_frac))
        val_keys = set(all_keys[:n_val])
        val_paths = [p for p in ds.paths if _tk(ds.meta[p], p) in val_keys]
        ds.paths = [p for p in ds.paths if _tk(ds.meta[p], p) not in val_keys]
        val_ds = copy.deepcopy(ds)
        val_ds.paths = val_paths
        val_dl = DataLoader(val_ds, batch_size=args.batch, shuffle=False, drop_last=False,
                            num_workers=0, collate_fn=collate)
        print(f"[val] {len(val_paths)} crops from {len(val_keys)} val tracks; "
              f"{len(ds.paths)} train crops remain", flush=True)
    dl = DataLoader(ds, batch_size=args.batch, shuffle=True, drop_last=True,
                    num_workers=args.num_workers, collate_fn=collate,
                    # keep workers alive across epochs: respawning them every epoch
                    # stalled ~9 min/epoch (worker teardown/join), ~90 min/run wasted.
                    persistent_workers=(args.num_workers > 0))
    print(f"[data] {len(ds)} crops, {ds.track_stats()['tracks']} tracks; "
          f"crop {args.crop_frames}f ({crop_seconds:.1f}s)", flush=True)

    wb = None
    if args.wandb:
        try:
            import wandb as wb
            wb.init(project=args.wandb_project, name=args.run_name, config=vars(args))
        except Exception as e:
            print(f"[wandb] disabled ({e})", flush=True)
            wb = None

    from sa3_control.telemetry import TrainTelemetry        # rich per-layer + trajectory + opt logging
    _telem_mod = torch.nn.ModuleList([w.adapter for w in wrappers] + [cond_enc])
    telem = TrainTelemetry(_telem_mod, wb, scalar_every=args.log_every,
                           traj_every=args.save_every, optimizer=opt)

    # Control-consistency probe (optional): frozen differentiable meter for the scalar
    # target; the run's normalized request is remapped to the probe's own scalar_norm.
    cc_probe = None
    if args.cc_probe:
        if args.control_mode != "scalar":
            raise SystemExit("[cc] --cc-probe requires --control-mode scalar")
        from sa3_control.cc_probe import load_probe, rf_z0_hat, control_consistency_loss
        cc_probe, (cc_mean, cc_std) = load_probe(args.cc_probe, device=device)
        print(f"[cc] probe loaded: {args.cc_probe} (norm mean={cc_mean:.3f} std={cc_std:.3f}) "
              f"lambda={args.lambda_cc} t_max={args.cc_t_max}", flush=True)

    # Genre-consistency probe (optional, FINGERPRINT mode): frozen latent-space genre meter
    # (CONTINUITY's cc_probe_genre.pt, R2=0.85). Sibling of --cc-probe with its own guard so the
    # scalar path is untouched. The probe outputs in target_keys order (sorted names) — reindex the
    # fingerprint's vocab-order genre block to match, or we'd supervise the wrong genre. norm=(0,1)
    # for this probe (raw probabilities), so no request remapping.
    fp_probe = None
    if args.fp_probe:
        if args.control_mode != "fingerprint":
            raise SystemExit("[fp] --fp-probe requires --control-mode fingerprint")
        from sa3_control.cc_probe import load_probe as _lp, rf_z0_hat
        fp_probe, _ = _lp(args.fp_probe, device=device)
        _pck = torch.load(args.fp_probe, map_location="cpu", weights_only=False)
        _tkeys = _pck["target_keys"]                              # probe output order
        _fp_order = list(_fp_vocab) + ["other"]                   # fingerprint genre-block order
        fp_perm = torch.tensor([_fp_order.index(k) for k in _tkeys], device=device)  # req[:,fp_perm]->probe order
        _sup_vocab = {int(x) for x in args.fp_supervise.split(",") if x.strip() != ""}
        fp_sup_mask = torch.tensor([int(fp_perm[i]) in _sup_vocab for i in range(len(_tkeys))],
                                   device=device)                 # (D,) bool, probe order
        _sup = [_tkeys[i].split('---')[-1] for i in range(len(_tkeys)) if bool(fp_sup_mask[i])]
        _held = [_tkeys[i].split('---')[-1] for i in range(len(_tkeys)) if not bool(fp_sup_mask[i])]
        print(f"[fp] genre probe loaded: {args.fp_probe} val_r2={_pck.get('val_r2', float('nan')):.3f} "
              f"lambda={args.lambda_fp} t_max={args.fp_t_max}", flush=True)
        print(f"[fp] supervise {len(_sup)} dims {_sup}; monitor(held-out) {_held}", flush=True)

    def fp_consistency_loss(probe, z0_hat, req_probe, t, mask, t_max):
        """Thin wrapper (don't touch cc_probe.control_consistency_loss): MSE on SUPERVISED dims only,
        over t<t_max rows; returns (sup_loss_tensor, held_err_float, held_pred_mean_float) for the
        probe-hack telemetry. req_probe is already in probe (target_keys) order."""
        gate = t < t_max
        if not bool(gate.any()):
            z = z0_hat.new_zeros(())
            return z, 0.0, 0.0
        pred = probe(z0_hat[gate])                                # (Bg, D) probe order
        r = req_probe[gate].to(pred.dtype)
        sup_loss = torch.nn.functional.mse_loss(pred[:, mask], r[:, mask])
        with torch.no_grad():
            held = ~mask
            he = float(torch.nn.functional.mse_loss(pred[:, held], r[:, held])) if bool(held.any()) else 0.0
            hp = float(pred[:, held].mean()) if bool(held.any()) else 0.0
        return sup_loss, he, hp

    if args.preencode_text:
        preencode_text(sam, [ds.meta[p].get("prompt", "") for p in ds.paths], crop_seconds, device)

    os.makedirs(args.save_dir, exist_ok=True)

    def _extra_ckpt_fields():
        """melody_contour/metrical_position/dora additions to the checkpoint dict. Call INSIDE the EMA-swapped
        region so lora_state (read from module state) captures the averaged weights, like
        the adapter state does."""
        d = {"melody_dir": getattr(args, "melody_dir", None),
             "melody_dropout": getattr(args, "melody_dropout", None),
             "metrical_dir": getattr(args, "metrical_dir", None),
             "metrical_dropout": getattr(args, "metrical_dropout", None),
             "dora_rank": int(getattr(args, "dora_rank", 0) or 0),
             "dora_alpha": getattr(args, "dora_alpha", None)}
        if d["dora_rank"] > 0:
            from stable_audio_3.models.lora import get_lora_state_dict
            d["lora_state"] = {k: v.detach().cpu() for k, v in get_lora_state_dict(dit).items()}
        return d

    prof = {"data": 0.0, "text": 0.0, "ref": 0.0, "fwd": 0.0, "bwd": 0.0, "opt": 0.0}

    def _sync():
        if device == "cuda":
            torch.cuda.synchronize()

    step = start_step
    gnorm = torch.tensor(0.0)   # last known gnorm; stale by up to grad_accum-1 steps between opt steps
    epoch = 0
    best_val_loss = float("inf")
    epochs_since_best = 0
    t0 = time.time()
    t_iter = time.time()
    cond_enc.train()
    while step < args.steps:
        for b in dl:
            if args.profile:
                _sync(); _tm = time.time(); prof["data"] += _tm - t_iter
            T = args.crop_frames
            clean = b["latent"][:, :, :T].to(device=device, dtype=dtype)
            B = clean.shape[0]

            t = _sample_t(args.timestep_sampler, B, device)
            tb = t.view(B, 1, 1)
            noise = torch.randn_like(clean)
            noised = clean * (1 - tb) + noise * tb
            target = noise - clean                          # rectified-flow velocity

            if args.control_mode == "scalar" and args.scalar_from_timeseries:
                feat = b["controls"][args.scalar_from_timeseries][:, :, :T]    # (B, C, T)
                raw = feat.to(device=device, dtype=torch.float32).mean(dim=(1, 2))   # window-mean
                sc = ((raw - ds.scalar_mean) / ds.scalar_std).to(dtype)
                ctrl = cond_enc(sc)
            elif args.control_mode == "scalar":
                ctrl = cond_enc(b["scalar"].to(device=device, dtype=dtype))    # (B, n_tokens, control_dim)
            elif args.control_mode == "dual_scalar":
                if args.scalar_from_timeseries:                                # feature1 = crop-correct window-mean
                    feat = b["controls"][args.scalar_from_timeseries][:, :, :T]
                    raw = feat.to(device=device, dtype=torch.float32).mean(dim=(1, 2))      # (B,)
                    std_f = (raw - ds.scalar_mean) / ds.scalar_std                          # (B,)
                    std_bpm = b["dual_bpm"].to(device=device, dtype=torch.float32)          # (B,) pre-standardized
                    vec = torch.stack([std_f, std_bpm], dim=1).to(dtype)                    # (B, 2)
                else:
                    vec = b["dual_scalar"].to(device=device, dtype=dtype)                   # (B, 2)
                ctrl = cond_enc(vec)                                          # (B, n_tokens, control_dim)
            elif args.control_mode == "attribute":
                feat = b["controls"][args.control_feature][:, :, :T].to(device=device, dtype=dtype)  # (B,C,T)
                ctrl = cond_enc(feat)                                          # (B, T/ds, control_dim)
            elif args.control_mode == "fingerprint":
                ctrl = cond_enc(b["fingerprint"].to(device=device, dtype=dtype))  # (B, n_tokens, control_dim)
            elif args.control_mode == "melody_contour":
                ctrl = cond_enc(b["melody_cls"][:, :T].to(device=device))         # (B, T, control_dim)
            elif args.control_mode == "metrical_position":
                m_cls = b["metrical_cls"][:, :, :T].to(device=device)             # (B, 5, T) int64
                m_conf = b["metrical_conf"][:, :T].to(device=device)              # (B, T) float32
                # per-item metrical dropout AT THE INPUT (not the encoded tokens): the null
                # token IS the all-zero input (5 class rows + coverage + conf all 0), so
                # dropping = feeding exactly what uncovered crops / un-sidecarred inference
                # prompts carry (zero-condition dropout, design doc §2). Drawn independently
                # of text dropout, like --melody-dropout.
                if args.metrical_dropout > 0:
                    m_drop = torch.rand(m_cls.shape[0], device=device) < args.metrical_dropout
                    m_cls = m_cls.masked_fill(m_drop.view(-1, 1, 1), 0)
                    m_conf = m_conf.masked_fill(m_drop.view(-1, 1), 0.0)
                ctrl = cond_enc(m_cls, m_conf)                                    # (B, T, control_dim)
            else:
                ctrl = cond_enc(b["ref_latent"].to(device=device, dtype=dtype))
            # per-item control-token dropout. melody_contour: the melody stream has its OWN
            # independent dropout prob (--melody-dropout) while --cfg-dropout is repurposed as
            # the TEXT cfg_dropout_prob (passed to the DiT below) — the StemGen multi-source
            # POOL item (docs/todos.md 2026-07-22): independent draws cover all 4 joint states.
            # metrical_position: same text-dropout repurposing, but the metrical stream was
            # already dropped at the INPUT above (null token, not zeroed tokens) -> no token drop.
            _ctrl_drop_p = (args.melody_dropout if args.control_mode == "melody_contour"
                            else 0.0 if args.control_mode == "metrical_position"
                            else args.cfg_dropout)
            _text_drop_p = (args.cfg_dropout
                            if args.control_mode in ("melody_contour", "metrical_position") else 0.0)
            if _ctrl_drop_p > 0:
                drop = (torch.rand(B, device=device) < _ctrl_drop_p).view(B, 1, 1)
                ctrl = ctrl.masked_fill(drop, 0.0)
            if args.profile:
                _sync(); _tr = time.time(); prof["ref"] += _tr - _tm

            cond_inputs = build_train_cond(sam, b["prompt"], crop_seconds, T, device, dtype)
            if args.profile:
                _sync(); _tt = time.time(); prof["text"] += _tt - _tr

            # keep the control context active THROUGH backward: the DiT uses gradient
            # checkpointing, which re-runs the block forward during backward — the
            # adapter branch must see the same ContextVar on recompute or tensor counts mismatch.
            with use_control_context(ControlContext(ctrl)):
                v = dit(noised, t, **cond_inputs, cfg_scale=1.0, cfg_dropout_prob=_text_drop_p,
                        use_checkpointing=args.use_checkpointing)
                loss = torch.nn.functional.mse_loss(v.float(), target.float())
                cc_val = 0.0
                fp_val = 0.0; fp_held = 0.0; fp_held_pred = 0.0
                if cc_probe is not None:
                    # request on the probe's normalized scale (run-norm -> raw -> probe-norm)
                    sc_run = (sc if (args.control_mode == "scalar" and args.scalar_from_timeseries)
                              else b["scalar"].to(device)).float()
                    raw = sc_run * ds.scalar_std + ds.scalar_mean
                    req = (raw - cc_mean) / cc_std
                    z0_hat = rf_z0_hat(noised.float(), v.float(), t)
                    cc_loss = control_consistency_loss(cc_probe, z0_hat, req, t,
                                                       t_max=args.cc_t_max)
                    loss = loss + args.lambda_cc * cc_loss
                    cc_val = float(cc_loss.detach())
                if fp_probe is not None:
                    # requested genre block (vocab-order, first D dims) -> probe order via fp_perm
                    req_g = b["fingerprint"][:, :fp_perm.numel()].to(device=device).float()
                    req_probe = req_g[:, fp_perm]
                    z0_hat = rf_z0_hat(noised.float(), v.float(), t)
                    fp_loss, fp_held, fp_held_pred = fp_consistency_loss(
                        fp_probe, z0_hat, req_probe, t, fp_sup_mask, args.fp_t_max)
                    loss = loss + args.lambda_fp * fp_loss
                    fp_val = float(fp_loss.detach()) if torch.is_tensor(fp_loss) else float(fp_loss)
                if args.profile:
                    _sync(); _tf = time.time(); prof["fwd"] += _tf - _tt
                # grad-accum: divide BEFORE backward so each microbatch contributes 1/N of the step gradient
                (loss / args.grad_accum).backward()
                if args.smoke:      # grads are live here at ANY --grad-accum; the step
                    # block below runs only every Nth microbatch and clears them after
                    _smoke_adapter_g = [float(q.grad.norm()) for w in wrappers
                                        for q in w.adapter.parameters() if q.grad is not None]
                    _smoke_dora_g = [float(q.grad.norm()) for q in _lora_params
                                     if q.grad is not None]
            if args.profile:
                _sync(); _tb = time.time(); prof["bwd"] += _tb - _tf
            # optimizer step only every grad_accum microbatches (standard gradient accumulation)
            if (step + 1) % args.grad_accum == 0:
                gnorm = torch.nn.utils.clip_grad_norm_(params, 1.0)
                if args.warmup_steps > 0 and args.optimizer == "adamw":  # FusionOpt warms up internally
                    for pg in opt.param_groups:
                        pg["lr"] = args.lr * min(1.0, (step + 1) / args.warmup_steps)
                if hasattr(opt, "_telem_on"):       # FusionOpt: instrument the step we're about to log
                    opt._telem_on = ((step + 1) % args.log_every == 0)
                opt.step()
                opt.zero_grad(set_to_none=True)
                if ema is not None:
                    ema.update()
                if args.profile:
                    _sync(); t_iter = time.time(); prof["opt"] += t_iter - _tb
                else:
                    t_iter = time.time()
            else:
                t_iter = time.time()
            step += 1

            if step % args.log_every == 0 or args.smoke:
                rate = step / (time.time() - t0)
                _cc = f" cc {cc_val:.4f}" if cc_probe is not None else ""
                _fp = f" fp {fp_val:.4f}(held {fp_held:.3f})" if fp_probe is not None else ""
                print(f"[step {step}/{args.steps}] loss {loss.item():.4f}{_cc}{_fp} "
                      f"gnorm {float(gnorm):.3f} {rate:.2f} it/s", flush=True)
                if cc_probe is not None and wb is not None:
                    wb.log({"cc/loss": cc_val, "cc/weighted": args.lambda_cc * cc_val}, step=step)
                if fp_probe is not None and wb is not None:
                    wb.log({"fp/loss": fp_val, "fp/weighted": args.lambda_fp * fp_val,
                            "fp/held_err": fp_held, "fp/held_pred_mean": fp_held_pred}, step=step)
                if args.profile:
                    tot = sum(prof.values()) or 1.0
                    brk = "  ".join(f"{k}={v / args.log_every * 1000:.0f}ms/{100 * v / tot:.0f}%"
                                    for k, v in prof.items())
                    peak = torch.cuda.max_memory_allocated() / 1e9 if device == "cuda" else 0.0
                    print(f"    [profile] per-step avg: {brk}  | peak VRAM {peak:.1f} GB", flush=True)
                    for k in prof:
                        prof[k] = 0.0
                telem.log(step, loss=loss.item(), gnorm=float(gnorm), it_s=rate,
                          lr=opt.param_groups[0]["lr"], epoch=step / max(1, len(ds)))
            if step % args.save_every == 0 and not args.smoke:
                p = os.path.join(args.save_dir, f"riffer_step{step}.pt")
                # capture exact-resume state in TRAIN mode (y iterate + opt state) BEFORE EMA/SF swap
                _resume_state = {"model_train": adapter_state_dict(wrappers, cond_enc), "opt": opt.state_dict(),
                                 "step": step, "torch_rng": torch.get_rng_state()}
                if ema is not None:
                    ema.copy_to()                            # EMA: swap in averaged weights for the save
                if _sf:
                    opt.eval()                               # SF: save the averaged iterate
                torch.save({"state": adapter_state_dict(wrappers, cond_enc), "args": vars(args),
                            "control_mode": args.control_mode, "scalar_field": getattr(args, "scalar_field", None),
                            "control_feature": getattr(args, "control_feature", None),
                            "scalar_from_timeseries": getattr(args, "scalar_from_timeseries", ""),
                            "scalar_norm": [getattr(ds, "scalar_mean", 0.0), getattr(ds, "scalar_std", 1.0)],
                            "bpm_norm": [getattr(ds, "bpm_mean", 0.0), getattr(ds, "bpm_std", 1.0)],
                            "fp_variant": getattr(args, "fp_variant", None),
                            "genre_vocab": _fp_vocab,
                            "fp_in_dim": getattr(cond_enc, "in_dim", None),
                            **_extra_ckpt_fields(),
                            **_resume_state}, p)
                if ema is not None:
                    ema.restore()
                if _sf:
                    opt.train()
                print(f"[save] {p}", flush=True)
                if args.save_cooldown and not args.smoke:
                    print(f"[cooldown] {args.save_cooldown:g}s GPU idle (thermal relief)", flush=True)
                    time.sleep(args.save_cooldown)
            if args.max_hours and (time.time() - t0) >= args.max_hours * 3600:
                print(f"[time] reached {args.max_hours}h limit at step {step}", flush=True)
                step = args.steps   # force the outer while to exit -> final save runs
                break
            if step >= args.steps:
                break

        # --- epoch boundary: val loss + early-stop for fingerprint mode ---
        # RF val loss is a coarse early-stop signal (loss is nearly blind to control);
        # --max-epochs 20 is the practical stop, val loss guards against divergence.
        epoch += 1
        if val_dl is not None and not args.smoke and step < args.steps:
            cond_enc.eval()
            if ema is not None:
                ema.copy_to()
            val_loss_sum = 0.0
            val_n = 0
            with torch.no_grad():
                for vb in val_dl:
                    vT = args.crop_frames
                    vc = vb["latent"][:, :, :vT].to(device=device, dtype=dtype)
                    vB = vc.shape[0]
                    vt = _sample_t(args.timestep_sampler, vB, device)
                    vn = torch.randn_like(vc)
                    vnoised = vc * (1 - vt.view(vB, 1, 1)) + vn * vt.view(vB, 1, 1)
                    vtarget = vn - vc
                    vctrl = cond_enc(vb["fingerprint"].to(device=device, dtype=dtype))
                    vcond = build_train_cond(sam, vb["prompt"], crop_seconds, vT, device, dtype)
                    with use_control_context(ControlContext(vctrl)):
                        vv = dit(vnoised, vt, **vcond, cfg_scale=1.0, cfg_dropout_prob=0.0,
                                 use_checkpointing=False)
                    val_loss_sum += torch.nn.functional.mse_loss(vv.float(), vtarget.float()).item()
                    val_n += 1
            if ema is not None:
                ema.restore()
            cond_enc.train()
            val_loss = val_loss_sum / max(1, val_n)
            print(f"[epoch {epoch}] val_rf_loss={val_loss:.4f} (best={best_val_loss:.4f} "
                  f"patience={epochs_since_best}/{args.early_stop_patience})", flush=True)
            if wb is not None:
                wb.log({"val/rf_loss": val_loss}, step=step)
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                epochs_since_best = 0
            else:
                epochs_since_best += 1
            if epochs_since_best >= args.early_stop_patience or epoch >= args.max_epochs:
                print(f"[early-stop] epoch={epoch} epochs_since_best={epochs_since_best} "
                      f"val_loss={val_loss:.4f} -> stopping", flush=True)
                step = args.steps   # force outer while exit -> final save
        elif epoch >= args.max_epochs and not args.smoke and step < args.steps:
            print(f"[max-epochs] reached {args.max_epochs} epochs at step {step}", flush=True)
            step = args.steps

    if args.smoke:
        # Confirm the adapters (not the base) received gradients.
        #
        # This used to read p.grad HERE, after the loop -- but the loop ends with
        # opt.zero_grad(set_to_none=True), so every .grad was None and the check reported
        # "0 adapter tensors got grads; mean grad-norm nan" while still printing
        # "[smoke OK]". A gate whose whole job is to catch "the thing you think you are
        # training is not training" cannot itself be blind to that, so it now samples
        # inside the step and FAILS instead of narrating. It also covers the joint DoRA
        # params, which is exactly the case that was silently a no-op under
        # --optimizer fusion*. (CONTINUITY 2026-09-09)
        g = list(_smoke_adapter_g)
        base_frozen = all(not p.requires_grad for w in wrappers for p in w.base_attention.parameters())
        base_no_grad = all(p.grad is None for w in wrappers for p in w.base_attention.parameters())
        dg = list(_smoke_dora_g)
        if not g:
            raise SystemExit("[smoke FAIL] no adapter tensor received a gradient — the "
                             "control adapters are not training")
        if args.dora_rank > 0 and not dg:
            raise SystemExit(f"[smoke FAIL] --dora-rank {args.dora_rank} was requested but no "
                             "DoRA tensor received a gradient — the rank is being paid for and "
                             "not trained (this is what the fusion param-group bug looked like)")
        if dg:
            print(f"[smoke] {len(dg)} DoRA tensors got grads; mean grad-norm {np.mean(dg):.4e}",
                  flush=True)
        print(f"[smoke OK] {len(g)} adapter tensors got grads; mean grad-norm {np.mean(g):.4e}; "
              f"base cross-attn frozen={base_frozen} got_no_grad={base_no_grad}", flush=True)
    else:
        _resume_state = {"model_train": adapter_state_dict(wrappers, cond_enc), "opt": opt.state_dict(),
                         "step": step, "torch_rng": torch.get_rng_state()}
        if ema is not None:
            ema.copy_to()                                    # EMA: final save = averaged weights
        if _sf:
            opt.eval()                                       # SF: final save = averaged iterate
        torch.save({"state": adapter_state_dict(wrappers, cond_enc), "args": vars(args),
                            "control_mode": args.control_mode, "scalar_field": getattr(args, "scalar_field", None),
                            "control_feature": getattr(args, "control_feature", None),
                            "scalar_from_timeseries": getattr(args, "scalar_from_timeseries", ""),
                            "scalar_norm": [getattr(ds, "scalar_mean", 0.0), getattr(ds, "scalar_std", 1.0)],
                            "bpm_norm": [getattr(ds, "bpm_mean", 0.0), getattr(ds, "bpm_std", 1.0)],
                            "fp_variant": getattr(args, "fp_variant", None),
                            "genre_vocab": _fp_vocab,
                            "fp_in_dim": getattr(cond_enc, "in_dim", None),
                            **_extra_ckpt_fields(),
                            **_resume_state},
                   os.path.join(args.save_dir, "riffer_final.pt"))
        if ema is not None:
            ema.restore()
        if getattr(args, "export_onnx_on_finish", True) and not getattr(args, "smoke", False):
            try:
                export_control_onnx_on_finish(os.path.join(args.save_dir, "riffer_final.pt"),
                                              args.save_dir, args.export_onnx_frames,
                                              getattr(args, "scalar_field", None))
            except Exception as e:
                print(f"[export] hook failed ({e}); training already saved, continuing", flush=True)
    if wb:
        wb.finish()
    print(f"done -> {args.save_dir}", flush=True)


if __name__ == "__main__":
    main()
