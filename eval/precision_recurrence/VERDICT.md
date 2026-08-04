# fp32cmp vs bf16cmp precision re-score (whitened-chroma recurrence)
Paired at matched (ep,cfg,w,prompt,seed) cells. delta = fp32 - bf16; positive = fp32 MORE recurrent.
Same whitening caveat as the melody-wall readout (raw chroma cosine saturates).

- **fp32cmp_avp_t512_bs8_lr1e4 vs bf16cmp_avp_t512_bs8_lr1e4** (n=1584): Δrecurrence_rate=-0.0011 (52% cells fp32-higher) Δrecurrence_mean=-0.0000 Δflatness=+0.0011 Δhf=+0.0047 -> **~flat**
- **fp32cmp_avp_t512_bs8_lr1e4_ptm vs bf16cmp_avp_t512_bs8_lr1e4_ptm** (n=96): Δrecurrence_rate=+0.0114 (55% cells fp32-higher) Δrecurrence_mean=+0.0031 Δflatness=+0.0042 Δhf=+0.0587 -> **fp32 MORE recurrent**
- **fp32cmp_avp_t512_bs8_lr1e4_repr vs bf16cmp_avp_t512_bs8_lr1e4_repr** (n=108): Δrecurrence_rate=+0.0034 (55% cells fp32-higher) Δrecurrence_mean=-0.0016 Δflatness=+0.0004 Δhf=+0.0032 -> **bf16 MORE recurrent**
- **fp32cmp_avp_t512_bs8_lr1e4_repr_ptm vs bf16cmp_avp_t512_bs8_lr1e4_repr_ptm**: no matched cells
- **fp32cmp_goa_t512_bs8_lr1e4 vs bf16cmp_goa_t512_bs8_lr1e4** (n=1584): Δrecurrence_rate=-0.0089 (46% cells fp32-higher) Δrecurrence_mean=-0.0059 Δflatness=+0.0007 Δhf=-0.0048 -> **bf16 MORE recurrent**
- **fp32cmp_goa_t512_bs8_lr1e4_ptm vs bf16cmp_goa_t512_bs8_lr1e4_ptm** (n=96): Δrecurrence_rate=+0.0174 (59% cells fp32-higher) Δrecurrence_mean=+0.0044 Δflatness=+0.0042 Δhf=+0.0219 -> **fp32 MORE recurrent**