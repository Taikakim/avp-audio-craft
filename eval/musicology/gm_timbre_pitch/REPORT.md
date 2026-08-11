# GM Timbre-Pitch Atlas — REPORT

Reduced melody-encoding test over 120/120 pitched General MIDI programs (0-119; SFX 120-127 skipped; 112-119 percussive flagged quasi-pitched), 4 frame-locked MIDIs (sweep, pat1, pat2, pat5) per program.

## Universal pitch subspace (LOPO, pooled ridge decoder)

Leave-one-program-out R² deciles: {'p10': 0.3568, 'p20': 0.5715, 'p30': 0.6575, 'p40': 0.7255, 'p50': 0.7693, 'p60': 0.8025, 'p70': 0.832, 'p80': 0.8475, 'p90': 0.871}

Mean LOPO R² = 0.6861. Pooled pitch subspace dimension (PCA n90 of pooled sweep vectors) = 138.

**10 worst-transferring programs:**

- Orchestra Hit (#55, Ensemble): LOPO R² = -0.5683
- Woodblock (#115, Percussive): LOPO R² = -0.0374
- Reverse Cymbal (#119, Percussive): LOPO R² = 0.0033
- Synth Drum (#118, Percussive): LOPO R² = 0.1612
- Pad 2 (warm) (#89, Synth Pad): LOPO R² = 0.1682
- Whistle (#78, Pipe): LOPO R² = 0.1802
- Kalimba (#108, Ethnic): LOPO R² = 0.2298
- Agogo (#113, Percussive): LOPO R² = 0.2667
- FX 6 (goblins) (#101, Synth Effects): LOPO R² = 0.2914
- Taiko Drum (#116, Percussive): LOPO R² = 0.2998

## Cross-program transfer / GM-family block structure

Mean within-family transfer R² = 0.0547 vs mean cross-family transfer R² = -0.198.

### Hierarchical clusters (k=12, cosine of pitch-decoder weight vectors)

- Cluster 1 (n=1, majority family Percussive, purity 1.0): Melodic Tom(117)
- Cluster 2 (n=1, majority family Percussive, purity 1.0): Synth Drum(118)
- Cluster 3 (n=3, majority family Synth Lead, purity 0.33): Clavinet(7), Glockenspiel(9), Lead 5 (charang)(84)
- Cluster 4 (n=4, majority family Guitar, purity 0.5): Overdriven Guitar(29), Distortion Guitar(30), Tenor Sax(66), Bag pipe(109)
- Cluster 5 (n=50, majority family Synth Pad, purity 0.16): Electric Grand Piano(2), Electric Piano 1(4), Electric Piano 2(5), Celesta(8), Marimba(12), Percussive Organ(17), Rock Organ(18), Reed Organ(20) ...
- Cluster 6 (n=2, majority family Organ, purity 0.5): Drawbar Organ(16), Taiko Drum(116)
- Cluster 7 (n=1, majority family Percussive, purity 1.0): Reverse Cymbal(119)
- Cluster 8 (n=4, majority family Brass, purity 0.25): Voice Oohs(53), Tuba(58), Recorder(74), FX 7 (echoes)(102)
- Cluster 9 (n=11, majority family Piano, purity 0.36): Acoustic Grand Piano(0), Bright Acoustic Piano(1), Honky-tonk Piano(3), Harpsichord(6), Music Box(10), Dulcimer(15), Acoustic Guitar (steel)(25), Guitar Harmonics(31) ...
- Cluster 10 (n=26, majority family Strings, purity 0.23): Church Organ(19), Electric Guitar (jazz)(26), Electric Guitar (muted)(28), Synth Bass 1(38), Violin(40), Viola(41), Contrabass(43), Tremolo Strings(44) ...
- Cluster 11 (n=16, majority family Bass, purity 0.31): Vibraphone(11), Xylophone(13), Tubular Bells(14), Harmonica(22), Acoustic Guitar (nylon)(24), Electric Guitar (clean)(27), Electric Bass (finger)(33), Electric Bass (pick)(34) ...
- Cluster 12 (n=1, majority family Percussive, purity 1.0): Woodblock(115)

## Jump detectability (pat5 vs pat1 control)

Jump-detect balanced LDA acc range [0.8073, 1.0]. pat1 no-jump control mean acc = 0.5904 (should be ~0.5). Correlation of jump-detect acc with per-program pitch-decoder R² = -0.0157.

## Interleave (pat2 E/G) separation

d' range [2.811, 36.408], mean 13.099.

## Implications for melody LatCH multi-timbre training set

1. **GM's textual "family" taxonomy is not an acoustic-similarity taxonomy for pitch geometry.**
   Within-family transfer R² (0.055) is barely above cross-family (-0.198), and the k=12
   cosine-clustering of pitch-decoder weight vectors does not recover the 15 GM families
   (most clusters mix families at 16-50% purity). In practice there is one large "generic
   pitched-tone" supercluster (cluster 5, 50/120 programs, spanning piano/organ/keys/mallet
   families) plus ~10 small/singleton outlier clusters. Sampling training timbres by walking
   the GM family list does **not** guarantee pitch-geometry coverage — dedupe against the
   generic supercluster and prioritize covering the outliers instead.
2. **Oversample the outlier programs, not a family.** The 10 worst LOPO-transfer programs are
   dominated by the flagged quasi-pitched percussive block (Woodblock, Reverse Cymbal, Synth
   Drum, Agogo, Taiko Drum — 5 of 10, all #112-119) plus a few pathological melodic timbres
   with transient/formant-heavy envelopes (Orchestra Hit, Pad 2 warm, Whistle, Kalimba, FX 6
   goblins). A decoder trained on the other 119 programs gets negative-to-near-zero R² on
   these — the melody LatCH head needs their own labeled examples, not zero-shot transfer
   from "similar" instruments.
3. **A single universal linear pitch readout is a workable baseline but not sufficient alone.**
   Pooled LOPO R² has median 0.77 (p50) but a fat poor tail (p10 = 0.36, worst case -0.57);
   the pooled subspace needs ~138 of 256 channels for 90% variance, i.e. pitch information is
   not concentrated in a small universal subspace. Separately, fifth-jump (local pitch-change)
   detectability is near-ceiling for *every* program (LDA acc 0.81-1.0) and is uncorrelated
   with absolute-pitch R² (corr -0.016) — change detection is timbre-robust even where
   absolute-value decoding fails, so a melody LatCH head relying on relative/onset cues will
   generalize far more easily across GM timbres than one relying on absolute pitch value.

## Per-program table

See `per_program.csv` in this directory.
