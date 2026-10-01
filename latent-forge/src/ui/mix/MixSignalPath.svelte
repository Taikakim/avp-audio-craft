<script lang="ts">
  // Spec §4.5 MIX + SIGNAL PATH, v3:211-282. The MIXDOWN button here is UI ONLY this milestone --
  // M9 wires the actual commit job submission (spec §7.1), same boundary as OVERLAP-INPAINT's
  // render button (M1 plan:6282).
  import { arrangement } from "../../lib/stores/arrangement.svelte";
  import { isQuad, mixTree, normalizedQuadWeights } from "../../lib/mix/mixMath";
  import { buildSignalPath, type SignalPathClip } from "../../lib/mix/signalPath";
  import { HELP } from "../../lib/help/strings";
  import { MIXDOWN_IDLE_LABEL } from "../topbar/mixdown";

  const mix = $derived(arrangement.mix);
  const master = $derived(arrangement.master);
  const tree = $derived(mixTree(mix.order));
  const quad = $derived(isQuad(mix.order));
  const normalisedWeights = $derived(normalizedQuadWeights(mix.quad_weights));

  const signalClips = $derived<SignalPathClip[]>(
    arrangement.clips.map((c) => ({
      lane: c.lane,
      isCropAudio: c.audio.kind === "crop",
      needsStretch: (c.native_bpm !== null && c.native_bpm !== arrangement.bpm) || c.detune_cents !== 0,
      a2aOn: c.a2a?.on ?? false,
    })),
  );
  const stages = $derived(
    buildSignalPath({
      lanes: arrangement.lanes.map((l) => ({ index: l.index, chain: l.chain })),
      clips: signalClips,
      overlapCount: arrangement.overlaps.length,
      mix, master,
    }),
  );

  let expanded = $state(true);

  function onMixdown() {
    // M9 wires the real `commit` job submission (spec §6.9, §7.1). No-op here on purpose.
  }
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
        <button class="mixdown" onclick={onMixdown} data-help={HELP.renderButton}>{MIXDOWN_IDLE_LABEL}</button>
      </div>
    </div>
  {:else}
    <div class="summary">
      <button data-testid="mix-expand" data-help={HELP.mixExpand} onclick={() => (expanded = true)}>▸</button>
      <span>MIX + SIGNAL PATH</span>
      <span>{mix.order}</span>
      <span class="dim">{stages.filter((s) => s.lit).length}/{stages.length} lit</span>
      <div class="spacer"></div>
      <button class="mixdown" onclick={onMixdown} data-help={HELP.renderButton}>{MIXDOWN_IDLE_LABEL}</button>
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
