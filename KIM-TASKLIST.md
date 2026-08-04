# Kim's tasklist — team-maintained

*The single place the fleet surfaces what needs Kim, so nothing gets lost across four agents,
sprawling subjects, and real life. **Every instance:** when work lands that needs Kim — a decision,
his ears, a review, a submit — **ADD it here**; when it's resolved, **MOVE it to "Recently done"**
with a date. Keep it short and current; a stale tasklist is worse than none. Filelock before
editing (`python3 Misc/filelock.py acquire KIM-TASKLIST.md --handle <you> --timeout 30`). THE-FINN
patrols it for staleness. (Repurposed from KIM-RETURN-NOTES.md, 2026-08-05.)*

---

## 🔴 Decisions waiting on Kim
- **Merge PR #1** — doc-oversight doc review → `main`, when you're happy: https://github.com/Taikakim/avp-audio-craft/pull/1
- **same-chroma-steering-demos** — 1 commit stranded off `main`; merge it, or keep it a demos branch? (C to action)
- **Dev-branch rename** — `sa3-style-adapter` is a misnomer now ("far past a style adapter"); rename / restructure around `main` whenever you want. No rush.
- **SSH to the desktop — half-done, needs you at the desk** (08-04/05). `sshd` is enabled + starts on
  boot, firewall open, and password login from the laptop is verified working on the home LAN. Still
  yours: install the key (`scp` the laptop pubkey → `authorized_keys`), then harden
  (`PasswordAuthentication no`) — *only after* key login works, or you lock yourself out. Both are
  sudo/interactive, so they can't be done for you.
- **Tailscale — yes or no?** Decides whether ssh works from *outside* the home LAN (it doesn't today:
  on a hotspot the laptop can't reach the desktop at all). ~10 min at the desk, both machines, no
  router changes, no exposed port. Also the prerequisite for the item below.
- **Do you want a local-only notes path I can actually read?** The Notes widget now lives on
  `dora_table` (moved off the matrix 08-04, your call). It is **write-only by design** — public
  endpoint, so your notes land in your offline review file and no instance may read them, meaning
  your ear-verdicts still reach `run_meta.kim_feedback` only when you relay them in chat. A
  local-only twin (private network, nothing public can write to it) would let me ingest verdicts
  straight into the sidecars and auto-clear the ❗. Needs Tailscale to work away from home. — W
- *Carried from the 07-31 return-notes — team to confirm still-open or close:* alpha campaign + GOA-node submits; aug8 redo-vs-aug3 (encode profile unmeasured, parked).

## 👂 Ear queue (needs Kim's ears)
- **melody-wall: subloss_k2 vs baseline** top cells — the 08-04 metric came back weak/inconclusive; your ears settle it.
- **E3 metrical-position bracket pairs** — phrase-return gain (real 0.0091 vs shuffled 0.0009); does it *sound* like structure?
- *Carried from 07-31 — confirm/close:* gs_kpdark Gram-Schmidt clips; interval-CFG nl.475 pairs; Head-B bracket; goa_t2048_bs1 anomaly.

## ⏳ In flight — FYI, no action
- **aug8 models missing clips on run_audit_board.html** (Kim noticed 08-05) — confirmed not a pull
  gap: `aug8_encode` never produces checkpoints (latents only), `aug8_train_ddp`'s checkpoints stay
  on LUMI scratch by design, never pulled to either local mirror, no render job registered. Routed
  to C (owns the 07-23 aug8-15ep-campaign spec) — waiting on her word on whether standard clips were
  ever rendered on LUMI scratch or genuinely don't exist yet. — G
- **LUMI campaigns** live (big-FT / grids — current job IDs in WORKLOG).
- **`sa3_lenvar_hq` (length-variant renders, 220 tasks)** — *blocked on you for one thing:* when it
  drains, relay the artifact count (`ls .../renders/length_variant/*.wav | wc -l`, or the `.out`
  tail). Agents can't reach LUMI. Everything downstream is built + deployed — the clips ingest and
  the boards fill the remaining 55 models' native/ptm cells with no further code changes. — W
- **model_index.md generator** — being built (F, 08-05).

## ✅ Recently done (rolling — prune monthly)
- **08-05** — doc-oversight first pass (PR #1); DISCOVERIES regenerated 54→201; fleet skills committed; this tasklist stood up.
- **08-04** — repo consolidated to GitHub (`main` + `sa3-style-adapter` synced, 104 GB artifacts gitignored); E1a x0-equiv arms shipped + scored (weak/inconclusive); board clip-resolution fixed.

---
*Deeper state: `WORKLOG.md` (what landed / broke) · `docs/open-threads.md` (open/dropped work ledger) · `profiles/*.journal.md` (per-instance).*
