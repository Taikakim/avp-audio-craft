// Owner: WINTERMUTE (created 2026-10-26)
import assert from 'node:assert/strict';

export const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg ?? ''} ${a} vs ${b} (tol ${tol})`);
export const mean = (xs) => xs.reduce((s, x) => s + x, 0) / xs.length;
