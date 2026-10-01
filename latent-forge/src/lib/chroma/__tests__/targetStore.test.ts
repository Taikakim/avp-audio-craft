import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AudioRef, ForgeClip } from "../../forge/types";
import {
  ChromaTargetStore,
  EMPTY_KEYS_LABEL,
  NO_TARGET_LANE_LABEL,
  keysLabel,
  laneTargetLabel,
  laneTargetRefs,
} from "../targetStore.svelte";

function clip(over: Partial<ForgeClip>): ForgeClip {
  return {
    id: "c", lane: 0, start_sec: 0, offset_sec: 0, dur_sec: 4, loop: false,
    audio: { kind: "upload", sha256: "raw" }, previewAudio: null, native_bpm: null,
    detune_cents: 0, downbeats_sec: [], render: {} as never, a2a: null,
    latentState: "none", history: [],
    ...over,
  } as ForgeClip;
}

/** One frame of pure C, quantised the way /forge/chroma transports it. */
function chromaBody(cls: number, T: number) {
  const bands = new Uint8Array(3 * 128 * T);
  const fold = new Uint8Array(12 * T);
  for (let t = 0; t < T; t++) fold[cls * T + t] = 255;
  const b64 = (u: Uint8Array) => {
    let s = "";
    for (const b of u) s += String.fromCharCode(b);
    return btoa(s);
  };
  return {
    ok: true,
    frames: T,
    fps: 10.7666015625,
    bands: { shape: [3, 128, T], scale: [1, 1, 1], data_b64: b64(bands) },
    fold12: { shape: [12, T], scale: 1.0, data_b64: b64(fold) },
  };
}

let store: ChromaTargetStore;

beforeEach(() => {
  store = new ChromaTargetStore();
});

afterEach(() => {
  store.dispose();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("the labels the row shows when it has nothing to show", () => {
  it("names the TARGET lane, or says there is none", () => {
    expect(laneTargetLabel(2)).toBe("LANE 3");
    expect(laneTargetLabel(null)).toBe(NO_TARGET_LANE_LABEL);
  });

  it("lists the selected classes, or says none are", () => {
    const keys = new Array(12).fill(false);
    expect(keysLabel(keys)).toBe(EMPTY_KEYS_LABEL);
    keys[0] = true;
    keys[4] = true;
    keys[7] = true;
    expect(keysLabel(keys)).toBe("C E G");
  });
});

describe("laneTargetRefs reads the STRETCHED preview, falling back to the source", () => {
  it("takes previewAudio when a clip has one and audio when it does not", () => {
    const refs = laneTargetRefs(
      [
        clip({ id: "a", lane: 1, previewAudio: { kind: "path", path: "/stretched.wav" } }),
        clip({ id: "b", lane: 1 }),
        clip({ id: "c", lane: 0 }),
      ],
      1,
    );
    expect(refs).toEqual([
      { kind: "path", path: "/stretched.wav" },
      { kind: "upload", sha256: "raw" },
    ]);
  });

  it("is empty when no lane is the target at all", () => {
    expect(laneTargetRefs([clip({ lane: 0 })], null)).toEqual([]);
  });
});

describe("SEMITONE SET mode", () => {
  it("starts in lane mode with nothing selected", () => {
    expect(store.mode).toBe("lane");
    expect(store.keys.some((k) => k)).toBe(false);
  });

  it("toggles a key on and off again", () => {
    store.toggleKey(4);
    expect(store.keys[4]).toBe(true);
    store.toggleKey(4);
    expect(store.keys[4]).toBe(false);
  });

  it("fills the key row from a chord symbol and switches to SEMITONE SET", () => {
    store.setChordText("F#m");
    expect(store.mode).toBe("set");
    expect(store.chordOk).toBe(true);
    // F# A C#
    expect([...store.keys.keys()].filter((p) => store.keys[p])).toEqual([1, 6, 9]);
  });

  it("keeps half-typed text without touching the keys, and flags it", () => {
    store.toggleKey(0);
    store.setChordText("Cm");
    const before = [...store.keys];
    store.setChordText("Cmzz");
    expect(store.chordText).toBe("Cmzz");
    expect(store.chordOk).toBe(false);
    expect([...store.keys]).toEqual(before);
  });

  it("treats an empty field as neither right nor wrong", () => {
    store.setChordText("");
    expect(store.chordOk).toBe(true);
  });

  it("profiles the twelve toggles flat, 1 and 0", () => {
    store.setChordText("C");
    expect([...store.profile]).toEqual([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0]);
  });
});

describe("lane mode", () => {
  it("is an all-zero profile, never NaN, before any lane has been loaded", () => {
    expect(store.mode).toBe("lane");
    expect([...store.profile]).toEqual(new Array(12).fill(0));
    expect(store.laneClipCount).toBe(0);
  });

  it("sums every target-lane clip's fold and max-normalises the result", async () => {
    vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body ?? "{}")) as { audio: AudioRef };
      const cls = body.audio.kind === "crop" && body.audio.crop_id === "second" ? 7 : 0;
      return new Response(JSON.stringify(chromaBody(cls, 3)), {
        status: 200, headers: { "content-type": "application/json" },
      });
    }));
    await store.loadLane([{ kind: "crop", crop_id: "first" }, { kind: "crop", crop_id: "second" }]);
    expect(store.laneClipCount).toBe(2);
    expect(store.profile[0]).toBeCloseTo(1, 6);
    expect(store.profile[7]).toBeCloseTo(1, 6);
    expect(store.profile[3]).toBe(0);
    expect(store.error).toBe(null);
  });

  it("clears the profile and says so when the TARGET lane is empty", async () => {
    await store.loadLane([]);
    expect(store.laneClipCount).toBe(0);
    expect([...store.profile]).toEqual(new Array(12).fill(0));
  });

  it("surfaces a server error as one line rather than a half-built profile (spec §9.7)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(
      JSON.stringify({ ok: false, error: "no such crop" }),
      { status: 404, headers: { "content-type": "application/json" } },
    )));
    await store.loadLane([{ kind: "crop", crop_id: "gone" }]);
    expect(store.error).not.toBe(null);
    expect([...store.profile]).toEqual(new Array(12).fill(0));
    expect(store.pending).toBe(false);
  });
});
