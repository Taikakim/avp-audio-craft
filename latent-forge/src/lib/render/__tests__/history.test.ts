import { beforeEach, describe, expect, it, vi } from "vitest";
import { forgeApi } from "../../forge/api";
import type { RenderHistoryEntry } from "../../forge/types";
import { settings } from "../../stores/settings.svelte";
import { history } from "../history.svelte";

function entry(patch: Partial<RenderHistoryEntry> = {}): RenderHistoryEntry {
  return {
    job_id: "gen-20260926-1", forge_job_id: "forge-1", file: "out_00.wav", label: "GEN 12:00:00",
    kind: "gen", dur_sec: 45, source_clip_id: null, created: 1_759_000_000, ...patch,
  };
}

beforeEach(() => history.clear());

describe("add", () => {
  it("returns the array's LIVE element, not the object it was handed ($state proxy rule)", () => {
    const built = entry();
    const live = history.add(built);
    expect(live).toBe(history.renders[history.renders.length - 1]);
    live.label = "renamed";
    expect(history.renders[0].label).toBe("renamed");
  });

  it("stores newest LAST", () => {
    history.add(entry({ forge_job_id: "forge-1" }));
    history.add(entry({ forge_job_id: "forge-2" }));
    expect(history.renders.map((r) => r.forge_job_id)).toEqual(["forge-1", "forge-2"]);
  });

  it("makes the new render the previewed one -- §4.5 'a finished render lands here'", () => {
    history.add(entry());
    expect(history.preview).toBe(0);
    history.add(entry({ forge_job_id: "forge-2" }));
    expect(history.preview).toBe(1);
  });

  it("moves mixdown only for a commit, and always to the newest one (§7.1 'always the latest')", () => {
    history.add(entry({ kind: "gen" }));
    expect(history.mixdown).toBeNull();
    history.add(entry({ kind: "mix", forge_job_id: "forge-m1" }));
    expect(history.mixdown).toBe(1);
    history.add(entry({ kind: "a2a", forge_job_id: "forge-3" }));
    expect(history.mixdown).toBe(1);
    history.add(entry({ kind: "mix", forge_job_id: "forge-m2" }));
    expect(history.mixdown).toBe(3);
  });
});

describe("select -- audio only (§4.5, §10 X15)", () => {
  it("moves preview and touches nothing else", () => {
    history.add(entry({ forge_job_id: "forge-1" }));
    history.add(entry({ forge_job_id: "forge-2" }));
    const before = JSON.stringify(settings.defaults);
    history.select(0);
    expect(history.preview).toBe(0);
    expect(JSON.stringify(settings.defaults)).toBe(before);
    expect(history.mixdown).toBeNull();
  });

  it("ignores an index that is not a real row", () => {
    history.add(entry());
    history.select(7);
    history.select(-1);
    history.select(0.5);
    expect(history.preview).toBe(0);
  });
});

describe("refOf and jobRecord", () => {
  it("builds the render AudioRef from the RESULT job id and the file, not the forge queue id", () => {
    const e = entry({ job_id: "gen-20260926-1", forge_job_id: "forge-1", file: "out_00.wav" });
    expect(history.refOf(e)).toEqual({ kind: "render", job_id: "gen-20260926-1", file: "out_00.wav" });
  });

  it("reads the job record by the FORGE id, because that is what /forge/jobs/{id} keys on", async () => {
    const spy = vi.spyOn(forgeApi, "job").mockResolvedValue({ payload: { prompt: "dub" } } as never);
    const rec = await history.jobRecord(entry({ forge_job_id: "forge-9" }));
    expect(spy).toHaveBeenCalledWith("forge-9");
    expect((rec as { payload: { prompt: string } }).payload.prompt).toBe("dub");
    spy.mockRestore();
  });
});

describe("clear and restore", () => {
  it("clear empties all three fields", () => {
    history.add(entry({ kind: "mix" }));
    history.clear();
    expect(history.renders).toEqual([]);
    expect(history.mixdown).toBeNull();
    expect(history.preview).toBeNull();
  });

  it("restore replaces the list wholesale and keeps valid indexes", () => {
    history.add(entry({ forge_job_id: "stale" }));
    history.restore([entry({ forge_job_id: "a" }), entry({ forge_job_id: "b", kind: "mix" })], 1, 0);
    expect(history.renders.map((r) => r.forge_job_id)).toEqual(["a", "b"]);
    expect(history.mixdown).toBe(1);
    expect(history.preview).toBe(0);
  });

  it("restore drops an index that does not address a row, rather than pointing the slot at nothing", () => {
    history.restore([entry()], 4, -1);
    expect(history.mixdown).toBeNull();
    expect(history.preview).toBeNull();
  });
});
