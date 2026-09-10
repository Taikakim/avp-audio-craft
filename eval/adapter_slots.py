"""Resident adapter slots -- A/B between models with no offload and no reload.

The mechanism already exists in the SA3 fork and this module only DRIVES it:

  stable_audio_3/model.py           load_lora(paths)  -> lora_index = enumerate(paths)
  models/lora/utils.py              enable_lora / disable_lora(model, lora_index=i)
  models/lora/model.py              set_lora_strength(s, lora_index=i)
  models/lora/model.py              remove_lora_by_index(model, i)
  models/dit.py                     per-index gating INSIDE the forward, every step,
                                    from lora_configs=[{"lora_index", "interval",
                                    "layer_filter"}]

TWO TRAPS, both silent:

1. dit.py only touches indices that APPEAR in lora_configs. An omitted index keeps
   whatever enable/disable state it last had, so an "A vs B" render can quietly be
   "A+B" -- and it would sound plausible. Therefore lora_configs() ALWAYS covers
   every resident index, and an inactive slot gets an interval sigma can never
   satisfy (belt) plus strength 0 (braces).

2. load_and_apply_loras re-indexes from 0 on every call, so calling load_lora()
   again to ADD one adapter collides with index 0. Changing the resident SET must
   be remove_lora_by_index for every index, then ONE load_lora(full list).
   Switching between already-resident adapters costs nothing.

VRAM, MEASURED on this box 2026-08-26 (not estimated -- the plan's estimates were
both optimistic):
  * medium-base resident leaves **7.40 GB free** on the 15.9 GB card, so the
    baseline is ~8.5 GB, not the ~5.1 GB the plan assumed.
  * two r128 DoRAs cost **0.79 GB together, i.e. ~0.40 GB each**, not 0.33 -- the
    0.33 figure counts adapter tensors only and misses the per-module
    parametrization bookkeeping.
  * `remove_lora_by_index` + reload was verified to revert the base weights EXACTLY
    (max |drift| = 0.0 over 50 tensors), which is what makes switching the slot set
    safe rather than cumulatively corrupting.
So the practical budget with a 6.0 GB floor is ~3 resident r128 adapters. Still far
better than a second backbone (+8.5 GB, which does not fit at all). Full-FT states
cannot be slots -- they replace the backbone, not augment it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

# An interval sigma is never inside, so dit.py calls disable_lora on this slot
# every step. Belt to the strength-0 braces.
_OFF_INTERVAL = (2.0, 3.0)
_ON_INTERVAL = (0.0, 1.0)


@dataclass
class Slot:
    index: int
    path: str
    label: str
    family: str
    cost_gb: float
    strength: float = 1.0

    def as_dict(self) -> dict:
        return asdict(self)


def free_vram_gb() -> float:
    """Live free VRAM. Another process on this GPU eats into it, so never assume."""
    try:
        import torch
        free, _total = torch.cuda.mem_get_info()
        return free / 1e9
    except Exception:
        return 0.0


class SlotTable:
    def __init__(self, max_slots: int = 4, vram_floor_gb: float = 6.0,
                 free_gb_fn=None):
        self.max_slots = int(max_slots)
        self.vram_floor_gb = float(vram_floor_gb)
        self._free_gb_fn = free_gb_fn or free_vram_gb
        self.slots: list[Slot] = []

    # ---------------------------------------------------------------- planning
    def plan(self, specs: list[dict]) -> dict:
        """Pure: touches no model. {"ok","slots","reason","projected_free_gb","rebuild"}."""
        cur = [s.path for s in self.slots]
        want = [s["path"] for s in specs]
        rebuild = cur != want
        slots = [Slot(index=i, path=s["path"], label=s.get("label") or s["path"],
                      family=s.get("family", "adapter"),
                      cost_gb=float(s.get("cost_gb", 0.33)),
                      strength=float(s.get("strength", 1.0)))
                 for i, s in enumerate(specs)]
        bad = [s for s in slots if s.family != "adapter"]
        if bad:
            return {"ok": False, "rebuild": False, "slots": slots,
                    "projected_free_gb": round(self._free_gb_fn(), 2),
                    "reason": (f"{bad[0].family} cannot be a slot: only adapters share "
                               "one base. Use the full-FT backbone swap instead.")}
        if len(slots) > self.max_slots:
            return {"ok": False, "rebuild": False, "slots": slots,
                    "projected_free_gb": round(self._free_gb_fn(), 2),
                    "reason": f"{len(slots)} slots requested, max is {self.max_slots}"}
        free = self._free_gb_fn()
        added = sum(s.cost_gb for s in slots) - sum(s.cost_gb for s in self.slots)
        projected = free - max(added, 0.0)
        if projected < self.vram_floor_gb:
            return {"ok": False, "rebuild": False, "slots": slots,
                    "projected_free_gb": round(projected, 2),
                    "reason": (f"would leave {projected:.2f} GB free, below the "
                               f"{self.vram_floor_gb:.1f} GB floor "
                               "(a T4096 render needs the headroom)")}
        return {"ok": True, "rebuild": rebuild, "slots": slots,
                "projected_free_gb": round(projected, 2), "reason": ""}

    # ---------------------------------------------------------------- applying
    def apply(self, model, specs: list[dict]) -> dict:
        plan = self.plan(specs)
        if not plan["ok"]:
            return plan
        if not plan["rebuild"]:
            self.slots = plan["slots"]
            return plan
        try:
            from stable_audio_3.models.lora import remove_lora_by_index
        except Exception:                        # CPU test double: no fork present
            remove_lora_by_index = None
        for s in self.slots:
            if remove_lora_by_index is not None and hasattr(model, "model"):
                remove_lora_by_index(model.model.model, s.index)
                remove_lora_by_index(model.model.conditioner, s.index)
            if hasattr(model, "removed"):        # test double
                model.removed.append(s.index)
        paths = [s.path for s in plan["slots"]]
        if paths:
            model.load_lora(paths)
        self.slots = plan["slots"]
        return plan

    # ---------------------------------------------------------------- driving
    def lora_configs(self, active: int | None,
                     interval: tuple[float, float] = _ON_INTERVAL,
                     layer_filter: str = "") -> list[dict]:
        """ALWAYS covers every resident index -- see trap 1 in the module docstring."""
        return [{"lora_index": s.index,
                 "interval": tuple(interval) if s.index == active else _OFF_INTERVAL,
                 "layer_filter": layer_filter if s.index == active else ""}
                for s in self.slots]

    def strengths(self, active: int | None, strength: float) -> list[tuple[int, float]]:
        return [(s.index, float(strength) if s.index == active else 0.0)
                for s in self.slots]

    def push_strengths(self, model, active: int | None, strength: float) -> None:
        for idx, val in self.strengths(active, strength):
            model.set_lora_strength(val, lora_index=idx)

    def as_dict(self) -> dict:
        return {"slots": [s.as_dict() for s in self.slots],
                "max_slots": self.max_slots,
                "vram_floor_gb": self.vram_floor_gb,
                "free_gb": round(self._free_gb_fn(), 2)}
