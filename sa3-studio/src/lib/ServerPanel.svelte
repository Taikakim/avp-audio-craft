<script lang="ts">
  import { project } from "./store.svelte";

  let open = $state(true);

  // /status returns log_tail -- the last 20 lines of the server's own log ring.
  // The design handoff's TERMINAL panel showed invented lines; this one is the
  // real thing, already arriving on the 3s status poll.
  const tail = $derived(project.logTail);
</script>

<div class="panel">
  <button class="head" onclick={() => (open = !open)}>
    <span class="section-label">Server</span>
    <span class="dot" class:ok={!project.serverError} class:busy={project.serverStatus?.busy}></span>
    <span class="chev">{open ? "▾" : "▸"}</span>
  </button>

  {#if open}
    <div class="body">
      {#if project.serverError}
        <p class="err">{project.serverError}</p>
        <p class="hint">
          Start <code>eval/explorer_render_server.py</code> (port 8056), or point vite at it with
          <code>SA3_RENDER_SERVER</code>.
        </p>
      {:else if project.serverInfo}
        <dl>
          <dt>model</dt>
          <dd>{project.serverInfo.model}</dd>
          <dt>rate</dt>
          <dd>{project.serverInfo.sample_rate} Hz · {project.serverInfo.fps} fps</dd>
          <dt>max dur</dt>
          <dd>{project.serverInfo.max_duration_sec}s</dd>
          <dt>heads</dt>
          <dd>{project.serverInfo.latch_heads?.length ?? 0} LatCH</dd>
          <dt>ckpts</dt>
          <dd>{project.ckpts.length}</dd>
          <dt>presets</dt>
          <dd>{project.presets.length}</dd>
          <dt>state</dt>
          <dd>{project.serverStatus?.busy ? `busy — ${project.serverStatus.job_id}` : "idle"}</dd>
        </dl>
      {:else}
        <p class="hint">connecting…</p>
      {/if}

      {#if tail.length}
        <div class="term">
          {#each tail as line}
            <div class="line">{line}</div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .panel {
    background: var(--panel-bg);
    border: 1px solid var(--border);
  }
  .head {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    background: var(--panel2);
    border: none;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    font-family: inherit;
  }
  .section-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--fg-dim);
  }
  .dot {
    width: 7px;
    height: 7px;
    background: var(--red);
  }
  .dot.ok {
    background: var(--green);
  }
  .dot.busy {
    background: var(--warn);
  }
  .chev {
    margin-left: auto;
    color: var(--fg-dim);
    font-size: 10px;
  }
  .body {
    padding: 8px 10px;
  }
  dl {
    display: grid;
    grid-template-columns: 58px 1fr;
    gap: 2px 8px;
    margin: 0;
    font-size: 11px;
  }
  dt {
    color: var(--fg-dim);
    font-size: 10px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  dd {
    margin: 0;
    color: var(--fg);
    overflow-wrap: anywhere;
  }
  .err {
    margin: 0 0 4px;
    font-size: 11px;
    color: var(--warn);
  }
  .hint {
    margin: 0;
    font-size: 10px;
    color: var(--fg-dim);
    line-height: 1.5;
  }
  code {
    font-family: ui-monospace, monospace;
    font-size: 10px;
  }
  .term {
    margin-top: 8px;
    max-height: 150px;
    overflow-y: auto;
    background: var(--panel2);
    border: 1px solid var(--border);
    padding: 4px 6px;
  }
  .line {
    font-family: ui-monospace, monospace;
    font-size: 10px;
    line-height: 1.55;
    color: var(--fg-dim);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
</style>
