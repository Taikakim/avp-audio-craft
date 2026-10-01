// Spec §6.3, verbatim: the server 400s a name outside this pattern, so the
// client validates before the PUT rather than round-tripping a guaranteed error.
export const SESSION_NAME_RE = /^[A-Za-z0-9._-]{1,80}$/;

// The pattern admits "." and "..", which the server refuses on their own (WINTERMUTE 2026-09-25;
// M2's `name in (".", "..") or not _NAME_RE.match(name)`) -- critic follow-up #8.
export function isValidSessionName(name: string): boolean {
  return name !== "." && name !== ".." && SESSION_NAME_RE.test(name);
}
