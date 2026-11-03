---
name: goa-corpus-quality-flac-plan
description: Big-FT corpus is MP3 now; planned FLAC re-source + ~1000 handpicked favorites as a later higher-quality pass
metadata: 
  node_type: memory
  type: project
  originSessionId: 49cd5391-27e7-4545-8295-a1053db2a077
  modified: 2026-08-04T21:23:28.170Z
---

The #68 big-FT trains on the **goa_archive MP3 keep-set** (12,523 tracks, `encode_ok`). That keep-set is **100% A+B tier** (4,058 near-lossless + 8,465 at 256–320k) — the `encode_ok` curation already dropped ALL the C_~192k (2,138) + D_≤128k (1,259) low-bitrate lossy tracks, so no degraded sources are in training.

**Plan (Kim, 2026-08-04):** initial runs on MP3 are fine; **after them, do a higher-quality pass that replaces MP3 with FLAC.**
- **FLAC provenance (Mantu/ai-music), clarified by Kim 2026-08-05:**
  - `Goa Dataset` (~2,873 FLAC + 782 mp3, `goa/`+`goa-unsorted/`), `Full-on, Psytrance` (1,180), `Prog & Psytechno` (1,445), `Progressive Trance` (866), etc. = **pulled from TIDAL** → *genuine lossless FLAC* (not FLAC-from-MP3), accumulated as backup breadth for the good datasets + control-head training.
  - `Goa_Separated` (~17,707 FLAC) = a **Demucs STEMS corpus** (bass/drums/vocals/other + `full_mix.flac` for ~3,150); provenance MIXED (some full_mix rolled off ~13–19 kHz → possibly lossy-origin) — NOT a trustworthy lossless ref without per-track spectral verification.
  - **The PRIZED old collection** (purchase-curated by what Kim bought over the years, clarified 2026-08-05) contains TWO distinct things, don't conflate: (i) his **~1k individually hand-picked favourites — mostly OGG = LOSSY** (an *aesthetic/curation* asset — the hand-selection is the signal — NOT a lossless-audio source); (ii) his **CD rips** (ripped from his own CDs before selling them) = the genuine **lossless personal** source. Likely OVERLAP between the favourites and the CD rips. **Location TBD** (disconnected drive / somewhere on Mantu; tracklist not preserved).
  - **Production strategy corollary:** use the favourites *tracklist* as the curation prior, but SOURCE those tracks from lossless (CD rips where they overlap, Tidal FLAC otherwise) — don't train on the OGG audio if quality is the goal. Curation (which tracks) and audio-quality (from where) are separate levers.
- **For the BITRATE TEST**: Tidal `Goa Dataset` FLAC is a valid genuine-lossless reference — no track/caption matching needed (bitrate is the isolated variable; use a consistent generic caption across arms). Provenance scan running on it (distinguish MP3-brickwall from genuinely-dark psytrance).

**Gating decision — RESOLVED 2026-08-04** by `eval/mp3_latent_sensitivity.py` (15 Goa full-mix FLACs → MP3 @320/256/192/128k → SAME encode; outputs `Mantu/sa3_control_runs/analysis/mp3_latent_sensitivity_2026-08-04/`):
- The SAME encode does **NOT** swamp MP3 (my earlier claim was wrong — monotonic Δ, no invisibility floor). BUT the perturbation is **diffuse, melody-NEUTRAL fidelity noise** (melody-fraction 0.07–0.10 ≈ random 0.059), not musical corruption.
- Magnitude vs a single-note (fifth-jump) Δlatent: 320k **0.22×**, 256k **0.35×** (med 0.25×), 192k **0.49×**, 128k **0.74×**. So the artifact reaches musically-relevant scale only at **≤192k**.
- **Verdict:** re-sourcing already-256k+ tracks from FLAC is **low-value** (sub-note, melody-neutral). The real lever is a **bitrate floor ≤192k** — which the big-FT ALREADY enforces (encode_ok dropped all C_~192k + D_≤128k; keep-set is 100% A+B ≥256k). So a future FLAC pass is justified **only** by (a) the ~1000 missing hand-picked favourites and (b) any Goa_Separated tracks absent from the new set — NOT by the quality of existing 256k+ tracks. Dense/HF-rich mixes perturb 3–5× more than sparse ones; melody subspace is not specifically hit.
