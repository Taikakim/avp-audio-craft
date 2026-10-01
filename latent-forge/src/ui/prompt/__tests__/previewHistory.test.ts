// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Transport } from "../../../lib/audio/transport";
import { cleanup, fireEvent, render } from "@testing-library/svelte";
import { flushSync } from "svelte";
import type { PlaybackEngine, PlaybackClip, PlaybackLane } from "../../../lib/audio/transport";
import { history } from "../../../lib/render/history.svelte";
import { previewPlayer } from "../../../lib/render/previewPlayer.svelte";
import { playback } from "../../../lib/stores/transport.svelte";
import { settings } from "../../../lib/stores/settings.svelte";
import { view } from "../../../lib/stores/view.svelte";
import PreviewContainer from "../PreviewContainer.svelte";

function fakeEngine(): PlaybackEngine {
  return {
    play: vi.fn(async (_c: PlaybackClip[], _l: PlaybackLane[], _s: number) => {}),
    pause: vi.fn(), stop: vi.fn(),
    seek: vi.fn(async () => {}),
    preload: vi.fn(async () => ({ duration: 30 }) as unknown as AudioBuffer),
    invalidate: vi.fn(), scrub: vi.fn(), stopScrub: vi.fn(), updateLanes: vi.fn(),
    currentTimeSec: 0, playing: false,
  };
}

function entry(p: Partial<Parameters<typeof history.add>[0]> = {}) {
  return history.add({
    job_id: "gen-1", forge_job_id: "forge-1", file: "out_00.wav", label: "GEN 12:00:00",
    kind: "gen", dur_sec: 30, source_clip_id: null, created: 1, ...p,
  });
}

let engine: PlaybackEngine;

beforeEach(() => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 200 }));
  history.clear();
  view.clearSelection();
  engine = fakeEngine();
  previewPlayer.useEngine(engine);
  previewPlayer.url = null;
  previewPlayer.playing = false;
  playback.playing = false;
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("HISTORY, the waveform and the handle — spec §4.5", () => {
  it("is disabled and empty until the session has a render", () => {
    const { getByTestId } = render(PreviewContainer);
    const select = getByTestId("preview-history") as HTMLSelectElement;
    expect(select.disabled).toBe(true);
    expect(select.textContent?.trim()).toBe("no renders yet");
  });

  it("lists renders newest first, tagged and with their length", () => {
    entry({ label: "GEN 12:00:00" });
    entry({ label: "A2A 12:01:00", kind: "a2a", dur_sec: 8 });
    const { getByTestId } = render(PreviewContainer);
    const select = getByTestId("preview-history") as HTMLSelectElement;
    expect(select.disabled).toBe(false);
    expect([...select.options].map((o) => o.textContent)).toEqual([
      "A2A 12:01:00 · 8.0 s",
      "GEN 12:00:00 · 30.0 s",
    ]);
  });

  it("does not take the shared player back when MIXDOWN loads the mix into it (review 2026-10-01)", () => {
    entry({ label: "GEN 12:00:00" });
    render(PreviewContainer);
    flushSync();
    const genUrl = previewPlayer.url;
    expect(genUrl).not.toBeNull();
    previewPlayer.load("/forge/audio?mix", 47);
    flushSync();
    expect(previewPlayer.url).toBe("/forge/audio?mix");
  });

  it("loading from HISTORY loads audio only — the target's settings are untouched (X15)", async () => {
    entry({ label: "GEN 12:00:00" });
    entry({ label: "A2A 12:01:00", kind: "a2a", dur_sec: 8 });
    settings.defaults.prompt = "untouched";
    settings.defaults.steps = 24;
    const { getByTestId } = render(PreviewContainer);
    await fireEvent.change(getByTestId("preview-history"), { target: { value: "0" } });
    expect(history.preview).toBe(0);
    expect(settings.defaults.prompt).toBe("untouched");
    expect(settings.defaults.steps).toBe(24);
  });

  it("shows the previewed render's length in the DOM, not on the canvas", () => {
    entry({ dur_sec: 12.5 });
    const { getByTestId } = render(PreviewContainer);
    expect(getByTestId("preview-length").textContent?.trim()).toBe("12.5 s");
  });

  it("starting the preview stops the timeline transport (§4.5)", async () => {
    entry();
    playback.playing = true;
    const { getByTestId } = render(PreviewContainer);
    await fireEvent.click(getByTestId("preview-play"));
    expect(playback.playing).toBe(false);
    expect(previewPlayer.playing).toBe(true);
  });

  it("starting the timeline transport stops the preview (§4.5, the other direction)", async () => {
    entry();
    const { getByTestId } = render(PreviewContainer);
    await fireEvent.click(getByTestId("preview-play"));
    expect(previewPlayer.playing).toBe(true);
    // The arrangement's engine is a real Transport on jsdom's AudioContext stub, which has no
    // gain.setValueAtTime; stub only its play() so this exercises the SOLO BUS (takeAudio runs
    // before engine.play), not Web Audio.
    vi.spyOn(Transport.prototype, "play").mockResolvedValue(undefined);
    await playback.play();
    expect(previewPlayer.playing).toBe(false);
    expect(engine.stop).toHaveBeenCalled();
  });

  it("clicking the waveform scrubs to that second", async () => {
    entry({ dur_sec: 30 });
    const { getByTestId } = render(PreviewContainer);
    const canvas = getByTestId("preview-wave") as HTMLCanvasElement;
    vi.spyOn(canvas, "getBoundingClientRect").mockReturnValue(
      { left: 0, top: 0, width: 900, height: 30, right: 900, bottom: 30, x: 0, y: 0, toJSON: () => "" },
    );
    await fireEvent.pointerDown(canvas, { clientX: 300 });
    expect(previewPlayer.playheadSec).toBeCloseTo(10, 5);
    expect(engine.scrub).toHaveBeenCalled();
  });

  it("the handle carries the render AudioRef as application/x-forge-ref", async () => {
    const e = entry();
    const { getByTestId } = render(PreviewContainer);
    const handle = getByTestId("preview-drag-handle");
    expect(handle.getAttribute("draggable")).toBe("true");
    const setData = vi.fn();
    await fireEvent.dragStart(handle, { dataTransfer: { setData, effectAllowed: "" } });
    expect(setData).toHaveBeenCalledWith(
      "application/x-forge-ref",
      JSON.stringify({ kind: "render", job_id: e.job_id, file: e.file }),
    );
  });
});
