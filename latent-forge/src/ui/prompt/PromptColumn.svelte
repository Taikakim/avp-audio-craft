<script lang="ts">
  // Spec 4.5 item 1: the flex prompt textarea and the 34px negative prompt.
  // Reads and writes the SELECTED TARGET's own settings (spec 7.2) through the
  // settings store Task 1 of this milestone built -- with nothing attached,
  // settings.current(target) is session.defaults regardless of target, which
  // is correct until M5 attaches a source.
  import type { Target } from "../../lib/forge/types";
  import { HELP } from "../../lib/help/strings";
  import { settings } from "../../lib/stores/settings.svelte";

  interface Props {
    target: Target;
  }
  let { target }: Props = $props();

  const current = $derived(settings.current(target));

  function onPrompt(e: Event): void {
    settings.patch(target, { prompt: (e.target as HTMLTextAreaElement).value });
  }
  function onNegPrompt(e: Event): void {
    settings.patch(target, { negative_prompt: (e.target as HTMLTextAreaElement).value });
  }
</script>

<div class="prompt-column">
  <textarea
    class="prompt"
    data-testid="prompt-text"
    data-help={HELP.prompt}
    placeholder="describe the sound…"
    value={current.prompt}
    oninput={onPrompt}
  ></textarea>
  <textarea
    class="negative"
    data-testid="prompt-negative"
    data-help={HELP.negativePrompt}
    placeholder="negative prompt — what to steer away from"
    value={current.negative_prompt}
    oninput={onNegPrompt}
  ></textarea>
</div>

<style>
  .prompt-column {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .prompt,
  .negative {
    resize: none;
    box-sizing: border-box;
    background: var(--panel2);
    color: var(--text);
    border: 1px solid var(--border);
    padding: 5px 6px;
    font-size: 11px;
    font-family: inherit;
  }
  .prompt {
    flex: 1;
    min-height: 44px;
  }
  .negative {
    flex: 0 0 34px;
    padding: 3px 6px;
  }
</style>
