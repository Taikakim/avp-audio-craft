# VENDORED SHIM (LUMI) — minimal stable_audio_tools namespace carrying ONLY the
# Fusion optimizer modules that stable-audio-3's training imports. The real
# package __init__ pulls the full SAT model zoo (heavy deps not in the LUMI
# container); this shim intentionally does none of that. Regenerate with
# lumi/make_vendor.sh. Do NOT add model-side imports here.
