import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SCHEDULE_DEFAULT } from "../../forge/defaults";
import type { ScheduleSpec } from "../../forge/types";
import {
  isNonIncreasing, SCHEDULE_DEBOUNCE_MS, ScheduleClient, scheduleIsDefault, scheduleKey,
} from "../scheduleClient.svelte";
import type { ScheduleRequest, ScheduleResult } from "../scheduleClient.svelte";

// The client owns its own call to /schedule (see this task's Interfaces), so the seam under
// test is `fetch`, not `forgeApi`. Stubbing the global is also what lets a test hold on to the
// AbortSignal the client passed and assert it was aborted.
const fetchMock = vi.fn<typeof fetch>();

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

/** A fresh Response per call: a Response body can only be read once, and several tests below
 * let the client call /schedule twice. */
function answers(body: unknown, status = 200): () => Promise<Response> {
  return () => Promise.resolve(jsonResponse(body, status));
}

function callAt(i: number): { url: string; init: RequestInit } {
  const [url, init] = fetchMock.mock.calls[i] as [string, RequestInit];
  return { url, init };
}

function sentBody(i: number): ScheduleRequest {
  return JSON.parse(String(callAt(i).init.body)) as ScheduleRequest;
}

function sentSignal(i: number): AbortSignal {
  return callAt(i).init.signal as AbortSignal;
}

function schedule(over: Partial<ScheduleSpec> = {}): ScheduleSpec {
  return {
    shape: "model", rho: 1, sigma_min: 0.01, lam_min: -6.2, lam_max: 2.0,
    stepped: false, plateaus: 6, tilt: 0.15, ...over,
  };
}

function req(over: Partial<ScheduleRequest> = {}): ScheduleRequest {
  return {
    steps: 24, duration: 30, sigma_max: 1.0, sampler_type: null, schedule: schedule(), ...over,
  };
}

function result(over: Partial<ScheduleResult> = {}): ScheduleResult {
  return {
    sigmas: [1, 0.5, 0], steps: 24, duration: 30, sigma_max: 1.0, dist_shift: "model",
    latent_len: 322, ...over,
  };
}

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

