// The client against RESPONSES RECORDED FROM THE REAL SERVER (WINTERMUTE 2026-09-25), never the
// hand-written mock: a mock that agrees with its client is how fetchAdapters read `ckpts` for two
// milestones. Recordings: M2 T15's record_fixtures.py -> docs/latent-forge/contract/fixtures/<name>.json.
// Only a RECORDED file counts; preferRecorded()'s hand-made fallback is the thing under test, so a
// hand-made hit skips -- with the reason in the title -- and never passes.
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchLatchHeads } from "../../chains/latch";
import { forgeApi } from "../api";
import { CHAIN_DEFAULTS } from "../defaults";
import { isAudioRef, isLatentRef } from "../guards";
import { fetchAdapters, fetchFilmCkpts, fetchSlots } from "../models";

interface Fixture { status: number; body: unknown }

// M1 T6's FIXTURE_DIR and preferRecorded, RESTATED rather than imported from mock/plugin.ts: M1
// keeps mock/ out of tsconfig's include, and importing it from src/ would pull it into svelte-check
// (critic follow-up #12). Same directory (repo docs/latent-forge/contract/fixtures), same rule.
const FIXTURE_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "../../../../../docs/latent-forge/contract/fixtures");
function preferRecorded(available: string[], name: string): string | null {
  if (available.includes(`${name}.json`)) return `${name}.json`;
  if (available.includes(`handmade-${name}.json`)) return `handmade-${name}.json`;
  return null;
}

function recorded(name: string): Fixture | null {
  const available = existsSync(FIXTURE_DIR) ? readdirSync(FIXTURE_DIR) : [];
  if (preferRecorded(available, name) !== `${name}.json`) return null;
  return JSON.parse(readFileSync(resolve(FIXTURE_DIR, `${name}.json`), "utf8")) as Fixture;
}

/** Where each recording keeps the rows its checks run over (critic follow-up #6): a list key, or
 *  RAW for a raw-object GET, whose own keys are its rows. An empty one makes every length and
 *  field assertion pass vacuously, so it skips instead. */
const RAW = "";
const ROWS: Record<string, string> = {
  models_adapters: "models", models_control_adapters: "models", slots: "slots",
  forge_files_crops: "files", forge_files_renders: "files",
  forge_sessions_list: "sessions", forge_presets_latch_list: "names",
  forge_session_get: RAW, forge_preset_latch_get: RAW,
};

function rowCount(name: string): number {
  const body = recorded(name)?.body;
  if (body === null || typeof body !== "object") return 0;
  if (ROWS[name] === RAW) return Object.keys(body).length;
  const rows = (body as Record<string, unknown>)[ROWS[name]];
  return Array.isArray(rows) ? rows.length : 0;
}

/** Recorded, and not empty where rows are what is under test. */
function ready(...names: string[]): boolean {
  return names.every((n) => recorded(n) !== null && (!(n in ROWS) || rowCount(n) > 0));
}

/** The test title, plus why it is skipped: a recording is missing, or holds no rows to check. */
function title(desc: string, ...names: string[]): string {
  const missing = names.filter((n) => recorded(n) === null);
  if (missing.length > 0) {
    return `${desc} [SKIPPED: ${missing.map((n) => `${n}.json`).join(", ")} not recorded yet -- run M2 T15's ` +
      `record_fixtures.py against the live server; a hand-made mock is not a contract]`;
  }
  const empty = names.filter((n) => n in ROWS && rowCount(n) === 0);
  return empty.length === 0
    ? desc
    : `${desc} [SKIPPED: ${empty.map((n) => `${n}.json has no ${ROWS[n] === RAW ? "fields" : `${ROWS[n]} rows`}`).join(", ")} ` +
      `-- re-record against a server that has some; an empty recording proves nothing]`;
}

/** Answer every fetch with the recorded response, status and all. */
function serve(f: Fixture): void {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(f.body), {
    status: f.status, headers: { "content-type": "application/json" },
  })));
}

const INFO = recorded("info");
const MODELS = recorded("models_adapters");
const SLOTS = recorded("slots");
const CROPS = recorded("forge_files_crops");
const RENDERS = recorded("forge_files_renders");
const CTRL = recorded("models_control_adapters");
const SESSIONS = recorded("forge_sessions_list");
const SESSION = recorded("forge_session_get");
const PRESETS = recorded("forge_presets_latch_list");
const PRESET = recorded("forge_preset_latch_get");
const PROBE = "_fixture_probe";   // M2 T15's throwaway session/preset name

