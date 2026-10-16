# Owner: KUANG (created 2026-10-17)
"""train.py --log-grad-noise builds the two half-batch gradients from accumulated micro-batches:
half 1 mean = 2 * (grads after the first grad_accum/2 micro-batches), half 2 mean = 2 * (total - that),
because every micro-batch loss is divided by grad_accum before backward. Checked here on a toy model
against directly computed half means (CPU, no SA3)."""
import pytest
import torch

modular_opt = pytest.importorskip("stable_audio_tools.training.modular_opt")
if not hasattr(modular_opt, "GradNoiseMeter"):
    pytest.skip("stable_audio_tools without the C-series modular_opt", allow_module_level=True)


@pytest.mark.parametrize("accum", [2, 4])
def test_half_means_from_accumulation(accum):
    torch.manual_seed(0)
    lin = torch.nn.Linear(16, 8)
    xs = [torch.randn(1, 16) for _ in range(accum)]
    ys = [torch.randn(1, 8) for _ in range(accum)]
    meter = modular_opt.GradNoiseMeter(lin.named_parameters(), every=1)

    def mean_grad(idx):
        lin.zero_grad()
        sum(torch.nn.functional.mse_loss(lin(xs[i]), ys[i]) for i in idx).div(len(idx)).backward()
        return lin.weight.grad.clone()

    want1, want2 = mean_grad(range(accum // 2)), mean_grad(range(accum // 2, accum))
    lin.zero_grad()
    c1 = None
    for i in range(accum):                       # the trainer's loop: loss / grad_accum, then backward
        (torch.nn.functional.mse_loss(lin(xs[i]), ys[i]) / accum).backward()
        if i == accum // 2 - 1:
            c1 = meter.capture()
    tot = meter.capture()
    h1, h2 = 2.0 * c1[0], 2.0 * (tot[0] - c1[0])
    assert torch.allclose(h1, want1, atol=1e-6) and torch.allclose(h2, want2, atol=1e-6)
    out = meter.measure(0, [h1], [h2], b_half=accum // 2)
    assert -1.0 <= out["grad_noise/cos_pooled"] <= 1.0
