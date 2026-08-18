# eval/test_spectral_repair_lora.py — run: SAO/.venv/bin/python -m pytest eval/test_spectral_repair_lora.py -q
import torch

from eval.spectral_repair_lora import refactor, repair_pair


def _rand_pair(out=40, inn=30, r=8, seed=0):
    g = torch.Generator().manual_seed(seed)
    A = torch.randn(r, inn, generator=g); B = torch.randn(out, r, generator=g)
    return A, B


def test_refactor_roundtrip_reproduces_BA_at_same_shapes():
    A, B = _rand_pair()
    A2, B2 = refactor(B @ A, rank=8)
    assert A2.shape == A.shape and B2.shape == B.shape
    assert torch.allclose(B2 @ A2, B @ A, atol=1e-4)


def test_remove_top1_removes_exactly_the_leading_component():
    A, B = _rand_pair()
    M = B @ A
    U, s, Vh = torch.linalg.svd(M, full_matrices=False)
    A2, B2 = repair_pair(A, B, mode="remove", k=1)
    expected = M - s[0] * torch.outer(U[:, 0], Vh[0])
    assert torch.allclose(B2 @ A2, expected, atol=1e-4)


def test_keep_only_top1_leaves_a_rank1_matrix_equal_to_the_leading_component():
    A, B = _rand_pair()
    M = B @ A
    U, s, Vh = torch.linalg.svd(M, full_matrices=False)
    A2, B2 = repair_pair(A, B, mode="keep", k=1)
    assert torch.allclose(B2 @ A2, s[0] * torch.outer(U[:, 0], Vh[0]), atol=1e-4)
    assert torch.linalg.matrix_rank(B2 @ A2, atol=1e-4) == 1


def test_shrink_scales_only_the_top_components():
    A, B = _rand_pair()
    M = B @ A
    U, s, Vh = torch.linalg.svd(M, full_matrices=False)
    A2, B2 = repair_pair(A, B, mode="shrink", k=2, factor=0.25)
    s2 = s.clone(); s2[:2] *= 0.25
    assert torch.allclose(B2 @ A2, (U * s2) @ Vh, atol=1e-4)


def test_remove_zero_is_identity():
    A, B = _rand_pair()
    A2, B2 = repair_pair(A, B, mode="remove", k=0)
    assert torch.allclose(B2 @ A2, B @ A, atol=1e-4)
