# D. The meters: how we tried to see melody, and how each one fooled us

Evidence dossier (track D of the melody field guide), compiled 2026-11-03 by reading existing logs, docs and result files only. No renders, no GPU, nothing re-measured. Every number is copied from the cited source; "UNSOURCED" marks what I could not trace. MEASURED means a meter read it; HEARD means Kim (or another listener) said it. Line numbers are as of 2026-11-03 and drift.

Abbreviations: EXP = EXPERIMENTS.md; C/W/G/F = CONTINUITY / WINTERMUTE / GHOST-NOTE / THE-FINN journals in `profiles/`; WL = WORKLOG.md; TF = docs/training-findings.md.

---

## 1. Meter catalog

Format per entry: what it measures (plain words) / dynamic range (known positive, known negative) / trivial baseline / failures / trust now / relied on by.

### M1. Raw chroma cosine (STFT or SAME chroma, time-averaged or per frame)
- **Measures:** how similar two 12-pitch-class energy profiles are. Cannot tell "same key" from "same tune".
- **Dynamic range:** none on goa. Tier-2 real-goa readout, raw matched vs raw mismatched (null): bass 0.987 vs 0.983, mid 0.996 vs 0.994, air 0.997 vs 0.995, i.e. delta +0.004 / +0.002 / +0.002 (`eval/musicology/same_chroma_readout_tier2_muscriptor_2026-08-11/REPORT.md:12-24`). Whitened-recurrence tool note: raw chroma cosine "saturates ~0.95 on tonal goa" (`eval/melody_wall_analysis.py:30-35`, WL:2266).
- **Trivial baseline:** any two goa tracks. That IS the "chroma trap": goa is minor-key, tonic-heavy, rolling bass, shared lead grammar, so everything correlates (Tier-2 REPORT:12-14).
- **Failures:** (a) 2026-06-19, W: a mode-collapsed riffer adapter (same output for every reference) still scored chroma about 0.9 against any goa reference; "declared success twice" (W journal:259-266; DISCOVERIES.md:203). Fix then: cross-reference audio diff (generate with reference A vs B, same seed, RMS-diff). (b) 2026-08-26 D15 first verdict: chroma screen gave true minus shuffled = +0.022 n.s. ("follows pitch, loose on timing"); MuScriptor transcription on the same clips gave +0.100, 6/6, p=0.016 (EXP:749-776, 778-790). The shuffled arm preserves the pitch-class distribution by construction, so a chroma meter is blind to the placement of the right pitches in time. (c) 2026-08-28 same page: "adopted the key" and "followed the melody" score alike; six rolls have mean pairwise pitch-class-profile cosine 0.29, so foreign pairings sit in different keys (EXP:749-752).
- **Trust now:** do not use as a melody meter. OK only as a key detector, and only against a same-seed unguided baseline (delta form, M6).
- **Relied on by:** riffer adapter (06), D15 first verdict (08-26), melody_wall (M4), Tier-1/Tier-2 readouts (M5).

### M2. Corpus-demeaned cos12, derangement nulls, per-window z-norm, frame-shuffle null (the repairs for M1)
- **Measures:** chroma cosine after subtracting the corpus-mean 12-d profile per band (so only track-specific deviation remains), compared with 5 derangement (mismatched-pair) nulls; later per-window z-norm; later a within-track frame shuffle.
- **Numbers:** Tier-2 demeaned cos12 median (n=1200, audio ground truth): air 0.918, mid 0.536, bass 0.214 (Tier-2 REPORT:29-36). Tier-1 (synthetic) air was 0.054 (REPORT:5). The MuScriptor-MIDI secondary (n=752, 448 dropped on integrity): air matched 0.403 vs null 0.207 (delta +0.196, 386/752 with notes); bass/mid delta about 0.01 (REPORT:42-47). Per-window z-norm medians matched / shuffled / null: bass 0.323/0.248/0.136, mid 0.449/0.345/0.220, air 0.526/0.401/0.266, fingerprint fractions 0.60 / 0.55 / 0.52 (D11, EXP:1195-1200).
- **Failure and correction:** the 0.918 "melody" reading was read as melodic content; D11 showed ~half of the matched-over-null identity signal is a static per-track fingerprint (mastering EQ, codec lowpass, constant chroma shape), ~half temporal. EXP:1195-1200 says to "halve in spirit" any claim quoting 0.918 as melody. Also: the demeaned variant is time-averaged and shuffle-invariant by construction (D11 results.json provenance note), so it cannot be a melody-timing meter. Also: the demeaned MIDI-GT air distribution is bimodal and polluted by ~366/752 tracks with zero transcribed air notes (Tier-2 REPORT:42-45, 63-67).
- **Stem vs mix:** the head's prediction is closer to full-mix GT than to the isolated `other` stem on every band (air 0.918 to 0.837; mid 0.526 to 0.509; bass 0.181 to 0.133), explained as training-target circularity (target is `W@z+b`, a full-mix proxy) (`same_chroma_stem_vs_mix_2026-08-12/REPORT.md:9-18`). Bass vs a kick-free bass stem rises 0.181 to 0.302 (+67%).
- **Trust now:** medium for "the 384-d readout carries band-specific identity"; low for "melody". Always report the shuffle-surviving share.
- **Relied on by:** E2 per-window norm (08-12), D11 (08-21), conditioning design key "condition on whitened chroma, not raw" (C journal:1540-1552).

### M3. Frame-cosine / patch recurrence meters (loop and hook detection)
- **Measures:** how much a clip repeats itself. Frame-level cosine, then 4 s patches, then per-band-whitened log-mel patches.
- **Dynamic range:** frame cosine saturates: 0.99 for the source and every noise level on a2a ladders (W journal:106-112; DISCOVERIES.md:336). The patch-level meter separates (kaikkialla novelty 0.059 to 0.029, -50%; vapausvoima 0.044 to 0.013, -70% at nl .55-.60) and "matches Kim's ear" (W:112-117). v3 whitened log-mel: novelty 0.659 to 0.471 at nl .55, about 8x the chroma separation (W:123-126).
- **Failures:** the frame-cosine meter would have fired on everything; chroma is tonality-biased and breaks on non-tonal psytrance, rhythm is constant and saturates (W:121-124). "0.968 loop is looping for one track, about source for another" (W:118-120): needs per-track calibration.
- **Trust now:** patch-level whitened version OK for loops; it is a repetition meter, not a melody meter.

### M4. Whitened-chroma self-similarity recurrence ("melody_wall_analysis", hook proxy)
- **Measures:** after z-scoring each pitch class over time (to remove the static harmonic bed), the fraction of frame pairs more than 2 s apart with similarity above 0.5. Higher = more returning motifs (`eval/melody_wall_analysis.py:4-9, 30-45`).
- **Numbers:** baseline recurrence_rate 0.188. Deltas vs baseline on 2304 clips, n=360/arm: K2 +0.029 (+15% rel, 54% of cells up), K12 +0.019 (+10%, 52%), x0eq +0.010 (51%), x0eq+sub5 +0.006 (59%), K5 -0.008 (53%) (C journal:1322-1327; WL:2266). Verdict then: "weak, inconclusive, near-noise", per-cell coin flip, non-monotonic K (K2>K5<K12). Later 1680-cell v3sel readout: all arms recurrence-up, k5 +16% rel, tgate +0.011 < k5 +0.030 (EXP:426).
- **Failures:** (a) The meter's own author caveat: chroma is a harmonic proxy, not lead-isolated (C:1330-1332). (b) The interval-resolution ladder (08-06) found Euclidean latent displacement saturates (semitone about 0.94 of a fifth, octave 0.98), so anything keyed on displacement magnitude or raw-chroma energy is "contour-blind", "which likely poisons the whitened-chroma melody-recurrence readout" (`interval_resolution_ladder_2026-08-06/VERDICT.md:22-27`). (c) The automatic HOOK up/down labels in v1 were miscalibrated (thresholded on %-up) (C:1337). (d) KIM-TASKLIST.md:394-398: W scored the same clips on CLAP and quality: "neither metric is a MELODY metric, so the melody question is still yours".
- **Disagreement with ears:** on 2026-09-27 Kim heard the subspace loss "really seems to work", "has the most distinct melody" (section 3). The meter said +10-16% relative at best and a coin flip per cell. See section 4.
- **Trust now:** low. Use only as a repetition screen; a null does not mean no melody effect.

