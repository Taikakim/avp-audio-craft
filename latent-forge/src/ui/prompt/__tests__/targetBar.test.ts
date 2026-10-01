import { describe, expect, it } from "vitest";
import type { Target } from "../../../lib/forge/types";
import {
  CLIP_OPS, targetTag, targetTagColorVar,
} from "../targetBar";

const NONE: Target = { kind: "none" };
const CLIP: Target = { kind: "clip", id: "c1" };
const OVERLAP: Target = { kind: "overlap", key: "c1-c2" };

describe("targetTag (spec 4.5)", () => {
  it("tags nothing selected as GENERATE", () => {
    expect(targetTag(NONE, false)).toBe("GENERATE");
  });

  it("tags an overlap as INPAINT regardless of a2a", () => {
    expect(targetTag(OVERLAP, false)).toBe("INPAINT");
    expect(targetTag(OVERLAP, true)).toBe("INPAINT");
  });

  it("tags a clip as CLIP with a2a off and A2A with a2a on", () => {
    expect(targetTag(CLIP, false)).toBe("CLIP");
    expect(targetTag(CLIP, true)).toBe("A2A");
  });
});

describe("targetTagColorVar (spec 4.5)", () => {
  it("is turquoise for GENERATE", () => {
    expect(targetTagColorVar("GENERATE", 0)).toBe("--turq-strong");
  });

  it("is the target's own lane colour for CLIP, not always lane 1", () => {
    expect(targetTagColorVar("CLIP", 0)).toBe("--lane1");
    expect(targetTagColorVar("CLIP", 2)).toBe("--lane3");
  });

  it("is purple for A2A and INPAINT", () => {
    expect(targetTagColorVar("A2A", 1)).toBe("--purple-strong");
    expect(targetTagColorVar("INPAINT", 3)).toBe("--purple-strong");
  });
});

describe("CLIP_OPS (spec 10 X11)", () => {
  it("is generate, decode, longform, bend in that order", () => {
    expect(CLIP_OPS).toEqual(["generate", "decode", "longform", "bend"]);
  });
});
