# OWNERSHIP — one agent per subject

*Kim, 2026-10-07: "we should have an ownership.md where agents take ownership of subjects so one agent
preferably works with any single one. I believe this might run smoother."*

**Why.** The same subject kept being worked by two agents at once (H4 knob directions, the DJ mixtape, the
model matrix), which means duplicated discovery, crossed edits and results that live in two journals. One
owner per subject keeps the thread, the data and the open questions in one head.

## Rules

1. **One owner per subject.** The owner does the experiments, edits the code and docs, and posts the
   findings (chat summary + journal + WORKLOG, per the post-task protocol). Everyone else may *read* and
   *analyse*, but a change or a new experiment on someone's subject goes to the owner by DM, or into their
   queue, instead of being started in parallel.
2. **Claiming = adding a row** (or changing "proposed" to "claimed" with your handle and the date). Kim can
   override any row. If two agents want a subject, post both claims in the chat and Kim decides.
3. **Handoff = edit the row** with the date and the reason; the old owner leaves a one-line state-of-play in
   the new owner's DM. Never leave a subject silently ownerless: if you stop working on one, say so here.
4. **Cross-subject work** (an analysis on someone else's data) is fine as a *service*: ask, deliver, and the
   owner records the result in their lane. The service giver does not open a parallel thread.
5. **Status column:** *claimed* = the owner said so; *proposed* = filled in from the documented lanes
   (`CONSTRUCTS.md`, `MASTER.md` §4, the skills) and from who actually did the last work. A proposed owner
   confirms or amends it the next time they read this file. THE-FINN's patrol checks the table for drift.
6. Keep it short: a subject is one line. Depth lives in the linked doc.

## Subjects

| Subject | Owner | Status | Backup / services | Where it lives |
|---|---|---|---|---|
| Optimizers and training recipes (ModularOptimizer, LoRA-TSD, AdaGC, Lion), training-failure postmortems | CONTINUITY | claimed 2026-10-07 | | `docs/training-findings.md`, `docs/train_lora_modular.md`, skill `sa3-training` |
| LatCH heads and the FiLM adapter under the modular optimizer (E5), density targets, noise-floor audits | CONTINUITY | claimed 2026-10-07 | W for mir targets | `EXPERIMENTS.md` E5, `latch/`, Mantu `latch_sweep/` |
| Epoch soups, ladder analytics, checkpoint trajectory forensics | CONTINUITY | claimed 2026-10-07 | | `eval/ladder_*`, `checkpoint-stats/` |
| Synth inversion (Surge XT, Synth-JEPA / Synth-JDF line, H1-H3, H5-H9) and Ben Hayes' suggestions | WINTERMUTE | claimed 2026-10-07 (Kim: "direct it to W") | C: CPU-side analysis on request | `EXPERIMENTS.md` H-series, `stable-audio-tools/scripts/synth_inversion/` |
| Synth knob directions in SAME latent space (H4) | WINTERMUTE | proposed | C supplied the ridge / transfer analyses and keeps them as a service | `EXPERIMENTS.md` H4, `eval/h4_*.py` |
| Latent Forge (GUI, worktree `sa3-studio-review`) | WINTERMUTE | claimed | C re-drives GUI tests on request | `ARCHITECTURE.md`, branch `latent-forge` |
| Kim's website, hosting, publish pipeline, leak-scan, `ratings.php` | WINTERMUTE | claimed (`CONSTRUCTS.md`) | everyone stages, W publishes | `MASTER.md` §4, `web/` |
| Audio-feature subsystem, training data, precalculated latents (mir, `docs/data.md`) | WINTERMUTE | claimed (`CONSTRUCTS.md`) | | `docs/data.md`, `mir/` |
| DJ mixtape pipeline (clips -> BPM -> bounds -> crossfade -> mix -> Kone page) | GHOST-NOTE | proposed: G built v1-v5; C rebuilt v6 on Kim's ask and hands it back | C for latent / decode questions; v7 waits for Kim's taps | `eval/mixtape_*`, `eval/chain_simple_crossfade.py`, `eval/build_dj_mixes_section.py`, Mantu `mixtape_v6_rerender/run_meta.json` |
| Model matrix, canonical clips, eval boards and tables | GHOST-NOTE | proposed | W deploys the pages | skill `sa3-canonical-clips`, `eval/model_matrix_gen.py` |
| LUMI operations (submit, monitor, pull, render) | GHOST-NOTE | proposed (`lumi-ops` skill: daily runs moved to G 2026-08-10) | C / W craft the configs | skill `lumi-ops`, `RUNBOOK.md` |
| Bitwig and other external software / services (except the website) | GHOST-NOTE | claimed (`CONSTRUCTS.md`) | | `CONSTRUCTS.md` |
| Papers: reading, verdicts, `papers/knowledge.md`, the verdict page | THE-FINN | claimed 2026-10-07 | W deploys the verdict page | `papers/`, `Misc/build_paper_verdicts.py` |
| Fleet comms, staleness patrol, doc-index health (`ARCHITECTURE.md`, `DISCOVERIES.md`, this file) | THE-FINN | claimed (`CONSTRUCTS.md`) | | `CONSTRUCTS.md`, `MASTER.md` §4 |
| Melody-subspace loss and the `sa3_control` adapters | *unclaimed* | | | `control/`, `EXPERIMENTS.md` |
| SA3 ONNX suite, SAME-S export | *unclaimed* | | | `onnx/` |

## Handoff log

- 2026-10-07 — file created by CONTINUITY at Kim's request; Synth-JEPA / Ben's suggestions routed to
  WINTERMUTE (DM). Proposed rows await their owners' confirmation.
