<script lang="ts">
  import { project } from "./store.svelte";

  let rendering = $state(false);
  let renderError = $state<string | null>(null);

  async function doRender() {
    const clip = project.selectedClip;
    if (!clip) return;
    rendering = true;
    renderError = null;
    try {
      await project.renderClip(clip.id);
    } catch (e) {
      renderError = e instanceof Error ? e.message : String(e);
    } finally {
      rendering = false;
    }
  }
</script>

<div class="inspector">
  <h3>Clip</h3>
  {#if !project.selectedClip}
    <p class="hint">Select a clip to inspect and render it.</p>
  {:else}
    {@const clip = project.selectedClip}
    <div class="row">
      <span class="field-label">SOURCE</span>
      <span class="mono">
        {clip.source.kind === "audio-file" ? clip.source.name : clip.source.kind === "crop" ? `crop:${clip.source.cropId}` : `job:${clip.source.jobId}`}
      </span>
    </div>
    <div class="row">
      <span class="field-label">POSITION</span>
      <span class="mono">{clip.startSec.toFixed(3)}s → {(clip.startSec + clip.durationSec).toFixed(3)}s</span>
    </div>
    <div class="row">
      <span class="field-label">LATENT</span>
      <span class="latent-state {clip.latentState}">{clip.latentState}</span>
      {#if clip.latentState === "stale"}
        <span class="hint-inline">moved since last encode — RENDER to re-encode at this position</span>
      {/if}
    </div>

    <hr />

    <label class="field">
      <span>PROMPT <em>(empty = just re-decode the source latent)</em></span>
      <textarea rows="2" bind:value={clip.render.prompt}></textarea>
    </label>
    <label class="field">
      <span>NEGATIVE PROMPT</span>
      <input type="text" bind:value={clip.render.negativePrompt} />
    </label>
    <div class="row-fields">
      <label class="field narrow">
        <span>STEPS</span>
        <input type="number" min="1" bind:value={clip.render.steps} />
      </label>
      <label class="field narrow">
        <span>CFG</span>
        <input type="number" step="0.1" bind:value={clip.render.cfgScale} />
      </label>
      <label class="field narrow">
        <span>SEED</span>
        <input type="number" bind:value={clip.render.seed} />
      </label>
    </div>

    <button class="render-btn" onclick={doRender} disabled={rendering || !!clip.pendingJobId}>
      {rendering || clip.pendingJobId ? "RENDERING…" : "▸ RENDER"}
    </button>
    {#if renderError}
      <p class="error">{renderError}</p>
    {/if}
    <p class="note">
      RENDER commits: it runs the real op on the server (POST /generate or /decode) and replaces this
      clip's preview with the actual output. Everything before this button is audio-domain preview only.
    </p>
  {/if}
</div>

<style>
  .inspector {
    padding: 10px 12px;
    background: var(--panel-bg);
    border: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-width: 260px;
  }
  h3 {
    margin: 0;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: var(--fg-dim);
    text-transform: uppercase;
  }
  .hint {
    color: var(--fg-dim);
    font-size: 12px;
  }
  .hint-inline {
    color: var(--warn);
    font-size: 11px;
  }
  .row {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
  }
  .field-label {
    color: var(--fg-dim);
    width: 64px;
    flex: 0 0 auto;
    font-size: 10px;
    letter-spacing: 0.05em;
  }
  .mono {
    font-family: ui-monospace, monospace;
    font-size: 12px;
    color: var(--fg);
  }
  .latent-state {
    padding: 1px 6px;
    font-size: 10px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .latent-state.valid {
    background: var(--ok);
    color: var(--ok-fg);
  }
  .latent-state.stale {
    background: var(--warn);
    color: var(--warn-fg);
  }
  .latent-state.none {
    background: var(--btn-bg);
    color: var(--fg-dim);
  }
  hr {
    border: none;
    border-top: 1px solid var(--border);
    margin: 4px 0;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 3px;
    font-size: 10px;
    letter-spacing: 0.04em;
    color: var(--fg-dim);
  }
  .field em {
    font-style: normal;
    text-transform: none;
    letter-spacing: normal;
    opacity: 0.8;
  }
  .field input,
  .field textarea {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--fg);
    padding: 4px 6px;
    font-size: 12px;
    font-family: inherit;
  }
  .row-fields {
    display: flex;
    gap: 8px;
  }
  .field.narrow {
    width: 70px;
  }
  .render-btn {
    background: var(--accent);
    color: var(--accent-fg);
    border: 1px solid var(--accent);
    padding: 8px;
    font-weight: 700;
    letter-spacing: 0.05em;
    font-family: inherit;
    font-size: 12px;
    cursor: pointer;
  }
  .render-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .error {
    color: var(--warn);
    font-size: 12px;
  }
  .note {
    color: var(--fg-dim);
    font-size: 10px;
    line-height: 1.4;
  }
</style>
