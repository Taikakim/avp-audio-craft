#!/usr/bin/env node
// Pull every data-help string out of the design handoff and emit
// latent-forge/src/lib/help/strings.ts (spec §9.4).
//
// The keys are held here, in document order, each pinned to the source line it
// came from. That is deliberate: deriving a key from nearby markup would be
// silent and wrong the first time the drawing is touched, whereas a pinned line
// makes the script fail loudly and name the mismatch. Run it with:
//
//   cd latent-forge && npm run help:extract
//
// Nothing else reads the drawing at build time; strings.ts is committed.

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..", "..");
const SOURCE = resolve(REPO, "docs/sa3-studio/design_handoff/SA3 Studio v3.dc.html");
const OUT = resolve(REPO, "latent-forge/src/lib/help/strings.ts");

// ---------------------------------------------------------------- the 80 keys
// [id, source line]. Order is document order. Two entries share line 392: the
// SEED field and the RND button beside it.
const KEYS = [
  ["session", 27],
  ["model", 32],
  ["modelFolder", 37],
  ["masterPreset", 40],
  ["renderButton", 45],
  ["helpToggle", 49],
  ["masterStrip", 68],
  ["projectBpm", 88],
  ["snapMode", 90],
  ["matchBpm", 96],
  ["matchDownbeats", 98],
  ["zoomHint", 99],
  ["ruler", 108],
  ["laneHeader", 114],
  ["laneDropSlot", 120],
  ["laneTarget", 122],
  ["clipBpm", 124],
  ["clipDetune", 126],
  ["mixFold", 216],
  ["mixOrder", 218],
  ["mixNodeT", 248],
  ["signalPath", 262],
  ["mixExpand", 274],
  ["chromaMatchMarks", 292],
  ["chromaChord", 323],
  ["chromaMatchLegend", 330],
  ["chromaDetuneScan", 332],
  ["chromaBestCriterion", 335],
  ["chromaBest", 336],
  ["chromaHeatmap", 344],
  ["chromaMatchCurve", 346],
  ["targetBar", 358],
  ["promptPreset", 361],
  ["a2aToggle", 367],
  ["a2aNoise", 370],
  ["prompt", 373],
  ["negativePrompt", 374],
  ["modelStagePost", 381],
  ["modelStageBase", 382],
  ["steps", 385],
  ["cfg", 386],
  ["length", 391],
  ["seed", 392],
  ["seedRandom", 392],
  ["sigmaGraph", 404],
  ["sidePaneToggle", 436],
  ["overlapChromaXfade", 460],
  ["overlapOverride", 464],
  ["overlapSteps", 466],
  ["overlapCfg", 467],
  ["filesRow", 480],
  ["generationRenderButton", 490],
  ["modulePreset", 509],
  ["latchHead", 516],
  ["latchTargetKind", 519],
  ["latchTargetValue", 522],
  ["latchWeight", 523],
  ["latchStartPct", 524],
  ["latchEndPct", 525],
  ["latchRho", 529],
  ["latchMu", 530],
  ["latchGamma", 531],
  ["latchMeanIter", 532],
  ["latchLogNorms", 534],
  ["bungeeSemitones", 560],
  ["cfgLo", 570],
  ["cfgHi", 571],
  ["cfgUnit", 572],
  ["sampler", 576],
  ["scheduleShape", 581],
  ["scheduleRho", 585],
  ["lamMin", 588],
  ["lamMax", 589],
  ["sigmaMin", 590],
  ["sigmaMax", 591],
  ["stepped", 592],
  ["tilt", 593],
  ["plateaus", 594],
  ["rescale", 595],
  ["latentNormalise", 616],
];

