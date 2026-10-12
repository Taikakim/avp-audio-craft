import { describe, expect, it } from "vitest";
import { SCHEDULE_DEFAULT } from "../../../lib/forge/defaults";
import type { LatchSlot, ScheduleSpec } from "../../../lib/forge/types";
import { FLAT_PLATEAU_NOTE } from "../../../lib/sampling/scheduleRules";
import {
  buildScheduleRequest, sigmaNote, slotLegendLabel, STALE_SHAPE_NOTE,
} from "../sigmaColumn";

function spec(over: Partial<ScheduleSpec> = {}): ScheduleSpec {
  return { ...SCHEDULE_DEFAULT, ...over };
}

function slot(over: Partial<LatchSlot> = {}): LatchSlot {
  return { head: "onsets", kind: "value", value: 0.5, weight: 1, start_pct: 0, end_pct: 1, ...over };
}

describe("buildScheduleRequest carries duration through (spec 5.3, the plan's Global Constraints)", () => {
  it("puts every argument in its own request field, duration included", () => {
    const s = spec({ rho: 3 });
    expect(buildScheduleRequest(24, 30, 1.0, "euler", s)).toEqual({
      steps: 24, duration: 30, sigma_max: 1.0, sampler_type: "euler", schedule: s,
    });
  });

  it("never substitutes a default for duration, even 0", () => {
    expect(buildScheduleRequest(8, 0, 0.4, null, spec()).duration).toBe(0);
  });
});

describe("sigmaNote picks the first applicable message", () => {
  it("shows the client's error before anything else", () => {
    const flat = spec({ stepped: true, tilt: 0 });
    expect(sigmaNote("render server unreachable", true, flat, "euler"))
      .toBe("render server unreachable");
  });

  it("shows the stale-shape note when there is no error", () => {
    // A spec that differs from SCHEDULE_DEFAULT, because that is the only state in which the
    // client's own `staleShape` can be true -- passing the untouched default here would assert
    // against a combination the caller can never hand this function.
    expect(sigmaNote(null, true, spec({ shape: "geometric" }), "euler")).toBe(STALE_SHAPE_NOTE);
    expect(STALE_SHAPE_NOTE).toBe("schedule shape is charted from M3 onward");
  });

  it("falls back to the flat-plateau note once neither an error nor staleness applies", () => {
    const flat = spec({ stepped: true, tilt: 0 });
    expect(sigmaNote(null, false, flat, "euler")).toBe(FLAT_PLATEAU_NOTE);
  });

  it("is null when nothing is wrong", () => {
    expect(sigmaNote(null, false, spec(), "euler")).toBeNull();
  });
});

describe("slotLegendLabel (spec 4.5's LatCH slot legend)", () => {
  it("shows the slot's head name", () => {
    expect(slotLegendLabel(slot({ head: "beat_grid" }))).toBe("beat_grid");
  });

  it("shows an em dash for an absent slot", () => {
    expect(slotLegendLabel(undefined)).toBe("—");
  });

  it("shows an em dash for a slot with no head or head 'none'", () => {
    expect(slotLegendLabel(slot({ head: "" }))).toBe("—");
    expect(slotLegendLabel(slot({ head: "none" }))).toBe("—");
  });
});
