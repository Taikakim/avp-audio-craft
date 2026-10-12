// Registers @testing-library/jest-dom's matchers (toHaveValue, toHaveClass, toHaveAttribute, ...)
// on vitest's expect, for every test file. Importing it in a node-environment test is harmless.
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/svelte";
import { afterEach } from "vitest";

// vitest runs without `globals`, so @testing-library/svelte does NOT register its own auto-cleanup.
// Several plan-written DOM tests omit `afterEach(cleanup)`, so a render leaks into the next case in
// the file ("Found multiple elements"). cleanup() is idempotent, so a global one is harmless to the
// tests that already call it and fixes the ones that do not. (Electro-Sheep 1, M9 T5)
afterEach(() => cleanup());

// jsdom (25.x) returns a custom property from getComputedStyle only for the element that declares
// it -- it does NOT inherit `--tokens` down to descendants, which every real browser does and
// which the canvas panels rely on (panelColour reads `--text-dim` off the <canvas>, a descendant of
// wherever the theme tokens live). Walk up the ancestors for `--*` reads so tests see what a
// browser would. Every non-custom property goes through jsdom untouched. (Electro-Sheep 1,
// 2026-10-01: found twice -- SigmaGraph and XYPanel -- so fixed once, here.)
if (typeof window !== "undefined" && typeof window.getComputedStyle === "function") {
  const realGcs = window.getComputedStyle.bind(window);
  window.getComputedStyle = ((el: Element, pseudo?: string | null) => {
    const cs = realGcs(el, pseudo);
    return new Proxy(cs, {
      get(target, prop) {
        if (prop === "getPropertyValue") {
          return (name: string) => {
            if (!name.startsWith("--")) return target.getPropertyValue(name);
            for (let n: Element | null = el; n; n = n.parentElement) {
              const v = realGcs(n).getPropertyValue(name);
              if (v) return v;
            }
            return "";
          };
        }
        const v = Reflect.get(target, prop);
        return typeof v === "function" ? v.bind(target) : v;
      },
    });
  }) as typeof window.getComputedStyle;
}

// jsdom (25.x) has no PointerEvent, so @testing-library's fireEvent.pointerDown/Move/Up falls back
// to a bare Event that carries NO button/clientX/clientY -- a handler reading `e.button` or
// `e.clientY` then sees undefined and silently does nothing (found by the CHROMA middle-drag
// tests, Electro-Sheep 1). A MouseEvent subclass with pointerId is the standard polyfill: pointer
// handlers get real coordinates and buttons, which is all these tests exercise.
if (typeof window !== "undefined" && typeof (window as unknown as { PointerEvent?: unknown }).PointerEvent === "undefined") {
  class PointerEventPolyfill extends MouseEvent {
    readonly pointerId: number;
    readonly pointerType: string;
    constructor(type: string, init: MouseEventInit & { pointerId?: number; pointerType?: string } = {}) {
      super(type, init);
      this.pointerId = init.pointerId ?? 0;
      this.pointerType = init.pointerType ?? "mouse";
    }
  }
  (window as unknown as { PointerEvent: unknown }).PointerEvent = PointerEventPolyfill;
}
