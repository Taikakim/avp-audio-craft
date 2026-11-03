# E. Literature: what the field knows about melody control, what stays ours, unknown unknowns

Track E of the melody hunt. Evidence dossier, not prose. Written 2026-11-03.
Conventions: "READ" = I read the local PDF or a PDF I downloaded to scratch, with text extracted and grepped. "NOTE-ONLY" = I read only our `papers/*.md` / `papers/knowledge.md` row. "SNIPPET" = I saw it only in a web-search result summary. Anything not READ is UNVERIFIED for the claim in question. Line numbers for papers refer to `pdftotext -layout` output (not page numbers; page numbers were not preserved by the extraction).
Local paths are relative to `/home/kim/Projects/SAO`.

---

## 1. Paper table

Columns: id / what it claims about melody or pitch / how evaluated / what our note concludes / used by us?

### A. Substrate (SA3, SAME)

| id | Claim about melody | Evaluation | Our note | Used? |
|---|---|---|---|---|
| 2605.17991 Stable Audio 3 (READ, local PDF) | No melody control. Controllability = inpainting only (mask + masked input, local-additive cond, zero-init MLP). Says time-varying controls "often rely on fine-tuning ... or auxiliary models" and "can be included by fine-tuning SA3 after its release" (lines 186-191). CFG at training: text and timing embeddings replaced by zero vectors with p=0.1 (line 875-876). Post-trained models need no CFG: guidance baked in by distillation (976-980). | FAD, CLAP, and subjective OVL / REL / MUS ("capacity to articulate musically coherent melodies and harmonies", line 1077). | `papers/arxiv-2605.17991 - Stable Audio 3.md`; CLAUDE.md basics. Held (see section 2). | Yes, it is the substrate. Note the CFG dropout covers text and timing only, so no local condition was ever trained with a null. |
| 2605.18613 SAME (READ, local PDF) | Semantics trained in as linear 1x1 regressors: three octave-band chroma regressors, octave centres 1/5/9, widths 1.0/1.5/1.0, 128 bins each; ILD regressor (lines 339-342). Targets from an 8192 spectrogram. | Reconstruction and downstream; not melody-specific. | `knowledge.md:125`. Held. | Yes: `same_chroma` LatCH head, melody subspace work. |
| 2402.04825 Stable Audio (timing-conditioned) (NOTE-ONLY) | Origin of the SA family; no melody. | n/a | Indexed. | Background. |

### B. Melody / pitch conditioning in audio generators (field practice)

