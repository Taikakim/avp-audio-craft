import { afterEach, describe, expect, it, vi } from "vitest";
import type { AudioRef } from "../../forge/types";
import { ChromaClient, chromaClient, chromaRefKey } from "../chromaClient.svelte";

const REF: AudioRef = { kind: "crop", crop_id: "000412" };

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function b64(bytes: Uint8Array): string {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}

/** A well-formed §6.3 body: band b is filled with the constant byte 50*(b+1),
 *  fold12 class p frame t with the byte p*10 + t. */
function chromaBody(T: number, scales: [number, number, number] = [1, 2, 4]) {
  const bandBytes = new Uint8Array(3 * 128 * T);
  for (let band = 0; band < 3; band++) {
    bandBytes.fill(50 * (band + 1), band * 128 * T, (band + 1) * 128 * T);
  }
  const foldBytes = new Uint8Array(12 * T);
  for (let p = 0; p < 12; p++) for (let t = 0; t < T; t++) foldBytes[p * T + t] = p * 10 + t;
  return {
    ok: true,
    frames: T,
    fps: 10.7666015625,
    bands: { shape: [3, 128, T], scale: scales, data_b64: b64(bandBytes) },
    fold12: { shape: [12, T], scale: 1.0, data_b64: b64(foldBytes) },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  chromaClient.dispose();
});

describe("request decodes the §6.3 payload on arrival", () => {
  it("applies ONE SCALE PER BAND to that band's own slice of the byte stream", () => {
    // The whole reason this task exists: bands has three scales, fold12 has one.
    const client = new ChromaClient();
    const T = 2;
    vi.stubGlobal("fetch", vi.fn(async (_url: string, _init?: RequestInit) => jsonResponse(chromaBody(T, [1, 2, 4]))));

    return client.request(REF).then(() => {
      const bands = client.result!.bands;
      expect(bands).toBeInstanceOf(Float32Array);
      expect(bands.length).toBe(3 * 128 * T);
      // band 0: byte 50, scale 1 ; band 1: byte 100, scale 2 ; band 2: byte 150, scale 4
      expect(bands[0]).toBe(Math.fround((50 / 255) * 1));
      expect(bands[128 * T]).toBe(Math.fround((100 / 255) * 2));
      expect(bands[2 * 128 * T]).toBe(Math.fround((150 / 255) * 4));
      // and the LAST value of each slice, not just the first
      expect(bands[128 * T - 1]).toBe(Math.fround((50 / 255) * 1));
      expect(bands[2 * 128 * T - 1]).toBe(Math.fround((100 / 255) * 2));
      expect(bands[3 * 128 * T - 1]).toBe(Math.fround((150 / 255) * 4));
    });
  });

  it("applies the single fold12 scale and keeps the [12,T] C-order layout", async () => {
    const client = new ChromaClient();
    const T = 2;
    vi.stubGlobal("fetch", vi.fn(async (_url: string, _init?: RequestInit) => jsonResponse(chromaBody(T))));

    await client.request(REF);

    const fold12 = client.result!.fold12;
    expect(fold12.length).toBe(12 * T);
    expect(fold12[0 * T + 0]).toBe(Math.fround((0 / 255) * 1.0));
    expect(fold12[7 * T + 1]).toBe(Math.fround((71 / 255) * 1.0));
    expect(fold12[11 * T + 1]).toBe(Math.fround((111 / 255) * 1.0));
  });

  it("carries frames, fps and T, toggles pending, and POSTs {audio} to /forge/chroma", async () => {
    const client = new ChromaClient();
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => jsonResponse(chromaBody(3)));
    vi.stubGlobal("fetch", fetchMock);

    const p = client.request(REF);
    expect(client.pending).toBe(true);
    await p;

    expect(client.pending).toBe(false);
    expect(client.error).toBeNull();
    expect(client.result?.frames).toBe(3);
    expect(client.result?.T).toBe(3);
    expect(client.result?.fps).toBe(10.7666015625);
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/forge/chroma");
    expect((init as RequestInit).method).toBe("POST");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({ audio: REF });
  });

  it("surfaces a server error (§9.7) and leaves result null and pending false", async () => {
    const client = new ChromaClient();
    vi.stubGlobal("fetch", async () => jsonResponse({ ok: false, error: "no such crop" }, 404));

    await client.request(REF);

    expect(client.pending).toBe(false);
    expect(client.result).toBeNull();
    expect(client.error).toBe("no such crop");
  });

  it("reports a byte count that does not match [3,128,T] rather than mis-slicing it", async () => {
    const client = new ChromaClient();
    const body = chromaBody(2);
    body.bands.data_b64 = b64(new Uint8Array(3 * 128 * 2 - 1));
    vi.stubGlobal("fetch", async () => jsonResponse(body));

    await client.request(REF);

    expect(client.result).toBeNull();
    expect(client.error).toMatch(/expected 768 bytes/);
  });
});

