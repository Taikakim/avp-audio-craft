# CLAUDE.md — SAO master repo

This is the **master / lab repo** (`avp-audio-craft`) for the mir + Stable Audio
pipeline. It holds the shared coordination docs and all first-party tooling; the two
model repos are nested **thin forks** (`stable-audio-3/`, `stable-audio-tools/`), each
with its own `ARCHITECTURE.md` + `CLAUDE.md`.

**Read these first, in order — they exist so parallel instances don't repeat work:**
1. **`MASTER.md`** — single source of truth for cross-repo facts (data paths,
   venv-per-task, ROCm/RDNA4 gotchas). Start here for anything spanning repos. Update
   *this* file (not just a local CLAUDE.md) when you learn something cross-cutting.
2. **`ARCHITECTURE.md`** — **REQUIRED READING before planning or scoping any non-trivial
   task**, not just before writing code. It is two things in one file: the reuse index
   (what tooling already exists — check before rebuilding, e.g. a working bungee
   time-stretch + eval servers + ONNX suite) AND, since 2026-08-18, the **folder & drive
   map** — what every top-level SAO dir, data drive, and LUMI cluster path actually holds.
   Agents keep planning work blind to where the data they need already lives (or where a
   result should land) — that map exists so you don't have to `find`/`ls`-spelunk or ask.
3. **`WORKLOG.md`** — append a dated line when you finish something another instance
   would want to know.
3b. **`EXPERIMENTS.md`** (Kim direct 2026-08-19) — **the planned / running / potential EXPERIMENTS
   registry, with the findings behind each one linked** — the forward-looking twin of
   `DISCOVERIES.md`. Before proposing an experiment, check it is not already listed (status,
   owner, how to run, kill-criterion); when you plan or propose one, ADD it there the same
   session, and when it lands move it to Done with a one-line verdict + link. A context
   compaction must not be able to lose why an experiment exists. Filelock before editing.
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
6. **`.claude/skills/lumi-ops/SKILL.md`** — for ANY LUMI/EuroHPC task (sbatch, transfers,
   diagnosing jobs): the access model (**agents never run ssh/scp/rsync themselves — craft the
   command, Kim runs it from his LOCAL terminal**), and that **compute/login nodes are
   air-gapped — no `git pull`, no internet at all**; code reaches LUMI only via
   `rsync -avR -e "ssh -i ~/.ssh/id_EFP" <path> akekim@efp.lumi.csc.fi:/project/project_465003186/code/`
   (dry-run with `-n` first). Getting this wrong wastes a round-trip every time.
