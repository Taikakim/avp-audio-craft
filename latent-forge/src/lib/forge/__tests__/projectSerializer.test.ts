import { beforeEach, describe, expect, it } from "vitest";
import { history } from "../../render/history.svelte";
import { arrangement } from "../../stores/arrangement.svelte";
import { settings } from "../../stores/settings.svelte";
import { view } from "../../stores/view.svelte";
import { CHAIN_DEFAULTS, MASTER_DEFAULT, MIX_DEFAULT, OVERLAP_DEFAULT } from "../defaults";
import {
  applyMasterPreset, applyProject, buildMasterPresetPayload, normalizeMaster, serializeProject, unsavedWorkKey,
  validateProjectV2,
} from "../projectSerializer.svelte";
import type { ProjectV2, RenderHistoryEntry } from "../types";

beforeEach(() => {
  arrangement.clips.splice(0, arrangement.clips.length);
  for (const lane of arrangement.lanes) lane.chain = structuredClone(CHAIN_DEFAULTS);
  arrangement.clearOverlapParams();
  settings.stage = "BASE";
  view.clearSelection();
  view.restoreUi({ bottomTab: "prompt", modules: ["files", "lane-chain"], sideOpen: true, terminal: "pane" });
});

describe("serializeProject reads the live stores into ProjectV2 (spec §9.2)", () => {
  it("carries meter, snap, viewport, lanes, clips, mix, master, defaults and ui", () => {
    arrangement.addClip({ lane: 0, startSec: 1, durSec: 3, audio: { kind: "crop", crop_id: "X" } });
    arrangement.lanes[0].chain.lora = { ckpt_path: "/SERVER/a.safetensors", slot: 2, strength: 1 };
    const p = serializeProject({ name: "my-session" });
    expect(p.version).toBe(2);
    expect(p.name).toBe("my-session");
    expect(p.meter).toEqual({ bpm: arrangement.bpm, beatsPerBar: arrangement.beatsPerBar });
    expect(p.snap).toBe(arrangement.snap);
    expect(p.view).toEqual({ pxPerSec: arrangement.pxPerSec, scrollSec: arrangement.scrollSec });
    expect(p.lanes).toHaveLength(4);
    // ckpt_path is the durable identity; the resident slot index is never saved (critic pass 2 #14)
    expect(p.lanes[0].chain.lora).toEqual({ ckpt_path: "/SERVER/a.safetensors", slot: null, strength: 1 });
    expect(arrangement.lanes[0].chain.lora.slot).toBe(2);   // the live chain keeps its resolution
    expect(p.clips).toHaveLength(1);
    expect(p.mix).toEqual(arrangement.mix);
    expect(p.master).toEqual(arrangement.master);
    expect(p.defaults).toEqual(settings.defaults);
    expect(p.backbone).toBe(settings.backboneId);
    expect(p.ckpt_path).toBe(settings.ckptPath);
    expect(p.ui).toEqual(view.snapshotUi());
  });

  it("carries every overlap keyed exactly as arrangement.overlaps names it", () => {
    arrangement.addClip({ lane: 0, startSec: 0, durSec: 10, audio: { kind: "crop", crop_id: "A" } });
    arrangement.addClip({ lane: 0, startSec: 6, durSec: 10, audio: { kind: "crop", crop_id: "B" } });
    const [ov] = arrangement.overlaps;
    arrangement.setOverlapParams(ov.key, { steps: 40 });
    const p = serializeProject({ name: "s" });
    expect(p.overlaps[ov.key].steps).toBe(40);
  });

  it("never persists a clip's previewAudio (spec §9.2 'Not serialised'), and returns plain data, not $state proxies", () => {
    const c = arrangement.addClip({ lane: 1, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: "P" } });
    arrangement.setPreviewAudio(c.id, { kind: "path", path: "/SERVER/out/stretched.wav" });
    const p = serializeProject({ name: "s" });
    expect(p.clips[0].previewAudio).toBeNull();
    expect(JSON.stringify(p)).not.toContain("stretched.wav");
    // structuredClone throws DataCloneError on a $state proxy (Global Constraint #7): passing
    // proves nothing proxied leaked into the result.
    expect(() => structuredClone(p)).not.toThrow();
    // and the live clip still has its in-memory preview
    expect(arrangement.clips[0].previewAudio).toEqual({ kind: "path", path: "/SERVER/out/stretched.wav" });
  });
});

