<script lang="ts">
  // Owner: WINTERMUTE (created 2026-10-13)
  // MODEL NOTES: the census entry for the selected run (Misc/models_index_overrides.json, through
  // GET /models/notes) and an auto-saving notes box. The box writes ONE key, `forge_notes`; the
  // fields written at training/eval time (purpose, status, kim_feedback, ...) are shown read-only
  // and are never sent back, so nothing created automatically can be overwritten from here.
  // Last edited: WINTERMUTE 2026-10-14 — RATING 1..5 row (writes only `forge_rating`, saved on click)
  import { fetchModelNotes, saveModelNotes, saveModelRating, type ModelNotes } from "../../lib/forge/models";
  import { HELP } from "../../lib/help/strings";
  import { ratingColor } from "./modelOptions";

  let { label, onrated = () => {} }: { label: string; onrated?: (run: string, rating: number | null) => void } = $props();

  const FIELD_NAMES: Record<string, string> = {
    one_liner: "summary", purpose: "purpose", hypothesis: "hypothesis", status: "status",
    note: "evaluation", verdict: "verdict", kim_feedback: "Kim's feedback", recipe: "recipe",
  };
  const SAVE_DELAY_MS = 800;

  let open = $state(false);
  let notes = $state<ModelNotes | null>(null);
  let text = $state("");
  let status = $state("");
  let loadedFor = "";
  let timer: ReturnType<typeof setTimeout> | null = null;
  let dirty = false;
  let rating = $state<number | null>(null);
  let ratingStatus = $state("");

  // One rough axis: usefulness, sound quality, everything. Clicking the current rating clears it.
  async function rate(r: number): Promise<void> {
    if (!loadedFor) return;
    const l = loadedFor;
    const next = rating === r ? null : r;
    ratingStatus = "saving…";
    try {
      const saved = await saveModelRating(l, next);
      if (l !== loadedFor) return;
      rating = saved;
      ratingStatus = saved === null ? "cleared" : "saved";
      onrated(l, saved);
    } catch (e) {
      ratingStatus = `not saved: ${e instanceof Error ? e.message : String(e)}`;
    }
  }

  async function load(l: string): Promise<void> {
    notes = null;
    status = "loading…";
    try {
      const n = await fetchModelNotes(l);
      if (l !== label) return;          // the selection moved on while this was in flight
      notes = n;
      text = n.forge_notes;
      rating = n.forge_rating;
      ratingStatus = "";
      loadedFor = l;
      status = n.forge_notes_updated ? `saved ${n.forge_notes_updated}` : n.known ? "" : "no census entry yet";
    } catch (e) {
      status = e instanceof Error ? e.message : String(e);
    }
  }

  async function flush(): Promise<void> {
    if (timer) clearTimeout(timer);
    timer = null;
    if (!dirty || !loadedFor) return;
    dirty = false;
    const l = loadedFor;
    const t = text;
    status = "saving…";
    try {
      const at = await saveModelNotes(l, t);
      if (l === loadedFor) status = at ? `saved ${at}` : "cleared";
    } catch (e) {
      dirty = true;                     // kept: the next keystroke or close retries it
      status = `not saved: ${e instanceof Error ? e.message : String(e)}`;
    }
  }

  function onInput(e: Event): void {
    text = (e.currentTarget as HTMLTextAreaElement).value;
    dirty = true;
    status = "editing…";
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => void flush(), SAVE_DELAY_MS);
  }

  // A model switch while the box is open saves the old run's notes first, then reads the new run's.
  $effect(() => {
    const l = label;
    if (!open || l === loadedFor) return;
    void flush().then(() => load(l));
  });

  function toggle(): void {
    if (open) void flush();
    open = !open;
  }
</script>

<button class="btn" class:on={open} data-testid="model-notes-toggle" data-help={HELP.modelNotes}
  title="Census notes for this model" onclick={toggle}>NOTES</button>

{#if open}
  <div class="panel" data-testid="model-notes-panel">
    <div class="head">
      <span class="title">MODEL NOTES</span>
      <span class="run" title={label}>{label}</span>
      <button class="btn" onclick={toggle}>CLOSE</button>
    </div>
    {#if notes}
      <div class="fields">
        {#each Object.entries(notes.fields) as [k, v] (k)}
          <div class="field"><span class="k">{FIELD_NAMES[k] ?? k}</span><span class="v">{v}</span></div>
        {:else}
          <div class="empty">The census has nothing written about this run yet.</div>
        {/each}
      </div>
    {/if}
    <div class="rating" data-testid="model-rating">
      <span class="cap">RATING</span>
      {#each [1, 2, 3, 4, 5] as r (r)}
        <button class="rate" class:on={rating === r} disabled={!notes} data-testid={`model-rating-${r}`}
          style:--c={ratingColor(r)} title={rating === r ? "click again to clear" : `rate this run ${r} of 5`}
          onclick={() => void rate(r)}>{r}</button>
      {/each}
      <span class="hint">1 poor … 5 great: usefulness, sound, everything · saved as <code>forge_rating</code></span>
      <span class="status">{ratingStatus}</span>
    </div>
    <span class="cap">YOUR NOTES (saved to the census as <code>forge_notes</code>)</span>
    <textarea data-testid="model-notes-text" value={text} oninput={onInput} onblur={() => void flush()}
      disabled={!notes} placeholder="Anything about this model: what it is good for, settings that work…"
    ></textarea>
    <span class="status" data-testid="model-notes-status">{status}</span>
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
    flex-shrink: 0;
  }
  .btn.on {
    border-color: var(--turq-strong);
    color: var(--turq-strong);
  }
  /* fixed, not absolute: the top bar is overflow:hidden and would clip it */
  .panel {
    position: fixed;
    top: 46px;
    left: 50%;
    transform: translateX(-50%);
    width: min(640px, calc(100vw - 32px));
    max-height: calc(100vh - 80px);
    z-index: 50;
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 10px;
    background: var(--panel);
    border: 1px solid var(--turq-strong);
    box-shadow: 0 6px 24px rgb(0 0 0 / 0.35);
  }
  .head {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .title {
    font-size: 10px;
    letter-spacing: 0.08em;
    color: var(--turq-strong);
  }
  .run {
    flex: 1;
    min-width: 0;
    font-size: 11px;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .fields {
    overflow-y: auto;
    max-height: 40vh;
    display: flex;
    flex-direction: column;
    gap: 5px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 6px;
  }
  .field {
    display: grid;
    grid-template-columns: 96px 1fr;
    gap: 8px;
    font-size: 11px;
  }
  .k {
    color: var(--text-dim);
    font-size: 10px;
  }
  .v {
    color: var(--text);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .empty,
  .cap,
  .status {
    font-size: 10px;
    color: var(--text-dim);
  }
  .rating {
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .rate {
    width: 24px;
    height: 20px;
    background: var(--panel2);
    border: 1px solid var(--c);
    color: var(--c);
    font-family: inherit;
    font-size: 11px;
    font-weight: 700;
    cursor: pointer;
  }
  .rate.on {
    background: var(--c);
    color: var(--bg);
  }
  .hint {
    font-size: 10px;
    color: var(--text-dim);
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  textarea {
    min-height: 110px;
    resize: vertical;
    background: var(--panel2);
    color: var(--text);
    border: 1px solid var(--border);
    padding: 5px 6px;
    font-family: inherit;
    font-size: 11px;
  }
</style>
