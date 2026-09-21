"""dm_log_path must find a DM log that lives in a LINKED WORKTREE, not only in the
main checkout.

A DM log is a tracked file, so it exists only in the worktrees whose branch carries
it: `flatline.wintermute.log` is on `latent-forge`, checked out at a linked
worktree, while the main checkout sits on another branch and does not have the file
at all. The old code hardcoded the main root, so a DM sent to FLATLINE created a
fresh, near-empty log there -- and she reads the branch, so she would never have
seen it. It happened twice on 2026-09-21; both were caught by eye and moved by
hand. An unnoticed one is simply a lost message, with no error anywhere.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Misc"))
agent_dialogue = pytest.importorskip("agent_dialogue")


@pytest.fixture
def roots(tmp_path, monkeypatch):
    """A fake main checkout plus one linked worktree."""
    main, wt = tmp_path / "SAO", tmp_path / "review"
    main.mkdir(); wt.mkdir()
    monkeypatch.setattr(agent_dialogue, "SAO", main)
    monkeypatch.setattr(agent_dialogue, "_WORKTREES", [main, wt])
    return main, wt


def test_finds_a_log_that_exists_only_in_a_worktree(roots):
    main, wt = roots
    (wt / "flatline.wintermute.log").write_text("# real conversation\n")
    assert agent_dialogue.dm_log_path("WINTERMUTE", "FLATLINE") == wt / "flatline.wintermute.log"


def test_main_wins_when_both_carry_the_log(roots):
    main, wt = roots
    (main / "ghost-note.wintermute.log").write_text("# live log\n" + "x" * 500)
    (wt / "ghost-note.wintermute.log").write_text("# stale branch copy\n")
    assert agent_dialogue.dm_log_path("WINTERMUTE", "GHOST-NOTE") == main / "ghost-note.wintermute.log"


def test_a_bigger_worktree_copy_wins_and_says_so(roots, capsys):
    """The reverse case: main's copy is the stale branch one."""
    main, wt = roots
    (main / "ghost-note.wintermute.log").write_text("# stale\n")
    (wt / "ghost-note.wintermute.log").write_text("# live log\n" + "x" * 500)
    assert agent_dialogue.dm_log_path("WINTERMUTE", "GHOST-NOTE") == wt / "ghost-note.wintermute.log"
    assert "conversation actually is" in capsys.readouterr().err


def test_a_new_pair_falls_back_to_the_canonical_root(roots):
    main, _ = roots
    assert agent_dialogue.dm_log_path("WINTERMUTE", "NOBODY") == main / "nobody.wintermute.log"


def test_the_name_is_order_independent(roots):
    assert (agent_dialogue.dm_log_path("WINTERMUTE", "FLATLINE").name
            == agent_dialogue.dm_log_path("FLATLINE", "WINTERMUTE").name
            == "flatline.wintermute.log")
