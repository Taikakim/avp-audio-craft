# Uncovering the Generative Landscape of Diffusion Models: A Spectral-Guided Quality-Diversity Diffusion Framework

- **arXiv:** 2610.15724v1 (2026-10-11, cs.LG)
- **Authors:** Hannah Janmohamed, João Correia, Penousal Machado, Antoine Cully (Imperial College London, University
  of Coimbra)
- **PDF:** `papers/arxiv-2610.15724.pdf`
- **Code:** https://github.com/adaptive-intelligent-robotics/qd-diffusion
- **Read by:** KUANG, 2026-10-17: main text read; appendices (pseudocode, ablations, sample images) skimmed.

## What it contains

- Quality-diversity search over a frozen diffusion model's genotype (initial noise x_T + conditioning embedding c):
  fitness = CLIP score, diversity = DreamSim embeddings, archive = Dominated Novelty Search with a fitness threshold
  (stops novel-but-invalid outputs from filling the archive).
- **h-space spectral mutation:** run deterministically to an intermediate timestep, take the top right singular
  vectors of the Jacobian from the latent x_t (or c) to a mid-network activation (power iteration with autodiff),
  perturb along one of them, invert deterministically back to x_T.
- SDXL-Turbo (36 PartiPrompts) and Flux.1-dev (12 prompts, a DiT): lowest FID of 12 baselines; pure fitness
  maximisers (Adam, CMA-ES) reward-hack with artefacts; intermediate-layer Gaussian noise gives "diversity" made of
  corrupted images.

## What it does not contain / caveats

- Images only; audio is proposed future work, not shown. The quality and diversity numbers depend entirely on the
  chosen embedding models. A large internal Jacobian response is not shown to be a meaningful or desirable change.

## For us

- A later tool for exploring SA3 (diverse listening sets, mapping which control or conditioning directions have
  leverage) and a link to the representation track (information_flow, adapter-mixer block curves). LatCH guidance is
  already a Jacobian of a head with respect to the latent. Not an optimizer change; not scheduled.
