<script lang="ts">
  // The tab assembly (spec 4.5): Task 8's target bar, Task 9's prompt and model-stage
  // columns, and this task's sigma column, stacked in the 162px body M1 T11 reserved for
  // the `prompt` bottom tab. Every clip-shaped fact is a prop with a safe default -- M5's
  // arrangement store does not exist yet, so a caller that passes nothing gets exactly the
  // fresh-generate reading, same as Task 8's TargetBar taken alone. `target` itself comes
  // from `view.selection` (an M1 store every milestone reads, not M5's), matching M1 T12's
  // own RightPaneModules.svelte precedent.
  import { LENGTH_CAP_SEC } from "../../lib/forge/defaults";
  import type { ClipOp } from "../../lib/forge/types";
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { settings } from "../../lib/stores/settings.svelte";
  import { view } from "../../lib/stores/view.svelte";
  import InlineError from "./InlineError.svelte";
  import ModelStageColumn from "./ModelStageColumn.svelte";
  import PromptColumn from "./PromptColumn.svelte";
  import SigmaColumn from "./SigmaColumn.svelte";
  import TargetBar from "./TargetBar.svelte";

  interface Props {
    clipName?: string | null;
    lane?: 0 | 1 | 2 | 3;
    a2a?: { on: boolean; noise: number } | null;
    clipHasLatent?: boolean;
    onA2AToggle?: (on: boolean) => void;
    onNoise?: (v: number) => void;
    op?: string | null;
    onOp?: (op: string) => void;
  }
  let {
    clipName = null, lane, a2a, clipHasLatent,
    onA2AToggle, onNoise, op, onOp,
  }: Props = $props();

  const target = $derived(view.selection);

  // M7 T9: the active lane's LatCH slots for the sigma graph's slot lanes -- only while that lane's
  // LATCH GUIDANCE is on (M4 plan line 1982: the caller passes slots when there is something to draw).
  // Unfiltered by the head registry, unlike RightPaneModules' `activeLatch`: here it only decides
  // what is DRAWN, so a deleted head can at worst draw one lane that will not be sent (Open questions 28).
  const latchSlots = $derived.by(() => {
    const chain = arrangement.lanes[view.activeLane].chain;
    return chain.latch_on ? chain.slots : [];
  });

  // M7 T9 (critic follow-up #2): the selected clip, read from M5's store -- never seeded.
  const clip = $derived.by(() => {
    const sel = view.selection;
    return sel.kind === "clip" ? (arrangement.clips.find((c) => c.id === sel.id) ?? null) : null;
  });

  /** A2A on/off through M5 (T1 `ensureA2A(id)`: creates {on: true, noise, envelope} once, a no-op
   *  if the clip already has one), then the flag in place (Global Constraint #1). */
  function toggleA2A(on: boolean): void {
    const c = clip;
    if (!c) return;
    if (on) arrangement.ensureA2A(c.id);
    if (c.a2a) c.a2a.on = on;
  }

  function setClipNoise(v: number): void {
    if (clip) arrangement.setNoise(clip.id, v);   // M5 T1: rescales the envelope proportionally
  }

  const barLane = $derived(lane ?? clip?.lane ?? 0);
  const barA2A = $derived(a2a !== undefined ? a2a : clip?.a2a ? { on: clip.a2a.on, noise: clip.a2a.noise } : null);
  // "has a latent" = one exists at all; staleness is informational only (spec §7.3).
  const barHasLatent = $derived(clipHasLatent ?? (clip ? clip.latentState !== "none" : false));
  const barOnA2AToggle = $derived(onA2AToggle ?? toggleA2A);
  const barOnNoise = $derived(onNoise ?? setClipNoise);

  // M9 T6: the clip's OP (7.1 row 3), sourced like the five above -- a passed prop still wins.
  function setClipOpFromBar(next: string): void {
    if (clip) arrangement.setClipOp(clip.id, next as ClipOp);
  }
  const barOp = $derived(op ?? clip?.op ?? null);
  const barOnOp = $derived(onOp ?? setClipOpFromBar);

  // LENGTH is settings.duration_sec, and this component is its single owner: Task 9's column
  // displays it and Task 10's sigma column sends it as /schedule's `duration`, so exactly one
  // place reads the store and writes it back. It is PER TARGET -- selecting another clip shows
  // that clip's own length (spec 9.3: a render preset recalls every txt2audio parameter).
  const length = $derived(settings.current(target).duration_sec);
  function onLength(sec: number): void {
    settings.patch(target, { duration_sec: Math.min(LENGTH_CAP_SEC, sec) });
  }
</script>

<div class="prompt-sigma-tab" data-tab-body="prompt">
  <div class="col" data-col="prompt">
    <TargetBar
      {target} {clipName} lane={barLane} a2a={barA2A} clipHasLatent={barHasLatent}
      onA2AToggle={barOnA2AToggle} onNoise={barOnNoise} op={barOp} onOp={barOnOp}
    />
    <InlineError targetKey={view.selectionKey} />
    <PromptColumn {target} />
  </div>
  <div class="col-fixed" data-col="model-stage">
    <ModelStageColumn {target} {length} {onLength} />
  </div>
  <div class="col" data-col="sigma">
    <SigmaColumn {target} {length} a2a={barA2A} slots={latchSlots} />
  </div>
</div>

<style>
  .prompt-sigma-tab {
    box-sizing: border-box;
    height: 100%;
    width: 100%;
    display: flex;
    flex-wrap: nowrap;
    gap: 10px;
    align-items: stretch;
    min-height: 0;
    overflow-x: auto;
  }
  .col {
    flex: 1 1 250px;
    min-width: 186px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-height: 0;
  }
  .col-fixed {
    flex: 0 0 auto;
    min-width: 0;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
</style>
