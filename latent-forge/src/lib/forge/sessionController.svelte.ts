// The ONE session load / IMPORT / SAVE sequence (spec §9.2), plus MASTER PRESET recall and save,
// outside App.svelte so every ordering guarantee is unit-tested (sessionController.test.ts). Task
// 9's WHY states the order as steps 1-9; the numbered comments below are those steps. Invariant,
// whenever `loading` is false: either `session` is "" and autosave is disarmed, or `session` is X,
// autosave is armed on X, and the stores hold X's content (possibly edited).
import { scheduleStretch as m5ScheduleStretch } from "../clips/lifecycle";
import { arrangement } from "../stores/arrangement.svelte";
import { settings, STAGE_BACKBONE, type ModelStage } from "../stores/settings.svelte";
import { createSnapshotAutosave, type SnapshotAutosave } from "./autosave";
import { convertProjectV1 } from "./convertProjectV1";
import {
  applyMasterPreset, applyProject, buildMasterPresetPayload, serializeProject, validateMasterPreset,
  validateProjectV2, type MasterPresetPayload, unsavedWorkKey } from "./projectSerializer.svelte";
import { isValidSessionName } from "./sessionName";
import type { ProjectV2 } from "./types";

export interface SessionDeps {
  api: {
    session(name: string): Promise<unknown>;
    saveSession(name: string, project: ProjectV2): Promise<unknown>;
    setBackbone(id: string): Promise<unknown>;
    preset(level: string, name: string): Promise<unknown>;
    savePreset(level: string, name: string, payload: unknown): Promise<unknown>;
  };
  log(text: string, level?: "info" | "error"): void;
  prompt(message: string): string | null;
  /** Yes/no before unsaved work is replaced or a listed name overwritten (critic pass 3 #3, #4). */
  confirm(message: string): boolean;
  /** Whether the TopBar already lists a session / master preset of that name (App reads its lists). */
  exists(kind: "session" | "master", name: string): boolean;
  /** M5 T10's debounced per-clip stretch; defaults to the real one, tests pass a spy. */
  scheduleStretch?: (clipId: string) => void;
  delayMs?: number;
}

const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));

interface Loaded { project: ProjectV2; kind: "v1" | "v2" }

/** Step 3. v2 is validated as a whole (throws on a malformed object, before anything is touched);
 *  v1 goes through the converter (Task 8, never throws); ANY other version -- missing, "2", 3 -- is
 *  refused, never converted as if it were v1 (critic pass 3 #1: the converter would read v1 field
 *  names off it and empty the timeline). v1's own loadJSON refuses the same way. */
function toLoaded(raw: unknown): Loaded {
  const version = (raw as { version?: unknown } | null)?.version;
  if (version === 2) return { project: validateProjectV2(raw), kind: "v2" };
  if (version === 1) return { project: convertProjectV1(raw), kind: "v1" };
  throw new Error(`unsupported project version ${JSON.stringify(version) ?? "(none)"}`);
}

export class SessionController {
  /** The session the TopBar shows. See the invariant above. */
  session = $state("");
  /** A load or import is in flight. SAVE is refused meanwhile. */
  loading = $state(false);
  /** What is loading, for the TopBar's `loading <name>…` note (critic pass 3 #11); "" when idle. */
  loadingName = $state("");

