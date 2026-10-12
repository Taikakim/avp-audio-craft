import { describe, expect, it } from "vitest";
import { BOTTOM_TABS, bottomHint } from "../bottomTabs";

describe("the bottom tab row is spec §4.5's four tabs in order", () => {
  it("is CHROMA · PROMPT + SIGMA · MIX + SIGNAL PATH · TERMINAL", () => {
    expect(BOTTOM_TABS.map((t) => t.id)).toEqual(["chroma", "prompt", "mix", "terminal"]);
    expect(BOTTOM_TABS.map((t) => t.label)).toEqual([
      "CHROMA",
      "PROMPT + SIGMA",
      "MIX + SIGNAL PATH",
      "TERMINAL",
    ]);
  });

  it("carries the right-aligned hint of each tab verbatim", () => {
    expect(bottomHint("chroma")).toBe("hover the heatmap to read a frame");
    expect(bottomHint("prompt")).toBe("settings follow the selection");
    expect(bottomHint("mix")).toBe("lane order feeds the mix nodes");
    expect(bottomHint("terminal")).toBe("stdout of the running job");
  });
});
