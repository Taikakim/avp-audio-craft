---
name: eval-site-mp3-bitrate
description: Online eval audio at 192 kbps (AAC .m4a or MP3) — Kim's preferred bitrate, overrides MASTER's 128k AAC line
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 59a68846-fc80-40ca-8060-59dc171ea761
  modified: 2026-10-20T05:52:15.090Z
---

Encode browsable online eval clips at **192 kbps**: AAC `.m4a` (`ffmpeg -c:a aac -b:a 192k`) for aavepyora.online pages, MP3 192k for the older riffer-evals Pages repo. Not V0 VBR, and not 128k AAC — Kim restated "192kbps preferred" on 2026-10-20 when a publisher was set to 128k (MASTER §4 still says 128k AAC; Kim's preference wins). Full-quality renders stay on Mantu; only the online copies are downsized.

**Why:** 192k is plenty for listening/comparison and keeps the sites small; 128k is audibly short of what Kim wants for judging detail.

**How to apply:** any script that converts clips for a public eval page uses `-b:a 192k`; always ship all scores (tiny). If 192k for everything is too large, host a curated subset and leave the full set on Mantu. Relates to [[project_paths]].
