# Same-Chroma Steering — Review Demos (2026-06-18)

Training-free chroma steering of **SA3 medium-base** via a refit linear chroma
readout on SAME-L latents (the `same-chroma` work from `mir-feature-extraction`).
Run from the mir worktree; heads refit on 61 tracks of the **aavepyora 1999–2017
discography** (FLAC, fetched from archive.org).

## How these were made
- Readout refit (`sa3_refit_readout.py`, model `same-l`), held-out R²:
  bass **0.55**, mid **0.71**, treble **0.77**.
- Steering (`sa3_steer_chroma.py`, model `medium-base`), 50 steps, seed 1234,
  guidance config **mu=0.5, n-iter=8, frac=0.3** (the SA3-medium defaults of
  mu=0.03 are far too weak — pitch did not move until ~mu=0.5; consistent with
  MASTER.md "SA3-medium needs high guidance gain").
- Each preset = same seed, baseline vs steered.

## What to listen for
| File pair | Target | bass Δ | mid Δ | treble Δ | pitch-class result |
|---|---|---|---|---|---|
| `only-c__{baseline,steered}.wav` | all pitch → C | +0.152 | +0.051 | +0.082 | top PCs reshaped, C 4.2→5.42 |
| `goa-e__{baseline,steered}.wav` | E-phrygian + E bass | **+0.216** | +0.035 | −0.022 | `[D,A,F#,C,G]` → **`[E,B,D,G#,G]`** (E now dominant) |

`goa-e` is the clearest: the tonal center audibly/metrically shifts to **E**, the
intended root. `only-c` is the blunt "everything to C" stress test.

**The metric (chroma cosine alignment) is a sanity check — your ear is the gate.**
Does the steered take actually sit on the target pitch without sounding degraded?

`*_report.json` hold the full per-band numbers.
