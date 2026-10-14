<script lang="ts">
  // Owner: WINTERMUTE (created 2026-10-13)
  // TEST PROMPTS: the model-matrix test prompts (render presets test-*, written by
  // eval/forge/make_test_prompt_presets.py) in one list with their text and seed visible, so the
  // exact board prompt + seed is one click away. The same presets are also in SETTINGS PRESET.
  import { forgeApi } from "../../lib/forge/api";
  import { HELP } from "../../lib/help/strings";
  import { applyRenderPreset, presetComment, TEST_PREFIX } from "../../lib/presets/renderPresets";
  import { promptNotes } from "../../lib/stores/promptNotes.svelte";
  import { settings } from "../../lib/stores/settings.svelte";
  import type { Target } from "../../lib/forge/types";

  let { target }: { target: Target } = $props();

  interface Entry { name: string; id: string; prompt: string; seed: number | null; notes: string; body: unknown }

  let open = $state(false);
  let entries = $state<Entry[] | null>(null);
  let message = $state("");
  let pos = $state({ left: 0, bottom: 0 });
  let btn = $state<HTMLButtonElement>();

  async function load(): Promise<void> {
    message = "loading…";
    try {
      const names = (await forgeApi.presets("render")).names.filter((n) => n.startsWith(TEST_PREFIX));
      const bodies = await Promise.all(names.map((n) => forgeApi.preset("render", n).catch(() => null)));
      entries = names.map((name, i) => {
        const b = (bodies[i] ?? {}) as Record<string, unknown>;
        return {
          name, id: name.slice(TEST_PREFIX.length),
          prompt: typeof b.prompt === "string" ? b.prompt : "",
          seed: typeof b.seed === "number" ? b.seed : null,
          notes: presetComment(b), body: bodies[i],
        };
      }).filter((e) => e.body !== null);
      message = entries.length ? "" : "no test-* presets — run eval/forge/make_test_prompt_presets.py";
    } catch (e) {
      message = e instanceof Error ? e.message : String(e);
    }
  }

  function toggle(): void {
    open = !open;
    if (open) {
      const r = btn?.getBoundingClientRect();
      // fixed and opening upward: the prompt tab sits at the bottom of the window in a short pane
      if (r) pos = { left: Math.max(8, Math.min(r.left, window.innerWidth - 568)), bottom: window.innerHeight - r.top + 4 };
      if (entries === null) void load();
    }
  }

  function pick(e: Entry): void {
    const r = applyRenderPreset(settings.editable(target), e.body);
    promptNotes.showComment(e.name, e.notes);
    message = r.rejected.length ? `ignored: ${r.rejected.join(", ")}` : "";
    if (!r.rejected.length) open = false;
  }
</script>

<button bind:this={btn} class="btn" class:on={open} data-testid="test-prompts-toggle"
  data-help={HELP.testPrompts} onclick={toggle}>TEST</button>

{#if open}
  <div class="menu" data-testid="test-prompts-menu" style:left="{pos.left}px" style:bottom="{pos.bottom}px">
    <div class="head">
      <span>MODEL-MATRIX TEST PROMPTS · exact text + seed · CFG 7 · 20 s</span>
      <button class="btn" onclick={() => (open = false)}>CLOSE</button>
    </div>
    {#if message}<div class="msg">{message}</div>{/if}
    <div class="list">
      {#each entries ?? [] as e (e.name)}
        <button class="row" title={`${e.prompt}\n\n${e.notes}`} onclick={() => pick(e)}>
          <span class="id">{e.id}</span>
          <span class="seed">{e.seed ?? "?"}</span>
          <span class="text">{e.prompt}</span>
        </button>
      {/each}
    </div>
  </div>
{/if}

<style>
  .btn {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text-dim);
    font-family: inherit;
    font-size: 10px;
    padding: 3px 6px;
    cursor: pointer;
  }
  .btn.on {
    border-color: var(--turq-strong);
    color: var(--turq-strong);
  }
  .menu {
    position: fixed;
    z-index: 50;
    width: min(560px, calc(100vw - 16px));
    max-height: min(60vh, 520px);
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 8px;
    background: var(--panel);
    border: 1px solid var(--turq-strong);
    box-shadow: 0 6px 24px rgb(0 0 0 / 0.35);
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 10px;
    color: var(--turq-strong);
    letter-spacing: 0.04em;
  }
  .msg {
    font-size: 10px;
    color: var(--text-dim);
  }
  .list {
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }
  .row {
    display: grid;
    grid-template-columns: 110px 86px 1fr;
    gap: 8px;
    text-align: left;
    background: transparent;
    border: 0;
    border-bottom: 1px solid var(--border);
    color: var(--text);
    font-family: inherit;
    font-size: 11px;
    padding: 4px 2px;
    cursor: pointer;
  }
  .row:hover {
    background: var(--panel2);
  }
  .id {
    color: var(--turq-strong);
  }
  .seed {
    color: var(--text-dim);
    font-variant-numeric: tabular-nums;
  }
  .text {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>
