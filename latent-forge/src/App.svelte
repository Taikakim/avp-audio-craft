<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import CropLibrary from "./lib/CropLibrary.svelte";
  import Inspector from "./lib/Inspector.svelte";
  import MasterStrip from "./lib/MasterStrip.svelte";
  import ServerPanel from "./lib/ServerPanel.svelte";
  import { project } from "./lib/store.svelte";
  import { view } from "./lib/stores/view.svelte";
  import Timeline from "./lib/Timeline.svelte";
  import TransportBar from "./lib/TransportBar.svelte";
  import BottomPane from "./ui/shell/BottomPane.svelte";
  import CentreColumn from "./ui/shell/CentreColumn.svelte";
  import ModuleShell from "./ui/shell/ModuleShell.svelte";
  import RightPane from "./ui/shell/RightPane.svelte";
  import TopBar from "./ui/shell/TopBar.svelte";
  import { forgeApi } from "./lib/forge/api";
  import { fetchAdapters } from "./lib/forge/models";
  import { buildModelOptions, type ModelOption } from "./ui/topbar/modelOptions";

  // Spec §9.1: the theme lives on the document element, so tokens.css's
  // `:root[data-theme="dark"]` block also reaches the root-level overlays.
  $effect(() => {
    document.documentElement.setAttribute("data-theme", view.theme);
  });

  // Top-bar contents (spec §4.2). Loading a session and recalling a preset are
  // M7's; M1 lists what the server has and remembers the selection.
  let sessions = $state<{ name: string; updated: number; n_clips: number }[]>([]);
  let session = $state("");
  let models = $state<ModelOption[]>(buildModelOptions([]));
  let model = $state("medium");
  let modelFolder = $state("");
  let masterPresets = $state<string[]>([]);
  let masterPreset = $state("");

  async function loadTopBar() {
    try {
      const s = await forgeApi.sessions();
      sessions = s.sessions;
      if (!session && sessions.length > 0) session = sessions[0].name;
    } catch {
      sessions = [];
    }
    try {
      masterPresets = (await forgeApi.presets("master")).names;
    } catch {
      masterPresets = [];
    }
    models = buildModelOptions(await fetchAdapters());
  }

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
    void loadTopBar();
  });
  onDestroy(() => {
    project.disconnect();
    window.removeEventListener("keydown", onKeydown);
  });
</script>

<div class="forge-root">
  <TopBar
    view={view.screen}
    onview={(v) => view.setView(v)}
    helpMode={view.helpOn}
    onhelp={() => view.toggleHelp()}
    theme={view.theme}
    ontheme={() => view.toggleTheme()}
    {sessions}
    {session}
    onsession={(name) => (session = name)}
    {models}
    {model}
    onmodel={(value) => {
      model = value;
      const picked = models.find((m) => m.value === value);
      if (picked?.ckptPath) modelFolder = picked.ckptPath;
    }}
    {modelFolder}
    onmodelfolder={(value) => (modelFolder = value)}
    {masterPresets}
    {masterPreset}
    onmasterpreset={(name) => (masterPreset = name)}
  />

  <div class="main-row">
    <CentreColumn>
      {#snippet centre()}
        {#if view.screen === "workspace"}
          <section class="centre-stack" data-region="workspace-centre">
            <TransportBar />
            <MasterStrip />
            <Timeline />
          </section>
        {:else}
          <!-- filled by the statistics-shell task of this milestone (spec §4.4) -->
          <section class="centre-stack" data-region="statistics-centre"></section>
        {/if}
      {/snippet}

      {#snippet bottom()}
        <BottomPane
          visible={view.screen === "workspace"}
          tab={view.bottomTab}
          ontab={(t) => view.setBottomTab(t)}
          terminalMode={view.terminal}
          onterminalmode={(m) => view.setTerminal(m)}
        />
      {/snippet}
    </CentreColumn>

    <RightPane open={view.sideOpen} ontoggle={() => view.toggleSide()}>
      <!-- ModuleShell's Normative props {id, title, lit}; ids are the view store's kebab
           ModuleId. Task 12 moves the first five into RightPaneModules.svelte. -->
      <ModuleShell id="overlap" title="OVERLAP — INPAINT" lit={false}>
        <!-- body: M7 (spec §4.6.1); its render button is wired in M9 -->
        <div class="module-empty"></div>
      </ModuleShell>

      <ModuleShell id="files" title="FILES" lit={project.clips.length > 0}>
        <CropLibrary />
      </ModuleShell>

      <ModuleShell id="lane-chain" title="LANE 1 CHAIN" lit={false}>
        <!-- body: M7 (spec §5.5); the header follows the active lane from M5 -->
        <div class="module-empty"></div>
      </ModuleShell>

      <ModuleShell id="advanced-sampling" title="ADVANCED SAMPLING" lit={false}>
        <!-- body: M4 (spec §5.3) -->
        <div class="module-empty"></div>
      </ModuleShell>

      <ModuleShell id="master-chain" title="MASTER CHAIN" lit={false}>
        <!-- body: M7 (spec §4.6.5) -->
        <div class="module-empty"></div>
      </ModuleShell>

      <ModuleShell id="legacy-inspector" title="INSPECTOR (legacy — M4 removes)" lit={false}>
        <Inspector />
      </ModuleShell>

      <ModuleShell id="legacy-server" title="SERVER (legacy — M9 removes)" lit={false}>
        <ServerPanel />
      </ModuleShell>
    </RightPane>
  </div>

  <!-- Spec §9.5: the raster border is a root-level overlay. M9 copies
       phosphor-border.js in and drives this canvas from steps_left_total. -->
  <canvas
    class="raster-border"
    data-region="raster-border"
    width="300"
    height="170"
    aria-hidden="true"
  ></canvas>

  <!-- HelpTooltip (spec §9.4) is Task 14's component; it and the rootEl/onRootMove
       mousemove machinery that feeds it are not built here (T9-T11 must not create
       HelpTooltip.svelte -- Normative-names table). Task 14 wires both together. -->
</div>

<style>
  :global(body) {
    margin: 0;
  }
  .forge-root {
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    position: relative;
    background: var(--bg);
    color: var(--text);
    font-family: "Space Grotesk", ui-monospace, monospace;
    font-size: 12px;
  }
  .main-row {
    flex: 1;
    min-height: 0;
    display: flex;
  }
  .centre-stack {
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-width: 0;
  }
  .module-empty {
    min-height: 0;
  }
  .raster-border {
    position: fixed;
    inset: 0;
    width: 100vw;
    height: 100vh;
    image-rendering: pixelated;
    pointer-events: none;
    z-index: 90;
  }
</style>