### M5. same_chroma LatCH head readouts (SAME 256-ch latent to 384-d 3-band chroma, folded to 12; bands bass oct1 / mid oct5 / air oct9)
- **Measures:** whether the SAME latent linearly carries pitch-class energy per register band. This is a readout of the representation, not a steering test (`same_chroma_readout_2026-08-11/REPORT.md:1-8`).
- **Known-positive / negative:** Tier-1 synthetic MIDI (1380/1380 pairs scored): bass/mid pooled cos12 0.79-0.86, air about 0.054 pooled but register-content-limited (chromatic sweep to C8 reads cos12 0.55-0.99) (REPORT:12-24). Frame-precise "loudest pitch class" argmax under a fast chromatic run is "near/below chance" even where whole-vector cosine is excellent (REPORT:19-22). Contrast: the melodic-contour Head-A hit macro-F1 0.28 (chance 0.125) (REPORT:24-31).
- **Failures:** Tier-1 reported air as a head weakness; Tier-2 on real goa reversed it (0.054 to 0.918) and showed it was a synthetic-material artifact (Tier-2 REPORT:33-36). Then D11 halved the 0.918 as melody (M2).
- **Trust now:** medium-high for "chroma is linearly readable from z0 on bass/mid" (it is a trained SAME readout by design); low for per-note resolution.

### M6. Delta cos12 / strongest-class hit vs a same-seed gain-0 baseline (steering authority for chroma heads)
- **Measures:** how far a guided render's frame-wise chroma moves toward the target compared with the same seed unguided; plus the share of frames whose strongest class is the target's strongest. Built to be chroma-trap-safe (C journal:844).
- **Numbers (E13, mid band, mean over 3 prompts x 4 targets x 4 seeds):** production head +0.014 / +0.033 / +0.075 / +0.133 / +0.189 at gain 512 / 1024 / 2048 / 4096 / 8192; C3 lr1e-3 ep10 +0.152 / +0.232 / +0.300 / +0.354 / +0.384 (EXP:1677-1712). E13x sharp target: strongest-note hit 0.25 to 0.45 at gain 32768 while frame cos falls (EXP:1766).
- **Failures:** (a) 2026-10-28 E21: `chroma_steer_render.build_target_raw` locked the bass root with argmax over equal-weight triad classes, so F# and A got root C#; bass-band numbers invalid (EXP:1874, RESULT). (b) The hpcp head was trained on Essentia HPCP with a 440 Hz reference, bin 0 = A, but targets put C at bin 0, so every C request asked for A and "every earlier hpcp steering result used the 9-semitone-off target"; this also explains MASTER's old `hpcp` "dead" label (MASTER.md:1036-1038 vs 1055; EXP:1874 second run). (c) 2026-10-28: a gain-0 baseline rendered through `generate()` without `latch_configs` takes a different sampler than the guided path at rho = mu = 0; 4 of 12 such baselines scored CE about 3 vs 6-7 for steered clips, flipping the production head's low-gain sign (W journal:1148-1150). (d) Reliability fault: a request can decode to all-NaN audio from a finite latent or come out unsteered; 2 of 1,715 cells at gain >= 2048 (EXP:1776). Root cause later traced to `expandable_segments` set by an import (W journal:1190).
- **Trust now:** medium-high as a within-run relative meter with same-seed baseline, bungee control and gate. Not a melody meter: it scores a 12-class profile.

### M7. Essentia HPCP (hpcp_ts target) and MERT-layer readouts
- **Measures:** 12-d harmonic pitch class profile (Essentia); MERT layers as generic music embeddings.
- **Failures:** (a) "essentia hpcp_ts = garbage recipe (my proposed tier-1 would have used it)" (C journal:418-424). (b) The June LatCH sweep read heads with the upper MERT layer ("melody/harmony") for energy heads and mislabeled the two best heads "dead"; conversely the MERT-mid sweep was "blind to harmony" so hpcp was labelled dead at any weight, later refuted for harmonic steering (MASTER.md:1036-1042; C journal:846-848). (c) Bin-0-is-A bug (M6).
- **Trust now:** hpcp is usable only with `HPCP_BIN0_PC` applied; MERT as a melody meter: low (see M13).

### M8. MuScriptor transcription: (pitch, frame) F1, key/content/melody decomposition, top-line follow, consonance-weighted precision
- **Measures:** a neural transcriber turns audio into MIDI; the meter compares notes in time with a requested roll.
- **Best dynamic range of any melody meter we have.** D15 (6 tracks, 2026-08-28): key (pitch-class profile cos) true 0.952 / shuffled 0.955 / foreign 0.169; content (pitch-set Jaccard) 0.875 / 0.857 / 0.533; melody (pitch,frame) F1 0.534 / 0.435 / 0.094. True minus shuffled +0.100, 6/6, sd 0.044, sign test p=0.016 (EXP:753-763). Consonance: of 5871 played notes, 69.5% exact, 30.4% a different note inside the roll's pitch-class set, 0.2% outside; 87.0% unison/3rd/4th/5th class (EXP:765-770). 2026-11-03 re-read with CFG on the stream: fed roll F1 0.653, source crop 0.609, no stream 0.045; fed minus shuffled +0.203 [+0.181, +0.226], 48/48; top-line follow +0.636, 47/48 (EXP:735). Invented melodies: fed pitch sounds on 73% of frames vs 2.5% no stream and 3.2% another melody; transposed crops F1 0.63 vs 0.05 (EXP:735).
- **Trivial baseline:** no-stream render, shuffled-in-time roll, foreign roll. All three are in the D15 design.
- **Failures:** (a) Under-transcribes legato: sustained notes over 1 s approximately 0 on every source (C journal:943-950); it is universal, so "held-note recovery" is its own rung. (b) Stems are worse than the full mix for MuScriptor (bass < mix 10/10, other < mix 10/10; median notes 1305 mix vs 366 bass vs 641 other); it is OOD on separated stems (C:943-947). (c) Full-mix transcription "collapses to a near-mono bassline with collapsed instrument labels" (C:951-954). (d) Codec-decode gate (SAME-decoded vs original audio, 12 tracks): median F1 0.738 vs deterministic ceiling 0.997, F1 gap 0.259, pc-corr 0.9955 (gap 0.004); mechanical verdict RED, overruled to GREEN on Kim's "section-relevant" rule; outlier "Passage" decode F1 0.026, pc-corr -0.114 (`eval/muscriptor_gate.json`; W journal:638-646). (e) SDEdit at nl 0.45 destroys transcribability (coverage 0-0.47) while chroma stays on source, so transcription evals of a2a outputs need nl-awareness (WL:2213). (f) D15 first full eval (2026-09-04): its own-vs-foreign gate showed the measure could not tell true from foreign reference ("own-vs-foreign melody +0.022, 80/192, p=1") for a contour stream, because contour tokens discard absolute pitch by design (WL:2420; C journal:2444-2470). (g) 2026-11-03 E24 eval 1 uninformative: one prompt and seed made every render read as one held note, foreign arm duplicated true arm (EXP:1912). (h) 2026-11-03 scoring error: true-minus-shuffled on each arm's own stream gave about 0 because both arms follow (W journal:1197). (i) Circularity: MuScriptor built the training rolls and scored the renders; hence the independent Melodia check (M9).
- **Trust now:** highest of our melody meters for "are these pitches there at those times", with limits: one transcriber, legato blind, coverage failures, and not a taste meter. Always run with fed / shuffled / foreign / no-stream arms and report coverage.
- **Relied on by:** D15, E21 (equivariance), E24 arms B/C, B13, the Head-B bracket "adopt_active minus wrong-contour" confusion metric (C journal:Head-B 2026-07-29, "cfg16 conf +0.227, adopt .464 vs wrong .237"), the hook metric (M16), Tier-2 secondary GT.