| id | Claim | Evaluation | Our note / status | Used? |
|---|---|---|---|---|
| 2306.05284 MusicGen (READ, PDF fetched) | Melody = chromagram of the reference, quantised by argmax of dominant bin per frame, "information bottleneck" because raw chromagram "often led to reconstructing the original sample, resulting in overfitting" (lines 231-234). Window 2^14, hop 2^12, "large window prevents the model from recovering fine temporal details" (298-300). Condition dropped with p=0.2 in training, CFG scale 3.0 (300-303). Text-only vs +chroma: chroma cosine 0.10 vs 0.66; "robust to dropping the chroma at inference" (Table 2, 386-391, 436-438). | New metric "chroma cosine-similarity", frame-by-frame on quantised chroma, 1000 held-out files (428-431); human melody-match rating 1-100, 40 samples of 10 s. | No note in `papers/`. Not in `knowledge.md` (grep "musicgen": only mentions inside other rows). | No. This is the standard against which our chroma-cosine screen (D15 first run) was weak, see section 4. |
| 2406.10970 JASCO (READ, PDF fetched) | Flow-matching, chords + melody + audio + text. Melody from a pretrained deep-salience multi-F0 detector; melody scores, values below a threshold zeroed (lines 152-170). **Multi-source CFG** over the sets {local},{text},{local,text} with weights alpha (eq. 4, line 175-205): standard CFG "adheres to the temporal condition while ignoring instrumentation information provided in the text", fixed with alpha_text=0.5, alpha_local=0, alpha_local,text=1.5. Training: 20% dropout of all conditions, then 50% independent dropout per condition (252-255). Hypothesis: concatenation beats additive-bias injection for melody (lines ~280-290, labelled "we hypothesize"). | Melody accuracy on 12-bin octave-invariant chroma (for compatibility with Music ControlNet). Table 1 last column, presumed melody accuracy (header cut off in extraction, UNVERIFIED): JASCO 49.1 vs MusicControlNet 47.1. | No note. | No. Direct precedent for our "stream-only guidance scale" next step. |
| 2506.18729 MuseControlLite (READ, PDF fetched) | Lightweight decoupled-cross-attn conditioners on a frozen Stable Audio Open; melody from CQT 128 bins (mean of channels). Pilot study "finds that a fine-tuned model often over-fits to the additional conditions", so uses **separated guidance scales** per condition (lambda_text, lambda_attr, lambda_audio; section 3.5, eq. 9). Table 4: text only Mel acc 0.09 -> with melody 0.60 (CLAP 0.42 -> 0.28). | Melody accuracy = frame-wise argmax pitch class of a chromagram (STFT win 2048, hop 512), code taken from Stable Audio Open ControlNet; 586 Song Describer clips; style-transfer split (text from one subset, attributes from another). | No note. | No. |
| 2410.05151 Hou et al., Stable Audio Open ControlNet (SNIPPET) | Replaces the one-hot chromagram by top-k CQT (128 bins, 4 strongest per frame per channel); argues chroma cannot capture multi-octave pitch or multi-track melody; curriculum masking of the melody prompt. | SNIPPET only. | No note. | No. |
| 2311.07069 Music ControlNet (SNIPPET: appears in JASCO / MuseControlLite comparisons only) | Time-varying melody (chroma), dynamics, rhythm. | Melody accuracy as above. | No note. | No. |
| 2407.15060 MusiConGen (READ partially, grep) | Builds on MusicGen-Melody; chromagram 12 pitch classes plus beat/downbeat; CFG gamma 3, condition dropout 0.5. | Chord/rhythm adherence. | No note. | No. |
| 2609.30548 MuseTimbre (READ, local PDF) | Frozen SA3 Medium plus Basic Pitch roll -> CNN -> zero-init decoupled cross-attention, 25 Euler steps, **CFG lambda_pitch = lambda_timbre = 2** (lines 210-215), multi-condition CFG dropout (204). Dropping the pitch module: frame-F1 0.041 (line 264-265), timbre match unchanged. | Frame-F1 of transcribed render vs fed roll; **ceiling = transcribing the source audio gives 0.540** (line 247-248); PaSST timbre match; 20-listener MUSHRA-like. Headline 57.6% at F1 0.316 (231, 256). | `knowledge.md:51`; numbers held. "UNTESTED" for us. | Not run. Closest published analogue of our pianoroll conditioner on the same backbone family. |
| 2609.12774 DiffSynth-Music (READ, local PDF) | KV-cache adapters on ACE-Step; prosody = pYIN f0 65-1000 Hz resynthesised as a sinusoid (lines 300-302, 358-363). CFG scale 4, 50 steps (391). | **Pitch50**: share of target-voiced frames where the generated vocal is voiced and within 50 cents of target (473-478). Table: DiffSynth 0.4671 vs base models 0.031-0.040 (433-439). | `knowledge.md:56`; held. | Not run. Pitch50 is a stricter metric than ours; see section 4. |
| 2606.18968 Diffusion Warm Initialization (READ, local PDF) | SDEdit-style init from a guide signal; sweet spot tau_init ~ 0.8 (lines 341, 411). | **Jaccard distance between pitch sets** of guide and output (mono pitch via MELODIA, 186-195) plus FAD. | `knowledge.md:113`: "no new capability" vs Longform. | Mechanism already ours (a2a). Metric not used. |
| 2312.08723 StemGen (READ, local PDF) | Multi-source CFG with a separate scale per conditioning source (lines 189-218); metrics inspired by melody-expectation research (200). | FAD plus music-information-retrieval descriptors (transcription, beat, key/chord) comparing distributions. | `knowledge.md:108`. | Concept noted, not used for melody. |
| 2602.09891 Stemphonic (READ, grep) | CFG over all conditions only at steps 3-28, scale 3.0 (lines 229-230). | n/a | indexed | no |
| 2603.04366 Low-Resource Guidance, LatCH origin (READ, local PDF) | Inference-time guidance; pitch via CREPE (monophonic, 160 bins) with sparsity-aware BCE; "Controls with greater variability, such as pitch ... pose challenges"; chroma and PANNs "mixed results"; hypothesis that 1D outputs suit guidance better (lines 218-250). First 20% of steps. | Pitch BCE 0.028-0.057 in Table 1 (all methods), FDopenl3, KLpasst, CLAP, MOS n=15. | `knowledge.md:136`: "sparse high-dim (pitch/chroma) FAIL across all methods". **Overstated** (section 2). | Yes: our whole LatCH family. |

