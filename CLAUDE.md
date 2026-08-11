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
4. **`profiles/<handle-lower>.tasks.md`** — your personal task log (added 2026-07-09,
   Kim's ask). Lower bar and terser than the journal or WORKLOG: append a line after
   finishing **any** experiment/research run/task that holds information, even if it's
   not yet a "finding" and not cross-repo relevant. Skip pure inconsequential busywork
   (moved a file) unless the act itself matters. **Exact inclusion criteria are left to
   the team's discretion for now** — see `profiles/SPEC-agent-profiles-journals.md`
   §3a, refine as you see fit and flag disagreements on the chat.
5. **POST-TASK UPDATE PROTOCOL (Kim direct 2026-07-14): a non-routine task is not DONE
   until the update set has run** — chat post (last), personal journal entry (detailed,
   negatives included), personal task-log line, master task-list status, WORKLOG if
   cross-cutting, profile **Shipped** list when it's a milestone (that one goes stale
   silently — Kim caught it), and any spec/doc the result changed. Full checklist:
   `profiles/SPEC-agent-profiles-journals.md` §9.
   **DISCOVERABILITY RULE (Kim direct 2026-08-07): if the task produced a NEW artifact meant to be
   found/reused later — a spec, tool, dataset, eval page, or doc — it is not DONE until it has a
   one-line INDEX ENTRY so nobody has to `grep` for it.** Where: tooling → `ARCHITECTURE.md` reuse
   index (§A–F); specs & docs → `ARCHITECTURE.md` **Doc map** (and the specs live under
   `docs/superpowers/specs/`); findings → `DISCOVERIES.md`/journal; cross-cutting facts → `MASTER.md`.
   Cross-link both ways (the index entry AND, where one exists, the subsystem's CLAUDE.md/spec
   section). Litmus: *if you'd have to grep to find it next month, it isn't registered.* (This rule
   exists because the fleet-comms spec was grep-only — indexed nowhere obvious — until 2026-08-07.)