// -------------------------------------------------- spec §9.4 rewrite list
// Exactly the fourteen the spec names. The original is emitted above each one
// as `// handoff: "..."`, so the divergence is always visible in review.
const REWRITES = {
  steps:
    "Number of denoising steps. More steps cost time and give diminishing returns. " +
    "Safe value: 8 for POST — the released checkpoints are distilled to sample in eight — " +
    "and 24 for BASE. Drag to scale; hold shift for 1/100th detail.",
  cfg:
    "Classifier-free guidance scale — how hard the prompt is enforced. Too high burns the " +
    "output and flattens dynamics. POST ignores it: guidance is distilled into the checkpoint, " +
    "so the field greys out and 1.0 is sent. Range 0–64. Safe value: 6.0 on BASE.",
  modelStagePost:
    "POST is the released, adversarially post-trained checkpoint: ping-pong in 8 steps on a " +
    "logSNR-uniform schedule and no CFG, because guidance is baked in during distillation. " +
    "It is the resident model here. Safe value: POST.",
  modelStageBase:
    "BASE is the flow-matching model before distillation: euler over about 24 steps with real " +
    "CFG. Switching stage reloads the backbone on the render server and takes roughly a minute, " +
    "so it asks before it does. Safe value: POST.",
  sampler:
    "Which sampler integrates the reverse diffusion. SA3 is rectified flow, so the list is " +
    "euler / rk4 / dpmpp / pingpong on BASE and pingpong / euler on POST; the k-diffusion " +
    "samplers are not offered. LatCH guidance forces euler while it is on. " +
    "Safe value: euler on BASE, pingpong on POST.",
  scheduleShape:
    "How sigma falls across the steps. MODEL is the checkpoint's own schedule and the safe " +
    "default; LOGSNR is uniform in log-SNR, which is what the released checkpoints ship with; " +
    "GEOMETRIC is the backend's three-number ramp; LINEAR lingers at low noise, LOG spends more " +
    "steps on detail, EXPONENTIAL more on structure, COSINE is a smooth S. Every shape but " +
    "MODEL reaches the server as an explicit sigma array. STEPPED beside PLATEAUS holds any of " +
    "these shapes in plateaus and jumps down between them. Safe value: MODEL.",
  sigmaMin:
    "The noise level the schedule ends at, in unitless multiples of the latent's standard " +
    "deviation. Range 0.001–0.5, and it must stay below σ MAX. Only the sigma shapes use it — " +
    "MODEL and LOGSNR take λ MIN / λ MAX instead. Safe value: 0.01. " +
    "Drag to scale; hold shift for 1/100th detail.",
  sigmaMax:
    "The noise level the schedule starts from, as a unitless multiple of the latent's own " +
    "standard deviation. Latent Forge reads it from the checkpoint rather than offering it as a " +
    "free field: the render server reports the model's own σ MAX with the schedule and the graph " +
    "is drawn from that. Shown here for reference.",
  a2aNoise:
    "Init noise level — how much of the clip is destroyed before re-denoising. Near 0 barely " +
    "changes it; at the top it is a fresh generation with only a hint of the source. The range " +
    "here is 0–1 throughout: SA3 is rectified flow, so the far wider v/eps noise scale does not " +
    "apply. Safe value: 0.4. Drag to scale.",
  length:
    "Requested duration. This is not just a buffer size — SA3 conditions on it through both " +
    "cross-attention and AdaLN, and allocates a variable-length latent of " +
    "ceil((d + 6 s) · 44100 / 4096) embeddings, the trailing 6 s being silence padding that is " +
    "trimmed after generation. A forge pass is capped at 184 s, which is what the display card " +
    "holds; longer arrangements are built from several clips. Safe value: anything under 184 s. " +
    "Drag to scale.",
  latchWeight:
    "How much this slot contributes relative to the other. 0 disables the slot without " +
    "unloading it; past roughly 10 the head tends to dominate the prompt. The two slots are " +
    "summed, and the result applies to this lane's latent only. Safe value: 1.0.",
  latchRho:
    "Weight on the variance term of the LatCH guidance objective — how strongly the latent's " +
    "spread is pushed toward the head's target. High values wash out transients. This is a lane " +
    "chain setting, applied before the mix, so raising it on one lane leaves the others alone. " +
    "Safe value: 1.0.",
  latchMu:
    "Weight on the mean term — how strongly the latent's centre is moved toward the target. " +
    "This is the one that actually shifts the feature; raise it before ρ. Like ρ it belongs to " +
    "this lane's chain. Safe value: 1.0.",
  latchTargetKind:
    "Target kind. constant holds one value; ramp_up / ramp_down sweep it over the window; " +
    "beat_grid takes a BPM instead of a feature value. chroma_major and chroma_minor are not " +
    "offered here — chroma is matched against the TARGET lane in the CHROMA tab instead.",
  // Fix wave 2026-09-29 (finding #4): TopBar.svelte's live data-help had already drifted from
  // the generated string by an extra sentence -- reconciled here using the LIVE text as source
  // of truth, per the fix-wave instruction (what's on screen now is more likely what users saw).
  model:
    "Checkpoint used for generation, a2a, inpainting and the encode/decode round trip. The " +
    "first four entries are backbones and switching one rebuilds the model; the rest are " +
    "adapters and set the session's default checkpoint path.",
};

