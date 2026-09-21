# Stable Audio 3 Checkpoint Analysis Catalog

> **Generated:** 2026-09-21 22:20:05  
> **Total Runs Analyzed:** 389  
> **Total Checkpoints Cataloged:** 2005  

---

## Executive Run Roster & Trajectory Summary

| Run Name | Family | Ckpts | Step Range | Final ||B||_F | Final Vel (u/1k) | Final Dir Cos | Efficiency | Finite | Demos |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `.merged_cache` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `2ankrkoh` | DoRA/LoRA adapter | 1 | 5400–5400 | 24.87 | --- | --- | 1.000 | **YES** | 0 |
| `59h2y4zo` | DoRA/LoRA adapter | 7 | 5–35 | 3.84 | 114.10 | +0.8204 | 0.915 | **YES** | 0 |
| `A_control` | DoRA/LoRA adapter | 2 | 1500–3000 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `B_autoscale` | DoRA/LoRA adapter | 2 | 1500–3000 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `C_dual` | DoRA/LoRA adapter | 2 | 1500–3000 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `_probe_b2` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `_probe_b4` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `_unfixed_missing_wd` | DoRA/LoRA adapter | 1 | 7475–7475 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `adamw` | DoRA/LoRA adapter | 3 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `adamw_avp_t512_bs1_lr1e4` | adamw_bf16_sweep | 2 | 19144–23930 | 139.16 | 12.30 | --- | 1.000 | **YES** | 0 |
| `adamw_avp_t512_bs4_lr1e4` | adamw_bf16_sweep | 2 | 4784–5980 | 76.52 | 25.73 | --- | 1.000 | **YES** | 0 |
| `adamw_avp_t512_bs4_lr2e4` | adamw_bf16_sweep | 2 | 2990–5980 | 139.62 | 31.69 | --- | 1.000 | **YES** | 0 |
| `adamw_avp_t512_bs4_lr5e5` | adamw_bf16_sweep | 1 | 5980–5980 | 41.08 | --- | --- | 1.000 | **YES** | 0 |
| `adamw_fair_s1` | DoRA/LoRA adapter | 1 | 5980–5980 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `adamw_fair_s2` | DoRA/LoRA adapter | 1 | 5980–5980 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `adamw_goa_t512_bs1_lr1e4` | adamw_bf16_sweep | 1 | 54000–54000 | 185.88 | --- | --- | 1.000 | **YES** | 0 |
| `adamw_goa_t512_bs4_lr1e4` | adamw_bf16_sweep | 1 | 13500–13500 | 103.41 | --- | --- | 1.000 | **YES** | 0 |
| `adamw_goa_t512_bs4_lr2e4` | adamw_bf16_sweep | 1 | 13500–13500 | 188.29 | --- | --- | 1.000 | **YES** | 0 |
| `adamw_goa_t512_bs4_lr5e5` | adamw_bf16_sweep | 1 | 13500–13500 | 56.15 | --- | --- | 1.000 | **YES** | 0 |
| `adamw_lr1e-4` | DoRA/LoRA adapter | 6 | 1000–6000 | 46.79 | 29.94 | -0.1815 | 0.259 | **YES** | 0 |
| `adamw_lr3e-4_step2000` | DoRA/LoRA adapter | 2 | 1000–2000 | 125.00 | 84.89 | --- | 1.000 | **YES** | 0 |
| `adamw_scratch_step5000` | DoRA/LoRA adapter | 5 | 1000–5000 | 76.39 | 28.51 | +0.0373 | 0.549 | **YES** | 0 |
| `analysis` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `aug8ddp_ddp_smoke_dora` | DoRA/LoRA adapter | 1 | 1350–1350 | 121.42 | --- | --- | 1.000 | **YES** | 0 |
| `base_fusion` | DoRA/LoRA adapter | 3 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `beat_activation_ema20` | DoRA/LoRA adapter | 20 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `beat_activation_ema40` | DoRA/LoRA adapter | 40 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `bf16_plain_s1` | DoRA/LoRA adapter | 2 | 5980–7176 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `bf16_plain_s2` | DoRA/LoRA adapter | 2 | 5980–7176 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `bf16cmp_avp_t512_bs8_lr1e4` | fp32cmp_bf16cmp | 7 | 598–2392 | 170.67 | 75.74 | +0.7364 | 0.764 | **YES** | 0 |
| `bf16cmp_avp_t512_bs8_lr1e4_repr` | fp32cmp_bf16cmp | 7 | 598–2392 | 170.67 | 75.74 | +0.7364 | 0.764 | **YES** | 0 |
| `bf16cmp_goa_t512_bs8_lr1e4` | fp32cmp_bf16cmp | 8 | 675–5400 | 233.77 | 47.48 | +0.7046 | 0.684 | **YES** | 0 |
| `chroma_heads` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `dora128_300trk__59h2y4zo` | DoRA/LoRA adapter | 7 | 5–35 | 3.84 | 114.10 | +0.8204 | 0.793 | **YES** | 0 |
| `dora128_47s_newcaptions_5ep` | dora_caption_stack | 5 | 1350–6750 | 462.30 | 76.02 | +0.6377 | 0.740 | **YES** | 0 |
| `dora128_everything_8ep_lr0.5x` | dora_everything_lr_sweep | 8 | 1527–12216 | 329.56 | 30.57 | +0.6849 | 0.668 | **YES** | 0 |
| `dora128_everything_8ep_lr0.5x_cont5` | dora_everything_lr_sweep | 5 | 1527–7635 | 413.81 | 24.56 | +0.6215 | 0.821 | **YES** | 0 |
| `dora128_everything_8ep_lr1x` | dora_everything_lr_sweep | 8 | 1527–12216 | 584.71 | 57.30 | +0.6497 | 0.636 | **YES** | 0 |
| `dora128_everything_8ep_lr3x` | dora_everything_lr_sweep | 8 | 1527–12216 | 1343.38 | 147.43 | +0.5751 | 0.569 | **YES** | 0 |
| `dora128_mix3_nodas_20260918_231123` | DoRA/LoRA adapter | 15 | 500–7500 | 8708.94 | 7021.74 | -0.0155 | 0.140 | **YES** | 143 |
| `dora128_mix3_overnight_20260918_084329` | DoRA/LoRA adapter | 8 | 500–4000 | 9925.20 | 11615.11 | -0.1251 | 0.228 | **YES** | 104 |
| `dora128_newcap_continued_3more` | dora_caption_stack | 3 | 1350–4050 | 564.28 | 60.49 | +0.6383 | 0.905 | **YES** | 0 |
| `dora128adj_avp_8ep` | dora128adj_avp | 7 | 299–2093 | 298.25 | 149.48 | +0.7237 | 0.718 | **YES** | 0 |
| `dora128adj_avp_8ep_final` | dora128adj_avp | 1 | 299–299 | 317.43 | --- | --- | 1.000 | **YES** | 0 |
| `dora128adj_avp_aug10_lr1e4` | dora128adj_avp | 10 | 300–3000 | 213.15 | 73.38 | +0.7667 | 0.709 | **YES** | 0 |
| `dora16_avp_8ep` | dora16_avp_exploration | 8 | 299–2392 | 161.15 | 84.98 | +0.6199 | 0.651 | **YES** | 0 |
| `dora16_avp_familiarity_8ep` | dora16_avp_exploration | 8 | 299–2392 | 172.45 | 81.47 | +0.6996 | 0.666 | **YES** | 0 |
| `dora16_avp_freeform_8ep` | dora16_avp_exploration | 8 | 288–2304 | 176.80 | 94.18 | +0.6907 | 0.662 | **YES** | 0 |
| `dora16_avp_originals_64ep` | dora16_avp_exploration | 8 | 288–2304 | 168.87 | 93.24 | +0.7352 | 0.651 | **YES** | 0 |
| `dora16_avp_originals_densewin` | dora16_avp_exploration | 11 | 36–396 | 129.37 | 137.26 | +0.5853 | 0.737 | **YES** | 0 |
| `dora16_avp_originals_earlyeps` | dora16_avp_exploration | 5 | 36–180 | 60.55 | 258.46 | +0.7246 | 0.807 | **YES** | 0 |
| `dora16_avp_originals_win7` | dora16_avp_exploration | 11 | 36–396 | 85.67 | 170.06 | +0.7249 | 0.713 | **YES** | 0 |
| `dora16_glitchheal_5ep_2xlr` | dora16_special | 5 | 5–25 | 5.43 | 224.13 | +0.7705 | 0.809 | **YES** | 0 |
| `dora16_goa_newstack_8ep` | dora16_special | 8 | 1350–10800 | 317.25 | 35.98 | +0.6737 | 0.586 | **YES** | 0 |
| `dora256_avp_aug10_lr7e5` | dora_rank_extreme | 1 | 300–300 | 18.89 | --- | --- | 1.000 | **YES** | 0 |
| `dora256_mixed_a128_lr5e5` | DoRA/LoRA adapter | 2 | 994–1481 | 77.37 | 55.16 | --- | 1.000 | **YES** | 0 |
| `dora256_mixed_a196_lr1e4` | DoRA/LoRA adapter | 2 | 994–1481 | 146.47 | 109.04 | --- | 1.000 | **YES** | 0 |
| `dora64_avp_tiered_lr1e4` | dora64_tiered_lr | 12 | 36–432 | 87.84 | 195.32 | +0.8045 | 0.650 | **YES** | 0 |
| `dora64_avp_tiered_lr2e4` | dora64_tiered_lr | 12 | 36–432 | 169.95 | 363.75 | +0.7848 | 0.644 | **YES** | 0 |
| `dorlor_avpaug_dora_adamw_r128a45_t256_bf16_bs128_s1` | DoRA/LoRA adapter | 2 | 1728–2880 | 51.16 | 9.25 | --- | 1.000 | **YES** | 0 |
| `dorlor_avpaug_dora_adamw_r128a45_t256_bf16_bs128_s2` | DoRA/LoRA adapter | 2 | 1728–2880 | 51.39 | 9.27 | --- | 1.000 | **YES** | 0 |
| `dorlor_avpaug_dora_fusion_r128a45_t256_bf16_bs128_s1` | DoRA/LoRA adapter | 2 | 1728–2880 | 77.86 | 17.35 | --- | 1.000 | **YES** | 0 |
| `dorlor_avpaug_dora_fusion_r128a45_t256_bf16_bs128_s2` | DoRA/LoRA adapter | 2 | 1728–2880 | 77.52 | 17.23 | --- | 1.000 | **YES** | 0 |
| `dorlor_avpaug_lora_adamw_r128a45_t256_bf16_bs128_s1` | DoRA/LoRA adapter | 2 | 1728–2880 | 51.11 | 9.42 | --- | 1.000 | **YES** | 0 |
| `dorlor_avpaug_lora_adamw_r128a45_t256_bf16_bs128_s2` | DoRA/LoRA adapter | 2 | 1728–2880 | 51.29 | 9.40 | --- | 1.000 | **YES** | 0 |
| `dorlor_avpaug_lora_fusion_r128a45_t256_bf16_bs128_s1` | DoRA/LoRA adapter | 2 | 1728–2880 | 89.85 | 18.78 | --- | 1.000 | **YES** | 0 |
| `dorlor_avpaug_lora_fusion_r128a45_t256_bf16_bs128_s2` | DoRA/LoRA adapter | 2 | 1728–2880 | 90.12 | 18.68 | --- | 1.000 | **YES** | 0 |
| `dorlor_biggoa_dora_adamw_r128a45_t256_bf16_bs128_s2` | DoRA/LoRA adapter | 2 | 1746–3104 | 44.83 | 8.44 | --- | 1.000 | **YES** | 0 |
| `dorlor_biggoa_dora_fusion_r128a45_t256_bf16_bs128_s1` | DoRA/LoRA adapter | 2 | 1746–3104 | 61.04 | 12.07 | --- | 1.000 | **YES** | 0 |
| `dorlor_biggoa_dora_fusion_r128a45_t256_bf16_bs128_s2` | DoRA/LoRA adapter | 2 | 1746–3104 | 61.21 | 12.09 | --- | 1.000 | **YES** | 0 |
| `dorlor_biggoa_lora_adamw_r128a45_t256_bf16_bs128_s2` | DoRA/LoRA adapter | 2 | 1746–3104 | 45.18 | 8.42 | --- | 1.000 | **YES** | 0 |
| `dorlor_biggoa_lora_fusion_r128a45_t256_bf16_bs128_s1` | DoRA/LoRA adapter | 2 | 1746–3104 | 73.41 | 13.43 | --- | 1.000 | **YES** | 0 |
| `dorlor_biggoa_lora_fusion_r128a45_t256_bf16_bs128_s2` | DoRA/LoRA adapter | 2 | 1746–3104 | 73.93 | 13.48 | --- | 1.000 | **YES** | 0 |
| `dorlor_dora_adamw_r128a45_t256_bf16_bs128_s1` | DoRA/LoRA adapter | 2 | 1746–3104 | 44.81 | 8.47 | --- | 1.000 | **YES** | 0 |
| `dorlor_goa_dora_adamw_r128a45_t256_bf16_bs128_s1` | DoRA/LoRA adapter | 2 | 1680–2688 | 45.15 | 163.44 | --- | 1.000 | **YES** | 0 |
| `dorlor_goa_dora_adamw_r128a45_t256_bf16_bs128_s2` | DoRA/LoRA adapter | 2 | 1680–2688 | 45.38 | 8.82 | --- | 1.000 | **YES** | 0 |
| `dorlor_goa_dora_fusion_r128a45_t256_bf16_bs128_s1` | DoRA/LoRA adapter | 2 | 1680–2688 | 61.68 | 13.34 | --- | 1.000 | **YES** | 0 |
| `dorlor_goa_dora_fusion_r128a45_t256_bf16_bs128_s2` | DoRA/LoRA adapter | 2 | 1680–2688 | 64.64 | 14.12 | --- | 1.000 | **YES** | 0 |
| `dorlor_goa_lora_adamw_r128a45_t256_bf16_bs128_s1` | DoRA/LoRA adapter | 2 | 1680–2688 | 45.59 | 8.88 | --- | 1.000 | **YES** | 0 |
| `dorlor_goa_lora_adamw_r128a45_t256_bf16_bs128_s2` | DoRA/LoRA adapter | 2 | 1680–2688 | 45.56 | 8.82 | --- | 1.000 | **YES** | 0 |
| `dorlor_goa_lora_fusion_r128a45_t256_bf16_bs128_s1` | DoRA/LoRA adapter | 2 | 1680–2688 | 75.04 | 15.41 | --- | 1.000 | **YES** | 0 |
| `dorlor_goa_lora_fusion_r128a45_t256_bf16_bs128_s2` | DoRA/LoRA adapter | 2 | 1680–2688 | 75.18 | 15.45 | --- | 1.000 | **YES** | 0 |
| `dorlor_lora_adamw_r128a45_t256_bf16_bs128_s1` | DoRA/LoRA adapter | 2 | 1746–3104 | 45.13 | 8.47 | --- | 1.000 | **YES** | 0 |
| `dorlor_suomi_dora_adamw_r128a45_t256_bf16_bs128_s1` | DoRA/LoRA adapter | 2 | 1728–2880 | 46.77 | 8.91 | --- | 1.000 | **YES** | 0 |
| `dorlor_suomi_dora_adamw_r128a45_t256_bf16_bs128_s2` | DoRA/LoRA adapter | 2 | 1728–2880 | 46.46 | 8.94 | --- | 1.000 | **YES** | 0 |
| `dorlor_suomi_dora_fusion_r128a45_t256_bf16_bs128_s1` | DoRA/LoRA adapter | 2 | 1728–2880 | 65.54 | 14.03 | --- | 1.000 | **YES** | 0 |
| `dorlor_suomi_dora_fusion_r128a45_t256_bf16_bs128_s2` | DoRA/LoRA adapter | 2 | 1728–2880 | 66.41 | 14.32 | --- | 1.000 | **YES** | 0 |
| `dorlor_suomi_lora_adamw_r128a45_t256_bf16_bs128_s1` | DoRA/LoRA adapter | 2 | 1728–2880 | 47.45 | 9.00 | --- | 1.000 | **YES** | 0 |
| `dorlor_suomi_lora_adamw_r128a45_t256_bf16_bs128_s2` | DoRA/LoRA adapter | 2 | 1728–2880 | 46.56 | 8.95 | --- | 1.000 | **YES** | 0 |
| `dorlor_suomi_lora_fusion_r128a45_t256_bf16_bs128_s1` | DoRA/LoRA adapter | 2 | 1728–2880 | 75.71 | 15.17 | --- | 1.000 | **YES** | 0 |
| `dorlor_suomi_lora_fusion_r128a45_t256_bf16_bs128_s2` | DoRA/LoRA adapter | 2 | 1728–2880 | 76.20 | 15.30 | --- | 1.000 | **YES** | 0 |
| `downbeat_activation_ema20` | DoRA/LoRA adapter | 20 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `downbeat_activation_ema40` | DoRA/LoRA adapter | 40 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `dq0egegi` | DoRA/LoRA adapter | 8 | 1350–10800 | 95.96 | 24.21 | -0.0234 | 0.382 | **YES** | 0 |
| `e2_phm` | DoRA/LoRA adapter | 1 | 1350–1350 | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `e3hun0v6` | DoRA/LoRA adapter | 37 | 4000–22000 | 51.44 | 4.99 | +0.0378 | 0.290 | **YES** | 0 |
| `force_scalar_s1` | DoRA/LoRA adapter | 1 | 4784–4784 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `force_scalar_s2` | DoRA/LoRA adapter | 1 | 4784–4784 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fp32cmp_avp_t4096_bs1_lr1e4` | fp32cmp_bf16cmp | 5 | 9572–86148 | 887.45 | 15.88 | +0.3813 | 0.645 | **YES** | 0 |
| `fp32cmp_avp_t4096_bs1_lr1e4_repr` | fp32cmp_bf16cmp | 5 | 9572–86148 | 887.45 | 15.88 | +0.3813 | 0.645 | **YES** | 0 |
| `fp32cmp_avp_t4096_bs4_lr1e4` | fp32cmp_bf16cmp | 5 | 2392–27511 | 658.83 | 31.68 | +0.3895 | 0.698 | **YES** | 0 |
| `fp32cmp_avp_t4096_bs4_lr1e4_repr` | fp32cmp_bf16cmp | 5 | 2392–27511 | 658.83 | 31.68 | +0.3895 | 0.698 | **YES** | 0 |
| `fp32cmp_avp_t4096_bs4_lr5e5` | fp32cmp_bf16cmp | 3 | 2392–8970 | 200.98 | 21.24 | +0.6594 | 0.913 | **YES** | 0 |
| `fp32cmp_avp_t4096_bs4_lr5e5_repr` | fp32cmp_bf16cmp | 3 | 2392–8970 | 200.98 | 21.24 | +0.6594 | 0.913 | **YES** | 0 |
| `fp32cmp_avp_t512_bs8_lr1e4` | fp32cmp_bf16cmp | 4 | 598–4485 | 239.37 | 51.07 | +0.6301 | 0.843 | **YES** | 0 |
| `fp32cmp_avp_t512_bs8_lr1e4_repr` | fp32cmp_bf16cmp | 2 | 2392–4485 | 239.37 | 51.07 | --- | 1.000 | **YES** | 0 |
| `fp32cmp_goa_t4096_bs1_lr1e4` | fp32cmp_bf16cmp | 4 | 21600–118800 | 840.21 | 12.61 | +0.2290 | 0.672 | **YES** | 0 |
| `fp32cmp_goa_t4096_bs1_lr1e4_repr` | fp32cmp_bf16cmp | 4 | 21600–118800 | 840.21 | 12.61 | +0.2290 | 0.672 | **YES** | 0 |
| `fp32cmp_goa_t4096_bs4_lr1e4` | fp32cmp_bf16cmp | 4 | 5400–37800 | 619.11 | 23.02 | +0.3232 | 0.718 | **YES** | 0 |
| `fp32cmp_goa_t4096_bs4_lr1e4_repr` | fp32cmp_bf16cmp | 4 | 5400–37800 | 619.11 | 23.02 | +0.3232 | 0.718 | **YES** | 0 |
| `fp32cmp_goa_t4096_bs4_lr5e5` | fp32cmp_bf16cmp | 3 | 6750–20250 | 259.64 | 12.57 | +0.5431 | 0.888 | **YES** | 0 |
| `fp32cmp_goa_t512_bs8_lr1e4` | fp32cmp_bf16cmp | 3 | 2700–10125 | 323.02 | 31.23 | +0.5293 | 0.876 | **YES** | 0 |
| `fp32frames_avp_t1024_bs1_lr1e4` | fp32frames | 2 | 9572–23930 | 457.54 | 19.40 | --- | 1.000 | **YES** | 0 |
| `fp32frames_avp_t1024_bs4_lr1e4` | fp32frames | 2 | 2392–5980 | 261.73 | 43.60 | --- | 1.000 | **YES** | 0 |
| `fp32frames_avp_t2048_bs1_lr1e4` | fp32frames | 2 | 9572–23930 | 468.90 | 19.78 | --- | 1.000 | **YES** | 0 |
| `fp32frames_avp_t2048_bs4_lr1e4` | fp32frames | 2 | 2392–5980 | 268.50 | 44.61 | --- | 1.000 | **YES** | 0 |
| `fp32frames_avp_t4096_bs1_lr1e4` | fp32frames | 2 | 9572–23930 | 480.60 | 20.15 | --- | 1.000 | **YES** | 0 |
| `fp32frames_avp_t4096_bs4_lr1e4` | fp32frames | 2 | 2392–5980 | 276.07 | 45.56 | --- | 1.000 | **YES** | 0 |
| `fp32frames_avp_t512_bs1_lr1e4` | fp32frames | 2 | 9572–23930 | 453.17 | 19.26 | --- | 1.000 | **YES** | 0 |
| `fp32frames_avp_t512_bs4_lr1e4` | fp32frames | 2 | 2392–5980 | 259.43 | 43.12 | --- | 1.000 | **YES** | 0 |
| `fp32frames_goa_t1024_bs1_lr1e4` | fp32frames | 1 | 54000–54000 | 579.80 | --- | --- | 1.000 | **YES** | 0 |
| `fp32frames_goa_t1024_bs4_lr1e4` | fp32frames | 2 | 5400–13500 | 350.60 | 26.50 | --- | 1.000 | **YES** | 0 |
| `fp32frames_goa_t2048_bs1_lr1e4` | fp32frames | 2 | 21600–54000 | 582.39 | 11.47 | --- | 1.000 | **YES** | 0 |
| `fp32frames_goa_t2048_bs4_lr1e4` | fp32frames | 2 | 5400–13500 | 356.09 | 26.68 | --- | 1.000 | **YES** | 0 |
| `fp32frames_goa_t4096_bs1_lr1e4` | fp32frames | 2 | 21600–37800 | 521.64 | 14.77 | --- | 1.000 | **YES** | 0 |
| `fp32frames_goa_t4096_bs4_lr1e4` | fp32frames | 2 | 5400–12150 | 342.84 | 28.50 | --- | 1.000 | **YES** | 0 |
| `fp32frames_goa_t512_bs1_lr1e4` | fp32frames | 2 | 21600–54000 | 579.79 | 21.55 | --- | 1.000 | **YES** | 0 |
| `fp32frames_goa_t512_bs4_lr1e4` | fp32frames | 3 | 5400–13500 | 349.40 | 27.36 | +0.5448 | 0.880 | **YES** | 0 |
| `fullft_3src_t512_fp32_hyperball_lr1e-4` | DoRA/LoRA adapter | 1 | 20–20 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_avp_t1024` | fullft | 2 | 2990–4784 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_avp_t1024_bf16_lr25e6_sub12v3sel_wsd10_bs8_s1` | DoRA/LoRA adapter | 2 | 12000–19200 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_avp_t2048` | fullft | 2 | 2990–4784 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_avp_t256` | fullft | 3 | 4784–90598 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_avp_t4096` | fullft | 2 | 2990–4784 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_avp_t512` | fullft | 2 | 2990–4784 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_avpaug_t1024_fp32_lr1e-4_s1` | DoRA/LoRA adapter | 2 | 3588–5980 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_biggoa_t1024_fp32_lr1e-4_s1` | DoRA/LoRA adapter | 1 | 3132–3132 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_bigset` | DoRA/LoRA adapter | 1 | 25040–25040 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_goa_t1024` | fullft | 2 | 6750–10800 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_goa_t2048` | fullft | 2 | 6750–10800 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_goa_t256` | fullft | 3 | 10800–94500 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_goa_t4096` | fullft | 2 | 6750–10800 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_goa_t512` | fullft | 2 | 6750–10800 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_ladder_A_control` | DoRA/LoRA adapter | 2 | 1500–3000 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_ladder_B_autoscale` | DoRA/LoRA adapter | 2 | 1500–3000 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_ladder_C_dual` | DoRA/LoRA adapter | 2 | 1500–3000 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_mix3_t1024_fp32_lr1e-4_s1` | DoRA/LoRA adapter | 2 | 3036–5060 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_mixed_avp_latents_sa3_t4096` | DoRA/LoRA adapter | 1 | 3896–3896 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_mixed_avp_latents_sa3_t4096_wd03` | DoRA/LoRA adapter | 2 | 1220–1952 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_mixed_avp_latents_sa3_t4096_wdfix` | DoRA/LoRA adapter | 2 | 9740–15584 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_suomi_t1024_fp32_lr1e-4_s1` | DoRA/LoRA adapter | 2 | 1896–3160 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fullft_wd_ab_wd0` | DoRA/LoRA adapter | 1 | 2700–2700 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `fusion_autoscale_lr1e-4` | DoRA/LoRA adapter | 3 | 1000–3000 | 2492.20 | 963.94 | +0.3807 | 0.834 | **YES** | 0 |
| `fusion_autoscale_lr1e-6_full` | DoRA/LoRA adapter | 3 | 1000–3000 | 177.20 | 68.97 | +0.5904 | 0.893 | **YES** | 0 |
| `fusion_autoscale_lr5e-6_full3h` | DoRA/LoRA adapter | 3 | 1000–3000 | 391.02 | 141.96 | +0.5392 | 0.879 | **YES** | 0 |
| `fusion_autoscale_lr5e6_bs2` | DoRA/LoRA adapter | 3 | 4000–12000 | 691.41 | 64.36 | +0.4534 | 0.855 | **YES** | 0 |
| `fusion_autoscale_lr5e6_control2` | DoRA/LoRA adapter | 3 | 1000–3000 | 355.62 | 128.83 | +0.5449 | 0.880 | **YES** | 0 |
| `fusion_nm` | DoRA/LoRA adapter | 3 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `head_a_ceiling_act` | DoRA/LoRA adapter | 73 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `headb_base_s1` | DoRA/LoRA adapter | 8 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `headb_ft_s1` | DoRA/LoRA adapter | 8 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `headb_melody` | DoRA/LoRA adapter | 16 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `heads_ema20` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `heads_ema40` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `highdrop` | DoRA/LoRA adapter | 3 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `hpcp_attr` | DoRA/LoRA adapter | 3 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `hpcp_ema20` | DoRA/LoRA adapter | 20 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `hpcp_ema40` | DoRA/LoRA adapter | 40 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `i8nygj4y` | DoRA/LoRA adapter | 8 | 1350–10800 | 70.39 | 16.99 | -0.0219 | 0.392 | **YES** | 0 |
| `latch_f0_bass_s1` | DoRA/LoRA adapter | 30 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `latch_f0_other_s1` | DoRA/LoRA adapter | 30 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `latch_hpcp_s1` | DoRA/LoRA adapter | 30 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `latch_onset_envelope_s1` | DoRA/LoRA adapter | 30 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `latch_rms_energy_bass_s1` | DoRA/LoRA adapter | 30 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `latch_spectral_flatness_s1` | DoRA/LoRA adapter | 30 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `lion_lr1e-5` | DoRA/LoRA adapter | 6 | 1000–6000 | 77.61 | 23.23 | +0.0880 | 0.540 | **YES** | 0 |
| `lion_lr5e-5-batch32` | DoRA/LoRA adapter | 6 | 1000–6000 | 305.62 | 113.01 | +0.0257 | 0.473 | **YES** | 0 |
| `longctx_t1024_r128` | longctx | 2 | 1685–2696 | 174.40 | 65.57 | --- | 1.000 | **YES** | 0 |
| `longctx_t2048_r128` | longctx | 2 | 2700–5400 | 243.31 | 45.42 | --- | 1.000 | **YES** | 0 |
| `lr5e5mix_r128a128_t512_bf16_bs8_s1` | DoRA/LoRA adapter | 1 | 43152–43152 | 99.20 | --- | --- | 1.000 | **YES** | 0 |
| `lr5e5mixwarm_r128a128_t512_bf16_bs8_s1` | DoRA/LoRA adapter | 1 | 43152–43152 | 112.87 | --- | --- | 1.000 | **YES** | 0 |
| `lr5e5mixwarmwsd_r128a128_t512_bf16_bs8_s1` | DoRA/LoRA adapter | 1 | 43152–43152 | 102.23 | --- | --- | 1.000 | **YES** | 0 |
| `lr5e5mixwsd_r128a128_t512_bf16_bs8_s1` | DoRA/LoRA adapter | 1 | 43152–43152 | 86.44 | --- | --- | 1.000 | **YES** | 0 |
| `lreq_goa_lr1e4` | DoRA/LoRA adapter | 2 | 5400–27000 | 146.33 | 6.80 | --- | 1.000 | **YES** | 0 |
| `lreq_goa_lr2e4` | DoRA/LoRA adapter | 2 | 8100–18900 | 221.48 | 22.12 | --- | 1.000 | **YES** | 0 |
| `lreq_goa_lr5e5` | DoRA/LoRA adapter | 2 | 5400–54000 | 115.56 | 2.30 | --- | 1.000 | **YES** | 0 |
| `melodychroma_r32_hpcp` | DoRA/LoRA adapter | 6 | 2700–16200 | 63.50 | 7.98 | +0.0069 | 0.491 | **YES** | 0 |
| `modular_opt_cubic5_sf_ev_20ep_13500s_2026-09-21_0148` | DoRA/LoRA adapter | 20 | 100–12825 | 44.09 | 3.50 | +0.8070 | 0.724 | **YES** | 30 |
| `modular_opt_lr1e4_w200_ev_normuon_300s_2026-09-20_2304` | DoRA/LoRA adapter | 3 | 100–300 | 2.71 | 15.24 | +0.6499 | 0.910 | **YES** | 18 |
| `modular_opt_lr1e4_w200_sf_normuon_300s_2026-09-20_2230` | DoRA/LoRA adapter | 3 | 100–300 | 2.72 | 15.27 | +0.6497 | 0.910 | **YES** | 48 |
| `modular_opt_normuon_sf_otwd_3000s_2026-09-20_2138` | DoRA/LoRA adapter | 3 | 100–600 | 0.50 | 0.84 | +0.7777 | 0.944 | **YES** | 48 |
| `modular_opt_stage3_ns5_2026-09-20` | DoRA/LoRA adapter | 2 | 100–120 | 0.35 | 4.86 | --- | 1.000 | **YES** | 19 |
| `modular_opt_stage3_ns5_otwd_3000s_2026-09-20_1800` | DoRA/LoRA adapter | 4 | 100–666 | 1.35 | 3.40 | +0.3741 | 0.815 | **YES** | 48 |
| `morph_IOI3_base_s1` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `morph_IOI3_base_s2` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `morph_IOI3_base_s3` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `morph_IOI3_base_s4` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `morph_IOI3_ft_s1` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `morph_IOI3_ft_s2` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `morph_IOI3_ft_s3` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `morph_IOI3_ft_s4` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `morph_L2_base_s1` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `morph_L2_ft_s1` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `morph_L3_base_s1` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `morph_L3_base_s2` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `morph_L3_ft_s1` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `morph_L3_ft_s2` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `morph_L4_base_s1` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `morph_L4_ft_s1` | DoRA/LoRA adapter | 1 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `mqe3ne49` | DoRA/LoRA adapter | 8 | 1350–10800 | 573.76 | 62.66 | +0.6576 | 0.644 | **YES** | 0 |
| `onset_AdamW_lr7.5e-5_continuous` | DoRA/LoRA adapter | 13 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `onset_AdamW_lr7.5e-5_randomcrop` | DoRA/LoRA adapter | 13 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `onset_AdamW_lr7.5e-5_randomcrop_20ep` | DoRA/LoRA adapter | 25 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `onset_FUSION_lr1e4_5000_FIXED` | DoRA/LoRA adapter | 6 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `onset_FUSION_lr2e5_40epoch` | DoRA/LoRA adapter | 43 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `onset_FUSION_lr8e5_10epoch` | DoRA/LoRA adapter | 11 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `onset_FUSION_lr8e5_1p2ep` | DoRA/LoRA adapter | 4 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `onset_FusionCC_lr1e-4_randomcrop` | DoRA/LoRA adapter | 11 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `onset_FusionCaut_lr1e-4_randomcrop` | DoRA/LoRA adapter | 11 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `onset_Fusion_lr1e-4_randomcrop` | DoRA/LoRA adapter | 12 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `onset_Fusion_lr1e-4_randomcrop_20ep` | DoRA/LoRA adapter | 3 | 5400–16200 | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `onset_Fusion_lr1e-4_randomcrop_L13-15` | DoRA/LoRA adapter | 11 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `onset_Fusion_lr1e-4_randomcrop_L8-15` | DoRA/LoRA adapter | 11 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `onset_Fusion_opb_10ep` | DoRA/LoRA adapter | 11 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `onset_Fusion_opb_lr1.5e-4_30ep` | DoRA/LoRA adapter | 26 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `onset_density_400trk_crop1024` | DoRA/LoRA adapter | 7 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `onset_density_FULL_3000_crop1024` | DoRA/LoRA adapter | 2 | 1000–2000 | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `onset_density_FULL_3000b_crop1024` | DoRA/LoRA adapter | 2 | 1000–2000 | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `onset_density_FULL_3000c_crop1024` | DoRA/LoRA adapter | 4 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `onset_envelope_ema20` | DoRA/LoRA adapter | 20 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `onset_envelope_ema40` | DoRA/LoRA adapter | 40 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `plain_s1` | DoRA/LoRA adapter | 1 | 4784–4784 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `plain_s2` | DoRA/LoRA adapter | 1 | 4784–4784 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `precision_ladder_t256_bf16mixed` | DoRA/LoRA adapter | 1 | 4500–4500 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `precision_ladder_t256_fp16mixed` | DoRA/LoRA adapter | 1 | 4500–4500 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `precision_ladder_t256_fp32` | DoRA/LoRA adapter | 1 | 4500–4500 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `proll_fullft_t256_bf16_s1` | DoRA/LoRA adapter | 1 | 2688–2688 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `proll_fullft_t256_bf16_s2` | DoRA/LoRA adapter | 1 | 2688–2688 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `pzqv5mcw` | DoRA/LoRA adapter | 2 | 5–10 | 1.53 | 140.11 | --- | 1.000 | **YES** | 0 |
| `qy50uilf` | DoRA/LoRA adapter | 8 | 1350–10800 | nan | nan | +nan | --- | ❌ NaN | 0 |
| `real` | DoRA/LoRA adapter | 23 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `repaired` | DoRA/LoRA adapter | 4 | -1–-1 | 93.19 | --- | -0.6582 | 0.000 | **YES** | 0 |
| `rhythm_heads` | DoRA/LoRA adapter | 3 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `riffer_200trk_2e-4_adamw` | DoRA/LoRA adapter | 7 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `riffer_200trk_2e-4_fusion` | DoRA/LoRA adapter | 5 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `riffer_200trk_2e-4_sfadamw` | DoRA/LoRA adapter | 5 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `riffer_200trk_4e-4_adamw` | DoRA/LoRA adapter | 7 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `riffer_200trk_5e-5_fusion` | DoRA/LoRA adapter | 5 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `riffer_200trk_6e-4_adamw_wu` | DoRA/LoRA adapter | 7 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `riffer_20pct_2048_lr1e3` | DoRA/LoRA adapter | 12 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `riffer_20pct_2048_nockpt` | DoRA/LoRA adapter | 12 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `riffer_400trk_lr1e-4_crop1024` | DoRA/LoRA adapter | 13 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `riffer_bf16test` | DoRA/LoRA adapter | 2 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `rms_energy_air_ema20` | DoRA/LoRA adapter | 20 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `rms_energy_air_ema40` | DoRA/LoRA adapter | 40 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `rms_energy_body_ema20` | DoRA/LoRA adapter | 20 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `rms_energy_body_ema40` | DoRA/LoRA adapter | 40 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `sa3-goa-dora-47s-b4-cont__x20b3ygb` | DoRA/LoRA adapter | 5 | 1350–6750 | 39.44 | 8.45 | -0.0118 | 0.495 | **YES** | 0 |
| `sa3-goa-dora-47s-b4__vjnnndnu` | DoRA/LoRA adapter | 3 | 1350–4050 | 23.24 | 8.49 | +0.0492 | 0.724 | **YES** | 0 |
| `sa3-goa-dora-47s-r128-adamw__dq0egegi` | DoRA/LoRA adapter | 8 | 1350–10800 | 95.96 | 24.21 | -0.0234 | 0.382 | **YES** | 0 |
| `sa3-goa-dora-47s-r128-fusion-caut__qy50uilf` | DoRA/LoRA adapter | 8 | 1350–10800 | nan | nan | +nan | --- | ❌ NaN | 0 |
| `sa3-goa-dora-47s-r128-fusion__mqe3ne49` | DoRA/LoRA adapter | 8 | 1350–10800 | 573.76 | 62.66 | +0.6576 | 0.644 | **YES** | 0 |
| `sa3-goa-dora-47s-r64__i8nygj4y` | DoRA/LoRA adapter | 8 | 1350–10800 | 70.39 | 16.99 | -0.0219 | 0.392 | **YES** | 0 |
| `sa3-goa-dora-47s__2ankrkoh` | DoRA/LoRA adapter | 1 | 5400–5400 | 24.87 | --- | --- | 1.000 | **YES** | 0 |
| `sa3_control_runs` | DoRA/LoRA adapter | 2 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `sanity16_suomi` | DoRA/LoRA adapter | 1 | 9420–9420 | 35.08 | --- | --- | 1.000 | **YES** | 0 |
| `seg1` | DoRA/LoRA adapter | 4 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `seg2` | DoRA/LoRA adapter | 4 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `seg3` | DoRA/LoRA adapter | 4 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `seg4` | DoRA/LoRA adapter | 3 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `shuffled` | DoRA/LoRA adapter | 23 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `site_L13_15` | DoRA/LoRA adapter | 3 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `site_L8_15` | DoRA/LoRA adapter | 3 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `smoke_r256_a256_lr1e4_f512_bs8` | smoke | 3 | 100–300 | 61.49 | 191.26 | +0.6131 | 0.899 | **YES** | 0 |
| `soups` | DoRA/LoRA adapter | 12 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `soups_vibe` | DoRA/LoRA adapter | 15 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `spectral_kurtosis_ema20` | DoRA/LoRA adapter | 20 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `spectral_kurtosis_ema40` | DoRA/LoRA adapter | 40 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `stereo_sweep_w0.0` | DoRA/LoRA adapter | 8 | 500–4000 | 204.83 | 56.03 | +0.7025 | 0.683 | **YES** | 0 |
| `style_fpA_adamw` | DoRA/LoRA adapter | 2 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `style_fpC_adamw` | DoRA/LoRA adapter | 2 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `style_fpC_genrecc` | DoRA/LoRA adapter | 8 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `subloss_goa_k12` | DoRA/LoRA adapter | 2 | 5400–27000 | 144.06 | 6.73 | --- | 1.000 | **YES** | 0 |
| `subloss_goa_k2` | DoRA/LoRA adapter | 2 | 5400–27000 | 146.34 | 6.80 | --- | 1.000 | **YES** | 0 |
| `subloss_goa_k20` | DoRA/LoRA adapter | 1 | 2700–2700 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `subloss_goa_k5` | DoRA/LoRA adapter | 2 | 5400–27000 | 145.03 | 6.76 | --- | 1.000 | **YES** | 0 |
| `subloss_k24_avpaug_t512_bf16_s1` | DoRA/LoRA adapter | 1 | 2368–2368 | 48.47 | --- | --- | 1.000 | **YES** | 0 |
| `subloss_k24_biggoa_t512_bf16_s1` | DoRA/LoRA adapter | 1 | 12480–12480 | 98.77 | --- | --- | 1.000 | **YES** | 0 |
| `subloss_k24_bigmix_t512_bf16_s1` | DoRA/LoRA adapter | 1 | 15680–15680 | 109.16 | --- | --- | 1.000 | **YES** | 0 |
| `subloss_k24_suomi_t512_bf16_s1` | DoRA/LoRA adapter | 1 | 1216–1216 | 31.10 | --- | --- | 1.000 | **YES** | 0 |
| `subloss_v3sel_k12` | DoRA/LoRA adapter | 1 | 27000–27000 | 147.40 | --- | --- | 1.000 | **YES** | 0 |
| `subloss_v3sel_k2` | DoRA/LoRA adapter | 1 | 27000–27000 | 146.65 | --- | --- | 1.000 | **YES** | 0 |
| `subloss_v3sel_k5` | DoRA/LoRA adapter | 1 | 27000–27000 | 147.19 | --- | --- | 1.000 | **YES** | 0 |
| `subloss_v3sel_k5_s2` | DoRA/LoRA adapter | 1 | 27000–27000 | 146.66 | --- | --- | 1.000 | **YES** | 0 |
| `subloss_v3sel_k5_tgate` | DoRA/LoRA adapter | 1 | 16200–16200 | 115.09 | --- | --- | 1.000 | **YES** | 0 |
| `subloss_v3sel_k5_tgate_deficit_s1` | DoRA/LoRA adapter | 1 | 27000–27000 | 147.06 | --- | --- | 1.000 | **YES** | 0 |
| `subloss_v3sel_k5_tgate_deficit_s2` | DoRA/LoRA adapter | 1 | 27000–27000 | 147.08 | --- | --- | 1.000 | **YES** | 0 |
| `subloss_v3sel_k5_tgate_r2_s2` | DoRA/LoRA adapter | 1 | 27000–27000 | 146.70 | --- | --- | 1.000 | **YES** | 0 |
| `suomi` | DoRA/LoRA adapter | 1 | 9420–9420 | 35.08 | --- | --- | 1.000 | **YES** | 0 |
| `suomi_r256_lr1e-4` | DoRA/LoRA adapter | 1 | 2340–2340 | 164.38 | --- | --- | 1.000 | **YES** | 0 |
| `suomi_r256_lr3e-5` | DoRA/LoRA adapter | 1 | 2340–2340 | 65.16 | --- | --- | 1.000 | **YES** | 0 |
| `suomi_r32_lr1e-4` | DoRA/LoRA adapter | 1 | 1140–1140 | 152.43 | --- | --- | 1.000 | **YES** | 0 |
| `suomi_r32_lr3e-5` | DoRA/LoRA adapter | 1 | 1140–1140 | 85.08 | --- | --- | 1.000 | **YES** | 0 |
| `suomift_warm_avpaug19_t1024_bf16_k5_s1` | DoRA/LoRA adapter | 3 | 320–1280 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `suomift_warm_goaft_t1024_bf16_k5_s1` | DoRA/LoRA adapter | 3 | 320–1280 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `version_None` | DoRA/LoRA adapter | 1 | 75–75 | 0.00 | --- | --- | 1.000 | ❌ NaN | 0 |
| `vjnnndnu` | DoRA/LoRA adapter | 3 | 1350–4050 | 23.24 | 8.49 | +0.0492 | 0.724 | **YES** | 0 |
| `wfleet_avp_t1024_a45_fp32_s1` | DoRA/LoRA adapter | 1 | 23930–23930 | 189.83 | --- | --- | 1.000 | **YES** | 0 |
| `wfleet_mix3_t1024_a45_fp32_s1` | DoRA/LoRA adapter | 1 | 40440–40440 | 336.28 | --- | --- | 1.000 | **YES** | 0 |
| `wfleet_suomi_t1024_a128_fp32_s1` | DoRA/LoRA adapter | 1 | 25200–25200 | nan | --- | --- | 1.000 | ❌ NaN | 0 |
| `wfleet_suomi_t1024_a128_fp32_s2` | DoRA/LoRA adapter | 1 | 25200–25200 | 185.40 | --- | --- | 1.000 | **YES** | 0 |
| `wfleet_suomi_t1024_a45_fp32_s1` | DoRA/LoRA adapter | 1 | 25200–25200 | 157.21 | --- | --- | 1.000 | **YES** | 0 |
| `wfleet_suomi_t1024_a45_fp32_s2` | DoRA/LoRA adapter | 1 | 25200–25200 | 146.64 | --- | --- | 1.000 | **YES** | 0 |
| `wfleet_suomi_t512_a45_fp32_s1` | DoRA/LoRA adapter | 1 | 3160–3160 | 64.64 | --- | --- | 1.000 | **YES** | 0 |
| `wfleet_suomi_t512_a45_fp32_s2` | DoRA/LoRA adapter | 1 | 2520–2520 | 53.94 | --- | --- | 1.000 | **YES** | 0 |
| `wide_r256` | DoRA/LoRA adapter | 3 | N/A | 0.00 | --- | --- | 1.000 | **YES** | 0 |
| `winning_avp_t1024_a45_fp32` | fp32_winning | 6 | 6578–35880 | 665.16 | 17.99 | +0.6894 | 0.757 | **YES** | 0 |
| `winning_avp_t512_a128_fp32` | fp32_winning | 10 | 3289–68471 | 873.99 | 16.90 | +0.3168 | 0.609 | **YES** | 0 |
| `winning_avp_t512_a45_bf16` | fp32_winning | 8 | 3289–17940 | 515.14 | 27.08 | +0.7221 | 0.761 | **YES** | 0 |
| `winning_avp_t512_a45_fp32` | fp32_winning | 8 | 3289–17940 | 514.25 | 27.01 | +0.7193 | 0.761 | **YES** | 0 |
| `winning_avpaug10_t512_a45_fp32` | fp32_winning | 7 | 440–2400 | 200.73 | 79.24 | +0.7592 | 0.801 | **YES** | 0 |
| `winning_goa_t512_a128_fp32` | fp32_winning | 9 | 7425–91125 | 802.31 | 12.06 | +0.3041 | 0.588 | **YES** | 0 |
| `winning_goa_t512_a45_bf16` | fp32_winning | 6 | 7425–40500 | 632.40 | 16.09 | +0.6543 | 0.737 | **YES** | 0 |
| `winning_goa_t512_a45_fp32` | fp32_winning | 6 | 7425–40500 | 631.99 | 16.16 | +0.6518 | 0.736 | **YES** | 0 |
| `x0eq_goa` | DoRA/LoRA adapter | 2 | 5400–27000 | 141.14 | 6.63 | --- | 1.000 | **YES** | 0 |
| `x0eq_sub5_goa` | DoRA/LoRA adapter | 2 | 5400–27000 | 141.10 | 6.62 | --- | 1.000 | **YES** | 0 |
| `x20b3ygb` | DoRA/LoRA adapter | 5 | 1350–6750 | 39.44 | 8.45 | -0.0118 | 0.495 | **YES** | 0 |
| `xftdora128_fullft_avp_t1024` | xft_distillation | 1 | N/A | 137.24 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora128_fullft_avp_t2048` | xft_distillation | 1 | N/A | 138.16 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora128_fullft_avp_t256` | xft_distillation | 1 | N/A | 136.57 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora128_fullft_avp_t4096` | xft_distillation | 1 | N/A | 139.45 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora128_fullft_avp_t512` | xft_distillation | 1 | N/A | 136.68 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora128_fullft_goa_t1024` | xft_distillation | 1 | N/A | 168.29 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora128_fullft_goa_t2048` | xft_distillation | 1 | N/A | 168.62 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora128_fullft_goa_t256` | xft_distillation | 1 | N/A | 168.32 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora128_fullft_goa_t4096` | xft_distillation | 1 | N/A | 168.86 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora128_fullft_goa_t512` | xft_distillation | 1 | N/A | 168.33 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora16_fullft_avp_t1024` | xft_distillation | 1 | N/A | 52.64 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora16_fullft_avp_t2048` | xft_distillation | 1 | N/A | 53.01 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora16_fullft_avp_t256` | xft_distillation | 1 | N/A | 52.33 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora16_fullft_avp_t4096` | xft_distillation | 1 | N/A | 53.52 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora16_fullft_avp_t512` | xft_distillation | 1 | N/A | 52.37 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora16_fullft_goa_t1024` | xft_distillation | 1 | N/A | 64.59 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora16_fullft_goa_t2048` | xft_distillation | 1 | N/A | 64.73 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora16_fullft_goa_t256` | xft_distillation | 1 | N/A | 64.54 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora16_fullft_goa_t4096` | xft_distillation | 1 | N/A | 64.87 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora16_fullft_goa_t512` | xft_distillation | 1 | N/A | 64.60 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora64_fullft_avp_t1024` | xft_distillation | 1 | N/A | 100.59 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora64_fullft_avp_t2048` | xft_distillation | 1 | N/A | 101.29 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora64_fullft_avp_t256` | xft_distillation | 1 | N/A | 100.06 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora64_fullft_avp_t4096` | xft_distillation | 1 | N/A | 102.26 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora64_fullft_avp_t512` | xft_distillation | 1 | N/A | 100.14 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora64_fullft_goa_t1024` | xft_distillation | 1 | N/A | 123.30 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora64_fullft_goa_t2048` | xft_distillation | 1 | N/A | 123.56 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora64_fullft_goa_t256` | xft_distillation | 1 | N/A | 123.28 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora64_fullft_goa_t4096` | xft_distillation | 1 | N/A | 123.76 | --- | --- | 1.000 | **YES** | 0 |
| `xftdora64_fullft_goa_t512` | xft_distillation | 1 | N/A | 123.33 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora128_fullft_avp_t1024` | xft_distillation | 1 | N/A | 137.24 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora128_fullft_avp_t2048` | xft_distillation | 1 | N/A | 138.16 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora128_fullft_avp_t256` | xft_distillation | 1 | N/A | 136.57 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora128_fullft_avp_t4096` | xft_distillation | 1 | N/A | 139.45 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora128_fullft_avp_t512` | xft_distillation | 1 | N/A | 136.68 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora128_fullft_goa_t1024` | xft_distillation | 1 | N/A | 168.29 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora128_fullft_goa_t2048` | xft_distillation | 1 | N/A | 168.62 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora128_fullft_goa_t256` | xft_distillation | 1 | N/A | 168.32 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora128_fullft_goa_t4096` | xft_distillation | 1 | N/A | 168.86 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora128_fullft_goa_t512` | xft_distillation | 1 | N/A | 168.33 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora16_fullft_avp_t1024` | xft_distillation | 1 | N/A | 52.64 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora16_fullft_avp_t2048` | xft_distillation | 1 | N/A | 53.01 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora16_fullft_avp_t256` | xft_distillation | 1 | N/A | 52.33 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora16_fullft_avp_t4096` | xft_distillation | 1 | N/A | 53.52 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora16_fullft_avp_t512` | xft_distillation | 1 | N/A | 52.37 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora16_fullft_goa_t1024` | xft_distillation | 1 | N/A | 64.59 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora16_fullft_goa_t2048` | xft_distillation | 1 | N/A | 64.73 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora16_fullft_goa_t256` | xft_distillation | 1 | N/A | 64.54 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora16_fullft_goa_t4096` | xft_distillation | 1 | N/A | 64.87 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora16_fullft_goa_t512` | xft_distillation | 1 | N/A | 64.60 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora64_fullft_avp_t1024` | xft_distillation | 1 | N/A | 100.59 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora64_fullft_avp_t2048` | xft_distillation | 1 | N/A | 101.29 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora64_fullft_avp_t256` | xft_distillation | 1 | N/A | 100.06 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora64_fullft_avp_t4096` | xft_distillation | 1 | N/A | 102.26 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora64_fullft_avp_t512` | xft_distillation | 1 | N/A | 100.14 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora64_fullft_goa_t1024` | xft_distillation | 1 | N/A | 123.30 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora64_fullft_goa_t2048` | xft_distillation | 1 | N/A | 123.56 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora64_fullft_goa_t256` | xft_distillation | 1 | N/A | 123.28 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora64_fullft_goa_t4096` | xft_distillation | 1 | N/A | 123.76 | --- | --- | 1.000 | **YES** | 0 |
| `xftlora64_fullft_goa_t512` | xft_distillation | 1 | N/A | 123.33 | --- | --- | 1.000 | **YES** | 0 |
| `z18fy24b` | DoRA/LoRA adapter | 7 | 500–3500 | 24.65 | 12.25 | +0.1277 | 0.567 | **YES** | 0 |

---

## Detailed Per-Run Step Dynamics

### `.merged_cache`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 4397.8 |


### `2ankrkoh`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | 0 | 24.87 | 39.11 | --- | --- | 0.00 | 0.00 | ✓ | 82.6 |


### `59h2y4zo`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5 | 0 | 1.06 | 34.90 | --- | --- | 0.00 | 0.00 | ✓ | 82.5 |
| 10 | 1 | 1.75 | 34.93 | 165.56 | --- | 0.83 | 0.83 | ✓ | 82.5 |
| 15 | 2 | 2.32 | 34.98 | 147.90 | +0.8128 | 1.57 | 1.49 | ✓ | 82.5 |
| 20 | 3 | 2.81 | 35.04 | --- | --- | 0.00 | 0.00 | ✓ | 82.5 |
| 25 | 4 | 3.21 | 35.10 | 128.05 | --- | 0.64 | 0.64 | ✓ | 82.5 |
| 30 | 5 | 3.55 | 35.16 | 122.88 | +0.8293 | 1.25 | 1.20 | ✓ | 82.5 |
| 35 | 6 | 3.84 | 35.21 | 114.10 | +0.8204 | 1.83 | 1.67 | ✓ | 82.5 |


### `A_control`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1500 | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 9956.4 |
| 3000 | 39 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 9956.4 |


### `B_autoscale`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1500 | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 10649.6 |
| 3000 | 39 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 10649.6 |


### `C_dual`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1500 | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 10649.6 |
| 3000 | 39 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 10649.6 |


### `_probe_b2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `_probe_b4`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `_unfixed_missing_wd`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 7475 | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 21028.8 |


