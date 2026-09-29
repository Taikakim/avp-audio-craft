import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  FIXTURE_DIR, preferRecorded, routeFor, scheduleFixtureName, statusFixtureName, toneFor, wavBytes,
} from "../plugin";

function route(method: string, url: string) {
  const u = new URL(url, "http://mock.local");
  return routeFor(method, u.pathname, u.searchParams);
}

describe("a recorded fixture always beats a hand-made one (spec §11.4)", () => {
  it("prefers the recorded file when both exist", () => {
    expect(preferRecorded(["handmade-info.json", "info.json"], "info")).toBe("info.json");
  });

  it("falls back to the hand-made file", () => {
    expect(preferRecorded(["handmade-info.json"], "info")).toBe("handmade-info.json");
  });

  it("returns null when neither exists", () => {
    expect(preferRecorded(["handmade-status_idle.json"], "info")).toBe(null);
  });
});

describe("route table covers spec §6", () => {
  it("maps each contract route", () => {
    expect(route("GET", "/info")).toEqual({ kind: "fixture", name: "info" });
    expect(route("GET", "/status")).toEqual({ kind: "status" });
    expect(route("POST", "/schedule")).toEqual({ kind: "schedule" });
    expect(route("GET", "/forge/log?since=3")).toEqual({ kind: "fixture", name: "forge_log" });
    expect(route("GET", "/forge/backbone")).toEqual({ kind: "fixture", name: "forge_backbone" });
    expect(route("POST", "/forge/backbone")).toEqual({ kind: "backbone_set" });
    expect(route("GET", "/forge/files?root=crops")).toEqual({ kind: "fixture", name: "forge_files_crops" });
    expect(route("GET", "/forge/files?root=renders")).toEqual({ kind: "fixture", name: "forge_files_renders" });
    expect(route("GET", "/forge/audio?ref=%7B%7D")).toEqual({ kind: "audio" });
    expect(route("PUT", "/forge/upload?filename=a.wav")).toEqual({ kind: "upload" });
    expect(route("POST", "/forge/analyze")).toEqual({ kind: "fixture", name: "forge_analyze_crop" });
    expect(route("POST", "/forge/stretch")).toEqual({ kind: "fixture", name: "forge_stretch_render" });
    expect(route("POST", "/forge/chroma")).toEqual({ kind: "fixture", name: "forge_chroma_render" });
    expect(route("POST", "/forge/stats")).toEqual({ kind: "fixture", name: "forge_stats_crops" });
    expect(route("GET", "/forge/dataset_scalars?x=bpm&y=lufs")).toEqual({ kind: "fixture", name: "forge_dataset_scalars" });
    expect(route("GET", "/forge/sessions")).toEqual({ kind: "fixture", name: "forge_sessions" });
    expect(route("GET", "/forge/sessions/my%20set")).toEqual({ kind: "session_get", name: "my set" });
    expect(route("PUT", "/forge/sessions/my%20set")).toEqual({ kind: "session_put", name: "my set" });
    expect(route("GET", "/forge/presets/render")).toEqual({ kind: "preset_list", level: "render" });
    expect(route("PUT", "/forge/presets/render/warm")).toEqual({ kind: "preset_put", level: "render", name: "warm" });
    expect(route("DELETE", "/forge/presets/render/warm")).toEqual({ kind: "preset_delete", level: "render", name: "warm" });
    expect(route("POST", "/forge/jobs")).toEqual({ kind: "jobs_submit" });
    expect(route("GET", "/forge/jobs?limit=12")).toEqual({ kind: "jobs_list", limit: 12 });
    expect(route("GET", "/forge/jobs/forge-1")).toEqual({ kind: "job_get", jobId: "forge-1" });
    expect(route("DELETE", "/forge/jobs/forge-1")).toEqual({ kind: "job_cancel", jobId: "forge-1" });
  });

  it("returns null for anything the contract does not define", () => {
    expect(route("GET", "/src/main.ts")).toBe(null);
    expect(route("GET", "/forgery/jobs")).toBe(null);
    expect(route("DELETE", "/forge/log")).toBe(null);
  });
});

