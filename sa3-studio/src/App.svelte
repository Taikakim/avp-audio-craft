<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import CropLibrary from "./lib/CropLibrary.svelte";
  import Inspector from "./lib/Inspector.svelte";
  import { project } from "./lib/store.svelte";
  import Timeline from "./lib/Timeline.svelte";
  import TransportBar from "./lib/TransportBar.svelte";

  onMount(() => {
    project.connect();
  });
  onDestroy(() => {
    project.disconnect();
  });
</script>

<main>
  <header>
    <h1>SA3 Studio</h1>
    <span class="tagline">the timeline is audio — RENDER commits</span>
  </header>

  <TransportBar />

  <div class="workspace">
    <Timeline />
    <aside>
      <CropLibrary />
      <Inspector />
    </aside>
  </div>
</main>

<style>
  /* Palette + type lifted from docs/sa3-studio/design_handoff/SA3 Studio v3.dc.html
     (LANE_META, the header bar, the --panel/--border/--text tokens) -- same oklch
     hues and structure (sharp-edged boxy panels, uppercase letter-spaced section
     labels, monospace-leaning technical type), translated to a dark ground because
     UI_BRIEF.md (mir-feature-extraction/plots/explorer_sa3/) records Kim's own
     preference for a dark theme, which v3's mockup didn't follow. Light block is
     the handoff's values verbatim; dark block only re-maps lightness/chroma. */
  :global(:root) {
    --bg: oklch(96% 0.006 240);
    --panel-bg: oklch(93% 0.008 240);
    --panel2: oklch(90% 0.012 240);
    --track-bg: oklch(90% 0.012 240);
    --border: oklch(80% 0.014 240);
    --fg: oklch(27% 0.02 250);
    --fg-dim: oklch(52% 0.016 250);
    --accent: oklch(55% 0.11 195); /* turq -- primary actions, playhead */
    --accent-fg: oklch(98% 0.01 195);
    --purple: oklch(54% 0.1 300);
    --green: oklch(56% 0.11 150);
    --neutral-lane: oklch(50% 0.02 250);
    --btn-bg: var(--panel2);
    --clip-bg: oklch(90% 0.012 240 / 0.6);
    --clip-border: var(--border);
    --ok: var(--green);
    --ok-fg: oklch(98% 0.02 150);
    --warn: oklch(72% 0.15 75); /* amber -- stale latent, not yet an error */
    --warn-fg: oklch(20% 0.02 75);
    --red: oklch(55% 0.2 25); /* reserved for real errors / clipping, not staleness */
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: oklch(17% 0.012 240);
      --panel-bg: oklch(22% 0.014 240);
      --panel2: oklch(26% 0.016 240);
      --track-bg: oklch(26% 0.016 240);
      --border: oklch(34% 0.018 240);
      --fg: oklch(92% 0.008 250);
      --fg-dim: oklch(65% 0.02 250);
      --accent: oklch(72% 0.13 195);
      --accent-fg: oklch(15% 0.02 195);
      --purple: oklch(72% 0.12 300);
      --green: oklch(72% 0.13 150);
      --neutral-lane: oklch(70% 0.015 250);
      --clip-bg: oklch(26% 0.016 240 / 0.6);
      --ok-fg: oklch(15% 0.02 150);
      --warn: oklch(78% 0.14 75);
      --warn-fg: oklch(18% 0.02 75);
      --red: oklch(68% 0.18 25);
    }
  }
  :global(body) {
    margin: 0;
    background: var(--bg);
    color: var(--fg);
    font-family: "Space Grotesk", ui-monospace, "Cascadia Code", monospace;
    font-size: 12px;
  }
  main {
    max-width: 1400px;
    margin: 0 auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  header {
    display: flex;
    align-items: baseline;
    gap: 10px;
    height: 42px;
    padding: 0 12px;
    background: var(--panel-bg);
    border: 1px solid var(--border);
  }
  h1 {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.16em;
    color: var(--accent);
    margin: 0;
  }
  .tagline {
    color: var(--fg-dim);
    font-size: 11px;
  }
  .workspace {
    display: flex;
    gap: 12px;
    align-items: flex-start;
  }
  .workspace > :global(.timeline) {
    flex: 1;
    min-width: 0;
  }
  aside {
    display: flex;
    flex-direction: column;
    gap: 12px;
    flex: 0 0 260px;
  }
</style>
