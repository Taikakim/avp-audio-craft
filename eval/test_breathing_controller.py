"""TDD for the breathing-noise controller's window-level control law (#35).

Pure state machine (Kim's design + W's meter validation, docs/a2a-loop-attractor.md):
per window it sees the emerging output's NOVELTY (1 - max patch-self-sim to the
preceding 8-40s; W's recurrence_meter v3) and sets the NEXT window's init_noise_level.
W's finding drives the design: NOVELTY is the robust signal (raw recurrence saturates),
so the trigger is novelty collapsing below the SOURCE's own floor. Schmitt-trigger
hysteresis: step DOWN when novelty < source floor (output loops harder than the source
ever did), step back UP only once novelty recovers above the source's median — never
oscillate. NaN novelty (the meter's first-8s no-reference band) => HOLD.

Recurrence is available as an optional secondary down-trigger but novelty leads.
No GPU, no decode, no meter dependency here — just the law.
"""
import math
from breathing_controller import BreathingController


def _ctl(**kw):
    kw.setdefault("requested_nl", 0.7)
    kw.setdefault("novelty_floor", 0.30)   # source never dipped below this novelty (p10)
    kw.setdefault("novelty_up", 0.50)      # source's median novelty (recovery threshold)
    kw.setdefault("nl_step", 0.1)
    kw.setdefault("nl_min", 0.3)
    return BreathingController(**kw)


def test_holds_at_requested_when_novelty_healthy():
    c = _ctl()
    assert c.update(novelty=0.6) == 0.7        # above floor -> no loop -> requested nl
    assert c.update(novelty=0.55) == 0.7


def test_steps_down_when_novelty_below_source_floor():
    c = _ctl()
    # output novelty collapses below the source's floor => looping => step nl DOWN
    assert c.update(novelty=0.1) == 0.6
    assert c.engaged is True


def test_holds_down_in_hysteresis_band():
    c = _ctl()
    c.update(novelty=0.1)                       # -> 0.6, engaged
    # novelty back above the floor but not yet above the median (median=0.5):
    # in the hysteresis band => hold, do NOT step up yet
    assert c.update(novelty=0.4) == 0.6


def test_steps_up_when_novelty_recovers_above_median():
    c = _ctl()
    c.update(novelty=0.1)                       # -> 0.6, engaged
    c.update(novelty=0.6)                       # above median -> ease up
    assert abs(c.nl - 0.7) < 1e-9


def test_nan_novelty_holds():
    c = _ctl()
    c.update(novelty=0.1)                       # -> 0.6, engaged
    # meter's first-8s no-reference band: NaN => hold, neither down nor up
    assert c.update(novelty=float("nan")) == 0.6
    assert c.engaged is True


def test_clamps_down_to_nl_min():
    c = _ctl(requested_nl=0.7, nl_min=0.5, nl_step=0.1)
    c.update(novelty=0.0)   # 0.6
    c.update(novelty=0.0)   # 0.5 (floor)
    assert c.update(novelty=0.0) == 0.5


def test_recovery_caps_at_requested_and_disengages():
    c = _ctl()
    c.update(novelty=0.1)          # 0.6, engaged
    c.update(novelty=0.9)          # 0.7, back to requested
    assert abs(c.nl - 0.7) < 1e-9
    assert c.engaged is False
    assert c.update(novelty=0.99) == 0.7        # can't exceed requested


def test_recurrence_secondary_trigger():
    # if a source r_max is supplied, a recurrence spike also steps down even when
    # novelty looks ok (belt-and-suspenders; novelty still leads by default)
    c = _ctl(r_src_max=0.6)
    assert c.update(novelty=0.6, recurrence=0.8) == 0.6
    assert c.engaged is True
