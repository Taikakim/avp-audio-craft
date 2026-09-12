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
  :global(:root) {
    --bg: #14161a;
    --panel-bg: #1c1f26;
    --track-bg: #10121600;
    --border: #2e323c;
    --fg: #e4e6eb;
    --fg-dim: #8a8f9c;
    --accent: #5fa8ff;
    --accent-fg: #0a1420;
    --btn-bg: #262a33;
    --clip-bg: #2a3f5f;
    --clip-border: #4a6fa5;
    --ok: #2e7d4f;
    --ok-fg: #dff5e6;
    --warn: #b5892b;
    --warn-fg: #241a02;
  }
  :global(body) {
    margin: 0;
    background: var(--bg);
    color: var(--fg);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
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
  }
  h1 {
    font-size: 18px;
    margin: 0;
  }
  .tagline {
    color: var(--fg-dim);
    font-size: 12px;
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
