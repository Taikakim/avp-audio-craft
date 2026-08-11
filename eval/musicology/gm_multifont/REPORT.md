# GM Multi-Font Melody Probe -- REPORT

640 renders across 40 GM programs (<=16 fonts/variants each).

## (a) Clustering around patch number

Frame-mean-latent space: silhouette(cosine)=-0.2257, within-program cos=0.6597 vs cross-program cos=0.5729 (permutation p=0.005).

Pitch-decoder-weight space: silhouette=-0.0421, within=0.2382 vs cross=0.1245 (p=0.005).

Most coherent (frame-mean): ['Pad 2 (warm)', 'Flute', 'FX 6 (goblins)', 'Pad 6 (metallic)', 'Oboe', 'Pad 8 (sweep)', 'Synth Strings 2', 'Synth Strings 1']

Least coherent (frame-mean): ['FX 2 (soundtrack)', 'Lead 3 (calliope)', 'Lead 2 (sawtooth)', 'Lead 7 (fifths)', 'Tinkle Bell', 'Pad 1 (new age)', 'FX 3 (crystal)', 'FX 5 (brightness)']

Generic-supercluster check: mean nearest-OTHER-program centroid cosine = 0.9448 (higher -> more cross-program mixing).

## (b) Interval decodability

- k=1 cell_vs_pedal (up): 5-fold LDA acc = 0.8637, per-program d' [0.739, 1.465, 2.569] (min/mean/max)
- k=1 cell_vs_pedal (down): 5-fold LDA acc = 0.8607, per-program d' [0.811, 1.467, 2.906] (min/mean/max)
- k=1 direction (up_vs_down): 5-fold LDA acc = 0.8523, per-program d' [0.849, 1.553, 2.802] (min/mean/max)
- k=2 cell_vs_pedal (up): 5-fold LDA acc = 0.885, per-program d' [0.87, 1.707, 3.084] (min/mean/max)
- k=2 cell_vs_pedal (down): 5-fold LDA acc = 0.8885, per-program d' [0.886, 1.633, 2.989] (min/mean/max)
- k=2 direction (up_vs_down): 5-fold LDA acc = 0.8649, per-program d' [0.799, 1.538, 2.408] (min/mean/max)
- k=3 cell_vs_pedal (up): 5-fold LDA acc = 0.8886, per-program d' [0.863, 1.777, 3.118] (min/mean/max)
- k=3 cell_vs_pedal (down): 5-fold LDA acc = 0.8866, per-program d' [0.872, 1.585, 2.82] (min/mean/max)
- k=3 direction (up_vs_down): 5-fold LDA acc = 0.8667, per-program d' [0.892, 1.55, 2.44] (min/mean/max)
- k=5 cell_vs_pedal (up): 5-fold LDA acc = 0.8947, per-program d' [0.798, 1.71, 3.241] (min/mean/max)
- k=5 cell_vs_pedal (down): 5-fold LDA acc = 0.8579, per-program d' [0.871, 1.664, 3.299] (min/mean/max)
- k=5 direction (up_vs_down): 5-fold LDA acc = 0.8586, per-program d' [0.803, 1.595, 2.443] (min/mean/max)
- k=7 cell_vs_pedal (up): 5-fold LDA acc = 0.8683, per-program d' [0.936, 1.66, 2.893] (min/mean/max)
- k=7 cell_vs_pedal (down): 5-fold LDA acc = 0.8535, per-program d' [0.813, 1.465, 2.701] (min/mean/max)
- k=7 direction (up_vs_down): 5-fold LDA acc = 0.875, per-program d' [0.876, 1.566, 2.555] (min/mean/max)
- k=12 cell_vs_pedal (up): 5-fold LDA acc = 0.7908, per-program d' [0.81, 1.38, 2.081] (min/mean/max)
- k=12 cell_vs_pedal (down): 5-fold LDA acc = 0.8217, per-program d' [0.793, 1.273, 1.978] (min/mean/max)
- k=12 direction (up_vs_down): 5-fold LDA acc = 0.8435, per-program d' [0.997, 1.473, 2.425] (min/mean/max)

## (c) Hysteresis

Predecessor-identity (13-class) balanced acc = 0.4068; successor/anticipation (13-class) balanced acc = 0.3486 vs chance 0.0769 (held-out fonts: [np.str_('CrisisGeneralMidi3.01.sf2'), np.str_('GMR Basico1.1.sf2'), np.str_('Just T4.sf2')]). Predecessor >> successor would indicate mostly acoustic tails; predecessor ~= successor indicates symmetric/architectural (non-causal receptive field) context.

