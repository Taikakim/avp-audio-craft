// use:dragScale={{ min, max, int, value, onValue }} -- spec §5.1.
//
// Pointer events, not mouse events, so a pen or a touch drag works the same. The
// arithmetic lives in lib/math/dragScale.ts; this file only turns pointer motion
// into calls to it.

import { clamp, dragRaw, hasMoved, inertiaMs, quantize, settleDistance } from "../math/dragScale";

export interface DragScaleOptions {
  min: number;
  max: number;
  /** whole numbers only (steps, seed, plateaus, detune cents, overlap steps) */
  int?: boolean;
  /** the field's current value; read at pointerdown as the drag's origin */
  value: number;
  onValue: (next: number) => void;
  /**
   * Time constant (ms) of the glide the value follows the pointer with. 0 = exactly under the
   * pointer. Left out, ranges wider than 1 000 (SEED) glide and everything else does not.
   */
  inertia?: number;
}

export function dragScale(node: HTMLElement, options: DragScaleOptions) {
  let opts = options;
  let startX = 0;
  let startVal = 0;
  let moved = false;
  let dragging = false;

  // The glide: `want` is where the pointer is, `shown` is where the value is, and each frame closes a
  // fraction of the gap. It keeps running after the button is released, so the value settles on the
  // release point instead of stopping dead part-way.
  let want = 0;
  let shown = 0;
  let shiftNow = false;
  let raf = 0;
  let lastFrame = 0;
  let lastEmitted: number | null = null;

  node.style.cursor = "ew-resize";

  function emit(raw: number): void {
    const v = quantize(raw, { min: opts.min, max: opts.max, int: opts.int, shift: shiftNow });
    if (v === lastEmitted) return;
    lastEmitted = v;
    opts.onValue(v);
  }

  function frame(now: number): void {
    const tau = inertiaMs(opts);
    const a = tau > 0 ? 1 - Math.exp(-Math.max(0, now - lastFrame) / tau) : 1;
    lastFrame = now;
    shown += (want - shown) * a;
    if (Math.abs(want - shown) <= settleDistance(opts.min, opts.max, opts.int)) {
      shown = want;
      raf = 0;
      emit(shown);
      return;
    }
    emit(shown);
    raf = requestAnimationFrame(frame);
  }

  function stopGlide(): void {
    if (raf && typeof cancelAnimationFrame === "function") cancelAnimationFrame(raf);
    raf = 0;
  }

  function onPointerMove(ev: Event): void {
    if (!dragging) return;
    const m = ev as MouseEvent;
    const dx = m.clientX - startX;
    if (hasMoved(dx)) moved = true;
    if (!moved) return;
    shiftNow = m.shiftKey;
    const raw = clamp(
      dragRaw({ startVal, dx, min: opts.min, max: opts.max, shift: m.shiftKey }), opts.min, opts.max,
    );
    if (inertiaMs(opts) > 0 && typeof requestAnimationFrame === "function") {
      want = raw;
      if (!raf) {
        lastFrame = typeof performance !== "undefined" ? performance.now() : 0;
        raf = requestAnimationFrame(frame);
      }
    } else {
      want = shown = raw;
      emit(raw);
    }
  }

  function onPointerUp(): void {
    if (!dragging) return;
    dragging = false;
    window.removeEventListener("pointermove", onPointerMove);
    window.removeEventListener("pointerup", onPointerUp);
    if (moved) return;
    // Mouse-up without movement focuses the input for typing (spec §5.1). The
    // action is applied to inputs directly and to wrappers that contain one.
    const input = node instanceof HTMLInputElement ? node : node.querySelector("input");
    if (input) {
      input.focus();
      input.select();
    } else {
      node.focus();
    }
  }

  function onPointerDown(ev: Event): void {
    const m = ev as MouseEvent;
    if (m.button !== 0) return;             // primary button only (spec §5.1)
    stopGlide();
    dragging = true;
    moved = false;
    startX = m.clientX;
    startVal = opts.value;
    want = shown = startVal;
    lastEmitted = null;
    try {
      (node as HTMLElement & { setPointerCapture?: (id: number) => void }).setPointerCapture?.(
        (m as MouseEvent & { pointerId?: number }).pointerId ?? 1,
      );
    } catch {
      // jsdom and non-pointer environments: capture is an optimisation, not a need
    }
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    // stop the drag from selecting the label text next to the field
    ev.preventDefault();
  }

  node.addEventListener("pointerdown", onPointerDown);

  return {
    update(next: DragScaleOptions): void {
      opts = next;
    },
    destroy(): void {
      stopGlide();
      node.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    },
  };
}
