// @vitest-environment jsdom
import { cleanup, render } from "@testing-library/svelte";
import { afterEach, describe, expect, it } from "vitest";
import type { ChromaHover } from "../../../lib/chroma/hoverReadout";
import { HOVER_DETAIL_PX, HOVER_NOTE_PX } from "../../../lib/chroma/hoverReadout";
import HoverReadout from "../HoverReadout.svelte";

const HOVER: ChromaHover = {
  frame: 48, frames: 96, frac: 0.5, pitchClass: 0, cents: null,
  value: 1, top: 7, topValue: 0.5, match: 0.62, sec: 4.46,
};

afterEach(cleanup);

describe("HoverReadout renders as DOM, never as fillText (the blocking M4 finding)", () => {
  it("puts the note name where findByText can actually find it", () => {
    const { getByText, getByTestId } = render(HoverReadout, { props: { hover: HOVER } });
    // getByText normalises the NODE's whitespace ("C  1.00" -> "C 1.00") but not the string it is
    // given, so the double space can never match through it. Assert the text with a normalised
    // matcher (findable as DOM text, the point of the test) and the raw text via textContent.
    expect(getByText("C 1.00")).toBeTruthy();
    expect(getByTestId("chroma-hover-note").textContent?.trim()).toBe("C  1.00");
  });

  it("puts the detail line beside it, with the frame index 1-based", () => {
    const { getByTestId } = render(HoverReadout, { props: { hover: HOVER } });
    expect(getByTestId("chroma-hover-detail").textContent).toBe(
      "strongest G 0.50 · match 0.62 · frame 49/96 · 4.46 s",
    );
  });

  it("is 14 px for the note and 9 px for the detail (spec §5.4)", () => {
    const { getByTestId } = render(HoverReadout, { props: { hover: HOVER } });
    expect(getByTestId("chroma-hover-note").style.fontSize).toBe(`${HOVER_NOTE_PX}px`);
    expect(getByTestId("chroma-hover-detail").style.fontSize).toBe(`${HOVER_DETAIL_PX}px`);
  });

  it("renders nothing at all when the pointer has left the canvas", () => {
    const { queryByTestId } = render(HoverReadout, { props: { hover: null } });
    expect(queryByTestId("chroma-hover-note")).toBeNull();
    expect(queryByTestId("chroma-hover-detail")).toBeNull();
  });
});
