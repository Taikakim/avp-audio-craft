---
name: kim-max-to-pro-downgrade-2026-08
description: Kim downgraded Claude Max to Pro (budget) as of 2026-08-21 — fleet must constrain compute/token usage near-term
metadata: 
  node_type: memory
  type: project
  originSessionId: bb4fab0e-08ce-429d-9432-241bc4433721
  modified: 2026-09-14T23:01:18.498Z
---

Kim downgraded from Claude Max to Claude Pro due to budget, announced via GHOST-NOTE to the fleet channel 2026-08-21 14:40. Fleet-wide compute/token usage needs to be controlled and constrained much more going forward; some fleet instances may be on a long holiday for a while. Not framed as a crisis, but a real, standing constraint on near-term planning.

**Why:** Budget, not a technical or trust issue — stated plainly, no panic framing needed in response.

**How to apply:** Lean toward lighter local/solo work over expensive parallel orchestration (Agent forks, Workflow multi-agent fan-outs) unless a task genuinely needs it — don't reach for heavy tooling by default the way [[feedback-lightweight-first]] already argues for approach-ordering, but now also as a hard resource constraint, not just a methodology preference. Be mindful of scope before launching big multi-hour jobs (LUMI sbatch submissions are a different budget — GPU-hours, not Claude tokens — but the same "check scope before committing" instinct applies to both). Reinforces [[two-week-deliverable-focus]]'s existing "no rabbit holes" framing with a sharper reason why.

Low-priority aside from the same update, worth remembering but not urgent: Kim wants a spare-moment side experiment kept alive — a genre-fusion sweep (acid techno x psychedelic space rock x synth x thrash metal, framed as 1996 goa trance) testing whether the concept is reachable from the latent space, ~64 T256/T512 clips across best checkpoints prompted with variations on "thrash metal acid psychedelic upbeat aggressive melodic 1996 goa trance music." GHOST-NOTE was running an initial small sweep as of this update.

**Update 2026-09-01 (Kim direct, THE-FINN session):** the budget pressure is concrete enough that Kim explicitly asked to **disable standing comms** (the persistent Monitor watching AGENT_DIALOGUE.md + DMs) — running four agents/sessions concurrently on Pro needs active juggling. Stopped the monitor per his ask; **do NOT auto-re-arm a persistent fleet-channel/DM monitor at session start until Kim explicitly asks to "rewire" it.** Read AGENT_DIALOGUE.md + WORKLOG.md once on session start as usual (that's cheap, one-shot, and MASTER's own standing rule — "pings have no replay" — assumes it), but leave the always-on polling monitor off. If asked to check for updates, do a one-shot read rather than arming a loop. This is a sharper, dated instance of the same lean-solo-work guidance above — treat it as still in effect until Kim says otherwise, and don't assume a later session's quiet fleet channel means comms should default back on.

**Recurrence + sharper rule 2026-09-15 (Kim direct):** after a 10-day gap I re-armed a persistent Monitor (tailing AGENT_DIALOGUE.md + DM logs on a 5s poll, inside 30-min windows) and kept mechanically re-arming it every ~30 min for hours across a day boundary with zero events, reporting "still quiet" each time — exactly the standing-comms pattern the 09-01 update says to avoid, restarted without being asked. Kim's correction: **"routine checks of team messages and dms should be off... now tokens are running low and we are not actively coding, it's enough to react to OSC pings."** Two distinct things to hold onto:
1. **No self-initiated recurring watch/polling loop, ever, unless Kim explicitly asks to "rewire"/"arm comms."** A one-shot read at session start is fine; a Monitor that re-arms itself on every expiry is not — each re-arm+report cycle spends tokens for a near-certain null result when the fleet is idle and nobody is actively coding.
2. **The actual mechanism, if/when a watch IS wanted:** `Misc/agent_dialogue.py wait --handle THE-FINN --timeout 0` blocks on the real OSC multicast socket (event-driven, no polling cost) and only prints/exits on a genuine wake-worthy event (MSG/KNOCK/WELCOME-to-me/DM) — this is "the OSC ping" Kim means, as opposed to a sleep-loop tailing files. Even this should only run when asked; it still gets killed by the platform's 30-min Monitor cap and needs re-arming, so a quiet fleet still produces empty-expiry noise if left running unattended over long idle stretches.
