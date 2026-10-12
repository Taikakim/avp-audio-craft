// @vitest-environment jsdom
import { cleanup, render } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { chromaLink } from "../../../lib/chroma/chromaLink.svelte";
import { SCORE_PLACEHOLDER } from "../../../lib/math/clipBox";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import ClipBox from "../ClipBox.svelte";

beforeEach(() => {
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  chromaLink.reset();
});

afterEach(() => {
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  chromaLink.reset();
  cleanup();
});

describe("the clip box's score label (spec §4.3; M5 T6 left the slot for M6)", () => {
  it("keeps M5's placeholder for a clip nothing has analysed", () => {
    const clip = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: "a" } });
    const { getByTestId } = render(ClipBox, { props: { clip } });
    expect(getByTestId("clip-score").textContent).toBe(SCORE_PLACEHOLDER);
  });

  it("shows the real mean frame match once the CHROMA tab has scored that clip", () => {
    const clip = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: "a" } });
    chromaLink.setScore(clip.id, 0.7148);
    const { getByTestId } = render(ClipBox, { props: { clip } });
    expect(getByTestId("clip-score").textContent).toBe("χ 0.71");
  });

  it("scores only the clip it was told about, not every clip on the timeline", () => {
    const a = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: "a" } });
    arrangement.addClip({ lane: 0, startSec: 8, durSec: 4, audio: { kind: "crop", crop_id: "b" } });
    chromaLink.setScore(a.id, 0.5);
    const { getByTestId } = render(ClipBox, { props: { clip: arrangement.clips[1] } });
    expect(getByTestId("clip-score").textContent).toBe(SCORE_PLACEHOLDER);
  });
});
