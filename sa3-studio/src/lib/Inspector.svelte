<script lang="ts">
  import { formatBarsBeats, frameAt } from "./musictime";
  import { project } from "./store.svelte";
  import { BEND_OP_NAMES, RENDER_OPS, type BendOp } from "./types";

  let rendering = $state(false);
  let renderError = $state<string | null>(null);

  const clip = $derived(project.selectedClip);
  const block = $derived(clip ? project.renderBlock(clip) : null);

  async function doRender() {
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

  function addBendOp() {
    if (!clip) return;
    clip.render.bendOps = [...(clip.render.bendOps ?? []), { op: "noise", amount: 0.1 }];
  }
  function removeBendOp(i: number) {
    if (!clip) return;
    clip.render.bendOps = (clip.render.bendOps ?? []).filter((_, j) => j !== i);
  }
  function setBendOpName(i: number, name: BendOp["op"]) {
    if (!clip?.render.bendOps) return;
    clip.render.bendOps[i].op = name;
  }
</script>

<div class="inspector">
  <div class="head">
    <span class="section-label">Clip</span>
    {#if clip}
      <button class="mini" onclick={() => project.duplicateClip(clip.id)} title="duplicate">⧉</button>
      <button class="mini danger" onclick={() => project.removeClip(clip.id)} title="delete">✕</button>
    {/if}
  </div>

  {#if !clip}
    <p class="hint">Select a clip to inspect and render it.</p>
  {:else}
    <div class="rows">
      <span class="k">SOURCE</span>
      <span class="v mono">
        {clip.source.kind === "empty"
          ? "empty slot — nothing rendered yet"
          : clip.source.kind === "audio-file"
            ? clip.source.name
            : clip.source.kind === "crop"
              ? `crop:${clip.source.cropId}`
              : `job:${clip.source.jobId}`}
      </span>

      <span class="k">POSITION</span>
      <span class="v mono">
        {clip.startSec.toFixed(3)}s · bar {formatBarsBeats(clip.startSec, project.meter)} · frame {frameAt(
          clip.startSec,
        )}
      </span>

      <span class="k">LENGTH</span>
      <span class="v mono">{clip.durationSec.toFixed(3)}s{clip.offsetSec > 0 ? ` (trim +${clip.offsetSec.toFixed(3)}s)` : ""}</span>

      <span class="k">LATENT</span>
      <span class="v">
        <span class="state {clip.latentState}">{clip.latentState}</span>
        {#if clip.latentState === "stale"}
          <span class="warn-text">moved since encode — RENDER re-encodes here</span>
        {/if}
      </span>

      <span class="k" title="Absolute path on the SERVER. /a2a_track and /a2a_mix resolve this with require_path(); there is no upload route.">SERVER PATH</span>
      <span class="v">
        <input
          class="path"
          type="text"
          placeholder="set by a render, or paste one"
          value={clip.serverPath ?? ""}
          oninput={(e) => (clip.serverPath = (e.target as HTMLInputElement).value || undefined)}
        />
      </span>

      <span class="k">CLIP BPM</span>
      <span class="v">
        <input
          class="num"
          type="number"
          step="0.1"
          placeholder="—"
          value={clip.bpm ?? ""}
          oninput={(e) => (clip.bpm = +(e.target as HTMLInputElement).value || undefined)}
        />
        <span class="k inline-k">DOWNBEAT @</span>
        <input
          class="num"
          type="number"
          step="0.01"
          placeholder="—"
          value={clip.downbeatSec ?? ""}
          oninput={(e) => (clip.downbeatSec = +(e.target as HTMLInputElement).value || undefined)}
        />
      </span>
    </div>

    <hr />

    <label class="field">
      <span>RENDER OP</span>
      <select value={clip.render.op} onchange={(e) => project.setRenderOp(clip.id, (e.target as HTMLSelectElement).value as never)}>
        {#each RENDER_OPS as op}
          <option value={op.value}>{op.label}</option>
        {/each}
      </select>
    </label>

    {#if clip.render.op === "generate" || clip.render.op === "a2a_track"}
      <label class="field">
        <span>PROMPT</span>
        <textarea rows="2" bind:value={clip.render.prompt}></textarea>
      </label>
    {/if}
    {#if clip.render.op === "generate"}
      <label class="field">
        <span>NEGATIVE PROMPT</span>
        <input type="text" bind:value={clip.render.negativePrompt} />
      </label>
    {/if}
    {#if clip.render.op === "longform"}
      <label class="field">
        <span>SCHEDULE <em>(arc grammar: 0:promptA|45:promptB)</em></span>
        <textarea rows="2" bind:value={clip.render.schedule}></textarea>
      </label>
      <div class="row-fields">
        <label class="field narrow"><span>WINDOW</span><input type="number" step="1" bind:value={clip.render.windowSec} placeholder="30" /></label>
        <label class="field narrow"><span>OVERLAP</span><input type="number" step="1" bind:value={clip.render.overlapSec} placeholder="5" /></label>
        <label class="field narrow"><span>XFADE</span><input type="number" step="1" bind:value={clip.render.xfadeSec} placeholder="4" /></label>
      </div>
    {/if}
    {#if clip.render.op === "a2a_mix"}
      <label class="field">
        <span>B PATH <em>(server-side)</em></span>
        <input type="text" bind:value={clip.render.mixBPath} />
      </label>
      <label class="field">
        <span>REGION PROMPT</span>
        <input type="text" bind:value={clip.render.promptRegion} />
      </label>
    {/if}
    {#if clip.render.op === "a2a_track" || clip.render.op === "a2a_mix" || clip.render.op === "longform"}
      <label class="field narrow">
        <span>NOISE</span>
        <input type="number" step="0.01" min="0" max="1" bind:value={clip.render.noiseLevel} />
      </label>
    {/if}
    {#if clip.render.op === "bend"}
      <div class="field">
        <span>BEND OPS <em>(eval/latent_bend.py)</em></span>
        {#each clip.render.bendOps ?? [] as op, i}
          <div class="bend-row">
            <select value={op.op} onchange={(e) => setBendOpName(i, (e.target as HTMLSelectElement).value as BendOp["op"])}>
              {#each BEND_OP_NAMES as name}
                <option value={name}>{name}</option>
              {/each}
            </select>
            <input class="num" type="number" step="0.05" bind:value={op.amount} placeholder="amt" />
            {#if op.op === "channel_roll"}
              <input class="num" type="number" bind:value={op.k} placeholder="k" />
              <input class="num" type="number" bind:value={op.shift} placeholder="shift" />
            {:else if op.op === "quantize"}
              <input class="num" type="number" bind:value={op.bits} placeholder="bits" />
            {:else if op.op === "segment_shuffle"}
              <input class="num" type="number" bind:value={op.seg} placeholder="seg" />
            {/if}
            <button class="mini danger" onclick={() => removeBendOp(i)}>✕</button>
          </div>
        {/each}
        <button class="mini wide" onclick={addBendOp}>+ add op</button>
      </div>
    {/if}

    {#if clip.render.op !== "decode"}
      <div class="row-fields">
        <label class="field narrow"><span>STEPS</span><input type="number" min="1" bind:value={clip.render.steps} /></label>
        <label class="field narrow"><span>CFG</span><input type="number" step="0.1" bind:value={clip.render.cfgScale} /></label>
        <label class="field narrow"><span>SEED</span><input type="number" bind:value={clip.render.seed} /></label>
      </div>
    {/if}

    {#if block}
      <p class="blocked"><strong>{block.reason}</strong> — {block.hint}</p>
    {/if}

    <button class="render-btn" onclick={doRender} disabled={rendering || !!clip.pendingJobId || !!block}>
      {rendering || clip.pendingJobId ? "RENDERING…" : "▸ RENDER"}
    </button>

    {#if renderError}
      <p class="error">{renderError}</p>
    {:else if clip.lastRenderNote}
      <p class="note ok-note">last: {clip.lastRenderNote}</p>
    {/if}
    <p class="note">
      RENDER commits: it runs the real op server-side and replaces this clip's preview with the
      actual output. Everything before this button is audio-domain preview only.
    </p>
  {/if}
</div>

<style>
  .inspector {
    padding: 8px 10px 10px;
    background: var(--panel-bg);
    border: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: 7px;
    min-width: 260px;
  }
  .head {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .section-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--fg-dim);
    margin-right: auto;
  }
  .mini {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--fg-dim);
    font-family: inherit;
    font-size: 10px;
    padding: 2px 6px;
    cursor: pointer;
  }
  .mini.danger:hover {
    border-color: var(--red);
    color: var(--red);
  }
  .mini.wide {
    width: 100%;
    margin-top: 3px;
  }
  .hint {
    color: var(--fg-dim);
    font-size: 12px;
    margin: 0;
  }
  .rows {
    display: grid;
    grid-template-columns: 74px 1fr;
    gap: 3px 6px;
    align-items: center;
  }
  .k {
    font-size: 9px;
    letter-spacing: 0.05em;
    color: var(--fg-dim);
  }
  .inline-k {
    margin-left: 4px;
  }
  .v {
    font-size: 11px;
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: wrap;
  }
  .mono {
    font-family: ui-monospace, monospace;
    overflow-wrap: anywhere;
  }
  .state {
    padding: 1px 5px;
    font-size: 9px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .state.valid {
    background: var(--ok);
    color: var(--ok-fg);
  }
  .state.stale {
    background: var(--warn);
    color: var(--warn-fg);
  }
  .state.none {
    background: var(--panel2);
    color: var(--fg-dim);
  }
  .warn-text {
    color: var(--warn);
    font-size: 10px;
  }
  hr {
    border: none;
    border-top: 1px solid var(--border);
    margin: 2px 0;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 3px;
    font-size: 9px;
    letter-spacing: 0.05em;
    color: var(--fg-dim);
  }
  .field em {
    font-style: normal;
    text-transform: none;
    letter-spacing: normal;
    opacity: 0.8;
  }
  .field input,
  .field textarea,
  .field select,
  .path,
  .num {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--fg);
    padding: 3px 5px;
    font-size: 11px;
    font-family: inherit;
  }
  .path {
    width: 100%;
    font-family: ui-monospace, monospace;
    font-size: 10px;
  }
  .num {
    width: 56px;
  }
  .row-fields {
    display: flex;
    gap: 6px;
  }
  .field.narrow {
    width: 70px;
  }
  .bend-row {
    display: flex;
    gap: 3px;
    align-items: center;
    margin-top: 3px;
  }
  .bend-row select {
    flex: 1;
    min-width: 0;
  }
  .bend-row .num {
    width: 46px;
  }
  .blocked {
    margin: 0;
    font-size: 10px;
    line-height: 1.45;
    color: var(--warn);
    background: var(--panel2);
    border-left: 3px solid var(--warn);
    padding: 5px 7px;
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
    opacity: 0.45;
    cursor: default;
  }
  .error {
    color: var(--red);
    font-size: 11px;
    margin: 0;
  }
  .note {
    color: var(--fg-dim);
    font-size: 10px;
    line-height: 1.45;
    margin: 0;
  }
  .ok-note {
    color: var(--green);
  }
</style>
