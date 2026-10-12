import { describe, expect, it } from "vitest";
import { LANE_SELECTIONS, laneSelAttr, laneSelLabel, type LaneSel } from "../statsHeader";

describe("LANE_SELECTIONS (spec §4.4)", () => {
  it("is lanes 1-4 then ALL, in that order", () => {
    expect(LANE_SELECTIONS).toEqual([1, 2, 3, 4, "all"]);
  });
});

describe("laneSelLabel", () => {
  it("labels each lane number LANE <n>", () => {
    expect(laneSelLabel(1)).toBe("LANE 1");
    expect(laneSelLabel(2)).toBe("LANE 2");
    expect(laneSelLabel(3)).toBe("LANE 3");
    expect(laneSelLabel(4)).toBe("LANE 4");
  });

  it('labels "all" as ALL', () => {
    expect(laneSelLabel("all")).toBe("ALL");
  });
});

describe("laneSelAttr feeds [data-stats-lane], which M1 T13 already fixed", () => {
  it("stringifies every selection to exactly the fixed attribute values", () => {
    const attrs = LANE_SELECTIONS.map((s: LaneSel) => laneSelAttr(s));
    expect(attrs).toEqual(["1", "2", "3", "4", "all"]);
  });
});
