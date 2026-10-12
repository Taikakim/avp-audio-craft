import { beforeEach, describe, expect, it } from "vitest";
import type { RenderHistoryEntry } from "../../forge/types";
import { history } from "../history.svelte";
import { masterSource, MIXDOWN_UNAVAILABLE_HINT } from "../masterSource.svelte";

function entry(p: Partial<RenderHistoryEntry> = {}): RenderHistoryEntry {
  return {
    job_id: "mix-1", forge_job_id: "forge-1", file: "mix.wav", label: "MIX 12:00:00",
    kind: "mix", dur_sec: 96, source_clip_id: null, created: 1, ...p,
  };
}

beforeEach(() => {
  history.clear();
  masterSource.set("preview");
});

describe("masterSource — the A/B choice, and the availability it is gated on", () => {
  it("starts on PREVIEW with no mix available", () => {
    expect(masterSource.value).toBe("preview");
    expect(masterSource.available).toBe(false);
    expect(masterSource.url).toBeNull();
  });

  it("is available exactly when history.mixdown is not null", () => {
    history.add(entry({ kind: "gen" }));
    expect(masterSource.available).toBe(false);   // a render is not a mixdown
    history.add(entry());
    history.mixdown = history.renders.length - 1;
    expect(masterSource.available).toBe(true);
  });

  it("resolves the mix through the same /forge/audio route as every clip", () => {
    history.add(entry());
    history.mixdown = 0;
    expect(masterSource.url).toContain("/forge/audio?ref=");
    expect(masterSource.url).toContain("mix.wav");
    expect(masterSource.durSec).toBe(96);
  });

  it("records the operator's choice even while no mix exists", () => {
    masterSource.set("mixdown");
    expect(masterSource.value).toBe("mixdown");
  });

  it("but plays PREVIEW until one does — `effective` gates, `value` remembers", () => {
    masterSource.set("mixdown");
    expect(masterSource.effective).toBe("preview");
    history.add(entry());
    history.mixdown = 0;
    expect(masterSource.effective).toBe("mixdown");
  });

  it("falls back the moment a session load leaves no mix, without any effect running", () => {
    history.add(entry());
    history.mixdown = 0;
    masterSource.set("mixdown");
    expect(masterSource.effective).toBe("mixdown");
    history.restore([], null, null);
    expect(masterSource.effective).toBe("preview");
    expect(masterSource.value).toBe("mixdown");   // the choice is never silently rewritten
  });

  it("names the reason the MIXDOWN half is unpressable, in the words the button shows", () => {
    expect(MIXDOWN_UNAVAILABLE_HINT).toBe("nothing has been committed yet");
  });
});
