# What we're attempting on top-octave clarity — please shoot holes in it

*(Draft for Kim to send to Julian. No-hype; the goal is a fast expert refutation before we
spend compute. Nothing is trained yet — code prototyped only.)*

**Context.** We run SA3/SAME frozen and train adapters/DiTs on top (electronic/psytrance
corpus). To my ear the one thing keeping outputs from producer-grade is top-octave clarity:
the >8k "air" reads softer / less defined than a 128k MP3.

**What we measured** (SAME round-trip = encode→decode vs original; 8–16k band; env-xcorr
aligned; multi-res STFT): magnitude *retention* ~0.92 (the energy is there), but air-band
**envelope** correlation ~0.54 vs 0.97 (128k MP3) / 0.997 (320k), and >7k phase coherence
~0.05. Reading: the top octave is present at ~the right average level but doesn't **track the
source's dynamics over time** (energy is envelope-domain / phase-free, so this isn't the phase
point — that's separate and we agree it's cheap to lose).

**What we're prototyping** — codec stays frozen:
1. **Generative post-net** on the decoded audio (~2.5M params): multi-res magnitude loss +
   multi-period discriminator + feature-matching to regenerate a better top octave.
   Generative, not regression, because we measured regression collapses HF to the mean.
   Possibly conditioned on the SAME latent and/or a multi-window PSD.
2. **DiT-side** (retrain diffusion, codec frozen): whiten the latent to uniform variance +
   v-prediction + zero-terminal-SNR, aimed at low-variance latent directions sitting under
   the flow target's noise floor.

**Where you could save us weeks** (you trained it; we're inferring from the outside):
- Is the air-band deficit fixable downstream at all, or is that info gone at encode by design
  — so a post-net can only make *plausible* air, never *source-tracking* air (and would that
  even read as better, or just different)?
- Is "env_corr below MP3" even the right thing to chase for a regenerating decoder, or a
  metric artifact? Is SAME's air-band simply *meant* to be plausible texture, full stop?
- Track B assumes SAME's latent has a strongly anisotropic covariance (we measure ~786×,
  188/256 directions below unit variance) that starves the DiT. Does the soft-norm +
  dual-axis reg already handle that — making whitening redundant or even harmful?
- Are we at the wrong layer entirely — would a decoder fine-tune weighted toward air-band
  dynamics, or a larger-latent variant, just fix this at the source and make the post-net
  pointless?

Very happy to be told any of this is a dead end.
