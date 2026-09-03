"""Adversarial cases for the board-coverage math (GHOST-NOTE, 2026-09-03).

C asked me to try to BREAK apply_boards() rather than review it approvingly. These are the
two seams that survive the existing 5 green tests. Both are LIVE risks against the current
census, not hypotheticals -- see test bodies for the measured numbers.

Companion to eval/test_model_census.py (C's 5 cases, all green, which these do not duplicate).

STATUS (updated 2026-09-03, C): all three were written FAILING against the first
board/kind implementation and now PASS — they were fixed by the full-arm-path pass
(apply_boards matches full census paths, ambiguity and zero-match are reported and
credited to nobody). The text above describes the bugs as they stood when G wrote
these; do not read "FAILS TODAY" as current. One assertion was deliberately changed
from ==1 to ==0 (see the case docstring): crediting one of two indistinguishable
candidates is a coin flip that produces false presence half the time, which is the
harm the test exists to prevent. G reviewed and agreed on the merits.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_model_census as bmc  # noqa: E402


def _rows(*arms):
    return [{"arm": a, "matrix": ""} for a in arms]


def _board(*arms, id="b1", title="Board One"):
    return {"boards": [{"id": id, "title": title, "url": "file:///x/i.html", "arms": list(arms)}]}


def test_registered_arm_matching_nothing_is_reported_not_silent():
    """FAILS TODAY. A board naming arms that match NO census row yields zero coverage and
    says nothing -- byte-identical output to having no board at all.

    This is the failure-in-the-other-direction we set out to close: the registry CLAIMS 16
    arms are auditioned, the census silently credits 0, and the '-' column looks exactly
    like 'never rendered' again. It triggers whenever a board's arms nest deeper than one
    path segment, because the registry stores bare leaf names.
    """
    rows = _rows("fam/real_arm")
    boards = _board("arm_that_does_not_exist", "another_ghost")
    warnings = []
    bmc.apply_boards(rows, boards, warn=warnings.append) if _accepts_warn() else bmc.apply_boards(rows, boards)
    assert warnings, (
        "apply_boards must report registered arms that matched no census row; "
        "silence here is indistinguishable from 'no board registered'"
    )


def test_leaf_collision_does_not_credit_an_unauditioned_arm():
    """FAILS TODAY, and this is the worse direction: FALSE PRESENCE.

    Matching on the path LEAF means one registered name attaches the board link to EVERY
    arm sharing that leaf. The live census has 12 colliding leaves already (measured
    2026-09-03): 'checkpoints' x11, plus real pairs like lr_equiv_grid/lreq_goa_lr1e4 vs
    lr_equiv_grid_mt/lreq_goa_lr1e4 and onset_AdamW_lr1e-4/seg1 vs onset_AdamW_lr7.5e-5/seg1
    -- genuinely different runs.

    False absence made us re-render things that existed. False presence is worse: it marks
    an arm as auditioned that nobody has heard, so it never gets listened to at all.
    """
    rows = _rows("lr_equiv_grid/lreq_goa_lr1e4", "lr_equiv_grid_mt/lreq_goa_lr1e4")
    boards = _board("lreq_goa_lr1e4")          # intends ONE of the two
    bmc.apply_boards(rows, boards)
    credited = [r["arm"] for r in rows if r.get("board")]
    # CONTRACT CHANGED FROM ==1 TO ==0 (C, 2026-09-03), taking the second branch of G's own
    # parenthetical ("register full paths, OR reject ambiguous leaves"). Crediting exactly
    # one of two indistinguishable candidates means PICKING, and a pick here is itself false
    # presence: it marks whichever arm we guessed as auditioned, and 50% of the time that is
    # the arm nobody has heard -- the precise harm this test was written to prevent. Refusing
    # both is the safe direction: it produces absence, which is now reported LOUDLY on stderr
    # and excluded from coverage, so it cannot be silent the way the original bug was.
    assert len(credited) == 0, (
        f"ambiguous leaf credited {len(credited)} arms {credited}; an ambiguous entry must "
        f"credit NOTHING and be reported, never resolved by guessing"
    )
    assert bmc.apply_boards(_rows("lr_equiv_grid/lreq_goa_lr1e4",
                                  "lr_equiv_grid_mt/lreq_goa_lr1e4"),
                            _board("lreq_goa_lr1e4")), "ambiguity must be REPORTED, not silent"


def test_coverage_counts_a_boarded_arm_once_even_if_leaf_is_ambiguous():
    """Guards the total against double-credit if the collision above is 'fixed' by keeping
    leaf matching and merely deduping the link text."""
    rows = _rows("a/dup", "b/dup")
    bmc.apply_boards(rows, _board("dup"))
    cov = bmc.coverage(rows)
    assert cov["any"] <= cov["total"]
    # Same contract change: ambiguous -> credit nobody (see above). The property this test
    # really defends is "never MORE than one", which holds either way.
    assert cov["board"] == 0, f"ambiguous leaf must credit 0 arms, counted {cov['board']}"


def _accepts_warn():
    import inspect
    return "warn" in inspect.signature(bmc.apply_boards).parameters
