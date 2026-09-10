"""LR schedule: warmup -> hold -> cosine, and who is allowed to own it.

Two things are being pinned here. The SHAPE (a run asking for a schedule gets one), and
the GATE -- before 2026-09-09 --warmup-steps was silently ignored on every optimizer except
adamw, so a run could ask for warmup, have it echoed into its own run_meta, and train
without it. A no-op that reports success is worse than an error.
"""
import importlib.util, sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "control" / "sa3_control" / "train.py"


def _lr_multiplier():
    """Pull just the pure helper out of train.py without importing torch etc."""
    src = SRC.read_text()
    start = src.index("def lr_multiplier(")
    end = src.index("\nclass EMA:", start)
    ns = {}
    exec("import math\n" + src[start:end], ns)
    return ns["lr_multiplier"]


lr_multiplier = _lr_multiplier()


def test_warmup_is_linear_and_reaches_one():
    assert lr_multiplier(1, 1000, 0, 0) == 0.001
    assert lr_multiplier(500, 1000, 0, 0) == 0.5
    assert lr_multiplier(1000, 1000, 0, 0) == 1.0


def test_hold_keeps_full_lr_then_cosine_starts():
    # warmup 1000, hold 1000, cosine 10000 -- the requested D18 shape.
    assert lr_multiplier(1000, 1000, 1000, 10000) == 1.0
    assert lr_multiplier(1999, 1000, 1000, 10000) == 1.0
    assert lr_multiplier(2000, 1000, 1000, 10000) == 1.0        # cosine's first point IS 1.0
    mid = lr_multiplier(7000, 1000, 1000, 10000)                # halfway through the cosine
    assert abs(mid - 0.5) < 1e-9
    assert lr_multiplier(12000, 1000, 1000, 10000) == 0.0       # fully decayed


def test_monotone_non_increasing_through_the_decay():
    prev = 1.1
    for st in range(2000, 12001, 100):
        cur = lr_multiplier(st, 1000, 1000, 10000)
        assert cur <= prev + 1e-12, f"LR rose at step {st}"
        prev = cur


def test_floor_is_respected():
    assert abs(lr_multiplier(12000, 1000, 1000, 10000, 0.1) - 0.1) < 1e-12
    assert lr_multiplier(99999, 1000, 1000, 10000, 0.1) == 0.1


def test_no_flags_is_exactly_the_old_behaviour():
    # cosine 0 => flat forever; this is what guarantees an existing run cannot change.
    for st in (1, 10, 5000, 100000):
        assert lr_multiplier(st, 0, 0, 0) == 1.0


def test_warmup_gate_covers_lion_not_just_adamw():
    src = SRC.read_text()
    assert '_sched_external = args.optimizer in ("adamw", "lion", "sfadamw")' in src, \
        "the schedule gate must name lion; gating on adamw alone made --warmup-steps a silent no-op"
    assert 'args.optimizer == "adamw"' not in src.split("_sched_external")[1][:2000], \
        "the old adamw-only gate is still applying the LR"
