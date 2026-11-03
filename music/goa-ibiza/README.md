# goa-ibiza — early-Goa / Ibiza-trance loop engine + variations

GHOST-NOTE's music work (2026-07-02). A deterministic **style engine** that renders
1996-98-flavoured Goa/Ibiza-trance 8-bar loops (modal, hypnotic, bittersweet) as
multi-track MIDI, plus a live Bitwig-via-OSC play/record path and a set of generated
variations.

## Files

| File | What |
|---|---|
| `render_variation.py` | The style engine. Reads compact JSON specs and writes 7-track type-1 MIDI (Chords / Ostinato Lead / Wailing Backing / 303 / 909 Kit / Sub Bass / Kick), matching the reference-track layout. Idiomatic layers (octave-bounce bass, 16th-acid pedal, 909 groove, four-on-floor kick) are templates; the creative content (chords, ostinato cell + cadence variation, wail, root motion, energy) comes from the spec. |
| `play_ibiza_chords.py` | Live path: plays/records MIDI into Bitwig over OSC (Driven by Moss) via `mido` → ALSA `snd-virmidi`. Modes: `chords`, `lead`, `midi` (writes bar-perfect files). |
| `variations/var01..16_*.mid` | 16 variation loops spanning A/D/G/F♯ Dorian + B/C♯/D/E Aeolian, 126–138 BPM, intro→peak→breakdown→acid energies. |
| `variations/*_v2.mid` | Second-pass leads for each — regenerated with a named-field note schema and a drummer-logic groove brief (fixed cell + cadence-only variation). Keep both for A/B. |

## How the variations were made

A concept panel → per-variation composer → adversarial Goa-producer critic (multi-agent
workflow) produced the specs; the engine rendered them; each `.mid` was validated for
7-track / 8-bar structure and in-range pitches. The lead redo fixed a positional-tuple
ordering bug by switching to named fields `{b,d,p,v}` — see the GHOST-NOTE journal for the
finding.

## Provenance

Authored in-session against the WeModulate `bitwig-mcp-server` MCP integration (a
third-party clone); the engine and scripts are original and moved here to be versioned +
linkable. The musicological analysis of the reference loop lives in the session record.
