// The load/import/save order (Task 9's WHY, steps 1-9), proven on the coupled cases. The App
// $effect is simulated by calling ctl.observe() wherever a store edit would re-run it.
import { afterEach, describe, expect, it, vi } from "vitest";
import { CHAIN_DEFAULTS, MASTER_DEFAULT, POST_DEFAULTS } from "../defaults";
import { arrangement } from "../../stores/arrangement.svelte";
import { settings, type ModelStage } from "../../stores/settings.svelte";
import { view } from "../../stores/view.svelte";
import { buildMasterPresetPayload, serializeProject, type MasterPresetPayload } from "../projectSerializer.svelte";
import { SessionController, type SessionDeps } from "../sessionController.svelte";
import type { ProjectV2 } from "../types";

function resetStores() {
  arrangement.clips.splice(0, arrangement.clips.length);
  for (const lane of arrangement.lanes) lane.chain = structuredClone(CHAIN_DEFAULTS);
  arrangement.master = structuredClone(MASTER_DEFAULT);
  settings.stage = "BASE";
  settings.stageLocked = false;
  settings.stageRebuilding = false;
  view.clearSelection();
}

/** Plain data holding one crop clip, built through the real serialiser; the stores are reset
 *  afterwards, so a test starts from a different arrangement than the one it will load. */
function project(name: string, cropId: string, stage: ModelStage = "BASE"): ProjectV2 {
  resetStores();
  settings.stage = stage;
  arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: cropId } });
  const p = JSON.parse(JSON.stringify(serializeProject({ name }))) as ProjectV2;
  resetStores();
  return p;
}

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

/** `confirmAnswer` answers every yes/no (critic pass 3 #3, #4); `exists` lists nothing unless a test says so. */
function harness(promptAnswer: string | null = null, confirmAnswer = true) {
  const api = {
    session: vi.fn<(name: string) => Promise<unknown>>(),
    saveSession: vi.fn(async (_name: string, _project: ProjectV2): Promise<unknown> => ({ ok: true })),
    setBackbone: vi.fn(async (_id: string): Promise<unknown> => ({ ok: true })),
    preset: vi.fn<(level: string, name: string) => Promise<unknown>>(),
    savePreset: vi.fn(async (_level: string, _name: string, _payload: unknown): Promise<unknown> => ({ ok: true })),
  };
  const deps: SessionDeps = {
    api, log: vi.fn(), prompt: vi.fn(() => promptAnswer), confirm: vi.fn(() => confirmAnswer),
    exists: vi.fn((_kind: "session" | "master", _name: string) => false), scheduleStretch: vi.fn(),
  };
  return { api, deps, ctl: new SessionController(deps) };
}

const loadedCrops = () => arrangement.clips.map((c) => (c.audio as { crop_id: string }).crop_id);
const savedCrops = (p: ProjectV2) => p.clips.map((c) => (c.audio as { crop_id: string }).crop_id);

afterEach(() => {
  vi.useRealTimers();
  resetStores();
});

