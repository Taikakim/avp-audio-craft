import { describe, expect, it } from "vitest";
import { BOTTOM_TABS, bottomHint } from "../bottomTabs";

describe("the bottom tab row: spec §4.5's four tabs plus ADAPTER MIX", () => {
  it("is CHROMA · PROMPT + SIGMA · MIX + SIGNAL PATH · TERMINAL", () => {
    expect(BOTTOM_TABS.map((t) => t.id)).toEqual(["chroma", "prompt", "mix", "adapter-mix", "terminal"]);
    expect(BOTTOM_TABS.map((t) => t.label)).toEqual([
      "CHROMA",
      "PROMPT + SIGMA",
      "MIX + SIGNAL PATH",
      "ADAPTER MIX",
      "TERMINAL",
    ]);
  });

  it("carries the right-aligned hint of each tab verbatim", () => {
    expect(bottomHint("chroma")).toBe("hover the heatmap to read a frame");
    expect(bottomHint("prompt")).toBe("settings follow the selection");
    expect(bottomHint("mix")).toBe("lane order feeds the mix nodes");
    expect(bottomHint("terminal")).toBe("stdout of the running job");
    expect(bottomHint("adapter-mix")).toBe("draw how much of the adapter acts in each DiT block");
  });
});