### M9. Melodia (Essentia PredominantPitchMelodia; frame 2048, hop 441, 55-1760 Hz, after EqualLoudness)
- **Measures:** the dominant single pitch line per 10 ms, then compared as a curve or as "within 1 semitone of a line".
- **Dynamic range:** E23a (synthetic known lines, 8 melodies x 3 soundfonts x 3 programs, alone and at 0 dB over goa drums and bass): corr with true line 0.999 up/down, 0.998 arch/valley, 0.993 at a 5 s wave, 0.97-0.98 at 2 s, versus about -0.15 to 0 for the other melodies; within a semitone (up to octave) on 98% of voiced frames; E4b follow score 1.996 of 2. `steps_big` scores low (own -0.10 / +0.13) because voiced coverage is 0.46 (EXP:1898 part (a)). D15 independent check on invented melodies: within 1 st of the fed line 74%, shuffled 43%, other melody 17%, no stream 18%; fed minus other +0.58 [+0.50, +0.65], 34/36 (WL:2918).
- **Failures:** (a) **Input-length dependence:** Melodia's contour selection uses statistics of the whole input, so the same stem read over a 47 s window agrees with the whole-track reading on only 52% of frames (19% octave-off on track 000600); a render is a 47 s window, so the fed stream cannot be reproduced from any render (`eval/morph_f0_contour_ab.py:5-16`; EXP:1293). (b) YIN is not a substitute: PitchYinFFT gave 28.4% of steps within 2 semitones and 10% octave jumps; Melodia on stems gave 96.9% / 0.0% (W journal:811-815). (c) Octave errors and window dependence are the stated reason D17's streams may have been too noisy (EXP:1898, "Reading"). (d) E4: "a tracker on a mix may read an existing voice getting louder" (EXP:1463-1468).
- **Trust now:** good for slow whole-line shape (E23a ceiling); weak for notes; window length must match.
- **Relied on by:** D17 contour A/B, E23a/b, E4/E4b/D16 f0 heads, D15 independent check, the f0 head store targets.

### M10. Demucs `htdemucs` "other" stem as pre-processing
- **Measures nothing alone**; it isolates the stem that Melodia then reads. The fed morph stream was Melodia on the Goa_Separated `other` stem, so the meter had to reproduce that path exactly (reproduced: raw 100 Hz agreement 1.000, pooled 99.5% within 0.5 st on track 000600) (`morph_f0_contour_ab.py:10-13`).
- **Failure:** separator output is out-of-distribution for MuScriptor (M8b). 18% of stem folders (818/4461) carry `.mp3` not `.flac`; a hardcoded extension would silently give them no f0, correlated with which separator ran (W journal:817-823).
- **Trust now:** needed for like-for-like with the fed stream; adds its own error (separation bleed).

### M11. Pitch-curve Pearson r (render vs fed stem's semitone curve), plus local 48-frame windowed r
- **Measures:** whether the render's dominant pitch line rises and falls with the fed line (invariant to transposition and scale, what a contour conditioner controls). Built after exact contour symbols failed.
- **Dynamic range (the gate):** known positive (reference clips through the same path): r own +0.431 vs foreign -0.066. Symbol agreement on the same positive: 0.13 vs 0.08 for a wrong stem (`morph_f0_contour_ab.py:17-25`; EXP:1293). Local windowed r: positive 0.125 vs 0.034.
- **Ceiling:** 0.43 on a perfect copy, so "any effect is below about 12% of a perfect copy's 0.43" (2 SE = 0.05) (EXP:1293).
- **Result:** D17, 200 clips: pooled own - foreign +0.0001 (74/144 positive, p 0.80); conditioned - null +0.023 (73/144, p 0.93) (EXP:1293). Open failure points listed there: the conditioner never learned it, or the prompt at cfg 7 swamps it, or the meter sees only whole-line shape.
- **Trust now:** medium. It has range on a known positive, but the ceiling is low. E23b later showed fed streams inside chance as well.

### M12. K&P / Polansky contour: exact dense-rank symbols (L2/L3/L4), L3 shape agreement, contour-cosine loss
- **Measures:** Kant and Polansky morphological-space contour: rank order only, invariant to any monotone transform (`contour_codes.py` docstring quoted in C journal:2457-2462). Contour distance is approximately angle, which gave the differentiable `control/sa3_control/contour_loss.py` (C journal:1555-1565).
- **Failures:** (a) 2026-09-04: `eval/morph_contour_ab.py` failed its own positive control: re-extracting from the reference audio scored 0.146, LOWER than the renders' 0.151; encoder control against ground-truth `f0_other_ts` reached only 0.755 / 0.550 / 0.337 for L2 / L3 / L4 (WL:2420; C journal:2444-2490). Fixed as FATAL gate. (b) Exact symbols compound every pitch error (EXP:1293). (c) E24 arm B: L3 shape agreement +0.020 [+0.006, +0.037] vs centred pitch +0.028 on its own measure; decoded crops +0.209 (EXP:1906, Arm B RESULT).
- **Trust now:** exact symbols: do not use. Centred-pitch correlation (M11/E24): medium.

### M13. MERIT (frozen MERT-330M + three heads; S_mel / S_rhy / S_tim) and MERT embeddings
- **Measures:** disentangled melody / rhythm / timbre similarity between two audio clips (`eval/morph_merit.py:1-14`).
- **Dynamic range:** self-check exact 1.000, but S_mel is SATURATED on same-corpus material: two DIFFERENT references score 0.611 mean / 0.861 max while a cell scores 0.49-0.69 against its own (WL:2420). At gain 2.0 conditioning raised FOREIGN similarity more (+0.041) than own (+0.025), diff -0.017, p=0.71: a generic style shift, which would have been reported as "the conditioner works" at +0.0247, 48/64 positive, p=7.7e-05 (C journal:2448-2452).
- **Trust now:** low on goa-vs-goa. Must be read as own-minus-foreign with null arm.

### M14. Pitch-blind onset "timing" measure and onset-density authority
- **Measures:** whether onset times in a render line up with the roll's, ignoring pitch.
- **Failure:** read 0.795-1.000 across every arm including the foreign control; "uninformative, do not quote" (EXP:772-773). Saturated by the dense 16th-note goa texture. Related: the onset-authority metric was gameable: a request for "ambient drone with low-volume rapid hats" measured 12.9 onsets/s and "Kim's ear caught it instantly; no metric did" (C journal, "onset-authority metric is gameable"; DISCOVERIES.md:73). And Ph3's "onset_density +2 raises onsets 5.7 to 6.8/s" was disintegration mis-scored; re-measured 0.17 onsets/s at flatness 0.64 (C journal 2026-07-30).
- **Trust now:** do not use timing-only for melody. Onset density is a separate lane.

