---
name: long-lived-servers-daemonize
description: "Long-lived servers (:8056 explorer, eval servers) must be setsid-daemonized, NOT launched as run_in_background/Monitor tasks — the harness reaps those"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 59a68846-fc80-40ca-8060-59dc171ea761
---

Long-lived servers (the :8056 explorer render server `SAO/eval/explorer_render_server.py`, the CPU eval servers) must be launched as a **detached OS daemon**, never as a harness-tracked background task.

**What fails:** `Bash(run_in_background:true)` — the harness *stops/reaps* the task (status `killed`) seconds-to-minutes later, taking the server's process group with it. Hit 2026-07-13 restarting :8056: posted "live", server reaped ~seconds after, brief down-window.

**What works:**
```
cd /home/kim/Projects/SAO
setsid nohup env FLASH_ATTENTION_TRITON_AMD_ENABLE=FALSE \
  .venv/bin/python eval/explorer_render_server.py --port 8056 \
  </dev/null >logs/render_server_daemon.log 2>&1 &
disown
```
Run in a NORMAL (foreground) Bash call — the setsid process is in its own session, so the tool-shell exiting and the harness reaping tracked tasks leave it alone. Verify: poll `/status` (NOT `/health` — that route 404s) until 200, then confirm the intended routes are present in `/openapi.json` (`/bend`, `/longform`, `/a2a_mix`, `/generate` = the steering-v2 build) — C's lesson: verify the code you think is running IS running, not a stale process.

**Why:** it launches ~5GB SA3 resident; `[boot] ready — sr=44100 ds=4096 fps=10.7666` in the log = model loaded. Restart activates whatever new server code + endpoints landed since last boot.

Sibling to [[fleet-wait-arming]] (that one: OSC *wait* wants run_in_background; this one: *servers* must NOT). Distinction — short jobs/waits: run_in_background/Monitor; indefinite servers: setsid daemon.
