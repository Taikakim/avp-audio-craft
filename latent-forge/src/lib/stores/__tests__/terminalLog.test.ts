import { beforeEach, describe, expect, it, vi } from "vitest";
import { ForgeApiError, forgeApi } from "../../forge/api";
import { jobs } from "../../render/jobs.svelte";
import { logStore } from "../log.svelte";
import { view } from "../view.svelte";

beforeEach(() => {
  logStore.clear();
  view.clearLog();
  jobs.active = null;
  jobs.lastError = null;
  vi.restoreAllMocks();
});

describe("Fact 8: view.appendLog's red lines must reach what TERMINAL renders", () => {
  it("mirrors into logStore.lines -- the array BottomPane hands to <Terminal>", () => {
    view.appendLog("[chroma] stretch: drive not mounted", "error");
    expect(logStore.lines.at(-1)?.text).toBe("[chroma] stretch: drive not mounted");
    expect(logStore.lines.at(-1)?.tone).toBe("error");
  });

  it("keeps its own M1 T7 contract: still returns view.logLines' LIVE element", () => {
    const line = view.appendLog("[session] saved");
    expect(line).toBe(view.logLines[view.logLines.length - 1]);
    expect(line.level).toBe("info");
  });

  it("does NOT advance the server log cursor -- /forge/log would skip real lines", () => {
    logStore.append("server line", 41);
    const cursor = logStore.seq;
    view.appendLog("[stats] client-side failure", "error");
    view.appendLog("[stats] another", "error");
    expect(logStore.seq).toBe(cursor);
  });

  it("a server error reaches TERMINAL with its hint text intact (§9.7 unmounted drives)", async () => {
    const hint = "crops root /run/media/… is not mounted — plug the drive or pick another root";
    vi.spyOn(forgeApi, "submitJob").mockRejectedValue(new ForgeApiError(400, hint));
    await jobs.submit({ op: "generate", payload: {}, kind: "gen", sourceClipId: null, targetKey: "session" });
    expect(logStore.lines.at(-1)?.tone).toBe("error");
    expect(logStore.lines.at(-1)?.text).toContain(hint);
    expect(jobs.lastError?.message).toBe(hint);
  });
});
