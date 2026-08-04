---
name: ckpt-prune
description: Use when reclaiming checkpoint disk space (LUMI /scratch or local drives) by stripping optimizer states — running or crafting commands for lumi/prune_optimizer_states.py, deciding which checkpoints keep resume state, or auditing a run dir after a prune.
---

# Checkpoint pruning (optimizer-state stripping)

**The tool: `lumi/prune_optimizer_states.py`** — never write an ad-hoc pruner; this one is
safe-by-design (slim `<name>.weights.ckpt` is written and verified BEFORE the fat `.ckpt`
is deleted; the LAST checkpoint per run keeps its full resumable form + gets a slim twin).

## Standing policy (Kim)

- **ALL checkpoints are kept** — pruning means stripping optimizer states, NEVER deleting
  epochs (rule #10). Slims stay eval/inference-usable.
- **The terminal epoch's fat ckpt is sacred**: it is the RESUME POINT. As of 2026-07-23
  runs routinely train FURTHER ("models just start to sound good at eps 5-7" — Kim's
  audit), so a lost terminal fat = a lost ability to continue that run. The script keeps
  it by default; the danger modes are the flags:
- **`--slim-all` and `--keep-last-only` are LOCAL-COPY-ONLY flags.** Never on LUMI, never
  on the only copy of a run. `--settle` likewise is a local endgame tool.

## Running on LUMI (agents craft, Kim runs — lumi-ops access model)

Dry-run FIRST, always; its listing is also the inventory audit:

```bash
singularity exec --bind /scratch/project_465003186,/project/project_465003186 \
  /project/project_465003186/containers/sa3.sif \
  python /project/project_465003186/code/lumi/prune_optimizer_states.py \
  --root /scratch/project_465003186/runs/<SUBTREE> --dry-run
```

Then the same without `--dry-run`. Scope `--root` to the intended subtree (e.g.
`runs/fp32_frames`, `runs/fullft`) — running at the bare `runs/` root prunes EVERYTHING
under it, including runs someone else is mid-flight on. **Never prune a run that is still
training** (its "last" ckpt moves; squeue first).

## Post-prune verification (count artifacts, never trust the run's own chatter)

Per pruned run dir, verify BOTH:
1. exactly one fat `.ckpt` remains and it is the max-step one:
   `for d in <root>/*/; do echo "$d: $(ls $d/epoch=*.ckpt 2>/dev/null | grep -vc weights) fat"; done`
   (expect `1 fat` everywhere; the fat's step must equal the run's max step)
2. slim count == original epoch count (nothing lost, only lightened).
If a run shows `0 fat`, STOP and flag Kim immediately — its resume point is gone; do not
prune anything else until understood.

## Sync note

After a LUMI prune, local pulls get cheaper (slims); the local mirror convention for
mixed dirs is `--settle` (LOCAL only). The fat-means-terminal convention feeds
lumi-ops's conditional-pull patterns — keep the two skills consistent.
