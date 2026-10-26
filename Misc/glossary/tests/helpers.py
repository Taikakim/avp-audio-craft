# Owner: WINTERMUTE (created 2026-10-26)
"""Builders for valid glossary entries; tests override one field to break exactly one rule."""
import copy


def make_q(level=1, **over):
    q = {"level": level, "q": "What does it average?", "options": ["a", "b", "c", "d", "e"],
         "answer": 0, "why": "Because it keeps a running average."}
    q.update(over)
    return q


def make_entry(**over):
    e = {"id": "momentum", "term": "momentum", "plain": "A running average of recent gradients.",
         "quiz": [make_q(1), make_q(2), make_q(3)], "quiz_reviewed": "2026-10-26"}
    e.update(copy.deepcopy(over))
    return e


def other_entry(**over):
    """A second valid entry with a different id/term, for collision tests."""
    base = make_entry(id="weight", term="weight", plain="A number the model learns.")
    base.update(copy.deepcopy(over))
    return base