### M15. Audiobox Aesthetics PQ / CE (and CLAP, crest, flatness)
- **Measures:** production quality (PQ) and content enjoyment (CE) by a learned predictor; not melody.
- **Finding (B13 rationale, 146 transcribed clips, 2026-09-08 autoscale renders):** split by whether MuScriptor found a lead voice: pq no-lead 7.956 vs lead 7.927 (d -0.10, z -0.61); ce 6.676 vs 6.782 (d +0.22, z +1.27); crest 4.058 vs 4.744 (d +0.45, z +2.62); flatness d +0.31; hf_ratio d 0.00. "Whether a render contains a melody at all is invisible to PQ and CE" (EXP:854-868; G journal:951-985; `eval/midi_metrics_ingest.py:1-30`).
- **B13 status:** PLANNED; Test 1 (do lead presence / hook_melodic_ratio separate Kim's rated 4s from 5s?) is NOT recorded as run anywhere I found. Power bound stated: at n5=154 only d >= 0.26 detectable (EXP:876-880). Test 2 hint: `fullft_ladder_C_dual` vs `B_autoscale` at ep39 is 5-0 discordant (McNemar p about 0.06), n=12 pairs (EXP:881-886). "Coverage is the trap": the melodic fields are NULL on about 66% of clips because 40% have no lead (EXP:870-876).
- **Other failures:** Audiobox scoring dies silently when a system package moves a SONAME and returns rc 0 (`audiobox DONE: 0 scored`), MASTER.md:780-783; a gate passed on `ce > 0` while scoring nothing (G journal:940-945); PQ varied only 0.13 across air-head epochs that Kim heard as clean vs glitchy, click meter and validation loss pointed the wrong way (TF:319-323); k2 "costs more than it gives" on quality but quality is not melody (KIM-TASKLIST.md:394-398).
- **Trust now:** valid as a quality guard; blind to melody. Do not read a flat PQ/CE as "no melody change".

### M16. Hook metrics from MuScriptor MIDI (`hook_melodic_ratio`, contour_compression, top_motif, distinct46_grid_ratio, has_lead, n_lead)
- **Measures:** skyline lead line, kick-refined grid, motif mining: how much of a clip's lead is repeated motifs.
- **Dynamic range:** corpus: top hook-decile repeats its best motif 56x vs 0x (bottom), vocab compression 0.41 vs 0.98 (WL:2208). 20 corpus ids reproduce memorability.json exactly (8/8 fields) (WL:2209). P2 cfg axis: `hook_melodic_ratio` falls cfg7 to cfg16 in 8/10 families while pedal occupancy rises; no-lead 32-84% everywhere vs corpus about 5% (WL:2214; `eval/musicology/hook_pilot_cfg_axis_2026-07-22.md`).
- **Failures:** NULL on 66-81% of clips (needs a lead voice), so averaging over a mixed set averages over "no melody" as missing at random (G journal:957-962). MIDI grids need beat-period refinement or raw bpm drifts whole beats over 380 s (WL:2208). Inherits every MuScriptor limit (M8).
- **Trust now:** medium as a descriptive screen; no ratings join has been reported.

### M17. Disintegration gate (`eval/disintegration_metrics.py`, `eval/control_head_disintegration_eval.py`, `eval/post_run_gate.py`)
- **Measures:** whether a steered render has drifted from its own unsteered baseline in whitening (flatness), hf-blowout (hf_ratio), zcr, beat-loss and CE (|dCE| > 1.5). It guards against "static buzz moves the feature meter" (MASTER.md:516-530).
- **Role for melody:** E4 pitch heads and E13 chroma steering report gate fails alongside authority (E4: gate 0/24 at each gain; E4b 0/48, 5/48, 13/48 at 8192 / 16384 / 32768; EXP:1463-1468).
- **Failures:** it is a DSP screen, "not the ear", thresholds still to be recalibrated against Kim's GUI verdicts (MASTER.md:528-530). Kim heard buzz on heads that the authority pipeline tagged working (MASTER.md:516-520). Air-head sweep: the click meter ranked glitch-free ep3 and glitchy ep4 the same (TF:319-323). Gate-clean says nothing about whether the output is a melody (EXP:1463-1468: "a slow gesture over the clip, not a melody").
- **Trust now:** necessary, not sufficient.

### M18. Essentia `melodic` mood tag (and the 56-tag Essentia mood set)
- **Measures:** a classifier's "melodic" score, a mood, not a note-level property.
- **Numbers:** R^2 of the tag from SAME latent mean+std 0.392 (calm 0.586, dark 0.403, energetic 0.110, shuffled -0.018) (`docs/mf2-mood-deconf-review-2026-11-03.md:100-112`). Naive Melodic vs `Deconf_Uplifting` was not like-for-like; like-for-like `Deconf_Melodic` on Goa is flat (+0.005 to +0.012); "over 16 model x gain cells naive raises `melodic` more in 12" (review:128-135). Space and Dark vectors contain melodic directly (0.204, 0.159) (review:138).
- **Trust now:** low as evidence about melody. It was used as a steering target and as a side-effect readout ("kept more melodic" is partly a weaker push). One prompt, one seed, no noise floor.

### M19. SAME linear readouts of melody: Head A contour classifier, ridge pitch probes, subspace energy share, interval-resolution ladder
- **Measures:** how readable pitch and contour are from the latent.
- **Numbers:** pitch is linearly readable on synthetic MIDI, ridge R^2 0.86-0.97, in a roughly 15-dim distributed subspace (WL:2211); LOTO pitch transfer 0.679 [0.55, 0.78] (v1's 0.74 was optimistic; flute 0.25); sweep-derived atlas does not transfer to patterns (MAE 11-12.5 st) (WL:2212). Lone fifth-jump frame-detectable at least 91% at all 20 BPMs (WL:2212). Head A on real mixes: macro-F1 0.273 / bacc 0.280 (chance 0.125), failure mode lead presence, acceptance r=0.083 FAILED; open suspect "target noise" (WL:2218). Interval ladder: minor 2nd ||dz|| 10.63 (0.94 of a fifth), SNR vs codec 1.20x; 15-dim subspace melody-share 0.088-0.108 vs codec 0.073-0.080 vs random 0.059, so "#59 target subspace is only weakly melody-selective" (VERDICT:12-37).
- **Generated melody-energy share:** v3 subspace share in generated latents 0.029 +/- 0.011 for the 24-epoch K=5 run vs 0.023-0.025 for each 3-epoch ablation arm (TF:446-466 section "Measurement agrees but is weak"). D10: heavy-tailed sampling updates, melody no more than a random subspace, closed negative (EXP:1177; DISCOVERIES.md:277).
- **Failures:** the "melody" subspace is partly codec noise and partly static fingerprint; Head A's low score may be target noise rather than a representation limit (WL:2218).
- **Trust now:** medium for "pitch is linearly there"; low for "this scalar is melody".

### M20. Bungee pitch-shift as a positive control (E21)
- **Measures nothing about the model**: shifts k=0 steered renders by 3/6/9 semitones with bungee (never sox) so the transposition meter must report the shift (`eval/e21_bungee_posctl.py`).
- **Result:** meter valid: 24/24 first run; 84/84 after the bug fixes; 42/42 both bands in E21c (EXP:1874). It is what let E21 conclude hpcp and the E13 head are equivariant (33/42 -> 42/42 at gain 2048).
- **Trust now:** high. A model of how to build a control. Not applied to the MuScriptor F1 meter (UNSOURCED whether the F1 meter was ever bungee-shifted).

### M21. Synthetic-MIDI soundfont batteries (latent_melody_analysis v1/v2, same_chroma Tier-1, E23a/b)
- **Measures:** ground-truth lines rendered with fluidsynth GM programs (900 renders: 19 patterns x 4 tempos x 10 timbres), then encoded, probed or fed to a conditioner.
- **Findings:** the encoder is NOT the melody bottleneck (fifth-jump >= 91% at all 20 BPMs, WL:2212); the audio meter can read clean contours (E23a, M9); the Head-B conditioner does not follow them (E23b: follow, fed line minus its mirror, step4000 -0.01 / -0.08 / +0.08, step10000 +0.05 / +0.04 / -0.00 at gains 1/2/4; shuffled |0.11-0.21|, null |0.07-0.21|; 132 clips; EXP:1898-1900).
- **Failures:** pitch atlases from sweeps do not transfer across register (WL:2212); per-timbre statements replace general ones (flute 15 ch, synthbrass, epiano above R^2 0.5); synthetic air band was "register-limited" and misread as head weakness (M5). E23a does not test pads and leads competing in a real arrangement (EXP:1898, "not lower over the backing").
- **Trust now:** high as a ceiling check; it is the only place the meter has a known-answer at scale.

### M22. Melodic-movement / chroma-flux ladder (`mir/src/tools/melodic_movement_ladder.py`)
- **Measures:** chroma flux across a2a noise levels; found it floors at nl .4-.55 (-20% vs source) and overshoots at .7 (U-shape), matching Kim's ear that a2a melodies go "stereotypical" there (W journal:341-350).
- **Trust now:** medium; explained the ear, did not discover it ("ear wins, regime explains").

### M23. Register / f0-height probe (`eval/musicology/z_f0height_probe.py`) and pitch-height fields
- **Measures:** whether absolute pitch height is in the latent.
- **Failure:** reported corr 0.214, MAE 66 semitones ("register is not in the latent"); the script raised `TypeError` on every variant and trained on raw semitones while evaluating un-standardised; fixed: corr 0.511 linear / 0.561 MLP, MAE 6.4 st; always guessing the mean scores 8.05 (CLAUDE.md "AUDIT THE INSTRUMENT" case 2). I did not find the result file (UNSOURCED beyond CLAUDE.md).
- **Why it matters:** every pitch field in the store before 2026-08-12 was octave-folded pitch class, so "rising line vs its inversion" was inexpressible (W journal:803-809).

### M24. f0 head steering meters: rising-minus-falling slope, E4b follow score, D16 period sweep
- **Measures:** how far the Melodia curve of a guided render tilts toward a requested up/down or arch/valley shape; follow = corr with target minus corr with its mirror (chance 0, max 2).
- **Numbers:** lead head rising minus falling +7.4 / +11.0 / +22.1 st per clip at gain 512 / 2048 / 8192 (12/12), bass head no separation; E4b up/down +0.81 / +1.12 / +1.28 and arch/valley +0.63 / +0.94 / +1.14 at 8192 / 16384 / 32768; same measure on spectral centroid +0.15 to +0.35 (so a side effect cannot be excluded); D16 follow +0.16 at 10 s period, -0.08 at 5 s, -0.07 at 2.5 s, -0.04 at 1.25 s, -0.02 at 0.625 s (EXP:708-709, 1463-1468).
- **Caveat stated by the authors:** "Baseline correlations with slow targets are large by chance (0.52 at 10 s), so slow-period numbers are noisy" (EXP:709). E2: retrained f0 head intervals all span 0 (EXP:1455).
- **Trust now:** medium; it measures a slow gesture, not a melody.

### M25. CFG-null configuration of the conditioning stream (an instrument setting, not a meter)
- **What went wrong:** the per-frame `mir_ctrl` stream went to both CFG branches by default, so at cfg 7 the text was scaled 7x and the stream was not. With zeros in the uncond branch (`dit.py` `modular_cfg_null`), the same checkpoint and seeds moved from fed-minus-shuffled +0.151 [+0.050, +0.249], 30/48 to +0.467 [+0.392, +0.543], 46/48, gate 0/48 (TF:685-687; EXP:1906). D15's August eval had the roll in both branches (EXP:735). Consequence: "melody does not transfer" (D15 first verdict, MASTER section 5 arrangement-only reading of `target_raw`) was measured with control unscaled (TF:689-691).
- **Trust now:** any pre-2026-11-03 per-frame-inlet null is not a verdict (TF:687). Cross-attention adapters already used a null uncond, so this does not rescue the morph lane (EXP:1906).

### M26. Human rating UI (A/B questions and 0-5 enjoyment)
- **Measures:** Kim's pairwise choice on 6 question axes and a 0-5 enjoyment rating. Counts in `eval/ratings_export_2026-09-08.jsonl` (3078 rows): 1153 A/B, 1925 enjoyment; enjoyment values 4: 573, 3: 530, 5: 319, 2: 246, 1: 164, 0: 93 (my count). Question ids: interesting 292, top_end 300, spectral_image 291, structure 124, clarity_meaning 120, production 13, preference 13 (my count; list matches `eval/build_concordance.py:44-56`).
- **Blind spot:** none of the question ids is "melody", "tune", or "hook". "Interesting" and "structure" are the nearest proxies. This is the project-level reason melody judgments exist only as free-text ear notes (section 3).
- **Trust now:** the verdict of record (TRAINING.md D26: "Kim's ear is the verdict that closes an experiment"), but it does not ask the melody question.

### Summary table

| # | Meter | Sees | Blind to | Positive control | Negative control | Trust now |
|---|---|---|---|---|---|---|
| M1 | raw chroma cosine | key / harmonic bed | tune vs key, collapse, timing | none on goa | matched 0.997 vs null 0.995 (air) | do not use alone |
| M2 | demeaned / null / z-norm / shuffle | track-specific chroma identity | timing (demean is time-avg), fingerprint | air 0.918 (demeaned) | null ~0; shuffled 0.401 (air z-norm) | medium (identity), low (melody) |
| M3 | patch recurrence | looping | melody content | novelty -50..-70% at nl .55-.60 | frame-cos 0.99 everywhere | OK for loops |
| M4 | whitened chroma recurrence | returning motifs (harmonic proxy) | lead contour, magnitude | none stated | coin flip per cell (51-59% up) | low |
| M5 | same_chroma readout (cos12) | pitch-class energy per band | per-note, frame argmax | bass/mid 0.79-0.86 (synthetic) | air 0.054 (synthetic, misread) | medium-high |
| M6 | delta cos12 vs gain-0, hit rate | chroma steering authority | melody; target/sampler bugs | bungee 84/84 | 2/1715 unsteered cells | medium-high (relative) |
| M7 | HPCP / MERT layers | harmony (HPCP) | tuning offset, layer-specific | hpcp 42/42 after fix | "dead" label from wrong layer / A-bin | usable post-fix |
| M8 | MuScriptor F1 etc. | notes in time | legato, stems, SDEdit renders | F1 0.653 fed / source 0.609 | 0.045 none, 0.094 foreign | highest, with arms |
| M9 | Melodia | dominant line shape | notes, window length | r 0.999 (synthetic) | -0.15..0 other line | good for slow shape |
| M10 | Demucs other | stem isolation | bleed; OOD for MuScriptor | path reproduces 1.000 raw | n/a | needed for like-for-like |
| M11 | pitch-curve Pearson r | whole-line shape | note detail | own +0.431 | foreign -0.066 | medium (ceiling 0.43) |
| M12 | K&P contour symbols | rank-order contour | absolute pitch; extractor error | own 0.146 (failed!) | wrong stem 0.08-0.13 | exact symbols: no |
| M13 | MERIT S_mel | learned melody similarity | goa-vs-goa (saturated) | self 1.000 | different refs 0.611 mean | low |
| M14 | pitch-blind onset timing | onset alignment | pitch, content | 0.795-1.000 all arms | same | do not use |
| M15 | Audiobox PQ / CE | production, enjoyment | melody presence (d -0.10 / +0.22) | n/a | lead vs no-lead flat | quality only |
| M16 | hook metrics | motif repetition of lead | no-lead clips (NULL 66-81%) | decile 56x vs 0x | cfg16 collapse | medium, descriptive |
| M17 | disintegration gate | buzz / drift | melody | n/a | n/a | necessary not sufficient |
| M18 | Essentia melodic tag | mood label | notes | R^2 0.392 | shuffled -0.018 | low |
| M19 | SAME linear readouts | pitch linearly present | contour from mix (F1 0.273) | R^2 0.86-0.97 synthetic | chance 0.125 | medium |
| M20 | bungee shift | (control) | n/a | 84/84 | n/a | high |
| M21 | synthetic MIDI batteries | (known answer) | real arrangement | corr 0.999 | other line -0.15..0 | high as ceiling |
| M22 | chroma flux ladder | melodic movement per nl | n/a | explains Kim's ear | n/a | medium |
| M23 | f0-height probe | register | n/a | corr 0.511 / MAE 6.4 | mean-guess MAE 8.05 | medium |
| M24 | f0-head slope / follow | slow pitch tilt | notes | follow up to 1.996/2 (E4b on synth) | mirror; centroid +0.15..0.35 | medium (gesture) |
| M25 | CFG-null stream setting | (config) | n/a | +0.467 | +0.151 | fixed 2026-11-03 |
| M26 | rating UI | enjoyment, 6 axes | melody as a question | n/a | n/a | verdict of record |

---

## 2. Chronology of instrument failures and what each overturned

Dates are the date the failure was found or reported.

| Date | Instrument | What it first said | What corrected it | What it overturned | Source |
|---|---|---|---|---|---|
| 2026-06-19 | raw chroma correlation (riffer adapter) | success, twice | collapsed adapter still scored about 0.9; cross-reference audio diff | two declared wins | W journal:259-266 |
| 2026-06-28 (read 07) | MERT upper layer on LatCH sweep | two best heads "dead" | mid MERT layer for energy heads; upper layer is melody/harmony and blind to bass-RMS | head ranking; `hpcp` "dead at any weight" survived until 10-28 | MASTER.md:1036-1042 |
| 2026-07-01 | onset-authority metric | 12.9 onsets/s for "drone with low-volume hats" | Kim's ear | the metric as a judge ("numbers are instruments, audition is the verdict") | C journal (onset gameable); DISCOVERIES.md:73 |
| 2026-07-07 | discovery grep missed WORKLOG | "chroma-conditioning code-only, data never generated" | WORKLOG 06-25 held the full result; essentia hpcp_ts = garbage recipe | a todo | C journal:418-430 |
| 2026-07-11 / 07-30 | onset Ph3 | "onset +2 raises 5.7 to 6.8/s" | re-measure: 0.17 onsets/s at flatness 0.64 = disintegration | the claim, before the buzz gate existed (mandated 07-20) | C journal 2026-07-30 |
| 2026-07-12 | MuScriptor package | n/a | three faults all unverifiable-ground assumptions | package paths, not logic | W journal:658-664 |
| 2026-07-22 | chroma melody-turning probe | NEGATIVE 0/12 | head authority "slow-harmonic tint (~+0.03 cos), ~10x short of a pitch flip" | guidance route closed, conditioner route is live | WL:2213 |
| 2026-08-04 | whitened chroma recurrence (melody wall) | inconclusive / near-noise | later 08-06 ladder (displacement saturates) | the interpretation of the null | C journal:1322-1337; VERDICT.md:22-27 |
| 2026-08-06 | interval-resolution ladder | "a small second is below the noise floor" (Kim's worry) | ladder: semitone 0.94 of a fifth, SNR 1.20x | the premise; but also showed the #59 subspace is weakly melody-selective | VERDICT.md:10-37 |
| 2026-08-11 | Tier-2 raw cosine | matched 0.997 vs null 0.995 | derangement nulls, corpus demeaning | "head reads everything perfectly"; air reversed (0.054 to 0.918) | Tier-2 REPORT:12-36 |
| 2026-08-12 | PitchYinFFT f0 (proposed "free" melody) | free, already computed | prototype on one track: 28.4% steps <= 2 st, 10% octave jumps vs Melodia 96.9% / 0.0% | a public wrong prescription | W journal:811-816 |
| 2026-08-12 | store hardcoded `.flac` | n/a | 818/4461 (18%) folders carry `.mp3` | silent coverage hole correlated with separator | W journal:817-823 |
| 2026-08-12 | sidecar integrity floor (46 fields) | "INTEGRITY FAILURE" | measured 38/44/46/48/50 | a false alarm in the verifier | W journal:829-834 |
| 2026-08-21 | Tier-2 air 0.918 as melody | melody | D11 frame shuffle: fingerprint fraction 0.52-0.60 | "0.918 = melody" | EXP:1195-1200 |
| 2026-08-26 to 28 | D15 chroma screen | true-minus-shuffled +0.022 n.s. | MuScriptor: +0.100, 6/6, p=0.016 | "follows pitch, loose on timing" | EXP:749-776 |
| 2026-08-28 | onset "timing" | n/a | saturated 0.795-1.000 incl. foreign | uninformative; do not quote | EXP:772 |
| 2026-08-28 | single-window screen | true-shuffled +0.12 | 20 note-bearing frames; six tracks gave +0.022 (chroma) | "follows the roll" | EXP:791-794 |
| 2026-08-28 | `z_f0height_probe.py` | corr 0.214, MAE 66 st | TypeError on every variant, raw semitones; fixed corr 0.511 / 0.561, MAE 6.4 vs mean-guess 8.05 | "register is not in the latent" | CLAUDE.md |
| 2026-09-03 | D16 premise | quoted D15's retracted +0.022 | C coverage audit | D16 re-scoped to "how fast a trajectory" | WL:2419; EXP:710-713 |
| 2026-09-04 | MERIT S_mel; D15 transcription on contour; contour-to-contour | +0.0247, 48/64, p=7.7e-05; six nulls; 0.146 | foreign arm +0.041 > own; own-vs-foreign gate; positive control 0.146 < 0.151 | three publishable-looking numbers | C journal:2444-2470; WL:2420 |
| 2026-09-09 | PQ/CE on melody | n/a | lead/no-lead split: d -0.10, +0.22 | belief that existing metrics could model the 4-vs-5 gap | G journal:951-985 |
| 2026-09-24 | training-time instruments (loss halved, NaN-blind guard, SF swap skipped ModularOpt) | healthy | TF section B items 7-9 | runs judged on wrong numbers | TF:204-215 |
| 2026-10-15 | click meter and val loss on air-head glitches | ep3 and ep4 equal; val points to ep16-17 | Kim's ears | checkpoint choice | TF:319-323 |
| 2026-10-28 | E21 bass-root argmax, HPCP bin 0 = A, gain-0 via wrong sampler | steering follows k, off-target | fixes in `chroma_steer_render.build_target_raw`, `HPCP_BIN0_PC`, `base0__` baselines | every earlier hpcp steering result; MASTER "dead" label | EXP:1874; W journal:1148 |
| 2026-10-29 | Melodia contour symbols (D17) | exact symbols scored reference 0.12 vs 0.08 wrong stem | Pearson r curve, own +0.431 vs foreign -0.066 | the old meter measured the wrong quantity | EXP:1293; `morph_f0_contour_ab.py:5-25` |
| 2026-11-03 | CFG on the stream | D15 / mir_ctrl weak: +0.151 | zeros in uncond branch: +0.467 [+0.392, +0.543] | "melody does not transfer" | TF:685-691 |
| 2026-11-03 | E24 eval 1 | n/a | one prompt+seed: every render one held note | whole eval uninformative | EXP:1912 |
| 2026-11-03 | true-minus-shuffled on each arm's own stream | about 0 | both arms follow | scoring design error caught on first read | W journal:1197 |
| 2026-11-03 | `expandable_segments` set by an import | NaN / unsteered cells blamed on empty_cache | isolation: no faults in 1,980 clips | W's own prior explanation | W journal:1190 |

---

## 3. Every listening verdict on melody I could find

HEARD only. Quotes are verbatim from the cited line.

| Date | Material | Verdict | Source |
|---|---|---|---|
| 2026-07-07 | chroma-morph transition `kaikki2angelic__w1024_nl42_chroma.wav` | "The chroma steered versions rock so hard, this is honestly one of the coolest things I've heard in my nearly 30 years of music." (nl35 "gallops a bit"; kicks in sync, "transformation practically seamless") | C journal:445-455 |
| 2026-07-07/08 | a2a ladder at nl .4-.55 | melodies going "stereotypical"; W's chroma-flux floor at -20% explained it | W journal:341-350 |
| 2026-07-07 | stale refine clip (slerp midpoint + nl .55) | "actual noise... translated to some kind of airy constant drone; both tracks lose identity" | C journal:457-461 |
| 2026-07-23 | fp32 / full-FT policy (not melody-specific) | "models just about start to sound fine after ep5, and often 7 is the first really good one" | TF:101-110 |
| 2026-08-28 | D15 pianoroll true / shuffled / foreign | "true & shuffle have very identical notes; foreign seems to be in a different key" | EXP:749-752 |
| 2026-08-28 | consonance question | semitone error "treats C to C# and C to G alike, which is musically wrong" (a request to change the meter) | EXP:765 |
| 2026-09-09 | morph conditioner bracket (read before D17) | "now that the conditioner did something, a model with more weight in training might bring up something" | EXP:1291-1330 (D17 Why) |
| ~2026-09-04 | full-FT morph arms | sound like "weird glitchy organic noises" while base arms respond at gain 2.0 (as quoted in the MERIT script docstring) | `eval/morph_merit.py:7-12` |
| 2026-09-04 | morph conditioning on the Pattern-2 full-FT backbone | meter degrades 60/64 cells, S_tim 0.373 to 0.169, noted in the log as "matches Kim's ear" (a log statement, not a new verbatim verdict) | WL:2420 |
| 2026-09-27 | `goa5k_r128_shampoo_subloss_k5_2026-09-26` step 8088 | "has the most distinct melody"; "practically a kickless section"; kl_2: "can also have a punchy beat and still melodies, it is noticeably more melodic than of the ablation runs"; "the subspace thingy actually seems to work, although at the cost of bass sometimes" | `Misc/models_index_overrides.json` (key `goa5k_r128_shampoo_subloss_k5_2026-09-26`, kim_feedback); TF:446-452 |
| 2026-09-27 | verbatim summary | "now that I listened for the first time across all of my models, I have to say the subspace stuff really seems to work." | TF:448-449 |
| 2026-09-27 | `subloss_v3sel_k5` ep19 / k2 ep19 / k12 ep15,19 / k5_tgate ep11 | "This just... Superb"; k2 "also just superb, more aggressive"; k12 "coool"; tgate "very cool goa sound" | TF:450-452 |
| 2026-09-27 | `fullft_goa_t256` ep19 rb_mid_5 | "very good melodie on this ckpt but sound is quite hot (very sharp, lacks bass) But mixing this 50/50 with Base Medium might yield good stuff." | models_index_overrides.json (`fullft_goa_t256`) |
| 2026-09-27 | `winning_goa_t512_a45_bf16` ep50 kl_2 | "very good melodies, but very hot and thin sound" ("problem territory") | models_index_overrides.json |
| 2026-09-27 | `ablation_goa5k_a00_full` step 1011 | "melodically still very club trancey" | models_index_overrides.json |
| 2026-09-27 | `a02_no_brake` rb_mid_4 | "a quite genre-accurate midrangey phrygian bass melody, pads and atmosphere, but barely any kick" | models_index_overrides.json |
| 2026-09-27 | `a07_no_normuon` | "melodies more subdued"; `a08_no_subspace`: "Melody similar-ish to the subloss run" | models_index_overrides.json |
| 2026-10-16 | production same_chroma head, all-C sweep | steers "transparently (pad chords change their notes)", most audible at gain 2048 | EXP:1677-1680; DISCOVERIES.md:89 |
| 2026-10-15 | air head epochs | glitch-free through ep3 for O5; "spectral smoothing" dropouts from ep4 | TF:319-321 |
| 2026-08-04 (queue) | melody wall subloss_k2 vs baseline top cells | ears pending at that time; later answered 09-27 above | KIM-TASKLIST.md:394-398, 534-535 |

Not heard (flagged "Not listened" in the source): E13/E13x chroma steering at high gain, E21/E21b/E21c transposition, E22 root-locked, E4/E4b/D16 f0 heads, E23, E24 arms B/C, D15 11-03 re-read and invented-melody clips, D17 A/B (EXP:1293 "Not listened"). The Muon guide DRAFT header also states "nobody has listened to the selected excerpts yet" (blog draft:10-12), unrelated to melody but the same pattern.

Rating-data side: no rating question asks about melody (M26). I did not find a join of ratings to melody features (B13 Test 1 is unrun as far as the sources show).

---

## 4. Meters vs ears: where they disagreed

| # | Case | Meter said | Ear said | Resolution | Source |
|---|---|---|---|---|---|
| 1 | D15 pianoroll, 2026-08 | chroma true-minus-shuffled +0.022 n.s. ("loose on timing") | "true & shuffle have very identical notes; foreign seems to be in a different key" | Both halves right: key is adopted (0.952 vs foreign 0.169), and chroma could not separate key from melody; MuScriptor gave +0.100, 6/6 | EXP:749-776 |
| 2 | Melody-subspace loss, 2026-08 to 09 | whitened recurrence +10-16% rel, coin-flip per cell, non-monotonic K; PQ/CE/CLAP "k2 costs more than it gives" | "the subspace stuff really seems to work"; k5 "most distinct melody" | Unresolved by a meter. Generated melody-energy share 0.029 +/- 0.011 vs 0.023-0.025 "agrees but is weak". The recorded policy follows the ear (F18) | TF:446-466; C journal:1322; KIM-TASKLIST.md:394-398; TRAINING.md F18 |
| 3 | Onset density request | 12.9 onsets/s for "low-volume rapid hats" | heard instantly as wrong | Standing rule: audition is the verdict | C journal "onset-authority gameable" |
| 4 | a2a at nl .4-.55 | (no meter at the time) | melodies go stereotypical | chroma flux floor at -20% found after the ear | W journal:341-350 |
| 5 | Loops at nl .55-.60 | frame-cosine recurrence 0.99 everywhere | ear: looping at .55+ | patch-level meter matches the ear | W journal:106-126 |
| 6 | Air-head epochs | click rate lowest for O5 ep2-5; val loss best at ep16-17; PQ varied 0.13 | glitch-free through ep3, dropouts from ep4 | ears chosen over three meters | TF:319-323 |
| 7 | Buzz heads | authority pipeline tagged "working" | Kim heard buzz | disintegration gate mandated 2026-07-20 | MASTER.md:516-520 |
| 8 | Morph, full-FT backbone | conditioning degraded 60/64 cells, S_tim 0.373 to 0.169 | "weird glitchy organic noises" | meter and ear agreed on damage; neither saw melody transfer | WL:2420; `morph_merit.py:7-12` |
| 9 | MERIT S_mel gain 2.0 | +0.0247, 48/64 positive, p=7.7e-05 toward reference | n/a | foreign arm rose more: style shift, not melody | C journal:2448-2452 |
| 10 | Cross-optimizer soup blend ratio | metrics flat across 10-30% | the 25/75 soup is better by ear | "invisible to MERT/Audiobox" | C journal 2026-07-xx "cross-optimizer soup blend" |
| 11 | Subloss "cost of bass" | kick/bass thinner is not a melody metric | Kim hears it ("kickless section") | counter-measure suggested (low-band term / lower K) | TF:454-457 |
| 12 | MuScriptor-based "no lead" | 32-84% of renders have no lead everywhere vs corpus about 5% | n/a (not heard) | could be real melody collapse (P2 cfg axis) or transcriber failure on fast codec-decoded material | WL:2214; W journal:643-646 |

---

## 5. What no meter we have can see yet, and what one would need

1. **A melody preference or quality judgment.** No meter outputs "is this a good tune". The only judge is Kim's ear and the rating UI has no melody question (M26). A meter would need ground truth from ratings: add a melody/hook question to the A/B set and run B13 Test 1 on existing 4s vs 5s.
2. **Pitch and rhythm of the lead inside a dense polyphonic goa mix.** Melodia reads the dominant line; MuScriptor collapses to the bassline on full mixes and degrades on stems (M8, M9, M10). A meter would need either a lead-aware transcriber validated on mixed goa with known notes (E23a-style synthetic leads at multiple levels over real drums, pads competing) or a stem separator the transcriber is calibrated on.
3. **Held notes and legato.** MuScriptor drops sustained notes over 1 s (about 0 on every source). A sustained-note recovery rung is called for in the 2026-07-20 spec but its measured outcome is not recorded (C journal:943-950).
4. **Rendered-clip contour at the resolution the conditioner is trained on.** Melodia is window-dependent (52% agreement), so the fed stream cannot be reproduced from a 47 s render (M9). A meter would need the fed stream's extractor to be run with the same window the conditioner saw, or a contour extractor that does not depend on input length.
5. **Per-note timing independent of key.** The only pitch-blind timing measure saturated (M14). Needs a pitch-aware onset F1 with a shifted-onset negative control.
6. **A melody-specific content readout from the latent that is not a trained surrogate.** Head A at F1 0.273 and acceptance r=0.083, with "target noise" an open suspect (M19, WL:2218). Needs targets from a transcriber validated on stems or synthetic mixes.
7. **Does the output "play a tune" or "pin notes to frames"?** Two E24 arms both follow shape over seconds (+0.467) but not notes (within a semitone 14% vs 12% no-stream). Meters for tune-ness (singability, motif return) exist only as hook metrics on MuScriptor MIDI (M16), unvalidated against ears.
8. **Human-vs-meter calibration on melody.** There is no ratings join. B13 would provide the first; power bound d >= 0.26 at n5=154.

---

## 6. Possible blind spots nobody seems to have asked about (SPECULATION, mine)

Labelled speculation: none of these is sourced as asked or tested.

1. **Transcriber self-consistency across training and test.** The invented-melody result (73% fed pitch) is scored by the same family of model that produced the training rolls. The independent Melodia check agreed (74% within 1 st), but both are monophonic-lean pitch readers over a likely simple, synth-lead timbre. Whether the model learned "notes" or "a transcriber-friendly stimulus" is not separated.
2. **Dynamic range of the meters at the level of goa leads buried at -10 to -15 dB.** E23a mixed at 0 dB over drums and bass only. Real arrangements bury the lead, which is also where the model's own melody might live.
3. **Octave handling asymmetry.** Several meters fold octaves (Melodia "up to octave", chroma, E4b), but Kim's complaint (register, rising line vs inversion) is about height. M23 reports corr 0.511 only.
4. **CFG scale as a hidden coordinate of every melody null before 11-03.** The CFG-null finding implies any control stream put through any other inlet that is not null-conditioned could have been under-scaled. I did not audit which other nulls (for example Head-B at cfg 1 INERT, cfg 7 weak, cfg 16 positive in the July bracket) share the same mechanism. The July Head-B bracket already shows strong cfg dependence.
5. **Selection by coverage.** MuScriptor outputs "no lead" for 40% of renders. Any melody score computed on only the clips with a lead is conditioned on the model already producing one. This is flagged in B13 but not for D15 or E24 aggregates; I did not check how many clips were dropped in each.
6. **EMA and the meter.** The renders under many morph and drone results came from EMA shadows that started at the zero-init adapter (EXP:1291 status block). A positive result is not produced by a meter fixed for that, and a null may be partly the render weights. D17 checked deconvolved weights (no better), but the earlier morph-grid audition (384 cells) used EMA.
7. **Ear fatigue and seed: n=1.** Kim's melody verdicts on 09-27 are per cell (single prompt, single seed) in a long pass; no melody-specific blinded A/B has been run.
8. **Time-scale mismatch.** D16 puts the ceiling above a 10 s period for f0 heads while note-level control works through the per-block inlet; the two lanes are measured with different meters (Melodia curve vs MuScriptor F1), so "ceiling" is not comparable across lanes.
9. **Melodic identity vs genre identity.** Demeaned chroma removes "generic goa" but also removes shared motifs that Kim may hear as the genre's melody. The musicology study found a rolling same-note 16th pedal in 91% of files (WL:2208); if the "hook" is partly the pedal, the demeaning meter would erase it.

---

## 7. Recommended minimum test any future melody claim must pass

Built only from the failures above. Each item names the failure that motivates it.

1. **State which of four things you claim:** key / pitch set / note placement in time / contour or whole-line shape. Pick a meter that can see that one (D15: chroma saw key only; MERIT, pitch-class cosine, Jaccard, note-cell F1 are blind to contour-only conditioners, C journal:2457-2462).
2. **Four arms always:** fed, shuffled-in-time (same notes), foreign (different melody and key), no-stream. Report differences between arms, never an absolute (D15, MERIT +0.0247 and the foreign arm; M1 matched 0.997 vs null 0.995). Do not score shuffled against each arm's own stream (W 11-03 error).
3. **A known-positive and a known-negative run through the same path before any render is read:** reference audio through the identical extractor (D17 own +0.431 vs foreign -0.066; contour-to-contour failed at 0.146 < 0.151), synthetic MIDI lines with known contour (E23a), and a bungee pitch-shifted copy where transposition matters (E21 24/24 to 84/84). The gate must be FATAL, not printed (C 09-04).
4. **A trivial baseline stated with the number:** the no-stream render, mean-guess (8.05 st), a random subspace (D10), the corpus-mean profile (demeaned cos12). "MAE 6.4 st" means nothing without 8.05.
5. **Same-seed unguided baseline through the same sampler** (gain-0 via `generate()` without `latch_configs` gave CE about 3 vs 6-7 and flipped a sign, W 10-28).
6. **Stream scaled by CFG** for any per-frame inlet: zeros in the uncond branch (`modular_cfg_null`), otherwise the verdict is not a verdict (+0.151 vs +0.467).
7. **Multiple prompts, seeds and windows.** One window gave +0.12 on 20 note-bearing frames; six tracks gave +0.022 (D15). One prompt and seed made E24 eval 1 uninformative. Use confidence intervals and paired sign counts (as D15 11-03 and E24: [+0.392, +0.543], 46/48).
8. **Coverage and drop counts reported:** voiced fraction (E23a steps_big 0.46), no-lead share (40%; B13), clips dropped by integrity (448/1200 in Tier-2). Never average a conditional metric over unconditional clips.
9. **Frame-shuffle (or equivalent) null for any readout that smells of fingerprint** (D11: 0.52-0.60 of identity signal static). Report the shuffle-surviving share beside the headline.
10. **Gate the output:** disintegration gate against the unsteered baseline (flatness, hf, zcr, CE drift), but also check it is a melody and not an existing voice getting louder (E4 caveat; spectral centroid follow +0.15 to +0.35).
11. **Independent second meter** when the scoring model made the training targets (MuScriptor + Melodia, D15 independent check 74% / 43% / 17% / 18%).
12. **Label every result MEASURED or HEARD.** The default tag "not heard" appears on every 11-03 result; do not move to "works" without the ear (D26), and note that no melody rating axis exists.
13. **Do not call a null until the audit is written down:** dynamic range, baseline, has the tool ever produced a positive (CLAUDE.md AUDIT THE INSTRUMENT, case list).

---

## Source index (primary files read)
`EXPERIMENTS.md` (D10, D11, D15, D16, D17, B13, E4, E13, E21-E24 entries), `docs/training-findings.md` (sections B, 2026-09-27, 2026-11-03), `profiles/wintermute.journal.md`, `profiles/continuity.journal.md`, `profiles/ghost-note.journal.md`, `WORKLOG.md` (2208-2218, 2266, 2419-2420, 2918), `MASTER.md` (516-530, 780-783, 1036-1055), `DISCOVERIES.md`, `docs/mf2-mood-deconf-review-2026-11-03.md`, `docs/superpowers/specs/2026-07-20-note-following-eval-design.md`, `eval/musicology/{same_chroma_readout_2026-08-11, same_chroma_readout_tier2_muscriptor_2026-08-11, same_chroma_E2_perwindow_norm_2026-08-12, same_chroma_D11_frame_shuffle_2026-08-21, same_chroma_stem_vs_mix_2026-08-12, interval_resolution_ladder_2026-08-06}`, `eval/{morph_f0_contour_ab,morph_merit,e23a_contour_meter,d15_melodia_check,e21_bungee_posctl,midi_metrics_ingest,melody_wall_analysis,muscriptor_decode_gate,build_concordance}.py`, `eval/muscriptor_gate.json`, `eval/ratings_export_2026-09-08.jsonl`, `Misc/models_index_overrides.json`, `KIM-TASKLIST.md`, `CLAUDE.md`. Not re-run or re-measured: every number above is a transcription of a recorded result. Items I could not source are marked UNSOURCED inline (z_f0height result file; whether the F1 meter was ever bungee-shifted; B13 Test 1 outcome).
