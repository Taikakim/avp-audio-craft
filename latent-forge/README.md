# Latent Forge

A four-lane arrangement workspace for Stable Audio 3: place, stretch and align clips on an audio
timeline, audition renders before they touch the arrangement, then MIXDOWN — each lane is encoded,
steered through its own chain (LatCH / FiLM / LoRA / Bungee), overlaps are inpainted, lanes are
mixed in latent space and the master chain runs before one decode.

- **Spec:** `docs/superpowers/specs/2026-09-15-latent-forge-design.md`
- **Backend:** the resident render server `eval/explorer_render_server.py` (:8056) and its
  `/forge/*` routes (`eval/forge_api.py`).
- **Run it:** RUNBOOK §17. Development: `npm run dev` (Vite :5173, proxies to :8056).
- **Tests:** `npm test` (vitest), `npm run test:serve` (serve module), Playwright layout checks
  against the fixture mock (`docs/latent-forge/contract/fixtures/`).

The timeline is audio; renders land in the preview container and enter the timeline only when
dragged there; MIXDOWN is the only thing that commits the arrangement.
