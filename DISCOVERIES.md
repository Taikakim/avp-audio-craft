# DISCOVERIES — the "have we already figured this out / built this?" index

*The discovery-phase search target (CLAUDE.md ⛔ DISCOVERY PHASE). Regenerated
wholesale from `profiles/*.journal.md` by `Misc/build_discoveries.py` — do NOT
hand-edit below this point, it will be overwritten on the next run. To fix a
misfiled entry, edit the TOPICS keyword map in that script, not this file. To
add a finding, drop a journal line in your own journal; re-run the script.*

**Owner: THE-FINN.** Topic assignment is a keyword heuristic, not semantic
understanding — it will occasionally misfile something. `[RULED OUT]` = a
negative result (a path already tried and abandoned — first-class, not noise).

*54 entries from 4 journals.*

---

## Long-form generation · transitions · crossfade
- [reuse] **longform generation ALREADY IS the crossfade/transition solution (SDEdit) — a night lost re-deriving it.** → `stable-audio-3/stable_audio_3/inference/longform.py`, `stable-audio-3/docs/superpowers/specs/2026-06-19-longform-sdedit-reanchor-crossfade-design.md`, `control/sa3_control/steered_longform.py`, `mir/scripts/latent_server.py`, `mir/scripts/latent_crossfader.py` — CONTINUITY, 2026-07-06
- [ruled out] **layer-activation crossfade between two seeds — off-manifold artifacts.** → `onnx/steered_layer_crossfade.py` — CONTINUITY, 2026-07-06
- [tool] **on-manifold beat-aligned bridge experiments (audio-space).** → `onnx/beat_bridge.py`, `onnx/bridge_crossfade.py` — CONTINUITY, 2026-07-06

## Control adapters · FusionCC · guidance
- **novelty verdicts resolved — three contributions survive external + adversarial review.** — CONTINUITY, 2026-07-03
- **perfect meter, dead steering wheel — the mechanism of the dead walkers.** — CONTINUITY, 2026-07-03
- [RULED OUT] **onset_envelope head does NOT walk on the composed path (calibration probe).** — CONTINUITY, 2026-07-03
- [RULED OUT] **the recipe's boundary — meter-in-the-gradient needs a BLIND loss.** — CONTINUITY, 2026-07-03
- [RULED OUT] **meter-in-the-gradient does NOT transfer from onset to genre.** — WINTERMUTE, 2026-07-03
- **the consistency-loss neighbourhood, deep-read.** — THE-FINN, 2026-07-03
- **ES v3 fresh-seed verdict — mechanism proven, effect modest.** — CONTINUITY, 2026-07-02
- **FusionCC — the meter inside the gradient bites.** — CONTINUITY, 2026-07-02
- **NS5 destroys per-coordinate gradient sign structure.** — CONTINUITY, 2026-07-02
- **the hidden +37% — cautious rescale norm inflation.** → `1/keep_frac`, `1/sqrt(keep)` — CONTINUITY, 2026-07-02
- [tool] **the perceptual-signal quartet.** → `sa3_control/cc_probe.py`, `es_conditioner.py`, `training/sonar.py` — CONTINUITY, 2026-07-02
- **cautious masking is a quality trade, not a win — a four-instrument null.** — CONTINUITY, 2026-07-01
- **the 6–9 onsets/s saturation band is optimizer-independent.** — CONTINUITY, 2026-07-01
- **the onset-authority metric is gameable.** — CONTINUITY, 2026-07-01
- [session] **the night the thread started.** — CONTINUITY, 2026-06-30

## Evolutionary strategies · weight-trajectory search (ES)
- **the heard landscape, photographed — mapper × ES first contact.** — CONTINUITY, 2026-07-03
- **field-guided jump — walk direction transfers, fine relief doesn't.** — CONTINUITY, 2026-07-03
- **the ep5 triple convergence.** — CONTINUITY, 2026-07-02
- **a 119.6M-param run's trajectory is genuinely planar.** — CONTINUITY, 2026-07-02
- [RULED OUT] **ES v1 — σ calibrated against the weights, not the measurement.** — CONTINUITY, 2026-07-02
- [RULED OUT] **ES v2 — dimension eats global norms.** — CONTINUITY, 2026-07-02

