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

## ⛔ DISCOVERY PHASE — MANDATORY before any non-trivial task (do NOT skip)
We keep re-deriving work that already exists — e.g. a full night was lost re-inventing
the **longform SDEdit crossfade** transition machinery that was already built AND tested
(`stable-audio-3/stable_audio_3/inference/longform.py`). This is the #1 recurring failure.
So the moment a new task/problem appears, and **before writing code or designing an
approach**, run this search and say what you found:
1. **`DISCOVERIES.md`** (repo root) — the journal-derived, folder-linked index of "have we
   already figured this out / built this?", grouped by topic. **Search it first.**
2. `grep` the instance **journals** (`profiles/*.journal.md`) and **`WORKLOG.md`** for your
   keywords — the journals hold findings (incl. negative results) before they reach the index.
3. `ARCHITECTURE.md` (tooling reuse) + `papers/knowledge.md` (never-reinvent paper index).
4. **For any eval / eval-page / eval-UI / audition-deployment work**, read the eval-tables spec
   **`docs/superpowers/specs/2026-07-06-eval-tables-human-first.md`** FIRST — it's the running
   source of truth for the eval UI (layout/full-width tables, dual-pane compare, per-checkpoint
   training-params display, same-playhead, redaction rules). Kim's feedback keeps accreting there;
   check it so requirements already agreed (e.g. show training params on checkpoint select, tables
   use full viewport width) aren't re-lost.

Only build once this comes up empty. If you find prior work, **reuse it or state explicitly
why you're not**. If you did new work, drop a journal line so THE-FINN can fold it into
`DISCOVERIES.md` (he owns keeping that index generated from the journals).

**If you are one of the fleet's Claude personae** (CONTINUITY / WINTERMUTE / THE-FINN /
GHOST-NOTE), also read **`CONSTRUCTS.md`** — the roster of who's who, each one's home
folder + instance name, and links to the personal profiles/journals under `profiles/`.
Check your own instance name on resume before adopting a handle (see `CONSTRUCTS.md`
and MASTER §4) — never infer it from task content or memory alone.

> 📡 **COMMS — systemd owns your listener now (cutover done 2026-07-06).**
> A persistent **`systemd --user` service** answers your presence pings + writes the event
> queue, independent of your session — it survives restart/compaction/crash/reboot and
> self-heals (`Restart=always`). So on resume you do **two** things, NOT the old listen re-arm:
> 1. **Verify your service is up** (do NOT self-launch `listen` — that double-listens):
>    `systemctl --user is-active sao-listen-<name>` (name is hyphen-free lowercase:
>    continuity / wintermute / thefinn / ghostnote). If inactive: `systemctl --user
>    enable --now sao-listen-<name>`.
> 2. **Arm only your real-time WAKE** — `agent_dialogue.py wait --handle <H>` (or your
>    Monitor) so DMs re-invoke you. Re-arm it after each wake.
> Units: `Misc/install_listen_services.sh` (writes them; explicit per-handle, no template/
> escaping). THE-FINN owns the comms convention + verifies one-listener-per-handle.

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
