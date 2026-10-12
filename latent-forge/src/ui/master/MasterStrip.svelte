<script lang="ts">
  // Re-homed from src/lib/MasterStrip.svelte by M1 T15. This task moves it
  // off the v1 `project` store onto the M5 `arrangement` store, and adds:
  // red 2px clip marks (spec §4.3), the a2a envelope overlay, and the
  // PREVIEW | MIXDOWN toggle frame -- the A/B that tests the project's core
  // premise (does the timeline's preview match what actually got rendered).
  // MIXDOWN itself is wired up by M9; here it is a disabled frame.
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { view } from "../../lib/stores/view.svelte";
  import { Transport } from "../../lib/audio/transport";
  import { computePeaks, drawPeaks, mixdownToBuffer, peakLevel } from "../../lib/audio/waveform";
  import { forgeApi } from "../../lib/forge/api";
  import { A2A_ENVELOPE_DEFAULT } from "../../lib/forge/defaults";
  import { clipMarkColumns } from "../../lib/audio/clipMarks";
  import { HELP } from "../../lib/help/strings";
  import EnvelopeEditor from "./EnvelopeEditor.svelte";

  let canvasEl = $state<HTMLCanvasElement>();
  let busy = $state(false);
  let error = $state<string | null>(null);
  let masterBuffer = $state<AudioBuffer | null>(null);
  let masterStale = $state(true);

  /** Decode-only use of Transport: fetch + decode, cached by URL. Not the
   *  playback engine -- this only warms the same cache other consumers read. */
  const decoder = new Transport();

  import { masterSource, MIXDOWN_UNAVAILABLE_HINT } from "../../lib/render/masterSource.svelte";
  import { playback } from "../../lib/stores/transport.svelte";
  import { mixdown, signalInputNow } from "../../lib/render/mixdown.svelte";
  import { signalKeyOf } from "../../lib/mix/signalPath";

  /** The mix as a buffer, decoded through the same cache M5's preview mix uses. */
  let mixBuffer = $state<AudioBuffer | null>(null);

  const showing = $derived(masterSource.effective);
  const shownBuffer = $derived(showing === "mixdown" ? mixBuffer : masterBuffer);
  // The badge describes what is SHOWN: the mixdown is stale when the arrangement has moved off the
  // signal key its commit was stamped with, the preview by its own flag below.
  const shownStale = $derived(
    showing === "mixdown"
      ? mixdown.key !== null && mixdown.key !== signalKeyOf(signalInputNow())
      : masterStale,
  );

  async function chooseSource(v: "preview" | "mixdown") {
    masterSource.set(v);
    // The two sources share a timebase, so the comparison happens at a moment, not from the top
    // (§9.6). A seek re-snapshots the clip list, which is what actually swaps what is heard.
    if (playback.playing) await playback.seek(playback.playheadSec);
  }

  $effect(() => {
    // Decode the committed mix when there is one. Reads masterSource.url; writes only mixBuffer,
    // which no derivation in this effect reads -- never write what you read (state_unsafe_mutation).
    const url = masterSource.url;
    if (url === null) {
      mixBuffer = null;
      return;
    }
    let cancelled = false;
    void decoder.preload(url)
      .then((b) => { if (!cancelled) mixBuffer = b; })
      .catch((e) => { if (!cancelled) error = e instanceof Error ? e.message : String(e); });
    return () => { cancelled = true; };
  });

  const peakNow = $derived(shownBuffer ? peakLevel(shownBuffer) : 0);
  const clipping = $derived(peakNow >= 0.999);
  const dbfs = $derived(peakNow > 0 ? (20 * Math.log10(peakNow)).toFixed(1) : null);

  const selectedClip = $derived.by(() => {
    const sel = view.selection;
    return sel.kind === "clip" ? arrangement.clips.find((c) => c.id === sel.id) : undefined;
  });
  const envelopeActive = $derived(selectedClip?.a2a?.on === true);
  const envelope = $derived(selectedClip?.a2a?.envelope ?? A2A_ENVELOPE_DEFAULT);

  async function refresh() {
    busy = true;
    error = null;
    try {
      const parts: { buffer: AudioBuffer; startSec: number; gain: number }[] = [];
      for (const clip of arrangement.clips) {
        if (!arrangement.isAudible(clip.lane)) continue;
        const buf = await decoder.preload(forgeApi.audioUrl(clip.previewAudio ?? clip.audio));
        parts.push({ buffer: buf, startSec: clip.start_sec, gain: arrangement.lanes[clip.lane].gain });
      }
      masterBuffer = await mixdownToBuffer(parts, decoder.ctx.sampleRate);
      masterStale = false;
      draw();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      busy = false;
    }
  }

  function draw() {
    const canvas = canvasEl;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!shownBuffer) {
      ctx?.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }
    const cols = Math.max(1, Math.round(canvas.clientWidth));
    const color = getComputedStyle(canvas).getPropertyValue("--accent").trim();
    const peaks = computePeaks(shownBuffer, cols);
    drawPeaks(canvas, peaks, color);
    if (!ctx) return;
    const red = getComputedStyle(canvas).getPropertyValue("--red").trim() || "red";
    ctx.fillStyle = red;
    for (const col of clipMarkColumns(peaks)) {
      ctx.fillRect(col, 0, 2, 2);
      ctx.fillRect(col, canvas.clientHeight - 2, 2, 2);
    }
  }

  // Redraw (not re-render) when the buffer, the element size, or the theme
  // changes -- `draw()` reads --accent/--red off getComputedStyle, which only
  // picks up a new value once the DARK toggle flips [data-theme], so
  // `view.theme` must be a tracked dependency here or the strip (and its clip
  // marks) keep their stale-theme colour (the same class of bug as the M1
  // same-day regression fix -- see this milestone's canvas colour rule).
  $effect(() => {
    void shownBuffer;
    void canvasEl;
    void view.theme;
    draw();
  });

  // Informational only (spec §7.3): any arrangement change makes the last
  // mix stale; a commit re-encodes lanes anyway, so this never blocks anything.
  $effect(() => {
    void arrangement.clips.length;
    void arrangement.bpm;
    masterStale = true;
  });
