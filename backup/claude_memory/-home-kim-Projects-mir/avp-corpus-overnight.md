---
name: avp-corpus-overnight
description: "Overnight MIR+augmentation run on Kim's own-music (avp) corpus, launched 2026-07-06 — mid-flight, resumable"
metadata: 
  node_type: memory
  type: project
  originSessionId: 59a68846-fc80-40ca-8060-59dc171ea761
---

Kim's own music (Aavepyörä/Summamutikka) is being prepped as a personal-style LoRA
conditioning corpus. Launched 2026-07-06 ~03:07 (overnight, token-limited), **resumable,
spills into 07-07**. Drive: `/run/media/kim/9a410a1d-a4a8-4faf-8298-bcaa2576ea9d` (UUID
drive, 2.4 TB free), kept separate from Goa per the data-layout rule.

**Full handoff:** `<UUIDdrive>/avp-analyzed/_STATUS.md` — read it first.

- **Sources:** `avp-flac` (313 tracks, long ~5–9 min) + `avp-stems` (40 tracks, richly-named production stems).
- **A — pipeline:** `config/avp_pipeline.yaml` (flamingo OFF, metadata OFF, BS-Roformer, crop 11.9 s default) → `avp-analyzed`. Re-run same cmd to resume. Log `_pipeline.log`.
- **B — augmentation:** `src/tools/augment_tracks.py --watch` (nice/idle, bungee→**rubberband** in mir venv). 9 variants/track: pitch {−2,−1,+1,+2} st + **tempo as absolute BPM offsets** {−10,−5,+5,+10,+15}. Log `_augment.log`. `--watch` loops forever → kill when done.
- **A2 — caption:** `src/tools/inject_trigger_caption.py` writes `aavepyora`/`aavepyörä` 50/50 (deterministic per track). Run after crops exist. **TODO: confirm the exact prompt field the SA3/SAT encoder reads.**
- **C — stems → GHOST-NOTE:** classify 40 stem folders by filename into 9 categories (kick/drums/bass/acid/leads/arp+keys/pads+strings+atmospheres/sfx/speech) + per-category downmix + manifest, non-destructive.
- **D (pending):** crop augmented tracks; validate derive-vs-reanalysis metadata on ~50; add **384-width chroma** (chroma.py is 12-bin today).
- **E (pending):** stem chromas (bass/pads/keys/synth) + rest of per-stem features on the 40 real-stem tracks.

Infra: **Mantu remounted as `Mantu1`** 2026-07-06 (old sdc1 dead). Doesn't affect this run.
See also [[sa3-riffer-findings]] (E_fusion_v2 = simplest cell won: baseline FusionOpt onset-density adapter, LatCH off, no meter/genre — emergent spectral-balance, 95 s crops preserve structure).