describe("applyProject writes a loaded ProjectV2 back into the live stores", () => {
  it("round-trips a serialized project, including the backbone -> settings.stage", () => {
    arrangement.addClip({ lane: 2, startSec: 5, durSec: 4, audio: { kind: "crop", crop_id: "Z" } });
    settings.stage = "POST";
    const saved = serializeProject({ name: "round-trip" });
    expect(saved.backbone).toBe("medium");
    arrangement.clips.splice(0, arrangement.clips.length);
    settings.stage = "BASE";
    applyProject(saved);
    expect(arrangement.clips).toHaveLength(1);
    expect(arrangement.clips[0].lane).toBe(2);
    expect(arrangement.clips[0].previewAudio).toBeNull();
    expect(arrangement.bpm).toBe(saved.meter.bpm);
    expect(settings.stage).toBe("POST");   // backboneId is a getter over stage (M4 plan line 427)
    expect(view.snapshotUi()).toEqual(saved.ui);
  });

  it("clears the selection and every previous overlap's params -- nothing from the last project survives", () => {
    arrangement.addClip({ lane: 0, startSec: 0, durSec: 10, audio: { kind: "crop", crop_id: "A" } });
    arrangement.addClip({ lane: 0, startSec: 6, durSec: 10, audio: { kind: "crop", crop_id: "B" } });
    const [ov] = arrangement.overlaps;
    const saved = serializeProject({ name: "same-clips" });
    saved.overlaps = {};   // as a converted v1 file has it: same clip ids, so the same overlap key
    arrangement.setOverlapParams(ov.key, { steps: 40 });   // an edit the loaded project does not have
    view.select({ kind: "overlap", key: ov.key });
    applyProject(saved);
    expect(view.selection).toEqual({ kind: "none" });
    expect(arrangement.overlaps.map((o) => o.key)).toEqual([ov.key]);   // the key is back ...
    expect(arrangement.peekOverlapParams(ov.key).steps).toBe(OVERLAP_DEFAULT.steps);   // ... its old edit is not
  });
});

describe("validateProjectV2 checks a v2 object as a whole, before anything is applied (critic pass 2 #1)", () => {
  it("passes serializeProject's own output, and names the first missing field of anything else", () => {
    const good = JSON.parse(JSON.stringify(serializeProject({ name: "ok" }))) as Record<string, unknown>;
    expect(validateProjectV2(good)).toBe(good);
    for (const field of ["meter", "view", "lanes", "clips", "overlaps", "mix", "master", "defaults", "ui"]) {
      const broken = JSON.parse(JSON.stringify(good)) as Record<string, unknown>;
      delete broken[field];
      expect(() => validateProjectV2(broken)).toThrow(`not a v2 project: ${field}`);
    }
    expect(() => validateProjectV2({ version: 2 })).toThrow("not a v2 project: meter");
    expect(() => validateProjectV2(null)).toThrow("not a v2 project: version");
  });

  it("looks inside every entry, so nothing that passes can throw part-way through applyProject (critic pass 3 #8)", () => {
    arrangement.addClip({ lane: 0, startSec: 0, durSec: 10, audio: { kind: "crop", crop_id: "A" } });
    arrangement.addClip({ lane: 0, startSec: 6, durSec: 10, audio: { kind: "crop", crop_id: "B" } });
    const [ov] = arrangement.overlaps;
    arrangement.setOverlapParams(ov.key, { steps: 40 });
    const good = JSON.parse(JSON.stringify(serializeProject({ name: "ok" }))) as ProjectV2;
    expect(validateProjectV2(good)).toBe(good);
    const broken = (edit: (p: Record<string, any>) => void) => {
      const p = JSON.parse(JSON.stringify(good)) as Record<string, any>;
      edit(p);
      return p;
    };
    // M1's restoreUi calls .filter on it -- the LAST line of applyProject, after every store is written
    expect(() => validateProjectV2(broken((p) => { p.ui.modules = "files"; }))).toThrow("not a v2 project: ui");
    expect(() => validateProjectV2(broken((p) => { p.snap = "wobbly"; }))).toThrow("not a v2 project: snap");
    expect(() => validateProjectV2(broken((p) => { delete p.lanes[2].gain; }))).toThrow("not a v2 project: lanes[2]");
    expect(() => validateProjectV2(broken((p) => { p.lanes[1].chain.slots[0] = null; }))).toThrow("not a v2 project: lanes[1].chain");
    expect(() => validateProjectV2(broken((p) => { delete p.clips[1].history; }))).toThrow("not a v2 project: clips[1]");
    expect(() => validateProjectV2(broken((p) => { p.clips[0].offset_sec = "0"; }))).toThrow("not a v2 project: clips[0]");
    expect(() => validateProjectV2(broken((p) => { p.overlaps[ov.key].curve = null; }))).toThrow(`not a v2 project: overlaps.${ov.key}`);
    expect(() => validateProjectV2(broken((p) => { delete p.mix.nodes.MX; }))).toThrow("not a v2 project: mix");
    expect(() => validateProjectV2(broken((p) => { p.master.noise = null; }))).toThrow("not a v2 project: master");
  });
});