describe("the per-AudioRef cache", () => {
  it("serves a repeat request for the same ref without a round trip", async () => {
    const client = new ChromaClient();
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => jsonResponse(chromaBody(2)));
    vi.stubGlobal("fetch", fetchMock);

    await client.request(REF);
    const first = client.result;
    await client.request({ kind: "crop", crop_id: "000412" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(client.result).toBe(first);
    expect(client.pending).toBe(false);
  });

  it("keys on the ref's contents, not on the key order of the object literal", async () => {
    const client = new ChromaClient();
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => jsonResponse(chromaBody(2)));
    vi.stubGlobal("fetch", fetchMock);

    const a: AudioRef = { kind: "file", root: "crops", rel: "a/b.wav" };
    const b = { rel: "a/b.wav", root: "crops", kind: "file" } as AudioRef;
    expect(chromaRefKey(a)).toBe(chromaRefKey(b));

    await client.request(a);
    await client.request(b);

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("fetches again for a different ref", async () => {
    const client = new ChromaClient();
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => jsonResponse(chromaBody(2)));
    vi.stubGlobal("fetch", fetchMock);

    await client.request(REF);
    await client.request({ kind: "crop", crop_id: "000413" });

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe("supersession, flush and dispose", () => {
  it("discards a superseded result even if it resolves after the latest one", async () => {
    const client = new ChromaClient();
    let resolveFirst!: (v: Response) => void;
    let resolveSecond!: (v: Response) => void;
    const first = new Promise<Response>((r) => (resolveFirst = r));
    const second = new Promise<Response>((r) => (resolveSecond = r));
    let call = 0;
    vi.stubGlobal("fetch", vi.fn(async (_url: string, _init?: RequestInit) => (call++ === 0 ? first : second)));

    const p1 = client.request({ kind: "crop", crop_id: "a" });
    const p2 = client.request({ kind: "crop", crop_id: "b" });

    resolveSecond(jsonResponse(chromaBody(5)));
    await p2;
    resolveFirst(jsonResponse(chromaBody(9)));
    await p1;

    expect(client.result?.frames).toBe(5);
    expect(client.pending).toBe(false);
    expect(client.error).toBeNull();
  });

  it("flush() resolves once the in-flight request has settled", async () => {
    const client = new ChromaClient();
    let resolveFetch!: (v: Response) => void;
    const pendingFetch = new Promise<Response>((r) => (resolveFetch = r));
    vi.stubGlobal("fetch", vi.fn(async (_url: string, _init?: RequestInit) => pendingFetch));

    void client.request(REF);
    expect(client.pending).toBe(true);

    const flushed = client.flush();
    resolveFetch(jsonResponse(chromaBody(1)));
    await flushed;

    expect(client.pending).toBe(false);
    expect(client.result?.frames).toBe(1);
  });

  it("dispose() never hangs the caller and clears the cache the singleton would otherwise keep", async () => {
    // A singleton's cache outlives a component unmount: without this reset, the
    // next test would read the previous one's result and pass for the wrong reason.
    const never = new Promise<Response>(() => {});
    vi.stubGlobal("fetch", vi.fn(async (_url: string, _init?: RequestInit) => never));
    const p = chromaClient.request(REF);
    chromaClient.dispose();
    await expect(p).resolves.toBeUndefined();
    expect(chromaClient.result).toBeNull();
    expect(chromaClient.pending).toBe(false);
    expect(chromaClient.error).toBeNull();

    vi.unstubAllGlobals();
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => jsonResponse(chromaBody(2)));
    vi.stubGlobal("fetch", fetchMock);
    await chromaClient.request(REF);
    expect(fetchMock).toHaveBeenCalledTimes(1);   // the cache really was cleared
  });
});
