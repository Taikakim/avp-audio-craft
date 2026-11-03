---
name: run-params-provenance
description: Where checkpoint run-parameters come from — the 4-source recipe chain, and that run_params_extracted.json was hand-read from sbatch and CANNOT be regenerated
metadata:
  type: project
---

Recovering "what was this training run about" for a checkpoint resolves through **four
sources, in this precedence order** (implemented in `eval/model_db.py::record_for`, each
field tagged in the record's `prov` map so you can see which source won):

1. **ckpt probe** (`eval/ckpt_probe.py::probe`) — read from the checkpoint file itself.
   Highest trust: it is what the run actually did, not what a script asked for.
2. **`run_meta.json`** — sidecar written next to a run dir, when one exists.
3. **`lumi/run_params_extracted.json`** — 249 arms keyed by arm name (joined 2026-09-01,
   `parse_run_params()` maps its schema onto model_db's field names).
4. **`Misc/models_index_overrides.json`** — manual last word.

**⚠ Source 3 was HAND-READ, not parsed, and there is NO extractor script.** It was built
2026-08-21 by reading the **111 sbatch scripts in `lumi/sbatch/`** (each entry's `_source`
names the exact file; 236 of 249 come from that dir, 13 from `lumi/`). The `_notes` fields
carry things a parser could never derive — e.g. "arm table is ARITHMETIC from SLURM_PROCID
(no case statement) … lr is hardcoded 1e-4 at line 101 … SA3_SDPA_CAST_BF16 chosen at
runtime by an fp32-SDPA capability probe, so attention may be true-fp32 or a bf16 island;
not determinable from the script."

⇒ **Do not delete or regenerate it, and do not `grep` for a script that rebuilds it — none
exists.** To cover a NEW run, read its sbatch and append an entry by hand. Kim's own framing
of the method (2026-09-01): *"the sbatch files on either our end or LUMI, if we search by
output filenames inside them, should have the technical details"* — the join key is the
output/arm name that appears inside the sbatch.

Field coverage is uneven and that is expected (`optimizer` 243/249, `lr` 241, `rank` 157,
`full_finetune` 128, `weight_decay` 52) — absent means the flag was not passed and trainer
defaults applied, NOT that the value is unknown-and-lost.

Related: [[board-representative-cells]], [[no-hardcoded-drive-paths]],
[[audit-the-instrument-first]].
