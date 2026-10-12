import { describe, expect, it } from "vitest";
import type { ForgeClip } from "../../forge/types";
import {
  bpmLabel, edgeHitTest, EDGE_PX, laneForDrag, SCORE_PLACEHOLDER, scrubOffsetSec,
} from "../clipBox";

function clip(over: Partial<ForgeClip>): ForgeClip {
  return {
    id: "c", lane: 0, start_sec: 0, offset_sec: 0, dur_sec: 4, loop: false,
    audio: { kind: "upload", sha256: "x" }, native_bpm: null, detune_cents: 0,
    downbeats_sec: [], render: {} as never, a2a: null, latentState: "none", history: [],
    ...over,
  } as ForgeClip;
}

describe("edgeHitTest (spec 4.3: drag within 6px of an edge trims)", () => {
  it("is the spec's 6", () => {
    expect(EDGE_PX).toBe(6);
  });

  it("hits the start edge near the left", () => {
    expect(edgeHitTest(102, 100, 200)).toBe("start"); // local = 2
  });

  it("hits the end edge near the right", () => {
    expect(edgeHitTest(298, 100, 200)).toBe("end"); // local = 198, width-198=2
  });

  it("is body in the middle", () => {
    expect(edgeHitTest(200, 100, 200)).toBe("body");
  });

  it("is inclusive right at the threshold", () => {
    expect(edgeHitTest(106, 100, 200)).toBe("start"); // local = 6 = EDGE_PX
    expect(edgeHitTest(294, 100, 200)).toBe("end"); // local = 194, width-194=6
  });
});

describe("laneForDrag (spec 4.3: vertical drag changes lane)", () => {
  it("stays put for a small vertical delta", () => {
    expect(laneForDrag(1, 10, 62)).toBe(1);
  });

  it("moves one lane per lane-height of drag", () => {
    expect(laneForDrag(1, 62, 62)).toBe(2);
    expect(laneForDrag(1, -62, 62)).toBe(0);
  });

  it("clamps at both ends", () => {
    expect(laneForDrag(3, 620, 62)).toBe(3);
    expect(laneForDrag(0, -620, 62)).toBe(0);
  });
});

describe("scrubOffsetSec (spec §10 X2: Alt+drag scrubs the clip's own audio in a loop)", () => {
  it("maps the box's left edge to the clip's offset into its source", () => {
    expect(scrubOffsetSec(100, 100, 200, 3, 4)).toBe(3);
  });

  it("maps the box's right edge to offset + duration", () => {
    expect(scrubOffsetSec(300, 100, 200, 3, 4)).toBe(7);
  });

  it("maps the midpoint proportionally", () => {
    expect(scrubOffsetSec(200, 100, 200, 3, 4)).toBe(5);
  });

  it("clamps outside the box rather than scrubbing off the clip's own material", () => {
    expect(scrubOffsetSec(0, 100, 200, 3, 4)).toBe(3);
    expect(scrubOffsetSec(1000, 100, 200, 3, 4)).toBe(7);
  });
});

describe("bpmLabel", () => {
  it("is null for a clip with no native tempo", () => {
    expect(bpmLabel(clip({}), 120)).toBeNull();
  });

  it("shows native→project and the stretch percentage, signed", () => {
    expect(bpmLabel(clip({ native_bpm: 120 }), 140)).toBe("120.0→140 +16.7%");
    expect(bpmLabel(clip({ native_bpm: 140 }), 120)).toBe("140.0→120 -14.3%");
  });

  it("shows 0.0% unsigned for a clip already at project tempo", () => {
    expect(bpmLabel(clip({ native_bpm: 120 }), 120)).toBe("120.0→120 +0.0%");
  });
});

describe("SCORE_PLACEHOLDER (M6 fills the chroma-match number in)", () => {
  it("is an em-dash slot", () => {
    expect(SCORE_PLACEHOLDER).toBe("χ —");
  });
});
