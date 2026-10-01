"""Latent mix tree and norm restoration (spec §8.1 S7-S8)."""
import torch

from .contract import ForgeError

NODE_DEFS = {"tree": [("M1", "L0", "L1"), ("M2", "L2", "L3"), ("MX", "M1", "M2")],
             "cascade": [("M1", "L0", "L1"), ("M2", "M1", "L2"), ("MX", "M2", "L3")]}


def lerp(a, b, t):
    return (1.0 - float(t)) * a + float(t) * b


def _default_slerp():
    from stable_audio_3.inference.longform import slerp
    return slerp


def mix_latents(lanes, mix, slerp_fn=None):
    order = mix.get("order")
    if order == "quad":
        used = [i for i in range(4) if lanes[i] is not None]
        if not used:
            raise ForgeError(400, "nothing to mix — every lane is empty or muted")
        raw = [max(0.0, float(mix["quad_weights"][i])) for i in used]
        total = sum(raw)
        ws = [1.0 / len(used)] * len(used) if total <= 0 else [r / total for r in raw]
        z = sum(w * lanes[i].float() for w, i in zip(ws, used))
        weff = [0.0] * 4
        for w, i in zip(ws, used):
            weff[i] = w
        return z, weff
    if order not in NODE_DEFS:
        raise ForgeError(400, f"unknown mix order {order!r}")
    vals = {f"L{i}": ((lanes[i].float(), {i: 1.0}) if lanes[i] is not None else (None, None)) for i in range(4)}
    for name, a, b in NODE_DEFS[order]:
        (za, wa), (zb, wb) = vals[a], vals[b]
        if za is None and zb is None:
            vals[name] = (None, None)
        elif zb is None:
            vals[name] = (za, wa)
        elif za is None:
            vals[name] = (zb, wb)
        else:
            node = mix["nodes"][name]
            t = float(node["t"])
            if node["interp"] == "slerp":
                z = (slerp_fn or _default_slerp())(za, zb, t)
            elif node["interp"] == "lerp":
                z = lerp(za, zb, t)
            else:
                raise ForgeError(400, f"unknown interp {node['interp']!r} at {name}")
            w = {k: v * (1.0 - t) for k, v in wa.items()}
            for k, v in wb.items():
                w[k] = w.get(k, 0.0) + v * t
            vals[name] = (z, w)
    z, w = vals["MX"]
    if z is None:
        raise ForgeError(400, "nothing to mix — every lane is empty or muted")
    return z, [float(w.get(i, 0.0)) for i in range(4)]


def normalise(z, lanes, w_eff):
    target = torch.zeros_like(z[:, :1, :].float())
    for i, lane in enumerate(lanes):
        if lane is not None and w_eff[i] > 0:
            target = target + w_eff[i] * lane.float().norm(dim=1, keepdim=True)
    cur = z.float().norm(dim=1, keepdim=True).clamp(min=1e-8)
    return z.float() * (target / cur)