describe("SessionController: one load/import sequence (critic pass 2 #1-#3, #6, #7)", () => {
  it("IMPORT of a malformed v2 file PUTs nothing and leaves the session, its autosave and the stores alone", async () => {
    vi.useFakeTimers();
    const { api, ctl } = harness();
    const take1 = project("take1", "T1");
    const broken = JSON.parse(JSON.stringify(project("broken", "X"))) as Record<string, unknown>;
    delete broken.ui;   // the LAST field applyProject reads: the old code had written every store by then
    api.session.mockResolvedValue(take1);
    await ctl.loadSession("take1");
    await ctl.importProjectFile({ name: "broken.json", text: async () => JSON.stringify(broken) });
    ctl.observe();                                    // the App effect re-running after the attempt
    vi.advanceTimersByTime(10_000);
    expect(api.saveSession).not.toHaveBeenCalled();   // nothing PUT anywhere
    expect(ctl.session).toBe("take1");                // not cleared: nothing was touched
    expect(loadedCrops()).toEqual(["T1"]);            // not half-applied
    arrangement.lanes[0].chain.latch_on = true;       // and take1 is still armed on take1's content
    ctl.observe();
    vi.advanceTimersByTime(2000);
    expect(api.saveSession).toHaveBeenCalledTimes(1);
    expect(api.saveSession.mock.calls[0][0]).toBe("take1");
    expect(savedCrops(api.saveSession.mock.calls[0][1])).toEqual(["T1"]);
  });

  it("a session that fails to load keeps the previous name, still armed -- nothing renamed, nothing lost", async () => {
    vi.useFakeTimers();
    const { api, ctl } = harness();
    api.session.mockResolvedValueOnce(project("take1", "T1")).mockRejectedValueOnce(new Error("404 take2"));
    await ctl.loadSession("take1");
    await ctl.loadSession("take2");
    expect(ctl.session).toBe("take1");
    expect(ctl.loading).toBe(false);
    expect(loadedCrops()).toEqual(["T1"]);
    arrangement.lanes[0].chain.latch_on = true;       // take1's own edit, after the failed pick
    ctl.observe();
    vi.advanceTimersByTime(2000);
    expect(api.saveSession).toHaveBeenCalledTimes(1);
    expect(api.saveSession.mock.calls[0][0]).toBe("take1");   // autosaved to take1, not dropped
    expect(await ctl.saveSession()).toBe("take1");            // an explicit SAVE goes to take1 too
    expect(api.saveSession.mock.calls[1][0]).toBe("take1");
  });

  it("SAVE while a load is in flight writes nothing -- neither to the session being loaded nor to the previous one", async () => {
    const { api, ctl } = harness();
    const take1 = project("take1", "T1");
    const take2 = project("take2", "T2");
    const pending = deferred<unknown>();
    api.session.mockResolvedValueOnce(take1).mockReturnValueOnce(pending.promise);
    await ctl.loadSession("take1");
    const loading = ctl.loadSession("take2");
    expect(ctl.loading).toBe(true);
    expect(ctl.session).toBe("take1");                // the previous name until take2 is applied AND armed
    expect(ctl.loadingName).toBe("take2");            // ... beside `loading take2…` (critic pass 3 #11)
    expect(await ctl.saveSession()).toBeNull();
    pending.resolve(take2);
    await loading;
    expect(api.saveSession).not.toHaveBeenCalled();
    expect(ctl.session).toBe("take2");
    expect(ctl.loadingName).toBe("");
    expect(loadedCrops()).toEqual(["T2"]);
    expect(await ctl.saveSession()).toBe("take2");    // once armed, SAVE writes take2's content to take2
    expect(savedCrops(api.saveSession.mock.calls[0][1])).toEqual(["T2"]);
  });

  it("a failed model rebuild reverts the client stage but not the session's backbone, and edits made during the rebuild are saved", async () => {
    vi.useFakeTimers();
    const { api, ctl } = harness();
    const post = project("post-set", "P", "POST");
    expect(post.backbone).toBe("medium");
    const rebuild = deferred<unknown>();
    api.session.mockResolvedValue(post);
    api.setBackbone.mockReturnValue(rebuild.promise);
    const loading = ctl.loadSession("post-set");
    await vi.waitFor(() => expect(api.setBackbone).toHaveBeenCalledWith("medium"));
    arrangement.lanes[0].chain.latch_on = true;       // edited while the rebuild is still running
    ctl.observe();                                    // disarmed: nothing is queued yet
    rebuild.reject(new Error("rebuild failed"));
    await loading;
    expect(settings.stage).toBe("BASE");              // M4: never claim a model the server did not load
    expect(ctl.session).toBe("post-set");
    vi.advanceTimersByTime(2000);                     // the mid-rebuild edit was not folded into the baseline
    expect(api.saveSession).toHaveBeenCalledTimes(1);
    const saved = api.saveSession.mock.calls[0][1];
    expect(saved.backbone).toBe("medium");            // the revert did not reach the session
    expect(saved.defaults).toEqual(post.defaults);    // nor did it touch the loaded sampling defaults
    expect(saved.lanes[0].chain.latch_on).toBe(true);
  });

  it("a successful load schedules one stretch per loaded clip, then arms: only a later edit autosaves, under the loaded name", async () => {
    vi.useFakeTimers();
    const { api, deps, ctl } = harness();
    api.session.mockResolvedValue(project("take1", "T1"));
    await ctl.loadSession("take1");
    expect(deps.scheduleStretch).toHaveBeenCalledTimes(1);
    expect(deps.scheduleStretch).toHaveBeenCalledWith(arrangement.clips[0].id);
    ctl.observe();                                    // the effect re-running on what was just loaded
    vi.advanceTimersByTime(5000);
    expect(api.saveSession).not.toHaveBeenCalled();
    arrangement.master.noise = 90;
    ctl.observe();
    vi.advanceTimersByTime(2000);
    expect(api.saveSession).toHaveBeenCalledTimes(1);
    expect(api.saveSession.mock.calls[0][0]).toBe("take1");
    expect(api.saveSession.mock.calls[0][1].master.noise).toBe(90);
  });

  it("a v1 IMPORT keeps the loaded stage (v1 records no backbone) and that stage's sampling fields: no rebuild, and SAVE records the current backbone", async () => {
    const { api, ctl } = harness("from-v1");
    settings.stage = "POST";
    await ctl.importProjectFile({
      name: "old-set.json",
      text: async () => JSON.stringify({ version: 1, meter: { bpm: 100, beatsPerBar: 4 }, lanes: [], clips: [] }),
    });
    expect(arrangement.bpm).toBe(100);                // it did load
    expect(settings.stage).toBe("POST");
    // the converter fills defaults from BASE_DEFAULTS; under POST, M4's STAGE_FIELDS must stay POST's (critic pass 3 #7)
    expect(settings.defaults.steps).toBe(POST_DEFAULTS.steps);
    expect(settings.defaults.sampler_type).toBe(POST_DEFAULTS.sampler_type);
    expect(settings.defaults.schedule).toEqual(POST_DEFAULTS.schedule);
    expect(api.setBackbone).not.toHaveBeenCalled();
    expect(ctl.session).toBe("");                     // unsaved until SAVE names it
    expect(await ctl.saveSession()).toBe("from-v1");
    expect(api.saveSession.mock.calls[0][1].backbone).toBe("medium");
  });
});

