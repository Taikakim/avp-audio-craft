"""Breathing-noise controller for long-form a2a (#35, Kim's design 2026-07-08).

The a2a loop attractor: at high init_noise_level the source no longer constrains the
sampler, so in generated regions the model's only context is its own output and the
DiT's repetition prior locks onto a phrase that loops for minutes
(docs/a2a-loop-attractor.md). Fix: close the loop — when the emerging output's NOVELTY
collapses below what the SOURCE itself ever reached, step the noise level DOWN so source
evidence re-anchors and breaks the loop; ease it back UP only once genuinely new material
appears (novelty recovers above the source's median).

W's recurrence_meter v3 validation (mir/src/tools/recurrence_meter.py) drives the design:
NOVELTY (1 - max whitened-patch self-similarity to the preceding 8-40s) is the robust
signal — raw frame-recurrence saturates to ~0.99 on everything. So the controller is
NOVELTY-primary; recurrence is an optional secondary down-trigger. The meter's first-8s
band has no reference and reads NaN → the controller HOLDS there.

This module is the CONTROL LAW only — a pure, GPU-free, decode-free state machine. The
measurements come from the meter; the source-calibrated thresholds (novelty_floor = the
source's p10 novelty, novelty_up = its median) come from meter.calibrate_source(). Tier-1
= window-level: `update()` is called once per longform window with the previous window's
measured novelty and returns the init_noise_level for the next window.
"""
from __future__ import annotations
import math


class BreathingController:
    """Schmitt-trigger hysteresis over init_noise_level, driven by novelty.

    - novelty < novelty_floor (or, if r_src_max given, recurrence > r_src_max) → the
      output loops harder than the source ever did: step nl DOWN, engage.
    - engaged and novelty > novelty_up (source median) → new material emerged: ease nl
      back UP toward requested; disengage once fully recovered.
    - otherwise HOLD — including in the [floor, up] hysteresis band and on NaN novelty
      (the meter's no-reference first-8s band). This is what prevents oscillation.
    """

    def __init__(self, requested_nl: float, novelty_floor: float, novelty_up: float,
                 r_src_max: float | None = None, nl_step: float = 0.1,
                 nl_min: float = 0.3, nl_max: float | None = None):
        if novelty_up < novelty_floor:
            raise ValueError("novelty_up (recovery) must be >= novelty_floor (trigger)")
        self.requested_nl = float(requested_nl)
        self.novelty_floor = float(novelty_floor)
        self.novelty_up = float(novelty_up)
        self.r_src_max = None if r_src_max is None else float(r_src_max)
        self.nl_step = float(nl_step)
        self.nl_min = float(nl_min)
        self.nl_max = float(nl_max) if nl_max is not None else self.requested_nl
        self.nl = float(requested_nl)
        self.engaged = False

    def update(self, novelty: float, recurrence: float | None = None) -> float:
        """Feed the previous window's measured novelty (+ optional recurrence);
        return the next window's nl."""
        if novelty is None or (isinstance(novelty, float) and math.isnan(novelty)):
            return self.nl                       # no-reference band → hold

        looping = novelty < self.novelty_floor
        if self.r_src_max is not None and recurrence is not None:
            looping = looping or recurrence > self.r_src_max

        if looping:
            self.nl = max(self.nl_min, self.nl - self.nl_step)
            self.engaged = True
        elif self.engaged and novelty > self.novelty_up:
            self.nl = min(self.nl_max, self.nl + self.nl_step)
            if self.nl >= self.requested_nl - 1e-12:
                self.nl = self.requested_nl
                self.engaged = False
        # else: hold (healthy & disengaged, or in the hysteresis band)
        return self.nl


