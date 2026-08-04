"""TDD for BreathingControllerV2 (#35 T1, Kim's 2026-07-10 ear-verdict).

v1's 0.45-0.55 band was too narrow a mid-range (noisy/stringy/pale, lost melody+bass).
v2 (Kim's spec, via W): WIDER band (floor ~0.30, ceiling ~0.62) + a FEEDFORWARD
source-structure signal. On a SOURCE break/pause, duck nl hard to the floor (let the
source through nearly clean), then re-ramp to ~0.41 and climb slowly back to the ceiling.
In non-break regions the existing novelty feedback (Schmitt) still breaks output loops.

step(source_break, prev_novelty) -> nl for THIS window. source_break is feedforward
(known from the original track up front); prev_novelty is feedback from the last output
window. Pure state machine, no GPU/meter.
"""
import math
from breathing_controller import BreathingControllerV2


def _ctl(**kw):
    kw.setdefault("requested_nl", 0.62)      # ceiling
    kw.setdefault("novelty_floor", 0.30)
    kw.setdefault("novelty_up", 0.55)
    kw.setdefault("nl_min", 0.30)
    kw.setdefault("nl_step", 0.10)
    kw.setdefault("break_floor", 0.30)
    kw.setdefault("reramp_start", 0.41)
    kw.setdefault("reramp_step", 0.05)
    return BreathingControllerV2(**kw)


def test_holds_at_ceiling_when_healthy():
    c = _ctl()
    assert c.step(source_break=False, prev_novelty=0.7) == 0.62
    assert c.step(source_break=False, prev_novelty=0.6) == 0.62


def test_source_break_ducks_hard_to_floor():
    c = _ctl()
    assert c.step(source_break=True, prev_novelty=0.7) == 0.30   # let source through


def test_reramp_to_start_then_climb_slowly_after_break():
    c = _ctl()
    c.step(source_break=True, prev_novelty=0.7)                  # 0.30 (break)
    assert c.step(source_break=False, prev_novelty=0.7) == 0.41  # re-ramp start
    assert abs(c.step(source_break=False, prev_novelty=0.7) - 0.46) < 1e-9   # +reramp_step
    assert abs(c.step(source_break=False, prev_novelty=0.7) - 0.51) < 1e-9


def test_reramp_caps_at_ceiling_and_resumes_normal():
    c = _ctl()
    c.step(source_break=True, prev_novelty=0.7)     # 0.30
    for _ in range(20):                             # climb until ceiling
        nl = c.step(source_break=False, prev_novelty=0.7)
    assert abs(nl - 0.62) < 1e-9
    assert c.ramping is False


def test_novelty_loop_steps_down_in_normal_region():
    c = _ctl()
    # healthy first (at ceiling), then output loops -> step down (wider floor 0.30)
    c.step(source_break=False, prev_novelty=0.7)    # 0.62
    assert abs(c.step(source_break=False, prev_novelty=0.1) - 0.52) < 1e-9
    assert c.engaged is True


def test_novelty_down_clamps_to_nl_min():
    c = _ctl()
    for _ in range(10):
        nl = c.step(source_break=False, prev_novelty=0.05)
    assert abs(nl - 0.30) < 1e-9                     # never below nl_min


def test_break_overrides_active_loop():
    c = _ctl()
    c.step(source_break=False, prev_novelty=0.1)     # stepped down to 0.52, engaged
    assert c.step(source_break=True, prev_novelty=0.1) == 0.30   # break wins -> hard duck


def test_nan_novelty_holds_in_normal_region():
    c = _ctl()
    c.step(source_break=False, prev_novelty=0.7)     # 0.62
    assert c.step(source_break=False, prev_novelty=float("nan")) == 0.62