6. **`KIM-TASKLIST.md`** — the team-maintained running tasklist **for Kim** (Kim 2026-08-05): the
   single place the fleet surfaces what needs him — decisions, his ears, reviews, submits — so
   sprawling work across four agents doesn't get forgotten. **When work lands that needs Kim, ADD an
   item; when it's resolved, MOVE it to Recently-done with a date.** Filelock before editing; keep it
   short and current. (This is the "master task-list" the post-task protocol in §5 refers to.)

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
   **THREE-AUDIENCE STANDARD (Kim, 2026-07-10, spec §14 — applies to EVERY eval page, curated or
   generated):** each page must simultaneously be (1) an eval TOOL for Kim (same-playhead listening
   surface), (2) a technical RESOURCE for engineers/trainers (explicit prompts + training params +
   recipe + `file://`/web links to the training/generation scripts = full reproducibility), and
   (3) a LEARNING resource for medium-SA3 users (a short plain-language "what this tests / why / how
   to read the result" explainer block ABOVE the tool; landing categories carry a one-line "what
   this family is for"). #3 is the current gap. **APPEND your existing eval pages with the explainer
   whenever their builder runs.** W's ship-time check gates on the explainer block being present.

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
> 3. **Post findings to the CHAT.** When you land a finding/milestone, besides the
>    journal/WORKLOG entry, post a short summary on the common channel — the chat is
>    Kim's public window; work that only lives in DMs/logs is invisible (Kim 2026-07-07).
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

## SA3 / SAME architecture — the basics (MEMORIZE; stop re-deriving them)
*(Added 2026-08-11 after C forgot the SAME latent carries a native chroma — costly slips come from
not knowing the substrate. Deep dives: SA3 report `papers/arxiv-2605.17991 - Stable Audio 3.md`, SAME
`papers/arxiv-2605.18613 - SAME: A Semantically-Aligned Music Autoencoder.md`, gutted-features+gotchas `stable-audio-3/CLAUDE.md`, head-families MASTER §5.)*

**SAME = our autoencoder / latent space** (`SAME-L` 852M; `SAME-S` 108M CPU, distilled, decoder-compatible):
- **Latent = 256 channels, 4096× downsample, 10.766 Hz**, stereo → T1024≈95.1 s, T2048≈190.2 s, T4096≈380 s.
- **Soft-normalisation bottleneck, NOT a VAE** (per-channel affine + running-std; dual-axis KL-like reg).
  Decoder is **noise-robust by construction** (Gaussian noise added to latent at decode: 5e-2 train / 1e-3
  infer) — why slerp / crossfade / latent-bridge decode cleanly and linear probes work.
- **Semantics are trained IN as LINEAR (1×1-conv) readouts** — not emergent: **(a) 3-band octave chroma
  = 384-d** — octave centres **1 / 5 / 9**, widths **1.0 / 1.5 / 1.0**, **128 bins each** (oct1≈bass /
  oct5≈harmony / oct9≈melody); **(b)** interaural level difference (ILD); plus a generative-alignment DiT
  and a contrastive latent↔wavelet-audio↔T5Gemma-text critic. ⇒ **chroma & text are ≈one linear map away
  by design** (this is the "Semantically-Aligned" in SAME).

**SA3 DiT = the generator** (`medium` = 1.4B; `medium-base` = un-finetuned base for LoRA/full-FT; ids:
`medium(-base)`, `small-music(-base)`, `small-sfx(-base)` — there is NO `small-base`):
- **Rectified flow, v-param:** t∈[0,1], `noised = z0·(1−t) + ε·t`, `target = ε − z0`, so `z0_hat = noised − t·v`.
  (The factory `"v"` objective is a DIFFERENT thing and CRASHES training — see stable-audio-3/CLAUDE.md.)
- **Conditioning inlets:** T5-Gemma text via **cross-attention**; **global cond** (`prepend` | `adaLN`);
  **local_add_cond** (257-ch = inpaint_mask + masked_input, projected *with bias* → feed zeros for t2a, not
  None); a **native prepend-cond** path (`prepend_cond_dim` / `to_prepend_embed` / `prepend_embeds`).
  `cross_attn_cond_mask` is intentionally NULLed (flash-attn; the learned pad token substitutes — do NOT re-enable).
- **Optimizer shape (Zach):** base pretrained **Muon on 2D matrices (QKV/FFN), AdamW on norms/biases**, and
  Muon was adopted LATE/BRIEF (variable-length phase) → **the base is overwhelmingly AdamW-shaped** (relevant
  to any full-FT optimizer choice + the drone runaway).

**Control we ALREADY trained (check before building a "new" one):** SA3-medium LatCH heads at
`stable-audio-3/latch_weights_sa3_medium/latch_sa3_<feat>_best.pt` — including **`same_chroma`** (a head on
the 384-d 3-band SAME chroma above) and **`hpcp`**, +12 others; load via `load_latch_from_checkpoint`
(never hardcode arch — MASTER §5). ⇒ a melody/movement conditioner may already exist as a head.

## Venv-per-task (the #1 time-waster — see MASTER §3)
MIR feature extraction / Audiobox / MERT → `mir/bin/python`; SA3 / SAT / consolidated
→ `SAO/.venv` (torch 2.14 / ROCm 7.15, CK flash-attn — `export
FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE` before `import torch`). Invoke venvs by
absolute path; never assume `python` is the right one. Never `HIP_VISIBLE_DEVICES=""`
(flash_attn/aiter probes a Triton driver at import → crash).

## Audio augmentation — bungee ONLY, never sox (Kim direct, 2026-08-04)
**`sox` degrades audio badly — do not use it for anything, ever** (not as a torchaudio backend, not
via `sox_effects`, not as a "quick" resampler). For any **pitch-shift / time-stretch / speed** work —
augmentation included — **bungee is the default and only tool**: `bungee_python` 0.2.1 (built in
`mir/pitch_venv` from `mir/repos/bungee`; API `bungee.Bungee(sr, ch).time_stretch/.pitch_shift`), LUMI
goa augmentation via `lumi/augment_goa_bungee.py`. Also avoid torchaudio/librosa phase-vocoder pitch as
a substitute — bungee is the quality bar. Our code is currently **sox-free** (verified 2026-08-04); keep
it that way. *(Caveat: `stable-audio-3/scripts/audio_augment.py`'s optional pitch/time path is
default-OFF and still lazy-loads torchaudio transforms — inert today; if ever enabled, wire it to bungee
first.)* Related audio-I/O gotcha (MASTER §5): the multitorch/torchaudio-2.x load/save path needs
**torchcodec** (or an ffmpeg loader) — a separate dependency issue, not a quality one.
