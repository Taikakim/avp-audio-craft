<script lang="ts">
  // Spec §4.5: log lines, a busy status dot (turquoise while /status.busy) and the
  // three modes. Props-driven; Task 11 supplies `lines` and `busy` from the log
  // store and mounts this in the bottom pane's TERMINAL tab.
  type TerminalMode = "collapsed" | "pane" | "full";

  interface Props {
    mode: TerminalMode;
    busy: boolean;
    lines: { seq: number; text: string; tone: string }[];
    onmode: (m: TerminalMode) => void;
  }
  let { mode, busy, lines, onmode }: Props = $props();

  let bodyEl = $state<HTMLDivElement>();
  let stickToBottom = true;

  // "Am I near the bottom" has to be measured BEFORE the DOM grows with the new lines, or the
  // check is comparing against geometry that already includes them -- scrollHeight has already
  // grown, so a poll that adds more than ~2-3 lines (over ~40px) reads as "not near the bottom"
  // even though the operator genuinely was, and auto-follow silently stops. $effect.pre runs
  // before that DOM update (unlike a plain $effect, which runs after), so it captures the real
  // pre-growth answer. `stickToBottom` starts true, which also covers the very first render --
  // bodyEl may not be bound yet the first time this runs, and "not yet scrolled" should stick.
  $effect.pre(() => {
    void lines.length;
    const el = bodyEl;
    stickToBottom = !el || el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  });

  // Runs after the DOM has updated. Follows the tail -- including on mount, where scrollTop
  // otherwise defaults to 0 and a remount with a full backlog (e.g. switching back to the
  // TERMINAL tab with up to 400 lines already loaded) would land on the OLDEST lines instead
  // of jumping to the newest.
  $effect(() => {
    const el = bodyEl;
    if (!el) return;
    void lines.length;
    if (stickToBottom) el.scrollTop = el.scrollHeight;
  });
</script>

<div class="terminal" class:full={mode === "full"} data-region="terminal" data-mode={mode}>
  <div class="head">
    <span class="label">TERMINAL</span>
    <span class="dot" data-testid="terminal-dot" data-busy={busy ? "true" : "false"}></span>
    <div class="spacer"></div>
    <button class:on={mode === "collapsed"} onclick={() => onmode("collapsed")}>COLLAPSE</button>
    <button class:on={mode === "pane"} onclick={() => onmode("pane")}>PANE</button>
    <button class:on={mode === "full"} onclick={() => onmode("full")}>FULL SCREEN</button>
  </div>
  {#if mode !== "collapsed"}
    <div class="body" data-testid="terminal-body" bind:this={bodyEl}>
      {#each lines as line (line.seq)}
        <div class="line" data-tone={line.tone}>{line.text}</div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .terminal {
    box-sizing: border-box;
    height: 100%;
    min-height: 0;
    display: flex;
    flex-direction: column;
    background: var(--panel);
    border: 1px solid var(--border);
  }
  .terminal.full {
    position: absolute;
    inset: 0;
    z-index: 40;
    height: auto;
  }
  .head {
    height: 24px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 10px;
    background: var(--panel2);
    border-bottom: 1px solid var(--border);
  }
  .label {
    font-size: 10px;
    color: var(--text-dim);
    letter-spacing: 0.08em;
  }
  .dot {
    width: 6px;
    height: 6px;
    border: 1px solid var(--border);
    background: transparent;
    flex-shrink: 0;
  }
  .dot[data-busy="true"] {
    background: var(--turq-strong);
    border-color: var(--turq-strong);
  }
  .spacer {
    flex: 1;
  }
  .head button {
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-dim);
    font-family: inherit;
    font-size: 10px;
    letter-spacing: 0.04em;
    padding: 2px 8px;
    cursor: pointer;
  }
  .head button.on {
    background: var(--panel);
    border-color: var(--turq-strong);
    color: var(--turq-strong);
  }
  .body {
    flex: 1;
    min-height: 0;
    overflow: auto;
    padding: 6px 10px;
  }
  .line {
    font-family: ui-monospace, monospace;
    font-size: 11px;
    line-height: 1.6;
    white-space: pre;
    color: var(--text);
  }
  .line[data-tone="dim"] {
    color: var(--text-dim);
  }
  .line[data-tone="accent"] {
    color: var(--purple-strong);
  }
  .line[data-tone="error"] {
    color: var(--red);
  }
</style>