### `adamw`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 20 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2769.8 |
| 40 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2769.8 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2769.8 |


### `adamw_avp_t512_bs1_lr1e4`
> **Recipe:** {'base_model': 'SA3 medium (SAME latent, 10.77 Hz)', 'method': 'DoRA (dora-rows)', 'rank_alpha': 'rank 128, alpha 128 (alpha=rank convention, scaling=1); 229 target modules, full uniform coverage (no include/exclude filter) -- verified from checkpoint lora_config + state_dict', 'optimizer': 'AdamW, betas=(0.9,0.95), weight_decay=0.01, eps=1e-8, lr=1e-4 -- verified from checkpoint optimizer_states param_groups', 'lr_schedule': 'constant, peak lr 1e-4 (checkpoint lr_schedulers list is empty -- no scheduler)', 'precision': 'bf16', 'context_len': 'T=512 frames, 47.55s (10.7666 fps)', 'batch_seed': 'batch 1, seed not recorded in checkpoint', 'steps': 'epoch 5 and epoch 9 (terminal) both metered; avg_loss not recorded at these ckpts', 'corpus': 'avp corpus (generic name; scale redacted per spec)', 'objective': 'rectified-flow, standard SA3 DoRA training loss (no auxiliary control loss)', 'extras': 'dora-rows adapter_type, dropout=0.0'}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 19144 | 7 | 125.46 | 123.82 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 23930 | 9 | 139.16 | 128.78 | 12.30 | --- | 58.85 | 58.85 | ✓ | 1907.2 |


### `adamw_avp_t512_bs4_lr1e4`
> **Recipe:** {'base_model': 'SA3 medium (SAME latent, 10.77 Hz)', 'method': 'DoRA (dora-rows)', 'rank_alpha': 'rank 128, alpha 128 (alpha=rank convention, scaling=1); 229 target modules, full uniform coverage (no include/exclude filter) -- verified from checkpoint lora_config + state_dict', 'optimizer': 'AdamW, betas=(0.9,0.95), weight_decay=0.01, eps=1e-8, lr=1e-4 -- verified from checkpoint optimizer_states param_groups', 'lr_schedule': 'constant, peak lr 1e-4 (checkpoint lr_schedulers list is empty -- no scheduler)', 'precision': 'bf16', 'context_len': 'T=512 frames, 47.55s (10.7666 fps)', 'batch_seed': 'batch 4, seed not recorded in checkpoint', 'steps': 'epoch 5 and epoch 9 (terminal) both metered; avg_loss not recorded at these ckpts', 'corpus': 'avp corpus (generic name; scale redacted per spec)', 'objective': 'rectified-flow, standard SA3 DoRA training loss (no auxiliary control loss)', 'extras': 'dora-rows adapter_type, dropout=0.0'}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 4784 | 7 | 68.24 | 108.21 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 5980 | 9 | 76.52 | 110.47 | 25.73 | --- | 30.77 | 30.77 | ✓ | 1907.2 |


### `adamw_avp_t512_bs4_lr2e4`
> **Recipe:** {'base_model': 'SA3 medium (SAME latent, 10.77 Hz)', 'method': 'DoRA (dora-rows)', 'rank_alpha': 'rank 128, alpha 128 (alpha=rank convention, scaling=1); 229 target modules, full uniform coverage (no include/exclude filter) -- verified from checkpoint lora_config + state_dict', 'optimizer': 'AdamW, betas=(0.9,0.95), weight_decay=0.01, eps=1e-8, lr=2e-4 -- verified from checkpoint optimizer_states param_groups', 'lr_schedule': 'constant, peak lr 2e-4 (checkpoint lr_schedulers list is empty -- no scheduler)', 'precision': 'bf16', 'context_len': 'T=512 frames, 47.55s (10.7666 fps)', 'batch_seed': 'batch 4, seed not recorded in checkpoint', 'steps': 'epoch 5 and epoch 9 (terminal) both metered; avg_loss not recorded at these ckpts', 'corpus': 'avp corpus (generic name; scale redacted per spec)', 'objective': 'rectified-flow, standard SA3 DoRA training loss (no auxiliary control loss)', 'extras': 'dora-rows adapter_type, dropout=0.0'}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2990 | 4 | 99.85 | 115.57 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 5980 | 9 | 139.62 | 129.52 | 31.69 | --- | 94.76 | 94.76 | ✓ | 1907.2 |


