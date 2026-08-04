"""chroma_steer_targets.py — the harmonic-target + prompt library for the extended
chroma-steering eval page (Kim ask 2026-07-19: "extend the chroma steering page — add
solo instruments per the SA3 prompting guide, try turning chord progressions between
colours/keys, expand the examples, tabs for every chroma steering model we have").

This module is the SHARED CONTRACT between the renderer (eval/chroma_steer_render.py)
and the page builder — both import PROMPTS / TARGETS / MODELS from here so the clip
filenames, tabs, and explainer text can never drift out of sync.

Design anchors (verified against code + docs, 2026-07-19):
  * Engine reuse: chord progressions are built with control/sa3_control/
    chroma_guided_generator.py's chord_to_chroma / parse_progression / ChromaSchedule
    (chord names + pc-sets resolve correctly; roman numerals are NOT used — they mis-
    resolved by a semitone in a 2026-07-19 CPU check, so every target here is spelled
    with explicit chord names / pitch-class sets).
  * The chroma-trap (MASTER §5 / sa3-riffer-findings): absolute chroma similarity is
    meaningless on tonal music — everything correlates. Every metric downstream is
    Δ-vs-baseline (same seed, gain 0). Targets here carry the baseline pairing implicitly
    (gain 0 in the gain ladder).
  * Models = the chroma steering heads we actually have (see MODELS): the 12-d `hpcp`
    head (the natural chord-progression driver — its "dead at any weight" label in
    MASTER §5 came from an ENERGY-focused MERT-mid sweep blind to harmonic motion, so
    this page is also its first fair harmonic test), the 384-d 3-band `same_chroma`
    head, and the older stem `chroma_other` head.

Pure-Python + numpy only (no torch); the renderer adds the GPU pieces.
"""
from __future__ import annotations

# ── Solo-instrument prompts, per stable-audio-3/docs/guides/prompting.md ──────────────
# The guide's Stem/Solo recipe: lead with `TrackType: Instrument` to isolate one voice,
# then instrument + genre/context + mood. A solo, monophonic-ish line is the CLEAN test
# bed for pitch steering — far more legible than the dense goa mix, where "did the notes
# move?" is hard to hear. Contexts are chosen to be pitch-forward (melody/harmony
# carrying), not percussive.
SOLO_INSTRUMENTS: list[dict] = [
    {"id": "piano",   "text": "TrackType: Instrument, a solo grand piano playing a "
                              "reflective, melodic progression, intimate close-mic recording"},
    {"id": "guitar",  "text": "TrackType: Instrument, a sombre solo acoustic guitar with "
                              "delicate finger picking and cavernous reverb"},
    {"id": "eguitar", "text": "TrackType: Instrument, an expressive solo electric guitar "
                              "playing legato melodic phrases, live-recorded in a vintage studio"},
    {"id": "violin",  "text": "TrackType: Instrument, a solo violin playing a lyrical, "
                              "singing melodic line with warm vibrato"},
    {"id": "cello",   "text": "TrackType: Instrument, a solo cello playing a slow, "
                              "resonant melodic passage, rich and woody"},
    {"id": "flute",   "text": "TrackType: Instrument, a solo concert flute playing an "
                              "airy, flowing melody"},
    {"id": "sax",     "text": "TrackType: Instrument, a solo tenor saxophone playing a "
                              "smoky, expressive jazz melody"},
    {"id": "synth",   "text": "TrackType: Instrument, a solo analog synth lead playing a "
                              "hypnotic arpeggiated melodic line"},
    {"id": "harp",    "text": "TrackType: Instrument, a solo concert harp playing gentle "
                              "rolling arpeggios"},
    {"id": "organ",   "text": "TrackType: Instrument, a solo church pipe organ sustaining "
                              "a slow, majestic chord progression"},
]

# The two full-mix prompts the ORIGINAL page tested — kept so the extension is a superset,
# not a replacement (the guitar-vs-goa disentanglement read stays visible).
FULLMIX_PROMPTS: list[dict] = [
    {"id": "goa",    "text": "melodic goa trance, hypnotic arpeggiated lead, driving "
                            "rolling bassline"},
    {"id": "guitarq", "text": "steel string guitar finger picking solo"},
]

ALL_PROMPTS: list[dict] = SOLO_INSTRUMENTS + FULLMIX_PROMPTS


