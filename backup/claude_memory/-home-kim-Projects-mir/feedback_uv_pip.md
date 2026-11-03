---
name: use uv pip not pip
description: Always use uv pip (not pip) for package installation in this project
type: feedback
---

Always use `uv pip install` instead of `pip install` for package management in this project.

**Why:** User preference — this project uses uv as the package manager.

**How to apply:** Any time a shell command would use `pip install ...`, use `uv pip install ...` instead. Pass this instruction to any subagents dispatched for implementation tasks.