</script>

<div class="master" data-help={HELP.masterStrip}>
  <div class="head">
    <span class="section-label">Master — mix result</span>
    {#if dbfs}
      <span class="peak" class:clipping>peak {dbfs} dBFS{clipping ? " · CLIPPING" : ""}</span>
    {/if}
    {#if shownStale}
      <span class="stale-dot" title="the arrangement changed since this was rendered">stale</span>
    {/if}
    <button onclick={refresh} disabled={busy}>{busy ? "MIXING…" : "▸ MIX PREVIEW"}</button>
    <span class="spacer"></span>
    <div class="source-toggle" data-region="preview-mixdown-toggle" data-help={HELP.previewMixdownToggle}>
      <button
        class:active={showing === "preview"}
        data-testid="master-source-preview"
        onclick={() => void chooseSource("preview")}
      >PREVIEW</button>
      <button
        class:active={showing === "mixdown"}
        data-testid="master-source-mixdown"
        disabled={!masterSource.available}
        title={masterSource.available ? "" : MIXDOWN_UNAVAILABLE_HINT}
        onclick={() => void chooseSource("mixdown")}
      >MIXDOWN</button>
    </div>
  </div>
  <div class="canvas-wrap">
    <canvas bind:this={canvasEl} class="wave" data-region="master-canvas"></canvas>
    <EnvelopeEditor
      {envelope}
      active={envelopeActive}
      onChange={(env) => selectedClip && arrangement.setEnvelope(selectedClip.id, env)}
    />
  </div>
  {#if error}
    <p class="error">{error}</p>
  {:else if !shownBuffer}
    <p class="empty">no mix yet — add clips, then hit MIX PREVIEW</p>
  {/if}
</div>

<style>
  .master {
    background: var(--panel-bg);
    border: 1px solid var(--border);
  }
  .head {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 8px;
    background: var(--panel2);
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
  }
  .section-label {
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--fg-dim);
  }
  .spacer {
    flex: 1;
  }
  .peak {
    font-size: 10px;
    color: var(--fg-dim);
    font-variant-numeric: tabular-nums;
  }
  .peak.clipping {
    color: var(--red);
    font-weight: 600;
  }
  .stale-dot {
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    background: var(--warn);
    color: var(--warn-fg);
    padding: 1px 4px;
  }
  button {
    background: var(--panel-bg);
    border: 1px solid var(--accent);
    color: var(--accent);
    font-family: inherit;
    font-size: 10px;
    letter-spacing: 0.04em;
    padding: 3px 8px;
    cursor: pointer;
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .source-toggle {
    display: flex;
    gap: 2px;
  }
  .source-toggle button.active {
    background: var(--accent);
    color: var(--panel-bg);
  }
  .canvas-wrap {
    position: relative;
    width: 100%;
    height: 56px;
  }
  .wave {
    display: block;
    width: 100%;
    height: 56px;
  }
  .error {
    margin: 0;
    padding: 4px 8px;
    font-size: 11px;
    color: var(--red);
  }
  .empty {
    margin: 0;
    padding: 4px 8px;
    font-size: 10px;
    color: var(--fg-dim);
  }
</style>
