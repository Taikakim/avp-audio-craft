#!/usr/bin/env python3
"""Tests for goa_caption_task.compose_hint — the corpus-hint x per-track-metadata composition.

Worth testing because every failure mode here is SILENT: a wrongly composed hint still produces a
fluent caption, and the only symptom is a model that learns the wrong era for a corpus. The bug that
motivated the per-track map (goa big-set: no hint -> 1.2% of a goa corpus mentioned goa) took a day
to find precisely because nothing errored.

Run: python3 -m pytest lumi/test_compose_hint.py -q
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "goa_caption_task", Path(__file__).with_name("goa_caption_task.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
compose_hint = _mod.compose_hint

BASE = "This track's genre is: goa trance and psytrance."
META = ("According to the actual ID3 metadata, this is the release year, label and genres of the "
        "track: release year: 1995; genres: Goa Trance.")


def test_both_present_composes_and_labels_source():
    text, src = compose_hint(BASE, META)
    assert text == f"{BASE} {META}"
    assert src == "per_track+global"


def test_metadata_does_not_replace_the_genre_hint():
    """The failure this composition exists to prevent: a track whose metadata carries a YEAR but no
    genre tags must still be told the corpus genre. If the map replaced the global hint, that track
    would go to Music Flamingo with an era and no genre — i.e. ungrounded on exactly the axis the
    hint exists to ground, on tracks that looked best covered."""
    year_only = ("According to the actual ID3 metadata, this is the release year, label and genres "
                 "of the track: release year: 2024.")
    text, src = compose_hint(BASE, year_only)
    assert "goa trance and psytrance" in text
    assert "2024" in text
    assert src == "per_track+global"


def test_no_metadata_falls_back_to_global():
    text, src = compose_hint(BASE, None)
    assert text == BASE
    assert src == "global"


def test_no_global_still_uses_metadata():
    text, src = compose_hint("", META)
    assert text == META
    assert src == "per_track"


def test_neither_yields_none_not_empty_string():
    """None (not "") so prompts_for() returns None and .analyze() falls through to prompt_type= —
    an empty-string prompt would OVERRIDE the default prompt with nothing."""
    assert compose_hint("", None) == (None, None)
    assert compose_hint(None, "") == (None, None)


def test_no_double_space_when_one_side_empty():
    text, _ = compose_hint(BASE, "")
    assert "  " not in text
