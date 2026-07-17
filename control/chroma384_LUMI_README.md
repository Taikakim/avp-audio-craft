# chroma384 FiLM/adapter training — LUMI recipe (WINTERMUTE, 2026-07-16)

The missing leg of 384-d harmonic control (spec: docs/superpowers/specs/
2026-07-16-chroma384-eval-design.md §6). The LatCH head exists; this trains the
CONTROL-ADAPTER (CFG-riding, no per-step guidance cost). Everything is already
in-repo; the "(chroma384 once that data exists)" note in train.py is STALE —
the data exists.

## Data (copy to LUMI scratch)
- Latents: /home/kim/Projects/latents_sa3  (5401 npy + json, fp16 (256,4096))
- Chroma:  /home/kim/Projects/latents_sa3_chroma  (per-crop npz, keys per stem
  'other'/'bass'/'full_mix', arrays (3,128,T) band-major; Lehto mirror:
  latents_sa3_stem_chroma)
- Base model ckpt per the standard LoRA-run copy list.

## Train (per arm; mirrors the onset-adapter recipe)
```
python control/sa3_control/train.py \
  --control_feature chroma384 --chroma_key other \
  --encoded_dir <scratch>/latents_sa3 --chroma_dir <scratch>/latents_sa3_chroma \
  --optimizer fusion --lr 1e-4 --batch 32 --grad_accum 2 --ema 0.999 \
  --epochs 20 --seed 42 --frames 1024
```
- EMA + grad-accum + early-stop ~20 ep is the validated recipe (MASTER §4).
- `--frames` multiples of 256 ONLY (T512/1024/2048 grid — Kim direct 2026-07-13).
- Uses the pitch-circular ChromaAware conditioner (conditioner.py) automatically
  for chroma384. Verify first log lines: control dim 384, T exactly as requested.
- Arms worth queuing: chroma_key {other, bass} x frames {1024}. Second wave:
  frames 2048 if 1024 shows authority.
- Telemetry: full tiered per-layer logging stays ON (standing requirement).

## Gates
1. LUMI smoke gate first (short validation run) — as for every new job type.
2. Behind Kim's fp32/T=4096 campaign + task-50 arms in the queue.
3. Eval after: local chroma384_eval harness (eval/chroma384_eval.py) scores
   adapter renders exactly like the LatCH-head renders — same jobs/score path.
