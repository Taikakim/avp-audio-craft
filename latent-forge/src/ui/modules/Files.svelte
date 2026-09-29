<script lang="ts">
  // FILES (spec §4.6.2). Replaces the old CropLibrary: same job -- drag a
  // server-known item onto a lane -- but over /forge/files' roots rather than
  // the single /crops list.
  import { forgeApi } from "../../lib/forge/api";
  import type { AudioRef, LatentRef } from "../../lib/forge/types";
  import { HELP } from "../../lib/help/strings";

  interface Row {
    root: string;
    rel: string;
    kind: "audio" | "latent";
    size: number;
    mtime: number;
    ref: AudioRef | LatentRef;
  }

  let roots = $state<{ id: string; label: string; available: boolean }[]>([]);
  let root = $state("crops");
  let q = $state("");
  let rows = $state<Row[]>([]);
  let error = $state<string | null>(null);

  const rootLabel = $derived(roots.find((r) => r.id === root)?.label ?? root);

  $effect(() => {
    const selectedRoot = root;
    const filter = q.trim();
    let cancelled = false;
    forgeApi
      .files({ root: selectedRoot, q: filter || undefined, limit: 200 })
      .then((res) => {
        if (cancelled) return;
        roots = res.roots;
        rows = res.files as Row[];
        error = null;
      })
      .catch((e) => {
        if (cancelled) return;
        error = e instanceof Error ? e.message : String(e);
        rows = [];
      });
    return () => {
      cancelled = true;
    };
  });

  function onDragStart(e: DragEvent, row: Row) {
    e.dataTransfer?.setData("application/x-forge-ref", JSON.stringify(row.ref));
    // Kept so the existing Timeline drop handler keeps working unchanged until
    // M5 teaches it the ref payload.
    if (row.ref.kind === "crop") e.dataTransfer?.setData("text/sa3-crop-id", row.ref.crop_id);
    if (e.dataTransfer) e.dataTransfer.effectAllowed = "copy";
  }
</script>

<div class="files">
  <div class="root-head">{rootLabel}</div>
  <div class="controls">
    <select bind:value={root} aria-label="file root">
      {#each roots as r}
        <option value={r.id} disabled={!r.available}>{r.label}{r.available ? "" : " (unmounted)"}</option>
      {/each}
      {#if roots.length === 0}
        <option value={root}>{root}</option>
      {/if}
    </select>
    <input type="text" placeholder="filter" bind:value={q} aria-label="filter files" />
  </div>

  {#if error}
    <p class="msg err">{error}</p>
  {:else if rows.length === 0}
    <p class="msg">no files under this root</p>
  {/if}

  <div class="list">
    {#each rows as row (row.root + "/" + row.rel)}
      <div
        class="row"
        data-file-row
        data-help={HELP.filesRow}
        draggable="true"
        role="listitem"
        ondragstart={(e) => onDragStart(e, row)}
      >
        <span class="rel">{row.rel}</span>
        <span class="kind">{row.kind}</span>
      </div>
    {/each}
  </div>
</div>

<style>
  .files {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 4px 0 8px;
  }
  .root-head,
  .msg {
    margin: 0;
    padding: 2px 10px;
    font-size: 10px;
    color: var(--text-dim);
  }
  .msg.err {
    color: var(--red);
  }
  .controls {
    display: flex;
    gap: 4px;
    padding: 0 10px;
  }
  select,
  input {
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text);
    font-family: inherit;
    font-size: 10px;
    padding: 2px 4px;
    min-width: 0;
    flex: 1;
  }
  .list {
    display: flex;
    flex-direction: column;
    max-height: 240px;
    overflow-y: auto;
  }
  .row {
    display: flex;
    gap: 6px;
    padding: 4px 10px;
    font-size: 11px;
    cursor: grab;
    border-left: 2px solid transparent;
  }
  .row:hover {
    border-left-color: var(--turq-strong);
    background: var(--panel2);
  }
  .rel {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .kind {
    color: var(--text-dim);
    font-size: 9px;
    letter-spacing: 0.04em;
  }
</style>
