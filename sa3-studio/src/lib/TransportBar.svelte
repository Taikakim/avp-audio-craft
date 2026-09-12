<script lang="ts">
  import { formatBarsBeats, formatClock, frameAt } from "./musictime";
  import { project } from "./store.svelte";

  let fileInput = $state<HTMLInputElement>();
  let notice = $state<string | null>(null);

  function saveProject() {
    const blob = new Blob([project.toJSON()], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `sa3-studio-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "")}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function loadProject(e: Event) {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;
    try {
      const { relinkNeeded } = project.loadJSON(await file.text());
      notice = relinkNeeded
        ? `loaded — ${relinkNeeded} clip(s) need audio relinked (local files don't survive a save)`
        : "loaded";
    } catch (err) {
      notice = `load failed: ${err instanceof Error ? err.message : String(err)}`;
    }
    (e.target as HTMLInputElement).value = "";
    setTimeout(() => (notice = null), 6000);
  }
</script>

<div class="transport">
  <button onclick={() => project.togglePlay()} class="primary">
    {project.playing ? "❚❚ PAUSE" : "▶ PLAY"}
  </button>
  <button onclick={() => project.stop()}>■ STOP</button>

  <div class="readout">
    <span class="big">{formatClock(project.playheadSec)}</span>
    <span class="sub">bar {formatBarsBeats(project.playheadSec, project.meter)} · frame {frameAt(project.playheadSec)}</span>
  </div>

  <span class="spacer"></span>

  {#if notice}
    <span class="notice">{notice}</span>
  {/if}
  <button onclick={saveProject} title="save the arrangement as JSON">SAVE</button>
  <button onclick={() => fileInput?.click()} title="load an arrangement">LOAD</button>
  <input bind:this={fileInput} type="file" accept="application/json" onchange={loadProject} hidden />

  <span class="server" class:err={!!project.serverError}>
    {#if project.serverError}
      offline
    {:else if project.serverInfo}
      {project.serverInfo.model}{project.serverStatus?.busy ? " · busy" : ""}
    {:else}
      connecting…
    {/if}
  </span>
</div>

<style>
  .transport {
    display: flex;
    align-items: center;
    gap: 8px;
    height: 42px;
    padding: 0 12px;
    background: var(--panel-bg);
    border: 1px solid var(--border);
  }
  button {
    background: var(--btn-bg);
    border: 1px solid var(--border);
    color: var(--fg);
    padding: 5px 12px;
    cursor: pointer;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    font-family: inherit;
  }
  button.primary {
    background: var(--accent);
    color: var(--accent-fg);
    border-color: var(--accent);
  }
  .readout {
    display: flex;
    flex-direction: column;
    line-height: 1.15;
    font-variant-numeric: tabular-nums;
  }
  .big {
    font-size: 13px;
    color: var(--fg);
  }
  .sub {
    font-size: 9px;
    color: var(--fg-dim);
  }
  .spacer {
    flex: 1;
  }
  .notice {
    font-size: 10px;
    color: var(--green);
  }
  .server {
    font-size: 10px;
    color: var(--fg-dim);
    letter-spacing: 0.04em;
  }
  .server.err {
    color: var(--warn);
  }
</style>
