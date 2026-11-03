---
name: uv-reinstall-dependency-risk
description: uv pip install --reinstall without --no-deps can silently pull in a wrong dependency stack (e.g. CUDA torch over a custom ROCm torch build)
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b46bac88-6902-4ad2-a9ea-d4df3a96ae04
---

When reinstalling a single package from a local wheel/path in a venv with a **custom-built** dependency (e.g. ROCm torch, a CK-compiled flash-attn), always pass `--no-deps` to `uv pip install`. Without it, `--reinstall` resolves and reinstalls the package's full declared dependency tree — for a package like `flash-attn` that declares a plain `torch` dependency, this can mean uv installing a vanilla PyPI CUDA torch (pulling `nvidia-cublas`, `nvidia-cudnn`, etc.) **over** a working custom ROCm torch build, silently, mid-command.

**Why:** Discovered 2026-07-05 while trying to restore a CK flash-attn build in `stable-audio-3/.venv` (see [[rocm-flash-attn-env]]). `uv pip install --python .venv/bin/python <wheel> --reinstall` (no `--no-deps`) started downloading `nvidia/cu13/lib/libcublasLt.so` and `torch/lib/libtorch_cuda.so` into a temp dir — caught via `ls -la /proc/<pid>/fd` showing open handles to those files mid-install, before it reached the final atomic swap into site-packages. Killed the process immediately; verified the ROCm torch build was untouched afterward (`torch.__version__` still `2.10.0+rocm7.2.3...`, `torch.version.hip` still set).

**How to apply:** Before running `uv pip install <path> --reinstall` (or plain `--reinstall`) in any of the SAO venvs (all of which carry custom ROCm/CK builds — see MASTER §5), always add `--no-deps` unless you specifically intend to let uv touch the dependency tree. If you see open file descriptors to `nvidia/` or unexpected `torch/lib/` paths in `/proc/<pid>/fd` during an "unrelated" package install, that's the signal to kill it immediately and check `torch.version.hip` afterward. Also relevant when reinstalling any package that depends on `torch` in these venvs (not just flash-attn).

Separately learned in the same incident: a wheel that installs cleanly (`--no-deps`, no errors) can still be **ABI-incompatible** with the exact torch build in the venv (e.g. `undefined symbol: c10::cuda::CUDACachingAllocator::allocator`) — this crashes on `import`, which is *worse* than a missing extension (which is usually caught by a `try/except ModuleNotFoundError` and degrades gracefully). Always re-verify the actual application import path (e.g. `import stable_audio_3`, not just the raw extension module) after any such swap, and be ready to revert (delete the `.so`) if it crashes harder than the pre-existing state.
