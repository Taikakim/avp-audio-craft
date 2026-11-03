# Review: de-confounded mood targets and the Music Flamingo 2 mood mining (2026-11-03)

Owner of the review: CONTINUITY. Work under review: ANTIGRAVITY, 2026-11-03 (`eval/render_mood_deconfounded.py`,
`eval/build_mood_finegrained_page.py`, and scratch scripts for the mining). Everything here is measured from data; nobody has
listened to these clips for this review. Scripts and raw output: `eval/mf2_deconf_review/` (`results/`). Derived data:
`/run/media/kim/Kosmos/captions/review_20261103/` (`arch_feats.npz` = per-track mean Essentia mood, genre, VA, bark and MAEST for
all 23,231 goa_archive tracks, 120 MB, 35 min to rebuild with `arch_feats.py`).

## Verdict in brief

| Claim | Verdict |
|---|---|
| Hinted captions fill up with genre boilerplate and lose mood words | **Confirmed**, on all 23,231 pairs |
| Unhinted mood words are "4x to 35x more acoustically honest" | **Not supported as stated.** Word frequency is not honesty. A real but much smaller audio advantage exists for some words, and those words also follow the wrong genre label |
| Eight mood axes exist in MF2's vocabulary | **Reproduced as text structure**, three of eight clear the usual stability bar |
| Three of those axes are moods Essentia lacks | **Not supported.** No axis but the first is shown to be in the audio at all, by Essentia or by the latent |
| De-confounded targets beat naive ones | **Open, and the reported table overstates it.** Selected cells from one prompt and one seed. W's 15-prompt run decides |

## 1. Genre hint and mood words (`word_rates.py`, `word_vs_audio.py`)

**Confirmed.** Rates recounted on all 23,231 pairs match the reported 3,000 (the 3,000 are the first by hash, so effectively
random). `dark` 49.2% unhinted, 12.6% hinted; `raw` 32.1% and 0.7%; `gritty` 28.6% and 0.9%; `hypnotic` 56.9% and 96.5%. The one
hint string is the same for every track. `psychedelic` (1.2% to 93.7%) is an echo, since the hint contains that word. Median caption
length is the same (2,097 and 2,122 characters). The "up to 57x" headline is not in the reported table; the largest I found is `raw` at 45x.

**Not honesty.** The reported factors compare how often a word appears, not whether it is true of the track. Three measurements
change the reading:

1. **The words follow the genre the model named, in both directions.** Inside unhinted captions, by what the first sentence calls the track:

   | Word | Named industrial, techno or EBM (n about 14,700) | Named trance or goa (n about 2,600) |
   |---|---:|---:|
   | dark | 65.3% | 10.6% |
   | metallic | 58.2% | 2.4% |
   | raw | 46.2% | 0.5% |
   | gritty | 43.0% | 1.6% |
   | dystopian | 21.0% | 0.2% |
   | uplifting | 0.8% | 63.7% |
   | euphoric | 0.3% | 59.3% |

   And the named genre is mostly not what the audio shows: 63.8% of tracks are called industrial, techno or EBM, while Essentia's top
   genre is techno or industrial on 14.2%. Of the tracks so named, Essentia puts 73.3% on goa, psytrance or trance. So a large
   part of "raw, gritty, dark" comes with a wrong genre label, which is the same mechanism as the hinted boilerplate, pointing the
   other way.

2. **Same track, two captions, barely any agreement.** Correlation (phi) between a word in the unhinted and the hinted caption
   of one track: `dark` 0.044, `aggressive` 0.080, `metallic` 0.048, `raw` 0.053, `uplifting` 0.046. There are no repeat captions, so the
   test-retest ceiling is unknown.

3. **Against the audio, unhinted does better for some words, by a modest margin.** Held-out AUC, split by album, audio features
   (Essentia mood, valence/arousal, bark bands) predicting whether the word is present. The fair column is the middle one: it holds
   the named genre fixed, as the hint does.

   | Word | Unhinted, all | Unhinted, named industrial/techno only | Hinted |
   |---|---:|---:|---:|
   | dark | 0.667 | 0.635 | 0.571 |
   | aggressive | 0.753 | 0.720 | 0.607 |
   | metallic | 0.719 | 0.709 | 0.576 |
   | unsettling | 0.786 | 0.764 | 0.683 |
   | melancholic | 0.799 | 0.755 | 0.662 |
   | uplifting | 0.757 | 0.668 | 0.554 |
   | contemplative | 0.860 | 0.706 | 0.707 |
   | meditative | 0.827 | 0.715 | 0.742 |
   | ominous | 0.707 | 0.684 | 0.692 |
   | futuristic | 0.615 | 0.585 | 0.604 |
   | dystopian | 0.712 | 0.676 | 0.710 |
   | raw | 0.741 | 0.708 | 0.769 |
   | gritty | 0.692 | 0.628 | 0.701 |
   | brooding | 0.641 | 0.652 | 0.727 |

   Six words favour unhinted by more than 0.03, four favour hinted (on 75 to 220 hinted positives, so noisy), four are level. Against the
   single matching tag the effect is small: `dark` word vs Essentia `dark`, AUC 0.577 unhinted, 0.551 hinted, and 0.497 among
   captions that named trance.

