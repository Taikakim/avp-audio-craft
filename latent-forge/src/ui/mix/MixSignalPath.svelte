<script lang="ts">
  // Spec §4.5 MIX + SIGNAL PATH, v3:211-282. The MIXDOWN button here is UI ONLY this milestone --
  // M9 wires the actual commit job submission (spec §7.1), same boundary as OVERLAP-INPAINT's
  // render button (M1 plan:6282).
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { isQuad, mixTree, normalizedQuadWeights } from "../../lib/mix/mixMath";
  import { buildSignalPath, mergeSignalPath, signalKeyOf } from "../../lib/mix/signalPath";
  import { jobs } from "../../lib/render/jobs.svelte";
  import { mixdown, mixdownBlock, runMixdown, signalInputNow } from "../../lib/render/mixdown.svelte";
  import { HELP } from "../../lib/help/strings";
  import { mixdownLabel } from "../topbar/mixdown";

  const mix = $derived(arrangement.mix);
  const master = $derived(arrangement.master);
  const tree = $derived(mixTree(mix.order));
  const quad = $derived(isQuad(mix.order));
  const normalisedWeights = $derived(normalizedQuadWeights(mix.quad_weights));

  // M9 T4: one shared builder (signalInputNow) so the key a commit is stamped with and the key
  // compared here cannot disagree; the commit's real meta.stages reconcile with the estimate.
  const input = $derived(signalInputNow());
  const commitStages = () =>
    mixdown.stages === null || mixdown.key === null ? null : { key: mixdown.key, stages: mixdown.stages };
  const stages = $derived(mergeSignalPath(buildSignalPath(input), commitStages(), signalKeyOf(input)));
  const block = $derived(mixdownBlock());

  let expanded = $state(true);
</script>

<div class="mix-signal-path" data-tab-body="mix">
  {#if expanded}
    <div class="panels">
      <div class="order-panel">
        <div class="head">
          <button data-testid="mix-fold" data-help={HELP.mixFold} onclick={() => (expanded = false)}>▾</button>
          <span>MIX ORDER</span>
          <select aria-label="MIX ORDER" data-help={HELP.mixOrder} value={mix.order}
            onchange={(e) => (mix.order = (e.currentTarget as HTMLSelectElement).value as typeof mix.order)}>
            <option value="tree">(1+2) + (3+4)</option>
            <option value="cascade">((1+2)+3)+4</option>
            <option value="quad">weighted 4-way (lerp only)</option>
          </select>
        </div>

        {#if quad}
          <div class="quad-weights">
            {#each [0, 1, 2, 3] as i (i)}
              <!-- aria-label on the INPUT, not the <label>: findAllByLabelText returns the element
                   carrying it, and data-help lives on the input -->
              <label>
                LANE {i + 1} <span class="value">{normalisedWeights[i].toFixed(2)}</span>
                <input type="range" aria-label="quad weight — lane {i + 1}" min="0" max="1" step="0.01" data-help={HELP.mixQuadWeight}
                  value={mix.quad_weights[i]}
                  oninput={(e) => (mix.quad_weights[i] = Number((e.currentTarget as HTMLInputElement).value))} />
              </label>
            {/each}
          </div>
        {:else if tree}
          <div class="nodes">
            {#each tree as node (node.id)}
              <div class="node">
                <span class="label">{node.id}</span>
                <div class="interp">
                  <button data-testid="{node.id.toLowerCase()}-lerp" data-help={HELP.mixLerp}
                    class:on={mix.nodes[node.id].interp === "lerp"}
                    onclick={() => (mix.nodes[node.id].interp = "lerp")}>LERP</button>
                  <button data-testid="{node.id.toLowerCase()}-slerp" data-help={HELP.mixSlerp}
                    class:on={mix.nodes[node.id].interp === "slerp"}
                    onclick={() => (mix.nodes[node.id].interp = "slerp")}>SLERP</button>
                </div>
                <input type="range" aria-label="{node.id} position" data-help={HELP.mixNodeT}
                  min="0" max="1" step="0.01" value={mix.nodes[node.id].t}
                  oninput={(e) => (mix.nodes[node.id].t = Number((e.currentTarget as HTMLInputElement).value))} />
              </div>
            {/each}
          </div>
        {/if}
      </div>

      <div class="signal-panel">
        <span class="head">SIGNAL PATH <span class="live">live</span></span>
        <div class="stages">
          {#each stages as st (st.n)}
            <div class="stage" data-signal-stage data-lit={st.lit} data-help={HELP.signalPath} class:lit={st.lit}>
              <span class="n">{st.n}</span><span class="label">{st.label}</span><span class="note">{st.note}</span>
            </div>
          {/each}
        </div>
        <button class="mixdown" data-testid="mix-mixdown" data-help={HELP.mixdownButton}
          title={block ?? ""} disabled={jobs.busy || block !== null}
          onclick={() => void runMixdown()}>{mixdownLabel(jobs.busy, jobs.stepsLeft)}</button>
      </div>
    </div>
  {:else}
    <div class="summary">
      <button data-testid="mix-expand" data-help={HELP.mixExpand} onclick={() => (expanded = true)}>▸</button>
      <span>MIX + SIGNAL PATH</span>
      <span>{mix.order}</span>
      <span class="dim">{stages.filter((s) => s.lit).length}/{stages.length} lit</span>
      <div class="spacer"></div>
      <button class="mixdown" data-testid="mix-mixdown-folded" data-help={HELP.mixdownButton}
          title={block ?? ""} disabled={jobs.busy || block !== null}
          onclick={() => void runMixdown()}>{mixdownLabel(jobs.busy, jobs.stepsLeft)}</button>
    </div>
  {/if}
</div>

<style>
  .mix-signal-path { height: 100%; box-sizing: border-box; }
  .panels { display: flex; gap: 8px; height: 100%; }
  .order-panel, .signal-panel { flex: 1; min-width: 0; box-sizing: border-box; border: 1px solid var(--border); background: var(--panel); padding: 8px 10px; }
  .head { display: flex; align-items: center; gap: 8px; margin-bottom: 7px; font-size: 10px; color: var(--text-dim); }
  .nodes { display: flex; gap: 8px; }
  .node { flex: 1; box-sizing: border-box; border: 1px solid var(--border); padding: 6px; }
  .interp { display: flex; gap: 3px; margin-bottom: 5px; }
  button.on { background: var(--turq-strong); color: white; }
  .quad-weights { display: flex; gap: 12px; }
  .stages { display: flex; flex-direction: column; gap: 3px; }
  .stage { display: flex; gap: 6px; font-size: 10px; opacity: 0.4; }
  .stage.lit { opacity: 1; }
  .summary { display: flex; align-items: center; gap: 8px; height: 100%; }
  .spacer { flex: 1; }
</style>
