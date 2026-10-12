// @vitest-environment jsdom
// M7 T9 wired every TargetBar clip prop except op/onOp ("the OP select is M9's to back").
// This is that wiring, in the same shape as M7's own promptSigmaTabClip.test.ts.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import type { AudioRef } from "../../../lib/forge/types";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { view } from "../../../lib/stores/view.svelte";
import PromptSigmaTab from "../PromptSigmaTab.svelte";

const REF: AudioRef = { kind: "upload", sha256: "c".repeat(64) };

beforeEach(() => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 200 }));
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  view.clearSelection();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("the OP select is backed by the selected clip (spec §10 X11)", () => {
  it("shows the selected clip's op", async () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    arrangement.setClipOp(c.id, "longform");
    view.select({ kind: "clip", id: c.id });
    const { getByTestId } = render(PromptSigmaTab);     // propless, as BottomPane mounts it
    expect((getByTestId("target-op") as HTMLSelectElement).value).toBe("longform");
  });

  it("choosing an op writes it back to the clip", async () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    view.select({ kind: "clip", id: c.id });
    const { getByTestId } = render(PromptSigmaTab);
    await fireEvent.change(getByTestId("target-op"), { target: { value: "decode" } });
    expect(arrangement.clips[0].op).toBe("decode");
  });
});
