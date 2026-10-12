// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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

describe("inertia", () => {
  // A hand-driven animation clock: nothing moves until frame() is called.
  let now = 0;
  let queue: FrameRequestCallback[] = [];
  function frame(ms = 16): void {
    now += ms;
    const run = queue;
    queue = [];
    run.forEach((cb) => cb(now));
  }
  function settle(): void {
    for (let i = 0; i < 400 && queue.length; i++) frame();
  }

  beforeEach(() => {
    now = 0;
    queue = [];
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => (queue.push(cb), queue.length));
    vi.stubGlobal("cancelAnimationFrame", () => { queue = []; });
    vi.spyOn(performance, "now").mockImplementation(() => now);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("does not jump: a seed drag has moved only part-way after one frame and ends on the pointer's value", () => {
    const node = field();
    const onValue = vi.fn();
    dragScale(node, { min: 0, max: 999999, int: true, value: 1000, onValue });
    node.dispatchEvent(pointer("pointerdown", { clientX: 0 }));
    window.dispatchEvent(pointer("pointermove", { clientX: 26 }));       // asks for 1000 + 500
    expect(onValue).not.toHaveBeenCalled();                              // nothing before the first frame
    frame(16);
    const first = onValue.mock.calls.at(-1)![0] as number;
    expect(first).toBeGreaterThan(1000);
    expect(first).toBeLessThan(1500);
    settle();
    expect(onValue).toHaveBeenLastCalledWith(1500);
    const seen = onValue.mock.calls.map((c) => c[0] as number);
    expect(seen).toEqual([...seen].sort((a, b) => a - b));               // eased, never backwards
    expect(new Set(seen).size).toBe(seen.length);                        // and each value emitted once
    window.dispatchEvent(pointer("pointerup", { clientX: 26 }));
  });

  it("keeps gliding after release and lands on the release point", () => {
    const node = field();
    const onValue = vi.fn();
    dragScale(node, { min: 0, max: 999999, int: true, value: 0, onValue });
    node.dispatchEvent(pointer("pointerdown", { clientX: 0 }));
    window.dispatchEvent(pointer("pointermove", { clientX: 52 }));       // asks for 1000
    window.dispatchEvent(pointer("pointerup", { clientX: 52 }));
    frame(16);
    expect(onValue).toHaveBeenCalled();
    expect(onValue).not.toHaveBeenLastCalledWith(1000);
    settle();
    expect(onValue).toHaveBeenLastCalledWith(1000);
    expect(queue).toHaveLength(0);                                       // the loop stops by itself
  });

  it("a narrow field is untouched by default: exactly under the pointer, no frame needed", () => {
    const node = field();
    const onValue = vi.fn();
    dragScale(node, { min: 60, max: 200, value: 120, onValue });
    node.dispatchEvent(pointer("pointerdown", { clientX: 500 }));
    window.dispatchEvent(pointer("pointermove", { clientX: 630 }));
    expect(onValue).toHaveBeenLastCalledWith(190);
    expect(queue).toHaveLength(0);
    window.dispatchEvent(pointer("pointerup", { clientX: 630 }));
  });

  it("a field can ask for it, and inertia: 0 switches the wide-range default off", () => {
    const node = field();
    const onValue = vi.fn();
    dragScale(node, { min: 0, max: 64, value: 6, inertia: 100, onValue });
    node.dispatchEvent(pointer("pointerdown", { clientX: 0 }));
    window.dispatchEvent(pointer("pointermove", { clientX: 130 }));
    expect(onValue).not.toHaveBeenCalled();
    settle();
    expect(onValue).toHaveBeenLastCalledWith(38);
    window.dispatchEvent(pointer("pointerup", { clientX: 130 }));

    const wide = field();
    const onWide = vi.fn();
    dragScale(wide, { min: 0, max: 999999, int: true, value: 0, inertia: 0, onValue: onWide });
    wide.dispatchEvent(pointer("pointerdown", { clientX: 0 }));
    window.dispatchEvent(pointer("pointermove", { clientX: 26 }));
    expect(onWide).toHaveBeenLastCalledWith(500);
    window.dispatchEvent(pointer("pointerup", { clientX: 26 }));
  });

  it("destroy() cancels a glide that is still running", () => {
    const node = field();
    const onValue = vi.fn();
    const handle = dragScale(node, { min: 0, max: 999999, int: true, value: 0, onValue });
    node.dispatchEvent(pointer("pointerdown", { clientX: 0 }));
    window.dispatchEvent(pointer("pointermove", { clientX: 52 }));
    window.dispatchEvent(pointer("pointerup", { clientX: 52 }));
    handle.destroy();
    frame(16);
    expect(onValue).not.toHaveBeenCalled();
  });
});