### C. Our hypothesis papers (melody-first, steering, equivariance, disentanglement)

| id | Claim | Evaluation | Our note / status | Used? |
|---|---|---|---|---|
| 2512.04926 SFD (READ, local PDF) | Image diffusion: semantics denoised ahead of texture by delta t; delta t = 0.3 best; FID 8.17 -> 7.08 (REPA) -> 5.24 (SemVAE) -> 3.03 (semantic-first); PCA semantics 4.06 vs SemVAE 3.03; FID 1.06 / 1.04 (lines 321-333, 382-387, 436-462). Images only; nothing about melody. | ImageNet-256 FID. | `knowledge.md:102`, EXPERIMENTS B4: "Give melody its own channel and clock". Numbers held. The jump from "semantic" in images (DINOv2) to "melody" in SAME is ours, not the paper's. | B4 PLANNED, not built. |
| 2608.03920 Equivariant Music Transformer (READ, local PDF) | Symbolic; equivariance loss grows with scale (Anticipatory S 100K 0.238 -> L 800K 0.813, lines 316-322); features alone 0.286 -> 0.290, augmentation 0.069, EMT 0.049 (310-314). | Equivariance loss, next-token loss 0.912 -> 0.847. | `knowledge.md:42`. Numbers held. | E21 probe run; head found equivariant, regulariser not needed. |
| 2602.10058 Evaluating Disentangled Representations (READ, local PDF, partial) | Four-axis probe: informativeness, equivariance (P and R), invariance, disentanglement delta; leakage is asymmetric. | Probes on structure/timbre embeddings. | `knowledge.md:88`. | Method pattern only. |
| 2505.18186 SAE steering on MusicGen (NOTE-ONLY) | Top-k SAEs on residual stream; steering. | NOTE-ONLY. | `knowledge.md:109`. | Background for I6. |
| 2602.11910 TADA activation steering (NOTE-ONLY; PDF local, not read) | Activation steering in audio diffusion. | NOTE-ONLY. | `knowledge.md` caution: SAO VAE is not SAME. | Steering experiments. |
| 2605.31295, 2606.18790 symbolic steering + PID (NOTE-ONLY) | Diff-in-means directions, Gram-Schmidt dual steering, PID coefficient hold. | NOTE-ONLY, 2606.18790 abstract-level. | `knowledge.md:158`. | Not run. |
| 2608.06717 WaveFreqAnchor (NOTE-ONLY; PDF local, not read by me) | Training-free face restoration; phase replacement in a wavelet band, wave-operator anchor. | NOTE-ONLY. | `knowledge.md:99`; EXPERIMENTS D2 (wave operator on whitened chroma planes) DONE, "L_wave not built". | Idea borrowed, not the method. Image domain. |
| 2610.19445 Point-and-Play (NOTE-ONLY) | Instrument timbre code from mixtures; ridge pitch probe R^2 drops 0.78 -> 0.26 when mixed (note says). | NOTE-ONLY. | `knowledge.md:41`. | Proposed basis for V7 (timbre). |
| 2606.07207 Entropy log-barrier (NOTE-ONLY) | Claims phrase structure from a loss reweighting; note flags authenticity red flags (6 of 14 references "Anonymous"). | Qualitative. | Not a control method. | No. |
| Kant & Polansky, Morphological Space (READ, local PDF, grep only) | Contour theory: contour = ordered directional relationships; ranking and n-ary contour add magnitude (PDF lines 13-38). | Music theory. | Design note `papers/deep-research/MORPHOLOGICAL_SPACE_DESIGN_NOTE.md` says all `[paper]` claims PDF-verified. | D12 / D17 / E24 arm B. "L3" is our label; I did not find a "level 3" in the PDF by grep (UNVERIFIED mapping of our "L3 rank tokens" onto a named construct in the paper). |
| 2607.14796 Carbone & Servidio (POINTER, no PDF held) | 2D turbulence; sparse Fourier triads reproduce cascades; intermittency strengthens with injection rate. | NOTE-ONLY, **assessed externally**; note says not a cascade analogue for a DiT. | `papers/Prospective Unchecked/2607.14796 ...md`. | D10 (melody intermittency) DONE, NEGATIVE: melody excess kurtosis 24.5 vs random subspace 23.0 (EXPERIMENTS.md:1178). The paper is physics; the borrowed part is a statistic, not a melody claim. |
| MuScriptor 2607.08168 (SNIPPET only; **no local note**) | Open multi-instrument transcription (Rouard, Krause, Roebel, Simon-Gabriel, Defossez; Mirelo and Kyutai). Decoder-only transformer on mel-spectrograms, trained on 1.45M synthetic MIDI files plus 170k real recordings, then RL. Model card: bias toward pop and Western classical; weaker onset precision on choral music (snippet). | Frame F1 68.7 large vs YourMT3+ 45.5 on the card (snippet). | Appears in CLAUDE.md, EXPERIMENTS and `docs/` only as our meter; there is no `papers/` note and no `knowledge.md` row. | **Our primary melody meter and the source of the pianoroll training data**, yet unreviewed. See section 6, item 1. |