class BreathingControllerV2:
    """v2 (Kim's 2026-07-10 ear-verdict): WIDER band + FEEDFORWARD source-break ducking.

    v1 sat in a too-narrow mid-range (0.45-0.55) that neither let the source through nor
    allowed real change — the "noisy stringy pale" mid-noise-band. v2 uses the full range
    (floor ~0.30, ceiling ~0.62) and, crucially, ducks HARD to the floor on a SOURCE
    break/pause (feedforward from the original track) so the source comes through nearly
    clean there, then re-ramps to ~0.41 and climbs slowly back. Output-novelty feedback
    (the v1 Schmitt) still breaks generated loops in the normal (non-break, non-ramp)
    regions. `step(source_break, prev_novelty)` returns THIS window's nl.
    """

    def __init__(self, requested_nl, novelty_floor, novelty_up, nl_min=0.30,
                 nl_step=0.10, break_floor=0.30, reramp_start=0.41, reramp_step=0.05):
        self.requested_nl = float(requested_nl)      # ceiling
        self.novelty_floor = float(novelty_floor)
        self.novelty_up = float(novelty_up)
        self.nl_min = float(nl_min)
        self.nl_step = float(nl_step)
        self.break_floor = float(break_floor)
        self.reramp_start = float(reramp_start)
        self.reramp_step = float(reramp_step)
        self.nl = float(requested_nl)
        self.engaged = False
        self.ramping = False
        self._first_after_break = False

    def step(self, source_break, prev_novelty=None):
        if source_break:                              # feedforward: let the source through
            self.nl = self.break_floor
            self.ramping = True
            self._first_after_break = True
            self.engaged = False
            return self.nl
        if self.ramping:                              # re-ramp after a break
            if self._first_after_break:
                self.nl = self.reramp_start
                self._first_after_break = False
            else:
                self.nl = min(self.requested_nl, self.nl + self.reramp_step)
                if self.nl >= self.requested_nl - 1e-12:
                    self.nl = self.requested_nl
                    self.ramping = False
            return self.nl
        # normal region: novelty feedback (Schmitt, wider band)
        nov = prev_novelty
        if nov is not None and not (isinstance(nov, float) and math.isnan(nov)):
            if nov < self.novelty_floor:
                self.nl = max(self.nl_min, self.nl - self.nl_step)
                self.engaged = True
            elif self.engaged and nov > self.novelty_up:
                self.nl = min(self.requested_nl, self.nl + self.nl_step)
                if self.nl >= self.requested_nl - 1e-12:
                    self.nl = self.requested_nl
                    self.engaged = False
        return self.nl


class BreathingControllerV3:
    """v3 (Kim's 2026-07-10 v2-verdict): FLUSH the within-window average with DEEP dips.

    v2 kept bass/drums + break-timing but the a2a stayed static — high-nl SDEdit refills
    from the model's prior 'average' (the SDXL-video self-averaging failure). v3 dips DEEP
    (toward ~0.05) to re-inject crisp source, timed by more signals, and runs a HIGHER
    ceiling between dips:
      - deep flush on source BREAK, source FILL, or OUTPUT HF-static (the averaging
        signature: low 3-6 kHz envelope variance);
      - FILLs re-ramp FAST (the fill masks the seam); breaks/HF re-ramp slow;
      - low source density => 'relax' to a lower ceiling (smooth multi-measure dip);
      - novelty feedback still breaks output loops.
    step(source_break, source_fill, source_low_density, prev_novelty, prev_hf_static)->nl.
    """

    def __init__(self, ceiling, relax_ceiling, nl_min, novelty_floor, flush_floor=0.05,
                 reramp_start=0.30, reramp_step=0.05, fast_reramp_step=0.15, nl_step=0.10):
        self.ceiling = float(ceiling)
        self.relax_ceiling = float(relax_ceiling)
        self.nl_min = float(nl_min)
        self.novelty_floor = float(novelty_floor)
        self.flush_floor = float(flush_floor)
        self.reramp_start = float(reramp_start)
        self.reramp_step = float(reramp_step)
        self.fast_reramp_step = float(fast_reramp_step)
        self.nl_step = float(nl_step)
        self.nl = float(ceiling)
        self.ramping = False
        self._first_after = False
        self._fast = False

    def step(self, source_break=False, source_fill=False, source_low_density=False,
             prev_novelty=None, prev_hf_static=False):
        if source_break or source_fill or prev_hf_static:      # deep flush
            self.nl = self.flush_floor
            self.ramping = True
            self._first_after = True
            self._fast = bool(source_fill)                     # fills recover fast
            return self.nl
        target = self.relax_ceiling if source_low_density else self.ceiling
        if self.ramping:
            if self._first_after:
                self.nl = min(target, self.reramp_start)
                self._first_after = False
            else:
                step = self.fast_reramp_step if self._fast else self.reramp_step
                self.nl = min(target, self.nl + step)
            if self.nl >= target - 1e-12:
                self.nl = target
                self.ramping = False
            return self.nl
        nov = prev_novelty
        if nov is not None and not (isinstance(nov, float) and math.isnan(nov)) \
                and nov < self.novelty_floor:                  # output loop -> step down
            self.nl = max(self.nl_min, self.nl - self.nl_step)
        elif self.nl > target + 1e-12:                         # ease down to (relax) ceiling
            self.nl = max(target, self.nl - self.reramp_step)
        elif self.nl < target - 1e-12:                         # ease back up to ceiling
            self.nl = min(target, self.nl + self.reramp_step)
        return self.nl
