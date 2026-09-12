<script lang="ts">
  import { project } from "./store.svelte";

  function fmt(sec: number) {
    const m = Math.floor(sec / 60);
    const s = (sec % 60).toFixed(2).padStart(5, "0");
    return `${m}:${s}`;
  }
</script>

<div class="transport">
  <button onclick={() => (project.playing ? project.pause() : project.play())} class="primary">
    {project.playing ? "Pause" : "Play"}
  </button>
  <button onclick={() => project.stop()}>Stop</button>
  <span class="time">{fmt(project.playheadSec)}</span>

  <span class="spacer"></span>

  <span class="server" class:ok={!project.serverError} class:err={!!project.serverError}>
    {#if project.serverError}
      server: {project.serverError}
    {:else if project.serverInfo}
      {project.serverInfo.model} @ {project.serverInfo.sample_rate}Hz
      {#if project.serverStatus?.busy}· rendering…{/if}
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
    padding: 8px 12px;
    background: var(--panel-bg);
    border-radius: 6px;
  }
  button {
    background: var(--btn-bg);
    border: 1px solid var(--border);
    color: var(--fg);
    padding: 6px 14px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
  }
  button.primary {
    background: var(--accent);
    color: var(--accent-fg);
    border-color: var(--accent);
  }
  .time {
    font-variant-numeric: tabular-nums;
    color: var(--fg-dim);
    font-size: 13px;
  }
  .spacer {
    flex: 1;
  }
  .server {
    font-size: 12px;
    color: var(--fg-dim);
  }
  .server.err {
    color: var(--warn);
  }
</style>