  private seq = 0;
  /** A superseded load wrote its project into the stores and never armed: they belong to no one. */
  private orphaned = false;
  /** Step 8's pin: a loaded session's own backbone, serialised in place of settings.backboneId
   *  while the stage is still `underStage` (a failed rebuild, or a backbone with no stage). */
  private pin: { backbone: string; underStage: ModelStage } | null = null;
  /** workKey of what the stores held when last loaded (or at launch): step 3's reference. */
  private unsavedKey: string;
  /** Step 8. The stage the server holds while a rebuild this controller started is unsettled or
   *  unreconciled; null = trust settings.stage (M4: with nothing rebuilding, the client stage IS
   *  the loaded model -- so M4's own STAGE control, used between loads, stays authoritative). */
  private serverStage: ModelStage | null = null;
  /** The last rebuild this controller started. The next one waits for it: rebuilds never overlap. */
  private rebuildTail: Promise<void> = Promise.resolve();
  /** A setBackbone this controller started has not settled. settings.stageLocked outlives `loading`
   *  while it is true (critic follow-up #3): a superseded load's rebuild can still be running after
   *  the latest load ended, and M4's STAGE must not send a parallel setBackbone meanwhile. */
  private rebuildInFlight = false;
  /** The latest PUT per session name, settled. The next PUT to that name, and a load of it, wait. */
  private puts = new Map<string, Promise<void>>();
  private autosave: SnapshotAutosave;
  // A plain field, not a `constructor(private deps)` parameter property: that is TS-only emit,
  // which Svelte's type-stripping of rune modules does not promise to support.
  private deps: SessionDeps;

  constructor(deps: SessionDeps) {
    this.deps = deps;
    this.unsavedKey = unsavedWorkKey(serializeProject({ name: "" }));   // the blank launch project
    this.autosave = createSnapshotAutosave(
      (name, json) =>
        this.put(name, JSON.parse(json) as ProjectV2).catch((e) => {
          deps.log(`[forge] autosave of ${name} failed: ${errText(e)}`, "error");
          throw e;                               // createSnapshotAutosave keeps it pending (critic pass 3 #5)
        }),
      deps.delayMs,
    );
  }

  /** The project as it would be saved under `name` right now. */
  private current(name: string): ProjectV2 {
    if (this.pin && settings.stage !== this.pin.underStage) this.pin = null;   // the user changed STAGE
    return serializeProject({ name, backbone: this.pin?.backbone });
  }

  /** Every session PUT goes through here (critic pass 3 #5): PUTs to one name are chained, so they
   *  reach the server in the order they were made, and loadSession(name) waits for them. The first
   *  PUT to an idle name is sent synchronously -- no extra tick. */
  private put(name: string, project: ProjectV2): Promise<unknown> {
    const before = this.puts.get(name);
    const req = before
      ? before.then(() => this.deps.api.saveSession(name, project))
      : this.deps.api.saveSession(name, project);
    const settled = req.then(() => undefined, () => undefined);
    this.puts.set(name, settled);
    void settled.then(() => {
      if (this.puts.get(name) === settled) this.puts.delete(name);
    });
    return req;
  }

  /** App's $effect body. serializeProject reads every saved field through $state.snapshot, so the
   *  effect re-runs on ANY in-place edit (Global Constraint #1); observe() compares strings, so a
   *  re-run that changed nothing saves nothing. */
  observe(): void {
    this.autosave.observe(this.session, JSON.stringify(this.current(this.session)));
  }

  /** M4's stage lock (reconcile pass 2026-09-25, Open questions 32): a load never starts while M4's
   *  own POST/BASE rebuild is in flight, and holds settings.stageLocked for as long as `loading` --
   *  and past it while a rebuild this controller started is still running (critic follow-up #3) --
   *  so MODEL STAGE offers no switch mid-load. True when the load may start. */
  private begin(name: string): boolean {
    if (settings.stageRebuilding) {
      this.deps.log(`[forge] MODEL STAGE is rebuilding -- load ${name} again once it finishes`, "error");
      return false;
    }
    this.loading = true;
    this.loadingName = name;
    settings.stageLocked = true;
    return true;
  }

