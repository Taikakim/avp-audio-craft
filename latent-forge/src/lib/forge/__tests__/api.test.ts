import { afterEach, describe, expect, it, vi } from "vitest";
import { ForgeApiError, forgeApi } from "../api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => vi.unstubAllGlobals());

describe("request building", () => {
  it("GETs /forge/files with root and query", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse({ ok: true, roots: [], files: [] }));
    vi.stubGlobal("fetch", fetchMock);
    await forgeApi.files({ root: "crops", q: "kick", limit: 50 });
    expect(fetchMock.mock.calls[0][0]).toBe("/forge/files?root=crops&q=kick&limit=50");
  });

  it("URL-encodes an AudioRef into /forge/audio", () => {
    const url = forgeApi.audioUrl({ kind: "crop", crop_id: "000412" });
    expect(url).toBe(`/forge/audio?ref=${encodeURIComponent('{"kind":"crop","crop_id":"000412"}')}`);
  });

  it("POSTs a job as {op, payload} and returns the job id", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse({ ok: true, job_id: "forge-1", position: 0 }, 202));
    vi.stubGlobal("fetch", fetchMock);
    const out = await forgeApi.submitJob("generate", { prompt: "dub" });
    expect(out.job_id).toBe("forge-1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/forge/jobs");
    expect(init!.method).toBe("POST");
    expect(JSON.parse(init!.body as string)).toEqual({ op: "generate", payload: { prompt: "dub" } });
  });

  it("PUTs a session under its name", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await forgeApi.saveSession("my set", { version: 2 } as never);
    expect(fetchMock.mock.calls[0][0]).toBe("/forge/sessions/my%20set");
    expect(fetchMock.mock.calls[0][1]!.method).toBe("PUT");
  });

  it("hands back GET /forge/sessions/{name} and /forge/presets/{level}/{name} RAW -- no {ok} envelope", async () => {
    // WINTERMUTE 2026-09-25: those two GETs return the STORED OBJECT as-is; the list routes and
    // PUT/DELETE wrap theirs in {ok, ...}. request() must neither unwrap nor require `ok`.
    const stored = { version: 2, name: "take1", clips: [] };
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(stored)));
    await expect(forgeApi.session("take1")).resolves.toEqual(stored);
    const preset = { latch_on: true, slots: [] };
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(preset)));
    await expect(forgeApi.preset("latch", "warm")).resolves.toEqual(preset);
  });
});

describe("error handling", () => {
  it("throws ForgeApiError carrying the server's message and status", async () => {
    vi.stubGlobal("fetch", async () => jsonResponse({ ok: false, error: "job queue full" }, 409));
    await expect(forgeApi.submitJob("commit", {})).rejects.toMatchObject({
      status: 409,
      message: "job queue full",
    });
    await expect(forgeApi.submitJob("commit", {})).rejects.toBeInstanceOf(ForgeApiError);
  });

  it("reports a non-JSON body as unreachable rather than a parse error", async () => {
    vi.stubGlobal("fetch", async () => new Response("<html>502</html>", { status: 502 }));
    await expect(forgeApi.info()).rejects.toMatchObject({ status: 502 });
    await expect(forgeApi.info()).rejects.toThrow(/unreachable/);
  });
});

describe("pollJob", () => {
  it("reports every progress tick and resolves with the finished record", async () => {
    vi.useFakeTimers();
    const states = [
      { state: "queued", progress: null },
      { state: "running", progress: { steps_left_total: 20, steps_total: 24 } },
      { state: "running", progress: { steps_left_total: 6, steps_total: 24 } },
      { state: "done", progress: null, result: { files: ["/SERVER/out/out_00.wav"] } },
    ];
    let i = 0;
    vi.stubGlobal("fetch", async () => jsonResponse({ ok: true, job_id: "forge-1", op: "generate", ...states[i++] }));

    const seen: unknown[] = [];
    const p = forgeApi.pollJob("forge-1", (pr) => seen.push(pr));
    await vi.advanceTimersByTimeAsync(2000);
    const rec = await p;

    expect(rec.state).toBe("done");
    expect(seen).toHaveLength(2);
    expect((seen[1] as { steps_left_total: number }).steps_left_total).toBe(6);
    vi.useRealTimers();
  });

  it("stops when the signal aborts", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", async () => jsonResponse({ ok: true, job_id: "forge-1", op: "generate", state: "running", progress: null }));
    const ac = new AbortController();
    const p = forgeApi.pollJob("forge-1", () => {}, ac.signal);
    ac.abort();
    await expect(p).rejects.toThrow(/aborted/);
    vi.useRealTimers();
  });

  it("rejects when the job errors", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", async () =>
      jsonResponse({ ok: true, job_id: "forge-1", op: "commit", state: "error", error: "non-finite latents in lane 2" }));
    const p = forgeApi.pollJob("forge-1", () => {});
    await vi.advanceTimersByTimeAsync(600);
    await expect(p).rejects.toThrow(/non-finite latents/);
    vi.useRealTimers();
  });
});
