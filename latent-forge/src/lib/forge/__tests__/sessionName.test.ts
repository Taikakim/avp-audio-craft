import { describe, expect, it } from "vitest";
import { isValidSessionName, SESSION_NAME_RE } from "../sessionName";

describe("session name validation (spec §6.3, client-side before the PUT)", () => {
  it("rejects `.` and `..`, which the pattern allows but the server refuses (WINTERMUTE 2026-09-25; critic follow-up #8)", () => {
    expect(isValidSessionName(".")).toBe(false);
    expect(isValidSessionName("..")).toBe(false);
    expect(isValidSessionName("...")).toBe(true);        // only the two path names are special
    expect(isValidSessionName(".hidden")).toBe(true);
  });

  it("accepts letters, digits, dot, underscore, dash, up to 80 chars", () => {
    expect(isValidSessionName("session_2026-09-23.v2")).toBe(true);
    expect(isValidSessionName("a".repeat(80))).toBe(true);
  });
  it("rejects empty, spaces, slashes, and over-length names", () => {
    expect(isValidSessionName("")).toBe(false);
    expect(isValidSessionName("my set")).toBe(false);
    expect(isValidSessionName("a/b")).toBe(false);
    expect(isValidSessionName("a".repeat(81))).toBe(false);
  });
  it("SESSION_NAME_RE is exactly the spec's pattern", () => {
    expect(SESSION_NAME_RE.source).toBe("^[A-Za-z0-9._-]{1,80}$");
  });
});
