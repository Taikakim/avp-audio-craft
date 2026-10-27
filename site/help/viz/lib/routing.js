// Owner: WINTERMUTE (created 2026-10-27)
// Parameter routing for the `routing` animation: a JavaScript port of the rules in
// stable-audio-tools/stable_audio_tools/training/modular_opt/routing.py (copied 2026-10-27, default arguments:
// split_qkv=true, split_adaln=true, scalar_opt='sign', no force_sign, spectral_all=false).

// Regexes copied verbatim (re.IGNORECASE -> i flag; re.search -> RegExp.test).
const EMBEDDING_RE = /(embed|embedding|patch_embed|time_embed|token_embed)/i;
const OUTPUT_RE = /(^|\.)(project_out|final_layer|lm_head|output_proj|out_head|final_proj)($|\.)/i; // unused by the router, kept for fidelity
const ADALN_RE = /(^|\.)(global_cond_embedder\.2|modulation|scale_shift_table)($|\.)/i;
const FUSED_ATTN_RE = /\.(to_qkv|to_kv|to_q)\./;
const TO_OUT_RE = /\.to_out\./;
void OUTPUT_RE;

export const MIN_SPECTRAL_DIM = 64;
export const GROUPS = ['spectral', 'sign', 'colnorm'];

// The 28 parameters of one LatCH head (dim 256, depth 2), same order as routing_fixture.json "params".
export const HEAD_PARAMS = [
  ['latent_proj.weight', [256, 64]],
  ['latent_proj.bias', [256]],
  ['t_embedder.mlp.0.weight', [256, 256]],
  ['t_embedder.mlp.0.bias', [256]],
  ['t_embedder.mlp.2.weight', [256, 256]],
  ['t_embedder.mlp.2.bias', [256]],
  ['blocks.0.attn.qkv.weight', [768, 256]],
  ['blocks.0.attn.proj.weight', [256, 256]],
  ['blocks.0.attn.proj.bias', [256]],
  ['blocks.0.mlp.0.weight', [1024, 256]],
  ['blocks.0.mlp.0.bias', [1024]],
  ['blocks.0.mlp.2.weight', [256, 1024]],
  ['blocks.0.mlp.2.bias', [256]],
  ['blocks.0.adaLN_mod.1.weight', [1536, 256]],
  ['blocks.0.adaLN_mod.1.bias', [1536]],
  ['blocks.1.attn.qkv.weight', [768, 256]],
  ['blocks.1.attn.proj.weight', [256, 256]],
  ['blocks.1.attn.proj.bias', [256]],
  ['blocks.1.mlp.0.weight', [1024, 256]],
  ['blocks.1.mlp.0.bias', [1024]],
  ['blocks.1.mlp.2.weight', [256, 1024]],
  ['blocks.1.mlp.2.bias', [256]],
  ['blocks.1.adaLN_mod.1.weight', [1536, 256]],
  ['blocks.1.adaLN_mod.1.bias', [1536]],
  ['norm_final.weight', [256]],
  ['norm_final.bias', [256]],
  ['out_proj.weight', [1, 256]],
  ['out_proj.bias', [1]],
];

export const RENAME = [
  ['.attn.qkv.', '.attn.to_qkv.'],
  ['.attn.proj.', '.attn.to_out.'],
  ['.adaLN_mod.', '.modulation.'],
  ['t_embedder.mlp.', 'time_mlp.'],
];

export function renamed(name) {
  let out = name;
  for (const [a, b] of RENAME) out = out.split(a).join(b);
  return out;
}

const isWeight = (n) => n.endsWith('lora_B') || n.endsWith('.weight');

function gcd(a, b) { return b === 0 ? a : gcd(b, a % b); }

export function inferAttentionDim(params) {
  for (const [n, shape] of params) if (TO_OUT_RE.test(n) && isWeight(n)) return shape[0];
  const outs = params.filter(([n]) => FUSED_ATTN_RE.test(n) && isWeight(n)).map(([, s]) => s[0]);
  if (outs.length) return outs.length > 1 ? outs.reduce(gcd) : outs[0];
  return null;
}

// get_block_count with split_qkv = split_adaln = true.
export function blockCount(name, shape, attnDim) {
  if (shape.length !== 2) return 1;
  if (attnDim && FUSED_ATTN_RE.test(name)) {
    if (shape[0] % attnDim === 0 && shape[0] / attnDim > 1) return shape[0] / attnDim;
  }
  if (ADALN_RE.test(name)) {
    if (shape[1] > 0 && shape[0] % shape[1] === 0 && shape[0] / shape[1] > 1) return shape[0] / shape[1];
  }
  return 1;
}