// ------------------------------------------------- controls the drawing lacks
const NEW_STRINGS = {
  transportPlay:
    "Play or pause the arrangement from the playhead. Space does the same from anywhere outside " +
    "a text field. Preview playback in the render container is separate: starting one stops the other.",
  transportStop:
    "Stop and leave the playhead where it is. Home rewinds it to zero.",
  transportLoop:
    "Loop the marked region instead of running on to the end of the arrangement — the fastest " +
    "way to hear whether a join actually lands.",
  // Fix wave 2026-09-29 (finding #4): TopBar.svelte's live data-help had diverged completely
  // from the generated string. Reconciled using the LIVE text as source of truth (same rationale
  // as `model` in REWRITES above -- it is what users have actually been shown).
  darkToggle:
    "Light or dark ground. The choice is kept in this browser. Canvases read their colours " +
    "from the theme, so the waveforms, the ruler and the sigma graph follow it too.",
  filmTarget:
    "The value the FiLM head steers this lane toward, in onsets per second. The GAIN beside it " +
    "scales how hard the conditioning is applied. Safe value: 4.0.",
  opSelect:
    "What RENDER does with the selected clip: A2A re-noises and re-denoises it at the noise " +
    "amount above, DECODE just runs its latent back through the decoder, BEND applies the latent " +
    "operations. The prompt and settings in this pane belong to whichever op is chosen.",
  previewMixdownToggle:
    "A/B the audio-domain preview mix against the committed mixdown. PREVIEW is what the " +
    "timeline sounds like now; MIXDOWN is what the server actually rendered. They should agree — " +
    "where they do not, the commit changed something the preview cannot see.",
  // Fix wave 2026-09-29 (finding #4): seven controls (MixdownSlot x2, PreviewContainer x5) were
  // built in Tasks 9-11, before this module existed, and carried their own inline data-help
  // literals that never got an entry here. Text below is taken verbatim from those live literals.
  mixdownCommit:
    "Mixes the four lanes in the latent domain and decodes the result — the commit that turns " +
    "the arrangement into audio. While it samples, the window border runs a C64 loader raster " +
    "bar whose sweep rate falls with the remaining step count.",
  mixdownWave:
    "The latest mixdown. Click to scrub it, and drag it onto a lane to use it as a clip. " +
    "Earlier mixdowns stay in the render history at the bottom of the screen.",
  previewRender:
    "Renders the current target with the settings in this pane. The result lands here to be " +
    "auditioned; drag it onto a lane if you want it.",
  previewHistory:
    "Every render of this session, newest first. Loading one plays it here — it does not " +
    "change the settings in this pane.",
  previewDragToLane:
    "Drag the previewed render onto a lane to add it as a clip at the drop position.",
  previewUseSettings:
    "Copies the settings the previewed render was made with into the current target. Loading " +
    "a render from HISTORY never does this on its own.",
  previewReplaceClip:
    "Swaps the selected clip's audio for the previewed render, keeping the previous audio in " +
    "the clip's history. Enabled only when the render was made from that clip.",
  latchToggle:
    "Turns LatCH guidance on for this lane. Both slots keep their settings while off; nothing is " +
    "unloaded. Safe value: off.",
  filmToggle:
    "Turns the FiLM density adapter on for this lane. Safe value: off.",
  filmPreset:
    "Module preset — recalls just this FiLM slot's settings.",
  filmScale:
    "How hard the FiLM conditioning is applied, scaling the head's own default gain. Safe value: 1.75, the server's default.",
  loraToggle:
    "Turns the resident LoRA/DORA adapter on for this lane. Safe value: off.",
  loraPreset:
    "Module preset — recalls just this LoRA/DORA slot's settings.",
  loraModel:
    "Which adapter to apply. Resident slots (already loaded, from /slots) are listed first because " +
    "switching to one is instant; anything else is loaded from disk on first use.",
  loraScale:
    "Adapter strength. Safe value: 1.0.",
  bungeeToggle:
    "Turns Bungee pitch-shifting on for this lane, applied during the Bungee stage before " +
    "re-encoding. Safe value: off.",
  bungeePreset:
    "Module preset — recalls just this Bungee slot's settings. Undrawn in the handoff; the level " +
    "exists in the frozen preset contract (spec §9.3, §6.3's level enum), so it needs a place to live.",
  filmCkpt:
    "Which FiLM checkpoint this lane uses. Server default is whatever /info reports as the film " +
    "default; anything else is loaded from the film model root on first use.",
  modulePresetSave:
    "Saves this module's current settings, on/off state included, as a module preset -- under the " +
    "selected name, or a new one you are asked for. Recall applies to the active lane only.",
  modulePresetDelete:
    "Deletes the selected module preset from the server. The lane's current settings are not changed.",
  masterLatchToggle:
    "Turns LatCH steering on for the mixed latent, after the lane chains. Safe value: off.",
  masterLatchHeadLabel:
    "Which head steers the mixed latent (spec §8.1 S8 -- the existing /steer math).",
  masterHead:
    "The LatCH head applied to the mix. Uses the same registry as the lane chains' slots.",
  masterGain:
    "How hard the head's gradient is applied to the mixed latent. Safe value: 64.",
  mixQuadWeight:
    "This lane's share of the weighted 4-way mix. All four are renormalised together; leaving " +
    "every one at zero mixes the lanes equally.",
  mixLerp:
    "Linear interpolation between this node's two inputs.",
  mixSlerp:
    "Spherical interpolation between this node's two inputs -- the default, since SAME's latent " +
    "space is strongly anisotropic and a straight lerp can cut through low-energy regions a slerp " +
    "arcs around.",
};