describe("SessionController after critic pass 3: versions, prompts, PUT order, rebuild races, master presets", () => {
  it("a session or file whose version is neither 1 nor 2 is refused before anything is touched -- never converted as if it were v1 (#1)", async () => {
    vi.useFakeTimers();
    const { api, ctl } = harness();
    const future = { ...project("take2", "T2"), version: 3 };
    const stringVersion = JSON.stringify({ ...project("x", "X"), version: "2" });
    api.session.mockResolvedValueOnce(project("take1", "T1")).mockResolvedValueOnce(future);
    await ctl.loadSession("take1");
    await ctl.loadSession("take2");
    await ctl.importProjectFile({ name: "string-version.json", text: async () => stringVersion });
    ctl.observe();
    vi.advanceTimersByTime(10_000);
    expect(api.saveSession).not.toHaveBeenCalled();   // nothing PUT: the converter would have emptied take2
    expect(ctl.session).toBe("take1");
    expect(loadedCrops()).toEqual(["T1"]);
    arrangement.master.noise = 90;                     // take1 is still armed on take1's content
    ctl.observe();
    vi.advanceTimersByTime(2000);
    expect(api.saveSession).toHaveBeenCalledTimes(1);
    expect(api.saveSession.mock.calls[0][0]).toBe("take1");
  });

  it("loading or importing over edited work no session owns asks first -- a refusal changes nothing (#3)", async () => {
    const { api, deps, ctl } = harness(null, false);
    const file = JSON.stringify(project("t", "T"));
    api.session.mockResolvedValue(project("take1", "T1"));
    arrangement.addClip({ lane: 1, startSec: 0, durSec: 4, audio: { kind: "crop", crop_id: "MINE" } });   // a fresh tab's work
    await ctl.loadSession("take1");
    expect(deps.confirm).toHaveBeenCalledTimes(1);
    expect(loadedCrops()).toEqual(["MINE"]);          // declined: nothing replaced
    expect(ctl.session).toBe("");
    await ctl.importProjectFile({ name: "t.json", text: async () => file });
    expect(deps.confirm).toHaveBeenCalledTimes(2);
    expect(loadedCrops()).toEqual(["MINE"]);
    vi.mocked(deps.confirm).mockReturnValue(true);
    await ctl.importProjectFile({ name: "t.json", text: async () => file });
    expect(deps.confirm).toHaveBeenCalledTimes(3);
    expect(loadedCrops()).toEqual(["T"]);
    await ctl.loadSession("take1");                   // an untouched import is on disk already: no question
    expect(deps.confirm).toHaveBeenCalledTimes(3);
    expect(ctl.session).toBe("take1");
    expect(api.saveSession).not.toHaveBeenCalled();
  });

  it("SAVE and MASTER PRESET SAVE under a typed name that is already listed ask before overwriting it (#4)", async () => {
    const { api, deps, ctl } = harness(null, false);
    vi.mocked(deps.exists).mockImplementation((kind, name) => name === (kind === "session" ? "take1" : "live A"));
    vi.mocked(deps.prompt).mockReturnValue("take1");
    expect(await ctl.saveSession()).toBeNull();       // declined: take1 on the server is not replaced
    expect(api.saveSession).not.toHaveBeenCalled();
    expect(ctl.session).toBe("");
    vi.mocked(deps.prompt).mockReturnValue("live A");
    expect(await ctl.saveMasterPreset("")).toBeNull();
    expect(api.savePreset).not.toHaveBeenCalled();
    expect(deps.confirm).toHaveBeenCalledTimes(2);
    vi.mocked(deps.confirm).mockReturnValue(true);
    expect(await ctl.saveMasterPreset("")).toBe("live A");
    expect(api.savePreset.mock.calls[0].slice(0, 2)).toEqual(["master", "live A"]);
    vi.mocked(deps.prompt).mockReturnValue("take1");
    expect(await ctl.saveSession()).toBe("take1");
    expect(api.saveSession.mock.calls[0][0]).toBe("take1");
  });

  it("PUTs to one session are ordered: a second autosave waits for the first, and re-loading that session waits for both (#5)", async () => {
    vi.useFakeTimers();
    const { api, ctl } = harness();
    api.session.mockResolvedValue(project("take1", "T1"));
    await ctl.loadSession("take1");
    const first = deferred<unknown>();
    api.saveSession.mockReturnValueOnce(first.promise);
    arrangement.master.noise = 90;
    ctl.observe();
    vi.advanceTimersByTime(2000);                     // PUT #1 in flight
    arrangement.master.noise = 91;
    ctl.observe();
    vi.advanceTimersByTime(2000);                     // PUT #2 due -- queued behind #1, not sent
    expect(api.saveSession).toHaveBeenCalledTimes(1);
    const reload = ctl.loadSession("take1");
    expect(api.session).toHaveBeenCalledTimes(1);     // the GET waits for take1's PUTs too
    first.resolve({ ok: true });
    await reload;
    expect(api.saveSession).toHaveBeenCalledTimes(2);
    expect(api.saveSession.mock.calls[1][1].master.noise).toBe(91);
    expect(api.session).toHaveBeenCalledTimes(2);
  });

  it("a load superseded mid-rebuild by one that fails: the timeline goes unsaved and STAGE follows the server, not the orphaned project (#6, #9)", async () => {
    vi.useFakeTimers();
    const { api, ctl } = harness();
    const rebuild = deferred<unknown>();
    const take2 = deferred<unknown>();
    api.session
      .mockResolvedValueOnce(project("take1", "T1"))
      .mockResolvedValueOnce(project("post-set", "P", "POST"))
      .mockReturnValueOnce(take2.promise);
    api.setBackbone.mockReturnValue(rebuild.promise);
    await ctl.loadSession("take1");
    const loadA = ctl.loadSession("post-set");
    await vi.waitFor(() => expect(api.setBackbone).toHaveBeenCalledWith("medium"));
    const loadB = ctl.loadSession("take2");
    take2.reject(new Error("404 take2"));
    await loadB;                                      // B applied nothing; A's project is in the stores
    expect(ctl.loading).toBe(false);
    expect(ctl.session).toBe("");                     // settle's orphan branch: no session owns them
    expect(loadedCrops()).toEqual(["P"]);
    rebuild.reject(new Error("rebuild failed"));
    await loadA;
    await vi.waitFor(() => expect(settings.stage).toBe("BASE"));   // the server never left BASE
    arrangement.master.noise = 90;
    ctl.observe();
    vi.advanceTimersByTime(10_000);
    expect(api.saveSession).not.toHaveBeenCalled();   // nothing armed: neither take1 nor post-set
  });

  it("a SAVE whose PUT is still pending when a load commits names and arms nothing -- the load owns the stores (#9)", async () => {
    vi.useFakeTimers();
    const { api, ctl } = harness();
    api.session.mockResolvedValueOnce(project("take1", "T1")).mockResolvedValueOnce(project("take2", "T2"));
    await ctl.loadSession("take1");
    const put = deferred<unknown>();
    api.saveSession.mockReturnValueOnce(put.promise);
    const saving = ctl.saveSession();
    await ctl.loadSession("take2");
    expect(ctl.session).toBe("take2");
    put.resolve({ ok: true });
    expect(await saving).toBe("take1");               // it did save, under its own name ...
    expect(ctl.session).toBe("take2");                // ... and renamed nothing
    arrangement.master.noise = 90;
    ctl.observe();
    vi.advanceTimersByTime(2000);
    expect(api.saveSession).toHaveBeenCalledTimes(2);
    expect(api.saveSession.mock.calls[1][0]).toBe("take2");
    expect(savedCrops(api.saveSession.mock.calls[1][1])).toEqual(["T2"]);
  });

  it("an apply that throws anyway leaves the timeline unsaved: nothing is named, armed or PUT (#9)", async () => {
    vi.useFakeTimers();
    const { api, ctl } = harness();
    api.session.mockResolvedValueOnce(project("take1", "T1")).mockResolvedValueOnce(project("take2", "T2"));
    await ctl.loadSession("take1");
    const restoreUi = vi.spyOn(view, "restoreUi").mockImplementationOnce(() => {
      throw new Error("boom");                        // applyProject's LAST write: every store is take2's by now
    });
    await ctl.loadSession("take2");
    restoreUi.mockRestore();
    expect(ctl.session).toBe("");
    expect(ctl.loading).toBe(false);
    arrangement.master.noise = 90;
    ctl.observe();
    vi.advanceTimersByTime(10_000);
    expect(api.saveSession).not.toHaveBeenCalled();   // not take1 (its content is gone), not take2 (half-applied)
  });

  it("MASTER PRESET recall applies nothing mid-load, nothing a load overtook, and nothing malformed -- validated whole first (#2, #12)", async () => {
    const { api, ctl } = harness();
    const take1 = project("take1", "T1");
    const take2 = project("take2", "T2");
    const pending = deferred<unknown>();
    api.session.mockReturnValueOnce(pending.promise).mockResolvedValueOnce(take2);
    const loading = ctl.loadSession("take1");
    expect(await ctl.recallMasterPreset("live A")).toBe(false);   // refused while take1 loads
    expect(api.preset).not.toHaveBeenCalled();
    pending.resolve(take1);
    await loading;
    const preset = deferred<unknown>();
    api.preset.mockReturnValueOnce(preset.promise);
    const recall = ctl.recallMasterPreset("live A");
    await ctl.loadSession("take2");                   // picked while the preset was in flight
    const late: MasterPresetPayload = { ...buildMasterPresetPayload(), master: { ...MASTER_DEFAULT, noise: 99 } };
    preset.resolve(late);
    expect(await recall).toBe(false);                 // take1's pick never lands on take2's stores
    expect(arrangement.master.noise).toBe(MASTER_DEFAULT.noise);
    const broken = JSON.parse(JSON.stringify(late)) as Record<string, unknown>;
    (broken.lanes as MasterPresetPayload["lanes"])[0].chain.latch_on = true;
    delete broken.defaults;                           // read LAST by applyMasterPreset
    api.preset.mockResolvedValueOnce(broken);
    expect(await ctl.recallMasterPreset("broken")).toBe(false);
    expect(arrangement.lanes[0].chain.latch_on).toBe(false);   // not half-applied
    expect(arrangement.master.noise).toBe(MASTER_DEFAULT.noise);
    api.preset.mockResolvedValueOnce(late);
    expect(await ctl.recallMasterPreset("live A")).toBe(true);
    expect(arrangement.master.noise).toBe(99);
  });

  it("MASTER PRESET recall re-arms every clip's stretch, since it can move native_bpm/detune (review 2026-10-01)", async () => {
    const { api, deps, ctl } = harness();
    api.session.mockResolvedValueOnce(project("take1", "T1"));
    await ctl.loadSession("take1");
    (deps.scheduleStretch as ReturnType<typeof vi.fn>).mockClear();
    const payload = buildMasterPresetPayload();
    payload.clips[0].detune_cents = 50;
    api.preset.mockResolvedValueOnce(payload);
    expect(await ctl.recallMasterPreset("live A")).toBe(true);
    expect(arrangement.clips[0].detune_cents).toBe(50);
    expect(deps.scheduleStretch).toHaveBeenCalledWith(arrangement.clips[0].id);
  });

  it("a load never overlaps M4's STAGE rebuild: refused while one runs, and it holds settings.stageLocked throughout (reconcile pass, OQ 32)", async () => {
    const { api, deps, ctl } = harness();
    settings.stageRebuilding = true;                  // M4 T9's confirmStage is awaiting setBackbone
    try {
      await ctl.loadSession("take1");
      await ctl.importProjectFile({ name: "x.json", text: async () => "{}" });
      expect(api.session).not.toHaveBeenCalled();     // refused before the fetch
      expect(ctl.loading).toBe(false);
      expect(settings.stageLocked).toBe(false);
      expect(deps.log).toHaveBeenCalledWith(expect.stringContaining("MODEL STAGE is rebuilding"), "error");
    } finally {
      settings.stageRebuilding = false;
    }
    const take1 = project("take1", "T1");
    const pending = deferred<unknown>();
    api.session.mockReturnValueOnce(pending.promise);
    const loading = ctl.loadSession("take1");
    expect(settings.stageLocked).toBe(true);          // M4's MODEL STAGE offers no switch now
    pending.resolve(take1);
    await loading;
    expect(ctl.session).toBe("take1");
    expect(settings.stageLocked).toBe(false);         // released when the load settles
  });

  it("the stage lock outlives a superseded load's rebuild: M4's STAGE stays locked until that setBackbone settles (critic follow-up #3)", async () => {
    const { api, ctl } = harness();
    const rebuild = deferred<unknown>();
    const take2 = deferred<unknown>();
    api.session
      .mockResolvedValueOnce(project("post-set", "P", "POST"))
      .mockReturnValueOnce(take2.promise);
    api.setBackbone.mockReturnValue(rebuild.promise);
    const loadA = ctl.loadSession("post-set");
    await vi.waitFor(() => expect(api.setBackbone).toHaveBeenCalledWith("medium"));
    const loadB = ctl.loadSession("take2");
    take2.reject(new Error("404 take2"));
    await loadB;                                      // the LATEST load ended early ...
    expect(ctl.loading).toBe(false);
    expect(settings.stageLocked).toBe(true);          // ... but A's rebuild is still on the server: no STAGE yet
    rebuild.reject(new Error("rebuild failed"));
    await loadA;
    await vi.waitFor(() => expect(settings.stageLocked).toBe(false));   // released once it settled
    expect(api.setBackbone).toHaveBeenCalledTimes(1);   // and nothing sent a second, parallel one
  });
});