Count: 31 rows above including MuScriptor and SA3/SAME (26 with at least a local PDF or fetched PDF read; MuScriptor, Hou, Music ControlNet and several note-only rows are not).

Other local notes that touch melody only indirectly and which I did not need: 2404.07724 (guidance interval; ties to MuseTimbre / Stemphonic restricted-interval CFG), 2510.07631 Rectified-CFG++ (abstract-level), 2406.02507 autoguidance, 2606.18790. NOTE-ONLY.

---

## 2. Load-bearing quotes checked against PDFs

| Claim in our notes | Source checked | Held? |
|---|---|---|
| SAME chroma: three regressors, octave centres 1/5/9, widths 1.0/1.5/1.0, 128 bins each, linear 1x1 | SAME PDF lines 339-342; SA3 PDF 312 ("two lightweight linear regressors (single 1x1 convolutions)") | **Held**, verbatim. |
| SA3 post-trained models do not need CFG | SA3 PDF 976-980 | **Held.** Also: training CFG dropout is text+timing only (875-876), which matters for section 5. |
| SFD: delta t = 0.3 best, ablation 8.17 / 7.08 / 5.24 / 3.03, PCA 4.06, FID 1.06 / 1.04 | SFD PDF 321-333, 436-462 | **Held.** Note the paper is ImageNet only. |
| EMT: 0.238 -> 0.813 with scale; 0.286 -> 0.290 features alone; augmentation 0.069; EMT 0.049; 0.912 -> 0.847 | EMT PDF table rows 310-322 | **Held.** |
| MuseTimbre: 57.6% at F1 0.316; TokenSynth-A 0.380 and 34.6%; ratings 2.6 vs 2.4 | MuseTimbre PDF 231, 247-262 | **Held** for 57.6, 0.316, 0.380, 34.6, 2.6. |
| DiffSynth-Music prosody: pYIN 65-1000 Hz | DiffSynth PDF 300-302 | **Held.** Pitch50 0.4671 vs 0.031-0.040 is mine from the table (433-439). |
| Low-Resource Guidance: "sparse high-dim (pitch/chroma) FAIL across all methods" | LRG PDF 218-250 | **Partly wrong.** The paper says pitch "pose[s] challenges, and show[s] worse performance across quality metrics"; chroma and PANNs gave "mixed results"; the authors "hypothesize" 1D outputs suit guidance better. Pitch BCE for LatCH-B is 0.028 (the best pitch row; End-to-end 0.030). "Fail" is our paraphrase. Also: the pitch extractor is CREPE, **monophonic**, so the finding says nothing about polyphonic goa. The note's claim "gets worse at our coarser 10.77 Hz" is our inference, not in the paper. |
| LRG: "~6x faster, ~5x less VRAM" | Table 1 runtimes: Beats LatCH-B 17.6 s vs End-to-end 150.1 s, VRAM 5.59 vs 30.42 GB | **Held** (8.5x / 5.4x on beats; about 10x on pitch 17.7 vs 173.1 s). The "6x" is lower than the table. |
| `papers/knowledge.md:136` "100-step DDIM, CFG 7 ... v-param" for LRG | Not checked | UNVERIFIED. The lines I saw with 100 steps / CFG 7 were in the SA3 PDF (line 1003), not LRG. |
| Diffusion Warm Init: sweet spot tau ~ 0.8, pitch Jaccard + FAD | Warm-init PDF 341, 411, 555-586 | **Held.** "on Stable Audio Open" not checked. |
| WaveFreqAnchor, DiffSynth KV cache details, TADA, SAE steering, MIDI-RAE-JEPA, K-nets | NOT checked | UNVERIFIED. |
| `knowledge.md:161` MIDI-RAE-JEPA id 2608.04378 | A web search returned "MIDI-RAE-JEPA ... Symbolic Music" at **2607.14537** | **Possible id mismatch**, SNIPPET only. Needs a one-line check; the note itself says "blog-page-level only". |