**Meter check.** Known positive: a first sentence saying "ambient" vs Essentia's ambient genre, AUC 0.880, and vs `meditative`, 0.901. Known
negative: shuffled labels 0.500. Limit: the audio side is another classifier, trained on stock-music tags, not human judgement.

**What follows.** The hint did cost real information for some words (`dark`, `aggressive`, `metallic`, `unsettling`, `melancholic`,
`uplifting`). "Merge unhinted mood words with the authoritative genre" is a reasonable thing to try, not a shown improvement, and
"vastly more discriminative" has not been tested on any conditioning. Taking the word list wholesale would import the industrial
stereotype. E25 registers the cheap test.

### Merged captions already built on this

`eval/recover_mf2_lost_moods.py` (untracked, 01:10 on 11-03) builds "ready-to-train" merged sidecars, including `lumi/goa_longform_sidecar_merged.json`. Kim's decision on 2026-11-03: expected to be a noticeable quality improvement, hold lifted, E25b reads the words. It strips hinted `euphoric`/`uplifting` as hallucinated when the unhinted caption is dark-family (`contradiction_fixed` 7,460 of 23,232).
Check (`strip_check.py`, a proxy on MF2 full captions, not a replay of its Granite-tag rule): 4,863 tracks would be stripped, 5,002 kept. The audio leans the way the rule assumes, moderately: stripped tracks score
lower valence (AUC 0.61 and 0.63 on the two valence models) and higher Essentia `dark` (0.60). Essentia `uplifting` barely separates them (0.53), and the groups overlap heavily. So the rule points the right way
on average and is not a per-track truth; "hallucinated" is too strong. The claim that the original is 15-20% wrong was not measured here.

## 2. The eight axes (`axes.py`, `axes_latent.py`)

Reproduced exactly (these are hinted captions, `goa_src_captions`, so they carry the boilerplate section 1 describes).

- **Text structure is real but thin.** Parallel analysis supports 8 factors. They explain 26% of the variance of 55 terms.
- **Stability is mixed.** Split-half congruence per axis, sorted, mean of 10 splits: 0.29, 0.52, 0.68, 0.77, 0.83, 0.86, 0.88, 0.96. Three
  clear the usual 0.85. Several rest on rare words: `raw` 0.5% of tracks, `alien` 0.6%, `sci-fi` 1.5%.
- **Join size.** 5,400 crops cover 2,676 of the 4,461 tracks, not all of them.
- **Audio: this is the finding.** Reading axis scores from audio, holding out artists (600 artists, 2,676 tracks):

  | Axis (top words) | R² from 56 Essentia tags | R² from SAME latent mean + std |
  |---|---:|---:|
  | 1 contemplative, introspective, meditative | +0.058 | +0.039 |
  | 2 sci-fi, futuristic, robotic | +0.030 | +0.013 |
  | 3 raw, gritty, unsettling | -0.005 | -0.014 |
  | 4 mantra-like, ritualistic, spiritual | +0.002 | -0.018 |
  | 5 resonant, pulsating, energetic | -0.011 | -0.013 |
  | 6 uplifting, bright, euphoric | -0.003 | -0.005 |
  | 7 searching, dark, unsettled | -0.009 | -0.014 |
  | 8 otherworldly, cosmic, expansive | -0.009 | -0.011 |

  The same latent features, same split, read Essentia `calm` at R² 0.586, `dark` 0.403, `melodic` 0.392, `energetic` 0.110; shuffled -0.018.
  So the meter works, and these axes are not shown to be audio properties. "Missing from Essentia" cannot be told apart from "a
  habit of the caption model's vocabulary". The latent reading has one crop per track against a caption of the whole track, which weakens
  it somewhat, but the same limit applies to the known positives above. Individual words do better than the axes: `meditative` AUC 0.70 on
  both, `contemplative` 0.66 and 0.63, `robotic` 0.60 and 0.65. `searching`, called MF2's signature mood, is 0.551 and 0.510, and the hint
  raises it (8.8% to 24.5%).
- **Reported correlates.** "+0.80 to +0.90 sigma" for axis 1 is the single word `meditative`. Others on that axis are weaker
  (`calm` to Essentia calm: +0.23 by crop, +0.35 by track). Axis 7 "missing from Essentia" contains `dark`, which is an Essentia tag.
