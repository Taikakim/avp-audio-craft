// dev:mock -- serves the whole spec §6 contract from
// docs/latent-forge/contract/fixtures/, so the app runs with no GPU, no Python and
// no render server. A RECORDED `<name>.json` always beats `handmade-<name>.json`
// (spec §11.4); the directory is re-read per request, so a fixture M2 records lands
// without restarting vite.
//
// Fixture file shape: {"status": <int>, "body": <anything>}.

import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { Plugin } from "vite";
import type { JobOp } from "../src/lib/forge/types";
import { MockJobQueue } from "./jobs";

/** latent-forge/mock -> repo root -> docs/latent-forge/contract/fixtures */
export const FIXTURE_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "../../docs/latent-forge/contract/fixtures");

const SCHEDULE_SHAPES = ["model", "logsnr", "geometric", "linear", "log", "exponential", "cosine"];

export function preferRecorded(available: string[], name: string): string | null {
  if (available.includes(`${name}.json`)) return `${name}.json`;
  if (available.includes(`handmade-${name}.json`)) return `handmade-${name}.json`;
  return null;
}

export function scheduleFixtureName(shape: unknown): string {
  return typeof shape === "string" && SCHEDULE_SHAPES.includes(shape) ? `schedule_${shape}` : "schedule_model";
}

export function statusFixtureName(busy: boolean): string {
  return busy ? "status_busy" : "status_idle";
}

export type MockRoute =
  | { kind: "fixture"; name: string }
  | { kind: "status" }
  | { kind: "schedule" }
  | { kind: "audio" }
  | { kind: "upload" }
  | { kind: "backbone_set" }
  | { kind: "session_get"; name: string }
  | { kind: "session_put"; name: string }
  | { kind: "preset_list"; level: string }
  | { kind: "preset_get"; level: string; name: string }
  | { kind: "preset_put"; level: string; name: string }
  | { kind: "preset_delete"; level: string; name: string }
  | { kind: "jobs_submit" }
  | { kind: "jobs_list"; limit: number }
  | { kind: "job_get"; jobId: string }
  | { kind: "job_cancel"; jobId: string };

export function routeFor(method: string, pathname: string, query: URLSearchParams): MockRoute | null {
  if (method === "GET" && pathname === "/info") return { kind: "fixture", name: "info" };
  if (method === "GET" && pathname === "/status") return { kind: "status" };
  if (method === "POST" && pathname === "/schedule") return { kind: "schedule" };

  const seg = pathname.split("/").filter(Boolean).map((s) => decodeURIComponent(s));
  if (seg[0] !== "forge") return null;

  switch (seg[1]) {
    case "log":
      return method === "GET" ? { kind: "fixture", name: "forge_log" } : null;
    case "backbone":
      if (method === "GET") return { kind: "fixture", name: "forge_backbone" };
      if (method === "POST") return { kind: "backbone_set" };
      return null;
    case "files":
      return method === "GET"
        ? { kind: "fixture", name: query.get("root") === "renders" ? "forge_files_renders" : "forge_files_crops" }
        : null;
    case "audio":
      return method === "GET" ? { kind: "audio" } : null;
    case "upload":
      return method === "PUT" ? { kind: "upload" } : null;
    case "analyze":
      return method === "POST" ? { kind: "fixture", name: "forge_analyze_crop" } : null;
    case "stretch":
      return method === "POST" ? { kind: "fixture", name: "forge_stretch_render" } : null;
    case "chroma":
      return method === "POST" ? { kind: "fixture", name: "forge_chroma_render" } : null;
    case "stats":
      return method === "POST" ? { kind: "fixture", name: "forge_stats_crops" } : null;
    case "dataset_scalars":
      return method === "GET" ? { kind: "fixture", name: "forge_dataset_scalars" } : null;
    case "sessions":
      if (seg.length === 2) return method === "GET" ? { kind: "fixture", name: "forge_sessions" } : null;
      if (seg.length === 3 && method === "GET") return { kind: "session_get", name: seg[2] };
      if (seg.length === 3 && method === "PUT") return { kind: "session_put", name: seg[2] };
      return null;
    case "presets":
      if (seg.length === 3 && method === "GET") return { kind: "preset_list", level: seg[2] };
      if (seg.length === 4 && method === "GET") return { kind: "preset_get", level: seg[2], name: seg[3] };
      if (seg.length === 4 && method === "PUT") return { kind: "preset_put", level: seg[2], name: seg[3] };
      if (seg.length === 4 && method === "DELETE") return { kind: "preset_delete", level: seg[2], name: seg[3] };
      return null;
    case "jobs":
      if (seg.length === 2) {
        if (method === "POST") return { kind: "jobs_submit" };
        if (method === "GET") return { kind: "jobs_list", limit: Number(query.get("limit") ?? 50) };
        return null;
      }
      if (seg.length === 3 && method === "GET") return { kind: "job_get", jobId: seg[2] };
      if (seg.length === 3 && method === "DELETE") return { kind: "job_cancel", jobId: seg[2] };
      return null;
    default:
      return null;
  }
}

