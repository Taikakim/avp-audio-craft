<script lang="ts">
  // Spec 4.3: three rows, header unconstrained in height (Global Constraint —
  // only the 62px canvas is fixed).
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { view } from "../../lib/stores/view.svelte";
  import { addClip, scheduleStretch } from "../../lib/clips/lifecycle";
  import { dragScale } from "../../lib/actions/dragScale";
  import { CHAIN_DEFAULTS } from "../../lib/forge/defaults";
  import { deepEqual } from "../../lib/forge/nonDefault";
  import { HELP } from "../../lib/help/strings";
  import { bpmTargetClip, laneCountLabel, parseForgeRefPayload } from "../../lib/math/laneHeader";
  import { playback } from "../../lib/stores/transport.svelte";
  import { RULER_GUTTER_PX } from "../../lib/timelineLayout";
  import type { ForgeLane } from "../../lib/forge/types";

  interface Props {
    lane: ForgeLane;
  }
  let { lane }: Props = $props();

  const laneClips = $derived(arrangement.clips.filter((c) => c.lane === lane.index));
  const countLabel = $derived(laneCountLabel(laneClips));
  const chainActive = $derived(!deepEqual(lane.chain, CHAIN_DEFAULTS));
  // arrangement (Task 1) has no `selectedClip` -- selection is chrome state
  // (view.svelte.ts, M1 T7), a Target union keyed by clip id. Resolve it
  // against arrangement.clips here rather than inventing a second selection
  // concept on the arrangement store.
  const selectedClip = $derived.by(() => {
    const sel = view.selection;
    return sel.kind === "clip" ? arrangement.clips.find((c) => c.id === sel.id) : undefined;
  });
  const bpmClip = $derived(bpmTargetClip(laneClips, selectedClip, lane.index));
  const isTarget = $derived(arrangement.targetLane === lane.index);
  const isActive = $derived(view.activeLane === lane.index);

  function activate() {
    view.activeLane = lane.index;
  }

  // I1 fix wave: a CLIP BPM/DETUNE edit must re-arm the debounced stretch
  // (lifecycle.ts's scheduleStretch) -- arrangement.setClipBpm/setDetune only
  // update the store's numbers, they never touch previewAudio themselves.
  function setClipBpm(id: string, bpm: number) {
    arrangement.setClipBpm(id, bpm);
    scheduleStretch(id);
  }

  function setClipDetune(id: string, cents: number) {
    arrangement.setDetune(id, cents);
    scheduleStretch(id);
  }

  // I1 fix wave: routed through lifecycle.ts's addClip (upload/analyze/stretch)
  // instead of calling arrangement.addClip directly -- see Timeline.svelte's
  // onLaneBodyDrop for the same fix and why it matters.
  async function onDrop(e: DragEvent) {
    e.preventDefault();
    const raw = e.dataTransfer?.getData("application/x-forge-ref");
    const ref = raw ? parseForgeRefPayload(raw) : null;
    if (!ref) return;
    const { clip } = await addClip({ lane: lane.index, startSec: playback.playheadSec, ref, durationSec: 4 });
    view.activeLane = lane.index;
    view.select({ kind: "clip", id: clip.id });
  }
</script>

<div
  class="header"
  class:active={isActive}
  style="width: {RULER_GUTTER_PX}px; flex: 0 0 {RULER_GUTTER_PX}px; border-left-color: var(--lane{lane.index + 1})"
  data-help={HELP.laneHeader}
  onclick={activate}
  role="button"
  tabindex="0"
  onkeydown={(e) => (e.key === "Enter" || e.key === " ") && activate()}