# ── Harmonic targets ─────────────────────────────────────────────────────────────────
# kind:
#   "static"      -> hold one key/colour for the whole clip (the T2 12-TET target)
#   "progression" -> chord progression as a '|'-schedule "t0:C0|t1:C1|..." (seconds).
#                    This is Kim's "turning chord progressions between colours/keys":
#                    the target MOVES per window, so the generation's harmony develops.
# Every chord is spelled with explicit names / pc-sets (roman numerals avoided — see
# module docstring). Progression times assume a ~20 s clip.
TARGETS: list[dict] = [
    # — static keys / colours (T2): the minimal "steer to one place" test —
    {"id": "C",       "kind": "static", "chord": "C",
     "label": "hold C major", "family": "key"},
    {"id": "Am",      "kind": "static", "chord": "Am",
     "label": "hold A minor", "family": "key"},
    {"id": "Fsharpm", "kind": "static", "chord": "F#m",
     "label": "hold F# minor (far from C)", "family": "key"},
    {"id": "Ephry",   "kind": "static", "chord": "0,4,5,7,9,11,2",
     "label": "E phrygian colour (the goa palette)", "family": "colour"},

    # — chord progressions BETWEEN colours/keys (T4): the headline new capability —
    {"id": "i-VI-III-VII", "kind": "progression",
     "prog": "0:Am|5:F|10:C|15:G",
     "label": "Am → F → C → G  (classic minor-key turn)", "family": "progression"},
    {"id": "keylift", "kind": "progression",
     "prog": "0:C|7:Eb|14:F#",
     "label": "key-lift C → Eb → F#  (rising minor-thirds, modulating)",
     "family": "progression"},
    {"id": "colourmorph", "kind": "progression",
     "prog": "0:0,4,5,7,9,11,2|10:C",
     "label": "colour-morph  E phrygian (goa) → C major  (dark → bright)",
     "family": "progression"},
    {"id": "circle", "kind": "progression",
     "prog": "0:Am|5:Dm|10:G|15:C",
     "label": "Am → Dm → G → C  (ii-V-I resolution into C)", "family": "progression"},
]

# ── The chroma steering heads = the page's TABS ──────────────────────────────────────
# Each head is a separate steering MODEL; the page gets one tab per entry. `dim` sets
# which render path the harness uses (12-d hpcp = ChromaGuidedGenerator; 384-d = the
# same_chroma 3-band latch-guided path). `note` is the plain-language "what this is" for
# the per-tab explainer (three-audience standard, CLAUDE.md).
MODELS: list[dict] = [
    {"id": "hpcp", "ckpt": "latch_sa3_hpcp_best.pt", "dim": 12,
     "label": "HPCP (12-d)",
     "note": "The classic 12-bin chroma head — one weight per pitch class. It is the "
             "natural driver for chord progressions (12 knobs = the UX). Its earlier "
             "'dead' verdict came from an energy-focused sweep that could not see "
             "harmonic motion; this is its first fair harmonic test."},
    {"id": "same_chroma", "ckpt": "latch_sa3_same_chroma_best.pt", "dim": 384,
     "label": "SAME-chroma (384-d, 3-band)",
     "note": "The richer head: pitch class × 3 register bands (bass / mid / treble), "
             "128 bins each. Steers bass and melody registers independently — the head "
             "behind the 'coolest thing I've heard' chroma-morph transitions."},
    {"id": "chroma_other", "ckpt": "latch_sa3_chroma_other_best.pt", "dim": 384,
     "label": "stem-chroma (other-stem)",
     "note": "The earlier stem-chroma head, trained on the non-drum 'other' stem. Kept "
             "as a comparison point against SAME-chroma on the same targets."},
]

# Gain ladder — matches the ORIGINAL chroma_steer.html (0 = unguided baseline, then the
# SA3-medium LatCH operating band). 0 must stay first: it is the Δ-vs-baseline anchor.
GAIN_LADDER: list[int] = [0, 512, 1024, 2048]

# Seeds — a few per (model, prompt, target) so a win isn't one lucky draw.
SEEDS: list[int] = [1234, 5678, 9012]


def clip_name(model: str, prompt: str, target: str, gain: int, seed: int) -> str:
    """Builder-parseable clip filename. Kept flat + delimiter-safe (no dots in fields)."""
    g = "base" if gain == 0 else f"g{int(gain)}"
    return f"{model}__{prompt}__{target}__{g}__s{seed}.mp3"


if __name__ == "__main__":  # tiny self-report (no torch)
    print(f"{len(ALL_PROMPTS)} prompts ({len(SOLO_INSTRUMENTS)} solo instruments), "
          f"{len(TARGETS)} targets "
          f"({sum(t['kind']=='progression' for t in TARGETS)} progressions), "
          f"{len(MODELS)} models, gains {GAIN_LADDER}, {len(SEEDS)} seeds")
    print("example clip:", clip_name("hpcp", "violin", "keylift", 1024, 1234))