// ------------------------------------------------------------------ synthetic audio

/**
 * A real 16-bit stereo PCM WAV, so /forge/audio answers something the browser can
 * decode and the waveform canvases have a shape to draw. 12 ms attack and release
 * so the drawn envelope is not a rectangle.
 */
export function wavBytes(durationSec: number, hzL: number, hzR: number, sampleRate = 44100): Uint8Array {
  const frames = Math.max(1, Math.round(durationSec * sampleRate));
  const dataBytes = frames * 4;
  const buf = new ArrayBuffer(44 + dataBytes);
  const view = new DataView(buf);
  const ascii = (off: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i));
  };
  ascii(0, "RIFF");
  view.setUint32(4, 36 + dataBytes, true);
  ascii(8, "WAVE");
  ascii(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);            // PCM
  view.setUint16(22, 2, true);            // stereo
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 4, true);
  view.setUint16(32, 4, true);
  view.setUint16(34, 16, true);
  ascii(36, "data");
  view.setUint32(40, dataBytes, true);

  const ramp = 0.012 * sampleRate;
  for (let i = 0; i < frames; i++) {
    const env = Math.min(1, i / ramp, (frames - 1 - i) / ramp);
    const l = Math.sin((2 * Math.PI * hzL * i) / sampleRate) * 0.25 * env;
    const r = Math.sin((2 * Math.PI * hzR * i) / sampleRate) * 0.25 * env;
    view.setInt16(44 + i * 4, Math.round(l * 32767), true);
    view.setInt16(46 + i * 4, Math.round(r * 32767), true);
  }
  return new Uint8Array(buf);
}