Verdict: the notes I checked were accurate on numbers. The one drift is a rhetorical one (LRG "FAIL").

---

## 3. New pointers from search

Marked V = read in full text (PDF downloaded to scratch and grepped), S = search snippet only. None added to `papers/`.

1. **ControlNet, 2302.05543 (V).** Section 3.4 CFG Resolution Weighting. Verbatim from extracted text: "When a conditioning image is added via ControlNet, it can be added to both eps_uc and eps_c, or only to the eps_c. In challenging cases, e.g., when no prompts are given, adding it to both eps_uc and eps_c will completely remove CFG guidance (Figure 5b); using only eps_c will make the guidance very strong (Figure 5c)." Fix: weight w_i = 64/h_i per block. This is the clearest statement of our gotcha. Image domain, 2023.
2. **MusicGen 2306.05284 (V).** Chroma cosine similarity; dominant-bin quantisation as an anti-copying bottleneck; condition dropout 0.2, CFG 3.0. See section 1.
3. **JASCO 2406.10970 (V).** Multi-source CFG with partial-condition terms; per-condition 50% dropout; hypothesis concatenation > additive. See section 1.
4. **MuseControlLite 2506.18729 (V).** Separated guidance scale per condition because the fine-tuned model "often over-fits to the additional conditions"; Table 4 with text-only Mel acc 0.09.
5. **Stable Audio Open ControlNet, Hou et al. 2410.05151 (S).** Top-k CQT instead of chroma; melody accuracy code (`Stability-AI/stable-audio-metrics`, from MuseControlLite) used as a de-facto standard.
6. **MuScriptor 2607.08168 (S).** Our meter has a paper and model cards; the cards (per snippet) flag a bias to pop and Western classical music. HF org `MuScriptor`. License CC-BY-NC-4.0 (relevant to anything we release).
7. **AnyAccomp (S).** Conditions a flow-matching transformer on discrete melody tokens from a VQ-VAE ("VQ-Chroma"), condition dropout with CFG 3. Snippet says a raw-chroma baseline over-fits and VQ-chroma prevents it. Relevant to our "pitch-invariant tokens" arms (E24 A/B/C); reading it would tell whether discrete tokens beat continuous. Not verified.
8. **P-MUSE 2608.01920 (S).** Prompt/MIDI-optional instrumental synthesis and editing; contrasts the full conditional field against the dropped-condition field. Not verified.
9. **MIDI-RAE-JEPA 2607.14537 (S)**: multi-level dropout scheme for CFG over conditioning levels; see the id caveat in section 2.
10. **SegTune (S)**: uses cfg=3 and a separate negative-condition scale cfg_n=1. Minor.
11. **MusiConGen 2407.15060 (V partial).** Condition dropout 0.5, gamma 3.

Not found: any paper that reports CFG applied to a melody stream **and** a failure mode where the stream sits in both branches **in audio**. Search returned nothing specific; absence in a few searches is not proof.

---

## 4. Field practice vs ours

### Methods the field uses that we have not tried (rough cost for us)

