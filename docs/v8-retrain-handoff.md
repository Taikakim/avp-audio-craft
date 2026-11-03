# V8 retrain: step-by-step handoff

Owner of the line: WINTERMUTE (2026-11-03). Written so a fast model can run it exactly, with no decisions to make.
Why it exists: KUANG's review (`docs/synth-v8-code-review-2026-10-29.md`) found no V8 result counts as evidence. The code fixes are in. The retrain has not been done.

## Rules

1. **Run only the commands below, in this order, one at a time.** Each prints `PASS [stage]` or `STOP [stage]`.
2. **On `STOP`, stop.** Do not edit code, change a setting, retry, or try another approach. Report the `STOP` line and the last 30 lines of the log it names.
3. **A failed gate is a result, not a bug.** Do not retrain to make a gate pass.
4. **Do not edit any `.py` or `.sh` file.** If something looks wrong, say so and stop.
5. **Do not publish anything, and do not post to `AGENT_DIALOGUE.md` or DM logs.** WINTERMUTE reviews and publishes.
6. **Do not write words like "beat", "surpass" or "overwhelming" about results.** Report the numbers the stage prints.
7. **Do not touch `RENDER_CHECK_APPROVED`.** A person creates it after listening.
8. Do not set `PYTORCH_CUDA_ALLOC_CONF`. The runner clears it. It writes wrong audio on ROCm.
9. The runner takes the GPU lock itself and waits if someone else holds it. Waiting is normal. Do not kill anyone's job.

## Commands

Run from any directory. `R` is the runner:

```bash
R=/home/kim/Projects/SAO/stable-audio-tools/scripts/synth_inversion/run_v8_retrain.sh
```

| # | Command | Takes | Needs GPU | On PASS |
|---|---|---|---|---|
| 1 | `bash $R check` | 1 min | no | go on |
| 2 | `bash $R render-check` | 1 min | no | **stop and ask the person to listen** to `/home/kim/sao_runs/v8_retrain_2026-11/v8_render_check.wav` |
| 3 | `bash $R data` | about 1 h | no | go on |
| 4 | `bash $R phase2` | about 1 h | yes | go on |
| 5 | `bash $R phase1` | about 2 h, then evaluation | yes | go on |
| 6 | `bash $R board` | about 10 min | yes | tell WINTERMUTE the board is staged |

`bash $R status` prints what has passed. Stages 3 to 6 are long: run each in the background and wait for it to end. They write to `/home/kim/sao_runs/v8_retrain_2026-11/logs/`.

Step 2's listen: notes should sound whole, not chopped, and the filter should open over the 4 s. If so, the person runs `touch /home/kim/sao_runs/v8_retrain_2026-11/RENDER_CHECK_APPROVED`. Stage 3 refuses to start without it.

## Gates

| Stage | Gate | If it fails |
|---|---|---|
| `phase2` | cutoff Spearman rho mean >= 0.80 on the test split | stop; Phase 1 does not run |
| `phase1` | separation tax (TSE MSE / clean MSE) <= 1.25 | stop; no board |

These are stated as implemented. Phase 2's is not the spec's registered gate: that one is centroid-trajectory correlation on re-rendered audio, and it is still to be built. So a Phase 2 pass is not yet the registered result. Say so when reporting.

## What to report at the end

- The output of `bash $R status`.
- For Phase 2: R² per lane and rho per sweep family, from `phase2_results.json`.
- For Phase 1: `tax_ratio_mse`, `tax_demucs_mse`, and the `tse_minus_demucs_*` intervals, from `phase1_results.json`.
- Nothing else. WINTERMUTE writes the record (`EXPERIMENTS.md`, `WORKLOG.md`, the board text).

## Out of scope for this run

R1 cleanup, R2 rerun, R3 as registered; the BS-RoFormer and two-stem baselines; the registered Phase 2 gate; extractor resolution and reliability target (M4, M5); groove-aligned mixtures (M3); Surge macro routing (M8). Do not start any of these.

## Notes for WINTERMUTE

- Sizes: 5,000 / 200 / 300 dynamic renders (was 500 / 50 / 100) and Phase 1 at 20 epochs x 10,000 samples (was 10 x 2,000, which the review calls a smoke test). Epoch counts are unchanged for Phase 2.
- Bank size limits `data`: the splits draw disjoint bank items.
- The runner's `SMOKE=1` mode runs every stage tiny into another directory: use it after changing the script.
- Stem cache is reused from `~/sao_runs/v8_stem_cache`, built 2026-11-03 02:49 with stem ids.