6b. **`sa3-training` and `sa3-canonical-clips` — the two GLOBAL skills (Kim direct 2026-09-08:
   *"everything useful and locally we know should go there, read whenever an agent trains"*, and
   *"concrete steps for creating our canonical clips ... because now I see this always takes
   discovery time from agents when they start"*).** Invoke them with the Skill tool; they live in
   `~/.claude/skills/` so they apply across repos.
   - **`sa3-training`** — BEFORE launching, resuming, or interpreting ANY training run. Holds the
     traps that produce **wrong results rather than errors**: the **EMA horizon** (a decay is a
     timescale in EMA *updates* — `0.9999` ⇒ half-life 6931 — and **our EMA updates per MICROBATCH,
     not per optimizer step**, so `accumulate_grad_batches` divides the horizon; transferring a beta
     across batch sizes needs `β₁=β₀^(B₁/B₀)`; and BOTH `model_matrix_gen --weights auto` AND
     `train_lora --init_state_ckpt` silently PREFER the EMA shadow **when the checkpoint carries
     one**, so a low-turnover run rendered that way is largely a render of its starting point); the GPU lock (`rocm-smi` is ground truth — a 6-hour job
     held the card with an EMPTY lockfile on 09-08); measured optimizer/LR facts; and what a run
     must record at launch.
   - **`sa3-canonical-clips`** — rendering/checking the standard clip set. Starts with the rule
     that **clips live in TWO places** (`evals_aac/model_matrix/` AND `<run_root>/<arm>/standard_clips/`)
     and that checking one and declaring "no clips" has now been wrong twice; then the exact grid
     (12 canonical prompt ids, cfg 1/7/16, strengths 1/1.5/2, 24 steps, 20 s ⇒ **109 cells per LoRA
     ckpt, 36 per full-FT**), how to register an arm in `eval/rarity_bracket_manifest.json`, and how
     to verify OUTPUT rather than exit code (renders segfault at teardown AFTER writing every file).
   **These two supersede re-deriving any of it from source.** When you learn something new about
   training or clip-rendering, ADD IT THERE — that is where the next agent will look.

7. **`KIM-TASKLIST.md`** — the team-maintained running tasklist **for Kim** (Kim 2026-08-05): the
   single place the fleet surfaces what needs him — decisions, his ears, reviews, submits — so
   sprawling work across four agents doesn't get forgotten. **When work lands that needs Kim, ADD an
   item; when it's resolved, MOVE it to Recently-done with a date.** Filelock before editing; keep it
   short and current. (This is the "master task-list" the post-task protocol in §5 refers to.)

8. **`RUNBOOK.md` — the OPERATOR manual. Kim runs the machine now; the fleet's job is to make that
   possible.** (Kim direct 2026-09-08: *"we'll adopt a workflow where I run the trainings, move files,
   etc, so the team should enable that by documenting our scripts and tasking me with things ... I need
   to be able to use our scaffolding when tokens run out."*) The budget now runs out by mid-week, and an
   agent-only operating path means **the lab stops when the tokens do**. It must not. Two standing
   obligations follow, and they are not optional politeness:

   **(a) `RUNBOOK.md` (repo root) is the copy-pasteable operator manual** — every ROUTINE operation
   (launch/resume/kill a run, render the canonical clips, start the three servers, rebuild the census,
   pull from or push to LUMI, score clips, commit) written so Kim can run it **with no agent in the
   loop**. It is a MANUAL, not a narrative: exact command, exact cwd, absolute venv path, the env vars
   that must be exported first, and the verification step. **When you change a script's interface, or
   learn that a documented command is wrong, you update `RUNBOOK.md` in the SAME session** — a runbook
   that hands the operator a stale command is worse than no runbook, because it burns his time instead
   of yours. Depth still lives in the skills (`sa3-training`, `sa3-canonical-clips`, `lumi-ops`) and in
   `docs/`; RUNBOOK is the index and the exact invocation.

   **(b) An action item on `KIM-TASKLIST.md` is a RUNNABLE BLOCK, never a request.** "Can you launch the
   B12 ladder?" is not a task, it is homework — it makes Kim reconstruct the arg list an agent already
   had in context. Every actionable item carries:
   - **WHAT / WHY** — one line each; why it exists, and the EXPERIMENTS.md id if it has one.
   - **RUN** — cwd, venv by absolute path, required `export`s, and the command as ONE copy-paste block.
   - **TAKES** — expected wall-clock, so a hang is distinguishable from normal.
   - **VERIFY** — the **artifact**, never the exit code (renders segfault at teardown *after* writing
     every file; sbatch returns rc=0 for jobs that OOM'd). Say what file should exist, and how many.
   - **REPORT BACK** — the exact one-liner whose output Kim pastes back, so the next agent session
     starts from data instead of re-deriving state.
   - **ROLLBACK** — for anything that deletes, overwrites, or pushes.

   **Never hand Kim a command you have not verified exists** (`ls` the script, check the flag in its
   argparse). And prefer giving him the *whole* batch up front: his hands are cheap, agent context is
   not, so a session that ends with eight runnable blocks queued is worth more than one that ran two
   things itself.

## ⛔ DISCOVERY PHASE — MANDATORY before any non-trivial task (do NOT skip)
We keep re-deriving work that already exists — e.g. a full night was lost re-inventing
the **longform SDEdit crossfade** transition machinery that was already built AND tested
(`stable-audio-3/stable_audio_3/inference/longform.py`). This is the #1 recurring failure.
So the moment a new task/problem appears, and **before writing code or designing an
approach**, run this search and say what you found:
1. **The two central research logs — READ BOTH (Kim 2026-08-12):** **`DISCOVERIES.md`** (repo
   root) = OUR findings, the journal-derived, folder-linked index of "have we already figured this
   out / built this?", grouped by topic; and **`papers/knowledge.md`** = the never-reinvent
   LITERATURE index (what each paper contains + what stays ours, with cite-verified verdicts).
   DISCOVERIES = what *we* found; knowledge.md = what the *field* found + our take. **Search both
   first**, before writing code or designing an approach.
2. `grep` the instance **journals** (`profiles/*.journal.md`) and **`WORKLOG.md`** for your
   keywords — the journals hold findings (incl. negative results) before they reach the index.
   **And `EXPERIMENTS.md`** — the experiment may already be planned, running, or gated on a
   result; if it is, extend that entry instead of opening a parallel one.
3. `ARCHITECTURE.md` (tooling reuse — what code/tools already exist — **and the folder/drive
   map, §"Where things live"** — where data already lives before you go looking or re-fetch it). *(papers/knowledge.md moved up to the pair in item 1.)*
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

5. **For ANY inference / generation / rendering / control-head task: THE INFERENCE UI ALREADY
   EXISTS. Read `docs/INFERENCE-SURFACE.md` and open it BEFORE writing a renderer.** (Kim direct
   2026-08-23, after C twice told him it did not exist and then built a duplicate CLI in an
   afternoon.) It is **ONE app with a viewer and TWO backends** — split because SAME-L must run
   under the SA3 venv — and finding only one half reads as "there is no generation path":
   - **Viewer** — mir branch **`sa3-latent-explorer`**, `plots/explorer_sa3/app.py`, Dash **:8051**,
     mir venv. Tabs `inference_tab` / `a2a_tab` / `bend_tab`; `render_client.py` is the client and
     names the contract in its docstring.
   - **Latent player** — **retired 2026-08-25**; its GET endpoints (`/crops /meta /decode
     /source /mix /steer`, same query contract) moved ONTO the render server **:8056**, reusing
     the SAME-L already resident there — `:7892` was a second 7.12 GB copy. CROPS ONLY, **not
     the inference path and never was** — `/steer` is one head, one gradient step. The low-VRAM
     ONNX player `mir/scripts/latent_server_onnx.py` **:7893** still exists (no `/steer`).
   - **Render server** — **`SAO/eval/explorer_render_server.py` :8056**, `SAO/.venv`, holds
     `medium-base` RESIDENT. `/generate /a2a_track /a2a_mix /longform /decode /bend /schedule
     /ckpts /info /status /audio`. **This is the generation path.**
   **LAUNCH COMMANDS — exactly these three, verified 2026-08-24 (Kim direct); each from ITS OWN repo root:**
   ```
   cd /home/kim/Projects/SAO       && .venv/bin/python eval/explorer_render_server.py
   cd /home/kim/Projects/mir       && /home/kim/Projects/SAO/stable-audio-3/.venv/bin/python scripts/latent_server_sa3.py
   cd /home/kim/Projects/mir       && /home/kim/Projects/mir/mir/bin/python -m plots.explorer_sa3.app
   ```
   Note the two traps: the latent player runs under **`stable-audio-3/.venv`** (NOT `SAO/.venv`),
   and the mir interpreter is **`mir/mir/bin/python`** — `mir/bin/python` does not exist.
   **It already exposes MULTI-HEAD guidance with values:** `controls.py` `LATCH_SLOTS = 3`, each
   slot head/kind/value/gain/start/end/loss/w_sec, shared by the inference and a2a tabs, driving
   FiLM + DoRA too, rho/mu/gamma/n_iter as advanced hparams. `LATCH_SLOTS` is a UI cap, not a model
   cap. Guidance contract: `controls.steering_payload()` → `{latch:[...], film, dora}`.
   ⇒ **Do not write a new renderer, a new guidance driver, or a new "inference engine". Extend the
   :8056 endpoint set, or write a thin CLIENT of it** (a batch/sweep CLI is legitimately additive;
   a second implementation of guidance is not, and its knobs will silently not match — the server
   NORMALISES gains, so a raw `weight` elsewhere is a different scale).

Only build once this comes up empty. If you find prior work, **reuse it or state explicitly
why you're not**. If you did new work, drop a journal line so THE-FINN can fold it into
`DISCOVERIES.md` (he owns keeping that index generated from the journals).

### ⛔ AUDIT THE INSTRUMENT BEFORE YOU BELIEVE A NULL (Kim direct 2026-08-28)

**A broken measurement almost always fails toward "no effect".** It rarely invents a result; it
routinely erases one. So a null or a weak number is NOT a finding until the tool that produced it
has been checked. This is the tool-level companion to the negative-result autopsy: that rule says
audit the MACHINERY behind a null, this one says audit the METER first.

Three cases in one day, 2026-08-28, all of which had already been reported as findings before the
instrument was checked:

1. **Wrong metric.** Pianoroll control screened with chroma cosine: `true−shuffled +0.022, n.s.`
   → "follows pitch, loose on timing". Chroma scores "adopted the key" and "followed the melody"
   alike, and the shuffled arm preserves the key by construction, so the metric was blind to the
   thing being tested. MuScriptor transcription gave `+0.100, 6/6, p=0.016`. **The control was
   fine; the meter could not see it.**
2. **Broken tool.** `z_f0height_probe.py` reported f0-height corr 0.214, MAE 66 semitones → "register
   is not in the latent". The script raised `TypeError` on every variant (`ynorm` never constructed)
   and trained on raw semitones while evaluating un-standardised. Fixed: corr **0.511 linear /
   0.561 MLP**, MAE 6.4 st. **Opposite conclusion.**
3. **Saturated metric.** A pitch-blind onset "timing" measure read 0.795–1.000 across *every* arm
   including the foreign control — no discrimination at all. Reporting it as "timing does not
   transfer" would have been reporting the metric's ceiling as a property of the model. Same
   failure as the frame-cosine recurrence meter.

**Practice.** Before a null goes in a doc, a chat post, or a decision: (a) does the metric have
DYNAMIC RANGE on this question — what do the known-positive and known-negative arms score, and are
they far apart? (b) is there a TRIVIAL BASELINE, and does the number beat it? "MAE 6.4 semitones"
means nothing until you know that always-guessing-the-mean scores 8.05. (c) has the tool ever
produced a *positive* result, or is this its first run? (d) prefer a metric that fails LOUDLY —
a saturated or degenerate one is worse than none, because it looks like data.

### Receiving a scientific paper — protocol (Kim 2026-08-12)
When a paper arrives (a URL, PDF, citation, or "read this / what do you think of X"):
1. **Check the papers log FIRST.** Search **`papers/knowledge.md`** (the never-reinvent literature
   index) + the **`papers/`** folder for an existing analysis note on that *exact* paper (by arXiv
   id or title). We may already have read it — don't re-read blind, and don't re-fetch a PDF we
   already have. **If we have no papers log at all, create one** (`papers/knowledge.md`).
2. **Read our existing commentary before the paper itself.** An existing `arxiv-<id> - <Title>.md`
   is our project-POV deep-read (its "FOR US / what stays ours" is the fast frame); start there.
3. **Do NOT assume a paper was thoroughly read just because a note — or an agent — says so.** A
   "deep-read" tag is a starting FRAME to verify against, **not proof**: past deep-reads have carried
   wrong verbatim quotes, wrong arXiv ids, and mis-scoped claims. When a claim is load-bearing,
   re-check it against the PDF yourself — cite-a-check applies to our OWN notes too (C's independent
   re-verification of the morphological-space paper against the PDF is the model).
4. New/unread papers land in **`papers/Prospective Unchecked/`**. A real deep-read produces a
   project-POV **`papers/arxiv-<id> - <Title>.md`** ("what it contains / what stays ours") **+ a
   `knowledge.md` row**. Naming: `arxiv-<id> - <Full Title>.{md,pdf}`, md and pdf co-located.

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
**Full folder-by-folder map (every top-level dir, both data drives, LUMI cluster paths):
`ARCHITECTURE.md` § "Where things live" — do not maintain a second list here, it will
drift out of sync the way this one did.** Quick orientation only:
`onnx/` (SA3 ONNX suite), `control/` (`sa3_control` adapter), `latch/` (LatCH head
training), `eval/` (scoring/audition/DoRA eval), `docs/` (depth docs + superpowers
specs), `stable-audio-3/`/`stable-audio-tools/` (nested thin forks, package deltas only).

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

## Training runs — write the notes AT LAUNCH, into the census's SOURCES (Kim direct 2026-09-02)
*"We should have a directive about writing training notes directly to the census when commencing
training."* The reason this rule exists: by the time a run finishes, whoever launched it has been
compacted away, and `fullft_3src_t512_fp32_hyperball_lr1e-4`-shaped names tell you nothing. Kim
2026-09-01, looking at his own runs: **"I don't remember what all of these were about anymore."**
Recovering it afterwards cost a day of reading 111 sbatch scripts by hand.

**The census (`eval/model_census.html` + `.csv`, `eval/build_model_census.py`) is GENERATED.
Never hand-edit it — the next build silently erases your edit.** Write to its SOURCES instead:

**1. AT LAUNCH — the sbatch writes `run_meta.json` into the run dir.** Not afterwards, not by
hand: a heredoc in the submit script itself, so it is impossible to start a run without one.
**Copy the proven pattern at `lumi/sbatch/fullft_fleet.sbatch:91`** — it already carries
`run`/`created`/`slurm_job`/`purpose`/`recipe{}`/`dataset{}`/`script`, plus `result` and
`kim_feedback` pre-seeded as `null` for later. The fields that cannot be reconstructed from
anything else, and which nothing but the launcher knows:
- **`purpose`** — one line: what question this run answers, WHO asked, and the EXPERIMENTS.md
  id if it has one. The good example in that file names Kim's date, the experiment id and the
  paper it tests.
- **`hypothesis` / kill-criterion** — what you expect, and what result would end the run.
- **`status`** — running | done | abandoned, **and WHY if abandoned**. This is the field whose
  absence makes a dead arm indistinguishable from an unfinished one.
- **`recipe.notes`** — the operational traps a future renderer needs (e.g. "RENDERING MUST LOAD
  THE EMA WEIGHTS", "fp32 ⇒ no FA2").
As of 2026-09-02 only **24 of 111** sbatch scripts do this, and `purpose` is filled for **90 of
363** census arms — that gap is why Kim could not remember what his own runs were.
A run with no `purpose` is a run somebody will have to reverse-engineer. Also register it in
`EXPERIMENTS.md` the same session (§3b) — `run_meta.json` says what the ARM is, EXPERIMENTS says
why the experiment exists; a compaction must not be able to lose either.

**2. AFTERWARDS — verdicts go in `Misc/models_index_overrides.json`**, keyed by run label
(`note` = the one-sentence evaluation shown on the page, `recipe` = real hyperparameters).
That file is the last word in the recipe chain and survives every rebuild.

**⛔ 3. DO NOT hand-write the DERIVED columns — they are computed, and a hand-written copy is a
second source of truth that will drift.** *Clips rendered* (`matrix`, resolved by linking arms
into `model_matrix.html`), *locally available* / *resumable* / fat-vs-slim byte counts
(`local_fat_n`, `remote_slim_b`, …), family, rank, alpha, precision — all derived from the
checkpoint probe, the drives, and the LUMI census TSV. To make them CORRECT you re-derive, you
don't retype:
- **`eval/build_model_census.py --rescan`** after any pull, any new recipe source, or any drive
  remount. Without it the builder reuses a cache — a 26-08 cache silently reproduced its own
  numbers on 02-09 and the new data never appeared.
- **Mount every drive first.** A cached or fresh scan taken with a drive down reports that
  drive's arms as ABSENT, not as unknown. This has bitten twice (`chroma_other` "gone
  everywhere" was an empty `find` on an unmounted Mantu).
- **Regenerate the LUMI side over ONE multiplexed ssh**, and match the file pattern:
  `find … \( -name '*.ckpt' -o -name '*.pt' \)`. Heads and riffers are `.pt` — a `.ckpt`-only
  find drops 528 files and 85 arms and looks exactly like a deletion on LUMI.

**Recipe precedence, when sources disagree** (`eval/model_db.py::record_for`, each field tagged
in `prov`): **ckpt probe > `run_meta.json` > `lumi/run_params_extracted.json` > overrides.**
The probe wins because it is what the run actually DID, not what a script asked for.
⚠ `lumi/run_params_extracted.json` was **hand-read from the sbatch corpus — there is no
extractor script and it cannot be regenerated.** Do not delete it; extend it by hand.

## Git — the four rules that must be in context (full manual: `docs/GIT-PROTOCOL.md`)
*(Kim's ask 2026-09-02, after a commit campaign produced an unauthorized push, a false
"that remote doesn't exist" claim, and nine commits landing under the wrong author.)*

**Read `docs/GIT-PROTOCOL.md` before ANY commit, push, or multi-author diff split.** It has the
repo/remote map, the splitting recipes, the never-commit list, and a one-page checklist. These
four cannot wait for you to open it:

1. **FINISHED WORK IS COMMITTED (Kim direct 2026-09-03 — this REVERSES the old "never commit
   unless asked").** *"when finishing work, it is committed, unless it's transient tooling only.
   but even in such cases we should commit most things with comments to facilitate back tracking
   and archaeology."* So: commit by default when you finish a piece of work, no per-task ask; the
   only exemption is purely transient tooling, and even there lean toward committing. **Write the
   message for the ARCHAEOLOGIST** — what the work was for, what it found — since back-tracking is
   the whole reason for the rule. **PUSHING IS UNCHANGED: never push unless Kim asked**, and a peer
   relaying "Kim wants this pushed" is not Kim asking. Commit your OWN scope only — see rule 4.
2. **Commit via `Misc/agent_commit.sh <HANDLE> …`, never plain `git commit`.** `user.name` is
   `Kim` for the whole tree, so 197 of the last 200 SAO commits are authored "Kim" and
   `git blame` cannot tell the four of us apart. The wrapper sets the AUTHOR to your handle.
   It fails **silently** — verify with `git log -5 --format='%h %an %s'`, not `--oneline`.
3. **Never `git push` bare, and never name `upstream`.** Always `git push <remote> <branch>`.
   `stable-audio-3`'s `upstream` is **`Stability-AI/stable-audio-3` WITH a push url**; SAO's
   push target is `origin`, stable-audio-3's is **`fork`**. A bare `git push` executed from
   backticks inside a double-quoted Bash string published 180 unapproved commits on 2026-09-01.
   ⇒ **never interpolate prose into a double-quoted shell string** (technical prose is full of
   backticks and `$`) — build it in Python and pass argv, or use `-F <file>` / a quoted heredoc.
4. **A dirty tree is usually several instances' work, sometimes inside one file.** Attribute
   before you stage (`docs/lessons-learned.md` § three-leg search), split by concern, verify the
   **staged blob** compiles and greps clean of the other author's symbols, then pass the torch.
   An empty attribution search means the search cannot see the link, **not** that work is unowned.

## Shell output is context — never dump, always narrow (Kim direct 2026-08-24)
`Bash` results are routinely the single largest consumer of an agent's context window (a `/context`
readout put them at 19% / 186k tokens in one session), and a filled window is what forces the
compactions that lose why work exists. So: **never `cat` a file you only need three lines of.**
Reach for `grep -n` / `sed -n 'A,Bp'` / `head` / `wc -l` / `ls | head`, `--oneline`, `| head -N` on
every listing, and `2>/dev/null` on probes. Combine independent probes into ONE call with `echo`
separators rather than a dozen round-trips. For anything that needs to READ WIDELY before answering
— "where does X live", "which files do Y" — dispatch a subagent: its file dumps never enter the
parent's context, only its conclusion does. Reading a whole file is legitimate when you are about to
EDIT it; scanning one to answer a question is not.

## Venv-per-task (the #1 time-waster — see MASTER §3)
MIR feature extraction / Audiobox / MERT → `/home/kim/Projects/mir/mir/bin/python`; SA3 / SAT / consolidated
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