- **Stated mechanisms.** Mantra-like with spoken word: **supported**, 97.6% vs 30.2% of all captions. With Phrygian: not supported,
  0.0%. `searching` with half-diminished harmony: weak, 11.1% vs 7.6%. `uplifting` with minor-to-major colour: not supported on a crude
  text match, 11.5% vs 10.4%. All text-on-text, no audio.

## 3. De-confounded targets (`renders_naive_vs_deconf.py`, `renders_key_ce_floor.py`)

The 48 naive clips were not in the cached scores, so I scored them with the same meter (`EffnetMoodCPU`); it reproduces the cached
baselines to r >= 0.999, max difference 0.011. Quoted values check out within that. What the report leaves out:

- **One prompt, one seed.** Every cell is n=1, and the prompt already says "melodic mood". No noise floor. WINTERMUTE's
  `eval/mood_deconf_render.py` (15 prompts, 4 models, 1,980 clips) is the real test and is running.
- **Baseline.** The g=0 clips went through `generate()` with no config, the known confound (MASTER section 5). The percent changes from
  g=0 inherit it. Naive vs de-confounded at the same gain does not.
- **Different targets compared in row 1.** Naive Melodic is set against `Deconf_Uplifting`. The like-for-like `Deconf_Melodic`, not in the
  report, is just as flat on Goa (+0.005 to +0.012), and over 16 model x gain cells naive raises `melodic` more in 12. On Fusion+Goa at
  8192: naive +0.105, de-confounded +0.015.
- **`Deconf_Uplifting` does not move `uplifting`.** The "+85%" is 0.004 to 0.007, and on Base it falls. It raises `melodic` because melodic is the
  largest entry in its vector (0.355 vs uplifting 0.184).
- **De-confounded steers less.** It moves its own tag less than naive at the same gain: Space 0 of 16 cells better, Dark 2, Melodic 4. So
  "kept more melodic" at the same gain is partly a weaker push. The Space and Dark vectors also contain melodic directly (0.204, 0.159).
- **A real effect may remain.** Compared where both moved `space` about equally, de-confounded lost less melodic in 7 of 9 pairs (for example
  AdamW -0.083 vs -0.044). Dark has too few matched pairs to say: on Goa and Fusion+Goa, de-confounded hardly moves `dark`. The pairs share clips.
- **Dark's melodic rescue is Base only.** Goa at 8192: melodic -0.323 de-confounded, -0.261 naive, and `dark` +0.015 vs +0.051. Fusion+Goa
  -0.437 and -0.418.
- **Key lock is no better overall.** Key kept of 16: Melodic naive 15, de-confounded 13; Space 11 and 11; Dark 10 and 10. Goa `Deconf_Dark`
  leaves C major at every gain.
- **Audiobox enjoyment.** De-confounded higher in Dark 11 of 16 (mean +0.17), Space 12 of 16 (+0.11), Melodic 8 of 16 (-0.03). Base at 4096 +0.89 is
  right, and AdamW at 4096 and 8192 goes the other way (6.53 and 6.43 vs 6.93 and 7.08).
- **Library floor.** The drop is real on Base and AdamW (10 tags summed, -0.05 and -0.04 at 8192, naive Space -0.03 and -0.02), small on Goa and
  Fusion+Goa, where the floor is already low. Repulsion is not tested alone: no arm has it without the rest.
- **The target is not purely Kriging.** Negative entries are `0.35 * du / 3`, the library entries a fixed -0.15, ridge 0.15. Those are design
  choices with no sweep behind them, and it also has a different intent from naive (naive Melodic has three tags, `Deconf_Melodic` has one).

**What it does suggest, to carry into W's analysis:** on Goa, targets with melodic plus energetic (`Deconf_AntiDark`, `Deconf_Uplifting`) raise
`melodic` where a melodic target does not (+0.148 and +0.156 at 8192). Read on melodic, not on the tags they are named after, and only if it survives 15 prompts.

## 4. Practice notes

- The mining scripts lived only in the author's scratch folder; `antigravity_crossmodal_mf2_essentia.py` here is an unmodified copy, and the others
  are not copied.
- W republished `mood_finegrained` at 01:58 with the one-prompt Deconf results labelled one prompt, one seed, not established (WORKLOG). A rebuild can undo that text.
- Merged captions built on section 1: see above. Full inventory of this author's recent work: `docs/antigravity-work-2026-10-29_11-03.md`.

## 5. Addendum: E25b, the words by prompt (2026-11-03)

Single mood words appended to prompts barely move renders once placebo words are subtracted; none clears on the Goa LoRA, and `industrial` clears on neither model. Known positives (`solo piano`, `ambient, no drums`) do, so the meter works. This cannot judge the merged captions, because neither model was trained on these words: that needs a training comparison. Numbers: EXPERIMENTS E25b.
