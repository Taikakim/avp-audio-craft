// Owner: WINTERMUTE (created 2026-10-27)
import test from 'node:test';
import assert from 'node:assert/strict';
import { ROT, targetA, angleDeg, overlap, lossOf, createRotSim } from '../lib/lora-rot.js';

function run(mult) {
  const sim = createRotSim({ mult });
  const sizes = [];
  const steps = [];
  while (!sim.done) { const r = sim.step(); steps.push(r); sizes.push(Math.hypot(r.a[0], r.a[1])); }
  return { sim, sizes, steps };
}

test('1. x1: A turns under 10 deg, overlap with early A above 0.99, loss above 0.5', () => {
  const { sim } = run(1);
  const turn = Math.abs(angleDeg(sim.a));
  console.log(`x1: angle ${angleDeg(sim.a).toFixed(2)} overlap ${overlap(sim.a, sim.aEarly).toFixed(4)} loss ${sim.losses.at(-1).toFixed(4)}`);
  assert.ok(turn < 10, `turn ${turn}`);
  assert.ok(overlap(sim.a, sim.aEarly) > 0.99);
  assert.ok(sim.losses.at(-1) > 0.5);
});

test('2. x20: A ends within 2 deg of 70, overlap with early A below 0.8, loss below 1e-3', () => {
  const { sim } = run(20);
  console.log(`x20: angle ${angleDeg(sim.a).toFixed(2)} overlap ${overlap(sim.a, sim.aEarly).toFixed(4)} loss ${sim.losses.at(-1).toExponential(2)}`);
  assert.ok(Math.abs(angleDeg(sim.a) - 70) < 2);
  assert.ok(overlap(sim.a, sim.aEarly) < 0.8);
  assert.ok(sim.losses.at(-1) < 1e-3);
});

test('3. first step moves only B, by lrB, along b*', () => {
  const sim = createRotSim();
  assert.equal(sim.aEarly, null);
  const r = sim.step();
  assert.equal(r.stepA, 0);
  assert.ok(Math.abs(r.stepB - ROT.lrB) < 1e-12);
  assert.ok(overlap(sim.b, ROT.bTarget) > 0.999);
});

test('4. |a| stays between 2.9 and 3.3 at every step, both settings', () => {
  for (const m of [1, 20]) {
    const { sizes } = run(m);
    assert.equal(sizes.length, ROT.steps);
    for (const s of sizes) assert.ok(s > 2.9 && s < 3.3, `x${m}: ${s}`);
  }
});

test('5. two x1 sims give identical trails', () => {
  assert.deepEqual(run(1).sim.trail, run(1).sim.trail);
  const s = run(1).sim;
  assert.equal(s.trail.a.length, ROT.steps + 1);
  assert.equal(s.losses.length, ROT.steps + 1);
  assert.ok(Math.abs(s.losses[0] - lossOf(ROT.aStart, [0, 0])) < 1e-15);
});

test('6. overlap and angleDeg basics', () => {
  assert.ok(Math.abs(overlap([1, 2], [2, 4]) - 1) < 1e-12);
  assert.ok(Math.abs(overlap([1, 2], [-1, -2]) - 1) < 1e-12);
  assert.ok(Math.abs(overlap([1, 0], [0, 5])) < 1e-12);
  assert.equal(overlap([0, 0], [1, 0]), 0);
  assert.ok(Math.abs(angleDeg([0, 1]) - 90) < 1e-12);
  assert.ok(Math.abs(angleDeg(targetA()) - 70) < 1e-12);
});
