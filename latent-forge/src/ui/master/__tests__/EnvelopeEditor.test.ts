// @vitest-environment jsdom
import { render } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Envelope } from "../../../lib/forge/types";
import EnvelopeEditor from "../EnvelopeEditor.svelte";

const FLAT: Envelope = { points: [0.4, 0.4, 0.4, 0.4], curves: [0, 0, 0] };

// jsdom has no PointerEvent constructor (same workaround as M1 T8's dragScale
// action test): a plain MouseEvent carries everything this component reads.
function pointer(type: string, init: { clientY?: number; button?: number } = {}) {
  const ev = new MouseEvent(type, { bubbles: true, cancelable: true, button: 0, clientY: 0, ...init });
  Object.defineProperty(ev, "pointerId", { value: 1 });
  return ev;
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("inert until the selected clip has A2A on (spec §4.3)", () => {
  it("is 28% opacity and takes no pointer events when inactive", () => {
    const { getByTestId } = render(EnvelopeEditor, { props: { envelope: FLAT, active: false, onChange: () => {} } });
    const root = getByTestId("envelope-node-0").closest('[data-region="envelope-overlay"]') as HTMLElement;
    expect(root.style.opacity).toBe("0.28");
    expect(root.style.pointerEvents).toBe("none");
  });

  it("is fully opaque and interactive once active", () => {
    const { getByTestId } = render(EnvelopeEditor, { props: { envelope: FLAT, active: true, onChange: () => {} } });
    const root = getByTestId("envelope-node-0").closest('[data-region="envelope-overlay"]') as HTMLElement;
    expect(root.style.opacity).toBe("1");
    expect(root.style.pointerEvents).toBe("auto");
  });

  it("ignores a node drag while inactive", async () => {
    const onChange = vi.fn();
    const { getByTestId } = render(EnvelopeEditor, { props: { envelope: FLAT, active: false, onChange } });
    getByTestId("envelope-node-0").dispatchEvent(pointer("pointerdown", { clientY: 200 }));
    window.dispatchEvent(pointer("pointermove", { clientY: 100 }));
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe("dragging a node reports the spec §5.2 value", () => {
  it("calls onChange with a new points array, the other three points untouched", () => {
    const onChange = vi.fn();
    const { getByTestId } = render(EnvelopeEditor, { props: { envelope: FLAT, active: true, onChange } });
    const root = getByTestId("envelope-node-0").closest('[data-region="envelope-overlay"]') as HTMLElement;
    vi.spyOn(root, "getBoundingClientRect").mockReturnValue({
      top: 200, height: 56, left: 0, width: 400, right: 400, bottom: 256, x: 0, y: 200, toJSON: () => ({}),
    });
    getByTestId("envelope-node-0").dispatchEvent(pointer("pointerdown", { clientY: 200 }));
    // top=200, height=56 -> pct=30 at clientY=216.8 -> v = (90-30)/80 = 0.75
    window.dispatchEvent(pointer("pointermove", { clientY: 216.8 }));
    expect(onChange).toHaveBeenLastCalledWith({ points: [0.75, 0.4, 0.4, 0.4], curves: [0, 0, 0] });
  });
});

describe("dragging a segment bends its curve (spec §5.2)", () => {
  it("computes c from the drag's own start point, not the envelope's current value", () => {
    const onChange = vi.fn();
    const { getByTestId } = render(EnvelopeEditor, { props: { envelope: FLAT, active: true, onChange } });
    getByTestId("envelope-segment-0").dispatchEvent(pointer("pointerdown", { clientY: 300 }));
    window.dispatchEvent(pointer("pointermove", { clientY: 240 })); // c = (300-240)/60 = 1
    expect(onChange).toHaveBeenLastCalledWith({ points: [0.4, 0.4, 0.4, 0.4], curves: [1, 0, 0] });
  });
});