### `adamw_avp_t512_bs4_lr5e5`
> **Recipe:** {'base_model': 'SA3 medium (SAME latent, 10.77 Hz)', 'method': 'DoRA (dora-rows)', 'rank_alpha': 'rank 128, alpha 128 (alpha=rank convention, scaling=1); 229 target modules, full uniform coverage (no include/exclude filter) -- verified from checkpoint lora_config + state_dict', 'optimizer': 'AdamW, betas=(0.9,0.95), weight_decay=0.01, eps=1e-8, lr=5e-5 -- verified from checkpoint optimizer_states param_groups', 'lr_schedule': 'constant, peak lr 5e-5 (checkpoint lr_schedulers list is empty -- no scheduler)', 'precision': 'bf16', 'context_len': 'T=512 frames, 47.55s (10.7666 fps)', 'batch_seed': 'batch 4, seed not recorded in checkpoint', 'steps': 'epoch 5 and epoch 9 (terminal) both metered; avg_loss not recorded at these ckpts', 'corpus': 'avp corpus (generic name; scale redacted per spec)', 'objective': 'rectified-flow, standard SA3 DoRA training loss (no auxiliary control loss)', 'extras': 'dora-rows adapter_type, dropout=0.0'}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5980 | 9 | 41.08 | 103.97 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `adamw_fair_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5980 | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 25426.1 |


### `adamw_fair_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5980 | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 25426.1 |


### `adamw_goa_t512_bs1_lr1e4`
> **Recipe:** {'base_model': 'SA3 medium (SAME latent, 10.77 Hz)', 'method': 'DoRA (dora-rows)', 'rank_alpha': 'rank 128, alpha 128 (alpha=rank convention, scaling=1); 229 target modules, full uniform coverage (no include/exclude filter) -- verified from checkpoint lora_config + state_dict', 'optimizer': 'AdamW, betas=(0.9,0.95), weight_decay=0.01, eps=1e-8, lr=1e-4 -- verified from checkpoint optimizer_states param_groups', 'lr_schedule': 'constant, peak lr 1e-4 (checkpoint lr_schedulers list is empty -- no scheduler)', 'precision': 'bf16', 'context_len': 'T=512 frames, 47.55s (10.7666 fps)', 'batch_seed': 'batch 1, seed not recorded in checkpoint', 'steps': 'epoch 5 and epoch 9 (terminal) both metered; avg_loss not recorded at these ckpts', 'corpus': 'goa corpus (generic name; scale redacted per spec)', 'objective': 'rectified-flow, standard SA3 DoRA training loss (no auxiliary control loss)', 'extras': 'dora-rows adapter_type, dropout=0.0'}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 54000 | 9 | 185.88 | 142.48 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `adamw_goa_t512_bs4_lr1e4`
> **Recipe:** {'base_model': 'SA3 medium (SAME latent, 10.77 Hz)', 'method': 'DoRA (dora-rows)', 'rank_alpha': 'rank 128, alpha 128 (alpha=rank convention, scaling=1); 229 target modules, full uniform coverage (no include/exclude filter) -- verified from checkpoint lora_config + state_dict', 'optimizer': 'AdamW, betas=(0.9,0.95), weight_decay=0.01, eps=1e-8, lr=1e-4 -- verified from checkpoint optimizer_states param_groups', 'lr_schedule': 'constant, peak lr 1e-4 (checkpoint lr_schedulers list is empty -- no scheduler)', 'precision': 'bf16', 'context_len': 'T=512 frames, 47.55s (10.7666 fps)', 'batch_seed': 'batch 4, seed not recorded in checkpoint', 'steps': 'epoch 5 and epoch 9 (terminal) both metered; avg_loss not recorded at these ckpts', 'corpus': 'goa corpus (generic name; scale redacted per spec)', 'objective': 'rectified-flow, standard SA3 DoRA training loss (no auxiliary control loss)', 'extras': 'dora-rows adapter_type, dropout=0.0'}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 13500 | 9 | 103.41 | 114.64 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `adamw_goa_t512_bs4_lr2e4`
> **Recipe:** {'base_model': 'SA3 medium (SAME latent, 10.77 Hz)', 'method': 'DoRA (dora-rows)', 'rank_alpha': 'rank 128, alpha 128 (alpha=rank convention, scaling=1); 229 target modules, full uniform coverage (no include/exclude filter) -- verified from checkpoint lora_config + state_dict', 'optimizer': 'AdamW, betas=(0.9,0.95), weight_decay=0.01, eps=1e-8, lr=2e-4 -- verified from checkpoint optimizer_states param_groups', 'lr_schedule': 'constant, peak lr 2e-4 (checkpoint lr_schedulers list is empty -- no scheduler)', 'precision': 'bf16', 'context_len': 'T=512 frames, 47.55s (10.7666 fps)', 'batch_seed': 'batch 4, seed not recorded in checkpoint', 'steps': 'epoch 5 and epoch 9 (terminal) both metered; avg_loss not recorded at these ckpts', 'corpus': 'goa corpus (generic name; scale redacted per spec)', 'objective': 'rectified-flow, standard SA3 DoRA training loss (no auxiliary control loss)', 'extras': 'dora-rows adapter_type, dropout=0.0'}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 13500 | 9 | 188.29 | 144.94 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `adamw_goa_t512_bs4_lr5e5`
> **Recipe:** {'base_model': 'SA3 medium (SAME latent, 10.77 Hz)', 'method': 'DoRA (dora-rows)', 'rank_alpha': 'rank 128, alpha 128 (alpha=rank convention, scaling=1); 229 target modules, full uniform coverage (no include/exclude filter) -- verified from checkpoint lora_config + state_dict', 'optimizer': 'AdamW, betas=(0.9,0.95), weight_decay=0.01, eps=1e-8, lr=5e-5 -- verified from checkpoint optimizer_states param_groups', 'lr_schedule': 'constant, peak lr 5e-5 (checkpoint lr_schedulers list is empty -- no scheduler)', 'precision': 'bf16', 'context_len': 'T=512 frames, 47.55s (10.7666 fps)', 'batch_seed': 'batch 4, seed not recorded in checkpoint', 'steps': 'epoch 5 and epoch 9 (terminal) both metered; avg_loss not recorded at these ckpts', 'corpus': 'goa corpus (generic name; scale redacted per spec)', 'objective': 'rectified-flow, standard SA3 DoRA training loss (no auxiliary control loss)', 'extras': 'dora-rows adapter_type, dropout=0.0'}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 13500 | 9 | 56.15 | 104.69 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `adamw_lr1e-4`
> **Verdict / Note:** AdamW baseline, lr 1e-4. Steps 1000-4000 clean; RESUMED to 6000 and the resume introduced a discontinuity (step_cos -0.4993 at step 5000, net displacement DROPPED 65.6->45.9 and never recovered) -- Lightning restores model+optimizer but not dataloader/shuffle position. Superseded by adamw_scratch_step5000; use that instead. Kim: s6000 'not entirely bad'.

> **Recipe:** adamw · lr 1e-4 · rank 128 · bs 8 · T512 · bf16 · warmup 200 · clip 1.0 · seed 42 · 6000 steps (4000 + resumed 2000)

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | 27 | 32.71 | 101.66 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |
| 2000 | 54 | 47.18 | 104.53 | 30.04 | --- | 30.04 | 30.04 | ✓ | 1907.2 |
| 3000 | 81 | 58.47 | 107.39 | 29.25 | +0.0878 | 59.30 | 43.74 | ✓ | 1907.2 |
| 4000 | 108 | 68.12 | 110.21 | 28.81 | +0.0581 | 88.11 | 54.73 | ✓ | 1907.2 |
| 5000 | 135 | 32.38 | 101.55 | 66.03 | -0.5013 | 154.14 | 37.82 | ✓ | 1907.2 |
| 6000 | 162 | 46.79 | 104.41 | 29.94 | -0.1815 | 184.08 | 47.61 | ✓ | 1907.2 |


### `adamw_lr3e-4_step2000`
> **Verdict / Note:** Does a 3x-faster AdamW catch up to Fusion in 2000 steps? NO. Audiobox CE 6.51 +/- 0.55, joint-LOWEST of all arms. Mean RF loss over steps 1500-2000 was 0.7487 vs 0.7501 at lr 1e-4 -- a 3x LR change moved the loss by 0.0014, i.e. the loss is blind to this axis; judge by ear. path_eff 1.000 (single interval, step_cos undefined at 2 checkpoints).

> **Recipe:** adamw · lr 3e-4 · rank 128 · bs 8 · T512 · bf16 · warmup 200 · clip 1.0 · seed 42 · 2000 steps

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | 27 | 88.80 | 112.56 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |
| 2000 | 54 | 125.00 | 124.73 | 84.89 | --- | 84.89 | 84.89 | ✓ | 1907.2 |


### `adamw_scratch_step5000`
> **Verdict / Note:** Clean uninterrupted AdamW baseline to 5000 steps, run to avoid the resume bug in adamw_lr1e-4. Smooth ~34-36/1000-step velocity, path_eff 0.550, step_cos 0.087. Kim's pick of the AdamW arms: 'more engaging and coherent things'. Audiobox CE 6.72.

> **Recipe:** adamw · lr 1e-4 · rank 128 · bs 8 · T512 · bf16 · warmup 200 · clip 1.0 · seed 42 · 5000 steps

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | 27 | 32.72 | 101.65 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |
| 2000 | 54 | 47.17 | 104.50 | 30.04 | --- | 30.04 | 30.04 | ✓ | 1907.2 |
| 3000 | 81 | 58.37 | 107.31 | 29.19 | +0.0851 | 59.23 | 43.63 | ✓ | 1907.2 |
| 4000 | 108 | 67.97 | 110.11 | 28.77 | +0.0564 | 88.00 | 54.58 | ✓ | 1907.2 |
| 5000 | 135 | 76.39 | 112.82 | 28.51 | +0.0373 | 116.51 | 63.96 | ✓ | 1907.2 |


### `analysis`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `aug8ddp_ddp_smoke_dora`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1350 | 1 | 121.42 | 98.81 | --- | --- | 0.00 | 0.00 | ✓ | 3814.2 |


### `base_fusion`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 20 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2363.9 |
| 40 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2363.9 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2363.9 |


### `beat_activation_ema20`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 2 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 3 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 6 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 8 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 10 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 13 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 14 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 16 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 17 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 18 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `beat_activation_ema40`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 2 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 3 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 6 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 8 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 10 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 13 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 14 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 16 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 17 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 18 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 21 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 22 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 23 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 24 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 25 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 26 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 27 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 28 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 29 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 30 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 31 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 32 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 33 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 34 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 35 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 36 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 37 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 38 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 39 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 40 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `bf16_plain_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5980 | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 34887.1 |
| 7176 | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 26282.3 |


### `bf16_plain_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5980 | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 34887.1 |
| 7176 | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 28010.4 |


