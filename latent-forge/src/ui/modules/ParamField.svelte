<script lang="ts">
  // One right-pane parameter: a short title on one line, a slider, and a text field that shows the
  // value with its unit. Kim, 2026-10-09: "add text fields for all of the parameters in the right
  // hand view" and "the text is too large for the latch target, weight, start and end titles, they
  // wrap". The sliders were bare <label>s with the title inline, so a title longer than the slider's
  // leftover width broke onto a second line.
  //
  // The text field is the field that carries the parameter's full accessible name (`name`), and it
  // writes on every `input` event with a finite number, so typing "-12" and dragging the slider
  // both land in the chain immediately. A value typed outside the slider's range is kept (a target
  // beyond the head's mean ± 2σ is a legitimate thing to try); only `lo`..`hi`, the server's own
  // bounds, clamp it.
  interface Props {
    /** The visible title; short, it has 44 px and never wraps. */
    label: string;
    /** The full accessible name, e.g. "WEIGHT — slot 1". */
    name: string;
    value: number;
    onValue: (v: number) => void;
    /** The slider's range, in value units. */
    min: number;
    max: number;
    step?: number;
    /** Hard bounds for a typed value; default min..max. */
    lo?: number;
    hi?: number;
    unit?: string;
    /** Digits the text field shows. */
    decimals?: number;
    /** The text field shows value × factor (START / END are stored 0..1 and shown 0..100 %). */
    factor?: number;
    /** A non-linear slider: value → 0..1 and back. The text field is unaffected. */
    toPos?: (v: number) => number;
    fromPos?: (p: number) => number;
    /** A value to mark on the slider (a head's clean limit), and what the mark means. */
    mark?: number | null;
    markTitle?: string;
    /** A small line under the control; `warn` colours it. */
    note?: string;
    warn?: boolean;
    help?: string;
    disabled?: boolean;
  }
  let {
    label, name, value, onValue, min, max, step = 0.01, lo, hi, unit = "", decimals, factor = 1,
    toPos, fromPos, mark = null, markTitle = "", note = "", warn = false, help = "", disabled = false,
  }: Props = $props();

  const hardLo = $derived(lo ?? min);
  const hardHi = $derived(hi ?? max);
  const warped = $derived(toPos !== undefined && fromPos !== undefined);

  function clampTo(v: number): number {
    return v < hardLo ? hardLo : v > hardHi ? hardHi : v;
  }

  /** What the text field shows: value × factor at `decimals`, no float dust (0.30000000000000004). */
  function shown(v: number): number {
    const x = v * factor;
    return decimals === undefined ? Number(x.toPrecision(10)) : Number(x.toFixed(decimals));
  }

  /** A bound or step in the text field's unit (START / END: 0..1 stored, 0..100 shown). */
  function scaled(x: number): number {
    return Number((x * factor).toPrecision(10));
  }

  function onSlider(e: Event): void {
    const raw = Number((e.currentTarget as HTMLInputElement).value);
    onValue(warped ? (fromPos as (p: number) => number)(raw) : raw);
  }

  function onNumberInput(e: Event): void {
    const el = e.currentTarget as HTMLInputElement;
    // "" while a number is half typed ("-", "1e"): leave the chain alone until it parses
    if (el.value === "") return;
    const n = Number(el.value);
    if (Number.isFinite(n)) onValue(clampTo(n / factor));
  }

  function onNumberChange(e: Event): void {
    const el = e.currentTarget as HTMLInputElement;
    const n = Number(el.value);
    if (el.value === "" || !Number.isFinite(n)) {
      el.value = String(shown(value));   // an emptied field goes back to the value it had
      return;
    }
    const v = clampTo(n / factor);
    onValue(v);
    el.value = String(shown(v));          // shows the clamped / rounded value the chain now holds
  }

  const sliderPos = $derived(warped ? (toPos as (v: number) => number)(value) : value);
  const markPct = $derived.by(() => {
    if (mark === null || !Number.isFinite(mark)) return null;
    const p = warped ? (toPos as (v: number) => number)(mark) : (mark - min) / (max - min || 1);
    return p < 0 || p > 1 ? null : p;
  });
</script>

<div class="pf" class:off={disabled}>
  <span class="lbl" title={label}>{label}</span>
  <div class="track">
    <input
      type="range" class="slider" aria-label="{name} slider" data-help={help || undefined} {disabled}
      min={warped ? 0 : min} max={warped ? 1 : max} step={warped ? 0.001 : step}
      value={sliderPos} oninput={onSlider}
    />
    {#if markPct !== null}
      <span class="mark" title={markTitle} style:left="calc(6px + (100% - 12px) * {markPct})"></span>
    {/if}
  </div>
  <span class="num">
    <input
      type="number" class="field" aria-label={name} data-help={help || undefined} {disabled}
      min={scaled(min)} max={scaled(max)} step={scaled(step)}
      value={shown(value)} oninput={onNumberInput} onchange={onNumberChange}
    />
    <span class="unit">{unit}</span>
  </span>
  {#if note}<span class="note" class:warn title={note}>{note}</span>{/if}
</div>

<style>
  .pf {
    display: grid;
    grid-template-columns: 44px minmax(0, 1fr) 78px;
    align-items: center;
    column-gap: 6px;
    row-gap: 1px;
    min-width: 0;
  }
  .pf.off { opacity: 0.5; }
  .lbl {
    font-size: 9px;
    letter-spacing: 0.04em;
    color: var(--text-dim);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .track { position: relative; min-width: 0; display: flex; align-items: center; }
  .slider { width: 100%; min-width: 0; margin: 0; background: transparent; border: none; padding: 0; }
  .mark {
    position: absolute;
    top: 50%;
    width: 2px;
    height: 12px;
    transform: translate(-1px, -50%);
    background: var(--warm);
    pointer-events: none;
  }
  .num { display: flex; align-items: center; gap: 2px; min-width: 0; }
  .field {
    box-sizing: border-box;
    flex: 1 1 auto;
    min-width: 0;
    width: 52px;
    padding: 2px 3px;
    text-align: right;
    background: var(--panel2);
    border: 1px solid var(--border);
    color: var(--text);
    font-size: 10px;
    font-family: inherit;
    appearance: textfield;
    -moz-appearance: textfield;
  }
  .field::-webkit-inner-spin-button,
  .field::-webkit-outer-spin-button { appearance: none; -webkit-appearance: none; margin: 0; }
  .unit {
    flex: 0 0 20px;
    font-size: 9px;
    color: var(--text-dim);
    white-space: nowrap;
    overflow: hidden;
  }
  .note {
    grid-column: 2 / 4;
    font-size: 9px;
    color: var(--text-dim);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .note.warn { color: var(--warm); }
</style>
