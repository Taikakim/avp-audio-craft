# CLAUDE.md — SAO master repo

This is the **master / lab repo** (`avp-audio-craft`) for the mir + Stable Audio
pipeline. It holds the shared coordination docs and all first-party tooling; the two
model repos are nested **thin forks** (`stable-audio-3/`, `stable-audio-tools/`), each
with its own `ARCHITECTURE.md` + `CLAUDE.md`.

**Read these first, in order — they exist so parallel instances don't repeat work:**
1. **`MASTER.md`** — single source of truth for cross-repo facts (data paths,
   venv-per-task, ROCm/RDNA4 gotchas). Start here for anything spanning repos. Update
   *this* file (not just a local CLAUDE.md) when you learn something cross-cutting.
2. **`ARCHITECTURE.md`** — the reuse index: what tooling already exists across the
   repos. **Check it before writing new code — we keep rediscovering things already
   built** (e.g. a working bungee time-stretch + eval servers + ONNX suite).
3. **`WORKLOG.md`** — append a dated line when you finish something another instance
   would want to know.

> ⚠️ **`WORKLOG.md` and the `AGENT_DIALOGUE.md` cross-instance channel are PUBLIC** (the
> dialogue log auto-mirrors to a public URL for remote review). **Never write secrets** into
> either — passwords, API keys/tokens, SSH creds, `.netrc`, credential-revealing paths; keep
> secrets in the shell/env. (See MASTER §4.)

## Layout
- `onnx/` — SA3 ONNX suite (export, infer, eval servers, DiT / control / latch onnx).
- `control/` — `sa3_control` adapter training + recipes + findings.
- `latch/` — LatCH head training, render / audition, probes.
- `eval/` — riffer, scoring, audition, DoRA eval + soups (`eval_dora_*`, `soup_*`).
- `docs/` — depth docs (venvs, commands, latch, training-findings, inference-servers,
  the SA3 inference **speed shootout**, `flash-attn-ck-rdna4`). Superpowers specs/plans
  under `docs/superpowers/`.
- `stable-audio-3/`, `stable-audio-tools/` — nested thin forks (package deltas only).

## Venv-per-task (the #1 time-waster — see MASTER §3)
MIR feature extraction / Audiobox / MERT → `mir/bin/python`; SA3 / SAT / consolidated
→ `SAO/.venv` (torch 2.14 / ROCm 7.15, CK flash-attn — `export
FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` before `import torch`). Invoke venvs by
absolute path; never assume `python` is the right one. Never `HIP_VISIBLE_DEVICES=""`
(flash_attn/aiter probes a Triton driver at import → crash).
