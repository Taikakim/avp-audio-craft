// use:dragScale={{ min, max, int, value, onValue }} -- spec §5.1.
//
// Pointer events, not mouse events, so a pen or a touch drag works the same. The
// arithmetic lives in lib/math/dragScale.ts; this file only turns pointer motion
// into calls to it.

import { dragValue, hasMoved } from "../math/dragScale";

export interface DragScaleOptions {
  min: number;
  max: number;
  /** whole numbers only (steps, seed, plateaus, detune cents, overlap steps) */
  int?: boolean;
  /** the field's current value; read at pointerdown as the drag's origin */
  value: number;
  onValue: (next: number) => void;
}

export function dragScale(node: HTMLElement, options: DragScaleOptions) {
  let opts = options;
  let startX = 0;
  let startVal = 0;
  let moved = false;
  let dragging = false;

  node.style.cursor = "ew-resize";

  function onPointerMove(ev: Event): void {
    if (!dragging) return;
    const m = ev as MouseEvent;
    const dx = m.clientX - startX;
    if (hasMoved(dx)) moved = true;
    if (!moved) return;
    opts.onValue(dragValue({ startVal, dx, min: opts.min, max: opts.max, int: opts.int, shift: m.shiftKey }));
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
    dragging = true;
    moved = false;
    startX = m.clientX;
    startVal = opts.value;
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
      node.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    },
  };
}
