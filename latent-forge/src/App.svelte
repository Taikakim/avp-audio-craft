<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import CropLibrary from "./lib/CropLibrary.svelte";
  import Inspector from "./lib/Inspector.svelte";
  import MasterStrip from "./lib/MasterStrip.svelte";
  import ServerPanel from "./lib/ServerPanel.svelte";
  import { project } from "./lib/store.svelte";
  import Timeline from "./lib/Timeline.svelte";
  import TransportBar from "./lib/TransportBar.svelte";

  function onKeydown(e: KeyboardEvent) {
    const t = e.target as HTMLElement | null;
    // Never steal keys from a field the user is typing in.
    if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT")) return;
    if (e.key === " ") {
      e.preventDefault();
      project.togglePlay();
    } else if (e.key === "Delete" || e.key === "Backspace") {
      if (project.selectedClipId) {
        e.preventDefault();
        project.removeClip(project.selectedClipId);
      }
    } else if (e.key === "Home") {
      e.preventDefault();
      project.seek(0);
    } else if (e.key === "+" || e.key === "=") {
      project.zoomBy(1.4);
    } else if (e.key === "-") {
      project.zoomBy(1 / 1.4);
    }
  }

  onMount(() => {
    project.connect();
    window.addEventListener("keydown", onKeydown);
  });
  onDestroy(() => {
    project.disconnect();
    window.removeEventListener("keydown", onKeydown);
  });
</script>

<main>
  <header>
    <h1>LATENT FORGE</h1>
    <span class="tagline">the timeline is audio — MIXDOWN commits</span>
  </header>

  <TransportBar />

  <div class="workspace">
    <div class="stack">
      <MasterStrip />
      <Timeline />
    </div>
    <aside>
      <ServerPanel />
      <CropLibrary />
      <Inspector />
    </aside>
  </div>
</main>

<style>
  /* Theme tokens (--bg, --panel-bg, --border, --fg, --accent, etc.) and the
     html/body base rule now live in src/styles/tokens.css, imported once in
     main.ts before this component mounts. That file also owns the dark theme
     via :root[data-theme="dark"] -- there is no prefers-color-scheme query
     (spec §9.1: the DARK toggle is the only thing that changes the theme). */
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
  .stack {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  aside {
    display: flex;
    flex-direction: column;
    gap: 12px;
    flex: 0 0 280px;
  }
</style>
