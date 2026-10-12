<script lang="ts">
  // Spec §4.2 + §7.1. The commit action itself lives in lib/render/mixdown.svelte.ts, shared with
  // the MIX tab's button (§7.1: "same as the row above").
  import { HELP } from "../../lib/help/strings";
  import { forgeApi } from "../../lib/forge/api";
  import { drawPeaks, peaksFor } from "../../lib/audio/waveform";
  import { Transport } from "../../lib/audio/transport";
  import { writeForgeDrag } from "../../lib/math/laneHeader";
  import { history } from "../../lib/render/history.svelte";
  import { mixdownBlock, runMixdown } from "../../lib/render/mixdown.svelte";
  import { previewPlayer } from "../../lib/render/previewPlayer.svelte";
  import { mixdownLabel } from "./mixdown";

  interface Props {
    busy?: boolean;
    stepsLeft?: number | null;
  }
  let { busy = false, stepsLeft = null }: Props = $props();

  let canvasEl = $state<HTMLCanvasElement>();
  let buffer = $state<AudioBuffer | null>(null);

  const label = $derived(mixdownLabel(busy, stepsLeft));
  const block = $derived(mixdownBlock());
  const entry = $derived(history.mixdown === null ? null : history.renders[history.mixdown] ?? null);
  const url = $derived(entry === null ? null : forgeApi.audioUrl(history.refOf(entry)));

  // ■ only when THIS slot's audio is the loaded one -- the preview container drives the same
  // singleton, and a mix playing is not the same thing as a preview playing.
  const playing = $derived(previewPlayer.playing && previewPlayer.url === url);

  /** Decode-only Transport, the same lazy accessor Task 7's PreviewContainer uses: a module-level
   *  `new Transport()` throws at IMPORT time under jsdom. `peaksFor` needs a real `AudioBuffer`. */
  let _decoder: Transport | null | undefined;
  function decoder(): Transport | null {
    if (_decoder === undefined) {
      try { _decoder = new Transport(); } catch { _decoder = null; }
    }
    return _decoder;
  }

  // Reads url, writes `buffer` -- an $effect, NOT a $derived (Global constraint 4: no writes
  // inside a $derived), and guarded so a superseded load cannot overwrite a newer one. The
  // `.catch` is not optional: `mixdownSlotWired.test.ts` stubs no fetch.
  $effect(() => {
    const u = url;
    buffer = null;                 // a new url invalidates the old buffer, not merely supersedes it:
    if (u === null) return;        // peaksFor memoises on a url-derived key, so a stale pair poisons it
    let live = true;
    decoder()?.preload(u).then((b) => { if (live) buffer = b; }).catch(() => { if (live) buffer = null; });
    return () => { live = false; };
  });

  $effect(() => {
    if (canvasEl === undefined) return;
    const b = buffer;
    const ctx = canvasEl.getContext("2d");
    if (ctx === null) return;
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
    if (b === null || url === null) return;
    // `drawPeaks(canvas, peaks, color)` -- canvas first, three args, and `peaksFor` is
    // SYNCHRONOUS and takes a non-null AudioBuffer (sa3-studio/src/lib/waveform.ts:56-84, the
    // file M1 T15 re-homes verbatim). Global constraint 5: a token can come back "", so the
    // colour carries a literal fallback or `fillStyle = ""` is a silent no-op.
    drawPeaks(
      canvasEl,
      peaksFor(url, b, Math.max(1, canvasEl.width), 0, entry?.dur_sec ?? 0),
      getComputedStyle(canvasEl).getPropertyValue("--accent").trim() || "#4ec9b0",
    );
  });

  function scrub(e: MouseEvent) {
    if (entry === null || url === null || canvasEl === undefined) return;
    const rect = canvasEl.getBoundingClientRect();
    // rect.width, not canvas.width: the backing store is 220 px but CSS may size it otherwise.
    const frac = rect.width > 0 ? Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width)) : 0;
    previewPlayer.load(url, entry.dur_sec);
    void previewPlayer.scrubAt(frac * entry.dur_sec);
  }

  function togglePlay() {
    if (url === null || entry === null) return;
    // §4.5: preview playback is independent of the timeline transport, and starting one stops the
    // other. Writer B's `previewPlayer` owns that rule (it registers on the solo bus); M5's
    // `playback` is the ARRANGEMENT transport, so driving it from here would rewind the
    // operator's timeline instead of playing the mix.
    previewPlayer.load(url, entry.dur_sec);
    void previewPlayer.toggle();
  }

  function onDragStart(e: DragEvent) {
    if (entry === null || e.dataTransfer === null) return;
    writeForgeDrag(e.dataTransfer, history.refOf(entry), entry.dur_sec || null);
    e.dataTransfer.effectAllowed = "copy";
  }
</script>

<div class="mixdown-slot" data-region="mixdown-slot">
  <button
    class="commit"
    class:busy
    data-testid="mixdown-button"
    data-help={HELP.mixdownButton}
    title={block ?? ""}
    disabled={busy || block !== null}
    onclick={() => void runMixdown()}>{label}</button>
  <canvas
    class="wave"
    data-testid="mixdown-canvas"
    data-help={HELP.mixdownWave}
    bind:this={canvasEl}
    width="220"
    height="26"
    draggable={entry !== null}
    ondragstart={onDragStart}
    onclick={scrub}
  ></canvas>
  <button class="play" data-testid="mixdown-play" aria-label="play the latest mixdown"
    disabled={entry === null} onclick={togglePlay}>{playing ? "■" : "▶"}</button>
</div>

<style>
  .mixdown-slot {
    display: flex;
    align-items: center;
    gap: 5px;
    flex-shrink: 0;
    border-left: 1px solid var(--border);
    padding-left: 8px;
  }
  .commit {
    background: var(--turq-strong);
    border: 1px solid var(--turq-strong);
    color: white;
    font-family: inherit;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    padding: 5px 14px;
    cursor: pointer;
  }
  .commit.busy,
  .commit:disabled {
    background: var(--panel2);
    color: var(--turq-strong);
    cursor: default;
  }
  .wave {
    box-sizing: border-box;
    width: 220px;
    height: 26px;
    display: block;
    border: 1px solid var(--border);
    background: var(--panel2);
  }
  .play {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text-dim);
    font-family: inherit;
    font-size: 10px;
    padding: 4px 6px;
    cursor: pointer;
  }
  .play:disabled {
    cursor: default;
  }
</style>