>
  <div class="row identity">
    <span class="chip" style="background: var(--lane{lane.index + 1})"></span>
    <span class="name">{lane.name}</span>
    <span class="count" style="color: var(--lane{lane.index + 1})">{countLabel}</span>
    <button
      class:active={lane.solo}
      onclick={(e) => {
        e.stopPropagation();
        arrangement.toggleSolo(lane.index);
      }}>S</button
    >
    <button
      class:active={lane.muted}
      onclick={(e) => {
        e.stopPropagation();
        arrangement.toggleMute(lane.index);
      }}>M</button
    >
    <span class="dot" class:lit={chainActive} style="--dot-color: var(--lane{lane.index + 1})"></span>
  </div>

  <div
    class="row slot"
    role="group"
    aria-label="drop target: add a clip at the playhead"
    data-help={HELP.laneDropSlot}
    ondragover={(e) => e.preventDefault()}
    ondrop={onDrop}
  >
    drop to add clip at playhead
  </div>

  <div class="row settings">
    <button
      class="target"
      class:active={isTarget}
      data-help={HELP.laneTarget}
      onclick={(e) => {
        e.stopPropagation();
        arrangement.setTargetLane(isTarget ? null : lane.index);
      }}>TARGET</button
    >
    <span class="label">CLIP BPM</span>
    <input
      type="number"
      step="0.1"
      disabled={!bpmClip}
      value={bpmClip?.native_bpm ?? 0}
      data-help={HELP.clipBpm}
      onclick={(e) => e.stopPropagation()}
      onchange={(e) => bpmClip && setClipBpm(bpmClip.id, +(e.target as HTMLInputElement).value || 0)}
      use:dragScale={{
        min: 60, max: 200, value: bpmClip?.native_bpm ?? 0,
        onValue: (v) => bpmClip && setClipBpm(bpmClip.id, v),
      }}
    />
    <span class="label">DETUNE ¢</span>
    <input
      type="number"
      step="1"
      disabled={!bpmClip}
      value={bpmClip?.detune_cents ?? 0}
      data-help={HELP.clipDetune}
      onclick={(e) => e.stopPropagation()}
      onchange={(e) => bpmClip && setClipDetune(bpmClip.id, +(e.target as HTMLInputElement).value || 0)}
      use:dragScale={{
        min: -100, max: 100, int: true, value: bpmClip?.detune_cents ?? 0,
        onValue: (v) => bpmClip && setClipDetune(bpmClip.id, v),
      }}
    />
  </div>
</div>

<style>
  .header {
    box-sizing: border-box;
    padding: 5px 8px;
    border-right: 1px solid var(--border);
    border-left: 4px solid;
    display: flex;
    flex-direction: column;
    gap: 4px;
    cursor: pointer;
    background: transparent;
  }
  .header.active {
    background: var(--panel2);
  }
  .row {
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .identity .chip {
    display: inline-block;
    width: 10px;
    height: 10px;
    flex-shrink: 0;
  }
  .identity .name {
    font-size: 11px;
    font-weight: 600;
    color: var(--text);
  }
  .identity .count {
    font-size: 10px;
    margin-left: auto;
  }
  .identity button {
    width: 16px;
    height: 16px;
    padding: 0;
    font-size: 9px;
    background: var(--panel);
    border: 1px solid var(--border);
    color: var(--text-dim);
    cursor: pointer;
    font-family: inherit;
  }
  .identity button.active {
    background: var(--turq-strong);
    border-color: var(--turq-strong);
    color: var(--panel);
  }
  .dot {
    width: 6px;
    height: 6px;
    border: 1px solid var(--border);
    flex-shrink: 0;
  }
  .dot.lit {
    background: var(--dot-color);
    border-color: var(--dot-color);
  }
  .slot {
    height: 20px;
    background: var(--panel2);
    border: 1px dashed var(--border);
    justify-content: center;
    font-size: 9px;
    color: var(--text-dim);
  }
  .header.active .slot {
    border-color: var(--turq-strong);
  }
  .settings button.target {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-dim);
    font-size: 9px;
    padding: 1px 5px;
    cursor: pointer;
    font-family: inherit;
  }
  .settings button.target.active {
    background: var(--warm);
    border-color: var(--warm);
    color: white;
  }
  .settings .label {
    font-size: 10px;
    color: var(--text-dim);
  }
  .settings input {
    width: 46px;
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text);
    font-size: 11px;
    padding: 2px 4px;
    cursor: ew-resize;
    font-family: inherit;
  }
  .settings input:disabled {
    opacity: 0.5;
    cursor: default;
  }
</style>