## LatCH · probing · layer-feature mapping
- [tool] **layer x feature encodability-map scaffold.** → `latch/probe_layer_feature_map.py`, `*.TIMESERIES.npz` — CONTINUITY, 2026-07-05
- **four knobs at once — the full instrument composes, with measurable cross-talk.** — CONTINUITY, 2026-07-04
- **the SA3 LatCH head sweep — operating gain is ≈512, not 48–96.** — WINTERMUTE, 2026-06-28

## Weight garden · model mutation
- **weight garden: the mutation that never was.** → `stable-audio-3/scripts/weight_mutations.py`, `mutate_weights.py` — CONTINUITY, 2026-07-04

## Style/genre adapters · fingerprint conditioning
- **the style adapter steers genre — fpC wins, and it's corpus-limited.** — WINTERMUTE, 2026-07-03
- **the confound I almost shipped — minority-genre nulls aren't adapter failure.** — WINTERMUTE, 2026-07-03
- [fix] **the silence.npy dataloader crash (clean root cause).** → `silence.TIMESERIES.npz`, `.json`, `.npz` — WINTERMUTE, 2026-07-03
- **genre-conditioned SA3 style adapter (design → tested plumbing).** → `.json` — WINTERMUTE, 2026-07-02
- **the discogs-400 genre head is multi-label, not softmax.** — WINTERMUTE, 2026-07-02

## Captions · conditioning · training data
- [tool] **tiered caption system + multi-source train_lora.** → `stable-audio-3/scripts/caption_tools.py`, `stable-audio-3/scripts/train_lora.py`, `mir/data/feature_tables/flamingo_budget.json`, `docs/prompting-conditioning-plan.md` — CONTINUITY, 2026-07-05

## Evals · metrics · benchmarking pitfalls
- [tool] **the fleet's public face — private repos, zero-token dialogue, eval GUIs.** — WINTERMUTE, 2026-07-03
- **SA3 inference speed shootout — corrected my own soft numbers.** — WINTERMUTE, 2026-07-02
- [RULED OUT] **cross-optimizer soup blend ratio as a quality lever.** — CONTINUITY, 2026-07-01
- [RULED OUT] **chroma correlation is a mode-collapse trap — it declared wins twice.** — WINTERMUTE, 2026-06-19

## Data pipeline · corpus prep · augmentation
- **avp personal-corpus prep + the whole-track paradigm (reuse, don't re-cut).** → `.../avp-analyzed`, `mir/src/spectral/whole_track_timeseries.py`, `.TIMESERIES.npz`, `stable-audio-tools/scripts/whole_track_target_source.py`, `relative_position_start/end`, `mir/src/tools/augment_tracks.py`, `mir/src/tools/inject_trigger_caption.py` — WINTERMUTE, 2026-07-06
- [RULED OUT] **the ±16 BPM augmentation is too mild to disentangle — caught before the full run.** — WINTERMUTE, 2026-06-26

## Fleet process · dialogue protocol · presence
- **orientation audit — 24 confirmed inconsistencies on day one.** — THE-FINN, 2026-07-03
- [correction] **the cold case was already closed — by the repo, not by us.** — THE-FINN, 2026-07-03
- [note] **joined; the liturgy is archived.** — THE-FINN, 2026-07-03
- [tool] **the dialogue protocol + rule 6.** — CONTINUITY, 2026-07-02
- [infra] **cross-instance hardening (edge cases).** → `CLAUDE.md` — WINTERMUTE, 2026-07-02
- [tool] **`wait`: the exit IS the wake.** — GHOST-NOTE, 2026-07-02
- **roles move the voices.** — GHOST-NOTE, 2026-07-02

## Bitwig · OSC music production
- [session] **sixteen early-Goa loops, rebuilt until they breathed.** — GHOST-NOTE, 2026-07-02
- [RULED OUT] **OSC recording needs punch-in ordering.** → `/record`, `/play`, `/restart` — GHOST-NOTE, 2026-07-02
- **named-field schemas beat positional tuples.** — GHOST-NOTE, 2026-07-02
- [RULED OUT] **Bitwig calls middle C "C3".** — GHOST-NOTE, 2026-07-02

## Infra gotchas · venvs · ROCm/CK · storage
- [note] **torch 2.14 alpha is SLOWER than torch 2.10+CK for SA3 training.** → `SAO/.venv`, `stable-audio-3/.venv` — CONTINUITY, 2026-07-05
- **gfx1201 ROCm nightlies are the clean path.** — GHOST-NOTE, 2026-07-02

## Uncategorized · recent
- [session] **the cautious A/B campaign, end to end.** — CONTINUITY, 2026-07-01
