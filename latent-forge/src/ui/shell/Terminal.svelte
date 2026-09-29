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

  // Follow the tail unless the operator has scrolled up to read something.
  $effect(() => {
    const el = bodyEl;
    if (!el) return;
    void lines.length;
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 40) el.scrollTop = el.scrollHeight;
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