function radiusScale(shape) {
  if (shape.length < 2) return 1;
  const [o, i] = shape;
  if (i <= 0) return 1;
  return Math.max(1, Math.sqrt(o / i));
}

// Per-parameter loop of build_modular_param_groups; attention width inferred from the same params, as in Python.
export function route(params) {
  const attnDim = inferAttentionDim(params);
  const out = new Map();
  for (const [name, shape] of params) {
    const nd = shape.length;
    let group;
    if (nd < 2) group = 'sign';
    else if (ADALN_RE.test(name)) group = 'sign';
    else if (EMBEDDING_RE.test(name) && nd === 2) group = 'colnorm';
    else if (nd === 2 && Math.min(...shape) >= MIN_SPECTRAL_DIM) group = 'spectral';
    else group = 'sign';
    let radius;
    if (group === 'spectral') radius = radiusScale(shape);
    else if (group === 'sign' && nd === 2) radius = shape[1] > 0 ? 1 / Math.sqrt(shape[1]) : 1;
    else radius = 1;
    out.set(name, { group, blocks: blockCount(name, shape, attnDim), radius });
  }
  return out;
}

// Step per weight per step, before momentum and before the optimizer's row normalisation.
// Splitting into blocks changes the directions, not the size: rows/blocks only enters the orthogonal-update RMS, and
// the radius stays that of the whole matrix (as in routing.py).
export function stepPerWeight({ group, blocks, radius }, shape, lr) {
  if (group === 'spectral') return lr * radius / Math.sqrt(Math.max(shape[0] / blocks, shape[1]));
  if (group === 'sign') return lr * radius;
  return null; // colnorm: not worked out in the guide
}

export const ROWS = [
  { id: 'input', label: 'Input projection', names: ['latent_proj.weight'] },
  { id: 'time1', label: 'Time-embedding layer 1', names: ['t_embedder.mlp.0.weight'] },
  { id: 'time2', label: 'Time-embedding layer 2', names: ['t_embedder.mlp.2.weight'] },
  { id: 'adaln', label: 'AdaLN emitter', names: ['blocks.0.adaLN_mod.1.weight', 'blocks.1.adaLN_mod.1.weight'] },
  { id: 'qkv', label: 'Attention Q, K, V (stacked)', names: ['blocks.0.attn.qkv.weight', 'blocks.1.attn.qkv.weight'] },
  { id: 'attn-out', label: 'Attention output', names: ['blocks.0.attn.proj.weight', 'blocks.1.attn.proj.weight'] },
  { id: 'mlp-up', label: 'MLP up', names: ['blocks.0.mlp.0.weight', 'blocks.1.mlp.0.weight'] },
  { id: 'mlp-down', label: 'MLP down', names: ['blocks.0.mlp.2.weight', 'blocks.1.mlp.2.weight'] },
  {
    id: 'biases',
    label: 'Biases (all layers)',
    names: HEAD_PARAMS.filter(([n, s]) => s.length === 1 && n.endsWith('.bias') && n !== 'norm_final.bias').map(([n]) => n),
  },
  { id: 'final-norm', label: 'Final normalisation', names: ['norm_final.weight', 'norm_final.bias'] },
  { id: 'output', label: 'Output layer', names: ['out_proj.weight'] },
];

const LR = 1e-2;
const SHAPES = new Map(HEAD_PARAMS);

export function rowRouting(view) {
  if (view !== 'ours' && view !== 'expected') throw new Error(`unknown view ${view}`);
  const expected = view === 'expected';
  const names = (ns) => (expected ? ns.map(renamed) : ns);
  const routed = route(HEAD_PARAMS.map(([n, s]) => [expected ? renamed(n) : n, s]));
  const out = {};
  for (const row of ROWS) {
    const rn = names(row.names);
    const infos = rn.map((n) => routed.get(n));
    const { group, blocks } = infos[0];
    for (const i of infos) {
      if (i.group !== group || i.blocks !== blocks) throw new Error(`row ${row.id} is not uniform in view ${view}`);
    }
    const shapes = row.names.map((n) => SHAPES.get(n));
    out[row.id] = { group, blocks, names: rn, shape: shapes[0], shapes, step: stepPerWeight(infos[0], shapes[0], LR) };
  }
  return out;
}

export function differingRows() {
  const a = rowRouting('ours');
  const b = rowRouting('expected');
  return ROWS.map((r) => r.id).filter((id) => a[id].group !== b[id].group || a[id].blocks !== b[id].blocks);
}

export function summary(view) {
  const expected = view === 'expected';
  const routed = route(HEAD_PARAMS.map(([n, s]) => [expected ? renamed(n) : n, s]));
  const out = { spectral: 0, sign: 0, colnorm: 0 };
  for (const { group } of routed.values()) out[group]++;
  return out;
}
