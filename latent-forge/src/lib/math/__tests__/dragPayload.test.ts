import { describe, expect, it } from "vitest";
import type { AudioRef } from "../../forge/types";
import { FORGE_DUR_MIME, FORGE_REF_MIME, readForgeDrag, writeForgeDrag } from "../laneHeader";

const REF: AudioRef = { kind: "render", job_id: "gen-7", file: "out_00.wav" };

/** jsdom has no DataTransfer; this is the two methods the helpers touch. */
function dt(seed: Record<string, string> = {}): DataTransfer {
  const store = { ...seed };
  return {
    setData: (type: string, value: string) => { store[type] = value; },
    getData: (type: string) => store[type] ?? "",
  } as unknown as DataTransfer;
}

describe("the lane drag payload — the ref stays a bare AudioRef, the length rides beside it", () => {
  it("writes the ref exactly as M5 wrote it, so an old drop handler still parses it", () => {
    const d = dt();
    writeForgeDrag(d, REF, 96);
    expect(d.getData(FORGE_REF_MIME)).toBe(JSON.stringify(REF));
  });

  it("writes the length on its own MIME, never inside the ref", () => {
    const d = dt();
    writeForgeDrag(d, REF, 96);
    expect(d.getData(FORGE_DUR_MIME)).toBe("96");
    expect(JSON.parse(d.getData(FORGE_REF_MIME))).toEqual(REF);
  });

  it("omits the length rather than writing a fake one when the source does not know it", () => {
    const d = dt();
    writeForgeDrag(d, REF, null);
    expect(d.getData(FORGE_DUR_MIME)).toBe("");
    expect(readForgeDrag(d)).toEqual({ ref: REF, durationSec: null });
  });

  it("reads back both halves", () => {
    const d = dt();
    writeForgeDrag(d, REF, 12.5);
    expect(readForgeDrag(d)).toEqual({ ref: REF, durationSec: 12.5 });
  });

  it("is null for a drop that carries no ref at all — an OS file drag, say", () => {
    expect(readForgeDrag(dt())).toBeNull();
    expect(readForgeDrag(null)).toBeNull();
  });

  it("ignores a junk or non-positive length instead of passing it to addClip", () => {
    expect(readForgeDrag(dt({ [FORGE_REF_MIME]: JSON.stringify(REF), [FORGE_DUR_MIME]: "soon" })))
      .toEqual({ ref: REF, durationSec: null });
    expect(readForgeDrag(dt({ [FORGE_REF_MIME]: JSON.stringify(REF), [FORGE_DUR_MIME]: "0" })))
      .toEqual({ ref: REF, durationSec: null });
    expect(readForgeDrag(dt({ [FORGE_REF_MIME]: JSON.stringify(REF), [FORGE_DUR_MIME]: "-4" })))
      .toEqual({ ref: REF, durationSec: null });
  });

  it("is null for a ref-shaped payload that is not an AudioRef — M5's isAudioRef guard is kept", () => {
    expect(readForgeDrag(dt({ [FORGE_REF_MIME]: JSON.stringify({ kind: "nope" }) }))).toBeNull();
    expect(readForgeDrag(dt({ [FORGE_REF_MIME]: "{not json" }))).toBeNull();
  });
});