beforeEach(() => {
  vi.useFakeTimers();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("scheduleKey", () => {
  it("gives the same key for requests with the same fields, whatever order they were built in", () => {
    const a: ScheduleRequest = {
      steps: 24, duration: 30, sigma_max: 1, sampler_type: "euler",
      schedule: { shape: "model", rho: 1, sigma_min: 0.01, lam_min: -6.2, lam_max: 2, stepped: false, plateaus: 6, tilt: 0.15 },
    };
    const b: ScheduleRequest = {
      schedule: { tilt: 0.15, plateaus: 6, stepped: false, lam_max: 2, lam_min: -6.2, sigma_min: 0.01, rho: 1, shape: "model" },
      sampler_type: "euler", sigma_max: 1, duration: 30, steps: 24,
    };
    expect(scheduleKey(a)).toBe(scheduleKey(b));
  });

  it("gives a different key when any field differs", () => {
    expect(scheduleKey(req())).not.toBe(scheduleKey(req({ steps: 25 })));
    expect(scheduleKey(req())).not.toBe(scheduleKey(req({ schedule: schedule({ rho: 2 }) })));
  });
});

describe("isNonIncreasing", () => {
  it("is true for a strictly decreasing sequence", () => {
    expect(isNonIncreasing([1, 0.6, 0.3, 0])).toBe(true);
  });

  it("is true for a flat sequence — equal counts as non-increasing", () => {
    expect(isNonIncreasing([0.5, 0.5, 0.5])).toBe(true);
  });

  it("is true for empty and single-element arrays", () => {
    expect(isNonIncreasing([])).toBe(true);
    expect(isNonIncreasing([1])).toBe(true);
  });

  it("is false when any step increases", () => {
    expect(isNonIncreasing([1, 0.3, 0.5, 0])).toBe(false);
  });
});

describe("scheduleIsDefault", () => {
  it("is true for SCHEDULE_DEFAULT itself and for a copy of it", () => {
    expect(scheduleIsDefault(SCHEDULE_DEFAULT)).toBe(true);
    expect(scheduleIsDefault({ ...SCHEDULE_DEFAULT })).toBe(true);
  });

  it("is false for a changed shape", () => {
    expect(scheduleIsDefault({ ...SCHEDULE_DEFAULT, shape: "geometric" })).toBe(false);
  });

  it("is false for every other field too — not just shape", () => {
    expect(scheduleIsDefault({ ...SCHEDULE_DEFAULT, rho: 3 })).toBe(false);
    expect(scheduleIsDefault({ ...SCHEDULE_DEFAULT, sigma_min: 0.05 })).toBe(false);
    expect(scheduleIsDefault({ ...SCHEDULE_DEFAULT, lam_min: -5 })).toBe(false);
    expect(scheduleIsDefault({ ...SCHEDULE_DEFAULT, lam_max: 3 })).toBe(false);
    expect(scheduleIsDefault({ ...SCHEDULE_DEFAULT, stepped: true })).toBe(false);
    expect(scheduleIsDefault({ ...SCHEDULE_DEFAULT, plateaus: 10 })).toBe(false);
    expect(scheduleIsDefault({ ...SCHEDULE_DEFAULT, tilt: 0.4 })).toBe(false);
  });
});

describe("ScheduleClient debounce and caching", () => {
  it("starts with no result, not pending, no error", () => {
    const client = new ScheduleClient();
    expect(client.result).toBeNull();
    expect(client.pending).toBe(false);
    expect(client.error).toBeNull();
  });

  it("does not POST /schedule before the debounce elapses", () => {
    fetchMock.mockImplementation(answers(result()));
    const client = new ScheduleClient();
    client.request(req());
    expect(fetchMock).not.toHaveBeenCalled();
    expect(client.pending).toBe(true);
  });

  it("POSTs /schedule once after the debounce, with the latest request as the body", async () => {
    fetchMock.mockImplementation(answers(result()));
    const client = new ScheduleClient();
    client.request(req({ steps: 10 }));
    client.request(req({ steps: 20 }));
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(callAt(0).url).toBe("/schedule");
    expect(callAt(0).init.method).toBe("POST");
    expect(sentBody(0)).toEqual(req({ steps: 20 }));
  });

  it("sets pending false and result on a successful response", async () => {
    const r = result();
    fetchMock.mockImplementation(answers(r));
    const client = new ScheduleClient();
    client.request(req());
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    expect(client.pending).toBe(false);
    expect(client.error).toBeNull();
    expect(client.result).toEqual(r);
  });

  it("serves a cached result synchronously without POSTing again", async () => {
    fetchMock.mockImplementation(answers(result()));
    const client = new ScheduleClient();
    client.request(req());
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    client.request(req({ steps: 10 })); // a different request first, to prove the cache is keyed
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    client.request(req()); // back to the first request's exact fields
    expect(client.pending).toBe(false);
    expect(client.result).toEqual(result());
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe("ScheduleClient validation", () => {
  it("sets error and clears result when the response's sigmas are not non-increasing", async () => {
    fetchMock.mockImplementation(answers(result({ sigmas: [1, 0.2, 0.6, 0] })));
    const client = new ScheduleClient();
    client.request(req());
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    expect(client.result).toBeNull();
    expect(client.error).toBe("schedule sigmas are not non-increasing");
    expect(client.pending).toBe(false);
  });

  it("surfaces the route's own error message from a non-ok status", async () => {
    // The real route answers a bad body with 400 and {"error": "..."} and no `ok` key
    // (explorer_render_server.py:1024-1027), which is what postSchedule turns into a
    // ForgeApiError carrying that sentence.
    fetchMock.mockImplementation(answers({ error: "bad JSON body" }, 400));
    const client = new ScheduleClient();
    client.request(req());
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    expect(client.error).toBe("bad JSON body");
    expect(client.pending).toBe(false);
  });
});

describe("ScheduleClient supersedes an in-flight request", () => {
  it("aborts the previous request's signal when a new request arrives", async () => {
    fetchMock.mockImplementationOnce(() => new Promise<Response>(() => {})); // never settles
    fetchMock.mockImplementationOnce(answers(result({ sigmas: [1, 0.4, 0] })));
    const client = new ScheduleClient();
    client.request(req());
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    expect(sentSignal(0).aborted).toBe(false);
    client.request(req({ steps: 30 }));
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    expect(sentSignal(0).aborted).toBe(true);
    expect(client.result?.sigmas).toEqual([1, 0.4, 0]);
    expect(client.pending).toBe(false);
  });

  it("ignores a superseded response that resolves after the newer one", async () => {
    const a = deferred<Response>();
    fetchMock.mockImplementationOnce(() => a.promise);
    fetchMock.mockImplementationOnce(answers(result({ sigmas: [1, 0.4, 0] })));
    const client = new ScheduleClient();
    client.request(req());
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    client.request(req({ steps: 30 }));
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    expect(client.result?.sigmas).toEqual([1, 0.4, 0]);
    a.resolve(jsonResponse(result({ sigmas: [1, 0.9, 0] }))); // the stale request finally answers
    await vi.advanceTimersByTimeAsync(0);
    expect(client.result?.sigmas).toEqual([1, 0.4, 0]);
  });
});

describe("ScheduleClient.dispose", () => {
  it("aborts an in-flight request and clears pending without waiting for it to settle", async () => {
    fetchMock.mockImplementationOnce(() => new Promise<Response>(() => {})); // never settles
    const client = new ScheduleClient();
    client.request(req());
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    expect(client.pending).toBe(true);
    client.dispose();
    await vi.advanceTimersByTimeAsync(0);
    expect(client.pending).toBe(false);
  });

  it("ignores a request() call after dispose", async () => {
    const client = new ScheduleClient();
    client.dispose();
    client.request(req());
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(client.pending).toBe(false);
  });
});

describe("ScheduleClient.flush", () => {
  it("resolves immediately without waiting for the debounce timer", async () => {
    fetchMock.mockImplementation(answers(result()));
    const client = new ScheduleClient();
    client.request(req());
    await client.flush();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(client.result).toEqual(result());
    expect(client.pending).toBe(false);
  });
});

describe("staleShape", () => {
  it("is true when a non-model shape was requested and the response echoes no shape", async () => {
    fetchMock.mockImplementation(answers(result()));
    const client = new ScheduleClient();
    client.request(req({ schedule: schedule({ shape: "geometric" }) }));
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    expect(client.staleShape).toBe(true);
  });

  it("is true for a non-default spec at shape model — rho, STEPPED, PLATEAUS and TILT are as uncharted as the shape", async () => {
    fetchMock.mockImplementation(answers(result()));
    for (const over of [{ rho: 3 }, { stepped: true }, { plateaus: 10 }, { tilt: 0.4 }]) {
      const client = new ScheduleClient();
      client.request(req({ schedule: schedule(over) }));
      await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
      expect(client.staleShape).toBe(true);
    }
  });

  it("is false once the response echoes a shape (M3 landed)", async () => {
    fetchMock.mockImplementation(answers(result({ shape: "geometric" })));
    const client = new ScheduleClient();
    client.request(req({ schedule: schedule({ shape: "geometric" }) }));
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    expect(client.staleShape).toBe(false);
  });

  it("is false once the response echoes a shape even for a non-default spec at shape model", async () => {
    fetchMock.mockImplementation(answers(result({ shape: "model" })));
    const client = new ScheduleClient();
    client.request(req({ schedule: schedule({ rho: 3 }) }));
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    expect(client.staleShape).toBe(false);
  });

  it("is false for a wholly default spec even with no echoed shape", async () => {
    fetchMock.mockImplementation(answers(result()));
    const client = new ScheduleClient();
    client.request(req());
    await vi.advanceTimersByTimeAsync(SCHEDULE_DEBOUNCE_MS);
    expect(client.staleShape).toBe(false);
  });
});