  async loadSession(name: string): Promise<void> {
    if (!name) return;                       // the `unsaved` option is never a load
    if (!this.begin(name)) return;           //     refused before (1): nothing is superseded
    const mySeq = ++this.seq;                // (1) any earlier load/import is stale from here
    try {
      const inflight = this.puts.get(name);
      if (inflight) await inflight;          // (2) a PUT to this name still in flight lands first
      if (mySeq !== this.seq) return;
      let raw: unknown;
      try {
        raw = await this.deps.api.session(name);   //     stores untouched, previous session still armed
      } catch (e) {
        if (mySeq === this.seq) this.deps.log(`[forge] failed to load session ${name}: ${errText(e)}`, "error");
        return;
      }
      if (mySeq !== this.seq) return;
      await this.commit(mySeq, raw, name, `session ${name}`);
    } finally {
      this.settle(mySeq);
    }
  }

  async importProjectFile(file: { name: string; text(): Promise<string> }): Promise<void> {
    if (!this.begin(file.name)) return;
    const mySeq = ++this.seq;                // (1)
    try {
      let raw: unknown;
      try {
        raw = JSON.parse(await file.text());
      } catch (e) {
        if (mySeq === this.seq) this.deps.log(`[forge] could not import ${file.name}: ${errText(e)}`, "error");
        return;
      }
      if (mySeq !== this.seq) return;
      if (await this.commit(mySeq, raw, "", file.name)) {
        this.deps.log(`[forge] imported ${file.name} -- unsaved until you SAVE it under a session name`);
      }
    } finally {
      this.settle(mySeq);
    }
  }

  /** Steps 3-9. `target` is the session to name and arm ("" for an IMPORT). True when committed. */
  private async commit(mySeq: number, raw: unknown, target: string, what: string): Promise<boolean> {
    let loaded: Loaded;
    try {
      loaded = toLoaded(raw);                // (3) validate -- nothing touched yet
    } catch (e) {
      this.deps.log(`[forge] ${what} was not loaded: ${errText(e)}`, "error");
      return false;                          //     session, autosave and stores all unchanged
    }
    //     ... then ask before replacing work no session owns: autosave never wrote it (critic pass 3 #3)
    if ((!this.session || this.orphaned) && unsavedWorkKey(this.current("")) !== this.unsavedKey
      && !this.deps.confirm(`Replace the unsaved timeline with ${what}? Its edits were never saved.`)) {
      this.deps.log(`[forge] kept the unsaved timeline; ${what} was not loaded`);
      return false;                          //     a refusal touches nothing either
    }
    this.autosave.arm("", "");               // (4) disarm; flushes the outgoing session's pending
                                             //     save under ITS name, with ITS (untouched) content
    if (!target) this.session = "";          //     an IMPORT belongs to no session from here on
    this.orphaned = true;                    //     the stores are about to hold content nobody is armed on
    this.pin = null;
    if (this.serverStage === null) this.serverStage = settings.stage;   //     what the server holds, before (5) moves it
    try {
      applyProject(loaded.project, { restoreModel: loaded.kind === "v2" });   // (5) clears selection + overlap params first
    } catch (e) {
      this.orphaned = false;
      this.session = "";                     //     half-applied: the stores match no session, never name one
      this.unsavedKey = unsavedWorkKey(this.current(""));   //     and half-applied content is not work to protect
      this.deps.log(`[forge] ${what} failed part-way and is now unsaved: ${errText(e)}`, "error");
      void this.reconcileStage(mySeq);       //     STAGE follows the server, not the half-applied file
      return false;
    }
    const stretch = this.deps.scheduleStretch ?? ((id: string) => m5ScheduleStretch(id));
    for (const c of arrangement.clips) stretch(c.id);   // (6) previewAudio is re-derived on load
    const savedBackbone = loaded.kind === "v2" ? loaded.project.backbone : undefined;
    const loadedSnap = serializeProject({ name: target, backbone: savedBackbone });   // (7)
    const baseline = JSON.stringify(loadedSnap);
    this.unsavedKey = unsavedWorkKey(loadedSnap);   //     step 3's "was it edited?" reference from now on
    if (loaded.kind === "v2") await this.syncBackbone(mySeq);   // (8) rebuild to the saved stage
    else await this.reconcileStage(mySeq);   //     v1 keeps the model the server holds
    if (mySeq !== this.seq) return false;    // (9) superseded during the wait: the newer one owns the stores
    this.serverStage = null;                 //     client and server agree again
    this.pin = savedBackbone !== undefined && savedBackbone !== settings.backboneId
      ? { backbone: savedBackbone, underStage: settings.stage }
      : null;
    this.orphaned = false;
    this.session = target;
    this.autosave.arm(target, baseline);
    this.observe();                          //     an edit made during steps 5-8 differs from the baseline
    return true;
  }

