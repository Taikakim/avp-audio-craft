# Standardized experiment-commentary JSON — the record every artifact carries

*Standing directive (Kim, 2026-07-30): **every experiment that generates artifacts ships a
commentary section in a standardized JSON.** Depth = deep/full — enough to **replicate our
results, or at least learn from them** — plus a human-facing comment, because no one (Kim
included) can keep dozens of long filenames and experiments in their head. This spec is the
format. THE-FINN owns it (patrol/records lane); it is not a per-run reminder, it is the rule.*

This unifies and deepens two things that already existed piecemeal: the per-run `_meta.json` /
`run_meta.json` sidecars (purpose + script + checkpoints) and `models_index_overrides.json`
(auto-extracted recipe + one-line note). Neither carried the **why** or the **what-to-compare**,
and the recipe was terse. The standard below is a superset both should converge to.

## Where it lives
- **Per artifact-producing run** — a `commentary.json` sidecar next to the artifacts (the
  evolution of `_meta.json`; keep writing `_meta.json` too until consumers migrate). Emitted
  **as part of the run**, same as the self-eval directive — a run isn't "done" until it exists.
- **Per model on the eval matrix** — the same object, keyed by model label, in
  `Misc/models_index_overrides.json` (extended with the new fields). `build_model_matrix.py`
  renders it under each model header — the matrix *is* the public record.
- **The public render strips the internal block** via the site `redact()` layer (paths,
  checkpoints, drive labels, corpus scale) — see `docs/open-threads.md` redaction gotchas. The
  science (recipe, why, compare, verdict) stays; the plumbing does not.

## Schema (one object per experiment/model label)
```json
{
  "<label>": {
    "one_liner": "≤1 sentence: what this experiment IS, for fast human scanning",
    "family":    "which family it belongs to (shared why/compare live at family level)",
    "why":       "why it was made — the QUESTION or hypothesis it tests, in plain language",
    "recipe": {
      "base_model":   "e.g. SA3 medium (SAME latent, 10.77 Hz)",
      "method":       "fullft | DoRA | LoRA | control-adapter(FiLM/onset/LatCH) | soup | ...",
      "rank_alpha":   "rank + alpha + target modules (adapters); n/a for fullft",
      "optimizer":    "name + betas + weight_decay (adamw | fusion | sf-adamw | muon-composite)",
      "lr_schedule":  "peak LR + schedule (constant | cosine | schedule-free | warmup)",
      "precision":    "fp32 | bf16 | fp32-attention-bf16-weights | ...",
      "context_len":  "T in frames (256/512/1024/2048/4096) + seconds; native-train length",
      "batch_seed":   "batch size + gradient-accum + seed(s)",
      "steps":        "epochs and/or steps, avg_loss at ckpt if known",
      "corpus":       "which corpus + caption tier + augmentation (generic name; scale redacted)",
      "objective":    "loss/objective (rectified-flow, +aux losses) + any control target",
      "extras":       "anything else needed to reproduce (crop convention, dropout, EMA, ...)"
    },
    "compare_against": [
      {"target": "<label or family>", "axis": "the ONE variable it isolates vs this — e.g. precision, optimizer, rank, corpus, context-length"}
    ],
    "verdict":    "current result/ear+metric read (the old `note`; updated as evals land; honest, mixed ok)",
    "provenance": { "created": "YYYY-MM-DD", "by": "handle", "commit": "sha", "checkpoint": "manifest:<label>", "run_script": "honest pointer (job-id / script name / 'ask <owner>')" },
    "status":     "in-progress | done | superseded-by:<label> | finding-not-shippable"
  }
}
```

### Field rules
- **`recipe` is replication-grade.** The bar is: a competent stranger could re-run it. Where a
  field is auto-extractable from the checkpoint (optimizer param-groups, lora_config), extract it
  (don't hand-type — see the recipe-extraction note in `models_index_overrides.json`); hand-fill
  the rest. A pruned weights-only ckpt has no optimizer state → mark that field `"(pruned: not
  recorded)"`, never guess.
- **`why` and `compare_against` are the human layer** — the part Kim flagged as essential. They
  may be written **once per family** and inherited by members when members share a rationale;
  add a per-member line only where a member genuinely differs (e.g. the one epoch that won).
- **`one_liner`** is the fast-scan handle so a wall of long filenames becomes readable.
- **`verdict`** stays honest and mixed — "a finding, not a shippable model" is a valid verdict.
- **Checkpoint location — convention (c), locked 2026-07-30 (G):** `provenance.checkpoint =
  "manifest:<label>"`, a reference into `eval/rarity_bracket_manifest.json` (the single source of
  truth for `root` + `picks`, covering both the Mantu and UUID drives). **Never put a raw path in
  this git-tracked file** — the manifest holds them and is not public-rendered. `run_script` is
  NOT in the bracket manifest (checkpoint-only), so it stays an honest descriptive pointer
  (job-id / script name / "ask <owner>"), never a fake `manifest:` ref, never a guess.
- **Redaction:** with the above, no raw paths enter the commentary at all. The remaining
  public-surface concern is **corpus scale** in `recipe.corpus` / `training_data` — keep it
  generic in the source, and the render's `redact()` (the board imports `build_site.redact()`)
  strips any scale/drive/path that slips. Everything else is public-safe by construction
  (science, not plumbing).

## Rollout
1. **Backfill the eval matrix (213 models)** — deep recipes (re-extract from checkpoints, coord
   G for locations) + family-level `why`/`compare_against` (F drafts from history, C verifies the
   rationale, same gate that caught the style-adapter overstatement). Wire the new fields into
   `build_model_matrix.py` render (W/G board lane) + reship.
2. **New runs emit `commentary.json`** as part of the run, per the standing directive above.
3. THE-FINN patrols for artifacts landing without commentary (the drift this spec exists to stop).
