// Owner: WINTERMUTE (created 2026-10-27)
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {
  HEAD_PARAMS, RENAME, MIN_SPECTRAL_DIM, GROUPS, renamed, inferAttentionDim, blockCount, route, stepPerWeight,
  ROWS, rowRouting, differingRows, summary,
} from '../lib/routing.js';

const FIX = JSON.parse(fs.readFileSync(new URL('./routing_fixture.json', import.meta.url), 'utf8'));
const close = (a, b) => assert.ok(Math.abs(a - b) <= 1e-12 * Math.abs(b), `${a} vs ${b}`);
const strip = (m) => Object.fromEntries([...m].map(([k, v]) => [k, { group: v.group, blocks: v.blocks }]));

test('1. route(HEAD_PARAMS) equals the fixture "ours" for all 28 names', () => {
  assert.deepEqual(HEAD_PARAMS, FIX.params);
  assert.deepEqual(RENAME, FIX.rename);
  assert.equal(HEAD_PARAMS.length, 28);
  assert.equal(MIN_SPECTRAL_DIM, 64);
  assert.deepEqual(GROUPS, ['spectral', 'sign', 'colnorm']);
  assert.deepEqual(strip(route(HEAD_PARAMS)), FIX.ours);
});

test('2. route of the renamed params equals the fixture "expected_names"', () => {
  const r = route(HEAD_PARAMS.map(([n, s]) => [renamed(n), s]));
  assert.equal(r.size, 28);
  assert.deepEqual(strip(r), FIX.expected_names);
});

test('3. proj must be renamed too: attention width 768 / 1 block without to_out, 256 / 3 blocks with it', () => {
  const onlyQkv = HEAD_PARAMS.map(([n, s]) => [n.split('.attn.qkv.').join('.attn.to_qkv.'), s]);
  assert.equal(inferAttentionDim(onlyQkv), 768);
  assert.equal(blockCount('blocks.0.attn.to_qkv.weight', [768, 256], 768), 1);
  const both = HEAD_PARAMS.map(([n, s]) => [renamed(n), s]);
  assert.equal(inferAttentionDim(both), 256);
  assert.equal(blockCount('blocks.0.attn.to_qkv.weight', [768, 256], 256), 3);
  assert.equal(inferAttentionDim(HEAD_PARAMS), null);
});

test('4. differing rows and summary counts', () => {
  assert.deepEqual([...differingRows()].sort(), ['adaln', 'qkv', 'time1', 'time2']);
  const count = (o) => { const c = { spectral: 0, sign: 0, colnorm: 0 }; for (const v of Object.values(o)) c[v.group]++; return c; };
  assert.deepEqual(summary('ours'), count(FIX.ours));
  assert.deepEqual(summary('expected'), count(FIX.expected_names));
  assert.deepEqual(summary('ours'), { spectral: 11, sign: 15, colnorm: 2 });
  assert.deepEqual(summary('expected'), { spectral: 11, sign: 17, colnorm: 0 });
  assert.equal(ROWS.length, 11);
  assert.throws(() => rowRouting('x'));
});

test('5. step per weight at lr 1e-2', () => {
  const r = route(HEAD_PARAMS);
  const P = (n) => r.get(n);
  const S = new Map(HEAD_PARAMS);
  close(stepPerWeight(P('blocks.0.attn.proj.weight'), [256, 256], 1e-2), 6.25e-4);
  // the stack as one matrix (ours): radius sqrt 3
  close(stepPerWeight(P('blocks.0.attn.qkv.weight'), [768, 256], 1e-2), 6.25e-4);
  assert.equal(P('blocks.0.attn.qkv.weight').blocks, 1);
  close(stepPerWeight(P('blocks.0.attn.proj.bias'), [256], 1e-2), 1e-2);
  close(stepPerWeight(P('out_proj.weight'), [1, 256], 1e-2), 6.25e-4);
  close(stepPerWeight({ group: 'sign', blocks: 1, radius: 1 / 16 }, [1536, 256], 1e-2), 6.25e-4);
  close(stepPerWeight(P('blocks.0.mlp.2.weight'), [256, 1024], 1e-2), 3.125e-4);
  assert.equal(stepPerWeight(P('t_embedder.mlp.0.weight'), [256, 256], 1e-2), null);
  // Splitting changes the directions of the update; the radius stays that of the whole matrix (routing.py), so the
  // formula max(rows/blocks, cols) gives a LARGER step for the split stack: 1e-2*sqrt(3)/16, not 6.25e-4.
  const split = { group: 'spectral', blocks: 3, radius: Math.sqrt(3) };
  close(stepPerWeight(split, [768, 256], 1e-2), 1e-2 * Math.sqrt(3) / 16);
  void S;
});

test('6. rule order', () => {
  const r = route([['x.modulation.embed.weight', [256, 256]], ['h.weight', [32, 32]]]);
  assert.equal(r.get('x.modulation.embed.weight').group, 'sign');
  assert.equal(r.get('h.weight').group, 'sign');
});

test('7. rowRouting rows are uniform and consistent with the fixture', () => {
  for (const view of ['ours', 'expected']) {
    const rr = rowRouting(view);
    const fx = view === 'ours' ? FIX.ours : FIX.expected_names;
    for (const row of ROWS) {
      const v = rr[row.id];
      assert.deepEqual(v.names.map((n) => fx[n].group), v.names.map(() => v.group));
    }
    assert.ok(rr.biases.names.every((n) => n.endsWith('.bias')) && rr.biases.group === 'sign');
    close(rr.biases.step, 1e-2);
  }
});