describe("fixture name selection", () => {
  it("picks the schedule fixture by shape and falls back to model", () => {
    expect(scheduleFixtureName("logsnr")).toBe("schedule_logsnr");
    expect(scheduleFixtureName("model")).toBe("schedule_model");
    expect(scheduleFixtureName(undefined)).toBe("schedule_model");
    expect(scheduleFixtureName("not a shape")).toBe("schedule_model");
  });

  it("picks status_idle or status_busy from the queue state", () => {
    expect(statusFixtureName(false)).toBe("status_idle");
    expect(statusFixtureName(true)).toBe("status_busy");
  });
});

describe("synthetic audio", () => {
  it("writes a parseable 16-bit stereo PCM WAV", () => {
    const bytes = wavBytes(0.25, 220, 330, 44100);
    const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const tag = (off: number) => String.fromCharCode(...bytes.slice(off, off + 4));
    const frames = Math.round(0.25 * 44100);
    expect(tag(0)).toBe("RIFF");
    expect(tag(8)).toBe("WAVE");
    expect(tag(12)).toBe("fmt ");
    expect(tag(36)).toBe("data");
    expect(dv.getUint16(20, true)).toBe(1);       // PCM
    expect(dv.getUint16(22, true)).toBe(2);       // stereo
    expect(dv.getUint32(24, true)).toBe(44100);
    expect(dv.getUint16(34, true)).toBe(16);      // bits
    expect(dv.getUint32(40, true)).toBe(frames * 4);
    expect(bytes.length).toBe(44 + frames * 4);
    // not silent -- the waveform canvas must have something to draw
    let peak = 0;
    for (let i = 0; i < frames; i++) peak = Math.max(peak, Math.abs(dv.getInt16(44 + i * 4, true)));
    expect(peak).toBeGreaterThan(1000);
  });

  it("derives a stable tone from the ref so each ref draws its own waveform", () => {
    const a = toneFor('{"kind":"crop","crop_id":"000412"}');
    const b = toneFor('{"kind":"crop","crop_id":"000412"}');
    const c = toneFor('{"kind":"crop","crop_id":"000999"}');
    expect(a).toEqual(b);
    expect(a).not.toEqual(c);
    expect(a.durationSec).toBeGreaterThanOrEqual(3);
    expect(a.durationSec).toBeLessThanOrEqual(12);
    expect(a.hzL).toBeGreaterThan(0);
  });
});

describe("the hand-made fixtures themselves", () => {
  const names = readdirSync(FIXTURE_DIR).filter((n) => n.startsWith("handmade-") && n.endsWith(".json"));

  it("ships at least the ten fixtures M1's own shell calls", () => {
    // A superset check, not an exact-list one (WINTERMUTE, 2026-09-22): this
    // only needs to catch one of M1's own ten fixtures silently vanishing, and
    // arrayContaining does that exactly as well as toEqual on a sorted array
    // would -- while letting a later milestone add its own handmade fixtures
    // to this directory without also having to edit this list in the same
    // commit. The envelope test right below already validates any new
    // arrival's shape generically.
    expect(names).toEqual(
      expect.arrayContaining([
        "handmade-forge_backbone.json",
        "handmade-forge_files_crops.json",
        "handmade-forge_job_generate_done.json",
        "handmade-forge_job_running.json",
        "handmade-forge_job_submit.json",
        "handmade-forge_log.json",
        "handmade-forge_sessions.json",
        "handmade-info.json",
        "handmade-schedule_model.json",
        "handmade-status_idle.json",
      ]),
    );
  });

  it("each has the {status, body} envelope", () => {
    for (const n of names) {
      const parsed = JSON.parse(readFileSync(resolve(FIXTURE_DIR, n), "utf8"));
      expect(Number.isInteger(parsed.status), n).toBe(true);
      expect(parsed.status, n).toBeGreaterThanOrEqual(200);
      expect("body" in parsed, n).toBe(true);
    }
  });

  it("leaks no absolute server path -- everything is /SERVER/...", () => {
    for (const n of names) {
      const raw = readFileSync(resolve(FIXTURE_DIR, n), "utf8");
      expect(raw.match(/\/(home|run\/media|mnt|Users)\//g) ?? [], n).toEqual([]);
      for (const m of raw.matchAll(/"((?:\/[A-Za-z0-9._-]+)+\.(?:wav|flac|npy|npz|json|safetensors|ckpt))"/g)) {
        if (m[1].startsWith("/audio/")) continue; // an HTTP url, not a server path
        expect(m[1].startsWith("/SERVER/"), `${n}: ${m[1]}`).toBe(true);
      }
    }
  });
});