describe("buildMasterPresetPayload / applyMasterPreset (spec §9.3 master scope)", () => {
  it("captures every lane's chain, clip layout+a2a (no audio), mix, master, schedule+prompt only", () => {
    const clip = arrangement.addClip({ lane: 0, startSec: 2, durSec: 4, audio: { kind: "crop", crop_id: "Q" } });
    arrangement.setDetune(clip.id, 5);
    settings.defaults.prompt = "warm pad";
    const payload = buildMasterPresetPayload();
    expect(payload.lanes).toHaveLength(4);
    expect(payload.lanes[0].chain).toEqual(CHAIN_DEFAULTS);
    expect(payload.clips[0]).not.toHaveProperty("audio");
    expect(payload.clips[0].detune_cents).toBe(5);
    expect(payload.mix).toEqual(MIX_DEFAULT);
    expect(payload.master).toEqual(MASTER_DEFAULT);
    expect(payload.defaults.prompt).toBe("warm pad");
  });

  it("recall patches the same-id clip's layout and every lane's chain, and ignores a clip id no longer present", () => {
    const clip = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: "Q" } });
    const payload = buildMasterPresetPayload();
    arrangement.moveClip(clip.id, 9);   // M5's signature is (id, startSec) -- two arguments
    payload.clips.push({ id: "ghost", lane: 0, start_sec: 0, offset_sec: 0, dur_sec: 1, loop: false, native_bpm: null, detune_cents: 0, a2a: null });
    expect(() => applyMasterPreset(payload)).not.toThrow();
    expect(arrangement.clips.find((c) => c.id === clip.id)?.start_sec).toBe(0);
  });
});

