<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { installGlobalKeys } from "./lib/actions/keyboard";
  import Inspector from "./lib/Inspector.svelte";
  import ServerPanel from "./lib/ServerPanel.svelte";
  import { project } from "./lib/store.svelte";
  import { cloneRenderSettings } from "./lib/forge/defaults";
  import { SessionController } from "./lib/forge/sessionController.svelte";
  import { arrangement } from "./lib/stores/arrangement.svelte";
  import { settings } from "./lib/stores/settings.svelte";
  import { playback } from "./lib/stores/transport.svelte";
  import { view } from "./lib/stores/view.svelte";
  import MasterStrip from "./ui/master/MasterStrip.svelte";
  import Timeline from "./ui/timeline/Timeline.svelte";
  import BottomPane from "./ui/shell/BottomPane.svelte";
  import CentreColumn from "./ui/shell/CentreColumn.svelte";
  import HelpTooltip from "./ui/shell/HelpTooltip.svelte";
  import ModuleShell from "./ui/shell/ModuleShell.svelte";
  import RightPane from "./ui/shell/RightPane.svelte";
  import TopBar from "./ui/shell/TopBar.svelte";
  import { forgeApi } from "./lib/forge/api";
  import { logStore } from "./lib/stores/log.svelte";
  import { createRasterDriver, type RasterDriver } from "./lib/fx/rasterBorder";
  import { jobs } from "./lib/render/jobs.svelte";
  import { fetchAdapters } from "./lib/forge/models";
  import { buildModelOptions, type ModelOption } from "./ui/topbar/modelOptions";

  // Spec §9.1: the theme lives on the document element, so tokens.css's
  // `:root[data-theme="dark"]` block also reaches the root-level overlays.
  $effect(() => {
    document.documentElement.setAttribute("data-theme", view.theme);
  });

  // Top-bar contents (spec §4.2). The session name and every load/import/save/recall live in
  // SessionController (M7 T9); this holds only the lists the TopBar shows.
  let sessions = $state<{ name: string; updated: number; n_clips: number }[]>([]);
  let models = $state<ModelOption[]>(buildModelOptions([]));
  let model = $state("medium");
  let modelFolder = $state("");
  let masterPresets = $state<string[]>([]);
  let masterPreset = $state("");

  async function loadTopBar() {
    try {
      const s = await forgeApi.sessions();
      sessions = s.sessions;
    } catch {
      sessions = [];
    }
    try {
      masterPresets = (await forgeApi.presets("master")).names;
    } catch {
      masterPresets = [];
    }
    models = buildModelOptions(await fetchAdapters());
    try {
      // Show the backbone the server really runs. At start-up (no session load owns the stage yet)
      // also put MODEL STAGE on the matching side, so POST/BASE defaults match the loaded model.
      const b = await forgeApi.backbone();
      settings.activeBackbone = b.active;
      if (!settings.stageLocked && !settings.stageRebuilding) {
        const stage = b.objective === "rf_denoiser" ? "POST" : "BASE";
        if (stage !== settings.stage) settings.setStage(stage);
      }
    } catch {
      /* server down: the select keeps its last value */
    }
  }

  // Follow every successful backbone switch (top bar, MODEL STAGE, session load).
  $effect(() => {
    if (settings.activeBackbone) model = settings.activeBackbone;
  });

  /** A backbone picked in the top bar is a real switch: POST /forge/backbone, then MODEL STAGE
   *  follows the model's objective (distilled rf_denoiser -> POST defaults, base -> BASE). Refused
   *  while a session load or a STAGE rebuild owns the stage -- the same locks MODEL STAGE honours. */
  async function switchBackbone(id: string): Promise<void> {
    const previous = settings.activeBackbone ?? model;
    if (settings.stageLocked || settings.stageRebuilding) {
      model = previous;
      logStore.appendLocal("[forge] backbone switch refused: a session load or STAGE rebuild is in flight", "error");
      return;
    }
    settings.stageRebuilding = true;
    try {
      const r = await forgeApi.setBackbone(id);
      settings.activeBackbone = r.active;
      const stage = r.objective === "rf_denoiser" ? "POST" : "BASE";
      if (stage !== settings.stage) settings.setStage(stage);
      logStore.appendLocal(`[forge] backbone ${previous} -> ${r.active} (${r.rebuild_sec}s)`);
    } catch (e) {
      model = previous;
      logStore.appendLocal(`[forge] backbone switch to ${id} failed: ${e instanceof Error ? e.message : String(e)}`, "error");
    } finally {
      settings.stageRebuilding = false;
    }
  }

  // M4's seam (M4 T1 `attach`) + M5's source (M5 T1 `settingsSource`, never seeding): PROMPT +
  // SIGMA and ADVANCED SAMPLING now read and write the selected clip's / overlap's own `render`,
  // not always session.defaults. Once, at startup; M4 and M5 cannot import each other (§12), so
  // the composition root joins them (reconcile pass 2026-09-25).
  settings.attach(arrangement.settingsSource);
  // ... and a new clip starts from the session defaults, which follow STAGE (M4 setStage), not from
  // BASE_DEFAULTS: under POST a BASE-seeded clip showed and saved BASE's steps/sampler/schedule
  // (critic follow-up #4; Task 3's hook, tested in arrangementMixMaster.test.ts).
  arrangement.renderSeed = () => cloneRenderSettings(settings.defaults);

  // Task 9's load/import/save order lives here, unit-tested (sessionController.test.ts).
  const sessionCtl = new SessionController({
    api: forgeApi,
    log: (text, level) => view.appendLog(text, level),
    prompt: (message) => window.prompt(message, ""),
    confirm: (message) => window.confirm(message),
    // The lists the TopBar shows; a name created in another tab since they loaded is not known here.
    exists: (kind, name) =>
      kind === "session" ? sessions.some((s) => s.name === name) : masterPresets.includes(name),
  });

  // Autosave (spec §9.2): 2 s after the last change, to the current session -- only once that
  // session has been loaded or explicitly saved. observe() reads every saved field through
  // serializeProject's $state.snapshot, so this re-runs on ANY in-place edit (Global Constraint #1).
  $effect(() => {
    sessionCtl.observe();
  });

  async function saveSession() {
    const name = await sessionCtl.saveSession();
    if (name && !sessions.some((s) => s.name === name)) {
      // `updated` in epoch SECONDS (a float), the server's own unit (file mtime; WINTERMUTE 2026-09-25).
      sessions = [...sessions, { name, updated: Date.now() / 1000, n_clips: arrangement.clips.length }];
    }
  }

  // The recall is refused mid-load, dropped if a load started during its fetch, and validated whole
  // before its first write -- all in the controller (critic pass 3 #2, #12). The name is highlighted
  // only once it applied; the TopBar select snaps back until then.
  async function loadMasterPreset(name: string) {
    if (await sessionCtl.recallMasterPreset(name)) masterPreset = name;
  }

  async function saveMasterPreset() {
    const name = await sessionCtl.saveMasterPreset(masterPreset);
    if (!name) return;
    masterPreset = name;
    if (!masterPresets.includes(name)) masterPresets = [...masterPresets, name];
  }

  // M9 T2: the C64 raster border (spec 9.5). Reads jobs.active and writes nothing reactive -- the
  // only state this effect touches is the non-rune `raster` handle and the canvas itself.
  let rasterCanvas = $state<HTMLCanvasElement | null>(null);
  let raster: RasterDriver | null = null;
  // A job that is accepted but has not reported yet must still light the border, and
  // sweepHzFor maps a zero steps_total to SWEEP_START (never NaN).
  const EMPTY_PROGRESS = {
    job_id: "", op: "", stage: "", stage_index: 0, stage_count: 0,
    step: 0, steps: 0, steps_left_total: 0, steps_total: 0,
  } as const;
  $effect(() => {
    const active = jobs.active;
    if (rasterCanvas === null) return;
    raster ??= createRasterDriver(rasterCanvas);
    raster.update(active === null ? null : active.progress ?? { ...EMPTY_PROGRESS });
  });
  $effect(() => () => { raster?.stop(); raster = null; });

  let disposeKeys: (() => void) | null = null;

  onMount(() => {
    // §9.7 "GPU busy — <job_id>": jobs.gpuBusyOther only updates while this runs. The method
    // existed but nothing started it (review 2026-10-01).
    jobs.startStatusPolling();
    // project.connect() is unrelated to C1: it is the legacy ServerPanel's
    // render-server connectivity poll, not arrangement/clip state, so it stays.
    project.connect();
    // C1 fix wave: these four were still driving the v1 `project` store (an
    // always-empty transport/selection since Task 5) instead of the stores
    // this milestone actually built -- Space/Home controlled a transport with
    // no clips, and Delete checked a selectedClipId that is never set.
    disposeKeys = installGlobalKeys({
      togglePlay: () => playback.togglePlay(),
      rewind: () => playback.seek(0),
      deleteSelected: () => {
        if (view.selection.kind === "clip") {
          arrangement.removeClip(view.selection.id);
          view.select({ kind: "none" });
        }
      },
      zoomBy: (f) => arrangement.zoomBy(f),
    });
    void loadTopBar();
  });

  onDestroy(() => {
    jobs.stopStatusPolling();
    project.disconnect();
    disposeKeys?.();
    disposeKeys = null;
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
    session={sessionCtl.session}
    loadingName={sessionCtl.loadingName}
    onsession={(name) => sessionCtl.loadSession(name)}
    onsessionsave={saveSession}
    onimportv1={(file) => sessionCtl.importProjectFile(file)}
    {models}
    {model}
    onmodel={(value) => {
      model = value;
      const picked = models.find((m) => m.value === value);
      if (picked?.group === "backbone") void switchBackbone(value);
      else if (picked?.ckptPath) modelFolder = picked.ckptPath;
    }}
    {modelFolder}
    onmodelfolder={(value) => (modelFolder = value)}
    {masterPresets}
    {masterPreset}
    onmasterpreset={loadMasterPreset}
    onmasterpresetsave={saveMasterPreset}
    mixdownBusy={jobs.busy}
    mixdownStepsLeft={jobs.stepsLeft}
  />

  <div class="main-row">
    <CentreColumn>
      {#snippet centre()}
        {#if view.screen === "workspace"}
          <section class="centre-stack" data-region="workspace-centre">
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
           ModuleId. Task 12 moved the five spec modules into RightPaneModules.svelte
           (mounted inside RightPane itself); only the two legacy modules stay here. -->
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
    bind:this={rasterCanvas}
    class="raster-border"
    data-region="raster-border"
    width="300"
    height="170"
    aria-hidden="true"
  ></canvas>

  <!-- HelpTooltip (spec §9.4) is self-contained: it owns its own window mousemove
       listener and reads view.helpOn directly, so no rootEl/onRootMove wiring is
       needed here (T9-T11 must not create HelpTooltip.svelte -- Normative-names
       table; T14 owns and mounts it). -->
  <HelpTooltip />
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
