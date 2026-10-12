<script lang="ts">
  // HELP mode (spec §9.4, §4.1). One listener on the window: with help on, the
  // closest [data-help] ancestor of the pointer target supplies the text, via
  // the shared `helpTextAt` lookup (T9's helpLookup.ts, kept out of this
  // component so it stays unit-testable without mounting the shell). Controls
  // therefore need nothing but `data-help={HELP.someId}` -- no per-control
  // wiring, and a control that forgets its string simply shows nothing.
  import { helpTextAt } from "./helpLookup";
  import { view } from "../../lib/stores/view.svelte";

  let text = $state<string | null>(null);
  let x = $state(0);
  let y = $state(0);
  let boxEl = $state<HTMLDivElement>();

  function onMove(e: MouseEvent) {
    if (!view.helpOn) {
      if (text !== null) text = null;
      return;
    }
    text = helpTextAt(e.target);
    x = e.clientX;
    y = e.clientY;
  }

  // Keep the box on screen at the right and bottom edges; the drawing did not
  // and the longest strings (LENGTH, SHAPE) run off a 1800 px window.
  // Reading #11 (2026-09-16): §9.4's "a 14px box" is the drawing's +14/+16
  // cursor offset (helpBoxStyle, v3 line 1794), not 14px type -- kept at 11px.
  const left = $derived(Math.max(4, Math.min(x + 14, window.innerWidth - (boxEl?.offsetWidth ?? 280) - 4)));
  const top = $derived(Math.max(4, Math.min(y + 16, window.innerHeight - (boxEl?.offsetHeight ?? 60) - 4)));

  $effect(() => {
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  });

  // Turning help off must clear a box that is already on screen.
  $effect(() => {
    if (!view.helpOn) text = null;
  });
</script>

{#if view.helpOn && text}
  <div class="help-box" data-testid="help-box" bind:this={boxEl} style="left: {left}px; top: {top}px">{text}</div>
{/if}

<style>
  /* Reading #12 (2026-09-16): the drawing's helpBoxStyle hardcodes two oklch
     values with no theme variant (v3 line 1794) -- they are not in §9.1's
     token list, so this component carries them as literals rather than
     resolving through custom properties. The dark override is this build's
     own addition (not in the drawing): at the light-mode values the box is
     already a dark chip, which reads fine against the light --bg (96%) but
     nearly merges into the dark theme's --bg/--panel range (17-26%), so dark
     mode lifts it clear of that band. Same two hues throughout, lightness and
     chroma only -- the rule tokens.css states for every other token. */
  .help-box {
    position: fixed;
    max-width: 280px;
    background: oklch(24% 0.02 250);
    color: oklch(96% 0.006 240);
    font-size: 11px;
    line-height: 1.45;
    padding: 7px 9px;
    z-index: 100;
    pointer-events: none;
  }

  :global(:root[data-theme="dark"]) .help-box {
    background: oklch(32% 0.035 250);
    color: oklch(94% 0.008 240);
  }
</style>
