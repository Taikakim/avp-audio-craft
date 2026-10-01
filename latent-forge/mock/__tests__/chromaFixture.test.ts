import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { FIXTURE_DIR } from "../plugin";

const RAW = readFileSync(resolve(FIXTURE_DIR, "handmade-forge_chroma_render.json"), "utf8");
const FIX = JSON.parse(RAW) as {
  status: number;
  body: {
    ok: true; frames: number; fps: number;
    bands: { shape: [number, number, number]; scale: [number, number, number]; data_b64: string };
    fold12: { shape: [number, number]; scale: number; data_b64: string };
  };
};

function byteLength(b64: string): number {
  return Buffer.from(b64, "base64").length;
}

describe("handmade-forge_chroma_render.json is exactly spec §6.3's shape", () => {
  it("carries the 200 envelope and the latent frame rate", () => {
    expect(FIX.status).toBe(200);
    expect(FIX.body.ok).toBe(true);
    expect(FIX.body.fps).toBe(10.7666015625);
    expect(FIX.body.frames).toBe(24);
  });

  it("is [3,128,T] with THREE band scales and [12,T] with ONE fold scale", () => {
    expect(FIX.body.bands.shape).toEqual([3, 128, 24]);
    expect(FIX.body.bands.scale).toHaveLength(3);
    expect(FIX.body.fold12.shape).toEqual([12, 24]);
    expect(FIX.body.fold12.scale).toBe(1.0);
  });

  it("decodes to exactly one uint8 per element, C-order", () => {
    expect(byteLength(FIX.body.bands.data_b64)).toBe(3 * 128 * 24);
    expect(byteLength(FIX.body.fold12.data_b64)).toBe(12 * 24);
  });

  it("leaks no absolute server path", () => {
    expect(RAW.match(/\/(home|run\/media|mnt|Users)\//g) ?? []).toEqual([]);
  });
});