/** Deterministic tone per AudioRef, so two different refs look different on screen. */
export function toneFor(refJson: string): { durationSec: number; hzL: number; hzR: number } {
  let h = 2166136261;
  for (let i = 0; i < refJson.length; i++) {
    h ^= refJson.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  const n = Math.abs(h);
  const scale = [110, 123.47, 146.83, 164.81, 196, 220, 246.94, 293.66];
  return {
    durationSec: 3 + (n % 10),
    hzL: scale[n % scale.length],
    hzR: scale[Math.floor(n / 8) % scale.length],
  };
}

// ------------------------------------------------------------------ http helpers

function sendJson(res: ServerResponse, status: number, body: unknown): void {
  const text = JSON.stringify(body);
  res.statusCode = status;
  res.setHeader("content-type", "application/json");
  res.setHeader("content-length", Buffer.byteLength(text));
  res.end(text);
}

function readBody(req: IncomingMessage): Promise<Buffer> {
  return new Promise((ok, fail) => {
    const chunks: Buffer[] = [];
    req.on("data", (c: Buffer) => chunks.push(c));
    req.on("end", () => ok(Buffer.concat(chunks)));
    req.on("error", fail);
  });
}

async function readJson(req: IncomingMessage): Promise<Record<string, unknown>> {
  const raw = (await readBody(req)).toString("utf8");
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

function sendFixture(res: ServerResponse, name: string): void {
  const available = existsSync(FIXTURE_DIR) ? readdirSync(FIXTURE_DIR) : [];
  const file = preferRecorded(available, name);
  if (!file) {
    sendJson(res, 501, {
      ok: false,
      error: `no fixture "${name}" yet -- add docs/latent-forge/contract/fixtures/handmade-${name}.json, or wait for M2 to record ${name}.json`,
    });
    return;
  }
  const parsed = JSON.parse(readFileSync(resolve(FIXTURE_DIR, file), "utf8")) as { status: number; body: unknown };
  sendJson(res, parsed.status, parsed.body);
}

// ------------------------------------------------------------------ the plugin

export function mockForgePlugin(): Plugin {
  const queue = new MockJobQueue();
  const sessions = new Map<string, unknown>();
  const presets = new Map<string, unknown>();
  let backbone = { id: "medium-base", objective: "rectified_flow" };

  async function handle(route: MockRoute, req: IncomingMessage, res: ServerResponse, url: URL): Promise<void> {
    switch (route.kind) {
      case "fixture":
        return sendFixture(res, route.name);

      case "status":
        return sendFixture(res, statusFixtureName(queue.busy));

      case "schedule": {
        const body = await readJson(req);
        const schedule = body.schedule as { shape?: unknown } | undefined;
        return sendFixture(res, scheduleFixtureName(schedule?.shape));
      }

      case "audio": {
        const ref = url.searchParams.get("ref") ?? "{}";
        const { durationSec, hzL, hzR } = toneFor(ref);
        const bytes = wavBytes(durationSec, hzL, hzR);
        res.statusCode = 200;
        res.setHeader("content-type", "audio/wav");
        res.setHeader("content-length", bytes.length);
        res.end(Buffer.from(bytes));
        return;
      }

      case "upload": {
        const raw = await readBody(req);
        const sha256 = createHash("sha256").update(raw).digest("hex");
        const name = url.searchParams.get("filename") ?? "upload.wav";
        const ext = name.includes(".") ? name.split(".").pop() : "wav";
        return sendJson(res, 200, {
          ok: true,
          ref: { kind: "upload", sha256 },
          path: `/SERVER/out/_forge/uploads/${sha256}.${ext}`,
          bytes: raw.length,
          duration_sec: Math.max(0.1, (raw.length - 44) / (44100 * 4)),
          sample_rate: 44100,
          channels: 2,
        });
      }

      case "backbone_set": {
        const body = await readJson(req);
        const id = typeof body.id === "string" ? body.id : backbone.id;
        backbone = { id, objective: id.endsWith("-base") ? "rectified_flow" : "rf_denoiser" };
        return sendJson(res, 200, { ok: true, active: backbone.id, objective: backbone.objective, rebuild_sec: 9.4, warnings: [] });
      }

      case "session_get": {
        const project = sessions.get(route.name);
        return project
          ? sendJson(res, 200, project)
          : sendJson(res, 404, { ok: false, error: `no session named ${route.name}` });
      }
      case "session_put":
        sessions.set(route.name, await readJson(req));
        return sendJson(res, 200, { ok: true });

      case "preset_list":
        return sendJson(res, 200, {
          ok: true,
          names: [...presets.keys()].filter((k) => k.startsWith(`${route.level}/`)).map((k) => k.slice(route.level.length + 1)),
        });
      case "preset_get": {
        const p = presets.get(`${route.level}/${route.name}`);
        return p
          ? sendJson(res, 200, p)
          : sendJson(res, 404, { ok: false, error: `no ${route.level} preset named ${route.name}` });
      }
      case "preset_put":
        presets.set(`${route.level}/${route.name}`, await readJson(req));
        return sendJson(res, 200, { ok: true });
      case "preset_delete":
        presets.delete(`${route.level}/${route.name}`);
        return sendJson(res, 200, { ok: true });

      case "jobs_submit": {
        const body = await readJson(req);
        const out = queue.submit(body.op as JobOp, body.payload);
        return sendJson(res, out.status, out.body);
      }
      case "jobs_list": {
        const out = queue.list(route.limit);
        return sendJson(res, out.status, out.body);
      }
      case "job_get": {
        const out = queue.get(route.jobId);
        return sendJson(res, out.status, out.body);
      }
      case "job_cancel": {
        const out = queue.cancel(route.jobId);
        return sendJson(res, out.status, out.body);
      }
    }
  }

  return {
    name: "latent-forge:mock",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = new URL(req.url ?? "/", "http://mock.local");
        const route = routeFor((req.method ?? "GET").toUpperCase(), url.pathname, url.searchParams);
        if (!route) return next();
        handle(route, req, res, url).catch((err: unknown) => {
          sendJson(res, 500, { ok: false, error: String(err), traceback: "mock server" });
        });
      });
      server.config.logger.info("  \x1b[36m➜\x1b[0m  mock forge server: serving spec §6 from docs/latent-forge/contract/fixtures/");
    },
  };
}
