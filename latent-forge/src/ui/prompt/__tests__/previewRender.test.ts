// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import type { AudioRef } from "../../../lib/forge/types";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { jobs } from "../../../lib/render/jobs.svelte";
import { settings } from "../../../lib/stores/settings.svelte";
import { view } from "../../../lib/stores/view.svelte";
import PreviewContainer from "../PreviewContainer.svelte";

const REF: AudioRef = { kind: "upload", sha256: "d".repeat(64) };

beforeEach(() => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 200 }));
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  view.clearSelection();
  jobs.active = null;
  jobs.gpuBusyOther = null;
  jobs.lastError = null;
  settings.defaults.prompt = "a room";
  settings.defaults.duration_sec = 30;
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("preview ▸ RENDER — spec §7.1", () => {
  it("is enabled and reads ▸ RENDER with nothing selected and a prompt", () => {
    const { getByTestId } = render(PreviewContainer);
    const button = getByTestId("preview-render") as HTMLButtonElement;
    expect(button.disabled).toBe(false);
    expect(button.textContent?.trim()).toBe("▸ RENDER");
  });

  it("submits `generate` with LENGTH under the session target key", async () => {
    const submit = vi.spyOn(jobs, "submit").mockResolvedValue(null);
    const { getByTestId } = render(PreviewContainer);
    await fireEvent.click(getByTestId("preview-render"));
    expect(submit).toHaveBeenCalledTimes(1);
    const req = submit.mock.calls[0][0];
    expect(req.op).toBe("generate");
    expect(req.targetKey).toBe("session");
    expect((req.payload as Record<string, unknown>).duration).toBe(30);
  });

  it("submits `inpaint` when an overlap is selected", async () => {
    const a = arrangement.addClip({ lane: 0, startSec: 0, durSec: 8, audio: REF });
    const b = arrangement.addClip({ lane: 0, startSec: 6, durSec: 8, audio: REF });
    const key = `${a.id}-${b.id}`;
    view.select({ kind: "overlap", key });
    const submit = vi.spyOn(jobs, "submit").mockResolvedValue(null);
    const { getByTestId } = render(PreviewContainer);
    await fireEvent.click(getByTestId("preview-render"));
    expect(submit.mock.calls[0][0].op).toBe("inpaint");
    expect(submit.mock.calls[0][0].targetKey).toBe(`overlap:${key}`);
  });

  it("counts the remaining steps on the control that started the job (§7.1)", () => {
    jobs.active = {
      forgeJobId: "forge-1", op: "generate", kind: "gen", sourceClipId: null, targetKey: "session",
      progress: { job_id: "forge-1", op: "generate", stage: "", stage_index: 0, stage_count: 0, step: 3, steps: 24, steps_left_total: 21, steps_total: 24 },
    };
    const { getByTestId } = render(PreviewContainer);
    const button = getByTestId("preview-render") as HTMLButtonElement;
    expect(button.textContent?.trim()).toBe("SAMPLING · 21 steps left");
    expect(button.disabled).toBe(true);
  });

  it("is disabled but NOT relabelled while the MIXDOWN slot owns the job", () => {
    jobs.active = {
      forgeJobId: "forge-2", op: "commit", kind: "mix", sourceClipId: null, targetKey: "mixdown",
      progress: null,
    };
    const { getByTestId } = render(PreviewContainer);
    const button = getByTestId("preview-render") as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.textContent?.trim()).toBe("▸ RENDER");
  });

  it("a clip with neither A2A nor an OP is disabled with §7.1's own hint", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    view.select({ kind: "clip", id: c.id });
    const { getByTestId } = render(PreviewContainer);
    const button = getByTestId("preview-render") as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.getAttribute("data-blocked")).toBe("turn A2A on or choose an op");
    expect(button.title).toBe("turn A2A on or choose an op");
  });

  it("shows §9.7's GPU line when another client holds the card", () => {
    jobs.gpuBusyOther = "dash-77";
    const { getByTestId } = render(PreviewContainer);
    const button = getByTestId("preview-render") as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.getAttribute("data-blocked")).toBe("GPU busy — dash-77");
  });
});
