// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import CurveEditor from "../CurveEditor.svelte";
import { flatCurve } from "../../../lib/blend/curves";

afterEach(cleanup);

// jsdom may lack PointerEvent; MouseEvent carries clientX/clientY, which is all the editor reads.
if (!("PointerEvent" in window)) (window as unknown as Record<string, unknown>).PointerEvent = MouseEvent;

// jsdom has no layout: give the svg a fixed box so pointer x/y map to columns/values.
function box(el: Element, w = 240, h = 100) {
  el.getBoundingClientRect = () => ({ left: 0, top: 0, width: w, height: h, right: w, bottom: h, x: 0, y: 0, toJSON: () => ({}) });
}

describe("CurveEditor", () => {
  it("renders one column per DiT block with its value", () => {
    render(CurveEditor, { values: flatCurve(0.5), onChange: () => {} });
    expect(screen.getByTestId("curve-col-0").getAttribute("data-value")).toBe("0.5");
    expect(screen.getByTestId("curve-col-23")).toBeTruthy();
  });

  it("a drag from block 2 to block 6 rewrites every column between (no gaps)", async () => {
    const onChange = vi.fn();
    render(CurveEditor, { values: flatCurve(1), onChange });
    const svg = screen.getByTestId("curve-svg");
    box(svg);
    // 240 px / 24 blocks = 10 px per column; y 100 = value -0.5 (bottom), y 0 = 1.5 (top)
    await fireEvent.pointerDown(svg, { clientX: 25, clientY: 75, pointerId: 1 });   // block 2, value 0
    await fireEvent.pointerMove(svg, { clientX: 65, clientY: 25, pointerId: 1 });   // block 6, value 1
    await fireEvent.pointerUp(svg, { pointerId: 1 });
    const last = onChange.mock.calls.at(-1)![0] as number[];
    expect(last.slice(2, 7)).toEqual([0, 0.25, 0.5, 0.75, 1]);
  });

  it("double-click opens a typed value for that block", async () => {
    const onChange = vi.fn();
    render(CurveEditor, { values: flatCurve(1), onChange });
    await fireEvent.dblClick(screen.getByTestId("curve-col-4"));
    const input = screen.getByTestId("curve-value-input") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "0.3" } });
    await fireEvent.keyDown(input, { key: "Enter" });
    expect((onChange.mock.calls.at(-1)![0] as number[])[4]).toBe(0.3);
  });

  it("double-clicking does not leave the first click's tap drawn (KUANG 2026-10-15)", async () => {
    const onChange = vi.fn();
    render(CurveEditor, { values: flatCurve(1), onChange });
    const svg = screen.getByTestId("curve-svg");
    box(svg);
    await fireEvent.pointerDown(svg, { clientX: 45, clientY: 75, pointerId: 1 });   // block 4, value 0: the tap
    await fireEvent.pointerUp(svg, { pointerId: 1 });
    expect((onChange.mock.calls.at(-1)![0] as number[])[4]).toBe(0);
    await fireEvent.dblClick(screen.getByTestId("curve-col-4"));
    expect((onChange.mock.calls.at(-1)![0] as number[])[4]).toBe(1);               // restored
    expect((screen.getByTestId("curve-value-input") as HTMLInputElement).value).toBe("1");
  });
});
