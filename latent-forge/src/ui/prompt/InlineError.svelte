<script lang="ts">
  // Spec §9.7: "the target shows an inline one-line error under the target bar until the next
  // render". `jobs.lastError` is cleared by the next submit (M9 T1), which IS "until the next
  // render" -- nothing here needs a timer or a dismiss button.
  import { jobs } from "../../lib/render/jobs.svelte";

  interface Props {
    /** The same key the render control passes to jobs.submit. */
    targetKey: string;
  }
  let { targetKey }: Props = $props();

  // The GPU line is not a failure of THIS target, so it shows on every target, and an actual
  // error for this target outranks it.
  const text = $derived(
    jobs.lastError?.targetKey === targetKey
      ? jobs.lastError.message
      : jobs.gpuBusyOther !== null
        ? `GPU busy — ${jobs.gpuBusyOther}`
        : null,
  );
</script>

{#if text !== null}
  <div class="render-error" data-testid="render-error" role="status">{text}</div>
{/if}

<style>
  .render-error {
    font-size: 10px;
    color: var(--danger, var(--text-dim));
    padding: 2px 0 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>
