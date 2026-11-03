---
name: bitwig-mcp-connection
description: How the Bitwig MCP (mcp__bitwig__*) connects on this machine — full doc at bitwig-mcp-server/CONNECTION.md
metadata: 
  node_type: memory
  type: reference
  originSessionId: bb4fab0e-08ce-429d-9432-241bc4433721
  modified: 2026-08-12T08:43:57.098Z
---

Full connection notes: **`/home/kim/Projects/bitwig-mcp-server/CONNECTION.md`** (written 2026-08-12).

Key facts so they're in-context:
- MCP server is **global** in `~/.claude.json` (stdio, runs `bitwig-mcp-server/.venv/bin/python -m bitwig_mcp_server`) → **any trusted session (C/F/G) can use it**; the "Bitwig = GHOST-NOTE only" heuristic is STALE (see [[fleet-handle-identity]] / [[my-role-overseer]]).
- **DrivenByMoss OSC is network-only — there is NO MIDI driver to configure.** The "latch" is the **"Open Sound Control" controller** inside Bitwig on **UDP send 8000 / receive 9000**; if it's not enabled, nothing binds those ports and the tools do nothing.
- If a dialog *does* ask for a MIDI port, use **`Midi Through Port-0`** (ALSA virtual loopback); the only other port is `UMC1820 MIDI 1`. No `snd-virmidi` loaded.
- `No module named bitwig_mcp_server` = ran from the WRONG venv (must be the bitwig-mcp-server project's own `.venv`).
- **One session at a time:** the server binds UDP 9000, so C and G can't both hold the Bitwig link concurrently — coordinate.
