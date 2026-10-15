# Adapter mixer phase 1: implementation status and handoff (KUANG, October 15, 2026)

Branch `feature/adapter-mixer-phase1` (from `main` at the plan commit). Plan:
docs/superpowers/plans/2026-10-15-adapter-mixer-phase1.md (WINTERMUTE). Written on the laptop: CPU tests and type
checks only, no render server, GPU or browser.

## Done (tested)

| plan task | state | tests |
|---|---|---|
| 1 forge: `chain.lora.block_strengths` / `blend` | done as planned | `eval/tests/test_forge_render_settings.py` 22 pass |
| 2 GUI `LoraBlend` on the lane chain | done as planned | serializer + module-preset tests pass |
| 3 blend registry + wire mapping | done; help texts add the adapter-type and DoRA-zero notes | `registry.test.ts`, `latch.test.ts` |
| 4 curve math | done as planned (code taken verbatim from the plan) | `curves.test.ts` |
| 5 `CurveEditor.svelte` | done + fix: a double-click's first click no longer leaves a drawn tap; columns carry an ARIA role | 4 component tests |
| 6 ADAPTER MIX bottom tab | done + a direction-mode note in the header row | 4 component tests, shell tests |
| 7 right pane: SCALE greyed, status, open mixer | done; `loraBlend` help also says blending loads from disk | LaneChain component tests |
| 8 contract doc + RUNBOOK | done; contract doc adds the adapter-type table | — |

Extra (not in the plan): the render server reports `blend: "interp"` on adapter types that ignore it
(`bora`, `dora-rows-xs`, `dora-cols-xs`, `bora-xs`) in the response `warnings` of /generate, /a2a_track, longform
and /a2a_mix (`profile_warnings()` in `eval/explorer_render_server.py`). Test: `eval/tests/test_adapter_blend_profile.py`
(runs where the server imports, i.e. the desktop; skips elsewhere). The logic was also exercised on the laptop
by extracting the function.

Plan corrections made on the way:
- Task 1's tests called `R.parse_chain(chain(...))`, but the file's `chain()` helper already parses: they call
  `chain()` directly now.
- Task 7 adds a help string, so `src/lib/help/__tests__/strings.test.ts` expects 124 keys (was 123).

Whole latent-forge suite: 149 test files pass; `svelte-check` 0 errors (1 existing warning in Timeline.svelte).

## Left for the desktop (plan Task 8, steps 2 to 4)

1. Restart the :8056 server on this branch (needs SAO `5522423`, already on main).
2. The plan's GPU check (`amount` flat 1 vs a plain DoRA render: cosine >= 0.999; "last 8 off" clearly lower),
   plus three cheap additions:
   - `amount` flat 0 vs the base model (no adapter): cosine >= 0.999;
   - `direction` flat 1 vs plain: cosine >= 0.999;
   - if any `bora` or `*-xs` adapter exists: the response carries the new warning.
3. Manual GUI check (plan Task 8 step 4): the server log line `[dora] block profile applied: blend=interp ...`
   and SCALE greyed in LANE CHAIN.
