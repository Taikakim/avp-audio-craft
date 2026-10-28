# Review of the Synth Inversion V8 spec (2026-10-28)

Reviewer: KUANG. Under review: `docs/superpowers/specs/2026-10-28-synth-inversion-v8-dynamic-tse-spec.md` (commit 446aa0b).
Checked against: audio-tools-avp `fix/inharmonicity-aux` (ce2d452): `diagnostic_demucs_damage.py`, `eval_v7_cgsp_benchmark.py`,
`cgsp_extractor.py`, `surge_spec_v5.py`/`surge_spec_v6.py`, `render_bank_v5.py`, `models_v4.py`,
`stable_audio_tools/training/modular_opt/{routing,optimizer}.py`; the V7 spec, CONTINUITY's V7 review and its addendum, the walkthrough
review, the Point-and-Play sidecar, WORKLOG (October 28, 2026). Not checked: the stem counts in section 2.1 (the archive is not on this
machine), the Point-and-Play PDF itself, the Demucs source. Nothing was run.

## Verdict

The end state is worth building, and the plan has the right shape: cheap stages with gates. The pieces each exist somewhere in the
literature. The combination is the new part:
- cue-conditioned extraction from a full mix;
- an editable synth patch;
- automation lanes and notes.

I know of no system that returns all of these. I have only checked our own `papers/` notes, not done a literature search.

The argument for the central design choice does not hold yet. That choice is the "greedy" extractor that claims contested sub-bass for the synth.
- The V7 numbers it cites do not show what the spec says (F1–F4).
- The greedy rule would push errors into exactly the parameters the inverter has to get right (D1).

Before Phase 1, run the two cheap measurements in "Run first". They decide whether contested bins are the bottleneck at all. Keep the
real-stem data engine, which is the strongest part of the spec. Split the inverter's output into a static patch plus a few automation
lanes (D4).

## Factual corrections (verified in code or in the repository record)

- **F1. "0.0 % patch retrieval vs. 58.3 % for raw mixture baseline."** This is a broken-instrument result, not evidence about gating:
  - The 0 % comes from the run where the CLAP backbone was never loaded, so the codes collapsed (cosine 0.023 for every input and cue).
  - The 58.3 % is the raw mixture through that same encoder, top-1 among 101 candidates.
  - WINTERMUTE corrected the board text on October 28 (WORKLOG, 07:43).
  - The positive audio cue in that benchmark was the clean target itself (`eval_v7_cgsp_benchmark.py`, `q_audio_pos = encode_audio_cue(t_wav_norm)`).
    So even a working run would have measured an oracle cue, not a cue taken from elsewhere in the track.