  /** Step 8, v2. Stage is session-level and rebuilds the model (M4 T9 confirmStage). applyProject
   *  moved the client stage; move the server to match, or put the client back on the SERVER's stage
   *  if the rebuild fails (M4: never claim a model the server did not load). It first waits for any
   *  earlier load's rebuild, and compares against the server's stage, not the client's -- which a
   *  superseded load may have moved (critic pass 3 #6). The pin, set by commit(), keeps a revert out
   *  of the saved session. */
  private async syncBackbone(mySeq: number): Promise<void> {
    await this.rebuildTail;                  // an older load's rebuild settles first: serverStage is now true
    if (mySeq !== this.seq) return;          // superseded while waiting: the newer load decides
    const server = this.serverStage ?? settings.stage;
    const wanted = settings.stage;
    if (wanted === server) return;
    this.rebuildInFlight = true;             // the stage lock waits for this, even past `loading` (#3)
    const rebuild = this.deps.api.setBackbone(STAGE_BACKBONE[wanted]).then(
      () => {
        this.serverStage = wanted;
      },
      (e) => {
        if (mySeq !== this.seq) return;      // superseded: the newer load, or settle(), reconciles
        settings.stage = server;
        this.deps.log(
          `[forge] project wants backbone ${STAGE_BACKBONE[wanted]}; rebuild failed, staying on ` +
          `${STAGE_BACKBONE[server]}. The session keeps ${STAGE_BACKBONE[wanted]} and its own sampling ` +
          `defaults; change STAGE to retry: ${errText(e)}`,
          "error",
        );
      },
    ).finally(() => {
      this.rebuildInFlight = false;          // superseded or not: this rebuild is over
      this.releaseStageLock();
    });
    this.rebuildTail = rebuild;
    await rebuild;
  }

  /** settings.stageLocked goes only when no load is in flight AND no rebuild this controller started
   *  is still running (critic follow-up #3). Before, settle() dropped it with `loading`, so a
   *  superseded load's setBackbone could still be pending while M4 offered STAGE again. */
  private releaseStageLock(): void {
    if (!this.loading && !this.rebuildInFlight) settings.stageLocked = false;
  }

  /** Once every rebuild this controller started has settled, put the client stage on what the
   *  server holds (critic pass 3 #6). For stores no rebuild of their own will fix: an orphaned or
   *  half-applied project, and a converted v1 file, which keeps the loaded model. */
  private async reconcileStage(mySeq: number): Promise<void> {
    await this.rebuildTail;
    if (mySeq !== this.seq) return;          // a newer load decides
    const server = this.serverStage;
    this.serverStage = null;
    if (server === null || settings.stage === server) return;
    settings.stage = server;
    this.deps.log(
      `[forge] an interrupted load's rebuild did not land; STAGE follows the server (${STAGE_BACKBONE[server]})`,
      "error",
    );
  }

  /** End of the LATEST load/import only. If it did not commit after a superseded load had already
   *  written the stores, those stores match no session: show `unsaved`, keep autosave off, and let
   *  STAGE follow the server once that load's rebuild settles. */
  private settle(mySeq: number): void {
    if (mySeq !== this.seq) return;
    this.loading = false;
    this.loadingName = "";
    this.releaseStageLock();                 //     M4's MODEL STAGE is offered again -- unless a
                                             //     superseded load's rebuild is still running (#3)
    if (!this.orphaned) return;
    this.orphaned = false;
    this.session = "";
    this.autosave.arm("", "");
    this.deps.log("[forge] an interrupted load left its project in the timeline -- unsaved until you SAVE it", "error");
    void this.reconcileStage(mySeq);
  }

