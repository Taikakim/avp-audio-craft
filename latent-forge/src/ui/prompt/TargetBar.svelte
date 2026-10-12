<script lang="ts">
  // Target bar, spec 4.5 item 1's first row. M4 must not depend on M5's
  // arrangement store (spec 12): every clip-shaped fact below is a PROP, never
  // read from a store this milestone does not own. M5 wires clipName, a2a,
  // clipHasLatent and the two callbacks once it exists; until then a caller
  // passes null/false and the bar reads exactly as it does for a fresh
  // generate.
  import { dragScale } from "../../lib/actions/dragScale";
  import SettingsPresetSelect from "./SettingsPresetSelect.svelte";
  import type { Target } from "../../lib/forge/types";
  import { HELP } from "../../lib/help/strings";
  import { RANGES } from "../../lib/sampling/scheduleRules";
  import { CLIP_OPS, targetTag, targetTagColorVar } from "./targetBar";

  interface Props {
    target: Target;
    clipName: string | null;
    lane: 0 | 1 | 2 | 3;
    a2a: { on: boolean; noise: number } | null;
    /** Declared so callers (M5, and M9's RENDER control) have somewhere to put it. Nothing in
     *  this component reads it: the only op-related disabling the spec defines is the RENDER
     *  control's (7.1), and that control is M9's. */
    clipHasLatent: boolean;
    onA2AToggle: (on: boolean) => void;
    onNoise: (v: number) => void;
    op: string | null;
    onOp: (op: string) => void;
  }
  let {
    target, clipName, lane, a2a, onA2AToggle, onNoise, op, onOp,
  }: Props = $props();

  const a2aOn = $derived(a2a?.on ?? false);
  const tag = $derived(targetTag(target, a2aOn));
  const tagColorVar = $derived(targetTagColorVar(tag, lane));
  const targetIsClip = $derived(target.kind === "clip");
  const name = $derived(
    target.kind === "none" ? "session" : target.kind === "clip" ? (clipName ?? target.id) : target.key,
  );

  function handleOp(e: Event): void {
    onOp((e.target as HTMLSelectElement).value);
  }
</script>

<div class="target-bar" data-help={HELP.targetBar}>
  <span
    class="tag"
    data-testid="target-tag"
    style="color: var({tagColorVar}); border-color: var({tagColorVar});"
  >{tag}</span>
  <span class="name" data-testid="target-name">{name}</span>
  <SettingsPresetSelect {target} />

  {#if targetIsClip}
    <div class="clip-row" data-testid="target-clip-row">
      <button
        type="button"
        class="a2a-toggle"
        class:on={a2aOn}
        data-testid="target-a2a-toggle"
        data-help={HELP.a2aToggle}
        onclick={() => onA2AToggle(!a2aOn)}
      >{a2aOn ? "A2A ON" : "A2A OFF"}</button>
      <span class="noise-label">NOISE</span>
      <input
        class="noise"
        type="number"
        step="0.01"
        data-testid="target-noise"
        data-help={HELP.a2aNoise}
        value={a2a?.noise ?? 0}
        use:dragScale={{
          min: RANGES.noise.min, max: RANGES.noise.max, value: a2a?.noise ?? 0, onValue: onNoise,
        }}
      />
      <select
        class="op"
        data-testid="target-op"
        data-help={HELP.opSelect}
        value={op ?? CLIP_OPS[0]}
        onchange={handleOp}
      >
        {#each CLIP_OPS as o (o)}
          <option value={o}>{o}</option>
        {/each}
      </select>
    </div>
  {/if}
</div>

<style>
  .target-bar {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }
  .tag {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.05em;
    padding: 1px 5px;
    border: 1px solid;
  }
  .name {
    font-size: 10px;
    color: var(--text);
    flex: 1 1 60px;
    min-width: 50px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .clip-row {
    display: flex;
    align-items: center;
    gap: 5px;
    flex-wrap: wrap;
    width: 100%;
  }
  .a2a-toggle {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text-dim);
    font-size: 10px;
    padding: 2px 6px;
    cursor: pointer;
  }
  .a2a-toggle.on {
    background: var(--purple-strong);
    border-color: var(--purple-strong);
    color: white;
  }
  .noise-label {
    font-size: 10px;
    color: var(--text-dim);
  }
  .noise {
    width: 52px;
    box-sizing: border-box;
    background: var(--panel2);
    color: var(--text);
    border: 1px solid var(--border);
    padding: 2px 4px;
    font-size: 11px;
    cursor: ew-resize;
  }
  .op {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text);
    font-size: 10px;
    padding: 2px 4px;
  }
</style>
