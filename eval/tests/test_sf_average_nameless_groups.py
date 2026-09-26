"""sf_averaged_adapter_ckpt returns the checkpoint unchanged for optimizers without param_names.

Plain torch AdamW/Lion param_groups carry no 'param_names' and no Schedule-Free 'x'; the helper
used to KeyError on them (2026-09-26, plain-AdamW ablation arm) instead of rendering raw weights.
"""
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import model_matrix_gen as mmg  # noqa: E402


def test_adamw_checkpoint_is_returned_unchanged(tmp_path):
    p = torch.nn.Parameter(torch.zeros(2, 2))
    opt = torch.optim.AdamW([p], lr=1e-3)
    p.grad = torch.ones(2, 2)
    opt.step()
    ck = tmp_path / "adamw.ckpt"
    torch.save({"state_dict": {"model.w.lora_B": p.detach()}, "lora_config": {},
                "optimizer_states": [opt.state_dict()]}, ck)
    assert "param_names" not in opt.state_dict()["param_groups"][0]
    assert mmg.sf_averaged_adapter_ckpt(ck, tmp_path) == Path(ck)
