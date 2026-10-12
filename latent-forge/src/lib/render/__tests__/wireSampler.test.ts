import { describe, expect, it } from "vitest";
import { wireSampler } from "../payloads";

// Review 2026-10-01: the wire must carry the sampler the SAMPLER select shows, not a stored one the
// current objective does not offer.
describe("wireSampler", () => {
  it("keeps a sampler the objective offers", () => {
    expect(wireSampler("dpmpp", "rectified_flow")).toBe("dpmpp");
    expect(wireSampler("euler", "rf_denoiser")).toBe("euler");
  });
  it("falls back to the objective's first option, as the select does", () => {
    expect(wireSampler("dpmpp", "rf_denoiser")).toBe("pingpong");
    expect(wireSampler("rk4", "rf_denoiser")).toBe("pingpong");
  });
  it("leaves the server default alone", () => {
    expect(wireSampler("", "rf_denoiser")).toBeNull();
    expect(wireSampler(null, "rectified_flow")).toBeNull();
  });
});