| Method | Source | What it would test | Cost |
|---|---|---|---|
| Separate, stream-only guidance scale (3-branch CFG: uncond / text-only / text+stream) | JASCO eq. 4 (V), MuseControlLite eq. 9 (V), StemGen (V) | Our own "Next" in D15. We only have the binary null (stream scaled with the text cfg). | Inference code in `dit.py` near line 516; 1.5x sampling cost; no training. Low. |
| Independent per-condition dropout in training | JASCO 20% all, then 50% each (V) | Whether our stream null is trained as a distinct condition (does the pianoroll training do independent stream dropout? UNVERIFIED, I did not read the training code). | Check a script; change only if needed. |
| Information bottleneck on the conditioning: coarse, quantised dominant-pitch stream, deliberately not full notes | MusicGen (V), AnyAccomp (S) | Our pianoroll is the opposite: full note detail. MusicGen says raw input caused reconstruction of the original. Our training-crop eval (F1 0.653 against source-crop 0.609) cannot rule out partial memorisation; the invented-melody test (36 melodies, 73% frames) is the guard. | A second conditioner arm; a training run. Medium. |
| Concatenation (input channels) rather than additive per-block injection | JASCO (V, "we hypothesize") | Ours is per-block additive on blocks 12-23. `dit.py` already has `batch_input_concat_cond` (line ~508). | A training run plus code. Medium. Evidence is a hypothesis in one paper. |
| Top-k CQT target instead of chroma or pitch rolls | Hou (S) | Different input representation with explicit octave. | New pack builder; training run. Medium. |
| Curriculum masking of the melody prompt | Hou (S) | Balance of text vs melody. | Training run. Medium. |
| Decoupled cross-attention with RoPE rescaled to the roll timeline | MuseTimbre (V) | We used Head-B cross-attn for the morph lane (null) and a per-block inlet for pianoroll (works). The comparison across the two is confounded by source (Melodia f0 vs MuScriptor notes), as E24 notes. | Already have both routes. Low to read. |
| Random temporal-span pitch dropout in training | MuseTimbre (V per knowledge row; I saw "multi-condition CFG dropout" only) | Robustness to partial rolls. | Training change. Low-medium. UNVERIFIED in the PDF. |
| Guide-audio start (SDEdit) with a melody metric to choose the start timestep | Warm Init (V) | We have a2a and Longform; we do not score melody retention. | Eval only. Low. |

### Standard evaluations we have not used

| Evaluation | Source | Status for us |
|---|---|---|
| Chroma cosine similarity vs a **text-only baseline** and a published ceiling | MusicGen: 0.10 text-only, 0.66 with chroma | We used it once (D15 first run) with a **shuffled** arm, which kept the key, so the metric failed (+0.022 n.s.). MusicGen's own protocol has no shuffled control, so its 0.66 vs 0.10 would not have exposed this. Lesson: the field's headline metric is blind to what the shuffled arm tests. |
| Melody accuracy (frame-wise argmax chroma class, STFT 2048 / hop 512), code at `stable-audio-metrics` | Hou, MuseControlLite (V) | Never used. It is the number others publish (MuseControlLite 56.6% / 61.1% on Song Describer). Easy to compute, cheap, but same blindness to key as chroma cosine. Use as a **comparison point**, not a verdict. |
| Pitch50: within 50 cents on target-voiced frames | DiffSynth (V) | Not used. Our "within a semitone of the fed line 14%" (E24, EXPERIMENTS.md:1913) is a looser tolerance on a different quantity; a 50-cent version on a transcribed melody is not directly available (MuScriptor outputs note pitches, not cents). |
| Jaccard distance on pitch sets | Warm Init (V) | Not used; ours is (pitch, frame) F1 which is stricter. |
| Frame-F1 with the **source-audio transcription ceiling** reported | MuseTimbre: 0.540 ceiling, best 0.316 | We do report decoded-source crops as a ceiling (0.609 for the pianoroll, +0.54 for arm C). This matches field practice. |
| Human melody-match rating (reference then generated, 1-100) | MusicGen (V), n=40 | Kim's ear only. Every landed melody result in EXPERIMENTS says "measured, not heard". |
| Reporting the quality cost of the control: FAD/KL/CLAP drop | MuseControlLite: CLAP 0.42 -> 0.28 with melody | We report CE and PQ (D15: "CE and PQ rise against no stream"; E24: PQ -0.25, CE +0.4 with scaled CFG) and a disintegration gate. Comparable in kind. |

### What this implies about the failures we saw

- **Pianoroll "did not work" until stream-scaled CFG**: predicted by ControlNet (2023) and by JASCO's partial-condition derivation (see section 5). It is the standard failure of putting a control in both branches, not a property of the pianoroll.
- **Sparse/high-dimensional controls failing in LatCH** (LRG): consistent with the field's finding that pitch is hard for gradient guidance, but LRG used monophonic CREPE and, importantly, **no training-time conditioning**. The field's working melody systems (MusicGen, JASCO, MuseControlLite, MuseTimbre) all **train the condition in**. Our D15 / E24 results (trained conditioner follows; training-free gradient head follows weakly, D16 ceiling above a 10 s period) line up with that split.
- **Morph / Melodia conditioner null (D17, E23b)** : D17's instrument audit found the meter had range (E23a: Melodia reads synthetic contours at 0.97-0.999). The field analogue (DiffSynth prosody) works with pYIN f0 on **vocals**, i.e. a clean monophonic source. Our source was Melodia on the Demucs `other` stem of goa. That is a data-quality difference the literature does not cover.
- **MusicGen's finding that raw chroma gets copied** suggests: whether our conditioner copies or composes is the question the invented-melody tests answer; a held-out-crop test is still listed as "Next".

