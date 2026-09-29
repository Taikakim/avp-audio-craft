<script lang="ts">
  import type { Snippet } from "svelte";

  // Spec §4.1: centre column = scrolling centre (flex 1, padding 10, gap 8) plus,
  // in WORKSPACE, the 248 px bottom pane.
  //
  // `position: relative` is load-bearing: it is the containing block for the
  // TERMINAL tab's FULL SCREEN mode (Task 11), which is `position: absolute;
  // inset: 0`. An absolutely positioned element is not clipped by ancestors that
  // are not in its containing-block chain, so the bottom pane's `overflow: hidden`
  // does not cut it off, and it covers the centre column and nothing else — which
  // is what spec §4.5 asks for, rather than v3's `inset: 42px 0 0 0` (line 2280)
  // that also covered the right pane.
  interface Props {
    centre: Snippet;
    bottom?: Snippet;
  }
  let { centre, bottom }: Props = $props();
</script>

<div class="centre-column" data-region="centre-column">
  <div class="scrolling-centre" data-region="centre">
    {@render centre()}
  </div>
  {#if bottom}{@render bottom()}{/if}
</div>

<style>
  .centre-column {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    position: relative;
  }
  .scrolling-centre {
    flex: 1;
    min-height: 0;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow: auto;
  }
</style>
