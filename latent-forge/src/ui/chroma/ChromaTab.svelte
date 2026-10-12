<script lang="ts">
  // The CHROMA tab (spec §4.5 -> §5.4), composed from Tasks 6-10 into M1 T11's
  // [data-region="bottom-tab-body"]. The tab's right-aligned hint is M1 T12's
  // (bottomHint("chroma")) and is NOT re-rendered here.
  //
  // WHICH REQUEST LEADS. §5.4 wants chroma computed on the clip's STRETCHED
  // preview, and a detune change re-stretched through /forge/stretch debounced
  // 400 ms. Those are sequential:
  //
  //   setDetune (this tab's strip, or M5 T4's lane-header field)
  //     -> $effect on clip.detune_cents  -> scheduleStretch (M5 T10, 400 ms)
  //     -> clip.previewAudio changes
  //     -> $effect on (previewAudio ?? audio) -> chromaClient.request
  //
  // The chroma effect is keyed on the REF, not on the detune, so nothing ever
  // analyses the pre-stretch audio in between. One debounce, one owner, and it
  // covers the lane header's detune field as well as the strip's.
  //
  // HOW MUCH DETUNE TO ROTATE BY -- decided ONCE, here. runStretch has already
  // pitch-shifted previewAudio by clip.detune_cents / 100 (M5:5358), so when
  // the analysed ref WAS previewAudio the chroma is already detuned and a
  // consumer that rotates it again by the clip's detune applies the detune
  // twice. When the analysed ref was the raw clip.audio -- which happens
  // whenever runStretch returns early, i.e. clip.native_bpm == null -- the
  // detune is NOT in the audio and the rotation is still needed. That is the
  // whole rule, and `analysisDetuneCents` below is the only place it lives:
  // every consumer (heatmap hue, match curve, hover, clip score, detune scan)
  // gets THAT number rather than clip.detune_cents, so nothing re-derives it.
  // Its knock-on effect is that the scan strip's axis is relative and BEST is
  // additive -- see Task 8 and the plan's Open question 6.
  //
  // arrangement.selectedClip is promised by M5 T1's Interfaces line and never
  // defined in its code (M5's own self-review says so), so the selected clip is
  // computed locally from view.selection, exactly as M5 T9 does.
  import { chromaClient } from "../../lib/chroma/chromaClient.svelte";
  import { chromaLink, clipFrameRange } from "../../lib/chroma/chromaLink.svelte";
  import { meanMatchAtDetune, type ScanCriterion } from "../../lib/chroma/detuneScan";
  import {
    CHROMA_VIEWS,
    type ChromaView,
    type FrameWindow,
    VIEW_LABELS,
    fullWindow,
  } from "../../lib/chroma/heatmapGeometry";
  import { type ChromaHover, readHover } from "../../lib/chroma/hoverReadout";
  import { chromaTarget, laneTargetRefs } from "../../lib/chroma/targetStore.svelte";
  import { scheduleStretch } from "../../lib/clips/lifecycle";
  import type { ForgeApiError } from "../../lib/forge/api";
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { view } from "../../lib/stores/view.svelte";
  import ChromaHeatmap from "./ChromaHeatmap.svelte";
  import DetuneScanStrip from "./DetuneScanStrip.svelte";
  import HoverReadout from "./HoverReadout.svelte";
  import MatchCurveOverlay from "./MatchCurveOverlay.svelte";
  import MatchLegend from "./MatchLegend.svelte";
  import TargetRow from "./TargetRow.svelte";

  let chromaView = $state<ChromaView>("global");
  let showCurve = $state(true);
  let criterion = $state<ScanCriterion>("highest");
  let win = $state<FrameWindow>({ from: 0, to: 1 });
  let hover = $state<ChromaHover | null>(null);
  let boxEl = $state<HTMLDivElement>();
  let loggedError: string | null = null;

  const selectedClip = $derived.by(() => {
    const sel = view.selection;
    return sel.kind === "clip" ? arrangement.clips.find((c) => c.id === sel.id) : undefined;
  });
  /** §5.4: the STRETCHED preview, falling back to the source for an unstretched clip. */
  const audioRef = $derived(selectedClip ? (selectedClip.previewAudio ?? selectedClip.audio) : null);
  /**
   * The detune that is NOT already baked into the analysed audio -- 0 when the
   * analysed ref was the stretched preview, the clip's own when it was the raw
   * source. The single decision point; every consumer below takes this.
   */
  const analysisDetuneCents = $derived(
    selectedClip && !selectedClip.previewAudio ? selectedClip.detune_cents : 0,
  );
  const result = $derived(chromaClient.result);
  const target = $derived(chromaTarget.profile);
  const error = $derived(chromaClient.error ?? chromaTarget.error);
  const clipScore = $derived(selectedClip ? (chromaLink.scores[selectedClip.id] ?? null) : null);

  // 1. The analysis follows the REF, so a fresh stretch re-analyses and a bare
  //    detune change does not.
  $effect(() => {
    const ref = audioRef;
    if (!ref) return;
    void chromaClient.request(ref);
  });

  // 2. The window resets whenever a different-length analysis lands.
  $effect(() => {
    const res = result;
    win = res ? fullWindow(res.T) : { from: 0, to: 1 };
  });

  // 3. Detune -> M5 T10's debounced stretch. The ONLY place that arms it.
  $effect(() => {
    const clip = selectedClip;
    if (!clip) return;
    void clip.detune_cents;
    scheduleStretch(clip.id, (e: ForgeApiError) => view.appendLog(`[chroma] stretch: ${e.message}`, "error"));
  });

  // 4. lane-mode target: analyse the TARGET lane's own clips.
  $effect(() => {
    if (chromaTarget.mode !== "lane") return;
    void chromaTarget.loadLane(laneTargetRefs(arrangement.clips, arrangement.targetLane));
  });

  // 5. §5.4's clip score label: the mean frame match over EVERY frame.
  $effect(() => {
    const clip = selectedClip;
    const res = result;
    if (!clip || !res) return;
    chromaLink.setScore(clip.id, meanMatchAtDetune(res.fold12, res.T, target, analysisDetuneCents,
      clipFrameRange(clip, res.T, res.fps)));
  });

  // 6. §9.7: a server error is a red TERMINAL line as well as an inline one.
  $effect(() => {
    const e = error;
    if (!e || e === loggedError) return;
    loggedError = e;
    view.appendLog(`[chroma] ${e}`, "error");
  });

  function onMove(e: PointerEvent): void {
    const box = boxEl;
    const res = result;
    const clip = selectedClip;
    if (!box || !res || !clip) return;
    const rect = box.getBoundingClientRect();
    const h = readHover({
      result: res,
      target,
      view: chromaView,
      win,
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      widthPx: rect.width,
      heightPx: rect.height,
      detuneCents: analysisDetuneCents,
    });
    hover = h;
    if (h) chromaLink.setHover(clip.id, h.frac, (h.frac * Math.max(0, res.T - 1)) / res.fps);
    else chromaLink.clearHover();
  }

  function onLeave(): void {
    hover = null;
    chromaLink.clearHover();
  }
