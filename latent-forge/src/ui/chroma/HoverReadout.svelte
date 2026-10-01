<script lang="ts">
  // The hover readout (spec §5.4: 14 px note, 9 px detail; v3 338-341).
  //
  // DOM, as siblings of the canvas -- never fillText. A fillText label can
  // never be found by findByText, which was a blocking M4 finding, and the two
  // sizes the spec pins are CSS.
  //
  // No data-help: M1 T14's table has no id for the hover readout (v3 338), so
  // none is invented. See the plan's open questions.
  import {
    type ChromaHover,
    HOVER_DETAIL_PX,
    HOVER_NOTE_PX,
    hoverDetailText,
    hoverNoteText,
  } from "../../lib/chroma/hoverReadout";

  interface Props {
    hover: ChromaHover | null;
  }
  let { hover }: Props = $props();
</script>

{#if hover}
  <div class="readout">
    <div class="note" data-testid="chroma-hover-note" style="font-size:{HOVER_NOTE_PX}px">
      {hoverNoteText(hover)}
    </div>
    <div class="detail" data-testid="chroma-hover-detail" style="font-size:{HOVER_DETAIL_PX}px">
      {hoverDetailText(hover)}
    </div>
  </div>
{/if}

<style>
  .readout {
    flex-shrink: 0;
    margin-top: 3px;
    padding: 4px 6px;
    background: var(--panel2);
    border: 1px solid var(--border);
  }
  .note {
    font-weight: 600;
    line-height: 1.1;
    color: var(--purple-strong);
  }
  .detail {
    line-height: 1.35;
    color: var(--text-dim);
  }
</style>