  /** SAVE. Returns the name saved under, or null. */
  async saveSession(): Promise<string | null> {
    if (this.loading) {
      // Step 1's rule: mid-load the stores are either the previous session's or not yet armed as
      // the target's, so a SAVE could write the wrong content under either name. Refuse, say why.
      this.deps.log("[forge] a session is still loading -- SAVE again once it has", "error");
      return null;
    }
    let name = this.session;
    let typed = false;
    if (!name) {
      const answer = this.deps.prompt("Session name (letters, numbers, . _ - only):");
      if (!answer) return null;
      name = answer;
      typed = true;
    }
    if (!isValidSessionName(name)) {
      this.deps.log(`[forge] "${name}" is not a valid session name (spec §6.3)`, "error");
      return null;
    }
    // A typed name that is already listed would be replaced by the PUT: ask (critic pass 3 #4).
    if (typed && this.deps.exists("session", name)
      && !this.deps.confirm(`Session ${name} already exists -- overwrite it?`)) {
      return null;
    }
    const mySeq = this.seq;
    const project = this.current(name);
    try {
      await this.put(name, project);
    } catch (e) {
      this.deps.log(`[forge] session save failed: ${errText(e)}`, "error");
      return null;
    }
    // A load or import that started during the PUT owns the stores and the name now.
    if (mySeq !== this.seq) return name;
    this.session = name;
    this.autosave.arm(name, JSON.stringify(project));
    this.observe();                          // an edit made during the PUT is saved, not lost
    return name;
  }

  /** MASTER PRESET recall (spec §9.3). Refused while a load is in flight, dropped if one started
   *  during the fetch -- it would land in the NEW session's stores, which count as edits after step
   *  9 and autosave (critic pass 3 #2) -- and validated whole before the first write (critic pass 3
   *  #12). True when applied: App highlights the name only then. */
  async recallMasterPreset(name: string): Promise<boolean> {
    if (!name) return false;
    if (this.loading) {
      this.deps.log(`[forge] a session is still loading -- pick ${name} again once it has`, "error");
      return false;
    }
    const mySeq = this.seq;
    let payload: MasterPresetPayload;
    try {
      payload = validateMasterPreset(await this.deps.api.preset("master", name));
    } catch (e) {
      this.deps.log(`[forge] failed to load master preset ${name}: ${errText(e)}`, "error");
      return false;
    }
    if (mySeq !== this.seq || this.loading) {
      this.deps.log(`[forge] a session load started while master preset ${name} was loading -- pick it again`, "error");
      return false;
    }
    applyMasterPreset(payload);
    // A preset can move native_bpm / detune_cents; previewAudio must follow, exactly as on a session
    // load (step 6 above), or the timeline plays the old stretch while MIXDOWN renders the new one
    // (review 2026-10-01).
    const stretch = this.deps.scheduleStretch ?? ((id: string) => m5ScheduleStretch(id));
    for (const c of arrangement.clips) stretch(c.id);
    return true;
  }

  /** MASTER PRESET SAVE, under `current` (the highlighted name) or a typed one; a typed name that
   *  is already listed asks before it is overwritten (critic pass 3 #4). The name saved, or null. */
  async saveMasterPreset(current: string): Promise<string | null> {
    let name = current;
    if (!name) {
      const answer = this.deps.prompt("Master preset name:");
      if (!answer) return null;
      if (this.deps.exists("master", answer)
        && !this.deps.confirm(`Master preset ${answer} already exists -- overwrite it?`)) {
        return null;
      }
      name = answer;
    }
    try {
      await this.deps.api.savePreset("master", name, buildMasterPresetPayload());
    } catch (e) {
      this.deps.log(`[forge] master preset save failed: ${errText(e)}`, "error");
      return null;
    }
    return name;
  }
}
