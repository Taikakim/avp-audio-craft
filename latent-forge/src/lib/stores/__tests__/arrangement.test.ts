import { beforeEach, describe, expect, it } from "vitest";
import { A2A_ENVELOPE_DEFAULT } from "../../forge/defaults";
import type { AudioRef } from "../../forge/types";
import { arrangement, MAX_PX_PER_SEC, MIN_PX_PER_SEC } from "../arrangement.svelte";

const REF: AudioRef = { kind: "crop", crop_id: "000412" };

function reset() {
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
  arrangement.setBpm(120);
  arrangement.setSnap("free");
  for (let i = 0; i < 4; i++) {
    arrangement.lanes[i].muted = false;
    arrangement.lanes[i].solo = false;
    arrangement.lanes[i].gain = 1;
  }
}

beforeEach(reset);

describe("adding clips", () => {
  it("returns the LIVE element, not the object it built", () => {
    const clip = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    clip.start_sec = 2;
    expect(arrangement.clips[0].start_sec).toBe(2);
  });

  it("seeds render settings that are not shared between clips", () => {
    const a = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    const b = arrangement.addClip({ lane: 1, startSec: 0, durSec: 4, audio: REF });
    a.render.schedule.rho = 9;
    expect(b.render.schedule.rho).toBe(1);
  });

  it("starts with no a2a and no detune", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    expect(c.a2a).toBeNull();
    expect(c.detune_cents).toBe(0);
    expect(c.loop).toBe(false);
  });
});

describe("project tempo is non-elastic (spec §7.3)", () => {
  it("leaves start_sec alone and rescales duration by the tempo ratio", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 8, durSec: 4, audio: REF, nativeBpm: 120 });
    arrangement.setBpm(140);
    expect(c.start_sec).toBe(8);
    expect(c.dur_sec).toBeCloseTo(4 * (120 / 140), 6);
  });

  it("does not rescale a clip with no native tempo", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    arrangement.setBpm(140);
    expect(c.dur_sec).toBe(4);
  });

  it("rescales the TRIM as well, or a trimmed clip plays different material", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 8, audio: REF, nativeBpm: 120 });
    arrangement.trimClip(c.id, "start", 2);          // offset_sec = 2, dur_sec = 6
    arrangement.setBpm(240);                          // stretched source halves
    expect(c.offset_sec).toBeCloseTo(1, 9);
    expect(c.dur_sec).toBeCloseTo(3, 9);
  });
});

describe("trim (spec §7.3 — offset and start move together at the head)", () => {
  it("head trim moves start and offset by the same amount", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 4, durSec: 8, audio: REF });
    arrangement.trimClip(c.id, "start", 5);
    expect(c.start_sec).toBe(5);
    expect(c.offset_sec).toBe(1);
    expect(c.dur_sec).toBe(7);
  });

  it("refuses a head trim that would run before the source", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 4, durSec: 8, audio: REF });
    arrangement.trimClip(c.id, "start", 1);
    expect(c.offset_sec).toBe(0);
    expect(c.dur_sec).toBe(8);
  });

  it("tail trim changes only the duration", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 4, durSec: 8, audio: REF });
    arrangement.trimClip(c.id, "end", 9);
    expect(c.start_sec).toBe(4);
    expect(c.dur_sec).toBe(5);
  });
});

describe("staleness (ORIENTATION §3 — a latent is valid only where it was encoded)", () => {
  it("marks a valid latent-backed clip stale when it moves", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    c.latentState = "valid";
    c.encodedAtSec = 0;
    arrangement.moveClip(c.id, 3);
    expect(c.latentState).toBe("stale");
  });

  it("leaves a clip with no latent alone", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    arrangement.moveClip(c.id, 3);
    expect(c.latentState).toBe("none");
  });
});

