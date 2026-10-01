// @vitest-environment jsdom
import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RenderHistoryEntry } from "../../../lib/forge/types";
import { history } from "../../../lib/render/history.svelte";
import { masterSource } from "../../../lib/render/masterSource.svelte";
import { playback } from "../../../lib/stores/transport.svelte";
import MasterStrip from "../MasterStrip.svelte";

function mixEntry(): RenderHistoryEntry {
  return {
    job_id: "mix-1", forge_job_id: "forge-1", file: "mix.wav", label: "MIX 12:00:00",
    kind: "mix", dur_sec: 96, source_clip_id: null, created: 1,
  };
}

beforeEach(() => {
  history.clear();
  masterSource.set("preview");
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("the master strip's PREVIEW/MIXDOWN A/B", () => {
  it("is always in the DOM, with MIXDOWN disabled until something is committed", () => {
    const { getByTestId } = render(MasterStrip);
    const mix = getByTestId("master-source-mixdown") as HTMLButtonElement;
    expect(mix).toBeTruthy();
    expect(mix.disabled).toBe(true);
    expect(mix.title).toBe("nothing has been committed yet");
  });

  it("enables MIXDOWN the moment history.mixdown points at a render", async () => {
    const { getByTestId } = render(MasterStrip);
    history.add(mixEntry());
    history.mixdown = 0;
    await waitFor(() =>
      expect((getByTestId("master-source-mixdown") as HTMLButtonElement).disabled).toBe(false));
    expect((getByTestId("master-source-mixdown") as HTMLButtonElement).title).toBe("");
  });

  it("switches the store, and marks the pressed half active", async () => {
    history.add(mixEntry());
    history.mixdown = 0;
    const { getByTestId } = render(MasterStrip);

    await fireEvent.click(getByTestId("master-source-mixdown"));
    expect(masterSource.effective).toBe("mixdown");
    await waitFor(() =>
      expect(getByTestId("master-source-mixdown").classList.contains("active")).toBe(true));
    expect(getByTestId("master-source-preview").classList.contains("active")).toBe(false);

    await fireEvent.click(getByTestId("master-source-preview"));
    expect(masterSource.effective).toBe("preview");
  });

  it("re-seeks a playing transport to the same playhead, so the A/B is heard at one moment", async () => {
    history.add(mixEntry());
    history.mixdown = 0;
    playback.playing = true;
    playback.playheadSec = 40;
    const seek = vi.spyOn(playback, "seek").mockResolvedValue(undefined);

    const { getByTestId } = render(MasterStrip);
    await fireEvent.click(getByTestId("master-source-mixdown"));
    expect(seek).toHaveBeenCalledWith(40);
    playback.playing = false;
  });

  it("does not touch the transport when it is not playing", async () => {
    history.add(mixEntry());
    history.mixdown = 0;
    playback.playing = false;
    const seek = vi.spyOn(playback, "seek").mockResolvedValue(undefined);

    const { getByTestId } = render(MasterStrip);
    await fireEvent.click(getByTestId("master-source-mixdown"));
    expect(seek).not.toHaveBeenCalled();
  });

  it("finally attaches HELP.previewMixdownToggle, which M1 wrote and nothing has ever used", () => {
    const { container } = render(MasterStrip);
    const toggle = container.querySelector('[data-region="preview-mixdown-toggle"]');
    expect(toggle?.getAttribute("data-help")).toContain("A/B the audio-domain preview mix");
  });
});
