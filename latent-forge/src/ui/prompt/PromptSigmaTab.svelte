<script lang="ts">
  // The tab assembly (spec 4.5): Task 8's target bar, Task 9's prompt and model-stage
  // columns, and this task's sigma column, stacked in the 162px body M1 T11 reserved for
  // the `prompt` bottom tab. Every clip-shaped fact is a prop with a safe default -- M5's
  // arrangement store does not exist yet, so a caller that passes nothing gets exactly the
  // fresh-generate reading, same as Task 8's TargetBar taken alone. `target` itself comes
  // from `view.selection` (an M1 store every milestone reads, not M5's), matching M1 T12's
  // own RightPaneModules.svelte precedent.
  import { LENGTH_CAP_SEC } from "../../lib/forge/defaults";
  import { settings } from "../../lib/stores/settings.svelte";
  import { view } from "../../lib/stores/view.svelte";
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
    clipName = null, lane = 0, a2a = null, clipHasLatent = false,
    onA2AToggle = () => {}, onNoise = () => {}, op = null, onOp = () => {},
  }: Props = $props();

  const target = $derived(view.selection);

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
      {target} {clipName} {lane} {a2a} {clipHasLatent}
      {onA2AToggle} {onNoise} {op} {onOp}
    />
    <PromptColumn {target} />
  </div>
  <div class="col-fixed" data-col="model-stage">
    <ModelStageColumn {target} {length} {onLength} />
  </div>
  <div class="col" data-col="sigma">
    <SigmaColumn {target} {length} {a2a} />
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