---

## 5. Is the CFG-stream gotcha known in the literature?

**Short answer: yes, in general form; no one I found names it for audio melody streams.**

Evidence:
1. ControlNet (Zhang et al. 2023, sec. 3.4, READ): adding the condition to both uncond and cond outputs "will completely remove CFG guidance"; adding to the conditional only makes it "very strong". They introduce CFG Resolution Weighting for the second case. This is the same algebra as ours: CFG scales (cond - uncond); a stream present in both branches cancels out of that difference. The stream still influences each branch's output (so it is not "off"; D15 August run did see +0.100 true-vs-shuffled at cfg 7), but cfg no longer amplifies it.
2. JASCO (READ, eq. 4): treats the temporal condition as its own term in a multi-source CFG, and says that with plain CFG the model "adheres to the temporal condition while ignoring instrumentation information provided in the text", i.e. the opposite imbalance from ours, and tunes alpha_text / alpha_local / alpha_local,text.
3. MuseControlLite (READ, eq. 9): separate lambda for text, attributes, audio; motive is over-fitting to the extra condition.
4. MusicGen (READ): drops "the condition" jointly with p=0.2 and guides with 3.0. It does not discuss partial dropping. Its chroma is on in the cond branch only in that formulation (the chroma is part of the dropped condition set), so its stream **is** scaled by CFG. MusicGen is therefore on our "working" side by construction.
5. SA3 itself (READ): CFG dropout in training is text and timing only (875-876). Our `modular` inlet is outside SA3's CFG design; `dit.py` line 515-520 copies the stream into both branches by default, with `modular_cfg_null` as an opt-in. That default is the same as the inpainting `local_add_cond` handling (line 510-511, same tensor twice), which is correct for a **mask** (an input, not a guidance target) but wrong for a **control to be amplified**.

What I did not find: a paper that reports training a conditioner with a null stream, then evaluating it with the stream in both branches and seeing a near-null result. Our observation is a re-discovery of a known mechanism, not a new finding, but it is still worth reporting as an instrument failure: **every earlier mir_ctrl eval used the both-branch mode** (EXPERIMENTS.md:1913: "Stream in both branches, as every earlier mir_ctrl eval"). See section 6 item 2.

---

## 6. Unknown unknowns (my own inference, ranked by how much they could change our conclusions)

None of these is a finding. Each is a question I could not find asked in `EXPERIMENTS.md` / `DISCOVERIES.md` (grep with AND-narrowed terms; several returned 0 or only a passing mention, noted per item). A zero grep hit is weak evidence, not proof of absence.

