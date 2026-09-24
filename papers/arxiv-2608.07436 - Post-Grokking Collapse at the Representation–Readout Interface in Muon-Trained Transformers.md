# arxiv-2608.07436 - Post-Grokking Collapse at the Representation–Readout Interface in Muon-Trained Transformers

**Reading depth:** abstract + key passages (elasticity result, ablation, conclusion) via pdftotext search; NOT a full read (C 2026-09-22).

**What it contains:** Muon groks faster on modular addition but then loses generalisation. After the train loss is solved, its step has elasticity −0.03 on gradient size (AdamW +1.5) and drifts along the representation/readout ambiguity. Freezing either side prevents it.

**For us / what stays ours:** LoRA has the same symmetry (B·A = (BX)(X⁻¹A)). Measured with eval/lora_gauge_drift.py: the gauge share of step energy rises 4.8→12.4% on audition_160ep (chance 2%). Harmless so far.
