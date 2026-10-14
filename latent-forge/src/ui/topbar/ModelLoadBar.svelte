<script lang="ts">
  // Owner: WINTERMUTE (created 2026-10-13)
  // Top-bar model-load bar: GET /status `model_load`, polled by the jobs store. The fraction and
  // ETA are time-based on the last same-stage load, or this box's priors before the first one
  // (eval/forge/modelload.py); a stage with neither runs indeterminate with elapsed seconds only.
  import type { ModelLoad } from "../../lib/forge/types";

  let { load }: { load: ModelLoad } = $props();

  const pct = $derived(load.fraction === null ? null : Math.round(load.fraction * 100));
  const eta = $derived(
    load.eta_sec === null ? `${Math.round(load.elapsed_sec)}s`
      : load.eta_sec > 0 ? `ETA ~${Math.ceil(load.eta_sec)}s` : "finishing…",
  );
  const label = $derived(`${load.stage} ${load.stage_index}/${load.stage_count} · ${eta}`);
</script>

<div class="load" data-testid="model-load" title={`loading ${load.target}: ${label}`}>
  <span class="cap">LOADING</span>
  <div class="track" role="progressbar" aria-label="model load"
    aria-valuemin="0" aria-valuemax="100" aria-valuenow={pct ?? undefined}>
    {#if pct === null}
      <div class="fill indet"></div>
    {:else}
      <div class="fill" style:width={`${pct}%`}></div>
    {/if}
  </div>
  <span class="txt">{label}</span>
</div>

<style>
  .load { display: flex; align-items: center; gap: 6px; flex-shrink: 0; min-width: 0; }
  .cap { color: var(--text-dim); font-size: 10px; }
  .track {
    position: relative; width: 90px; height: 6px; overflow: hidden;
    background: var(--panel2); border: 1px solid var(--border);
  }
  .fill { height: 100%; background: var(--turq-strong); transition: width 0.9s linear; }
  .fill.indet { position: absolute; width: 30%; animation: slide 1.2s ease-in-out infinite; }
  .txt { color: var(--text); font-size: 10px; white-space: nowrap; }
  @keyframes slide { from { left: -30%; } to { left: 100%; } }
</style>
