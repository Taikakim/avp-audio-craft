"""TDD for BreathingControllerV3 (#35 v3, Kim's 2026-07-10 v2-verdict).

v2 fixed bass/drums + breaks but the a2a is still STATIC (within-window SDEdit averaging
at high nl — the SDXL-video self-averaging failure). v3 (Kim's design): flush the average
by dipping DEEP (toward ~0) to re-inject crisp source, timed by more source/output signals,
and use a HIGHER ceiling between dips:
- flush (deep dip to ~0.05) on: source break, source FILL, or OUTPUT HF-static;
- FILLs re-ramp FAST (the fill masks the transition); breaks/HF re-ramp slow;
- low source density => 'relax' to a lower ceiling (smooth dip for a few measures);
- novelty feedback still breaks loops.

step(source_break, source_fill, source_low_density, prev_novelty, prev_hf_static) -> nl.
Pure state machine, no GPU/meter.
"""
import math
from breathing_controller import BreathingControllerV3


def _c(**kw):
    kw.setdefault("ceiling", 0.70)
    kw.setdefault("relax_ceiling", 0.30)
    kw.setdefault("nl_min", 0.30)
    kw.setdefault("flush_floor", 0.05)
    kw.setdefault("reramp_start", 0.30)
    kw.setdefault("reramp_step", 0.05)
    kw.setdefault("fast_reramp_step", 0.15)
    kw.setdefault("novelty_floor", 0.30)
    kw.setdefault("nl_step", 0.10)
    return BreathingControllerV3(**kw)


def _s(c, brk=False, fill=False, low=False, nov=0.7, hf=False):
    return c.step(source_break=brk, source_fill=fill, source_low_density=low,
                  prev_novelty=nov, prev_hf_static=hf)


def test_holds_at_high_ceiling_when_healthy():
    c = _c()
    assert _s(c) == 0.70                          # starts at + holds the raised ceiling


def test_source_break_dips_deep():
    c = _c()
    assert _s(c, brk=True) == 0.05                # deep flush, not v2's 0.30


def test_fill_dips_deep_then_reramps_FAST():
    c = _c()
    assert _s(c, fill=True) == 0.05
    assert abs(_s(c) - 0.30) < 1e-9               # reramp_start
    assert abs(_s(c) - 0.45) < 1e-9               # + fast_reramp_step (0.15), not slow 0.05


def test_break_reramps_SLOW():
    c = _c()
    _s(c, brk=True)                               # 0.05
    assert abs(_s(c) - 0.30) < 1e-9               # reramp_start
    assert abs(_s(c) - 0.35) < 1e-9               # + slow reramp_step (0.05)


def test_output_hf_static_triggers_flush():
    c = _c()
    assert _s(c, hf=True) == 0.05                 # output going static -> deep dip to flush


def test_low_density_relaxes_to_lower_ceiling():
    c = _c()                                      # starts 0.70
    a = _s(c, low=True)                           # ease DOWN toward relax_ceiling 0.30
    b = _s(c, low=True)
    assert a < 0.70 and b < a                     # smooth dip
    for _ in range(20):
        nl = _s(c, low=True)
    assert abs(nl - 0.30) < 1e-9                  # settles at relax_ceiling


def test_recovers_to_full_ceiling_when_density_returns():
    c = _c()
    for _ in range(20):
        _s(c, low=True)                           # down at 0.30
    for _ in range(20):
        nl = _s(c, low=False)                     # density back -> ease up to 0.70
    assert abs(nl - 0.70) < 1e-9


def test_novelty_loop_steps_down_in_normal_region():
    c = _c()
    _s(c)                                          # 0.70
    assert abs(_s(c, nov=0.1) - 0.60) < 1e-9       # loop -> step down by nl_step