- **F2. "Standard 4-stem Demucs ... 58.3 % retrieval."** The 58.3 % belongs to the raw mixture, not to Demucs. Demucs retrieval was never
  computed (CONTINUITY's V7 audit, item 1).
- **F3. The "+23 %" Demucs damage contains no kick.** The V8 thesis rests on this number, but the test that produced it has none of the
  sound V8 is about. From `diagnostic_demucs_damage.py:59-98`:
  - The only drum source is one fixed 0.8 s slice of a single stem file named as a snare ("punchy noisy snare ...").
  - It is mixed with 20 single 0.8 s Surge notes at 0 dB, with one draw each.

  It measures Demucs damage under a snare. It says nothing about a kick and a bass on the same sixteenth.
- **F4. "Point-and-Play relies on a 1D temporal scalar gate ... for a 20ms frame."**
  - The paper gates the tokens of a LoRA-adapted HTSAT encoder (sidecar, method items 1 and 3). Those learned token features can carry a
    frame's bass and kick separately.
  - The 1-D-gate argument fits our own cheap V7 Step 1 variant, which gates `temporal_asp` frames. CONTINUITY found that gate probably
    ignored the cue: the oracle cue scored 0.1451 against 0.1416 for the Demucs cue.
  - The sidecar does not mention 20 ms.
- **F5. "Demucs ... is constrained to conserve total energy (∑Ŝ_k = X)."**
  - To my knowledge, HTDemucs has no sum-to-mix constraint; each source is trained with its own loss. I did not check the Demucs source
    here, so verify this before citing it.
  - Wherever the energy split in contested bins comes from, the asymmetric objective in the spec's own table does not change what the
    correct answer is in those bins (D1).
- **F6. "53 Surge parameters."** V6 has 59 (`surge_spec_v6.py:31`).
  - They include categorical parameters (oscillator, filter and waveshaper types, octaves) and Surge effects (chorus and delay mix).
  - "40 × 53 parameter blocks with cubic Hermite splines" is not defined for categorical parameters.
- **F7. "Dynamic filter sweeps from `bank_v5_s0` ladders."** A ladder is a set of static 0.8 s renders at stepped values of one parameter
  (`render_bank_v5.py:14`, shape `[L, S, 35280]`). No sweep exists inside a render. The Phase 2 gate needs a new render set with automation
  inside each note.
- **F8. "40 blocks per 4-second clip ... aligns with 10.76 Hz."** These are two different grids:
  - 4 s at 10.76 Hz is 43 frames, not 40.
  - 100 ms blocks and SA3 latent frames (4 096 samples, 92.9 ms) do not line up.
  - If LatCH alignment matters, use the latent grid and a clip length in whole latent frames.
- **F9. "Clean Mel Frames (10.76 Hz)" as the inverter input.**
  - The V4–V6 encoders take 128 mel bands × 81 frames per 0.8 s, about 100 frames per second (`models_v4.py:61`).
  - Attack and decay need that rate. Keep the input rate and make only the output 10 Hz.
- **F10. "FusionOpt with NorMuon + Schedule-Free."** That is Fusion v1. The synth-inversion trainers use ModularOptimizer (Fusion v2).

## Design problems

- **D1. The greedy rule works against the inverter.**
  - The objective in the spec's own table, a loss on the synth stem only, already gives the synth exactly what it has in contested bins.
    Giving it "100 % of contested energy" is extra error under that same loss.
  - Kick energy left in the synth estimate looks to the inverter like a retrigger with a low thump on every beat. The inverter then predicts
    shorter decays and a larger filter-envelope amount.
  - It depends on the style:
    - In modern rolling psytrance the bass usually leaves the kick's sixteenth free and is ducked. Greedy extraction would invent a bass
      note at every kick there.
    - Old-school Goa (correction from review discussion, October 28) often has a bright, unducked midrange bass over a damped sub with
      little attack or decay. There the bass is truly present under the kick, but the sub carries little patch information beyond level
      and pitch. The patch identity lives in the body band (120–2500 Hz in the Lexi bands), where the interference comes mostly from
      other synths, not from the kick's sub.
  - So in neither style is the contested sub-bass bin where inversion is won. In old-school Goa, the cue-conditioned single-sound
    extractor earns its keep in the midrange: picking one synth out of leads, acid lines and pads. R1 measures the split per band.

  Recommendation: drop the greedy rule. Train with the plain target loss on real stems and let the arrangement prior come from the data.
- **D2. Inpainting hands the inverter a guess.**
  - Where the kick hides the bass, the inpainted waveform is the extractor's prior, and the inverter then fits parameters to that prior.
  - Better: the extractor returns its estimate plus a per-bin reliability map (low where the estimated target-to-interference ratio is
    low). The inverter, or a refinement step, weights its evidence by that map.

  This is the asymmetric idea in a form that helps. The extractor does not need to sound perfect; it needs to say where it is guessing.
- **D3. Define the extraction target when effects are involved.** Pedalboard effects on the synth in the mix raise two questions:
  - Is the target the dry or the wet synth? A dry target means the extractor also removes reverb. A wet target means the inverter sees
    reverb tails and can read them as release.
  - V6's parameter vector includes Surge chorus and delay mix, and `bank_v5_s0` was rendered with effects off.

  Suggestion:
  - Target: the dry Surge render with effects off.
  - Mixture: that render through a random Pedalboard chain, plus the other stems.
  - Surge's own effect parameters: held fixed or removed from the vector.

  Write the choice into the spec.
- **D4. Static and dynamic parameters need splitting, or the output cannot be identified.**
  - A free 40 × 59 trajectory can explain a filter envelope as automation and automation as an envelope.
  - Predict three things separately:
    - a static patch per clip, with all categorical parameters static;
    - a few automation lanes at the latent rate: cutoff, resonance, drive, and perhaps oscillator mix or FM depth;
    - the envelopes, as static parameters.
  - Draw training automation from a distribution slower than envelope times (for example, no features shorter than about 250 ms).
  - Test the split directly: a filter envelope, a cutoff sweep and both together, each rendered with known parameters.
  - Export: `audio_utils.py:254` already writes Surge's native `.fxp`. Binding each lane to a Surge macro and writing the lanes as MIDI CC
    in a `.mid` file works in any DAW. That is simpler than `.vstpreset` plus host-specific automation.
- **D5. Notes are missing from the architecture.** Both the DAW export and the groove-preserved augmentation (section 2.2) need note events:
  pitch, onset, length, velocity, and slide and accent for 303 lines. "Parse the note events" from an audio stem means transcription.
  - Name the transcriber.
  - Measure its error on Surge renders whose notes are known.
  - Feed its output to the inverter, which is conditioned on `midi_note` in V6 (`CONDITION_PARAMS`).
- **D6. The synthetic-to-real gap.** If the extractor's targets are always Surge re-renders, it learns to "find the part that sounds like
  Surge". Real tracks use other synths and hardware 303s.
  - The archive stems can be extraction targets as they are: the extractor needs no parameters.
  - Mix real targets with Surge targets.
  - Only the inverter needs Surge ground truth.

  This is also the answer to the earlier worry about the professional sonic print: the real stems carry it.
- **D7. Hit replacement on full drum stems.**
  - In a full drum stem the hits overlap: kick tails run under hats and claps. Replacing at transients leaves residue.
  - Swap single hits only in the isolated kick stems, and swap full drum stems as whole loops.
  - Define "self-similar" (for example, nearest neighbors in an embedding).
  - The archive bass stems were likely exported with their original ducking. Ducking that is carried in the audio stays consistent only
    while kick positions are kept, which the spec does keep. Re-key the ducking from the new kick for Surge re-renders, which have none.
- **D8. Evaluation and gates.**
  - Split by song: hold out at least six of the 40 songs completely, drums included. Otherwise the same stems appear on both sides.
  - "Beat Demucs by 2 dB on our synthetic mixtures" favors the in-domain model by construction. The hypothesis is "asymmetric beats
    symmetric", so it needs a matched comparison:
    - the same network trained two-stem (synth and the rest) on the same data;
    - BS-RoFormer's bass output as a second off-the-shelf baseline.
  - Gate Phase 1 on the separation tax on inversion: parameter error and re-render Mel-SSIM from the V6 inverter, on extracted versus clean
    stems. Keep SI-SDR as a diagnostic. This answers the spec's question to CONTINUITY.
  - "Zero parameter degradation in contested bins" cannot be measured. Replace it with band-limited (40–150 Hz) error in frames with the
    kick on versus off.
  - Pre-register n, a paired test and a kill condition, as the V7 spec did. Run the registered design, not a smaller one (CONTINUITY's audit).
- **D9. ModularOptimizer on a convolutional U-Net (the spec's question to WINTERMUTE).** Read in code, not run:
  - `routing.py` sends every parameter that is not 2-D to the sign group (`routing.py:138-150`). `optimizer.py:647` falls back to sign for
    anything else that is not 2-D.
  - All Conv2d kernels (4-D) of a U-Net would therefore get sign updates and none would be spectral.
  - Add a reshape path, `(out, in·kh·kw)` as in common Muon implementations, before using it on a convolutional extractor. Depthwise
    kernels can stay sign.
  - Since October 27, `strict_group_lrs` refuses one lr for all groups. Give per-group lrs or pass `--allow-uniform-lr`.
- **D10. Unmeasured costs.** "About 1/3/4 GPU hours" is a guess. Run a 200-step timing test, including Pedalboard and Surge throughput in
  the dataloader on 12 CPU workers.

## Run first (no training, CPU or one evening)

- **R1. Contested-bin census on the archive.**
  - For each song: take kick onsets from the kick stem, then measure bass, acid and lead energy within ±30 ms of each kick, in the sub
    (below 120 Hz) and body (120–2500 Hz) bands.
  - Also measure, in the body band and across the whole song, how much of the bass's energy is masked by the other synth stems
    (time-frequency cells where another stem is within 6 dB).
  - Report both per subgenre (old-school Goa, modern psytrance, acid). This says where the extractor's difficulty really is: under the
    kick, or among the other synths.
- **R2. Oracle repair: is the contested bin the bottleneck?**
  - Mixtures: real kick stems plus Surge renders of known patches that follow real bass grooves.
  - Separate them with Demucs and with BS-RoFormer.
  - Replace the separator output with the clean stem only in the contested time-frequency cells (kick-on frames, 40–150 Hz), then run V6.
  - Compare against clean. If the error falls to near clean, Pillar 2 is justified as the fix. If it does not, the damage is elsewhere
    (bleed, high band, phase), and greedy extraction or inpainting will not help.
- **R3. V7 Step 0 as registered.** 100 patches at three SNRs, kick stems included, grooved notes instead of single notes, with confidence
  intervals and top-1 retrieval computed.

## Smaller points

- Mark the unsupported outcome claims as goals:
  - "exact harmonic preservation";
  - "lossless stem audio ... no phase smearing";
  - "recreates the live, breathing automation".
- On the spec's question about a causal transformer for the 10 Hz predictor: inversion is offline, so the whole clip is known and a
  non-causal sequence model loses nothing. Keep the V6 flow head and condition it on a temporal encoder. Only the output rate changes.
- Section 2.1 gives absolute archive paths. Leave them out if this spec is ever mirrored to the site: they are on the publish leak list.
- The Point-and-Play author list still differs between the sidecar and `papers/knowledge.md` (CONTINUITY's addendum).
- Route decisions to WINTERMUTE, who owns the line (OWNERSHIP.md).

## Addendum: the block-based predictor, and what the V4–V6 results predict for it

The block predictor is worth building. Today each note is inverted from a 0.8 s render in isolation, and the per-note answers are
reconciled by median and mode (`eval_real_stems_consensus_v6.py`). A sequence model that sees the whole phrase accumulates evidence
across notes instead of voting.

- **A block is about one note.** At Goa tempos a sixteenth lasts about 100 ms (107 ms at 140 BPM, 103 ms at 145 BPM). An SA3 latent
  frame is 92.9 ms.
  - Free per-block parameters are therefore per-note parameters, with the single-note problem back and room to jitter.
  - Block boundaries do not fall on note onsets.
  - Keep categorical parameters and envelopes static per clip. Let only a few lanes vary, with knots a beat or more apart or a
    smoothness penalty. Treat the latent rate as the render and evaluation grid.
- **Per-note brightness has static explanations.** Keytracking, velocity, the filter envelope and 303 accent all change brightness per
  note. A free cutoff lane absorbs all four and returns keytrack 0 plus a wiggly lane.
  - Extend Occam to lanes: flatten a lane when flattening it does not worsen the score.
  - Write the prior into the training data: automation slower than the envelopes, keytrack and velocity varied independently.
- **The training distribution is single-note shaped** (`surge_spec.py:15-19`, `render_bank_v6.py`):
  - items of 0.8 s: one note, then the note an octave up at 0.25 s;
  - note lengths of 180–450 ms;
  - notes from E1 to D3 only;
  - every render starts from a flushed synth.

  A sixteenth-note bassline (gates under 100 ms) is already outside the training range: `audio_utils.prepare_target` flags it as out of
  distribution. Phrase training fixes this, which is a real gain for V8. It also brings in what single notes never had:
  - legato and overlapping notes;
  - envelopes that have not finished releasing;
  - retrigger and glide behavior (the refinement script already tripped on retrigger state);
  - effect tails from earlier notes.
- **Some mitigations stop applying:**
  - The note-plus-octave second note and its librosa fallback.
  - Folding each note into E1–D3, which would break a phrase's intervals and glides. Shift whole phrases instead, or train on the real
    range.
  - The single pinned `midi_note`, which becomes a piano-roll condition.
- **The `temporal_asp` encoder pools time away.** The V4 A2 component was built for one static target. V8 needs a sequence encoder that
  keeps frames.
- **Notes come from transcription.** Muscriptor MIDI needed manual fixes and tempo rescaling (stems 04 and 21, `--midi_scale`). On an
  extracted stem from a full mix it will do worse, and a missed or misplaced note will show up as a jump in an automation lane.
- **Metrics:**
  - Phrase MSS did not track listening.
  - mel_ssim_dist did (within-stem median ρ +0.67, 22 of 24 stems), and so did the spectral centroid (18 of 21).
  - A per-frame centroid trajectory against the real stem is a natural, ear-aligned check for a cutoff lane.
  - The ladder idea transfers: a monotone sweep rendered inside one note should give a monotone lane (Spearman ρ, as the ladder gate
    does for static renders).
- **Carry these over:**
  - The 4 kHz scoring limit and the Lexi band order.
  - The measured run-to-run noise before any V8-against-V6 claim (the SJ2 replication: +0.042 fell to +0.030, p = 0.07).
  - The 24-stem listening test cannot rank five systems (Friedman p = 0.73), so a dynamic-automation claim needs ground truth. Project
    files with their MIDI and automation, where they survive, are the only real-music source of it.
- **Hold back DPO.** It narrowed the candidate spread (best-of-8 got worse), and later rounds over-optimized a reward that does not track
  listening (SJ2). Leave it out of V8 until a reward does.
