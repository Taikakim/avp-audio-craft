// Registers @testing-library/jest-dom's matchers (toHaveValue, toHaveClass, toHaveAttribute, ...)
// on vitest's expect, for every test file. Importing it in a node-environment test is harmless.
import "@testing-library/jest-dom/vitest";

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
