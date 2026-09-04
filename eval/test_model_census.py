"""Census coverage math — the board registry must not create false absence.

These pin the failure GHOST-NOTE flagged (2026-09-03): an arm registered on a
NON-standard board (the morph conditioner's control-response grid) must never be
counted as having zero clip coverage. The whole reason the board registry exists is
that 16 morphcond arms reported clips='-' while 4.5 GB of finished renders sat on
disk, and that false absence was read by a human as "never rendered".
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_model_census as bmc


BOARDS = {"boards": [{
    "id": "morph_conditioner", "title": "Morph conditioner", "kind": "control-response",
    "url": "file:///x/index.html", "cells": 384,
    "note": "no objective adherence metric exists for these cells",
    "arms": ["morph_L3_base_s1", "morph_L4_ft_s1"],
}]}


def test_board_arm_is_not_zero_coverage():
    """The regression: registered-but-off-standard-board must count as covered."""
    rows = [{"arm": "morphcond/morph_L3_base_s1", "matrix": ""},
            {"arm": "runs/other_arm", "matrix": ""}]
    bmc.apply_boards(rows, BOARDS)
    cov = bmc.coverage(rows)
    assert cov["board"] == 1, "board-registered arm not counted"
    assert cov["any"] == 1, "board arm read as zero coverage — the exact false-absence bug"
    assert cov["matrix"] == 0, "must not be double-counted as standard-board coverage"


def test_board_arm_gets_a_link_and_keeps_matrix_separate():
    rows = [{"arm": "morphcond/morph_L4_ft_s1", "matrix": ""}]
    bmc.apply_boards(rows, BOARDS)
    assert "Morph conditioner" in rows[0]["board"]
    assert rows[0]["matrix"] == "", "board link must not masquerade as a matrix link"


def test_matrix_arm_untouched_by_boards():
    rows = [{"arm": "x/already_linked", "matrix": "<a href='#'>ep1</a>"}]
    bmc.apply_boards(rows, BOARDS)
    cov = bmc.coverage(rows)
    assert cov["matrix"] == 1 and cov["board"] == 0 and cov["any"] == 1


def test_arm_on_both_counted_once_in_any():
    rows = [{"arm": "morphcond/morph_L3_base_s1", "matrix": "<a href='#'>ep1</a>"}]
    bmc.apply_boards(rows, BOARDS)
    cov = bmc.coverage(rows)
    assert cov["any"] == 1, "an arm on both boards must not inflate total coverage"


def test_empty_registry_is_a_noop():
    rows = [{"arm": "a/b", "matrix": ""}]
    bmc.apply_boards(rows, {"boards": []})
    assert rows[0].get("board", "") == ""
    assert bmc.coverage(rows)["any"] == 0