describe("render history round-trips through ProjectV2 (M9 T3)", () => {
  function makeEntry(patch: Partial<RenderHistoryEntry> = {}): RenderHistoryEntry {
    return {
      job_id: "gen-1", forge_job_id: "forge-1", file: "out_00.wav", label: "GEN 12:00:00",
      kind: "gen", dur_sec: 45, source_clip_id: null, created: 1_759_000_000, ...patch,
    };
  }

  it("serializeProject writes the live history instead of the hardcoded empty triple", () => {
    history.clear();
    history.add(makeEntry());
    history.add(makeEntry({ forge_job_id: "forge-2", kind: "mix", job_id: "mix-1" }));
    const p = serializeProject({ name: "s" });
    expect(p.renders).toHaveLength(2);
    expect(p.renders[1].kind).toBe("mix");
    expect(p.mixdown).toBe(1);
    expect(p.preview).toBe(1);
  });

  it("serializeProject writes a SNAPSHOT -- a later render does not mutate an already-saved project", () => {
    history.clear();
    history.add(makeEntry());
    const p = serializeProject({ name: "s" });
    history.add(makeEntry({ forge_job_id: "forge-2" }));
    expect(p.renders).toHaveLength(1);
  });

  it("validateProjectV2 refuses a bad renders array and a mixdown that is not an index or null", () => {
    const base = serializeProject({ name: "s" });
    expect(() => validateProjectV2({ ...base, renders: "nope" })).toThrow(/renders/);
    expect(() => validateProjectV2({ ...base, renders: [{ job_id: "x" }] })).toThrow(/renders\[0\]/);
    expect(() => validateProjectV2({ ...base, mixdown: "1" })).toThrow(/mixdown/);
    expect(() => validateProjectV2({ ...base, preview: 1.5 })).toThrow(/preview/);
    expect(() => validateProjectV2({ ...base, mixdown: null, preview: null })).not.toThrow();
  });

  it("applyProject restores all three fields", () => {
    history.clear();
    const project = {
      ...serializeProject({ name: "s" }),
      renders: [makeEntry(), makeEntry({ forge_job_id: "forge-2", kind: "mix" })],
      mixdown: 1,
      preview: 0,
    };
    applyProject(validateProjectV2(project));
    expect(history.renders.map((r) => r.forge_job_id)).toEqual(["forge-1", "forge-2"]);
    expect(history.mixdown).toBe(1);
    expect(history.preview).toBe(0);
  });

  it("applyProject clears a previous session's history when the loaded project has none", () => {
    history.clear();
    history.add(makeEntry({ forge_job_id: "stale", kind: "mix" }));
    applyProject(validateProjectV2({ ...serializeProject({ name: "s" }), renders: [], mixdown: null, preview: null }));
    expect(history.renders).toEqual([]);
    expect(history.mixdown).toBeNull();
    expect(history.preview).toBeNull();
  });

  it("a finished render is NOT unsaved work -- workKey ignores renders/mixdown/preview", () => {
    history.clear();
    const before = unsavedWorkKey(serializeProject({ name: "" }));
    history.add(makeEntry({ kind: "mix" }));
    expect(unsavedWorkKey(serializeProject({ name: "" }))).toBe(before);
    arrangement.setBpm(arrangement.bpm + 1);
    expect(unsavedWorkKey(serializeProject({ name: "" }))).not.toBe(before);
  });
});

describe("a master saved before the lane-style LatCH (one head, one gain)", () => {
  const legacy = { latch_on: true, head: "rms_energy_bass", gain: 80, norm_on: false };

  it("is still a valid file, and a session with the new master shape is valid too", () => {
    const good = JSON.parse(JSON.stringify(serializeProject({ name: "ok" }))) as Record<string, unknown>;
    expect(() => validateProjectV2({ ...good, master: legacy })).not.toThrow();
    expect(() => validateProjectV2({ ...good, master: structuredClone(MASTER_DEFAULT) })).not.toThrow();
    // neither shape: slots present but one is malformed, or noise is not a number
    const m = structuredClone(MASTER_DEFAULT) as unknown as Record<string, any>;
    m.slots[1] = null;
    expect(() => validateProjectV2({ ...good, master: m })).toThrow("not a v2 project: master");
  });

  it("loads as the defaults with its LatCH off and its normalise toggle kept -- a gradient step has no target to carry over", () => {
    const out = normalizeMaster(legacy);
    expect(out).toEqual({ ...MASTER_DEFAULT, norm_on: false });
    expect(out.latch_on).toBe(false);
    expect("head" in out || "gain" in out).toBe(false);
  });

  it("leaves a current master untouched, as a copy", () => {
    const current = structuredClone(MASTER_DEFAULT);
    current.latch_on = true;
    current.noise = 0.4;
    current.slots[0].head = "hardness";
    const out = normalizeMaster(current);
    expect(out).toEqual(current);
    expect(out).not.toBe(current);
  });

  it("applyProject writes the normalised master into the store", () => {
    const good = JSON.parse(JSON.stringify(serializeProject({ name: "ok" }))) as ProjectV2;
    applyProject({ ...good, master: legacy as unknown as ProjectV2["master"] });
    expect(arrangement.master).toEqual({ ...MASTER_DEFAULT, norm_on: false });
  });
});