describe("overlaps are derived, per lane, and keyed stably", () => {
  it("finds one overlap between two clips in the same lane", () => {
    const a = arrangement.addClip({ lane: 0, startSec: 0, durSec: 8, audio: REF });
    const b = arrangement.addClip({ lane: 0, startSec: 6, durSec: 8, audio: REF });
    expect(arrangement.overlaps).toHaveLength(1);
    expect(arrangement.overlaps[0]).toMatchObject({ lane: 0, start_sec: 6, end_sec: 8, a_id: a.id, b_id: b.id });
    expect(arrangement.overlaps[0].key).toBe(`${a.id}-${b.id}`);
  });

  it("finds a non-adjacent pair — the case the drawing's adjacency loop misses", () => {
    // A spans everything; B and C sit inside it. Sorted A,B,C, so (A,C) is not adjacent.
    const a = arrangement.addClip({ lane: 0, startSec: 0, durSec: 10, audio: REF });
    arrangement.addClip({ lane: 0, startSec: 2, durSec: 1, audio: REF });
    const c = arrangement.addClip({ lane: 0, startSec: 5, durSec: 1, audio: REF });
    const keys = arrangement.overlaps.map((o) => o.key);
    expect(keys).toContain(`${a.id}-${c.id}`);
  });

  it("does not pair clips in different lanes", () => {
    arrangement.addClip({ lane: 0, startSec: 0, durSec: 8, audio: REF });
    arrangement.addClip({ lane: 1, startSec: 6, durSec: 8, audio: REF });
    expect(arrangement.overlaps).toHaveLength(0);
  });

  it("gives an overlap the spec §7.2 defaults on first access and keeps edits", () => {
    const a = arrangement.addClip({ lane: 0, startSec: 0, durSec: 8, audio: REF });
    const b = arrangement.addClip({ lane: 0, startSec: 6, durSec: 8, audio: REF });
    const key = `${a.id}-${b.id}`;
    expect(arrangement.overlapParams(key).steps).toBe(28);
    expect(arrangement.overlapParams(key).cfg).toBe(3.0);
    expect(arrangement.overlapParams(key).chroma_xfade).toBe(true);
    arrangement.setOverlapParams(key, { steps: 40 });
    expect(arrangement.overlapParams(key).steps).toBe(40);
  });

  it("exposes M4's settings seam without ever seeding: a clip's own render, an overlap's only once created", () => {
    const a = arrangement.addClip({ lane: 0, startSec: 0, durSec: 8, audio: REF });
    const b = arrangement.addClip({ lane: 0, startSec: 6, durSec: 8, audio: REF });
    const key = `${a.id}-${b.id}`;
    expect(arrangement.settingsSource.clipSettings(a.id)).toBe(a.render);   // the owner's object, not a copy
    expect(arrangement.settingsSource.clipSettings("nope")).toBeNull();
    expect(arrangement.settingsSource.overlapSettings(key)).toBeNull();      // not created yet --
    expect(arrangement.settingsSource.overlapSettings(key)).toBeNull();      // and reading did not create it
    const params = arrangement.overlapParams(key);                         // what OverlapBox's click does
    expect(arrangement.settingsSource.overlapSettings(key)).toBe(params.render);
  });
});

describe("a2a (spec §5.2)", () => {
  it("initialises the envelope flat at the clip's noise value", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    arrangement.ensureA2A(c.id);
    expect(c.a2a!.envelope).toEqual(A2A_ENVELOPE_DEFAULT);
    expect(c.a2a!.noise).toBe(0.4);
  });

  it("scales all four points proportionally when NOISE changes afterwards", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    arrangement.ensureA2A(c.id);
    arrangement.setEnvelope(c.id, { points: [0.2, 0.4, 0.6, 0.8], curves: [0, 0, 0] });
    arrangement.setNoise(c.id, 0.8);           // was 0.4 -> factor 2
    expect(c.a2a!.envelope.points).toEqual([0.4, 0.8, 1, 1]);   // clamped at 1
  });

  it("survives a pass through zero instead of pinning every point to 1", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    arrangement.ensureA2A(c.id);
    arrangement.setNoise(c.id, 0);                       // legal drag value (§5.1)
    expect(c.a2a!.envelope.points).toEqual([0, 0, 0, 0]);
    arrangement.setNoise(c.id, 0.5);                     // from 0: flat at the new value
    expect(c.a2a!.envelope.points).toEqual([0.5, 0.5, 0.5, 0.5]);
  });
});

describe("viewport", () => {
  it("clamps zoom to its range", () => {
    arrangement.zoomBy(1e6);
    expect(arrangement.pxPerSec).toBe(MAX_PX_PER_SEC);
    arrangement.zoomBy(1e-6);
    expect(arrangement.pxPerSec).toBe(MIN_PX_PER_SEC);
  });

  it("never scrolls before zero", () => {
    arrangement.setScrollSec(-5);
    expect(arrangement.scrollSec).toBe(0);
  });
});

describe("solo and mute decide audibility together", () => {
  it("soloing one lane silences the others", () => {
    arrangement.toggleSolo(2);
    expect(arrangement.isAudible(0)).toBe(false);
    expect(arrangement.isAudible(2)).toBe(true);
  });

  it("mute applies when nothing is soloed", () => {
    arrangement.toggleMute(1);
    expect(arrangement.isAudible(1)).toBe(false);
    expect(arrangement.isAudible(0)).toBe(true);
  });
});
