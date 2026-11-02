# Owner: THE-FINN (created 2026-11-03) -- our .ckpt DoRA -> .safetensors for upstream's LiteRT runtime. Loads our own file only.
import sys, json, torch
from safetensors.torch import save_file
src, dst = sys.argv[1:3]
d = torch.load(src, map_location='cpu', weights_only=False)
sd = {k: v.float().contiguous().clone() for k, v in d['state_dict'].items()}
cfg = d['lora_config']
save_file(sd, dst, metadata={'lora_config': json.dumps(cfg)})
print('tensors', len(sd), 'cfg', cfg)
import collections
print(collections.Counter(k.split('.')[0] for k in sd))
