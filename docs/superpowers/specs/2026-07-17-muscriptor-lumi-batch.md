# MuScriptor full-corpus transcription — LUMI batch spec (WINTERMUTE, 2026-07-17)

*(Kim direct: "Run on LUMI definitely — a beautiful pile of data… if audio is needed, we
can just on-the-fly decode latents?" Answer: yes, and it kills the transfer problem.)*

## Purpose
Full-corpus MIDI transcription + musicology structure (sections, riffs, harmony) over the
SA3 training crops — the label source for section-conditioning (`section_ts` v2 character
labels), corpus-wide musicology, and future harmonic work. Local sample (160 tracks,
median 80 s/track GPU) already validated the transcriber.

## Data — NO new transfer needed
- **Audio source = SAME-decode of `latents_sa3` crops, on the fly** (Kim's call):
  `/data/latents_sa3` is ALREADY staged on LUMI (throughput guide §"~13 GB latents_sa3");
  each task decodes its crop batch through the SA3 pretransform (fast, same container)
  and transcribes the 380 s reconstruction.
- Labels land **aligned to the exact latents the model trains on** — for conditioning
  purposes this is arguably better than original-audio labels.
- Outputs come home small: ~0.1–0.5 MB MIDI + stats per crop ≈ ~2 GB total; the
  musicology structure pass runs LOCALLY on CPU afterwards (existing pipeline).

## GATE before spending node-hours (local, ~1 evening, REQUIRED)
Transcribing SAME *reconstructions* is the one epistemic risk. Validation: pick ~20 tracks
from the existing MuScriptor sample, decode their latents locally, transcribe the decode,
compare vs the original-audio transcription: note-level agreement (onset/pitch F-ish),
notes/sec delta, and **section-boundary agreement after the musicology pass** (the label
we actually want). Pass ⇒ proceed; material degradation ⇒ fallback = one-time transfer of
128 kbps m4a (~40 GB) instead — still no flac-scale transfer.

## Orchestration (per C's lumi-throughput-workflow-guide)
- **HyperQueue task array** inside one allocation, chunks of ~50 crops/task; model loads
  once per task (the local runner's pattern — `eval/muscriptor_batch_goa.py` is the port
  base, swapping file-read for latent-decode).
- Container: `sa3-train.sif` + MuScriptor pip-installed from the repo
  (`/home/kim/Projects/muscriptor` — pure-python package + weights; add to the image or
  bind-mount + `pip install -e` in-task).
- Node-local staging of the latent shard per node (guide §"stage once per node, not once
  per task"); write MIDIs to `/flash`, sync to `/scratch` at task end.
- Resumable by construction (skip existing `.mid`) — the local runner already does this.

## Cost
~90 s/crop (80 s transcribe + ~10 s decode) × 5401 crops ≈ **135 GCD-hours**; at 64
concurrent GCD-tasks ≈ **~2 h wall**. Small-node-hours job; queue behind Kim's fp32
campaign + task-50 arms per the standing order.

## Outputs
`/scratch/.../muscriptor_full/<crop>.mid + .stats.json` → rsync home →
`Mantu/sa3_lora_runs/muscriptor_full/` + local musicology pass → structure blocks
(n_sections, section_lens_bars, riffs, keys) per crop → `section_ts` v2 (type/character
labels) + corpus musicology upgrade (G's page goes 5% → 100%).

## Relation to the free road (independent, already in flight)
Foote/novelty segmentation on the 100 Hz whole-track timeseries provides section
BOUNDARIES + energy arcs corpus-wide on CPU without any of this — the v1 training signal
for the section adapter. This batch adds section CHARACTER and full transcription. The
two meet in the validation: MuScriptor-derived boundaries on the 160-track sample grade
the Foote segmentation.
