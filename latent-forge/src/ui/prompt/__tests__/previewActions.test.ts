// @vitest-environment jsdom
import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BASE_DEFAULTS, cloneRenderSettings } from "../../../lib/forge/defaults";
import type { AudioRef, RenderHistoryEntry } from "../../../lib/forge/types";
import { history } from "../../../lib/render/history.svelte";
import { jobs } from "../../../lib/render/jobs.svelte";
import { arrangement } from "../../../lib/stores/arrangement.svelte";
import { settings } from "../../../lib/stores/settings.svelte";
import { view } from "../../../lib/stores/view.svelte";
import PreviewContainer from "../PreviewContainer.svelte";

const OLD: AudioRef = { kind: "upload", sha256: "a".repeat(64) };

function entry(p: Partial<RenderHistoryEntry> = {}): RenderHistoryEntry {
  return {
    job_id: "gen-7", forge_job_id: "forge-7", file: "out_00.wav", label: "GEN 12:00:00",
    kind: "gen", dur_sec: 12, source_clip_id: null, created: 1, ...p,
  };
}

beforeEach(() => {
  history.clear();
  jobs.active = null;
  settings.defaults = cloneRenderSettings(BASE_DEFAULTS);
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  view.clearSelection();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("USE SETTINGS — X15's explicit path", () => {
  it("is disabled with an honest title when nothing has been rendered yet", () => {
    const { getByTestId } = render(PreviewContainer);
    const b = getByTestId("preview-use-settings") as HTMLButtonElement;
    expect(b.disabled).toBe(true);
    expect(b.title).toBe("load a render from HISTORY first");
  });

  it("copies the job payload's settings AND its length into the current target", async () => {
    history.add(entry());
    vi.spyOn(history, "jobRecord").mockResolvedValue({
      ok: true, job_id: "gen-7", op: "generate",
      payload: { prompt: "a room", steps: 40, cfg_scale: 7, duration: 62.5 },
      state: "done", position: null, progress: null, result: null, error: null,
      created: 1, started: 1, finished: 2,
    } as never);

    const { getByTestId } = render(PreviewContainer);
    await fireEvent.click(getByTestId("preview-use-settings"));

    await waitFor(() => expect(settings.current(view.selection).steps).toBe(40));
    expect(settings.current(view.selection).prompt).toBe("a room");
    expect(settings.current(view.selection).duration_sec).toBe(62.5);
  });

  it("changes no audio — the converse of X15, and the only way that regression is caught", async () => {
    history.add(entry());
    history.add(entry({ job_id: "gen-8", file: "out_01.wav" }));
    const before = history.preview;
    vi.spyOn(history, "jobRecord").mockResolvedValue({
      ok: true, job_id: "gen-8", op: "generate", payload: { steps: 11 }, state: "done",
      position: null, progress: null, result: null, error: null, created: 1, started: 1, finished: 2,
    } as never);

    const { getByTestId } = render(PreviewContainer);
    await fireEvent.click(getByTestId("preview-use-settings"));
    await waitFor(() => expect(settings.current(view.selection).steps).toBe(11));
    expect(history.preview).toBe(before);
  });

  it("says so, and writes nothing, when the render carries no settings", async () => {
    history.add(entry({ kind: "gen" }));
    settings.patch(view.selection, { steps: 33 });
    vi.spyOn(history, "jobRecord").mockResolvedValue({
      ok: true, job_id: "gen-7", op: "decode", payload: { crop_id: "000412" }, state: "done",
      position: null, progress: null, result: null, error: null, created: 1, started: 1, finished: 2,
    } as never);

    const { getByTestId } = render(PreviewContainer);
    await fireEvent.click(getByTestId("preview-use-settings"));
    await waitFor(() =>
      expect((getByTestId("preview-use-settings") as HTMLButtonElement).title)
        .toBe("that render carries no settings"));
    expect(settings.current(view.selection).steps).toBe(33);
  });

  it("surfaces a failed job fetch on §9.7's inline error line instead of throwing", async () => {
    history.add(entry());
    vi.spyOn(history, "jobRecord").mockRejectedValue(new Error("job forge-7 not found"));
    const { getByTestId } = render(PreviewContainer);
    await fireEvent.click(getByTestId("preview-use-settings"));
    await waitFor(() => expect(jobs.lastError?.message).toContain("forge-7"));
  });
});

describe("REPLACE CLIP", () => {
  it("is disabled when the selected clip is not the one the render came from", async () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 30, audio: OLD });
    history.add(entry({ source_clip_id: "someone-else" }));
    view.select({ kind: "clip", id: c.id });

    const { getByTestId } = render(PreviewContainer);
    const b = getByTestId("preview-replace-clip") as HTMLButtonElement;
    expect(b.disabled).toBe(true);
    expect(b.title).toBe("select the clip this render was made from");
  });

  it("swaps the clip's audio for the previewed render and archives the old ref", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(
      JSON.stringify({ ok: true, bpm: null, bpm_candidates: [], beats_sec: [], downbeats_sec: [], duration_sec: 12, source: "librosa" }),
      { status: 200, headers: { "content-type": "application/json" } },
    )));
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 30, audio: OLD });
    history.add(entry({ source_clip_id: c.id }));
    view.select({ kind: "clip", id: c.id });

    const { getByTestId } = render(PreviewContainer);
    await fireEvent.click(getByTestId("preview-replace-clip"));

    await waitFor(() => expect(c.audio).toEqual({ kind: "render", job_id: "gen-7", file: "out_00.wav" }));
    expect(c.history).toEqual([OLD]);
    expect(c.dur_sec).toBe(12);
    vi.unstubAllGlobals();
  });
});