Hysteresis magnitude (cos-dist of bar14-onset frame from pedal centroid): mean over patch renders = 0.2396; SINE CONTROL (no acoustic release tail, 5ms ramps only) = 0.0009 -- any nonzero sine value is encoder-intrinsic context, not reverb bleed.

Decay curves (balanced acc vs recency in frames, binary vs no-context reference; full data in hysteresis_decay.csv):

- predecessor (bar14 chain, patch-pooled): [{'recency_frames': 1, 'balanced_acc': 0.6661}, {'recency_frames': 2, 'balanced_acc': 0.6062}, {'recency_frames': 3, 'balanced_acc': 0.612}, {'recency_frames': 4, 'balanced_acc': 0.5724}, {'recency_frames': 5, 'balanced_acc': 0.5443}, {'recency_frames': 6, 'balanced_acc': 0.5401}, {'recency_frames': 7, 'balanced_acc': 0.5182}, {'recency_frames': 8, 'balanced_acc': 0.5224}]
- successor/anticipation (bar1-tail chain, patch-pooled): [{'recency_frames': 2, 'balanced_acc': 0.5427}, {'recency_frames': 3, 'balanced_acc': 0.5531}, {'recency_frames': 4, 'balanced_acc': 0.5437}, {'recency_frames': 5, 'balanced_acc': 0.551}, {'recency_frames': 6, 'balanced_acc': 0.5573}, {'recency_frames': 7, 'balanced_acc': 0.551}, {'recency_frames': 8, 'balanced_acc': 0.5698}, {'recency_frames': 9, 'balanced_acc': 0.5396}]
- predecessor (sine, cos-dist from ref, descriptive): [{'recency_frames': 1, 'cos_dist_from_ref': 0.0009}, {'recency_frames': 2, 'cos_dist_from_ref': 0.0}, {'recency_frames': 3, 'cos_dist_from_ref': 0.0}, {'recency_frames': 4, 'cos_dist_from_ref': 0.0}, {'recency_frames': 5, 'cos_dist_from_ref': 0.0}, {'recency_frames': 6, 'cos_dist_from_ref': 0.0}, {'recency_frames': 7, 'cos_dist_from_ref': 0.0}, {'recency_frames': 8, 'cos_dist_from_ref': 0.0}]
- successor (sine, cos-dist from ref, descriptive): [{'recency_frames': 2, 'cos_dist_from_ref': 0.0001}, {'recency_frames': 3, 'cos_dist_from_ref': 0.0}, {'recency_frames': 4, 'cos_dist_from_ref': 0.0001}, {'recency_frames': 5, 'cos_dist_from_ref': 0.0}, {'recency_frames': 6, 'cos_dist_from_ref': 0.0}, {'recency_frames': 7, 'cos_dist_from_ref': 0.0}, {'recency_frames': 8, 'cos_dist_from_ref': 0.0}, {'recency_frames': 9, 'cos_dist_from_ref': 0.0}]

Release-tail-vs-intrinsic correlation (release length vs hysteresis magnitude, patches only) = -0.2083.

## (mix) Two-voice separability + drum robustness

Retention (r2-on-mix / r2-on-solo): lead=-0.1665, bass=0.0356 (1.0 = perfect retention).

Superposition test z(mix) vs z(solo_lead)+z(solo_bass): mean cos=0.8847, mean relative residual=0.8435. Worst-cos sections: [{'section': 'pivot_up_k1', 'cos': 0.8745}, {'section': 'pivot_up_k12', 'cos': 0.8761}, {'section': 'pivot_down_k3', 'cos': 0.8771}, {'section': 'pivot_up_k3', 'cos': 0.8783}, {'section': 'pivot_down_k1', 'cos': 0.8794}].

Voice confusion: lead-decoder-on-mix corr with TRUE bass pitch = -0.1837; bass-decoder-on-mix corr with TRUE lead pitch = -0.2425 (near 0 = clean separation).

Drum robustness (n=8 pairs): lead decoder r2 mix(no drum)=0.5152, mix+drum=0.1073, lead+drum-only=0.6689. Latent delta from drum injection: kick frames=6.6826 vs offbeat-hat frames=9.2424.
