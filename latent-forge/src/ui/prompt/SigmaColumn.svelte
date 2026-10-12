<script lang="ts">
  // Spec 4.5 item 3: SIGMA label, graph label, LatCH slot legend, the sigma canvas. This
  // component is the ONLY caller of `scheduleClient.request()` in the milestone (Task 4 owns
  // the client itself, as a singleton) and the one place that turns the selected target's own
  // settings plus the tab's LENGTH into a ScheduleRequest -- Task 11's ADVANCED SAMPLING reads
  // the same client's result and never requests. M4 has no lane-chain store (M7's), so `slots`
  // arrives as a prop with a safe empty default, the same pattern Task 8's TargetBar uses for
  // `a2a`.
  import type { LatchSlot, Target } from "../../lib/forge/types";
  import { scheduleClient } from "../../lib/sampling/scheduleClient.svelte";
  import { chartableSigmaMax, sigmaMaxFor } from "../../lib/sampling/sigmaMax";
  import type { SigmaGraphInput } from "../../lib/sampling/sigmaGraph";
  import { settings } from "../../lib/stores/settings.svelte";
  import SigmaGraph from "./SigmaGraph.svelte";
  import {
    buildScheduleRequest, SIGMA_GRAPH_HEIGHT, SIGMA_GRAPH_WIDTH,
    sigmaNote, slotLegendLabel,
  } from "./sigmaColumn";

  interface Props {
    target: Target;
    length: number;
    a2a: { on: boolean; noise: number } | null;
    slots?: readonly LatchSlot[];
  }
  let { target, length, a2a, slots = [] }: Props = $props();

  // No dispose() on unmount: `scheduleClient` is a module singleton shared with Task 11's
  // ADVANCED SAMPLING, and dispose() is permanent (it sets #disposed, so every later
  // request() is ignored). Closing the PROMPT + SIGMA tab must not leave the right-pane
  // module reading a client that can never answer again. The client's own
  // abort-and-supersede handles the only thing dispose() was doing here: a request left in
  // flight is aborted the moment the next one is made.
  const client = scheduleClient;

  const current = $derived(settings.current(target));
  // Reading `current.schedule` (the reference) would not rerun this when Task 11 mutates a
  // field of it in place via settings.patchSchedule -- the $state proxy rule bites here.
  // Spreading reads every own field individually, which IS tracked.
  const scheduleSnapshot = $derived<typeof current.schedule>({ ...current.schedule });
  const sigmaMax = $derived(sigmaMaxFor(a2a));
  const chartable = $derived(chartableSigmaMax(sigmaMax));

  $effect(() => {
    if (chartable === null) return;
    client.request(
      buildScheduleRequest(current.steps, length, chartable, current.sampler_type, scheduleSnapshot),
    );
  });

  const graphInput = $derived<SigmaGraphInput | null>(
    client.result === null
      ? null
      : {
          sigmas: client.result.sigmas,
          steps: client.result.steps,
          cfgLo: current.cfg_interval_progress[0],
          cfgHi: current.cfg_interval_progress[1],
          stepped: current.schedule.stepped,
          scalePhi: current.scale_phi,
          slots,
          width: SIGMA_GRAPH_WIDTH,
          height: SIGMA_GRAPH_HEIGHT,
        },
  );

  const note = $derived(sigmaNote(client.error, client.staleShape, current.schedule, current.sampler_type));
</script>

<!-- No `data-col="sigma"` here: PromptSigmaTab's own wrapper carries it, and Playwright's
     strict mode fails a locator that matches two elements. The column marker belongs to
     whoever places the column, not to the column itself. -->
<div class="sigma-column">
  <div class="header">
    <span class="label">SIGMA</span>
    <span class="shape">{current.schedule.shape}</span>
    <span class="legend" data-testid="sigma-slot-0" style="color: var(--slot1);">
      {slotLegendLabel(slots[0])}
    </span>
    <span class="legend" data-testid="sigma-slot-1" style="color: var(--slot2);">
      {slotLegendLabel(slots[1])}
    </span>
  </div>
  <SigmaGraph input={graphInput} note={note} pending={client.pending} error={client.error} />
</div>

<style>
  .sigma-column {
    flex: 1 1 260px;
    min-width: 0;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
  .header {
    display: flex;
    align-items: baseline;
    gap: 6px;
    margin-bottom: 2px;
  }
  .label {
    color: var(--text-dim);
    font-size: 10px;
    letter-spacing: 0.06em;
  }
  .shape {
    font-size: 10px;
    color: var(--turq-strong);
  }
  .legend {
    font-size: 10px;
  }
</style>