// ------------------------------------------------------------------ extract
function decodeEntities(s) {
  return s
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&");
}

const lines = readFileSync(SOURCE, "utf8").split(/\r?\n/);
const found = [];
lines.forEach((line, i) => {
  for (const m of line.matchAll(/data-help="([^"]*)"/g)) {
    found.push({ line: i + 1, text: decodeEntities(m[1]) });
  }
});

if (found.length !== KEYS.length) {
  console.error(
    `extract_help: the drawing now has ${found.length} data-help strings, the key table has ` +
      `${KEYS.length}. Reconcile KEYS in ${fileURLToPath(import.meta.url)} before regenerating.`,
  );
  process.exit(1);
}

const mismatched = [];
KEYS.forEach(([id, line], i) => {
  if (found[i].line !== line) mismatched.push(`${id}: expected line ${line}, found ${found[i].line}`);
});
if (mismatched.length) {
  console.error("extract_help: the drawing moved under the key table:\n  " + mismatched.join("\n  "));
  process.exit(1);
}

// -------------------------------------------------------------------- emit
const ids = [...KEYS.map(([id]) => id), ...Object.keys(NEW_STRINGS)];
const dupes = ids.filter((id, i) => ids.indexOf(id) !== i);
if (dupes.length) {
  console.error(`extract_help: duplicate ids ${dupes.join(", ")}`);
  process.exit(1);
}

const out = [];
out.push("// GENERATED by docs/latent-forge/extract_help.mjs -- do not edit by hand.");
out.push("// Source: docs/sa3-studio/design_handoff/SA3 Studio v3.dc.html (80 data-help strings).");
out.push("// Regenerate with `npm run help:extract` from latent-forge/.");
out.push("//");
out.push("// Spec §9.4: strings describing behaviour this backend does not have are rewritten, and");
out.push("// each one is preceded by a comment naming the original, tagged handoff: and quoted.");
out.push("");
out.push("export type HelpId =");
ids.forEach((id, i) => out.push(`  ${i === 0 ? "|" : "|"} ${JSON.stringify(id)}`));
out.push("  ;");
out.push("");
out.push("export const HELP: Record<HelpId, string> = {");
KEYS.forEach(([id], i) => {
  const original = found[i].text;
  const rewritten = Object.prototype.hasOwnProperty.call(REWRITES, id);
  if (rewritten) out.push(`  // handoff: ${JSON.stringify(original)}`);
  out.push(`  ${id}: ${JSON.stringify(rewritten ? REWRITES[id] : original)},`);
});
out.push("");
out.push("  // --- controls this build has that the drawing did not (spec §9.4).");
for (const [id, text] of Object.entries(NEW_STRINGS)) out.push(`  ${id}: ${JSON.stringify(text)},`);
out.push("};");
out.push("");

mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, out.join("\n"), "utf8");
console.log(`extract_help: wrote ${ids.length} strings (${KEYS.length} extracted, ${Object.keys(REWRITES).length} rewritten, ${Object.keys(NEW_STRINGS).length} new) to ${OUT}`);
