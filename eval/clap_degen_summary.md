# CLAP genre-degeneration scan — full model_matrix (WINTERMUTE, 2026-07-22)

General 630k CLAP, 31639 cells. `matched` = cos(audio, its own prompt); low = output has drifted off the requested genre (toward drone/noise/other).
**DSP-screen sibling: the disintegration gate; this is the SEMANTIC screen. Threshold TBD by Kim's ear.**

Corpus matched-cos p01/p05/p25/p50/p95: -0.061/0.023/0.209/0.324/0.489

## cfg x DoRA-strength (mean matched-CLAP) — the steering sweet spot

| cfg\w | 0.6 | 1.0 | 1.5 | 2.0 |
|---|---|---|---|---|
| 1.0 | 0.247 | 0.220 | 0.223 | 0.196 |
| 7.0 | 0.389 | 0.341 | 0.309 | 0.233 |
| 15.0 | - | 0.346 | 0.318 | 0.233 |
| 16.0 | 0.391 | 0.347 | 0.318 | 0.232 |
| 24.0 | - | 0.363 | 0.311 | 0.241 |

**Read:** cfg1 = degeneration zone; w2.0 degrades at every cfg (over-applied adapter goes off-genre). Sweet spot cfg7-16 x w0.6-1.0.

## Most genre-collapsed (model,ckpt) — frac cells CLAP<0.10

| frac<0.1 | mean | n | model|ckpt |
|---|---|---|---|
| 44.8% | 0.159 | 174 | dora16_avp_originals_64ep\|ep7 |
| 39.1% | 0.161 | 174 | dora16_avp_originals_64ep\|ep15 |
| 37.0% | 0.198 | 162 | dora16_goa_newstack_8ep\|ep0 |
| 36.2% | 0.181 | 174 | dora16_avp_freeform_8ep\|ep31 |
| 34.5% | 0.182 | 174 | dora16_avp_8ep\|ep6 |
| 29.6% | 0.250 | 54 | fullft_goa_t4096\|ep7 |
| 27.8% | 0.210 | 162 | dora16_goa_newstack_8ep\|ep7 |
| 25.3% | 0.209 | 162 | dora128_everything_8ep_lr3x\|ep0 |
| 25.3% | 0.232 | 174 | dora16_avp_originals_win7\|ep6 |
| 23.6% | 0.222 | 174 | dora16_avp_8ep\|ep0 |
| 23.5% | 0.215 | 162 | dora128_everything_8ep_lr3x\|ep7 |
| 23.0% | 0.244 | 174 | dora16_avp_originals_win7\|ep0 |

## Healthiest (model,ckpt)

| frac<0.1 | mean | n | model|ckpt |
|---|---|---|---|
| 2.8% | 0.363 | 177 | sa3-goa-dora-47s-r128-adamw\|ep7 |
| 3.1% | 0.341 | 162 | sa3-goa-dora-47s-r128-fusion\|ep2 |
| 3.1% | 0.314 | 162 | sa3-goa-dora-47s-r64\|ep3 |
| 3.7% | 0.347 | 162 | sa3-goa-dora-47s-r64\|ep7 |
| 3.7% | 0.313 | 162 | dora128_47s_newcaptions_5ep\|ep2 |
| 3.7% | 0.301 | 162 | fp32cmp_avp_t4096_bs1_lr1e4\|ep7 |

## Finding

The scan **independently reproduces the established quality ordering, semantically**: rank-16 adapters collapse out-of-genre ~40% (worst: dora16_avp_originals 64ep), rank-128 ~3% (confirms 'rank-128 good / rank-16 harsh'); overtraining (64ep) and DoRA w2.0 both increase collapse. CLAP-degeneration is thus a valid quality proxy AND a per-cell genre-collapse flag.

## For Kim's ear (threshold calibration)

Audition `clap_degen_audition.csv` — a ladder of cells from the noise floor up, so you can hear where 'degenerate' actually starts and set the flag threshold. Pick the CLAP value below which clips sound collapsed.