</script>

<div class="tab" data-region="chroma-tab">
  <div class="mode-row">
    {#each CHROMA_VIEWS as v (v)}
      <button
        type="button"
        data-chroma-view={v}
        class:on={chromaView === v}
        onclick={() => (chromaView = v)}>{VIEW_LABELS[v]}</button
      >
    {/each}
    <button
      type="button"
      data-testid="chroma-curve-toggle"
      class:on={showCurve}
      onclick={() => (showCurve = !showCurve)}>MATCH CURVE</button
    >
    <MatchLegend target={target} clipScore={clipScore} />
    <div class="spacer"></div>
    <TargetRow />
  </div>

  <div class="body">
    <div class="side">
      <DetuneScanStrip
        clip={selectedClip ?? null}
        result={result}
        target={target}
        criterion={criterion}
        detuneCents={analysisDetuneCents}
        oncriterion={(c) => (criterion = c)}
      />
      <HoverReadout hover={hover} />
      {#if error}
        <p class="state error" data-testid="chroma-error">{error}</p>
      {:else if !selectedClip}
        <p class="state" data-testid="chroma-empty">no clip selected</p>
      {:else if chromaClient.pending}
        <p class="state" data-testid="chroma-empty">computing chroma…</p>
      {/if}
    </div>
    <div
      class="heatmap-box"
      data-region="chroma-heatmap-box"
      role="presentation"
      bind:this={boxEl}
      onpointermove={onMove}
      onpointerleave={onLeave}
    >
      <ChromaHeatmap
        view={chromaView}
        win={win}
        result={result}
        target={target}
        detuneCents={analysisDetuneCents}
        onwin={(w) => (win = w)}
      />
      {#if showCurve}
        <MatchCurveOverlay
          result={result}
          target={target}
          win={win}
          detuneCents={analysisDetuneCents}
        />
      {/if}
    </div>
  </div>
</div>

<style>
  .tab {
    box-sizing: border-box;
    height: 100%;
    display: flex;
    flex-direction: column;
    min-height: 0;
    border: 1px solid var(--border);
    background: var(--panel);
    overflow: hidden;
  }
  .mode-row {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    padding: 5px 8px;
    background: var(--panel2);
    border-bottom: 1px solid var(--border);
  }
  .mode-row button {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text);
    font-size: 9px;
    padding: 3px 5px;
    cursor: pointer;
  }
  .mode-row button.on {
    border-color: var(--turq-strong);
    color: var(--turq-strong);
  }
  .spacer {
    flex: 1;
  }
  .body {
    display: flex;
    gap: 8px;
    flex: 1;
    min-height: 0;
    padding: 7px 8px;
  }
  .side {
    width: 250px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
    overflow-y: auto;
  }
  .heatmap-box {
    position: relative;
    display: flex;
    flex: 1;
    min-width: 0;
    min-height: 0;
  }
  .state {
    margin: 0;
    font-size: 10px;
    color: var(--text-dim);
  }
  .state.error {
    color: var(--red);
  }
</style>