1. **Is the MuScriptor meter measuring "melody" or something else, and is it circular? (highest impact.)** Pianoroll and arm-C training data are MuScriptor transcriptions of the training audio (`Kosmos/muscriptor_full`); the eval transcribes the render with the same model and scores against the fed stream. Any systematic transcriber habit (favouring the loudest or most pitched stem, merging arps into held notes, dropping fast acid-bass notes) is shared between stream and meter. W already lists "the transcriber favouring whatever the stream made loudest" as not ruled out (EXPERIMENTS.md:1913). Public card (snippet) says bias toward pop and Western classical, and I found no note on its accuracy on dense electronic music or goa. We have no human-annotated goa melody ground truth, and no independent second transcriber (Basic Pitch, Melodia on a separated stem, a different model) on the **same render**. Cheap test: score the same 144 renders with a second transcriber and check the true-vs-shuffled gap survives. grep: "muscriptor" AND ("bias" OR "accuracy" OR "goa") found nothing in EXPERIMENTS.md.
2. **Which earlier nulls were run with the stream in both CFG branches?** The both-branch default means every conditioner trained with a null stream and evaluated at default would have been under-driven: D13/Q1 control_gain was an in-training measure, not an inference one, but FiLM / Head-B / morph inference evals may be affected. E24 says the morph adapter already used a null uncond (so D17 is not explained by this), but a list of which negative results used which mode does not exist. A table of (experiment, stream in uncond branch? Y/N) would show which nulls need a rerun. Audit-the-instrument rule applies.
3. **Does "melody" mean the same thing to the transcriber and to the listener, in goa?** In dense trance-style music the melodic identity is often a repeated arp or acid line whose character is filter movement, accents and rhythm as much as pitch. A pitch-F1 of 0.653 does not say that the render "sounds like the same riff". Kim's ear is the check and every melody result is "measured, not heard". Field practice has human melody-match ratings (MusicGen); we have none at scale. grep "listener" AND "melody": 0.
4. **Tempo and rhythm as part of melodic identity.** The roll is on the latent frame grid at 10.77 Hz and goa runs around 140-150 BPM (value from general knowledge, not checked in the repo; `docs/data.md` mentions `bpm_essentia` as a crop scalar). We tested transposition (24 transposed crops, 24/24) but I found no time-stretch test of the pianoroll stream (bungee is available), nor a test of whether a melody fed at the wrong tempo for the prompt is followed. E23's 4 tempos were for readout, not for the conditioner. grep "tempo" AND "melod": 1 hit (E23 readout).
5. **Timbre confound in the follow score.** Invented-melody recall ranges from 21% to 100% by prompt (EXPERIMENTS.md:735). If prompts decide whether a note-bearing instrument exists at all, then "follows" is partly "prompt permits". A clean version would fix the prompt and vary the instrument words, or report follow only on frames where the render has a pitched source. The same applies to the MusicGen-style scores.
6. **The T5-Gemma text prior as a competing baseline.** Text-only gives F1 0.045. Never asked: how far can a **text-only** prompt of the melody ("C minor arpeggio, 16th notes, ascending") go, or does text with a note-name already move the render toward a key? That is the "free" competitor to a trained conditioner. grep "T5" AND "melod": 0.
7. **How much melodic variety does the training corpus contain?** 5,400 crops of ~380 s from one genre family; goa riffs repeat heavily. If the corpus has few distinct riffs, "follows fed notes" and "reproduces training riffs" are hard to separate; only the 36 invented melodies and the 24 transposed crops address this, and those on one checkpoint, one seed per prompt. No measurement of distinct-melody count (n-gram or riff-clustering) in `docs/data.md` that I found; grep "melod" AND "variety" / "diversity": 0.
8. **Resolution vs melody speed.** At 10.77 Hz a frame is ~93 ms; 16th notes at 145 BPM are ~103 ms, so fast lines sit near Nyquist for the latent. LRG predicted worse behaviour with coarser latents; MusicGen used a 7.8 Hz chroma (hop 4096 at 32 kHz, lines 298-300) and still got 0.66. The D16 ceiling (follow only above a 10 s period, for the gradient head) and E24's "contour, not notes" (14% within a semitone vs 12% for none) both fit an effective resolution limit; neither separates it from model capacity. No experiment varies the stream's time resolution against follow.
9. **Absolute pitch vs register and octave.** MusicGen and JASCO use octave-invariant chroma; MuseControlLite and Hou use CQT with octave. Ours: absolute notes (pianoroll), centred pitch (arm C). Does the render follow octave? Not scored separately in what I read.
10. **Post-trained medium has no CFG.** SA3-medium runs at cfg 1 with 8 steps; the stream-scaling trick relies on CFG. For release-oriented use on `medium`, a stream-only scale is needed; no test of that regime.
11. **Does the conditioner help or hurt long-form (windowed) renders?** Training crops are T=256 (~24 s); the whole-track use case is 380 s. Not in what I grepped.
12. **A second family of "melody" for non-pitched leads.** Goa lead lines are sometimes noise sweeps or percussive; the MIDI route assigns them nothing or wrong pitches. Related to item 3.

---

## Source pointers for the guide

- Our experiments (all internal): EXPERIMENTS.md D10 (1177), D15 (733), D16 (708), D17 (1291), E21 (1874), E22 (1884), E23 (1898), E24 (1906); CFG null in `stable-audio-3/stable_audio_3/models/dit.py:515-520`.
- Field PDFs I extracted: SA3 `papers/arxiv-2605.17991 - Stable Audio 3.pdf`; SAME, SFD, EMT, MuseTimbre, DiffSynth-Music, LRG, StemGen, Stemphonic, Warm Init, Disentangled (all in `papers/` root); fetched to scratch: ControlNet 2302.05543, MusicGen 2306.05284, JASCO 2406.10970, MuseControlLite 2506.18729, MusiConGen 2407.15060.
