"""GPU passes of the commit pipeline and its preview jobs (spec §8.1). Every model call holds srv.GPU_LOCK."""
import numpy as np
import torch

from .holdpass import make_hold_callback, make_hold_renoise_hook
from .overlap import pad_target
from .splice import splice_by_mask


def _param(srv):
    return next(srv.MODEL.model.pretransform.parameters())


def _finite(z, label):
    if not torch.isfinite(z).all():
        raise RuntimeError(f"non-finite latents in {label} — refusing to continue")


def model_latent_frames(srv, req, duration):
    """The latent length generate() will actually use (sample_size is an explicit cap)."""
    cond, _ = srv.MODEL._build_conditioning_dicts(req["prompt"], req.get("negative_prompt") or None, duration, 1)
    return int(srv.MODEL._adapt_sample_size(cond, srv.budget_for(duration), 6.0, allow_grow=False) // srv.DS)


def _base_kwargs(srv, req, duration, sigma_max, warnings, latch_cfgs):
    steps = int(req["steps"])
    kw = dict(prompt=req["prompt"], duration=duration, steps=steps, cfg_scale=float(req["cfg_scale"]),
              seed=int(req["seed"]), batch_size=1, sample_size=srv.budget_for(duration),
              apg_scale=float(req["apg_scale"]),
              cfg_interval=srv.resolve_cfg_interval(req, sigma_max=sigma_max),
              dist_shift=srv.resolve_shift(req, steps, sigma_max, warnings))
    if req.get("negative_prompt"):
        kw["negative_prompt"] = req["negative_prompt"]
    if float(req.get("scale_phi") or 0.0) > 0:
        kw["scale_phi"] = float(req["scale_phi"])
    if req.get("sampler_type") and not latch_cfgs:
        kw["sampler_type"] = req["sampler_type"]
    srv.latch_sampler_warning(latch_cfgs, req, warnings)
    return kw


def _generate_latents(srv, kw, req, T, label):
    sink = []
    with srv.film_context(req.get("film")):
        srv.MODEL.generate(**srv.with_lora_interval(kw), latents_sink=sink, return_latents=True)
    z0 = sink[0][..., :T].float().cpu()
    _finite(z0, label)
    return z0


def run_hold_pass(srv, z_lane, depth, req, warnings, label="a2a"):
    depth = np.asarray(depth, dtype=np.float32)
    nl = float(depth.max()) if depth.size else 0.0
    if nl < 1e-3:
        return z_lane
    T = int(z_lane.shape[-1])
    duration = T * srv.DS / srv.SR
    ref = z_lane.float().cpu()
    eps = torch.randn(ref.shape, generator=torch.Generator().manual_seed(int(req["seed"])))
    steps = int(req["steps"])
    with srv.GPU_LOCK:
        srv.prepare_model(srv.resolve_dora_req(req), req.get("film"))
        latch_cfgs, latch_hp = srv.resolve_latch(req.get("latch"), req)
        kw = _base_kwargs(srv, req, duration, nl, warnings, latch_cfgs)
        kw.update(init_latents=ref.to(_param(srv).device), init_noise_level=nl)
        sampler = kw.get("sampler_type")
        pingpong = not latch_cfgs and (sampler == "pingpong" or
                                       (sampler is None and srv.MODEL.model.diffusion_objective == "rf_denoiser"))
        if pingpong:
            kw["renoise_hook"] = make_hold_renoise_hook(ref, eps, depth)
            kw["callback"] = srv.make_log_cb(steps)
        else:
            kw["callback"] = srv.make_log_cb(steps, extra=make_hold_callback(ref, eps, depth))
        srv.apply_latch(kw, latch_cfgs, latch_hp)
        srv.log(f"[forge] {label}: hold pass nl={nl:.2f} steps={steps} ({'renoise hook' if pingpong else 'callback'})")
        z0 = _generate_latents(srv, kw, req, T, label)
    return splice_by_mask(ref, z0, depth > 0)


def run_inpaint_pass(srv, z_lane, regions_sec, req, warnings, chroma_target=None, label="inpaint"):
    T = int(z_lane.shape[-1])
    fps = srv.SR / srv.DS
    mask = np.zeros(T, dtype=bool)
    for s, e in regions_sec:
        mask[max(0, int(np.floor(s * fps))):min(T, int(np.ceil(e * fps)))] = True
    if not mask.any():
        return z_lane
    duration = T * srv.DS / srv.SR
    ref = z_lane.float().cpu()
    with srv.GPU_LOCK:
        srv.prepare_model(srv.resolve_dora_req(req), req.get("film"))
        extra = None
        if chroma_target is not None:
            entry = srv.HEADS.get("chroma_other")
            if entry is None:
                warnings.append("chroma crossfade skipped: the chroma_other head is not registered "
                                "(is the eval drive mounted?)")
            else:
                frames = model_latent_frames(srv, req, duration)
                extra = ({"model_path": entry["path"], "target_raw": pad_target(chroma_target, frames),
                          "end_pct": 0.6}, float(entry["default_gain"]))
        latch_cfgs, latch_hp = srv.resolve_latch(req.get("latch"), req, extra_first=extra)
        kw = _base_kwargs(srv, req, duration, 1.0, warnings, latch_cfgs)
        kw.update(inpaint_latents=ref.to(_param(srv).device),
                  inpaint_mask_start_seconds=[float(s) for s, _ in regions_sec],
                  inpaint_mask_end_seconds=[float(e) for _, e in regions_sec],
                  callback=srv.make_log_cb(int(req["steps"])))
        srv.apply_latch(kw, latch_cfgs, latch_hp)
        srv.log(f"[forge] {label}: inpaint {len(regions_sec)} region(s)")
        z0 = _generate_latents(srv, kw, req, T, label)
    return splice_by_mask(ref, z0, mask)


def steer_master(srv, z, head, gain):
    with srv.GPU_LOCK:
        h = srv._player_steer_head(head)
        dev = _param(srv).device
        with torch.inference_mode(False), torch.enable_grad():
            zz = z.detach().float().to(dev).clone().requires_grad_(True)
            ts = torch.tensor([0.001], dtype=torch.float32, device=dev)
            h(zz, ts).mean().backward()
            out = (zz.detach() + float(gain) * zz.grad).cpu()
    _finite(out, "master chain")
    return out


def decode_latent(srv, z, n_samples):
    pre = srv.MODEL.model.pretransform
    p = _param(srv)
    with srv.GPU_LOCK, torch.inference_mode():
        audio = pre.decode(z.to(device=p.device, dtype=p.dtype), chunked=True, chunk_size=128, overlap=32)
    return audio[0, :, : int(n_samples)].float().cpu()
