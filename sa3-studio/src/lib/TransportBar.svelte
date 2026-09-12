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
    {project.playing ? "❚❚ PAUSE" : "▶ PLAY"}
  </button>
  <button onclick={() => project.stop()}>■ STOP</button>
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
  .time {
    font-variant-numeric: tabular-nums;
    color: var(--fg-dim);
    font-size: 12px;
  }
  .spacer {
    flex: 1;
  }
  .server {
    font-size: 11px;
    color: var(--fg-dim);
  }
  .server.err {
    color: var(--warn);
  }
</style>
