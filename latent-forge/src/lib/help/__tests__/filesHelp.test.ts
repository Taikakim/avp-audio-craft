import { describe, expect, it } from "vitest";
import { HELP } from "../strings";

describe("FILES' two brand-new HELP strings (spec §4.6.2, v3 474-484 has no select or filter at all)", () => {
  it("has filesRoot, non-empty, describing the root select", () => {
    expect(HELP.filesRoot.length).toBeGreaterThan(10);
    expect(HELP.filesRoot.toLowerCase()).toContain("root");
  });

  it("has filesFilter, non-empty, describing the filter field", () => {
    expect(HELP.filesFilter.length).toBeGreaterThan(10);
    expect(HELP.filesFilter.toLowerCase()).toContain("filter");
  });

  it("keeps filesRow exactly as the drawing had it (v3 line 480)", () => {
    expect(HELP.filesRow).toBe(
      "Drag onto a lane to add a clip at the playhead. Audio and latents are both accepted.",
    );
  });
});
