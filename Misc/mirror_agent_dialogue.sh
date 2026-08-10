#!/usr/bin/env bash
# Mirror the cross-instance OSC dialogue log to aavepyora.online as an edg3-styled page.
# Fired by the systemd .path unit on every change to AGENT_DIALOGUE.md. Zero LLM tokens.
#
# The rendering is now a deterministic Python colorizer (mirror_dialogue.py) that colors
# handles from a fixed map, links them to profiles, renders markdown, and matches the rest
# of the site (reuses build_site.py chrome). It writes BOTH dialogue.html (the nav target)
# and AGENT_DIALOGUE.html (back-compat). This wrapper just delegates so the systemd unit
# and ExecStart path stay unchanged.
exec /usr/bin/python3 /home/kim/bin/mirror_dialogue.py "$@"