### `bf16cmp_avp_t512_bs8_lr1e4`
> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 7, 'global_step': 2392, 'provenance': {'checkpoint': 'manifest:bf16cmp_avp_t512_bs8_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 598 | 1 | 88.25 | 98.98 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 897 | 2 | 106.41 | 99.31 | 115.51 | --- | 34.54 | 34.54 | ✓ | 635.7 |
| 1196 | 3 | 121.91 | 99.67 | 101.42 | +0.6740 | 64.86 | 59.36 | ✓ | 635.7 |
| 1495 | 4 | 135.69 | 100.07 | 92.17 | +0.7074 | 92.42 | 79.46 | ✓ | 635.7 |
| 1794 | 5 | 148.27 | 100.50 | 85.58 | +0.7252 | 118.01 | 96.70 | ✓ | 635.7 |
| 2093 | 6 | 159.87 | 100.93 | 79.69 | +0.7380 | 141.84 | 111.92 | ✓ | 635.7 |
| 2392 | 7 | 170.67 | 101.37 | 75.74 | +0.7364 | 164.48 | 125.64 | ✓ | 3814.2 |


### `bf16cmp_avp_t512_bs8_lr1e4_repr`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 7, 'global_step': 2392, 'provenance': {'checkpoint': 'manifest:bf16cmp_avp_t512_bs8_lr1e4_repr', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 598 | 1 | 88.25 | 98.98 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 897 | 2 | 106.41 | 99.31 | 115.51 | --- | 34.54 | 34.54 | ✓ | 635.7 |
| 1196 | 3 | 121.91 | 99.67 | 101.42 | +0.6740 | 64.86 | 59.36 | ✓ | 635.7 |
| 1495 | 4 | 135.69 | 100.07 | 92.17 | +0.7074 | 92.42 | 79.46 | ✓ | 635.7 |
| 1794 | 5 | 148.27 | 100.50 | 85.58 | +0.7252 | 118.01 | 96.70 | ✓ | 635.7 |
| 2093 | 6 | 159.87 | 100.93 | 79.69 | +0.7380 | 141.84 | 111.92 | ✓ | 635.7 |
| 2392 | 7 | 170.67 | 101.37 | 75.74 | +0.7364 | 164.48 | 125.64 | ✓ | 3814.2 |


### `bf16cmp_goa_t512_bs8_lr1e4`
> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 7, 'global_step': 5400, 'provenance': {'checkpoint': 'manifest:bf16cmp_goa_t512_bs8_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 675 | 0 | 91.08 | 98.77 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 1350 | 1 | 124.26 | 98.98 | 90.21 | --- | 60.89 | 60.89 | ✓ | 635.7 |
| 2025 | 2 | 149.33 | 99.29 | 73.96 | +0.5493 | 110.82 | 97.68 | ✓ | 635.7 |
| 2700 | 3 | 170.29 | 99.66 | 64.64 | +0.6365 | 154.46 | 125.64 | ✓ | 635.7 |
| 3375 | 4 | 188.56 | 100.06 | 58.17 | +0.6811 | 193.72 | 148.73 | ✓ | 635.7 |
| 4050 | 5 | 204.94 | 100.48 | 53.59 | +0.6977 | 229.89 | 168.67 | ✓ | 635.7 |
| 4725 | 6 | 219.93 | 100.90 | 50.27 | +0.7032 | 263.83 | 186.44 | ✓ | 635.7 |
| 5400 | 7 | 233.77 | 101.34 | 47.48 | +0.7046 | 295.88 | 202.51 | ✓ | 3814.2 |


### `chroma_heads`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 19.2 |


### `dora128_300trk__59h2y4zo`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5 | 0 | 1.06 | 34.90 | --- | --- | 0.00 | 0.00 | ✓ | 82.5 |
| 10 | 1 | 1.75 | 34.93 | 165.56 | --- | 0.83 | 0.83 | ✓ | 82.5 |
| 15 | 2 | 2.32 | 34.98 | 147.90 | +0.8128 | 1.57 | 1.49 | ✓ | 82.5 |
| 20 | 3 | 2.81 | 35.04 | 134.97 | +0.8330 | 2.24 | 2.05 | ✓ | 82.5 |
| 25 | 4 | 3.21 | 35.10 | 128.05 | +0.8071 | 2.88 | 2.50 | ✓ | 82.5 |
| 30 | 5 | 3.55 | 35.16 | 122.88 | +0.8293 | 3.50 | 2.89 | ✓ | 82.5 |
| 35 | 6 | 3.84 | 35.21 | 114.10 | +0.8204 | 4.07 | 3.23 | ✓ | 82.5 |


### `dora128_47s_newcaptions_5ep`
> **Verdict / Note:** First tiered-caption A/B (5 epochs) — the new caption system made outputs noticeably more consistent (tighter range) than the old baked-in prompts; an initial "era-steering" read was retracted as seed noise at n=2 seeds.

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': ['seconds_total']}, 'target_modules_count': 228, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0002, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 4, 'global_step': 6750, 'provenance': {'checkpoint': 'manifest:dora128_47s_newcaptions_5ep', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1350 | 0 | 229.42 | 100.85 | --- | --- | 0.00 | 0.00 | ✓ | 635.2 |
| 2700 | 1 | 312.19 | 104.63 | 118.63 | --- | 160.16 | 160.16 | ✓ | 635.2 |
| 4050 | 2 | 372.53 | 108.28 | 97.21 | +0.5053 | 291.39 | 253.21 | ✓ | 635.2 |
| 5400 | 3 | 421.18 | 111.68 | 84.53 | +0.5964 | 405.50 | 321.41 | ✓ | 635.2 |
| 6750 | 4 | 462.30 | 114.83 | 76.02 | +0.6377 | 508.13 | 375.92 | ✓ | 3811.2 |


### `dora128_everything_8ep_lr0.5x`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': ['seconds_total']}, 'target_modules_count': 228, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 7, 'global_step': 12216, 'provenance': {'checkpoint': 'manifest:dora128_everything_8ep_lr0.5x', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1527 | 0 | 127.38 | 98.38 | --- | --- | 0.00 | 0.00 | ✓ | 635.2 |
| 3054 | 1 | 175.43 | 99.08 | 58.22 | --- | 88.90 | 88.90 | ✓ | 635.2 |
| 4581 | 2 | 211.58 | 99.91 | 47.88 | +0.5324 | 162.02 | 142.03 | ✓ | 635.2 |
| 6108 | 3 | 241.50 | 100.83 | 41.81 | +0.6215 | 225.87 | 182.00 | ✓ | 635.2 |
| 7635 | 4 | 267.32 | 101.74 | 37.73 | +0.6601 | 283.48 | 214.65 | ✓ | 635.2 |
| 9162 | 5 | 290.17 | 102.65 | 34.73 | +0.6783 | 336.51 | 242.56 | ✓ | 635.2 |
| 10689 | 6 | 310.77 | 103.54 | 32.41 | +0.6857 | 386.00 | 267.07 | ✓ | 635.2 |
| 12216 | 7 | 329.56 | 104.41 | 30.57 | +0.6849 | 432.68 | 289.03 | ✓ | 3811.2 |


### `dora128_everything_8ep_lr0.5x_cont5`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': ['seconds_total']}, 'target_modules_count': 228, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 4, 'global_step': 7635, 'provenance': {'checkpoint': 'manifest:dora128_everything_8ep_lr0.5x_cont5', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1527 | 0 | 347.85 | 105.44 | --- | --- | 0.00 | 0.00 | ✓ | 635.2 |
| 3054 | 1 | 365.55 | 106.60 | 27.47 | --- | 41.95 | 41.95 | ✓ | 635.2 |
| 4581 | 2 | 382.45 | 107.80 | 26.29 | +0.6474 | 82.10 | 74.51 | ✓ | 635.2 |
| 6108 | 3 | 398.54 | 109.04 | 25.33 | +0.6358 | 120.77 | 103.58 | ✓ | 635.2 |
| 7635 | 4 | 413.81 | 110.28 | 24.56 | +0.6215 | 158.27 | 129.87 | ✓ | 3811.2 |


### `dora128_everything_8ep_lr1x`
> **Verdict / Note:** One of two full-corpus 8-epoch DoRA runs (2e-4) that fed the later avp analysis boards — no distinct standalone listening verdict recorded for this run vs its lr3x sibling.

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': ['seconds_total']}, 'target_modules_count': 228, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0002, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 7, 'global_step': 12216, 'provenance': {'checkpoint': 'manifest:dora128_everything_8ep_lr1x', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1527 | 0 | 242.42 | 101.33 | --- | --- | 0.00 | 0.00 | ✓ | 635.2 |
| 3054 | 1 | 329.25 | 105.64 | 111.01 | --- | 169.51 | 169.51 | ✓ | 635.2 |
| 4581 | 2 | 392.68 | 109.70 | 91.20 | +0.5019 | 308.77 | 268.00 | ✓ | 635.2 |
| 6108 | 3 | 443.64 | 113.45 | 79.22 | +0.5941 | 429.73 | 339.88 | ✓ | 635.2 |
| 7635 | 4 | 486.44 | 116.86 | 71.17 | +0.6317 | 538.41 | 396.94 | ✓ | 635.2 |
| 9162 | 5 | 523.39 | 119.98 | 65.36 | +0.6485 | 638.21 | 444.44 | ✓ | 635.2 |
| 10689 | 6 | 555.84 | 122.82 | 60.80 | +0.6529 | 731.04 | 485.07 | ✓ | 635.2 |
| 12216 | 7 | 584.71 | 125.42 | 57.30 | +0.6497 | 818.53 | 520.55 | ✓ | 3811.2 |


### `dora128_everything_8ep_lr3x`
> **Verdict / Note:** One of two full-corpus 8-epoch DoRA runs (6e-4) that fed the later avp analysis boards — no distinct standalone listening verdict recorded for this run vs its lr1x sibling.

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': ['seconds_total']}, 'target_modules_count': 228, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0006, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 7, 'global_step': 12216, 'provenance': {'checkpoint': 'manifest:dora128_everything_8ep_lr3x', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1527 | 0 | 670.08 | 139.57 | --- | --- | 0.00 | 0.00 | ✓ | 635.2 |
| 3054 | 1 | 877.15 | 167.55 | 303.38 | --- | 463.26 | 463.26 | ✓ | 635.2 |
| 4581 | 2 | 1014.64 | 188.25 | 244.33 | +0.4398 | 836.36 | 711.24 | ✓ | 635.2 |
| 6108 | 3 | 1116.16 | 204.70 | 209.58 | +0.5353 | 1156.38 | 878.78 | ✓ | 635.2 |
| 7635 | 4 | 1194.04 | 217.86 | 185.98 | +0.5726 | 1440.37 | 1001.68 | ✓ | 635.2 |
| 9162 | 5 | 1255.12 | 228.64 | 169.51 | +0.5826 | 1699.22 | 1096.04 | ✓ | 635.2 |
| 10689 | 6 | 1303.97 | 237.72 | 157.40 | +0.5806 | 1939.57 | 1170.80 | ✓ | 635.2 |
| 12216 | 7 | 1343.38 | 245.09 | 147.43 | +0.5751 | 2164.69 | 1231.20 | ✓ | 3811.2 |


### `dora128_mix3_nodas_20260918_231123`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 500 | 0 | 697.09 | 146.35 | --- | --- | 0.00 | 0.00 | ✓ | 2629.5 |
| 1000 | 0 | 1328.39 | 236.40 | 2399.83 | --- | 1199.92 | 1199.92 | ✓ | 2629.5 |
| 1500 | 0 | 1689.70 | 298.91 | 2472.38 | -0.1141 | 2436.11 | 1621.53 | ✓ | 2629.5 |
| 2000 | 0 | 7699.91 | 1535.06 | 15010.80 | +0.0040 | 9941.51 | 7684.84 | ✓ | 2629.5 |
| 2500 | 1 | 8626.54 | 1798.84 | 8910.88 | -0.0656 | 14396.95 | 8615.61 | ✓ | 2629.5 |
| 3000 | 1 | 8561.61 | 1826.09 | 7959.43 | -0.0971 | 18376.66 | 8554.77 | ✓ | 2629.5 |
| 3500 | 1 | 10432.22 | 2184.98 | 13528.82 | +0.0904 | 25141.07 | 10429.36 | ✓ | 2629.5 |
| 4000 | 1 | 11555.92 | 2421.00 | 11503.07 | +0.0904 | 30892.61 | 11555.57 | ✓ | 2629.5 |
| 4500 | 2 | 11918.84 | 2554.61 | 12824.64 | -0.0555 | 37304.93 | 11921.11 | ✓ | 2629.5 |
| 5000 | 2 | 10931.76 | 2407.95 | 8235.57 | -0.1300 | 41422.71 | 10936.58 | ✓ | 2629.5 |
| 5500 | 2 | 11221.44 | 2471.76 | 12335.11 | +0.0278 | 47590.27 | 11228.16 | ✓ | 2629.5 |
| 6000 | 2 | 10419.36 | 2302.18 | 7724.15 | -0.0953 | 51452.34 | 10428.51 | ✓ | 2629.5 |
| 6500 | 3 | 9672.09 | 2139.54 | 7335.07 | +0.0468 | 55119.88 | 9683.74 | ✓ | 2629.5 |
| 7000 | 3 | 9122.36 | 2022.52 | 7142.61 | +0.0258 | 58691.19 | 9136.26 | ✓ | 2629.5 |
| 7500 | 3 | 8708.94 | 1919.03 | 7021.74 | -0.0155 | 62202.06 | 8724.89 | ✓ | 2629.5 |


### `dora128_mix3_overnight_20260918_084329`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 500 | 0 | 4006.92 | 796.21 | --- | --- | 0.00 | 0.00 | ✓ | 2629.5 |
| 1000 | 0 | 9381.28 | 1918.49 | 17087.46 | --- | 8543.73 | 8543.73 | ✓ | 2629.5 |
| 1500 | 0 | 10156.48 | 2194.17 | 13086.43 | -0.2041 | 15086.95 | 9643.06 | ✓ | 2629.5 |
| 2000 | 0 | 10218.31 | 2288.01 | 11972.60 | -0.1251 | 21073.25 | 9917.52 | ✓ | 2629.5 |
| 2500 | 1 | 10170.52 | 2321.71 | 11778.44 | -0.1035 | 26962.47 | 10041.44 | ✓ | 2629.5 |
| 3000 | 1 | 10091.91 | 2330.39 | 11744.44 | -0.1094 | 32834.69 | 10105.81 | ✓ | 2629.5 |
| 3500 | 1 | 10044.29 | 2350.81 | 11702.02 | -0.1176 | 38685.70 | 10172.24 | ✓ | 2629.5 |
| 4000 | 1 | 9925.20 | 2332.96 | 11615.11 | -0.1251 | 44493.25 | 10152.88 | ✓ | 2629.5 |


### `dora128_newcap_continued_3more`
> **Verdict / Note:** 3-epoch warm-started continuation of the newcaptions run (loss 0.766→0.747), producing the "ep7-equivalent" newcaptions checkpoint referenced in later caption-system comparisons.

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': ['seconds_total']}, 'target_modules_count': 228, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0002, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 2, 'global_step': 4050, 'provenance': {'checkpoint': 'manifest:dora128_newcap_continued_3more', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1350 | 0 | 499.30 | 117.92 | --- | --- | 0.00 | 0.00 | ✓ | 635.2 |
| 2700 | 1 | 533.31 | 121.03 | 64.33 | --- | 86.84 | 86.84 | ✓ | 635.2 |
| 4050 | 2 | 564.28 | 124.02 | 60.49 | +0.6383 | 168.50 | 152.52 | ✓ | 3811.2 |


### `dora128adj_avp_8ep`
> **Verdict / Note:** Rank-128-adjusted AVP arm — completed via a warm-started continuation from an accidental partial run; later confirmed among the more tempo-stable ranks (86% stable) in WINTERMUTE's tempo-IQR triangulation. Flagged 2026-09-17 (Kim's own spectral/listening pass over the mixtape corpus): this arm's ptm renders (ep3, ep6) produce the worst harsh-timbre outliers in the whole genre-fusion set — wide, thin spectral peaks/valleys (5-14kHz bumps of 3-8dB, paired with midrange dips e.g. near the track's own B3/root), a "roller-coaster" full-spectrum contour, and an overall smoothly-distorted/pushed-level character (not digital clipping). 5 worst-offender clips quarantined to renders/_QUARANTINE_2026-09-17_harsh/ and dropped from the mixtape order; not pursued as a fix (deprioritized in favor of finishing a shareable mixtape) — see kim_feedback. UPDATE 2026-09-17 (Wintermute, WORKLOG): measured, this is sharper than "the checkpoint is harsh" -- of the 40 ear-flagged clips, 23 come from ONE render set (genre_fusion_probe_local, OOD genre-fusion prompts) at 74.2% harsh vs 35.1% for this same ptm+cfg1 family on normal prompts and 28.6% for non-ptm arms -- harshness tracks the OOD PROMPT more than the checkpoint. Also corrects the mechanism: per-band t-test (Bonferroni) found the significant bands are ALL LOW (20-605 Hz, -3 to -4 dB, d~-0.9), not high -- flagged clips are THIN (missing low-mid body), not excessive-treble; the rms_energy_air head/target used in the bracket tests above cannot fix this (confirmed no significant band anywhere in 2.5-22kHz) and an HF-cut approach would make it worse, matching what the LatCH bracket's degenerate absolute-energy solution actually did (cut air AND body together). UPDATE 2026-09-17 (GHOST-NOTE, direct waveform measurement -- SEVERITY REVISED UPWARD): not just 5 subjectively-harsh clips. Scanning single-sample amplitude jumps (>0.6 normalized) across the full genre_fusion_probe_local (gf2_*) OOD-prompt family found 18 of its clips (from this checkpoint and dora16_avp_originals_earlyeps's ptm renders) carry genuine waveform corruption -- rapid, large-amplitude sign-alternation with counts from 34 up to 5783 per ~47.5s clip, against 0-2 for a normal clip in this corpus. This matches and sharpens Wintermute's independent finding (WORKLOG 2026-09-17: 74.2% of this prompt family's clips ear-flagged harsh vs 28-35% elsewhere) -- the OOD-prompt family doesn't just sound worse subjectively, a majority of it is measurably corrupted at the sample level. Entire gf2_* family (26/77 clips, spanning this checkpoint and dora16_avp_originals_earlyeps) dropped from the mixtape, not just the 5 originally ear-flagged clips.

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 45.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0002, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 6, 'global_step': 2093, 'provenance': {'checkpoint': 'manifest:dora128adj_avp_8ep', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 299 | 0 | 121.81 | 100.32 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 598 | 1 | 166.58 | 101.54 | 269.30 | --- | 80.52 | 80.52 | ✓ | 635.7 |
| 897 | 2 | 200.71 | 102.88 | 220.91 | +0.5656 | 146.57 | 129.86 | ✓ | 635.7 |
| 1196 | 3 | 229.60 | 104.30 | 193.71 | +0.6515 | 204.49 | 167.76 | ✓ | 635.7 |
| 1495 | 4 | 254.85 | 105.72 | 174.61 | +0.6874 | 256.70 | 199.18 | ✓ | 635.7 |
| 1794 | 5 | 277.50 | 107.13 | 160.50 | +0.7131 | 304.69 | 226.40 | ✓ | 635.7 |
| 2093 | 6 | 298.25 | 108.52 | 149.48 | +0.7237 | 349.38 | 250.78 | ✓ | 3814.2 |


### `dora128adj_avp_8ep_final`
> **Verdict / Note:** The finished 8/8-epoch rank-128-adjusted AVP run (warm-started from epoch 6) — see dora128adj_avp_8ep for its tempo-stability verdict.

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 45.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0002, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 0, 'global_step': 299, 'provenance': {'checkpoint': 'manifest:dora128adj_avp_8ep_final', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 299 | 0 | 317.43 | 109.85 | --- | --- | 0.00 | 0.00 | ✓ | 3814.2 |


### `dora128adj_avp_aug10_lr1e4`
> **Verdict / Note:** "Arm G" — tempo-stable across its ENTIRE 3000-step run (mean IQR 0.94, never collapses), the strongest confirmation of the lower-LR/higher-rank stability hypothesis.

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 45.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 74, 'global_step': 3000, 'provenance': {'checkpoint': 'manifest:dora128adj_avp_aug10_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 300 | 7 | 66.69 | 100.07 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 600 | 14 | 94.56 | 101.10 | 149.67 | --- | 44.90 | 44.90 | ✓ | 635.7 |
| 900 | 22 | 115.46 | 101.87 | 123.07 | +0.6183 | 81.82 | 73.68 | ✓ | 635.7 |
| 1200 | 29 | 133.35 | 102.65 | 108.28 | +0.6997 | 114.30 | 96.31 | ✓ | 635.7 |
| 1500 | 37 | 149.39 | 103.46 | 97.65 | +0.7363 | 143.60 | 115.57 | ✓ | 635.7 |
| 1800 | 44 | 163.89 | 104.23 | 89.70 | +0.7582 | 170.51 | 132.51 | ✓ | 635.7 |
| 2100 | 52 | 177.30 | 104.99 | 84.40 | +0.7673 | 195.83 | 147.84 | ✓ | 635.7 |
| 2400 | 59 | 189.93 | 105.78 | 79.88 | +0.7678 | 219.79 | 162.02 | ✓ | 635.7 |
| 2700 | 67 | 201.82 | 106.56 | 75.85 | +0.7736 | 242.55 | 175.22 | ✓ | 635.7 |
| 3000 | 74 | 213.15 | 107.32 | 73.38 | +0.7667 | 264.56 | 187.65 | ✓ | 3814.2 |


### `dora16_avp_8ep`
> **Verdict / Note:** Early AVP DoRA arm (rank 16) — completed cleanly overnight; superseded as the tempo/quality reference by the later rank/LR comparison arms (r128adj, arm G).

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 6, 'global_step': 2093, 'provenance': {'checkpoint': 'manifest:dora16_avp_8ep', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 299 | 0 | 74.61 | 59.41 | --- | --- | 0.00 | 0.00 | ✓ | 82.6 |
| 598 | 1 | 95.99 | 72.02 | 146.97 | --- | 43.94 | 43.94 | ✓ | 82.6 |
| 897 | 2 | 111.31 | 81.13 | 117.80 | +0.5407 | 79.17 | 69.61 | ✓ | 82.6 |
| 1196 | 3 | 123.76 | 88.37 | 103.75 | +0.6018 | 110.19 | 88.42 | ✓ | 82.6 |
| 1495 | 4 | 134.47 | 94.51 | 91.74 | +0.6660 | 137.62 | 103.56 | ✓ | 82.6 |
| 1794 | 5 | 143.98 | 99.89 | 83.56 | +0.6883 | 162.60 | 116.37 | ✓ | 82.6 |
| 2093 | 6 | 152.71 | 104.83 | 81.67 | +0.6551 | 187.02 | 127.72 | ✓ | 82.6 |
| 2392 | 7 | 161.15 | 109.60 | 84.98 | +0.6199 | 212.43 | 138.36 | ✓ | 412.8 |


### `dora16_avp_familiarity_8ep`
> **Verdict / Note:** Novelty-gating (familiarity_beta) mechanism verified working end-to-end (weight spread 0.87-1.13 after the ep-1 warmup, loss 0.726) — musical-quality impact not yet separately assessed.

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 4, 'global_step': 1495, 'provenance': {'checkpoint': 'manifest:dora16_avp_familiarity_8ep', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 299 | 0 | 73.29 | 58.69 | --- | --- | 0.00 | 0.00 | ✓ | 82.6 |
| 598 | 1 | 93.62 | 70.63 | 148.06 | --- | 44.27 | 44.27 | ✓ | 82.6 |
| 897 | 2 | 110.76 | 80.86 | 133.38 | +0.4971 | 84.15 | 72.84 | ✓ | 82.6 |
| 1196 | 3 | 126.20 | 90.13 | 120.98 | +0.6038 | 120.33 | 95.23 | ✓ | 82.6 |
| 1495 | 4 | 140.03 | 98.38 | 105.36 | +0.7071 | 151.83 | 113.68 | ✓ | 82.6 |
| 1794 | 5 | 152.12 | 105.42 | 95.51 | +0.6897 | 180.38 | 129.02 | ✓ | 82.6 |
| 2093 | 6 | 162.84 | 111.54 | 86.34 | +0.7138 | 206.20 | 142.15 | ✓ | 82.6 |
| 2392 | 7 | 172.45 | 116.89 | 81.47 | +0.6996 | 230.56 | 153.66 | ✓ | 412.8 |


### `dora16_avp_freeform_8ep`
> **Verdict / Note:** Freeform-caption arm — a single descriptive caption did NOT fix conditioning collapse (prompt/seed ratio 0.22, same as the trigger-token baseline's 0.92); showed caption diversity, not caption quality, is what matters.

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 31, 'global_step': 1152, 'provenance': {'checkpoint': 'manifest:dora16_avp_freeform_8ep', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 288 | 7 | 72.93 | 58.79 | --- | --- | 0.00 | 0.00 | ✓ | 82.6 |
| 576 | 15 | 94.05 | 71.37 | 150.00 | --- | 43.20 | 43.20 | ✓ | 82.6 |
| 864 | 23 | 111.36 | 82.30 | 138.97 | +0.4774 | 83.22 | 71.55 | ✓ | 82.6 |
| 1152 | 31 | 127.06 | 92.25 | 125.33 | +0.6021 | 119.32 | 94.18 | ✓ | 82.6 |
| 1440 | 39 | 141.09 | 100.95 | 109.52 | +0.6830 | 150.86 | 112.85 | ✓ | 82.6 |
| 1728 | 47 | 153.90 | 108.65 | 106.56 | +0.6439 | 181.55 | 129.04 | ✓ | 82.6 |
| 2016 | 55 | 165.73 | 115.51 | 96.54 | +0.7135 | 209.35 | 143.44 | ✓ | 82.6 |
| 2304 | 63 | 176.80 | 121.77 | 94.18 | +0.6907 | 236.48 | 156.56 | ✓ | 412.8 |


### `dora16_avp_originals_64ep`
> **Verdict / Note:** "D'" — the aug-theory control arm (originals only, no augmentation). Turned out to be the LEAST tempo-stable arm (38% locked), refuting data-multimodality as the tempo-instability driver; instability is optimization-phase/LR-window-driven instead.

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 31, 'global_step': 1152, 'provenance': {'checkpoint': 'manifest:dora16_avp_originals_64ep', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 288 | 7 | 72.76 | 59.63 | --- | --- | 0.00 | 0.00 | ✓ | 82.6 |
| 576 | 15 | 94.52 | 73.29 | 150.95 | --- | 43.47 | 43.47 | ✓ | 82.6 |
| 864 | 23 | 110.66 | 83.55 | 126.82 | +0.5116 | 80.00 | 69.63 | ✓ | 82.6 |
| 1152 | 31 | 124.22 | 91.91 | 107.54 | +0.6518 | 110.97 | 89.40 | ✓ | 82.6 |
| 1440 | 39 | 136.10 | 99.01 | 101.76 | +0.6279 | 140.28 | 105.58 | ✓ | 82.6 |
| 1728 | 47 | 147.14 | 105.52 | 99.31 | +0.6324 | 168.88 | 119.94 | ✓ | 82.6 |
| 2016 | 55 | 158.09 | 111.97 | 103.17 | +0.6318 | 198.59 | 133.68 | ✓ | 82.6 |
| 2304 | 63 | 168.87 | 118.15 | 93.24 | +0.7352 | 225.45 | 146.79 | ✓ | 412.8 |


### `dora16_avp_originals_densewin`
> **Verdict / Note:** One of the fine epoch-window renders that fed the ep7-9 vs. ep31 dual-sweet-spot analysis — see dora128adj_avp_aug10_lr1e4 / the degradation-report findings for the consolidated verdict.

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': {'lr': 0.0002, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 10, 'global_step': 396, 'provenance': {'checkpoint': 'manifest:dora16_avp_originals_densewin', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 36 | 0 | 112.52 | 84.71 | --- | --- | 0.00 | 0.00 | ✓ | 82.6 |
| 72 | 1 | 114.34 | 85.85 | 143.26 | --- | 5.16 | 5.16 | ✓ | 82.6 |
| 108 | 2 | 116.13 | 86.96 | 138.38 | +0.7029 | 10.14 | 9.36 | ✓ | 82.6 |
| 144 | 3 | 117.88 | 88.05 | 138.30 | +0.6814 | 15.12 | 13.26 | ✓ | 82.6 |
| 180 | 4 | 119.60 | 89.10 | 137.96 | +0.6206 | 20.08 | 16.93 | ✓ | 82.6 |
| 216 | 5 | 121.30 | 90.14 | 131.90 | +0.6719 | 24.83 | 20.46 | ✓ | 82.6 |
| 252 | 6 | 122.95 | 91.15 | 131.51 | +0.6527 | 29.57 | 23.84 | ✓ | 82.6 |
| 288 | 7 | 124.58 | 92.14 | 126.41 | +0.6331 | 34.12 | 27.06 | ✓ | 82.6 |
| 324 | 8 | 126.18 | 93.12 | 128.84 | +0.6219 | 38.76 | 30.19 | ✓ | 82.6 |
| 360 | 9 | 127.78 | 94.10 | 158.05 | +0.4861 | 44.45 | 33.35 | ✓ | 82.6 |
| 396 | 10 | 129.37 | 95.07 | 137.26 | +0.5853 | 49.39 | 36.41 | ✓ | 412.8 |


### `dora16_avp_originals_earlyeps`
> **Verdict / Note:** One of the fine epoch-window renders that fed the ep7-9 vs. ep31 dual-sweet-spot analysis (ep31 = narrow, ringing-adjacent island; ep7-9 later found spectrally healthier). UPDATE 2026-09-17 (GHOST-NOTE, direct measurement): while rebuilding the mixtape, found this checkpoint's genre_fusion_probe_local (OOD genre-fusion prompt) ptm renders carry GENUINE WAVEFORM-LEVEL CORRUPTION, not just subjective harshness -- e.g. ep2/gf_11 has 15075 single-sample jumps >0.6 (normalized amplitude) in a 47.5s clip (~1 every 3ms of continuous distortion), ep2/gf_08 has 8161; both channels show near-identical rapid sign-alternation, not a normal percussive transient signature (a clean clip in the same corpus shows 0-2 such jumps in its whole duration). This is the single worst-measured checkpoint in the corpus for this defect. Dropped from the shareable mixtape entirely, along with the rest of the genre_fusion_probe_local (gf2_*) family (see dora128adj_avp_8ep entry) -- see [[genre-fusion-probe-waveform-corruption]].

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': {'lr': 0.0002, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 4, 'global_step': 180, 'provenance': {'checkpoint': 'manifest:dora16_avp_originals_earlyeps', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 36 | 0 | 32.23 | 39.94 | --- | --- | 0.00 | 0.00 | ✓ | 82.6 |
| 72 | 1 | 43.60 | 44.23 | 555.38 | --- | 19.99 | 19.99 | ✓ | 82.6 |
| 108 | 2 | 51.15 | 47.65 | 402.57 | +0.6372 | 34.49 | 31.29 | ✓ | 82.6 |
| 144 | 3 | 56.43 | 50.20 | 301.77 | +0.7227 | 45.35 | 38.63 | ✓ | 82.6 |
| 180 | 4 | 60.55 | 52.25 | 258.46 | +0.7246 | 54.65 | 44.11 | ✓ | 412.8 |


### `dora16_avp_originals_win7`
> **Verdict / Note:** One of the fine epoch-window renders that fed the ep7-9 vs. ep31 dual-sweet-spot analysis — see dora128adj_avp_aug10_lr1e4 / the degradation-report findings for the consolidated verdict.

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 6, 'global_step': 252, 'provenance': {'checkpoint': 'manifest:dora16_avp_originals_win7', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 36 | 0 | 60.56 | 52.25 | --- | --- | 0.00 | 0.00 | ✓ | 82.6 |
| 72 | 1 | 63.94 | 54.06 | 219.21 | --- | 7.89 | 7.89 | ✓ | 82.6 |
| 108 | 2 | 66.95 | 55.75 | 201.07 | +0.7611 | 15.13 | 14.20 | ✓ | 82.6 |
| 144 | 3 | 69.69 | 57.37 | 186.58 | +0.7729 | 21.85 | 19.63 | ✓ | 82.6 |
| 180 | 4 | 72.20 | 58.86 | 196.64 | +0.6947 | 28.93 | 24.62 | ✓ | 82.6 |
| 216 | 5 | 74.60 | 60.32 | 195.53 | +0.7141 | 35.97 | 29.31 | ✓ | 82.6 |
| 252 | 6 | 76.92 | 61.74 | 196.64 | +0.7077 | 43.04 | 33.75 | ✓ | 82.6 |
| 288 | 7 | 79.16 | 63.10 | 184.85 | +0.7302 | 49.70 | 37.91 | ✓ | 82.6 |
| 324 | 8 | 81.37 | 64.43 | 185.00 | +0.7005 | 56.36 | 41.88 | ✓ | 82.6 |
| 360 | 9 | 83.55 | 65.77 | 183.59 | +0.7072 | 62.97 | 45.65 | ✓ | 82.6 |
| 396 | 10 | 85.67 | 67.08 | 170.06 | +0.7249 | 69.09 | 49.24 | ✓ | 412.8 |


### `dora16_glitchheal_5ep_2xlr`
> **Verdict / Note:** Weight-mutation "healing" experiment — a 5-epoch LoRA trained on a glitched base neither heals nor compensates; the adapter simply dominates (~5x more shift than the glitch itself), and the glitch survives underneath as an accent.

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': ['seconds_total']}, 'target_modules_count': 228, 'rank_from_shapes': 16, 'optimizer': {'lr': 0.0002, 'betas': [0.9, 0.95], 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 4, 'global_step': 25, 'provenance': {'checkpoint': 'manifest:dora16_glitchheal_5ep_2xlr', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5 | 0 | 2.13 | 34.93 | --- | --- | 0.00 | 0.00 | ✓ | 82.5 |
| 10 | 1 | 3.32 | 35.02 | 312.50 | --- | 1.56 | 1.56 | ✓ | 82.5 |
| 15 | 2 | 4.16 | 35.11 | 262.27 | +0.6712 | 2.87 | 2.63 | ✓ | 82.5 |
| 20 | 3 | 4.81 | 35.19 | 239.28 | +0.7427 | 4.07 | 3.47 | ✓ | 82.5 |
| 25 | 4 | 5.43 | 35.28 | 224.13 | +0.7705 | 5.19 | 4.20 | ✓ | 247.6 |


### `dora16_goa_newstack_8ep`
> **Verdict / Note:** New caption-stack vs. old Hall-of-Fame checkpoint, epoch-by-epoch A/B rendered (30 clips) for Kim's direct listening — no recorded verdict yet on which stack won.

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': {'lr': 0.0002, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 7, 'global_step': 10800, 'provenance': {'checkpoint': 'manifest:dora16_goa_newstack_8ep', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1350 | 0 | 133.41 | 95.00 | --- | --- | 0.00 | 0.00 | ✓ | 82.6 |
| 2700 | 1 | 180.37 | 123.57 | 135.93 | --- | 183.51 | 183.51 | ✓ | 82.6 |
| 4050 | 2 | 212.70 | 141.54 | 59.85 | +0.2304 | 264.30 | 216.88 | ✓ | 82.6 |
| 5400 | 3 | 239.71 | 156.04 | 50.72 | +0.6044 | 332.77 | 244.91 | ✓ | 82.6 |
| 6750 | 4 | 262.77 | 168.18 | 45.76 | +0.6335 | 394.55 | 268.74 | ✓ | 82.6 |
| 8100 | 5 | 282.95 | 178.78 | 42.70 | +0.6310 | 452.20 | 289.50 | ✓ | 82.6 |
| 9450 | 6 | 301.05 | 188.24 | 39.31 | +0.6548 | 505.26 | 308.00 | ✓ | 82.6 |
| 10800 | 7 | 317.25 | 196.56 | 35.98 | +0.6737 | 553.84 | 324.52 | ✓ | 412.8 |


### `dora256_avp_aug10_lr7e5`
> **Verdict / Note:** "Arm H" (rank 256) — ruled out after repeated OOM/hang failures on the 16GB card across 4 attempts; this is the lone surviving checkpoint from a run that never completed. Max viable local rank stays 128.

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 256, 'alpha': 64.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 256, 'optimizer': {'lr': 7e-05, 'betas': [0.9, 0.95], 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 3, 'global_step': 300, 'provenance': {'checkpoint': 'manifest:dora256_avp_aug10_lr7e5', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 300 | 3 | 18.89 | 141.09 | --- | --- | 0.00 | 0.00 | ✓ | 3803.6 |


### `dora256_mixed_a128_lr5e5`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 994 | 2 | 61.12 | 140.04 | --- | --- | 0.00 | 0.00 | ✓ | 1267.8 |
| 1481 | 3 | 77.37 | 140.78 | 55.16 | --- | 26.86 | 26.86 | ✓ | 7607.2 |


### `dora256_mixed_a196_lr1e4`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 994 | 2 | 115.93 | 140.15 | --- | --- | 0.00 | 0.00 | ✓ | 1267.8 |
| 1481 | 3 | 146.47 | 142.34 | 109.04 | --- | 53.10 | 53.10 | ✓ | 7607.2 |


### `dora64_avp_tiered_lr1e4`
> **Verdict / Note:** r64 tiered-caption arm (1e-4) — same caption-diversity-fixes-collapse result as its lr2e4 sibling; part of the recipe validation (r64 + tiered captions + early-stop ~ep7-9).

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 64, 'alpha': 32.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 7, 'global_step': 288, 'provenance': {'checkpoint': 'manifest:dora64_avp_tiered_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 36 | 0 | 32.47 | 72.36 | --- | --- | 0.00 | 0.00 | ✓ | 319.6 |
| 72 | 1 | 44.02 | 74.89 | 561.70 | --- | 20.22 | 20.22 | ✓ | 319.6 |
| 108 | 2 | 51.70 | 77.04 | 402.82 | +0.6390 | 34.72 | 31.53 | ✓ | 319.6 |
| 144 | 3 | 57.57 | 78.89 | 341.34 | +0.6912 | 47.01 | 39.62 | ✓ | 319.6 |
| 180 | 4 | 62.41 | 80.54 | 287.48 | +0.7329 | 57.36 | 45.95 | ✓ | 319.6 |
| 216 | 5 | 66.68 | 82.12 | 281.10 | +0.7007 | 67.48 | 51.39 | ✓ | 319.6 |
| 252 | 6 | 70.74 | 83.75 | 276.68 | +0.7466 | 77.44 | 56.44 | ✓ | 319.6 |
| 288 | 7 | 74.57 | 85.33 | 243.92 | +0.8237 | 86.22 | 61.07 | ✓ | 319.6 |
| 324 | 8 | 78.15 | 86.89 | 229.21 | +0.7991 | 94.47 | 65.34 | ✓ | 319.6 |
| 360 | 9 | 81.54 | 88.40 | 225.08 | +0.7439 | 102.58 | 69.32 | ✓ | 319.6 |
| 396 | 10 | 84.78 | 89.86 | 225.62 | +0.7176 | 110.70 | 73.06 | ✓ | 319.6 |
| 432 | 11 | 87.84 | 91.29 | 195.32 | +0.8045 | 117.73 | 76.58 | ✓ | 1598.0 |


### `dora64_avp_tiered_lr2e4`
> **Verdict / Note:** r64 tiered-caption arm (2e-4) — tiered/diverse captions DID fix conditioning collapse where freeform failed (prompt/seed ratio 1.5-2.65 vs freeform's 0.22); later superseded as the leading recipe by the prompt-arc finding.

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 64, 'alpha': 32.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 0, 'global_step': 36, 'provenance': {'checkpoint': 'manifest:dora64_avp_tiered_lr2e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 36 | 0 | 63.61 | 79.09 | --- | --- | 0.00 | 0.00 | ✓ | 319.6 |
| 72 | 1 | 87.13 | 87.93 | 1121.15 | --- | 40.36 | 40.36 | ✓ | 319.6 |
| 108 | 2 | 102.50 | 95.08 | 814.12 | +0.6382 | 69.67 | 63.23 | ✓ | 319.6 |
| 144 | 3 | 114.48 | 101.06 | 755.84 | +0.5965 | 96.88 | 79.85 | ✓ | 319.6 |
| 180 | 4 | 124.91 | 106.65 | 626.65 | +0.7871 | 119.44 | 93.63 | ✓ | 319.6 |
| 216 | 5 | 133.64 | 111.43 | 528.19 | +0.7638 | 138.45 | 104.74 | ✓ | 319.6 |
| 252 | 6 | 141.05 | 115.51 | 463.64 | +0.7754 | 155.15 | 113.95 | ✓ | 319.6 |
| 288 | 7 | 147.72 | 119.33 | 458.76 | +0.7336 | 171.66 | 122.09 | ✓ | 319.6 |
| 324 | 8 | 153.82 | 122.96 | 427.33 | +0.7647 | 187.04 | 129.41 | ✓ | 319.6 |
| 360 | 9 | 159.45 | 126.39 | 392.27 | +0.7748 | 201.17 | 136.09 | ✓ | 319.6 |
| 396 | 10 | 164.87 | 129.78 | 450.08 | +0.6190 | 217.37 | 142.46 | ✓ | 319.6 |
| 432 | 11 | 169.95 | 132.97 | 363.75 | +0.7848 | 230.46 | 148.38 | ✓ | 1598.0 |


### `dorlor_avpaug_dora_adamw_r128a45_t256_bf16_bs128_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1728 | 95 | 47.49 | 113.63 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 2880 | 159 | 51.16 | 116.64 | 9.25 | --- | 10.66 | 10.66 | ✓ | 1907.2 |


### `dorlor_avpaug_dora_adamw_r128a45_t256_bf16_bs128_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1728 | 95 | 47.74 | 113.72 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 2880 | 159 | 51.39 | 116.70 | 9.27 | --- | 10.67 | 10.67 | ✓ | 1907.2 |


### `dorlor_avpaug_dora_fusion_r128a45_t256_bf16_bs128_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1728 | 95 | 62.42 | 103.30 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 2880 | 159 | 77.86 | 104.44 | 17.35 | --- | 19.99 | 19.99 | ✓ | 4450.0 |


### `dorlor_avpaug_dora_fusion_r128a45_t256_bf16_bs128_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1728 | 95 | 62.21 | 103.27 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 2880 | 159 | 77.52 | 104.39 | 17.23 | --- | 19.84 | 19.84 | ✓ | 4450.0 |


### `dorlor_avpaug_lora_adamw_r128a45_t256_bf16_bs128_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1728 | 95 | 47.39 | 113.06 | --- | --- | 0.00 | 0.00 | ✓ | 632.3 |
| 2880 | 159 | 51.11 | 116.05 | 9.42 | --- | 10.85 | 10.85 | ✓ | 1897.0 |


### `dorlor_avpaug_lora_adamw_r128a45_t256_bf16_bs128_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1728 | 95 | 47.59 | 113.09 | --- | --- | 0.00 | 0.00 | ✓ | 632.3 |
| 2880 | 159 | 51.29 | 116.02 | 9.40 | --- | 10.83 | 10.83 | ✓ | 1897.0 |


### `dorlor_avpaug_lora_fusion_r128a45_t256_bf16_bs128_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1728 | 95 | 73.96 | 104.00 | --- | --- | 0.00 | 0.00 | ✓ | 632.3 |
| 2880 | 159 | 89.85 | 105.19 | 18.78 | --- | 21.64 | 21.64 | ✓ | 4433.1 |


### `dorlor_avpaug_lora_fusion_r128a45_t256_bf16_bs128_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1728 | 95 | 74.34 | 104.07 | --- | --- | 0.00 | 0.00 | ✓ | 632.3 |
| 2880 | 159 | 90.12 | 105.25 | 18.68 | --- | 21.52 | 21.52 | ✓ | 4433.1 |


### `dorlor_biggoa_dora_adamw_r128a45_t256_bf16_bs128_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1746 | 17 | 41.26 | 106.37 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 3104 | 31 | 44.83 | 107.91 | 8.44 | --- | 11.46 | 11.46 | ✓ | 1907.2 |


### `dorlor_biggoa_dora_fusion_r128a45_t256_bf16_bs128_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1746 | 17 | 49.29 | 101.44 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 3104 | 31 | 61.04 | 101.88 | 12.07 | --- | 16.39 | 16.39 | ✓ | 4450.0 |


### `dorlor_biggoa_dora_fusion_r128a45_t256_bf16_bs128_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1746 | 17 | 49.48 | 101.49 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 3104 | 31 | 61.21 | 101.94 | 12.09 | --- | 16.41 | 16.41 | ✓ | 4450.0 |


### `dorlor_biggoa_lora_adamw_r128a45_t256_bf16_bs128_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1746 | 17 | 41.66 | 106.43 | --- | --- | 0.00 | 0.00 | ✓ | 632.3 |
| 3104 | 31 | 45.18 | 107.91 | 8.42 | --- | 11.44 | 11.44 | ✓ | 1897.0 |


### `dorlor_biggoa_lora_fusion_r128a45_t256_bf16_bs128_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1746 | 17 | 61.01 | 102.25 | --- | --- | 0.00 | 0.00 | ✓ | 632.3 |
| 3104 | 31 | 73.41 | 102.73 | 13.43 | --- | 18.24 | 18.24 | ✓ | 4433.1 |


### `dorlor_biggoa_lora_fusion_r128a45_t256_bf16_bs128_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1746 | 17 | 61.55 | 102.31 | --- | --- | 0.00 | 0.00 | ✓ | 632.3 |
| 3104 | 31 | 73.93 | 102.79 | 13.48 | --- | 18.30 | 18.30 | ✓ | 4433.1 |


### `dorlor_dora_adamw_r128a45_t256_bf16_bs128_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1746 | 17 | 41.30 | 106.34 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 3104 | 31 | 44.81 | 107.84 | 8.47 | --- | 11.50 | 11.50 | ✓ | 1907.2 |


### `dorlor_goa_dora_adamw_r128a45_t256_bf16_bs128_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1680 | 39 | 182.11 | 150.10 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 2688 | 63 | 45.15 | 109.83 | 163.44 | --- | 164.75 | 164.75 | ✓ | 1907.2 |


### `dorlor_goa_dora_adamw_r128a45_t256_bf16_bs128_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1680 | 39 | 42.77 | 108.31 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 2688 | 63 | 45.38 | 109.84 | 8.82 | --- | 8.89 | 8.89 | ✓ | 1907.2 |


### `dorlor_goa_dora_fusion_r128a45_t256_bf16_bs128_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1680 | 39 | 51.73 | 101.74 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 2688 | 63 | 61.68 | 102.23 | 13.34 | --- | 13.45 | 13.45 | ✓ | 4450.0 |


### `dorlor_goa_dora_fusion_r128a45_t256_bf16_bs128_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1680 | 39 | 54.01 | 102.19 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 2688 | 63 | 64.64 | 102.79 | 14.12 | --- | 14.23 | 14.23 | ✓ | 4450.0 |


### `dorlor_goa_lora_adamw_r128a45_t256_bf16_bs128_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1680 | 39 | 43.00 | 108.31 | --- | --- | 0.00 | 0.00 | ✓ | 632.3 |
| 2688 | 63 | 45.59 | 109.83 | 8.88 | --- | 8.95 | 8.95 | ✓ | 1897.0 |


### `dorlor_goa_lora_adamw_r128a45_t256_bf16_bs128_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1680 | 39 | 42.99 | 108.28 | --- | --- | 0.00 | 0.00 | ✓ | 632.3 |
| 2688 | 63 | 45.56 | 109.77 | 8.82 | --- | 8.89 | 8.89 | ✓ | 1897.0 |


### `dorlor_goa_lora_fusion_r128a45_t256_bf16_bs128_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1680 | 39 | 63.84 | 102.76 | --- | --- | 0.00 | 0.00 | ✓ | 632.3 |
| 2688 | 63 | 75.04 | 103.42 | 15.41 | --- | 15.53 | 15.53 | ✓ | 4433.1 |


### `dorlor_goa_lora_fusion_r128a45_t256_bf16_bs128_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1680 | 39 | 63.96 | 102.82 | --- | --- | 0.00 | 0.00 | ✓ | 632.3 |
| 2688 | 63 | 75.18 | 103.50 | 15.45 | --- | 15.57 | 15.57 | ✓ | 4433.1 |


### `dorlor_lora_adamw_r128a45_t256_bf16_bs128_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1746 | 17 | 41.64 | 106.42 | --- | --- | 0.00 | 0.00 | ✓ | 632.3 |
| 3104 | 31 | 45.13 | 107.91 | 8.47 | --- | 11.50 | 11.50 | ✓ | 1897.0 |


### `dorlor_suomi_dora_adamw_r128a45_t256_bf16_bs128_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1728 | 191 | 43.40 | 108.74 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 2880 | 319 | 46.77 | 110.68 | 8.91 | --- | 10.27 | 10.27 | ✓ | 1907.2 |


### `dorlor_suomi_dora_adamw_r128a45_t256_bf16_bs128_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1728 | 191 | 43.14 | 108.42 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 2880 | 319 | 46.46 | 110.29 | 8.94 | --- | 10.30 | 10.30 | ✓ | 1907.2 |


### `dorlor_suomi_dora_fusion_r128a45_t256_bf16_bs128_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1728 | 191 | 53.39 | 102.14 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 2880 | 319 | 65.54 | 102.81 | 14.03 | --- | 16.16 | 16.16 | ✓ | 4450.0 |


### `dorlor_suomi_dora_fusion_r128a45_t256_bf16_bs128_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1728 | 191 | 53.89 | 102.26 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 2880 | 319 | 66.41 | 103.00 | 14.32 | --- | 16.49 | 16.49 | ✓ | 4450.0 |


### `dorlor_suomi_lora_adamw_r128a45_t256_bf16_bs128_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1728 | 191 | 44.00 | 108.96 | --- | --- | 0.00 | 0.00 | ✓ | 632.3 |
| 2880 | 319 | 47.45 | 111.03 | 9.00 | --- | 10.37 | 10.37 | ✓ | 1897.0 |


### `dorlor_suomi_lora_adamw_r128a45_t256_bf16_bs128_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1728 | 191 | 43.29 | 108.45 | --- | --- | 0.00 | 0.00 | ✓ | 632.3 |
| 2880 | 319 | 46.56 | 110.25 | 8.95 | --- | 10.31 | 10.31 | ✓ | 1897.0 |


### `dorlor_suomi_lora_fusion_r128a45_t256_bf16_bs128_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1728 | 191 | 63.28 | 102.83 | --- | --- | 0.00 | 0.00 | ✓ | 632.3 |
| 2880 | 319 | 75.71 | 103.48 | 15.17 | --- | 17.48 | 17.48 | ✓ | 4433.1 |


### `dorlor_suomi_lora_fusion_r128a45_t256_bf16_bs128_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1728 | 191 | 63.67 | 102.98 | --- | --- | 0.00 | 0.00 | ✓ | 632.3 |
| 2880 | 319 | 76.20 | 103.67 | 15.30 | --- | 17.63 | 17.63 | ✓ | 4433.1 |


### `downbeat_activation_ema20`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 2 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 3 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 6 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 8 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 10 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 13 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 14 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 16 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 17 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 18 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `downbeat_activation_ema40`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 2 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 3 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 6 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 8 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 10 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 13 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 14 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 16 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 17 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 18 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 21 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 22 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 23 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 24 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 25 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 26 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 27 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 28 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 29 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 30 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 31 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 32 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 33 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 34 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 35 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 36 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 37 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 38 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 39 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 40 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `dq0egegi`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1350 | 0 | 34.92 | 101.09 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 2700 | 1 | 48.59 | 102.83 | 24.09 | --- | 32.52 | 32.52 | ✓ | 635.7 |
| 4050 | 2 | 59.31 | 104.65 | 24.15 | +0.0057 | 65.12 | 46.18 | ✓ | 635.7 |
| 5400 | 3 | 68.16 | 106.37 | 24.03 | -0.0062 | 97.56 | 56.61 | ✓ | 635.7 |
| 6750 | 4 | 76.02 | 108.12 | 24.07 | -0.0157 | 130.06 | 65.48 | ✓ | 635.7 |
| 8100 | 5 | 83.20 | 109.87 | 24.15 | -0.0164 | 162.66 | 73.40 | ✓ | 635.7 |
| 9450 | 6 | 89.83 | 111.59 | 24.21 | -0.0215 | 195.34 | 80.58 | ✓ | 635.7 |
| 10800 | 7 | 95.96 | 113.31 | 24.21 | -0.0234 | 228.02 | 87.20 | ✓ | 1907.2 |


### `e2_phm`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1350 | 0 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1828.8 |


### `e3hun0v6`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 4000 | 1 | 4.65 | 98.99 | --- | --- | 0.00 | 0.00 | ✓ | 2549.7 |
| 4500 | 2 | 10.14 | 99.22 | 14.86 | --- | 7.43 | 7.43 | ✓ | 2549.7 |
| 5000 | 2 | 13.97 | 99.41 | 13.76 | +0.2920 | 14.31 | 11.51 | ✓ | 2549.7 |
| 5500 | 2 | 17.27 | 99.60 | 13.31 | +0.2439 | 20.97 | 14.94 | ✓ | 2549.7 |
| 6000 | 2 | 20.06 | 99.75 | 12.84 | +0.2059 | 27.38 | 17.84 | ✓ | 2549.7 |
| 6500 | 3 | 22.42 | 99.88 | 12.50 | +0.1640 | 33.64 | 20.30 | ✓ | 2549.7 |
| 7000 | 3 | 24.56 | 100.00 | 12.27 | +0.1356 | 39.77 | 22.51 | ✓ | 2549.7 |
| 7500 | 3 | 26.54 | 100.11 | 12.11 | +0.1190 | 45.83 | 24.56 | ✓ | 2549.7 |
| 8000 | 3 | 28.33 | 100.21 | 11.94 | +0.0998 | 51.79 | 26.41 | ✓ | 2549.7 |
| 8500 | 4 | 29.93 | 100.29 | 11.68 | +0.0987 | 57.63 | 28.07 | ✓ | 2549.7 |
| 9000 | 4 | 31.50 | 100.38 | 11.56 | +0.0868 | 63.41 | 29.68 | ✓ | 2549.7 |
| 9500 | 4 | 32.95 | 100.46 | 11.38 | +0.0808 | 69.10 | 31.17 | ✓ | 2549.7 |
| 10000 | 4 | 34.31 | 100.54 | 11.21 | +0.0717 | 74.71 | 32.57 | ✓ | 2549.7 |
| 10500 | 5 | 35.69 | 100.62 | 10.99 | +0.0740 | 80.20 | 33.97 | ✓ | 2549.7 |
| 11000 | 5 | 36.85 | 100.68 | 10.74 | +0.0657 | 85.57 | 35.17 | ✓ | 2549.7 |
| 11500 | 5 | 37.99 | 100.75 | 10.50 | +0.0619 | 90.82 | 36.33 | ✓ | 2549.7 |
| 12000 | 5 | 39.08 | 100.81 | 10.35 | +0.0591 | 96.00 | 37.45 | ✓ | 2549.7 |
| 12500 | 6 | 40.09 | 100.87 | 10.08 | +0.0591 | 101.04 | 38.49 | ✓ | 2549.7 |
| 13000 | 6 | 41.01 | 100.92 | 9.95 | +0.0554 | 106.01 | 39.43 | ✓ | 2549.7 |
| 13500 | 6 | 41.93 | 100.98 | 9.67 | +0.0540 | 110.85 | 40.38 | ✓ | 2549.7 |
| 14000 | 6 | 42.86 | 101.04 | 9.39 | +0.0504 | 115.54 | 41.31 | ✓ | 2549.7 |
| 14500 | 7 | 43.68 | 101.08 | 9.17 | +0.0587 | 120.13 | 42.16 | ✓ | 2549.7 |
| 15000 | 7 | 44.42 | 101.13 | 8.93 | +0.0455 | 124.59 | 42.91 | ✓ | 2549.7 |
| 15500 | 7 | 45.13 | 101.18 | 8.63 | +0.0346 | 128.90 | 43.64 | ✓ | 2549.7 |
| 16000 | 7 | 45.80 | 101.22 | 8.38 | +0.0433 | 133.10 | 44.32 | ✓ | 2549.7 |
| 16500 | 8 | 46.44 | 101.25 | 8.11 | +0.0404 | 137.15 | 44.97 | ✓ | 2549.7 |
| 17000 | 8 | 47.07 | 101.30 | 7.86 | +0.0379 | 141.08 | 45.62 | ✓ | 2549.7 |
| 17500 | 8 | 47.67 | 101.34 | 7.59 | +0.0359 | 144.87 | 46.22 | ✓ | 2549.7 |
| 18000 | 8 | 48.21 | 101.38 | 7.28 | +0.0357 | 148.51 | 46.78 | ✓ | 2549.7 |
| 18500 | 9 | 48.68 | 101.40 | 6.96 | +0.0402 | 152.00 | 47.25 | ✓ | 2549.7 |
| 19000 | 9 | 49.16 | 101.44 | 6.96 | +0.0441 | 155.47 | 47.74 | ✓ | 2549.7 |
| 19500 | 9 | 49.59 | 101.47 | 6.40 | +0.0343 | 158.67 | 48.18 | ✓ | 2549.7 |
| 20000 | 9 | 50.02 | 101.50 | 6.15 | +0.0328 | 161.74 | 48.62 | ✓ | 2549.7 |
| 20500 | 10 | 50.42 | 101.52 | 5.83 | +0.0396 | 164.66 | 49.03 | ✓ | 2549.7 |
| 21000 | 10 | 50.80 | 101.55 | 5.56 | +0.0404 | 167.44 | 49.41 | ✓ | 2549.7 |
| 21500 | 10 | 51.13 | 101.58 | 5.27 | +0.0350 | 170.08 | 49.75 | ✓ | 2549.7 |
| 22000 | 10 | 51.44 | 101.60 | 4.99 | +0.0378 | 172.57 | 50.07 | ✓ | 2549.7 |


### `force_scalar_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 4784 | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 42054.7 |


### `force_scalar_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 4784 | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 42054.7 |


### `fp32cmp_avp_t4096_bs1_lr1e4`
> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 7, 'global_step': 19144, 'provenance': {'checkpoint': 'manifest:fp32cmp_avp_t4096_bs1_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 9572 | 3 | 318.89 | 106.71 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 19144 | 7 | 436.72 | 115.83 | 23.00 | --- | 220.20 | 220.20 | ✓ | 3814.2 |
| 35895 | 14 | 567.88 | 128.48 | 15.50 | +0.4542 | 479.83 | 409.67 | ✓ | 3814.2 |
| 52646 | 21 | 659.79 | 140.31 | 15.23 | +0.3674 | 734.86 | 538.08 | ✓ | 635.7 |
| 86148 | 35 | 887.45 | 203.99 | 15.88 | +0.3813 | 1267.02 | 817.84 | ✓ | 3814.2 |


### `fp32cmp_avp_t4096_bs1_lr1e4_repr`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 7, 'global_step': 19144, 'provenance': {'checkpoint': 'manifest:fp32cmp_avp_t4096_bs1_lr1e4_repr', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 9572 | 3 | 318.89 | 106.71 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 19144 | 7 | 436.72 | 115.83 | 23.00 | --- | 220.20 | 220.20 | ✓ | 3814.2 |
| 35895 | 14 | 567.88 | 128.48 | 15.50 | +0.4542 | 479.83 | 409.67 | ✓ | 3814.2 |
| 52646 | 21 | 659.79 | 140.31 | 15.23 | +0.3674 | 734.86 | 538.08 | ✓ | 635.7 |
| 86148 | 35 | 887.45 | 203.99 | 15.88 | +0.3813 | 1267.02 | 817.84 | ✓ | 3814.2 |


### `fp32cmp_avp_t4096_bs4_lr1e4`
> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 7, 'global_step': 4784, 'provenance': {'checkpoint': 'manifest:fp32cmp_avp_t4096_bs4_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2392 | 3 | 173.16 | 100.96 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 4784 | 7 | 246.76 | 105.03 | 51.20 | --- | 122.47 | 122.47 | ✓ | 3814.2 |
| 8970 | 14 | 344.26 | 113.50 | 36.87 | +0.5770 | 276.81 | 246.24 | ✓ | 3814.2 |
| 14953 | 28 | 447.71 | 125.08 | 33.37 | +0.4502 | 476.47 | 371.76 | ✓ | 635.7 |
| 27511 | 49 | 658.83 | 165.24 | 31.68 | +0.3895 | 874.31 | 610.38 | ✓ | 3814.2 |


### `fp32cmp_avp_t4096_bs4_lr1e4_repr`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 7, 'global_step': 4784, 'provenance': {'checkpoint': 'manifest:fp32cmp_avp_t4096_bs4_lr1e4_repr', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2392 | 3 | 173.16 | 100.96 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 4784 | 7 | 246.76 | 105.03 | 51.20 | --- | 122.47 | 122.47 | ✓ | 3814.2 |
| 8970 | 14 | 344.26 | 113.50 | 36.87 | +0.5770 | 276.81 | 246.24 | ✓ | 3814.2 |
| 14953 | 28 | 447.71 | 125.08 | 33.37 | +0.4502 | 476.47 | 371.76 | ✓ | 635.7 |
| 27511 | 49 | 658.83 | 165.24 | 31.68 | +0.3895 | 874.31 | 610.38 | ✓ | 3814.2 |


### `fp32cmp_avp_t4096_bs4_lr5e5`
> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 5e-05, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 7, 'global_step': 4784, 'provenance': {'checkpoint': 'manifest:fp32cmp_avp_t4096_bs4_lr5e5', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2392 | 3 | 95.27 | 100.13 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 4784 | 7 | 138.71 | 102.11 | 28.33 | --- | 67.76 | 67.76 | ✓ | 3814.2 |
| 8970 | 14 | 200.98 | 107.11 | 21.24 | +0.6594 | 156.67 | 142.98 | ✓ | 3814.2 |


### `fp32cmp_avp_t4096_bs4_lr5e5_repr`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 5e-05, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 7, 'global_step': 4784, 'provenance': {'checkpoint': 'manifest:fp32cmp_avp_t4096_bs4_lr5e5_repr', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2392 | 3 | 95.27 | 100.13 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 4784 | 7 | 138.71 | 102.11 | 28.33 | --- | 67.76 | 67.76 | ✓ | 3814.2 |
| 8970 | 14 | 200.98 | 107.11 | 21.24 | +0.6594 | 156.67 | 142.98 | ✓ | 3814.2 |


### `fp32cmp_avp_t512_bs8_lr1e4`
> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 7, 'global_step': 2392, 'provenance': {'checkpoint': 'manifest:fp32cmp_avp_t512_bs8_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 598 | 1 | 88.00 | 99.05 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 2093 | 6 | 160.05 | 100.97 | 75.17 | --- | 112.38 | 112.38 | ✓ | 635.7 |
| 2392 | 7 | 170.88 | 101.40 | 75.41 | +0.5456 | 134.93 | 126.10 | ✓ | 3814.2 |
| 4485 | 14 | 239.37 | 105.90 | 51.07 | +0.6301 | 241.81 | 203.85 | ✓ | 3814.2 |


### `fp32cmp_avp_t512_bs8_lr1e4_repr`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 7, 'global_step': 2392, 'provenance': {'checkpoint': 'manifest:fp32cmp_avp_t512_bs8_lr1e4_repr', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2392 | 7 | 170.88 | 101.40 | --- | --- | 0.00 | 0.00 | ✓ | 3814.2 |
| 4485 | 14 | 239.37 | 105.90 | 51.07 | --- | 106.88 | 106.88 | ✓ | 3814.2 |


### `fp32cmp_goa_t4096_bs1_lr1e4`
> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 3, 'global_step': 21600, 'provenance': {'checkpoint': 'manifest:fp32cmp_goa_t4096_bs1_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 21600 | 3 | 418.96 | 107.82 | --- | --- | 0.00 | 0.00 | ✓ | 3814.2 |
| 37800 | 6 | 517.66 | 114.15 | 14.68 | --- | 237.86 | 237.86 | ✓ | 3814.2 |
| 81000 | 14 | 670.22 | 130.00 | 9.02 | +0.2457 | 627.65 | 504.06 | ✓ | 635.7 |
| 118800 | 21 | 840.21 | 187.86 | 12.61 | +0.2290 | 1104.36 | 742.69 | ✓ | 3814.2 |


### `fp32cmp_goa_t4096_bs1_lr1e4_repr`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 6, 'global_step': 37800, 'provenance': {'checkpoint': 'manifest:fp32cmp_goa_t4096_bs1_lr1e4_repr', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 21600 | 3 | 418.96 | 107.82 | --- | --- | 0.00 | 0.00 | ✓ | 3814.2 |
| 37800 | 6 | 517.66 | 114.15 | 14.68 | --- | 237.86 | 237.86 | ✓ | 3814.2 |
| 81000 | 14 | 670.22 | 130.00 | 9.02 | +0.2457 | 627.65 | 504.06 | ✓ | 635.7 |
| 118800 | 21 | 840.21 | 187.86 | 12.61 | +0.2290 | 1104.36 | 742.69 | ✓ | 3814.2 |


### `fp32cmp_goa_t4096_bs4_lr1e4`
> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 4, 'global_step': 6750, 'provenance': {'checkpoint': 'manifest:fp32cmp_goa_t4096_bs4_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | 3 | 236.26 | 100.82 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 10800 | 7 | 325.26 | 104.58 | 30.54 | --- | 164.94 | 164.94 | ✓ | 3814.2 |
| 24300 | 17 | 480.72 | 117.62 | 20.21 | +0.3693 | 437.82 | 367.31 | ✓ | 635.7 |
| 37800 | 27 | 619.11 | 141.26 | 23.02 | +0.3232 | 748.58 | 537.63 | ✓ | 3814.2 |


### `fp32cmp_goa_t4096_bs4_lr1e4_repr`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 7, 'global_step': 10800, 'provenance': {'checkpoint': 'manifest:fp32cmp_goa_t4096_bs4_lr1e4_repr', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | 3 | 236.26 | 100.82 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 10800 | 7 | 325.26 | 104.58 | 30.54 | --- | 164.94 | 164.94 | ✓ | 3814.2 |
| 24300 | 17 | 480.72 | 117.62 | 20.21 | +0.3693 | 437.82 | 367.31 | ✓ | 635.7 |
| 37800 | 27 | 619.11 | 141.26 | 23.02 | +0.3232 | 748.58 | 537.63 | ✓ | 3814.2 |


### `fp32cmp_goa_t4096_bs4_lr5e5`
> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 5e-05, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 4, 'global_step': 6750, 'provenance': {'checkpoint': 'manifest:fp32cmp_goa_t4096_bs4_lr5e5', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 6750 | 4 | 144.99 | 99.60 | --- | --- | 0.00 | 0.00 | ✓ | 3814.2 |
| 10800 | 7 | 183.30 | 100.53 | 16.87 | --- | 68.33 | 68.33 | ✓ | 635.7 |
| 20250 | 14 | 259.64 | 105.38 | 12.57 | +0.5431 | 187.08 | 166.08 | ✓ | 3814.2 |


### `fp32cmp_goa_t512_bs8_lr1e4`
> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 7, 'global_step': 5400, 'provenance': {'checkpoint': 'manifest:fp32cmp_goa_t512_bs8_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2700 | 3 | 170.66 | 99.72 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 5400 | 7 | 234.55 | 101.44 | 43.84 | --- | 118.36 | 118.36 | ✓ | 3814.2 |
| 10125 | 14 | 323.02 | 106.95 | 31.23 | +0.5293 | 265.91 | 232.95 | ✓ | 3814.2 |


### `fp32frames_avp_t1024_bs1_lr1e4`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 9, 'global_step': 23930, 'provenance': {'checkpoint': 'manifest:fp32frames_avp_t1024_bs1_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 9572 | 3 | 310.01 | 105.63 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 23930 | 9 | 457.54 | 115.36 | 19.40 | --- | 278.50 | 278.50 | ✓ | 3814.2 |


### `fp32frames_avp_t1024_bs4_lr1e4`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 9, 'global_step': 5980, 'provenance': {'checkpoint': 'manifest:fp32frames_avp_t1024_bs4_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2392 | 3 | 167.87 | 100.42 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 5980 | 9 | 261.73 | 104.81 | 43.60 | --- | 156.45 | 156.45 | ✓ | 3814.2 |


### `fp32frames_avp_t2048_bs1_lr1e4`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 9, 'global_step': 23930, 'provenance': {'checkpoint': 'manifest:fp32frames_avp_t2048_bs1_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 9572 | 3 | 314.23 | 106.07 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 23930 | 9 | 468.90 | 117.45 | 19.78 | --- | 284.00 | 284.00 | ✓ | 3814.2 |


### `fp32frames_avp_t2048_bs4_lr1e4`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 9, 'global_step': 5980, 'provenance': {'checkpoint': 'manifest:fp32frames_avp_t2048_bs4_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2392 | 3 | 169.99 | 100.61 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 5980 | 9 | 268.50 | 105.80 | 44.61 | --- | 160.06 | 160.06 | ✓ | 3814.2 |


### `fp32frames_avp_t4096_bs1_lr1e4`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 9, 'global_step': 23930, 'provenance': {'checkpoint': 'manifest:fp32frames_avp_t4096_bs1_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 9572 | 3 | 319.03 | 106.67 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 23930 | 9 | 480.60 | 119.62 | 20.15 | --- | 289.36 | 289.36 | ✓ | 3814.2 |


### `fp32frames_avp_t4096_bs4_lr1e4`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 9, 'global_step': 5980, 'provenance': {'checkpoint': 'manifest:fp32frames_avp_t4096_bs4_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2392 | 3 | 173.21 | 100.95 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 5980 | 9 | 276.07 | 107.02 | 45.56 | --- | 163.46 | 163.46 | ✓ | 3814.2 |


### `fp32frames_avp_t512_bs1_lr1e4`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 9, 'global_step': 23930, 'provenance': {'checkpoint': 'manifest:fp32frames_avp_t512_bs1_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 9572 | 3 | 309.05 | 105.72 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 23930 | 9 | 453.17 | 114.79 | 19.26 | --- | 276.54 | 276.54 | ✓ | 3814.2 |


### `fp32frames_avp_t512_bs4_lr1e4`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 9, 'global_step': 5980, 'provenance': {'checkpoint': 'manifest:fp32frames_avp_t512_bs4_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2392 | 3 | 168.06 | 100.59 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 5980 | 9 | 259.43 | 104.65 | 43.12 | --- | 154.73 | 154.73 | ✓ | 3814.2 |


### `fp32frames_goa_t1024_bs1_lr1e4`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 9, 'global_step': 54000, 'provenance': {'checkpoint': 'manifest:fp32frames_goa_t1024_bs1_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 54000 | 9 | 579.80 | 119.53 | --- | --- | 0.00 | 0.00 | ✓ | 3814.2 |


### `fp32frames_goa_t1024_bs4_lr1e4`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 9, 'global_step': 13500, 'provenance': {'checkpoint': 'manifest:fp32frames_goa_t1024_bs4_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | 3 | 233.04 | 100.77 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 13500 | 9 | 350.60 | 105.54 | 26.50 | --- | 214.61 | 214.61 | ✓ | 3814.2 |


### `fp32frames_goa_t2048_bs1_lr1e4`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 9, 'global_step': 54000, 'provenance': {'checkpoint': 'manifest:fp32frames_goa_t2048_bs1_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 21600 | 3 | 422.16 | 108.60 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 54000 | 9 | 582.39 | 119.25 | 11.47 | --- | 371.51 | 371.51 | ✓ | 3814.2 |


### `fp32frames_goa_t2048_bs4_lr1e4`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 9, 'global_step': 13500, 'provenance': {'checkpoint': 'manifest:fp32frames_goa_t2048_bs4_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | 3 | 236.46 | 100.75 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 13500 | 9 | 356.09 | 105.85 | 26.68 | --- | 216.11 | 216.11 | ✓ | 3814.2 |


### `fp32frames_goa_t4096_bs1_lr1e4`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 6, 'global_step': 37800, 'provenance': {'checkpoint': 'manifest:fp32frames_goa_t4096_bs1_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 21600 | 3 | 422.53 | 108.27 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 37800 | 6 | 521.64 | 114.76 | 14.77 | --- | 239.29 | 239.29 | ✓ | 3814.2 |


### `fp32frames_goa_t4096_bs4_lr1e4`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 8, 'global_step': 12150, 'provenance': {'checkpoint': 'manifest:fp32frames_goa_t4096_bs4_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | 3 | 236.31 | 100.83 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 12150 | 8 | 342.84 | 105.50 | 28.50 | --- | 192.34 | 192.34 | ✓ | 3814.2 |


### `fp32frames_goa_t512_bs1_lr1e4`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 9, 'global_step': 54000, 'provenance': {'checkpoint': 'manifest:fp32frames_goa_t512_bs1_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 21600 | 3 | 423.57 | 109.33 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 54000 | 9 | 579.79 | 120.10 | 21.55 | --- | 698.21 | 698.21 | ✓ | 3814.2 |


### `fp32frames_goa_t512_bs4_lr1e4`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'PRUNED (slim .weights.ckpt — no optimizer_states)', 'epoch': 9, 'global_step': 13500, 'provenance': {'checkpoint': 'manifest:fp32frames_goa_t512_bs4_lr1e4', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True, 'optimizer_note': 'PRUNED (slim .weights.ckpt — no optimizer_states)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | 3 | 233.55 | 101.10 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 9450 | 6 | 299.53 | 103.52 | 32.64 | --- | 132.18 | 132.18 | ✓ | 635.7 |
| 13500 | 9 | 349.40 | 105.82 | 27.36 | +0.5448 | 242.97 | 213.78 | ✓ | 3814.2 |


### `fullft_3src_t512_fp32_hyperball_lr1e-4`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 20 | 0 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 30976.9 |


### `fullft_avp_t1024`
> **Recipe:** {'kind': 'non-lora (control/latch/other)', 'epoch': 7, 'global_step': 4784, 'state_dict_tensors': 997, 'provenance': {'checkpoint': 'manifest:fullft_avp_t1024', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True}, 'training': {'method': 'whole-DiT full fine-tune (all 1.4B params, NOT a low-rank adapter)', 'base_model': 'SA3 medium-base', 'precision': 'bf16', 'optimizer': 'FusionOpt, lr 1e-4', 'epochs': '8 (epoch=7 final, 0-indexed; only the final synced to local eval storage)', 'context_len': 'T=1024 latent frames', 'corpus': 'avp', '_source': 'manifest reason (LUMI campaign metadata); checkpoint is a full state_dict with no lora_config, so these training params come from the recorded campaign, not the ckpt'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2990 | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 4397.8 |
| 4784 | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 32115.2 |


### `fullft_avp_t1024_bf16_lr25e6_sub12v3sel_wsd10_bs8_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 12000 | 39 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 4397.8 |
| 19200 | 63 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 9941.7 |


### `fullft_avp_t2048`
> **Recipe:** {'kind': 'non-lora (control/latch/other)', 'epoch': 7, 'global_step': 4784, 'state_dict_tensors': 997, 'provenance': {'checkpoint': 'manifest:fullft_avp_t2048', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True}, 'training': {'method': 'whole-DiT full fine-tune (all 1.4B params, NOT a low-rank adapter)', 'base_model': 'SA3 medium-base', 'precision': 'bf16', 'optimizer': 'FusionOpt, lr 1e-4', 'epochs': '8 (epoch=7 final, 0-indexed; only the final synced to local eval storage)', 'context_len': 'T=2048 latent frames', 'corpus': 'avp', '_source': 'manifest reason (LUMI campaign metadata); checkpoint is a full state_dict with no lora_config, so these training params come from the recorded campaign, not the ckpt'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2990 | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 4397.8 |
| 4784 | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 32115.2 |


### `fullft_avp_t256`
> **Recipe:** {'kind': 'non-lora (control/latch/other)', 'epoch': 7, 'global_step': 4784, 'state_dict_tensors': 997, 'provenance': {'checkpoint': 'manifest:fullft_avp_t256', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True}, 'training': {'method': 'whole-DiT full fine-tune (all 1.4B params, NOT a low-rank adapter)', 'base_model': 'SA3 medium-base', 'precision': 'bf16', 'optimizer': 'FusionOpt, lr 1e-4', 'epochs': '8 (epoch=7 final, 0-indexed; only the final synced to local eval storage)', 'context_len': 'T=256 latent frames', 'corpus': 'avp', '_source': 'manifest reason (LUMI campaign metadata); checkpoint is a full state_dict with no lora_config, so these training params come from the recorded campaign, not the ckpt'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 4784 | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 32115.2 |
| 46944 | 80 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 7169.8 |
| 90598 | 153 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 21028.8 |


### `fullft_avp_t4096`
> **Recipe:** {'kind': 'non-lora (control/latch/other)', 'epoch': 7, 'global_step': 4784, 'state_dict_tensors': 997, 'provenance': {'checkpoint': 'manifest:fullft_avp_t4096', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True}, 'training': {'method': 'whole-DiT full fine-tune (all 1.4B params, NOT a low-rank adapter)', 'base_model': 'SA3 medium-base', 'precision': 'bf16', 'optimizer': 'FusionOpt, lr 1e-4', 'epochs': '8 (epoch=7 final, 0-indexed; only the final synced to local eval storage)', 'context_len': 'T=4096 latent frames', 'corpus': 'avp', '_source': 'manifest reason (LUMI campaign metadata); checkpoint is a full state_dict with no lora_config, so these training params come from the recorded campaign, not the ckpt'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2990 | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 4397.8 |
| 4784 | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 32115.2 |


### `fullft_avp_t512`
> **Recipe:** {'kind': 'non-lora (control/latch/other)', 'epoch': 7, 'global_step': 4784, 'state_dict_tensors': 997, 'provenance': {'checkpoint': 'manifest:fullft_avp_t512', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True}, 'training': {'method': 'whole-DiT full fine-tune (all 1.4B params, NOT a low-rank adapter)', 'base_model': 'SA3 medium-base', 'precision': 'bf16', 'optimizer': 'FusionOpt, lr 1e-4', 'epochs': '8 (epoch=7 final, 0-indexed; only the final synced to local eval storage)', 'context_len': 'T=512 latent frames', 'corpus': 'avp', '_source': 'manifest reason (LUMI campaign metadata); checkpoint is a full state_dict with no lora_config, so these training params come from the recorded campaign, not the ckpt'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2990 | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 4397.8 |
| 4784 | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 32115.2 |


### `fullft_avpaug_t1024_fp32_lr1e-4_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 3588 | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 14338.9 |
| 5980 | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 25426.1 |


### `fullft_biggoa_t1024_fp32_lr1e-4_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 3132 | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 25426.1 |


### `fullft_bigset`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 25040 | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 42056.2 |


### `fullft_goa_t1024`
> **Recipe:** {'kind': 'non-lora (control/latch/other)', 'epoch': 7, 'global_step': 10800, 'state_dict_tensors': 997, 'provenance': {'checkpoint': 'manifest:fullft_goa_t1024', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True}, 'training': {'method': 'whole-DiT full fine-tune (all 1.4B params, NOT a low-rank adapter)', 'base_model': 'SA3 medium-base', 'precision': 'bf16', 'optimizer': 'FusionOpt, lr 1e-4', 'epochs': '8 (epoch=7 final, 0-indexed; only the final synced to local eval storage)', 'context_len': 'T=1024 latent frames', 'corpus': 'goa', '_source': 'manifest reason (LUMI campaign metadata); checkpoint is a full state_dict with no lora_config, so these training params come from the recorded campaign, not the ckpt'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 6750 | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 4397.8 |
| 10800 | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 32115.2 |


### `fullft_goa_t2048`
> **Recipe:** {'kind': 'non-lora (control/latch/other)', 'epoch': 7, 'global_step': 10800, 'state_dict_tensors': 997, 'provenance': {'checkpoint': 'manifest:fullft_goa_t2048', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True}, 'training': {'method': 'whole-DiT full fine-tune (all 1.4B params, NOT a low-rank adapter)', 'base_model': 'SA3 medium-base', 'precision': 'bf16', 'optimizer': 'FusionOpt, lr 1e-4', 'epochs': '8 (epoch=7 final, 0-indexed; only the final synced to local eval storage)', 'context_len': 'T=2048 latent frames', 'corpus': 'goa', '_source': 'manifest reason (LUMI campaign metadata); checkpoint is a full state_dict with no lora_config, so these training params come from the recorded campaign, not the ckpt'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 6750 | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 4397.8 |
| 10800 | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 32115.2 |


### `fullft_goa_t256`
> **Recipe:** {'kind': 'non-lora (control/latch/other)', 'epoch': 7, 'global_step': 10800, 'state_dict_tensors': 997, 'provenance': {'checkpoint': 'manifest:fullft_goa_t256', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True}, 'training': {'method': 'whole-DiT full fine-tune (all 1.4B params, NOT a low-rank adapter)', 'base_model': 'SA3 medium-base', 'precision': 'bf16', 'optimizer': 'FusionOpt, lr 1e-4', 'epochs': '8 (epoch=7 final, 0-indexed; only the final synced to local eval storage)', 'context_len': 'T=256 latent frames', 'corpus': 'goa', '_source': 'manifest reason (LUMI campaign metadata); checkpoint is a full state_dict with no lora_config, so these training params come from the recorded campaign, not the ckpt'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 10800 | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 32115.2 |
| 52650 | 38 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 7169.8 |
| 94500 | 69 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 21028.8 |


### `fullft_goa_t4096`
> **Recipe:** {'kind': 'non-lora (control/latch/other)', 'epoch': 7, 'global_step': 10800, 'state_dict_tensors': 997, 'provenance': {'checkpoint': 'manifest:fullft_goa_t4096', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True}, 'training': {'method': 'whole-DiT full fine-tune (all 1.4B params, NOT a low-rank adapter)', 'base_model': 'SA3 medium-base', 'precision': 'bf16', 'optimizer': 'FusionOpt, lr 1e-4', 'epochs': '8 (epoch=7 final, 0-indexed; only the final synced to local eval storage)', 'context_len': 'T=4096 latent frames', 'corpus': 'goa', '_source': 'manifest reason (LUMI campaign metadata); checkpoint is a full state_dict with no lora_config, so these training params come from the recorded campaign, not the ckpt'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 6750 | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 4397.8 |
| 10800 | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 32115.2 |


### `fullft_goa_t512`
> **Recipe:** {'kind': 'non-lora (control/latch/other)', 'epoch': 7, 'global_step': 10800, 'state_dict_tensors': 997, 'provenance': {'checkpoint': 'manifest:fullft_goa_t512', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': True}, 'training': {'method': 'whole-DiT full fine-tune (all 1.4B params, NOT a low-rank adapter)', 'base_model': 'SA3 medium-base', 'precision': 'bf16', 'optimizer': 'FusionOpt, lr 1e-4', 'epochs': '8 (epoch=7 final, 0-indexed; only the final synced to local eval storage)', 'context_len': 'T=512 latent frames', 'corpus': 'goa', '_source': 'manifest reason (LUMI campaign metadata); checkpoint is a full state_dict with no lora_config, so these training params come from the recorded campaign, not the ckpt'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 6750 | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 4397.8 |
| 10800 | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 32115.2 |


### `fullft_ladder_A_control`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1500 | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 9956.4 |
| 3000 | 39 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 9956.4 |


### `fullft_ladder_B_autoscale`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1500 | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 10649.6 |
| 3000 | 39 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 10649.6 |


### `fullft_ladder_C_dual`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1500 | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 10649.6 |
| 3000 | 39 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 10649.6 |


### `fullft_mix3_t1024_fp32_lr1e-4_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 3036 | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 14338.9 |
| 5060 | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 25426.1 |


### `fullft_mixed_avp_latents_sa3_t4096`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 3896 | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 34887.1 |


### `fullft_mixed_avp_latents_sa3_t4096_wd03`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1220 | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 7169.8 |
| 1952 | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 34887.1 |


### `fullft_mixed_avp_latents_sa3_t4096_wdfix`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 9740 | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 7169.8 |
| 15584 | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 34887.1 |


### `fullft_suomi_t1024_fp32_lr1e-4_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1896 | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 14338.9 |
| 3160 | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 25426.1 |


### `fullft_wd_ab_wd0`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2700 | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 42056.2 |


### `fusion_autoscale_lr1e-4`
> **Verdict / Note:** FusionOpt + autoscale at lr 1e-4 -- UNSTABLE. path_length 2223 / net 1854, ~7x the 5e-6 arm. Kim: 'pretty granular and distorted'. Do not use; kept as the upper bound of the LR bracket.

> **Recipe:** fusion + autoscale · lr 1e-4 · rank 128 · bs 8 · T512 · bf16 · warmup 200 · clip 1.0 · seed 42 · 3000 steps

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | 27 | 1506.31 | 275.56 | --- | --- | 0.00 | 0.00 | ✓ | 3894.0 |
| 2000 | 54 | 2137.59 | 411.49 | 1221.64 | --- | 1221.64 | 1221.64 | ✓ | 3894.0 |
| 3000 | 81 | 2492.20 | 490.10 | 963.94 | +0.3807 | 2185.58 | 1821.60 | ✓ | 3894.0 |


### `fusion_autoscale_lr1e-6_full`
> **Verdict / Note:** FusionOpt + autoscale at a deliberately LOW lr 1e-6, testing whether autoscale grows the step itself. It does: step_cos 0.591, path_eff 0.893 -- the same trajectory shape as 5e-6 at half the displacement. Kim: 'also good but not quite, maybe learned some things [less]'. Audiobox CE 6.64.

> **Recipe:** fusion + autoscale · lr 1e-6 · rank 128 · bs 8 · T512 · bf16 · warmup 200 · clip 1.0 · seed 42 · 3000 steps

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | 27 | 71.51 | 100.04 | --- | --- | 0.00 | 0.00 | ✓ | 3894.0 |
| 2000 | 54 | 133.06 | 101.90 | 83.16 | --- | 83.16 | 83.16 | ✓ | 3894.0 |
| 3000 | 81 | 177.20 | 103.86 | 68.97 | +0.5904 | 152.13 | 135.81 | ✓ | 3894.0 |


### `fusion_autoscale_lr5e-6_full3h`
> **Verdict / Note:** THE PICK. Kim 2026-09-02: 'the clips sound excellent, and seem to have learned the dataset style very well ... in your face and forest-punk ... slightly saturated like tape'. step_cos 0.539, path_eff 0.879, net 283.0; highest onset density of all arms (8.09/s). Clip ladder rendered at steps 1000/2000/3000. Kim also notes it 'starts to sound similar-ish to the from-scratch s5000 AdamW'.

> **Recipe:** fusion + autoscale · lr 5e-6 · rank 128 · bs 8 · T512 · bf16 · warmup 200 · clip 1.0 · seed 42 · 3000 steps

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | 27 | 202.83 | 102.64 | --- | --- | 0.00 | 0.00 | ✓ | 3894.0 |
| 2000 | 54 | 313.70 | 108.91 | 175.00 | --- | 175.00 | 175.00 | ✓ | 3894.0 |
| 3000 | 81 | 391.02 | 114.70 | 141.96 | +0.5392 | 316.96 | 278.51 | ✓ | 3894.0 |


### `fusion_autoscale_lr5e6_bs2`
> **Verdict / Note:** QUARTER-BATCH test of the 5e-6 arm, sample-matched (12000 bs2 steps = 3000 bs8 steps). lr held at 5e-6 rather than sqrt-scaled to 2.5e-6, deliberately, to test whether autoscale is batch-size robust. IT IS NOT: path_length 590.1 vs 322.1 and net 504.1 vs 283.0 -- ~1.8x further in weight space for the same samples seen, path_eff 0.854, step_cos 0.453. Direction-convergence survives but weakens. Clean by DSP (hf 0.177, no disintegration); Audiobox CE 6.79. Follow-up if over-trained: rerun at 2.5e-6.

> **Recipe:** fusion + autoscale · lr 5e-6 · rank 128 · bs 2 · T512 · bf16 · warmup 800 · clip 1.0 · seed 42 · 12000 steps · ckpt every 4000 (steps 4000/8000/12000 are sample-equivalent to the bs8 arm's 1000/2000/3000)

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 4000 | 26 | 393.91 | 114.30 | --- | --- | 0.00 | 0.00 | ✓ | 3894.0 |
| 8000 | 53 | 577.42 | 131.19 | 80.81 | --- | 323.22 | 323.22 | ✓ | 3894.0 |
| 12000 | 79 | 691.41 | 143.01 | 64.36 | +0.4534 | 580.67 | 496.19 | ✓ | 3894.0 |


### `fusion_autoscale_lr5e6_control2`
> **Verdict / Note:** ATTRIBUTION CONTROL: is the autoscale direction-convergence a property of the optimizer or of the small training set? ANSWER: the optimizer. Different seed (9001) + disjoint 300-track subset reproduced step_cos to 0.5448 vs 0.5390 (delta 0.006) and path_eff 0.880 vs 0.879. BUT the SOUND changed: Kim 'sounds weak, the beat is not steady, like it was trained on more chill stuff, not as engaging'. => weight-space signature is optimizer-driven, timbre is data-driven. Confounded on seed+data+init; a same-data/different-seed arm would separate them. Audiobox rates it HIGHEST (CE 6.92) and is therefore not tracking Kim's judgment on this question.

> **Recipe:** fusion + autoscale · lr 5e-6 · rank 128 · bs 8 · T512 · bf16 · warmup 200 · clip 1.0 · seed 9001 · 3000 steps · disjoint 300-track subset (selection_seed 777, prior track ids excluded, artist overlap allowed)

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | 27 | 183.96 | 101.88 | --- | --- | 0.00 | 0.00 | ✓ | 3894.0 |
| 2000 | 54 | 284.65 | 107.18 | 157.80 | --- | 157.80 | 157.80 | ✓ | 3894.0 |
| 3000 | 81 | 355.62 | 112.11 | 128.83 | +0.5449 | 286.63 | 252.30 | ✓ | 3894.0 |


### `fusion_nm`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 20 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 3227.9 |
| 40 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 3227.9 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 3227.9 |


### `head_a_ceiling_act`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 0.2 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 9.1 |


### `headb_base_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.7 |
| 2000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.7 |
| 3000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.7 |
| 4000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.7 |
| 5000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.7 |
| 6000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.7 |
| 7000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.7 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.7 |


### `headb_ft_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.7 |
| 2000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.7 |
| 3000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.7 |
| 4000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.7 |
| 5000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.7 |
| 6000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.7 |
| 7000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.7 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.7 |


### `headb_melody`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 660 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2769.8 |
| 1320 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2769.8 |
| 1980 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2769.8 |
| 2640 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2769.8 |
| 3300 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2769.8 |
| 3960 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2769.8 |
| 4620 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2769.8 |
| 5280 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2769.8 |
| 5940 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2769.8 |
| 6600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2769.8 |
| 7260 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2769.8 |
| 7920 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2769.8 |
| 8580 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2769.8 |
| 9240 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2769.8 |
| 9900 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2769.8 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2769.8 |


### `heads_ema20`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `heads_ema40`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 40 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `highdrop`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 20 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2363.9 |
| 40 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2363.9 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2363.9 |


### `hpcp_attr`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 20 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2431.7 |
| 40 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2431.7 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2431.7 |


### `hpcp_ema20`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 2 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 3 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 6 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 8 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 10 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 13 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 14 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 16 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 17 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 18 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `hpcp_ema40`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 2 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 3 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 6 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 8 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 10 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 13 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 14 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 16 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 17 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 18 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 21 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 22 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 23 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 24 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 25 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 26 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 27 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 28 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 29 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 30 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 31 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 32 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 33 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 34 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 35 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 36 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 37 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 38 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 39 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 40 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `i8nygj4y`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1350 | 0 | 25.51 | 71.96 | --- | --- | 0.00 | 0.00 | ✓ | 319.6 |
| 2700 | 1 | 35.61 | 73.49 | 17.15 | --- | 23.15 | 23.15 | ✓ | 319.6 |
| 4050 | 2 | 43.35 | 74.96 | 16.97 | +0.0240 | 46.06 | 32.96 | ✓ | 319.6 |
| 5400 | 3 | 49.85 | 76.37 | 17.01 | +0.0029 | 69.02 | 40.55 | ✓ | 319.6 |
| 6750 | 4 | 55.75 | 77.84 | 17.05 | -0.0064 | 92.04 | 47.19 | ✓ | 319.6 |
| 8100 | 5 | 61.04 | 79.23 | 17.09 | -0.0103 | 115.12 | 53.04 | ✓ | 319.6 |
| 9450 | 6 | 65.84 | 80.53 | 17.11 | -0.0188 | 138.22 | 58.28 | ✓ | 319.6 |
| 10800 | 7 | 70.39 | 81.93 | 16.99 | -0.0219 | 161.16 | 63.20 | ✓ | 959.0 |


### `latch_f0_bass_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 2 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 3 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 6 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 8 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 10 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 13 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 14 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 16 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 17 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 18 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 21 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 22 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 23 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 24 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 25 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 26 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 27 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 28 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 29 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 30 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `latch_f0_other_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 2 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 3 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 6 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 8 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 10 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 13 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 14 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 16 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 17 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 18 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 21 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 22 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 23 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 24 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 25 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 26 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 27 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 28 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 29 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 30 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `latch_hpcp_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 2 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 3 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 6 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 8 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 10 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 13 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 14 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 16 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 17 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 18 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 21 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 22 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 23 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 24 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 25 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 26 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 27 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 28 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 29 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 30 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `latch_onset_envelope_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 2 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 3 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 6 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 8 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 10 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 13 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 14 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 16 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 17 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 18 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 21 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 22 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 23 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 24 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 25 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 26 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 27 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 28 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 29 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 30 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `latch_rms_energy_bass_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 2 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 3 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 6 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 8 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 10 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 13 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 14 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 16 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 17 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 18 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 21 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 22 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 23 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 24 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 25 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 26 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 27 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 28 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 29 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 30 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `latch_spectral_flatness_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 2 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 3 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 6 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 8 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 10 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 13 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 14 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 16 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 17 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 18 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 21 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 22 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 23 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 24 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 25 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 26 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 27 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 28 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 29 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 30 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `lion_lr1e-5`
> **Verdict / Note:** Trajectory (checkpoint-stats/lion_lr1e-5_trajectory.md, computed over steps 1000-4000 only -- 2 later ckpts exist): path efficiency 0.664 = wandering within a basin, so soup-averaging should help; centroid at step 2000. ⚠ T=512 here is what makes the d48 native cell render; it is asserted from the campaign recipe, not read off the checkpoint.

> **Recipe:** LoRA r128, T=512, bf16, lr 1e-5, optimizer Lion; 300-item constrained goa/psytrance subset of latents_sa3, seed42 -- same training recipe as the AdamW/Fusion arms of this campaign per its standard_clips run_meta.

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | 66 | 29.27 | 101.92 | --- | --- | 0.00 | 0.00 | ✓ | 953.6 |
| 2000 | 133 | 42.78 | 105.38 | 25.92 | --- | 25.92 | 25.92 | ✓ | 953.6 |
| 3000 | 199 | 53.98 | 108.80 | 26.03 | +0.1798 | 51.95 | 39.90 | ✓ | 953.6 |
| 4000 | 266 | 62.83 | 112.06 | 23.95 | +0.1371 | 75.90 | 50.02 | ✓ | 953.6 |
| 5000 | 333 | 70.67 | 115.17 | 23.76 | +0.1213 | 99.66 | 58.79 | ✓ | 953.6 |
| 6000 | 399 | 77.61 | 118.20 | 23.23 | +0.0880 | 122.89 | 66.42 | ✓ | 953.6 |


### `lion_lr5e-5-batch32`
> **Recipe:** DoRA-rows r128, alpha 128, T=512, lr 5e-5, optimizer Lion, batch 32, 6000 steps; 300-item constrained goa/psytrance subset of latents_sa3. No EMA in the checkpoint (LoRA runs force-disable it), so renders load the online weights.

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | 111 | 122.65 | 122.13 | --- | --- | 0.00 | 0.00 | ✓ | 953.6 |
| 2000 | 222 | 178.43 | 146.28 | 118.85 | --- | 118.85 | 118.85 | ✓ | 953.6 |
| 3000 | 333 | 218.35 | 165.25 | 114.90 | +0.0662 | 233.75 | 170.69 | ✓ | 953.6 |
| 4000 | 444 | 251.92 | 182.48 | 115.81 | +0.0463 | 349.56 | 210.96 | ✓ | 953.6 |
| 5000 | 555 | 280.64 | 197.27 | 113.57 | +0.0425 | 463.12 | 244.18 | ✓ | 953.6 |
| 6000 | 666 | 305.62 | 210.26 | 113.01 | +0.0257 | 576.13 | 272.45 | ✓ | 953.6 |


### `longctx_t1024_r128`
> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 7, 'global_step': 2696, 'provenance': {'checkpoint': 'manifest:longctx_t1024_r128', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1685 | 4 | 137.90 | 99.23 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 2696 | 7 | 174.40 | 100.27 | 65.57 | --- | 66.29 | 66.29 | ✓ | 3814.2 |


### `longctx_t2048_r128`
> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 7, 'global_step': 5400, 'provenance': {'checkpoint': 'manifest:longctx_t2048_r128', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2700 | 3 | 173.42 | 99.63 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 5400 | 7 | 243.31 | 102.17 | 45.42 | --- | 122.64 | 122.64 | ✓ | 3814.2 |


### `lr5e5mix_r128a128_t512_bf16_bs8_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 43152 | 15 | 99.20 | 115.18 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `lr5e5mixwarm_r128a128_t512_bf16_bs8_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 43152 | 15 | 112.87 | 119.53 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `lr5e5mixwarmwsd_r128a128_t512_bf16_bs8_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 43152 | 15 | 102.23 | 116.40 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `lr5e5mixwsd_r128a128_t512_bf16_bs8_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 43152 | 15 | 86.44 | 112.16 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `lreq_goa_lr1e4`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | 3 | 66.15 | 105.59 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |
| 27000 | 19 | 146.33 | 129.62 | 6.80 | --- | 146.91 | 146.91 | ✓ | 1907.2 |


### `lreq_goa_lr2e4`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 8100 | 5 | 123.23 | 120.42 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |
| 18900 | 13 | 221.48 | 159.84 | 22.12 | --- | 238.89 | 238.89 | ✓ | 1907.2 |


### `lreq_goa_lr5e5`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | 3 | 35.56 | 101.47 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |
| 54000 | 39 | 115.56 | 122.09 | 2.30 | --- | 112.00 | 112.00 | ✓ | 1907.2 |


### `melodychroma_r32_hpcp`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2700 | 0 | 26.22 | 52.80 | --- | --- | 0.00 | 0.00 | ✓ | 702.9 |
| 5400 | 1 | 36.80 | 55.46 | 8.44 | --- | 22.79 | 22.79 | ✓ | 702.9 |
| 8100 | 2 | 45.15 | 58.14 | 8.22 | +0.0806 | 44.98 | 33.06 | ✓ | 702.9 |
| 10800 | 3 | 52.02 | 60.53 | 8.08 | +0.0453 | 66.78 | 41.08 | ✓ | 702.9 |
| 13500 | 4 | 58.04 | 62.79 | 8.01 | +0.0206 | 88.39 | 47.91 | ✓ | 702.9 |
| 16200 | 5 | 63.50 | 65.02 | 7.98 | +0.0069 | 109.93 | 53.99 | ✓ | 702.9 |


### `modular_opt_cubic5_sf_ev_20ep_13500s_2026-09-21_0148`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 100 | 0 | 0.46 | 98.84 | --- | --- | 0.00 | 0.00 | ✓ | 3181.6 |
| 675 | 0 | 5.94 | 99.02 | 10.05 | --- | 5.78 | 5.78 | ✓ | 3181.6 |
| 1350 | 1 | 10.14 | 99.15 | 8.25 | +0.5597 | 11.34 | 10.02 | ✓ | 3181.6 |
| 2025 | 2 | 13.29 | 99.25 | 6.65 | +0.6971 | 15.84 | 13.18 | ✓ | 3181.6 |
| 2700 | 3 | 15.90 | 99.34 | 5.78 | +0.7622 | 19.74 | 15.80 | ✓ | 3181.6 |
| 3375 | 4 | 18.17 | 99.41 | 5.19 | +0.7870 | 23.24 | 18.07 | ✓ | 3181.6 |
| 4050 | 5 | 20.39 | 99.49 | 4.83 | +0.8106 | 26.51 | 20.30 | ✓ | 3181.6 |
| 4725 | 6 | 22.54 | 99.57 | 4.62 | +0.8272 | 29.62 | 22.46 | ✓ | 3181.6 |
| 5400 | 7 | 24.60 | 99.64 | 4.45 | +0.8338 | 32.63 | 24.52 | ✓ | 3181.6 |
| 6075 | 8 | 26.58 | 99.72 | 4.32 | +0.8360 | 35.55 | 26.51 | ✓ | 3181.6 |
| 6750 | 9 | 28.38 | 99.78 | 4.03 | +0.8188 | 38.26 | 28.30 | ✓ | 3181.6 |
| 7425 | 10 | 30.23 | 99.85 | 3.97 | +0.8226 | 40.94 | 30.16 | ✓ | 3181.6 |
| 8100 | 11 | 32.07 | 99.93 | 3.91 | +0.8255 | 43.58 | 32.01 | ✓ | 3181.6 |
| 8775 | 12 | 33.89 | 100.00 | 3.84 | +0.8245 | 46.17 | 33.82 | ✓ | 3181.6 |
| 9450 | 13 | 35.66 | 100.07 | 3.78 | +0.8240 | 48.73 | 35.60 | ✓ | 3181.6 |
| 10125 | 14 | 37.32 | 100.13 | 3.68 | +0.8150 | 51.21 | 37.26 | ✓ | 3181.6 |
| 10800 | 15 | 39.04 | 100.20 | 3.64 | +0.8126 | 53.67 | 38.98 | ✓ | 3181.6 |
| 11475 | 16 | 40.75 | 100.27 | 3.60 | +0.8128 | 56.10 | 40.69 | ✓ | 3181.6 |
| 12150 | 17 | 42.43 | 100.34 | 3.55 | +0.8103 | 58.49 | 42.38 | ✓ | 3181.6 |
| 12825 | 18 | 44.09 | 100.40 | 3.50 | +0.8070 | 60.86 | 44.03 | ✓ | 3181.6 |


### `modular_opt_lr1e4_w200_ev_normuon_300s_2026-09-20_2304`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 100 | 2 | 0.48 | 98.85 | --- | --- | 0.00 | 0.00 | ✓ | 3181.6 |
| 200 | 5 | 1.49 | 98.88 | 11.79 | --- | 1.18 | 1.18 | ✓ | 3181.6 |
| 300 | 8 | 2.71 | 98.93 | 15.24 | +0.6499 | 2.70 | 2.46 | ✓ | 3181.6 |


### `modular_opt_lr1e4_w200_sf_normuon_300s_2026-09-20_2230`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 100 | 2 | 0.48 | 98.85 | --- | --- | 0.00 | 0.00 | ✓ | 2545.9 |
| 200 | 5 | 1.49 | 98.88 | 11.79 | --- | 1.18 | 1.18 | ✓ | 2545.9 |
| 300 | 8 | 2.72 | 98.93 | 15.27 | +0.6497 | 2.71 | 2.46 | ✓ | 2545.9 |


### `modular_opt_normuon_sf_otwd_3000s_2026-09-20_2138`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 100 | 2 | 0.12 | 98.84 | --- | --- | 0.00 | 0.00 | ✓ | 2545.9 |
| 300 | 8 | 0.29 | 98.85 | 0.98 | --- | 0.20 | 0.20 | ✓ | 2545.9 |
| 600 | 16 | 0.50 | 98.86 | 0.84 | +0.7777 | 0.45 | 0.42 | ✓ | 2545.9 |


### `modular_opt_stage3_ns5_2026-09-20`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 100 | 2 | 0.31 | 98.84 | --- | --- | 0.00 | 0.00 | ✓ | 1271.5 |
| 120 | 3 | 0.35 | 98.84 | 4.86 | --- | 0.10 | 0.10 | ✓ | 1271.5 |


### `modular_opt_stage3_ns5_otwd_3000s_2026-09-20_1800`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 100 | 2 | 0.31 | 98.84 | --- | --- | 0.00 | 0.00 | ✓ | 1271.5 |
| 300 | 8 | 0.72 | 98.85 | 2.58 | --- | 0.52 | 0.52 | ✓ | 1271.5 |
| 600 | 16 | 1.24 | 98.86 | 2.27 | +0.5339 | 1.20 | 1.05 | ✓ | 1271.5 |
| 666 | 17 | 1.35 | 98.86 | 3.40 | +0.3741 | 1.42 | 1.16 | ✓ | 1271.5 |


### `morph_IOI3_base_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.8 |


### `morph_IOI3_base_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.8 |


### `morph_IOI3_base_s3`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.8 |


### `morph_IOI3_base_s4`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.8 |


### `morph_IOI3_ft_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.8 |


### `morph_IOI3_ft_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.8 |


### `morph_IOI3_ft_s3`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.8 |


### `morph_IOI3_ft_s4`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.8 |


### `morph_L2_base_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.6 |


### `morph_L2_ft_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.6 |


### `morph_L3_base_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.8 |


### `morph_L3_base_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.8 |


### `morph_L3_ft_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.8 |


### `morph_L3_ft_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1728.8 |


### `morph_L4_base_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1729.7 |


### `morph_L4_ft_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1729.7 |


### `mqe3ne49`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1350 | 0 | 234.31 | 101.86 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 2700 | 1 | 319.27 | 106.20 | 120.78 | --- | 163.06 | 163.06 | ✓ | 635.7 |
| 4050 | 2 | 381.68 | 110.36 | 99.32 | +0.5112 | 297.13 | 258.68 | ✓ | 635.7 |
| 5400 | 3 | 432.11 | 114.23 | 86.32 | +0.6016 | 413.67 | 328.92 | ✓ | 635.7 |
| 6750 | 4 | 474.67 | 117.78 | 77.50 | +0.6416 | 518.30 | 385.05 | ✓ | 635.7 |
| 8100 | 5 | 511.77 | 121.09 | 71.50 | +0.6556 | 614.83 | 432.16 | ✓ | 635.7 |
| 9450 | 6 | 544.50 | 124.12 | 66.51 | +0.6606 | 704.61 | 472.69 | ✓ | 635.7 |
| 10800 | 7 | 573.76 | 126.90 | 62.66 | +0.6576 | 789.21 | 508.26 | ✓ | 3814.2 |


### `onset_AdamW_lr7.5e-5_continuous`
> **Verdict / Note:** Continuous (no-segmentation) AdamW run, first-crop — finished clean at step 54000/10 checkpoints after an early dateutil-crash fix; later shown to have a much narrower control range than the random-crop variants it was compared against.

> **Recipe:** model medium-base · lr 7.5e-05 · batch 1 · crop_frames 512 · optimizer adamw · steps 54000 · mode:scalar · scalar:onset_density · feature:melody · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 10800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 16200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 21600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 27000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 32400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 37800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 43200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 48600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 54000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `onset_AdamW_lr7.5e-5_randomcrop`
> **Verdict / Note:** Random-crop AdamW baseline — random-crop dramatically widened the onset-density control range vs the earlier first-crop runs (this is one of the two runs that established that).

> **Recipe:** model medium-base · lr 7.5e-05 · batch 1 · crop_frames 512 (random-crop) · optimizer adamw · steps 54000 · mode:scalar · scalar:onset_density · feature:melody · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 10800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 16200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 21600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 27000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 32400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 37800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 43200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 48600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 54000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `onset_AdamW_lr7.5e-5_randomcrop_20ep`
> **Verdict / Note:** Random-crop AdamW at 20 epochs — part of the random-crop control-range study; superseded as a recipe by the Fusion+random-crop runs, which had a cleaner training trajectory.

> **Recipe:** model medium-base · lr 7.5e-05 · batch 1 · crop_frames 512 (random-crop) · optimizer adamw · steps 108000 · mode:scalar · scalar:onset_density · feature:melody · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 10800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 16200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 21600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 27000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 32400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 37800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 43200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 48600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 54000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 59400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 64800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 70200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 75600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 81000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 86400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 91800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 97200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 102600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 108000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `onset_FUSION_lr1e4_5000_FIXED`
> **Verdict / Note:** Became the E_fusion_v2 checkpoint used in the composed_sweep replication of the FusionCC advantage (Goa-only, 1e-4/5000 steps).

> **Recipe:** model medium-base · lr 0.0001 · batch 1 · crop_frames 1024 · optimizer fusion · steps 5000 · mode:scalar · scalar:onset_density · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 2000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 3000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 4000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 5000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `onset_FUSION_lr2e5_40epoch`
> **Verdict / Note:** The ONNX reference head — monotonic, calibrated steering (density 3→4.88, 11→11.15 onsets/sec); soup_exppeak.pt from this run is baked into the shipped ONNX DiT control graph.

> **Recipe:** model medium-base · lr 2e-05 · batch 1 · crop_frames 512 · optimizer fusion · steps 216000 · mode:scalar · scalar:onset_density · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 10800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 16200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 21600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 27000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 32400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 37800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 43200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 48600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 54000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 59400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 64800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 70200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 75600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 81000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 86400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 91800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 97200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 102600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 108000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 113400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 118800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 124200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 129600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 135000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 140400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 145800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 151200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 156600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 162000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 167400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 172800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 178200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 183600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 189000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 194400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 199800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 205200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 210600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 216000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `onset_FUSION_lr8e5_10epoch`
> **Verdict / Note:** Higher-LR FusionOpt variant, 10 epochs — no distinct standalone quality verdict recorded beyond the general optimizer-bracket findings.

> **Recipe:** model medium-base · lr 8e-05 · batch 1 · crop_frames 512 · optimizer fusion · steps 54000 · mode:scalar · scalar:onset_density · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 10800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 16200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 21600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 27000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 32400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 37800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 43200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 48600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 54000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `onset_FUSION_lr8e5_1p2ep`
> **Verdict / Note:** Quick higher-LR FusionOpt probe — no distinct standalone quality verdict recorded.

> **Recipe:** model medium-base · lr 8e-05 · batch 1 · crop_frames 1024 · optimizer fusion · steps 6480 · mode:scalar · scalar:onset_density · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 3600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `onset_FusionCC_lr1e-4_randomcrop`
> **Verdict / Note:** Best onset head — the campaign's first significant win: corr/gain g2 .584→.880 (P=.99), tracking mid-range densities beautifully (req 5/6/7 → meas 6.0/6.8/7.6 vs baseline's overshoot).

> **Recipe:** model medium-base · lr 0.0001 · batch 1 · crop_frames 512 (random-crop) · optimizer fusion · steps 54000 · mode:scalar · scalar:onset_density · feature:melody · cc-loss lambda 0.1 · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 10800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 16200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 21600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 27000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 32400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 37800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 43200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 48600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 54000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |


### `onset_FusionCaut_lr1e-4_randomcrop`
> **Verdict / Note:** Cautious-masking variant — a quality TRADE not a win (drier/cleaner separation, muted highs, smears when pushed); over-trains past ep5. Palette option with early-stop, not the default.

> **Recipe:** model medium-base · lr 0.0001 · batch 1 · crop_frames 512 (random-crop) · optimizer fusion (cautious) · steps 54000 · mode:scalar · scalar:onset_density · feature:melody · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 10800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 16200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 21600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 27000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 32400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 37800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 43200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 48600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 54000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |


### `onset_Fusion_lr1e-4_randomcrop`
> **Verdict / Note:** The FusionCC baseline ("E_fusion") — corr/gain g1 .582, g2 .657, g3 .793; solid but superseded by the CC-loss variant above.

> **Recipe:** model medium-base · lr 0.0001 · batch 1 · crop_frames 512 (random-crop) · optimizer fusion · steps 54000 · mode:scalar · scalar:onset_density · feature:melody · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 10800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 16200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 21600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 27000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 32400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 37800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 43200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 48600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 54000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `onset_Fusion_lr1e-4_randomcrop_20ep`
> **Verdict / Note:** 20-epoch Fusion companion to the AdamW 20ep multiprompt render — that render's headline finding (more epochs narrows control range) was specifically about the AdamW variant; no separate Fusion-specific verdict recorded.

> **Recipe:** model medium-base · lr 0.0001 · batch 1 · crop_frames 512 (random-crop) · optimizer fusion · steps 108000 · mode:scalar · scalar:onset_density · feature:melody · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 10800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 16200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `onset_Fusion_lr1e-4_randomcrop_L13-15`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 690.9 |
| 10800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 690.9 |
| 16200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 690.9 |
| 21600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 690.9 |
| 27000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 690.9 |
| 32400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 690.9 |
| 37800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 690.9 |
| 43200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 690.9 |
| 48600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 690.9 |
| 54000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 690.9 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 690.9 |


### `onset_Fusion_lr1e-4_randomcrop_L8-15`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 961.0 |
| 10800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 961.0 |
| 16200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 961.0 |
| 21600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 961.0 |
| 27000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 961.0 |
| 32400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 961.0 |
| 37800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 961.0 |
| 43200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 961.0 |
| 48600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 961.0 |
| 54000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 961.0 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 961.0 |


### `onset_Fusion_opb_10ep`
> **Verdict / Note:** First onset-per-beat (BPM-normalized) head — the tempo-shortcut is dead (corr −0.09 vs the raw onset_density baseline's +0.7 to +0.9), and control is still functional.

> **Recipe:** model medium-base · lr 0.0001 · batch 1 · crop_frames 512 (random-crop) · optimizer fusion · steps 54000 · mode:scalar · scalar:onset_per_beat · feature:melody · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 10800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 16200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 21600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 27000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 32400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 37800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 43200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 48600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 54000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `onset_Fusion_opb_lr1.5e-4_30ep`
> **Verdict / Note:** opb head at +50% LR, extended to 30 epochs — control authority plateaued by epoch 15 (+0.964, same as epoch 25); the extra 15 epochs bought nothing.

> **Recipe:** model medium-base · lr 0.00015 · batch 1 · crop_frames 512 (random-crop) · optimizer fusion · steps 135000 · mode:scalar · scalar:onset_per_beat · feature:melody · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 10800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 16200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 21600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 27000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 32400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 37800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 43200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 48600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 54000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 59400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 64800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 70200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 75600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 81000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1825.4 |
| 86400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1140.8 |
| 91800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1140.8 |
| 97200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1140.8 |
| 102600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1140.8 |
| 108000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1140.8 |
| 113400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1140.8 |
| 118800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1140.8 |
| 124200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1140.8 |
| 129600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1140.8 |
| 135000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1140.8 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1140.8 |


### `onset_density_400trk_crop1024`
> **Verdict / Note:** Original scalar onset-density head — steers output onset density at corr +0.90 (gain 1): sparse→dense = 4.3→8.3 onsets/sec.

> **Recipe:** model medium-base · lr 0.0002 · batch 1 · crop_frames 1024 · optimizer adamw · steps 6000 · mode:scalar · scalar:onset_density · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 2000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 3000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 4000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 5000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 6000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `onset_density_FULL_3000_crop1024`
> **Verdict / Note:** Full-dataset retrain attempt — crashed at step ~2000 on a junk silence.npy crop; superseded by the _c variant after the dataset fix.

> **Recipe:** model medium-base · lr 0.0002 · batch 1 · crop_frames 1024 · optimizer adamw · steps 3000 · mode:scalar · scalar:onset_density · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 2000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `onset_density_FULL_3000b_crop1024`
> **Verdict / Note:** Second full-dataset retrain attempt — crashed again on the same junk-crop issue; superseded by the _c variant.

> **Recipe:** model medium-base · lr 0.0002 · batch 1 · crop_frames 1024 · optimizer adamw · steps 3000 · mode:scalar · scalar:onset_density · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 2000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `onset_density_FULL_3000c_crop1024`
> **Verdict / Note:** Full-dataset result after the crop-skip fix — corr +0.92, wider range (3.6→9.1), but gain sweep shows non-monotonic collapse past gain 3 (overtraining elbow at ~2000 steps/lr2e-4).

> **Recipe:** model medium-base · lr 0.0002 · batch 1 · crop_frames 1024 · optimizer adamw · steps 3000 · mode:scalar · scalar:onset_density · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 2000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 3000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `onset_envelope_ema20`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 2 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 3 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 6 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 8 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 10 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 13 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 14 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 16 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 17 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 18 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `onset_envelope_ema40`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 2 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 3 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 6 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 8 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 10 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 13 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 14 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 16 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 17 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 18 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 21 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 22 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 23 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 24 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 25 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 26 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 27 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 28 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 29 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 30 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 31 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 32 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 33 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 34 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 35 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 36 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 37 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 38 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 39 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 40 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `plain_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 4784 | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 42056.2 |


### `plain_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 4784 | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 42056.2 |


### `precision_ladder_t256_bf16mixed`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 4500 | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 42056.2 |


### `precision_ladder_t256_fp16mixed`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 4500 | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 42056.2 |


### `precision_ladder_t256_fp32`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 4500 | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 42056.2 |


### `proll_fullft_t256_bf16_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2688 | 31 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 12948.0 |


### `proll_fullft_t256_bf16_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2688 | 31 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 12948.0 |


### `pzqv5mcw`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5 | 0 | 1.03 | 34.89 | --- | --- | 0.00 | 0.00 | ✓ | 82.5 |
| 10 | 1 | 1.53 | 34.91 | 140.11 | --- | 0.70 | 0.70 | ✓ | 82.5 |


### `qy50uilf`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1350 | 0 | 128.31 | 98.83 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 2700 | 1 | 176.85 | 99.64 | 66.07 | --- | 89.19 | 89.19 | ✓ | 635.7 |
| 4050 | 2 | 213.39 | 100.61 | 54.47 | +0.5354 | 162.72 | 142.78 | ✓ | 635.7 |
| 5400 | 3 | nan | nan | nan | +nan | nan | nan | ❌ | 635.7 |
| 6750 | 4 | nan | nan | nan | +nan | nan | nan | ❌ | 635.7 |
| 8100 | 5 | nan | nan | nan | +nan | nan | nan | ❌ | 635.7 |
| 9450 | 6 | nan | nan | nan | +nan | nan | nan | ❌ | 635.7 |
| 10800 | 7 | nan | nan | nan | +nan | nan | nan | ❌ | 3814.2 |


### `real`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 660 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 1320 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 1980 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 2640 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 3300 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 3960 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 4620 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 5280 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 5940 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 6600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 7260 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 7920 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 8580 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 9240 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 9900 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 10560 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 11220 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 11880 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 12540 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 13200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 13860 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 14520 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |


### `repaired`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| -1 | -1 | 93.19 | 93.19 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| -1 | -1 | 28.26 | 28.26 | --- | --- | 97.38 | 97.38 | ✓ | 635.7 |
| -1 | -1 | 88.99 | 88.99 | --- | -0.0878 | 190.74 | 128.85 | ✓ | 635.7 |
| -1 | -1 | 93.19 | 93.19 | --- | -0.6582 | 319.59 | 0.00 | ✓ | 635.7 |


### `rhythm_heads`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `riffer_200trk_2e-4_adamw`
> **Verdict / Note:** Part of the June-19 LR/optimizer bracket — reference-tracking peaks hard around step 6000 then elbow-declines; this is the recipe that set that baseline.

> **Recipe:** model medium-base · lr 0.0002 · batch 1 · crop_frames 2048 · optimizer adamw · steps 6000 · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 2000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 3000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 4000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 5000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 6000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |


### `riffer_200trk_2e-4_fusion`
> **Verdict / Note:** FusionOpt variant in the LR/optimizer bracket — no distinct standalone verdict beyond the bracket's overall lr1e-4-is-the-sweet-spot finding.

> **Recipe:** model medium-base · lr 0.0002 · batch 1 · crop_frames 1024 · optimizer fusion · steps 4000 · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 2000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 3000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 4000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |


### `riffer_200trk_2e-4_sfadamw`
> **Verdict / Note:** Optimizer-variant in the LR/optimizer bracket — no distinct standalone verdict beyond the bracket's overall lr1e-4-is-the-sweet-spot finding.

> **Recipe:** model medium-base · lr 0.0002 · batch 1 · crop_frames 1024 · optimizer sfadamw · steps 4000 · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 2000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 3000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 4000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |


### `riffer_200trk_4e-4_adamw`
> **Verdict / Note:** Higher-LR bracket variant — heavier LR pushed the adapter toward the mode-collapse regime the bracket was designed to detect.

> **Recipe:** model medium-base · lr 0.0004 · batch 1 · crop_frames 2048 · optimizer adamw · steps 6000 · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 2000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 3000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 4000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 5000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 6000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |


### `riffer_200trk_5e-5_fusion`
> **Verdict / Note:** Lowest-LR FusionOpt variant in the bracket — no distinct standalone verdict recorded.

> **Recipe:** model medium-base · lr 5e-05 · batch 1 · crop_frames 1024 · optimizer fusion · steps 4000 · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 2000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 3000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 4000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |


### `riffer_200trk_6e-4_adamw_wu`
> **Verdict / Note:** Highest-LR bracket variant (with warmup) — same bracket that established heavier LR mode-collapses outputs across references.

> **Recipe:** model medium-base · lr 0.0006 · batch 1 · crop_frames 2048 · optimizer adamw · steps 6000 · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 2000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 3000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 4000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 5000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 6000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |


### `riffer_20pct_2048_lr1e3`
> **Verdict / Note:** 10x-LR follow-up — outputs were nearly identical across different references (0.3% diff): a mode-collapse mirage, not real reference-tracking.

> **Recipe:** model medium-base · lr 0.001 · batch 1 · crop_frames 2048 · optimizer unset in checkpoint (early run, predates the --optimizer flag; current code default is adamw) · steps 200000 · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1500 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 3000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 4500 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 6000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 7500 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 9000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 10500 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 12000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 13500 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 15000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 16500 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |


### `riffer_20pct_2048_nockpt`
> **Verdict / Note:** First riffer concept test — loss barely moved (−0.05 vs a 0.168 noise floor); the adapter learned almost nothing at lr1e-4.

> **Recipe:** model medium-base · lr 0.0001 · batch 1 · crop_frames 2048 · optimizer unset in checkpoint (early run, predates the --optimizer flag; current code default is adamw) · steps 200000 · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1500 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 3000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 4500 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 6000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 7500 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 9000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 10500 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 12000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 13500 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 15000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 16500 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |


### `riffer_400trk_lr1e-4_crop1024`
> **Verdict / Note:** Retrained at more data / lower effective LR to test whether that smooths the riffer effect — reference-specific tracking confirmed, same lr1e-4 peak-then-elbow shape as the 200trk bracket.

> **Recipe:** model medium-base · lr 0.0001 · batch 1 · crop_frames 1024 · optimizer adamw · steps 6000 · mode:audio_ref · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 500 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 1000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 1500 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 2000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 2500 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 3000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 3500 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 4000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 4500 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 5000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 5500 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| 6000 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |


### `riffer_bf16test`
> **Verdict / Note:** Precision/infra smoke test only (bf16 training path) — no steering evaluation.

> **Recipe:** model medium-base · lr 0.0001 · batch 1 · crop_frames 1024 · optimizer unset in checkpoint (early run, predates the --optimizer flag; current code default is adamw) · steps 40 · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 40 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 221.5 |


### `rms_energy_air_ema20`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 2 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 3 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 6 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 8 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 10 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 13 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 14 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 16 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 17 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 18 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `rms_energy_air_ema40`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 2 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 3 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 6 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 8 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 10 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 13 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 14 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 16 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 17 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 18 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 21 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 22 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 23 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 24 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 25 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 26 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 27 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 28 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 29 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 30 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 31 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 32 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 33 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 34 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 35 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 36 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 37 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 38 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 39 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 40 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `rms_energy_body_ema20`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 2 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 3 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 6 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 8 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 10 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 13 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 14 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 16 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 17 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 18 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `rms_energy_body_ema40`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 2 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 3 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 6 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 8 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 10 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 13 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 14 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 16 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 17 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 18 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 21 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 22 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 23 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 24 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 25 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 26 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 27 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 28 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 29 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 30 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 31 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 32 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 33 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 34 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 35 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 36 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 37 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 38 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 39 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 40 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `sa3-goa-dora-47s-b4-cont__x20b3ygb`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1350 | 0 | 27.69 | 41.19 | --- | --- | 0.00 | 0.00 | ✓ | 82.6 |
| 2700 | 1 | 31.67 | 43.08 | 8.24 | --- | 11.12 | 11.12 | ✓ | 82.6 |
| 4050 | 2 | 35.16 | 44.72 | 8.26 | -0.0628 | 22.27 | 15.25 | ✓ | 82.6 |
| 5400 | 3 | 37.31 | 45.24 | 8.42 | -0.0174 | 33.64 | 19.02 | ✓ | 82.6 |
| 6750 | 4 | 39.44 | 45.86 | 8.45 | -0.0118 | 45.04 | 22.29 | ✓ | 247.8 |


### `sa3-goa-dora-47s-b4__vjnnndnu`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1350 | 0 | 13.95 | 37.36 | --- | --- | 0.00 | 0.00 | ✓ | 82.6 |
| 2700 | 1 | 19.18 | 38.49 | 8.64 | --- | 11.66 | 11.66 | ✓ | 82.6 |
| 4050 | 2 | 23.24 | 39.49 | 8.49 | +0.0492 | 23.13 | 16.75 | ✓ | 247.8 |


### `sa3-goa-dora-47s-r128-adamw__dq0egegi`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1350 | 0 | 34.92 | 101.09 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 2700 | 1 | 48.59 | 102.83 | 24.09 | --- | 32.52 | 32.52 | ✓ | 635.7 |
| 4050 | 2 | 59.31 | 104.65 | 24.15 | +0.0057 | 65.12 | 46.18 | ✓ | 635.7 |
| 5400 | 3 | 68.16 | 106.37 | 24.03 | -0.0062 | 97.56 | 56.61 | ✓ | 635.7 |
| 6750 | 4 | 76.02 | 108.12 | 24.07 | -0.0157 | 130.06 | 65.48 | ✓ | 635.7 |
| 8100 | 5 | 83.20 | 109.87 | 24.15 | -0.0164 | 162.66 | 73.40 | ✓ | 635.7 |
| 9450 | 6 | 89.83 | 111.59 | 24.21 | -0.0215 | 195.34 | 80.58 | ✓ | 635.7 |
| 10800 | 7 | 95.96 | 113.31 | 24.21 | -0.0234 | 228.02 | 87.20 | ✓ | 1907.2 |


### `sa3-goa-dora-47s-r128-fusion-caut__qy50uilf`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1350 | 0 | 128.31 | 98.83 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 2700 | 1 | 176.85 | 99.64 | 66.07 | --- | 89.19 | 89.19 | ✓ | 635.7 |
| 4050 | 2 | 213.39 | 100.61 | 54.47 | +0.5354 | 162.72 | 142.78 | ✓ | 635.7 |
| 5400 | 3 | nan | nan | nan | +nan | nan | nan | ❌ | 635.7 |
| 6750 | 4 | nan | nan | nan | +nan | nan | nan | ❌ | 635.7 |
| 8100 | 5 | nan | nan | nan | +nan | nan | nan | ❌ | 635.7 |
| 9450 | 6 | nan | nan | nan | +nan | nan | nan | ❌ | 635.7 |
| 10800 | 7 | nan | nan | nan | +nan | nan | nan | ❌ | 3814.2 |


### `sa3-goa-dora-47s-r128-fusion__mqe3ne49`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1350 | 0 | 234.31 | 101.86 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 2700 | 1 | 319.27 | 106.20 | 120.78 | --- | 163.06 | 163.06 | ✓ | 635.7 |
| 4050 | 2 | 381.68 | 110.36 | 99.32 | +0.5112 | 297.13 | 258.68 | ✓ | 635.7 |
| 5400 | 3 | 432.11 | 114.23 | 86.32 | +0.6016 | 413.67 | 328.92 | ✓ | 635.7 |
| 6750 | 4 | 474.67 | 117.78 | 77.50 | +0.6416 | 518.30 | 385.05 | ✓ | 635.7 |
| 8100 | 5 | 511.77 | 121.09 | 71.50 | +0.6556 | 614.83 | 432.16 | ✓ | 635.7 |
| 9450 | 6 | 544.50 | 124.12 | 66.51 | +0.6606 | 704.61 | 472.69 | ✓ | 635.7 |
| 10800 | 7 | 573.76 | 126.90 | 62.66 | +0.6576 | 789.21 | 508.26 | ✓ | 3814.2 |


### `sa3-goa-dora-47s-r64__i8nygj4y`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1350 | 0 | 25.51 | 71.96 | --- | --- | 0.00 | 0.00 | ✓ | 319.6 |
| 2700 | 1 | 35.61 | 73.49 | 17.15 | --- | 23.15 | 23.15 | ✓ | 319.6 |
| 4050 | 2 | 43.35 | 74.96 | 16.97 | +0.0240 | 46.06 | 32.96 | ✓ | 319.6 |
| 5400 | 3 | 49.85 | 76.37 | 17.01 | +0.0029 | 69.02 | 40.55 | ✓ | 319.6 |
| 6750 | 4 | 55.75 | 77.84 | 17.05 | -0.0064 | 92.04 | 47.19 | ✓ | 319.6 |
| 8100 | 5 | 61.04 | 79.23 | 17.09 | -0.0103 | 115.12 | 53.04 | ✓ | 319.6 |
| 9450 | 6 | 65.84 | 80.53 | 17.11 | -0.0188 | 138.22 | 58.28 | ✓ | 319.6 |
| 10800 | 7 | 70.39 | 81.93 | 16.99 | -0.0219 | 161.16 | 63.20 | ✓ | 959.0 |


### `sa3-goa-dora-47s__2ankrkoh`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | 0 | 24.87 | 39.11 | --- | --- | 0.00 | 0.00 | ✓ | 82.6 |


### `sa3_control_runs`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2.4 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2.4 |


### `sanity16_suomi`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 9420 | 59 | 35.08 | 43.30 | --- | --- | 0.00 | 0.00 | ✓ | 237.6 |


### `seg1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 10800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `seg2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 10800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `seg3`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 10800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `seg4`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| 10800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `shuffled`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 660 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 1320 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 1980 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 2640 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 3300 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 3960 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 4620 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 5280 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 5940 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 6600 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 7260 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 7920 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 8580 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 9240 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 9900 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 10560 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 11220 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 11880 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 12540 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 13200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 13860 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| 14520 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2774.3 |


### `site_L13_15`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 20 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1229.4 |
| 40 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1229.4 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1229.4 |


### `site_L8_15`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 20 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1499.5 |
| 40 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1499.5 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 1499.5 |


### `smoke_r256_a256_lr1e4_f512_bs8`
> **Recipe:** LUMI pipeline smoke run: DoRA r256 α256, T=512 crops, batch 8, lr 1e-4 — sanity artifact, not a model candidate.

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 100 | 2 | 37.40 | 139.78 | --- | --- | 0.00 | 0.00 | ✓ | 1267.8 |
| 200 | 5 | 51.36 | 139.80 | 234.35 | --- | 23.44 | 23.44 | ✓ | 1267.8 |
| 300 | 8 | 61.49 | 139.75 | 191.26 | +0.6131 | 42.56 | 38.27 | ✓ | 7607.2 |


### `soups`
> **Verdict / Note:** 12 weight-averaged blends of the 40-epoch Fusion onset run (ascending/descending/peak/sine/triangle schedules) — no single blend has a standout recorded verdict beyond exppeak/expasc being the ones referenced elsewhere as reasonable picks.

> **Recipe:** model medium-base · lr 2e-05 · batch 1 · crop_frames 512 · optimizer fusion · steps 216000 · mode:scalar · scalar:onset_density · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `soups_vibe`
> **Verdict / Note:** Cross-optimizer soups (AdamW × Fusion blends) — the cross_25A75F blend was the standout, topping tracking accuracy while keeping control range.

> **Recipe:** model medium-base · lr 7.5e-05 · batch 1 · crop_frames 512 (random-crop) · optimizer adamw · steps 54000 · mode:scalar · scalar:onset_density · feature:melody · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 228.1 |


### `spectral_kurtosis_ema20`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 2 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 3 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 6 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 8 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 10 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 13 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 14 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 16 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 17 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 18 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `spectral_kurtosis_ema40`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 2 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 3 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 4 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 5 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 6 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 8 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 9 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 10 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 11 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 12 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 13 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 14 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 16 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 17 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 18 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 19 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 20 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 21 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 22 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 23 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 24 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 25 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 26 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 27 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 28 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 29 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 30 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 31 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 32 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 33 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 34 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 35 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 36 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 37 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 38 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 39 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |
| None | 40 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 18.8 |


### `stereo_sweep_w0.0`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 500 | 0 | 80.44 | 98.68 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 1000 | 0 | 109.62 | 98.82 | 107.35 | --- | 53.67 | 53.67 | ✓ | 635.7 |
| 1500 | 0 | 131.68 | 99.05 | 88.23 | +0.5513 | 97.79 | 86.24 | ✓ | 635.7 |
| 2000 | 0 | 149.92 | 99.29 | 76.74 | +0.6390 | 136.16 | 110.78 | ✓ | 635.7 |
| 2500 | 0 | 165.76 | 99.55 | 68.98 | +0.6793 | 170.65 | 130.90 | ✓ | 635.7 |
| 3000 | 1 | 179.94 | 99.84 | 63.39 | +0.7013 | 202.34 | 148.27 | ✓ | 635.7 |
| 3500 | 1 | 192.87 | 100.13 | 59.38 | +0.7056 | 232.03 | 163.70 | ✓ | 635.7 |
| 4000 | 1 | 204.83 | 100.45 | 56.03 | +0.7025 | 260.05 | 177.66 | ✓ | 3814.2 |


### `style_fpA_adamw`
> **Verdict / Note:** Style+groove fingerprint (15-dim) — decisively outperformed by the simpler fpC variant in a direct A/B; not the shipped head.

> **Recipe:** model medium-base · lr 0.0001 · batch 4 x2accum · crop_frames 512 (random-crop) · optimizer adamw · steps 20000 · mode:fingerprint · fp_variant:A · ema 0.999 · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 912.4 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 912.4 |


### `style_fpC_adamw`
> **Verdict / Note:** Ship this — best genre steering of the style heads (Goa confidence 0.92, Psy 0.46).

> **Recipe:** model medium-base · lr 0.0001 · batch 4 x2accum · crop_frames 512 (random-crop) · optimizer adamw · steps 20000 · mode:fingerprint · fp_variant:C · ema 0.999 · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 912.4 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 912.4 |


### `style_fpC_genrecc`
> **Verdict / Note:** Don't use — the genre-consistency loss variant HURT steering vs plain fpC (Goa 0.92→0.65, Psy 0.46→0.03); meter-in-the-gradient added interference, not signal.

> **Recipe:** model medium-base · lr 0.0001 · batch 4 x2accum · crop_frames 512 (random-crop) · optimizer adamw · steps 20000 · mode:fingerprint · fp_variant:C · genre-cc lambda_fp 0.1 supervise@0,1,2,4 · ema 0.999 · bf16

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2700 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 912.4 |
| 5400 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 912.4 |
| 8100 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 912.4 |
| 10800 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 912.4 |
| 13500 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 912.4 |
| 16200 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 912.4 |
| 18900 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 912.4 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 912.4 |


### `subloss_goa_k12`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | 3 | 65.46 | 105.26 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |
| 27000 | 19 | 144.06 | 127.95 | 6.73 | --- | 145.45 | 145.45 | ✓ | 1907.2 |


### `subloss_goa_k2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | 3 | 66.35 | 105.64 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |
| 27000 | 19 | 146.34 | 129.54 | 6.80 | --- | 146.98 | 146.98 | ✓ | 1907.2 |


### `subloss_goa_k20`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2700 | 1 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 39256.2 |


### `subloss_goa_k5`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | 3 | 65.92 | 105.47 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |
| 27000 | 19 | 145.03 | 128.63 | 6.76 | --- | 145.93 | 145.93 | ✓ | 1907.2 |


### `subloss_k24_avpaug_t512_bf16_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2368 | 63 | 48.47 | 108.74 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `subloss_k24_biggoa_t512_bf16_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 12480 | 63 | 98.77 | 120.34 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `subloss_k24_bigmix_t512_bf16_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 15680 | 55 | 109.16 | 124.32 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `subloss_k24_suomi_t512_bf16_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1216 | 63 | 31.10 | 102.28 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `subloss_v3sel_k12`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 27000 | 19 | 147.40 | 129.62 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `subloss_v3sel_k2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 27000 | 19 | 146.65 | 129.80 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `subloss_v3sel_k5`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 27000 | 19 | 147.19 | 129.97 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `subloss_v3sel_k5_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 27000 | 19 | 146.66 | 129.70 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `subloss_v3sel_k5_tgate`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 16200 | 11 | 115.09 | 118.62 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `subloss_v3sel_k5_tgate_deficit_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 27000 | 19 | 147.06 | 129.86 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `subloss_v3sel_k5_tgate_deficit_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 27000 | 19 | 147.08 | 129.88 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `subloss_v3sel_k5_tgate_r2_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 27000 | 19 | 146.70 | 129.76 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `suomi`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 9420 | 59 | 35.08 | 43.30 | --- | --- | 0.00 | 0.00 | ✓ | 237.6 |


### `suomi_r256_lr1e-4`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2340 | 59 | 164.38 | 144.90 | --- | --- | 0.00 | 0.00 | ✓ | 7607.2 |


### `suomi_r256_lr3e-5`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2340 | 59 | 65.16 | 143.64 | --- | --- | 0.00 | 0.00 | ✓ | 7607.2 |


### `suomi_r32_lr1e-4`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1140 | 59 | 152.43 | 116.06 | --- | --- | 0.00 | 0.00 | ✓ | 807.9 |


### `suomi_r32_lr3e-5`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1140 | 59 | 85.08 | 80.80 | --- | --- | 0.00 | 0.00 | ✓ | 807.9 |


### `suomift_warm_avpaug19_t1024_bf16_k5_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 320 | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 7169.8 |
| 640 | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 7169.8 |
| 1280 | 31 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 40430.2 |


### `suomift_warm_goaft_t1024_bf16_k5_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 320 | 7 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 7169.8 |
| 640 | 15 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 7169.8 |
| 1280 | 31 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 40430.2 |


### `version_None`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 75 | 0 | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ❌ | 25426.1 |


### `vjnnndnu`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1350 | 0 | 13.95 | 37.36 | --- | --- | 0.00 | 0.00 | ✓ | 82.6 |
| 2700 | 1 | 19.18 | 38.49 | 8.64 | --- | 11.66 | 11.66 | ✓ | 82.6 |
| 4050 | 2 | 23.24 | 39.49 | 8.49 | +0.0492 | 23.13 | 16.75 | ✓ | 247.8 |


### `wfleet_avp_t1024_a45_fp32_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 23930 | 9 | 189.83 | 178.59 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `wfleet_mix3_t1024_a45_fp32_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 40440 | 19 | 336.28 | 229.69 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `wfleet_suomi_t1024_a128_fp32_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 25200 | 19 | nan | nan | --- | --- | 0.00 | 0.00 | ❌ | 1907.2 |


### `wfleet_suomi_t1024_a128_fp32_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 25200 | 19 | 185.40 | 154.87 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `wfleet_suomi_t1024_a45_fp32_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 25200 | 19 | 157.21 | 164.52 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `wfleet_suomi_t1024_a45_fp32_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 25200 | 19 | 146.64 | 151.63 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `wfleet_suomi_t512_a45_fp32_s1`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 3160 | 19 | 64.64 | 114.30 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `wfleet_suomi_t512_a45_fp32_s2`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 2520 | 1 | 53.94 | 110.08 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |


### `wide_r256`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 20 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2995.5 |
| 40 | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2995.5 |
| None | None | 0.00 | 0.00 | --- | --- | 0.00 | 0.00 | ✓ | 2995.5 |


### `winning_avp_t1024_a45_fp32`
> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 45.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 19, 'global_step': 11960, 'provenance': {'checkpoint': 'manifest:winning_avp_t1024_a45_fp32', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 6578 | 10 | 303.96 | 112.51 | --- | --- | 0.00 | 0.00 | ✓ | 3814.2 |
| 11960 | 19 | 406.62 | 122.40 | 32.90 | --- | 177.08 | 177.08 | ✓ | 3814.2 |
| 18538 | 30 | 503.54 | 134.08 | 25.42 | +0.5881 | 344.32 | 306.85 | ✓ | 635.7 |
| 24518 | 40 | 573.62 | 143.53 | 21.78 | +0.6694 | 474.56 | 400.13 | ✓ | 635.7 |
| 30498 | 50 | 626.62 | 150.40 | 19.39 | +0.6791 | 590.54 | 470.06 | ✓ | 635.7 |
| 35880 | 59 | 665.16 | 155.19 | 17.99 | +0.6894 | 687.37 | 520.57 | ✓ | 3814.2 |


### `winning_avp_t512_a128_fp32`
> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 19, 'global_step': 5980, 'provenance': {'checkpoint': 'manifest:winning_avp_t512_a128_fp32', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 3289 | 10 | 199.44 | 102.68 | --- | --- | 0.00 | 0.00 | ✓ | 3814.2 |
| 4784 | 15 | 238.77 | 104.71 | 49.98 | --- | 74.72 | 74.72 | ✓ | 635.7 |
| 5980 | 19 | 265.32 | 106.22 | 45.25 | +0.6720 | 128.83 | 118.09 | ✓ | 3814.2 |
| 6279 | 20 | 271.65 | 106.60 | 51.58 | +0.6546 | 144.25 | 127.55 | ✓ | 635.7 |
| 9269 | 30 | 329.26 | 110.97 | 34.31 | +0.6068 | 246.84 | 204.21 | ✓ | 635.7 |
| 12259 | 40 | 376.91 | 115.23 | 29.68 | +0.6564 | 335.57 | 266.77 | ✓ | 635.7 |
| 15249 | 50 | 414.16 | 118.36 | 26.62 | +0.6673 | 415.18 | 314.74 | ✓ | 635.7 |
| 17940 | 59 | 442.14 | 120.59 | 24.89 | +0.6832 | 482.15 | 350.28 | ✓ | 3814.2 |
| 34385 | 114 | 591.09 | 138.39 | 19.62 | +0.4220 | 804.87 | 528.73 | ✓ | 635.7 |
| 68471 | 228 | 873.99 | 197.83 | 16.90 | +0.3168 | 1380.95 | 841.23 | ✓ | 3814.2 |


### `winning_avp_t512_a45_bf16`
> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 45.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 19, 'global_step': 5980, 'provenance': {'checkpoint': 'manifest:winning_avp_t512_a45_bf16', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 3289 | 10 | 220.40 | 107.27 | --- | --- | 0.00 | 0.00 | ✓ | 3814.2 |
| 4784 | 15 | 266.94 | 111.03 | 54.79 | --- | 81.91 | 81.91 | ✓ | 3814.2 |
| 5980 | 19 | 298.73 | 113.84 | 49.42 | +0.7112 | 141.01 | 130.72 | ✓ | 3814.2 |
| 6279 | 20 | 306.36 | 114.57 | 54.40 | +0.7031 | 157.28 | 141.48 | ✓ | 635.7 |
| 9269 | 30 | 376.83 | 122.49 | 38.00 | +0.6557 | 270.91 | 230.38 | ✓ | 635.7 |
| 12259 | 40 | 435.32 | 129.89 | 32.92 | +0.7111 | 369.35 | 304.42 | ✓ | 635.7 |
| 15249 | 50 | 480.99 | 135.50 | 29.26 | +0.7099 | 456.84 | 361.19 | ✓ | 635.7 |
| 17940 | 59 | 515.14 | 139.57 | 27.08 | +0.7221 | 529.72 | 403.17 | ✓ | 3814.2 |


### `winning_avp_t512_a45_fp32`
> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 45.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 19, 'global_step': 5980, 'provenance': {'checkpoint': 'manifest:winning_avp_t512_a45_fp32', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 3289 | 10 | 220.16 | 107.22 | --- | --- | 0.00 | 0.00 | ✓ | 635.7 |
| 4784 | 15 | 266.75 | 110.95 | 54.73 | --- | 81.82 | 81.82 | ✓ | 3814.2 |
| 5980 | 19 | 298.48 | 113.77 | 49.45 | +0.7073 | 140.96 | 130.53 | ✓ | 3814.2 |
| 6279 | 20 | 306.06 | 114.49 | 54.43 | +0.7011 | 157.24 | 141.25 | ✓ | 635.7 |
| 9269 | 30 | 376.22 | 122.28 | 38.02 | +0.6535 | 270.92 | 229.99 | ✓ | 635.7 |
| 12259 | 40 | 434.68 | 129.65 | 32.87 | +0.7116 | 369.18 | 304.10 | ✓ | 635.7 |
| 15249 | 50 | 480.24 | 135.22 | 29.14 | +0.7109 | 456.32 | 360.76 | ✓ | 635.7 |
| 17940 | 59 | 514.25 | 139.24 | 27.01 | +0.7193 | 528.99 | 402.58 | ✓ | 3814.2 |


### `winning_avpaug10_t512_a45_fp32`
> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 45.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 19, 'global_step': 800, 'provenance': {'checkpoint': 'manifest:winning_avpaug10_t512_a45_fp32', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 440 | 10 | 80.46 | 100.42 | --- | --- | 0.00 | 0.00 | ✓ | 3814.2 |
| 640 | 15 | 96.91 | 101.00 | 143.70 | --- | 28.74 | 28.74 | ✓ | 3814.2 |
| 800 | 19 | 108.26 | 101.40 | 133.08 | +0.7204 | 50.03 | 46.49 | ✓ | 3814.2 |
| 1240 | 30 | 139.18 | 103.23 | 106.31 | +0.7089 | 96.81 | 84.89 | ✓ | 635.7 |
| 1640 | 40 | 164.40 | 105.31 | 95.56 | +0.7629 | 135.03 | 115.81 | ✓ | 635.7 |
| 2040 | 50 | 184.82 | 106.93 | 85.32 | +0.7468 | 169.16 | 139.93 | ✓ | 635.7 |
| 2400 | 59 | 200.73 | 108.19 | 79.24 | +0.7592 | 197.69 | 158.34 | ✓ | 3814.2 |


### `winning_goa_t512_a128_fp32`
> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 19, 'global_step': 13500, 'provenance': {'checkpoint': 'manifest:winning_goa_t512_a128_fp32', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 7425 | 10 | 271.47 | 102.79 | --- | --- | 0.00 | 0.00 | ✓ | 3814.2 |
| 13500 | 19 | 354.27 | 106.61 | 27.04 | --- | 164.24 | 164.24 | ✓ | 3814.2 |
| 14175 | 20 | 362.10 | 107.05 | 32.78 | +0.5287 | 186.36 | 176.94 | ✓ | 635.7 |
| 20925 | 30 | 432.23 | 112.11 | 20.99 | +0.5563 | 328.02 | 276.40 | ✓ | 635.7 |
| 27675 | 40 | 488.25 | 117.05 | 18.08 | +0.5891 | 450.09 | 354.59 | ✓ | 635.7 |
| 34425 | 50 | 529.61 | 120.38 | 16.40 | +0.6041 | 560.78 | 412.39 | ✓ | 635.7 |
| 40500 | 59 | 559.30 | 122.60 | 15.40 | +0.6239 | 654.36 | 453.71 | ✓ | 3814.2 |
| 45900 | 67 | 582.85 | 124.80 | 15.37 | +0.6038 | 737.34 | 485.57 | ✓ | 635.7 |
| 91125 | 134 | 802.31 | 170.01 | 12.06 | +0.3041 | 1282.98 | 754.32 | ✓ | 3814.2 |


### `winning_goa_t512_a45_bf16`
> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 45.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 19, 'global_step': 13500, 'provenance': {'checkpoint': 'manifest:winning_goa_t512_a45_bf16', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 7425 | 10 | 293.41 | 108.04 | --- | --- | 0.00 | 0.00 | ✓ | 3814.2 |
| 13500 | 19 | 385.38 | 114.26 | 28.36 | --- | 172.26 | 172.26 | ✓ | 3814.2 |
| 20925 | 30 | 477.94 | 123.55 | 22.11 | +0.5493 | 336.42 | 296.12 | ✓ | 635.7 |
| 27675 | 40 | 547.02 | 132.08 | 19.26 | +0.6412 | 466.45 | 388.07 | ✓ | 635.7 |
| 34425 | 50 | 597.01 | 137.80 | 17.27 | +0.6381 | 583.04 | 454.78 | ✓ | 635.7 |
| 40500 | 59 | 632.40 | 141.56 | 16.09 | +0.6543 | 680.78 | 502.02 | ✓ | 3814.2 |


### `winning_goa_t512_a45_fp32`
> **Recipe:** {'kind': 'dora/lora', 'lora_config': {'rank': 128, 'alpha': 45.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': {'lr': 0.0001, 'weight_decay': 0.01, 'eps': 1e-08}, 'epoch': 19, 'global_step': 13500, 'provenance': {'checkpoint': 'manifest:winning_goa_t512_a45_fp32', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 7425 | 10 | 292.35 | 107.99 | --- | --- | 0.00 | 0.00 | ✓ | 3814.2 |
| 13500 | 19 | 384.63 | 114.11 | 28.47 | --- | 172.94 | 172.94 | ✓ | 3814.2 |
| 20925 | 30 | 477.63 | 123.40 | 22.22 | +0.5473 | 337.92 | 297.25 | ✓ | 635.7 |
| 27675 | 40 | 546.69 | 131.92 | 19.25 | +0.6401 | 467.84 | 389.02 | ✓ | 635.7 |
| 34425 | 50 | 596.60 | 137.65 | 17.27 | +0.6365 | 584.44 | 455.51 | ✓ | 635.7 |
| 40500 | 59 | 631.99 | 141.44 | 16.16 | +0.6518 | 682.58 | 502.66 | ✓ | 3814.2 |


### `x0eq_goa`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | 3 | 66.00 | 105.62 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |
| 27000 | 19 | 141.14 | 127.41 | 6.63 | --- | 143.22 | 143.22 | ✓ | 1907.2 |


### `x0eq_sub5_goa`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 5400 | 3 | 65.80 | 105.55 | --- | --- | 0.00 | 0.00 | ✓ | 1907.2 |
| 27000 | 19 | 141.10 | 127.26 | 6.62 | --- | 143.00 | 143.00 | ✓ | 1907.2 |


### `x20b3ygb`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1350 | 0 | 27.69 | 41.19 | --- | --- | 0.00 | 0.00 | ✓ | 82.6 |
| 2700 | 1 | 31.67 | 43.08 | 8.24 | --- | 11.12 | 11.12 | ✓ | 82.6 |
| 4050 | 2 | 35.16 | 44.72 | 8.26 | -0.0628 | 22.27 | 15.25 | ✓ | 82.6 |
| 5400 | 3 | 37.31 | 45.24 | 8.42 | -0.0174 | 33.64 | 19.02 | ✓ | 82.6 |
| 6750 | 4 | 39.44 | 45.86 | 8.45 | -0.0118 | 45.04 | 22.29 | ✓ | 247.8 |


### `xftdora128_fullft_avp_t1024`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t1024', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora128_fullft_avp_t1024', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 137.24 | 137.24 | --- | --- | 0.00 | 0.00 | ✓ | 317.8 |


### `xftdora128_fullft_avp_t2048`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t2048', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora128_fullft_avp_t2048', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 138.16 | 138.16 | --- | --- | 0.00 | 0.00 | ✓ | 317.8 |


### `xftdora128_fullft_avp_t256`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t256', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora128_fullft_avp_t256', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 136.57 | 136.57 | --- | --- | 0.00 | 0.00 | ✓ | 317.8 |


### `xftdora128_fullft_avp_t4096`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t4096', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora128_fullft_avp_t4096', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 139.45 | 139.45 | --- | --- | 0.00 | 0.00 | ✓ | 317.8 |


### `xftdora128_fullft_avp_t512`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t512', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora128_fullft_avp_t512', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 136.68 | 136.68 | --- | --- | 0.00 | 0.00 | ✓ | 317.8 |


### `xftdora128_fullft_goa_t1024`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t1024', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora128_fullft_goa_t1024', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 168.29 | 168.29 | --- | --- | 0.00 | 0.00 | ✓ | 317.8 |


### `xftdora128_fullft_goa_t2048`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t2048', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora128_fullft_goa_t2048', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 168.62 | 168.62 | --- | --- | 0.00 | 0.00 | ✓ | 317.8 |


### `xftdora128_fullft_goa_t256`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t256', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora128_fullft_goa_t256', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 168.32 | 168.32 | --- | --- | 0.00 | 0.00 | ✓ | 317.8 |


### `xftdora128_fullft_goa_t4096`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t4096', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora128_fullft_goa_t4096', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 168.86 | 168.86 | --- | --- | 0.00 | 0.00 | ✓ | 317.8 |


### `xftdora128_fullft_goa_t512`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t512', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora128_fullft_goa_t512', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 168.33 | 168.33 | --- | --- | 0.00 | 0.00 | ✓ | 317.8 |


### `xftdora16_fullft_avp_t1024`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t1024', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora16_fullft_avp_t1024', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 52.64 | 52.64 | --- | --- | 0.00 | 0.00 | ✓ | 41.3 |


### `xftdora16_fullft_avp_t2048`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t2048', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora16_fullft_avp_t2048', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 53.01 | 53.01 | --- | --- | 0.00 | 0.00 | ✓ | 41.3 |


### `xftdora16_fullft_avp_t256`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t256', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora16_fullft_avp_t256', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 52.33 | 52.33 | --- | --- | 0.00 | 0.00 | ✓ | 41.3 |


### `xftdora16_fullft_avp_t4096`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t4096', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora16_fullft_avp_t4096', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 53.52 | 53.52 | --- | --- | 0.00 | 0.00 | ✓ | 41.3 |


### `xftdora16_fullft_avp_t512`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t512', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora16_fullft_avp_t512', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 52.37 | 52.37 | --- | --- | 0.00 | 0.00 | ✓ | 41.3 |


### `xftdora16_fullft_goa_t1024`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t1024', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora16_fullft_goa_t1024', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 64.59 | 64.59 | --- | --- | 0.00 | 0.00 | ✓ | 41.3 |


### `xftdora16_fullft_goa_t2048`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t2048', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora16_fullft_goa_t2048', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 64.73 | 64.73 | --- | --- | 0.00 | 0.00 | ✓ | 41.3 |


### `xftdora16_fullft_goa_t256`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t256', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora16_fullft_goa_t256', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 64.54 | 64.54 | --- | --- | 0.00 | 0.00 | ✓ | 41.3 |


### `xftdora16_fullft_goa_t4096`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t4096', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora16_fullft_goa_t4096', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 64.87 | 64.87 | --- | --- | 0.00 | 0.00 | ✓ | 41.3 |


### `xftdora16_fullft_goa_t512`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t512', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora16_fullft_goa_t512', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 64.60 | 64.60 | --- | --- | 0.00 | 0.00 | ✓ | 41.3 |


### `xftdora64_fullft_avp_t1024`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 64, 'alpha': 64.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t1024', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora64_fullft_avp_t1024', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 100.59 | 100.59 | --- | --- | 0.00 | 0.00 | ✓ | 159.8 |


### `xftdora64_fullft_avp_t2048`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 64, 'alpha': 64.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t2048', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora64_fullft_avp_t2048', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 101.29 | 101.29 | --- | --- | 0.00 | 0.00 | ✓ | 159.8 |


### `xftdora64_fullft_avp_t256`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 64, 'alpha': 64.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t256', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora64_fullft_avp_t256', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 100.06 | 100.06 | --- | --- | 0.00 | 0.00 | ✓ | 159.8 |


### `xftdora64_fullft_avp_t4096`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 64, 'alpha': 64.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t4096', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora64_fullft_avp_t4096', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 102.26 | 102.26 | --- | --- | 0.00 | 0.00 | ✓ | 159.8 |


### `xftdora64_fullft_avp_t512`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 64, 'alpha': 64.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t512', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora64_fullft_avp_t512', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 100.14 | 100.14 | --- | --- | 0.00 | 0.00 | ✓ | 159.8 |


### `xftdora64_fullft_goa_t1024`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 64, 'alpha': 64.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t1024', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora64_fullft_goa_t1024', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 123.30 | 123.30 | --- | --- | 0.00 | 0.00 | ✓ | 159.8 |


### `xftdora64_fullft_goa_t2048`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 64, 'alpha': 64.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t2048', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora64_fullft_goa_t2048', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 123.56 | 123.56 | --- | --- | 0.00 | 0.00 | ✓ | 159.8 |


### `xftdora64_fullft_goa_t256`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 64, 'alpha': 64.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t256', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora64_fullft_goa_t256', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 123.28 | 123.28 | --- | --- | 0.00 | 0.00 | ✓ | 159.8 |


### `xftdora64_fullft_goa_t4096`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 64, 'alpha': 64.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t4096', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora64_fullft_goa_t4096', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 123.76 | 123.76 | --- | --- | 0.00 | 0.00 | ✓ | 159.8 |


### `xftdora64_fullft_goa_t512`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 64, 'alpha': 64.0, 'adapter_type': 'dora-rows', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t512', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftdora64_fullft_goa_t512', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 123.33 | 123.33 | --- | --- | 0.00 | 0.00 | ✓ | 159.8 |


### `xftlora128_fullft_avp_t1024`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t1024', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora128_fullft_avp_t1024', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 137.24 | 137.24 | --- | --- | 0.00 | 0.00 | ✓ | 316.1 |


### `xftlora128_fullft_avp_t2048`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t2048', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora128_fullft_avp_t2048', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 138.16 | 138.16 | --- | --- | 0.00 | 0.00 | ✓ | 316.1 |


### `xftlora128_fullft_avp_t256`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t256', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora128_fullft_avp_t256', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 136.57 | 136.57 | --- | --- | 0.00 | 0.00 | ✓ | 316.1 |


### `xftlora128_fullft_avp_t4096`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t4096', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora128_fullft_avp_t4096', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 139.45 | 139.45 | --- | --- | 0.00 | 0.00 | ✓ | 316.1 |


### `xftlora128_fullft_avp_t512`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t512', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora128_fullft_avp_t512', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 136.68 | 136.68 | --- | --- | 0.00 | 0.00 | ✓ | 316.1 |


### `xftlora128_fullft_goa_t1024`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t1024', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora128_fullft_goa_t1024', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 168.29 | 168.29 | --- | --- | 0.00 | 0.00 | ✓ | 316.1 |


### `xftlora128_fullft_goa_t2048`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t2048', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora128_fullft_goa_t2048', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 168.62 | 168.62 | --- | --- | 0.00 | 0.00 | ✓ | 316.1 |


### `xftlora128_fullft_goa_t256`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t256', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora128_fullft_goa_t256', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 168.32 | 168.32 | --- | --- | 0.00 | 0.00 | ✓ | 316.1 |


### `xftlora128_fullft_goa_t4096`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t4096', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora128_fullft_goa_t4096', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 168.86 | 168.86 | --- | --- | 0.00 | 0.00 | ✓ | 316.1 |


### `xftlora128_fullft_goa_t512`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 128, 'alpha': 128.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 128, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t512', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora128_fullft_goa_t512', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 168.33 | 168.33 | --- | --- | 0.00 | 0.00 | ✓ | 316.1 |


### `xftlora16_fullft_avp_t1024`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t1024', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora16_fullft_avp_t1024', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 52.64 | 52.64 | --- | --- | 0.00 | 0.00 | ✓ | 39.6 |


### `xftlora16_fullft_avp_t2048`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t2048', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora16_fullft_avp_t2048', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 53.01 | 53.01 | --- | --- | 0.00 | 0.00 | ✓ | 39.6 |


### `xftlora16_fullft_avp_t256`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t256', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora16_fullft_avp_t256', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 52.33 | 52.33 | --- | --- | 0.00 | 0.00 | ✓ | 39.6 |


### `xftlora16_fullft_avp_t4096`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t4096', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora16_fullft_avp_t4096', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 53.52 | 53.52 | --- | --- | 0.00 | 0.00 | ✓ | 39.6 |


### `xftlora16_fullft_avp_t512`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t512', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora16_fullft_avp_t512', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 52.37 | 52.37 | --- | --- | 0.00 | 0.00 | ✓ | 39.6 |


### `xftlora16_fullft_goa_t1024`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t1024', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora16_fullft_goa_t1024', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 64.59 | 64.59 | --- | --- | 0.00 | 0.00 | ✓ | 39.6 |


### `xftlora16_fullft_goa_t2048`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t2048', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora16_fullft_goa_t2048', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 64.73 | 64.73 | --- | --- | 0.00 | 0.00 | ✓ | 39.6 |


### `xftlora16_fullft_goa_t256`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t256', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora16_fullft_goa_t256', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 64.54 | 64.54 | --- | --- | 0.00 | 0.00 | ✓ | 39.6 |


### `xftlora16_fullft_goa_t4096`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t4096', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora16_fullft_goa_t4096', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 64.87 | 64.87 | --- | --- | 0.00 | 0.00 | ✓ | 39.6 |


### `xftlora16_fullft_goa_t512`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 16, 'alpha': 16.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 16, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t512', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora16_fullft_goa_t512', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 64.60 | 64.60 | --- | --- | 0.00 | 0.00 | ✓ | 39.6 |


### `xftlora64_fullft_avp_t1024`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 64, 'alpha': 64.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t1024', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora64_fullft_avp_t1024', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 100.59 | 100.59 | --- | --- | 0.00 | 0.00 | ✓ | 158.1 |


### `xftlora64_fullft_avp_t2048`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 64, 'alpha': 64.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t2048', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora64_fullft_avp_t2048', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 101.29 | 101.29 | --- | --- | 0.00 | 0.00 | ✓ | 158.1 |


### `xftlora64_fullft_avp_t256`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 64, 'alpha': 64.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t256', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora64_fullft_avp_t256', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 100.06 | 100.06 | --- | --- | 0.00 | 0.00 | ✓ | 158.1 |


### `xftlora64_fullft_avp_t4096`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 64, 'alpha': 64.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t4096', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora64_fullft_avp_t4096', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 102.26 | 102.26 | --- | --- | 0.00 | 0.00 | ✓ | 158.1 |


### `xftlora64_fullft_avp_t512`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 64, 'alpha': 64.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_avp_t512', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora64_fullft_avp_t512', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 100.14 | 100.14 | --- | --- | 0.00 | 0.00 | ✓ | 158.1 |


### `xftlora64_fullft_goa_t1024`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 64, 'alpha': 64.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t1024', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora64_fullft_goa_t1024', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 123.30 | 123.30 | --- | --- | 0.00 | 0.00 | ✓ | 158.1 |


### `xftlora64_fullft_goa_t2048`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 64, 'alpha': 64.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t2048', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora64_fullft_goa_t2048', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 123.56 | 123.56 | --- | --- | 0.00 | 0.00 | ✓ | 158.1 |


### `xftlora64_fullft_goa_t256`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 64, 'alpha': 64.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t256', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora64_fullft_goa_t256', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 123.28 | 123.28 | --- | --- | 0.00 | 0.00 | ✓ | 158.1 |


### `xftlora64_fullft_goa_t4096`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 64, 'alpha': 64.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t4096', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora64_fullft_goa_t4096', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 123.76 | 123.76 | --- | --- | 0.00 | 0.00 | ✓ | 158.1 |


### `xftlora64_fullft_goa_t512`
> **Verdict / Note:** auto: recipe extracted from checkpoint; evaluation sentence pending

> **Recipe:** {'kind': 'safetensors adapter (svd-extracted)', 'lora_config': {'rank': 64, 'alpha': 64.0, 'adapter_type': 'lora', 'dropout': 0.0, 'include': None, 'exclude': None}, 'target_modules_count': 229, 'rank_from_shapes': 64, 'optimizer': 'N/A (SVD-extracted adapter — no training optimizer state)', 'extraction_provenance': {'extracted_from_run': 'fullft_goa_t512', 'extraction_method': 'svd-fullft-delta'}, 'provenance': {'checkpoint': 'manifest:xftlora64_fullft_goa_t512', 'extracted': '2026-07-30 via Misc/extract_recipes.py (real checkpoint read)', 'pruned_slim': False, 'optimizer_note': 'N/A (SVD-extracted adapter — no training optimizer state)'}}

| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| None | None | 123.33 | 123.33 | --- | --- | 0.00 | 0.00 | ✓ | 158.1 |


### `z18fy24b`
| Step | Epoch | ||B||_F | ||A||_F | Velocity (u/1k) | Dir Cosine | Path Len | Displ. Init | Finite | Size (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 500 | 0 | 4.79 | 99.01 | --- | --- | 0.00 | 0.00 | ✓ | 2549.7 |
| 1000 | 0 | 10.47 | 99.27 | 15.15 | --- | 7.57 | 7.57 | ✓ | 2549.7 |
| 1500 | 0 | 14.37 | 99.48 | 13.80 | +0.3232 | 14.48 | 11.78 | ✓ | 2549.7 |
| 2000 | 0 | 17.53 | 99.65 | 13.20 | +0.2489 | 21.08 | 15.12 | ✓ | 2549.7 |
| 2500 | 1 | 20.24 | 99.80 | 12.75 | +0.2016 | 27.45 | 17.97 | ✓ | 2549.7 |
| 3000 | 1 | 22.58 | 99.93 | 12.45 | +0.1605 | 33.67 | 20.41 | ✓ | 2549.7 |
| 3500 | 1 | 24.65 | 100.04 | 12.25 | +0.1277 | 39.80 | 22.56 | ✓ | 2549.7 |

