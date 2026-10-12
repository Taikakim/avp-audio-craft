import { describe, expect, it } from "vitest";
import type { RenderHistoryEntry } from "../../forge/types";
import { HISTORY_EMPTY_LABEL, historyOptions, lengthLabel } from "../historyLabel";

function entry(p: Partial<RenderHistoryEntry> = {}): RenderHistoryEntry {
  return {
    job_id: "gen-1", forge_job_id: "forge-1", file: "out_00.wav", label: "GEN 12:00:00",
    kind: "gen", dur_sec: 30, source_clip_id: null, created: 1, ...p,
  };
}

describe("historyOptions — spec §4.5's HISTORY select", () => {
  it("is newest first, though the store holds newest last", () => {
    const options = historyOptions([
      entry({ label: "GEN 12:00:00" }),
      entry({ label: "A2A 12:01:00", kind: "a2a" }),
      entry({ label: "MIX 12:02:00", kind: "mix" }),
    ]);
    expect(options.map((o) => o.index)).toEqual([2, 1, 0]);
    expect(options[0].label.startsWith("MIX")).toBe(true);
  });

  it("carries the tag and the length, which the stored label does not have", () => {
    expect(historyOptions([entry({ dur_sec: 30 })])[0].label).toBe("GEN 12:00:00 · 30.0 s");
  });

  it("says — rather than 0.0 s when the result carried no duration", () => {
    expect(historyOptions([entry({ dur_sec: 0 })])[0].label).toBe("GEN 12:00:00 · —");
    expect(lengthLabel(null)).toBe("—");
    expect(lengthLabel(0)).toBe("—");
  });

  it("has an empty-state label matching M1's own frame copy", () => {
    expect(historyOptions([])).toEqual([]);
    expect(HISTORY_EMPTY_LABEL).toBe("no renders yet");
  });
});
