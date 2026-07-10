# MEMO — the rarity-set extension is the right FIRST REAL LUMI JOB

*2026-07-10, WINTERMUTE (Kim's call, via chat: "this is a big run, so reserve some time
in a suitable slot… write a memo that this is a good initial simple Lumi job").*

## The job

Extend `rarity_gen_set` (currently 450 clips: {base, evr1x, newstack} × 150 stratified
prompts, steps 24 / cfg 6 / 20 s / unique seed per clip) along three axes Kim specified:

- **DoRA weight:** 1.33 in addition to 1.0 (adapter models only; `set_lora_strength` is a
  live knob, no retrain)
- **CFG:** 1 and 16 in addition to 6 (the absorption-crossover bracket — cfg 1 = "play the
  absorbed style", 16 = "obey the prompt", cf. CFG_ANALYSIS)
- **Prompts:** RICH prompts per seed, picked from the existing Granite tier sidecars,
  instead of / alongside the short stratified captions

Grid: base × 3 cfg + 2 adapters × 2 weights × 3 cfg = **15 model-variants × 150
(strata × prompts × seeds) ≈ 2 250 clips** (~4–5 local GPU-hours; embarrassing to
carry locally next to the training queue — perfect fan-out fodder instead).

## Why it's the ideal first LUMI job (after hello-world)

1. **Inference-only.** No training state, no optimizer, no LR schedule to get wrong on
   new hardware — just load → generate → decode → write. The failure modes are all
   environmental (container, ROCm, weights staging), which is exactly what a first job
   should surface.
2. **Embarrassingly parallel.** 15 model-variants shard cleanly across GCDs (8/node);
   each shard is an independent 150-clip loop with skip-if-exists resume. One node,
   one workflow, done in ~an hour of wall-clock; also solves the standard-g
   whole-node-billing caveat honestly by PACKING all 8 GCDs.
3. **Tests the full stack at scale, zero risk.** Container build (sa3-env), weights +
   T5-Gemma staging into `/project`, `/scratch` output, the EFP WebUI job-script →
   workflow flow — everything the LatCH/DoRA campaigns need, validated on a job whose
   worst case is "some wavs missing, resubmit".
4. **The output is small and the value is immediate.** ~2 250 × 20 s wavs ≈ a few GB back
   to the box; rarity-lite scoring (mir venv, CPU, local) + the new columns board give
   Kim a listenable, scored deliverable from LUMI run #1.
5. **Budget-trivial.** ~8–10 GCD-hours of the 5 000 — a rounding error that buys the
   entire operational path for the real campaigns.

## What it needs (prep checklist, mostly already in the bundle)

- [ ] hello-world green via the EFP WebUI first (blocked on the Create-Jobscript form
      walkthrough with Kim)
- [ ] `sa3-train.sif` built (cotainr, Day-1 step 2 — same container serves inference)
- [ ] Staged to `/project`: medium-base weights, T5-Gemma cache (`HF_HUB_DISABLE_XET=1`),
      evr1x + newstack adapter checkpoints (small), Granite prompt sidecars (KBs)
- [ ] A render script = the existing rarity_gen loop + `--source/--weight/--cfg/--shard`
      args (C owns the generator; the loop already exists — this is arg-plumbing)
- [ ] Job script body: 8 `srun` shards (one per GCD, `HIP_VISIBLE_DEVICES=$i`), each
      skip-if-exists; registered as an EFP Job Script, partition standard-g
- [ ] `run_meta.json` sidecar per the provenance convention, written by the script

## Presentation (lands with the local follow-through)

The board reorg Kim specified: **columns = models (+base) with identical settings
stacked vertically; delta-to-base columns** (per-clip rarity-lite deltas once C's
scoring pass runs over the extension). G owns the board build; the delta columns
depend on the scoring, not the render.
