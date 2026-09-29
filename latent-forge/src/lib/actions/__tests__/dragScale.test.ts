// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { dragScale } from "../dragScale";

/**
 * jsdom has no PointerEvent constructor, and the action only reads button,
 * clientX, shiftKey and pointerId -- all of which MouseEvent carries.
 */
function pointer(type: string, init: { clientX?: number; button?: number; shiftKey?: boolean } = {}) {
  const ev = new MouseEvent(type, { bubbles: true, cancelable: true, button: 0, clientX: 0, ...init });
  Object.defineProperty(ev, "pointerId", { value: 1 });
  return ev;
}

function field() {
  const input = document.createElement("input");
  input.type = "text";
  document.body.appendChild(input);
  return input;
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("the action", () => {
  it("sets the ew-resize cursor (spec §5.1)", () => {
    const node = field();
    dragScale(node, { min: 60, max: 200, value: 120, onValue: () => {} });
    expect(node.style.cursor).toBe("ew-resize");
  });

  it("emits the spec §5.1 value while dragging", () => {
    const node = field();
    const onValue = vi.fn();
    dragScale(node, { min: 60, max: 200, value: 120, onValue });
    node.dispatchEvent(pointer("pointerdown", { clientX: 500 }));
    window.dispatchEvent(pointer("pointermove", { clientX: 630 })); // dx = 130
    expect(onValue).toHaveBeenLastCalledWith(190);
    window.dispatchEvent(pointer("pointerup", { clientX: 630 }));
  });

  it("goes fine with shift held", () => {
    const node = field();
    const onValue = vi.fn();
    dragScale(node, { min: 60, max: 200, value: 120, onValue });
    node.dispatchEvent(pointer("pointerdown", { clientX: 500 }));
    window.dispatchEvent(pointer("pointermove", { clientX: 630, shiftKey: true }));
    expect(onValue).toHaveBeenLastCalledWith(120.7);
    window.dispatchEvent(pointer("pointerup", { clientX: 630 }));
  });

  it("rounds an integer field and clamps at the top", () => {
    const node = field();
    const onValue = vi.fn();
    dragScale(node, { min: 1, max: 150, int: true, value: 24, onValue });
    node.dispatchEvent(pointer("pointerdown", { clientX: 0 }));
    window.dispatchEvent(pointer("pointermove", { clientX: 26 }));
    expect(onValue).toHaveBeenLastCalledWith(39);
    window.dispatchEvent(pointer("pointermove", { clientX: 5000 }));
    expect(onValue).toHaveBeenLastCalledWith(150);
    window.dispatchEvent(pointer("pointerup", { clientX: 5000 }));
  });

  it("a click without movement changes nothing and focuses the field for typing", () => {
    const node = field();
    const onValue = vi.fn();
    dragScale(node, { min: 60, max: 200, value: 120, onValue });
    node.dispatchEvent(pointer("pointerdown", { clientX: 400 }));
    window.dispatchEvent(pointer("pointermove", { clientX: 401 })); // 1 px is not a move
    window.dispatchEvent(pointer("pointerup", { clientX: 401 }));
    expect(onValue).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(node);
  });

  it("ignores every button but the primary one", () => {
    const node = field();
    const onValue = vi.fn();
    dragScale(node, { min: 60, max: 200, value: 120, onValue });
    node.dispatchEvent(pointer("pointerdown", { clientX: 500, button: 2 }));
    window.dispatchEvent(pointer("pointermove", { clientX: 630 }));
    expect(onValue).not.toHaveBeenCalled();
  });

  it("picks up a new range through update()", () => {
    const node = field();
    const onValue = vi.fn();
    const handle = dragScale(node, { min: 60, max: 200, value: 120, onValue });
    handle.update({ min: 0, max: 64, value: 6, onValue });
    node.dispatchEvent(pointer("pointerdown", { clientX: 0 }));
    window.dispatchEvent(pointer("pointermove", { clientX: 130 })); // half of 64
    expect(onValue).toHaveBeenLastCalledWith(38);
    window.dispatchEvent(pointer("pointerup", { clientX: 130 }));
  });

  it("stops listening after destroy()", () => {
    const node = field();
    const onValue = vi.fn();
    const handle = dragScale(node, { min: 60, max: 200, value: 120, onValue });
    handle.destroy();
    node.dispatchEvent(pointer("pointerdown", { clientX: 500 }));
    window.dispatchEvent(pointer("pointermove", { clientX: 630 }));
    expect(onValue).not.toHaveBeenCalled();
  });
});