/** How many recorded control adapters FiLM may use: control_mode "scalar" only (WINTERMUTE
 *  2026-09-25). Zero means the recording cannot show the filter works, so the FiLM test skips. */
const SCALAR_ROWS = ((CTRL?.body as { models?: { control_mode?: unknown }[] } | undefined)?.models ?? [])
  .filter((m) => m.control_mode === "scalar").length;

afterEach(() => vi.unstubAllGlobals());

describe("the client against recorded real-server responses (M2 T15 fixtures)", () => {
  it.skipIf(!INFO)(title("GET /info: every latch head has the fields LatchHeadInfo reads, and film_default.gain is CHAIN_DEFAULTS.film.gain", "info"), async () => {
    serve(INFO!);
    const heads = Object.values(await fetchLatchHeads());
    expect(heads.length).toBeGreaterThan(0);
    for (const h of heads) {
      expect(typeof h.name).toBe("string");
      expect(typeof h.family).toBe("string");
      expect(typeof h.default_gain).toBe("number");
      expect(typeof h.health).toBe("string");
      expect(Array.isArray(h.supports_kinds)).toBe(true);
      expect(typeof h.slider_min).toBe("number");
      expect(typeof h.slider_max).toBe("number");
      expect(typeof h.value_default).toBe("number");
    }
    const info = (await forgeApi.info()) as { film_default?: { gain?: unknown } };
    expect(info.film_default?.gain).toBe(CHAIN_DEFAULTS.film.gain);   // 1.75 on both sides
  });

  it.skipIf(!ready("models_adapters"))(title("GET /models: the rows are under `models`, and fetchAdapters returns every one with the path and label the MODEL select reads", "models_adapters"), async () => {
    const body = MODELS!.body as { models?: { path?: unknown }[] };
    expect(Array.isArray(body.models)).toBe(true);   // not `ckpts` -- M1's old mock
    serve(MODELS!);
    const adapters = await fetchAdapters();
    expect(adapters.length).toBeGreaterThan(0);      // ready() skipped an empty recording
    expect(adapters).toHaveLength(body.models!.length);
    for (const a of adapters) {
      expect(typeof a.path).toBe("string");
      expect(typeof a.label).toBe("string");         // model_db writes `label` (= arm); `name` is optional
    }
  });

  // FiLM (critic follow-up #1): its OWN recording, /models?family=control_adapter -- the adapter
  // recording would pass whatever query the client sent. Only control_mode "scalar" rows may come
  // back (WINTERMUTE 2026-09-25: _install_film loads a ScalarAttributeEncoder).
  const ctrlRecorded = ready("models_control_adapters");
  it.skipIf(!ctrlRecorded || SCALAR_ROWS === 0)(
    ctrlRecorded && SCALAR_ROWS === 0
      ? "GET /models?family=control_adapter: fetchFilmCkpts [SKIPPED: models_control_adapters.json has no " +
        "control_mode \"scalar\" row -- nothing FiLM can load was recorded; an empty result proves nothing]"
      : title("GET /models?family=control_adapter: fetchFilmCkpts returns exactly the control_mode \"scalar\" rows, with the path and label FILM CKPT reads", "models_control_adapters"),
    async () => {
      const body = CTRL!.body as { models: { path?: unknown; control_mode?: unknown }[] };
      serve(CTRL!);
      const film = await fetchFilmCkpts();
      expect(film.length).toBeGreaterThan(0);         // the skip condition guarantees a scalar row
      expect(film.map((f) => f.path)).toEqual(
        body.models.filter((m) => m.control_mode === "scalar").map((m) => m.path),
      );
      for (const f of film) {
        expect(typeof f.path).toBe("string");
        expect(typeof f.label).toBe("string");
      }
    },
  );

  it.skipIf(!ready("slots"))(title("GET /slots: fetchSlots keeps every resident slot, with the fields LORA/DORA reads", "slots"), async () => {
    const body = SLOTS!.body as Record<string, unknown>;
    for (const k of ["active", "backbone", "slots", "max_slots", "vram_floor_gb", "free_gb"]) {
      expect(Object.prototype.hasOwnProperty.call(body, k), `/slots has no ${k}`).toBe(true);
    }
    serve(SLOTS!);
    const out = await fetchSlots();
    expect(out.ok).toBe(true);
    expect(out.slots.length).toBeGreaterThan(0);     // ready() skipped an empty recording
    expect(out.slots).toHaveLength((body.slots as unknown[]).length);
    for (const s of out.slots) {
      expect(typeof s.index).toBe("number");
      expect(typeof s.path).toBe("string");
      expect(typeof s.label).toBe("string");
      expect(typeof s.family).toBe("string");
      expect(typeof s.cost_gb).toBe("number");
      expect(typeof s.strength).toBe("number");
    }
  });

  it.skipIf(!ready("forge_files_crops", "forge_files_renders"))(title("GET /forge/files (crops, renders): roots are {id,label,available}, rows are {root,rel,kind,size,mtime,ref} with a real ref", "forge_files_crops", "forge_files_renders"), async () => {
    for (const f of [CROPS!, RENDERS!]) {
      serve(f);
      const res = await forgeApi.files({ root: "crops", limit: 5 });   // the query is not what is under test
      expect(res.roots.length).toBeGreaterThan(0);
      expect(res.files.length).toBeGreaterThan(0);   // ready() skipped an empty recording
      for (const r of res.roots) {
        expect(typeof r.id).toBe("string");
        expect(typeof r.label).toBe("string");
        expect(typeof r.available).toBe("boolean");
      }
      for (const row of res.files) {
        expect(typeof row.root).toBe("string");
        expect(typeof row.rel).toBe("string");
        expect(["audio", "latent"]).toContain(row.kind);
        expect(typeof row.size).toBe("number");
        expect(typeof row.mtime).toBe("number");
        expect(isAudioRef(row.ref) || isLatentRef(row.ref)).toBe(true);
      }
    }
  });

  // Sessions and presets (Open questions 35, resolved by M2 T15 in ebaf823): the LIST routes wrap,
  // the GET-one routes return the stored object RAW -- and M1's request() must neither require nor
  // strip an `ok` it will not find.
  it.skipIf(!ready("forge_sessions_list"))(title("GET /forge/sessions: wrapped {ok, sessions}; each row is {name, updated in epoch SECONDS, n_clips}, the probe listed", "forge_sessions_list"), async () => {
    expect((SESSIONS!.body as Record<string, unknown>).ok).toBe(true);
    serve(SESSIONS!);
    const res = await forgeApi.sessions();
    expect(res.sessions.length).toBeGreaterThan(0);   // ready() skipped an empty recording
    for (const s of res.sessions) {
      expect(typeof s.name).toBe("string");
      expect(typeof s.updated).toBe("number");
      expect(s.updated).toBeLessThan(1e11);           // seconds, not ms (M1 T5's note, W 2026-09-25)
      expect(typeof s.n_clips).toBe("number");
    }
    expect(res.sessions.map((s) => s.name)).toContain(PROBE);
  });

  it.skipIf(!ready("forge_session_get"))(title("GET /forge/sessions/{name}: the stored project RAW, no {ok} wrapper, and forgeApi.session returns it as is", "forge_session_get"), async () => {
    const body = SESSION!.body as Record<string, unknown>;
    expect(Object.prototype.hasOwnProperty.call(body, "ok")).toBe(false);   // raw, not enveloped
    expect(body.version).toBe(2);                     // what SessionController's validate step reads first
    serve(SESSION!);
    expect(await forgeApi.session(PROBE)).toEqual(body);
  });

  it.skipIf(!ready("forge_presets_latch_list"))(title("GET /forge/presets/{level}: wrapped {ok, names}; every name a string, the probe listed", "forge_presets_latch_list"), async () => {
    serve(PRESETS!);
    const res = await forgeApi.presets("latch");
    expect(res.ok).toBe(true);
    expect(res.names.length).toBeGreaterThan(0);      // ready() skipped an empty recording
    for (const n of res.names) expect(typeof n).toBe("string");
    expect(res.names).toContain(PROBE);
  });

  it.skipIf(!ready("forge_preset_latch_get"))(title("GET /forge/presets/{level}/{name}: the stored payload RAW, no {ok} wrapper, and forgeApi.preset returns it as is", "forge_preset_latch_get"), async () => {
    const body = PRESET!.body as Record<string, unknown>;
    expect(Object.prototype.hasOwnProperty.call(body, "ok")).toBe(false);   // raw, not enveloped
    expect(body.latch_on).toBe(false);                // exactly what M2 T15 PUT
    serve(PRESET!);
    expect(await forgeApi.preset("latch", PROBE)).toEqual(body);
  });
});
