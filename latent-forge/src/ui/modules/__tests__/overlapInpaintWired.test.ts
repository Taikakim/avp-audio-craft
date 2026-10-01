// @vitest-environment jsdom
import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AudioRef } from "../../../lib/forge/types";
import { jobs } from "../../../lib/render/jobs.svelte";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { view } from "../../../lib/stores/view.svelte";
import OverlapInpaint from "../OverlapInpaint.svelte";

const REF: AudioRef = { kind: "upload", sha256: "a".repeat(64) };

function seedOverlap(): string {
  const a = arrangement.addClip({ lane: 0, startSec: 0, durSec: 8, audio: REF });
  const b = arrangement.addClip({ lane: 0, startSec: 6, durSec: 8, audio: REF });
  const key = arrangement.overlaps[0].key;
  view.select({ kind: "overlap", key });
  return `${a.id}-${b.id}-${key}`.slice(0, 0) + key;
}

beforeEach(() => {
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  jobs.active = null;
  jobs.gpuBusyOther = null;
  jobs.lastError = null;
  view.clearSelection();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("▸ INPAINT OVERLAP — §7.1's fourth row, through the same dispatch as ▸ RENDER", () => {
  it("submits an inpaint job for the selected overlap", async () => {
    seedOverlap();
    const submit = vi.spyOn(jobs, "submit").mockResolvedValue(null);
    const { getByTestId } = render(OverlapInpaint);

    await fireEvent.click(getByTestId("inpaint-overlap-button"));

    await waitFor(() => expect(submit).toHaveBeenCalledTimes(1));
    const req = submit.mock.calls[0][0];
    expect(req.op).toBe("inpaint");
    expect(req.kind).toBe("inpaint");
    expect(req.sourceClipId).toBeNull();
    expect(req.targetKey.startsWith("overlap:")).toBe(true);
    expect(req.payload).toMatchObject({ region: expect.any(Object), pad_sec: expect.any(Number) });
  });

  it("is disabled while any job runs, and says which — §7.1's blanket rule", async () => {
    seedOverlap();
    jobs.gpuBusyOther = "forge-99";
    const { getByTestId } = render(OverlapInpaint);
    const b = getByTestId("inpaint-overlap-button") as HTMLButtonElement;
    expect(b.disabled).toBe(true);
    expect(b.title).toBe("GPU busy — forge-99");
  });

  it("reads SAMPLING · N steps left while its own job runs, not while another control's does", async () => {
    const key = seedOverlap();
    const { getByTestId } = render(OverlapInpaint);
    jobs.active = {
      forgeJobId: "forge-1", op: "inpaint", kind: "inpaint", sourceClipId: null,
      targetKey: `overlap:${key}`, progress: { steps_left_total: 18 } as never,
    } as never;
    await waitFor(() =>
      expect(getByTestId("inpaint-overlap-button").textContent?.trim()).toBe("SAMPLING · 18 steps left"));
  });

  it("puts a PayloadError on §9.7's inline surface instead of throwing out of the handler", async () => {
    seedOverlap();
    vi.spyOn(jobs, "submit").mockRejectedValue(new Error("region start_sec < end_sec required"));
    const { getByTestId } = render(OverlapInpaint);
    await fireEvent.click(getByTestId("inpaint-overlap-button"));
    await waitFor(() => expect(jobs.lastError?.message).toContain("region start_sec"));
  });

  it("still renders nothing for an overlap key that no longer exists (M7 critic pass 2 #5)", () => {
    view.select({ kind: "overlap", key: "gone-a-gone-b" });
    const { queryByTestId } = render(OverlapInpaint);
    expect(queryByTestId("inpaint-overlap-button")).toBeNull();
  });
});
