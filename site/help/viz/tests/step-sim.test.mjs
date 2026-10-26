// Owner: WINTERMUTE (created 2026-10-26)
import test from 'node:test';
import assert from 'node:assert/strict';
import { createSim, STEP_AT, TOTAL_STEPS } from '../lib/step-sim.js';
import { near, mean } from './helpers.mjs';

const run = (id, opts) => { const s = createSim(id, opts); const out = []; while (!s.done) out.push(s.step()); return out; };
const win = (xs, a, b, key) => mean(xs.slice(a, b).map((r) => r[key]));

test('a run lasts TOTAL_STEPS steps and is reproducible for a given seed', () => {
  const a = run('steady'), b = run('steady');
  assert.equal(a.length, TOTAL_STEPS);
  assert.deepEqual(a[10].adamUpdate, b[10].adamUpdate);
  assert.notDeepEqual(a[10].adamUpdate, run('steady', { seed: 8 })[10].adamUpdate);
});

test('gradient drops 100x: AdamW steps fall below a tenth, Muon stays flat', () => {
  const drop = run('drop');
  assert.ok(win(drop, 300, 450, 'adamMean') < 0.1 * win(drop, 100, STEP_AT, 'adamMean'));
  near(win(drop, 300, 450, 'muonMean') / win(drop, 100, STEP_AT, 'muonMean'), 1, 0.25, 'muon ratio');
});

test('noisy: AdamW moves 0.2-0.5 of lr per weight (the guide\'s 0.2-0.4), Muon about 0.2', () => {
  const noisy = run('noisy');
  const am = win(noisy, 100, 450, 'adamMean');
  assert.ok(am > 0.2 && am < 0.5, `noisy AdamW mean step ${am}`);
  near(win(noisy, 100, 450, 'muonMean'), 0.2, 0.06, 'Muon moves about 0.2 lr per weight');
});

test('gradient rises 100x: AdamW overshoots its usual step, Muon does not change', () => {
  const rise = run('rise');
  assert.ok(win(rise, STEP_AT, STEP_AT + 5, 'adamMean') > 1.3 * win(rise, 100, STEP_AT, 'adamMean'));
  near(win(rise, 300, 450, 'muonMean') / win(rise, 100, STEP_AT, 'muonMean'), 1, 0.25, 'muon ratio');
});

test('unknown scenario throws', () => assert.throws(() => createSim('nope')));

test('steady pins AdamW near 0.6 x lr (the page explains why it exceeds the guide\'s 0.2-0.4)', () => {
  const am = win(run('steady'), 100, 450, 'adamMean');
  assert.ok(am > 0.5 && am < 0.7, `steady AdamW mean step ${am}`);
});
