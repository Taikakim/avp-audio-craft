import { beforeEach, describe, expect, it, vi } from "vitest";
import { AUDIO_SOURCE_PREVIEW, AUDIO_SOURCE_TIMELINE, registerAudioSource, takeAudio } from "../soloBus";

describe("soloBus — §4.5's 'starting one stops the other', without an import cycle", () => {
  let timeline = vi.fn();
  let preview = vi.fn();

  beforeEach(() => {
    timeline = vi.fn();
    preview = vi.fn();
    registerAudioSource(AUDIO_SOURCE_TIMELINE, timeline);
    registerAudioSource(AUDIO_SOURCE_PREVIEW, preview);
  });

  it("stops every other registered source", () => {
    takeAudio(AUDIO_SOURCE_PREVIEW);
    expect(timeline).toHaveBeenCalledTimes(1);
  });

  it("never stops the source that is taking the bus", () => {
    takeAudio(AUDIO_SOURCE_PREVIEW);
    expect(preview).not.toHaveBeenCalled();
  });
});
