import { afterEach, describe, expect, it, vi } from "vitest";
import { StatsClient, statsClient } from "../statsClient.svelte";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function b64(bytes: number[]): string {
  return btoa(String.fromCharCode(...bytes));
}

afterEach(() => {
  vi.unstubAllGlobals();
  statsClient.dispose();
});

describe("requestStats decodes xcorr on arrival, using $state for result/pending/error", () => {
  it("populates a decoded Float32Array result and toggles pending", async () => {
    const client = new StatsClient();
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) =>
      jsonResponse({
        ok: true,
        n_frames: 40,
        xcorr: { shape: [2, 2], data_b64: b64([0, 255, 128, 128]) },
        timeseries: [{ index: 0, feature: "rms", fps: 10.77, values: [0.1, null, 0.3] }],
        features_available: ["rms"],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const p = client.requestStats({ latents: [{ kind: "crop", crop_id: "a" }], features: ["rms"] });
    expect(client.pending).toBe(true);
    await p;

    expect(client.pending).toBe(false);
    expect(client.error).toBeNull();
    expect(client.result?.n_frames).toBe(40);
    expect(client.result?.n).toBe(2);
    expect(client.result?.xcorr).toBeInstanceOf(Float32Array);
    expect(Array.from(client.result!.xcorr)).toEqual([
      Math.fround((0 / 255) * 2 - 1),
      Math.fround((255 / 255) * 2 - 1),
      Math.fround((128 / 255) * 2 - 1),
      Math.fround((128 / 255) * 2 - 1),
    ]);
    expect(client.result?.timeseries[0].values).toEqual([0.1, null, 0.3]);
    expect(client.result?.features_available).toEqual(["rms"]);

    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/forge/stats");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      latents: [{ kind: "crop", crop_id: "a" }],
      features: ["rms"],
      max_frames: 20000,
      max_points: 2000,
    });
  });

  it("surfaces a server error and leaves pending false", async () => {
    const client = new StatsClient();
    vi.stubGlobal("fetch", async () => jsonResponse({ ok: false, error: "no crops selected" }, 400));

    await client.requestStats({ latents: [], features: ["rms"] });

    expect(client.pending).toBe(false);
    expect(client.result).toBeNull();
    expect(client.error).toBe("no crops selected");
  });
});

describe("requestScalars", () => {
  it("populates scalars from /forge/dataset_scalars", async () => {
    const client = new StatsClient();
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) =>
      jsonResponse({
        ok: true,
        fields: ["bpm", "lufs", "rel_pos"],
        points: [{ crop_id: "c1", x: 120, y: -14, label: "c1" }],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await client.requestScalars("bpm", "lufs");

    expect(client.scalarsPending).toBe(false);
    expect(client.scalarsError).toBeNull();
    expect(client.scalars?.fields).toEqual(["bpm", "lufs", "rel_pos"]);
    expect(client.scalars?.points).toHaveLength(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/forge/dataset_scalars?x=bpm&y=lufs");
  });

  it("surfaces a server error independently of the stats call", async () => {
    const client = new StatsClient();
    vi.stubGlobal("fetch", async () => jsonResponse({ ok: false, error: "unknown field" }, 400));

    await client.requestScalars("nope", "lufs");

    expect(client.scalarsPending).toBe(false);
    expect(client.scalars).toBeNull();
    expect(client.scalarsError).toBe("unknown field");
    // The independent stats fields are untouched by a scalars-only error.
    expect(client.pending).toBe(false);
    expect(client.error).toBeNull();
  });
});

describe("supersession via AbortController", () => {
  it("discards a superseded result even if it resolves after the latest one", async () => {
    const client = new StatsClient();
    let resolveFirst!: (v: Response) => void;
    let resolveSecond!: (v: Response) => void;
    const first = new Promise<Response>((r) => (resolveFirst = r));
    const second = new Promise<Response>((r) => (resolveSecond = r));
    let call = 0;
    vi.stubGlobal("fetch", vi.fn(async () => (call++ === 0 ? first : second)));

    const p1 = client.requestStats({ latents: [{ kind: "crop", crop_id: "a" }], features: ["rms"] });
    const p2 = client.requestStats({ latents: [{ kind: "crop", crop_id: "b" }], features: ["rms"] });

    // Resolve the SECOND (latest) request first, then the superseded first
    // one late -- the final state must reflect the second regardless.
    resolveSecond(
      jsonResponse({
        ok: true, n_frames: 5,
        xcorr: { shape: [1, 1], data_b64: b64([255]) },
        timeseries: [], features_available: ["rms"],
      }),
    );
    await p2;
    resolveFirst(
      jsonResponse({
        ok: true, n_frames: 999,
        xcorr: { shape: [1, 1], data_b64: b64([0]) },
        timeseries: [], features_available: ["rms"],
      }),
    );
    await p1;

    expect(client.result?.n_frames).toBe(5);
    expect(client.pending).toBe(false);
    expect(client.error).toBeNull();
  });

  it("dispose() during a request never hangs the caller, even if the underlying fetch never settles", async () => {
    const client = new StatsClient();
    const never = new Promise<Response>(() => {});
    vi.stubGlobal("fetch", vi.fn(async () => never));

    const p = client.requestStats({ latents: [{ kind: "crop", crop_id: "a" }], features: ["rms"] });
    client.dispose();

    await expect(p).resolves.toBeUndefined();
    await expect(client.flush()).resolves.toBeUndefined();
    expect(client.result).toBeNull();
    expect(client.pending).toBe(false);
  });
});

describe("flush()", () => {
  it("resolves once the in-flight request has settled", async () => {
    const client = new StatsClient();
    let resolveFetch!: (v: Response) => void;
    const pendingFetch = new Promise<Response>((r) => (resolveFetch = r));
    vi.stubGlobal("fetch", vi.fn(async () => pendingFetch));

    void client.requestStats({ latents: [{ kind: "crop", crop_id: "a" }], features: ["rms"] });
    expect(client.pending).toBe(true);

    const flushed = client.flush();
    resolveFetch(
      jsonResponse({
        ok: true, n_frames: 1,
        xcorr: { shape: [1, 1], data_b64: b64([0]) },
        timeseries: [], features_available: [],
      }),
    );
    await flushed;

    expect(client.pending).toBe(false);
    expect(client.result?.n_frames).toBe(1);
  });
});

describe("dispose() resets state -- the singleton's cache outlives a component unmount", () => {
  it("clears result, scalars, pending and error on the exported singleton", async () => {
    vi.stubGlobal("fetch", async () =>
      jsonResponse({
        ok: true, n_frames: 1,
        xcorr: { shape: [1, 1], data_b64: b64([0]) },
        timeseries: [], features_available: [],
      }),
    );

    await statsClient.requestStats({ latents: [{ kind: "crop", crop_id: "a" }], features: ["rms"] });
    expect(statsClient.result).not.toBeNull();

    statsClient.dispose();

    expect(statsClient.result).toBeNull();
    expect(statsClient.scalars).toBeNull();
    expect(statsClient.pending).toBe(false);
    expect(statsClient.error).toBeNull();
  });
});
