#!/usr/bin/env python
"""goa_granite_task.py — LUMI Granite caption-REVISION pass over the big-set Music Flamingo
captions (CONTINUITY 2026-08-03, Kim direct). Produces multiple GENRE-CORRECTED short/medium
prompt variants per track (the T2 tier to sample from at train time), using a LARGER Granite
instruct model via transformers (MI250X 64GB has the headroom the local GGUF path avoided).

Mirrors mir/src/classification/granite_revision.py's XML-tag `revise` contract, but:
  - transformers (not llama-cpp GGUF) + a bigger Granite instruct model
  - authoritative genre hint injected -> Granite CORRECTS Flamingo's genre mislabels
  - N diversity samples per track -> a POOL of variants per tag (Kim: "generate still more to pick from")
Per-rank shard, resumable (skips tracks whose granite json already exists). Air-gapped: the
Granite model must be pre-staged to $HF_HOME (see sbatch header).
"""
import os, json, re, argparse
os.environ.setdefault("HF_HUB_OFFLINE", "1")
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

SYS = ("You rewrite music descriptions into short, accurate prompt tags for a text-to-music model. "
       "Use the authoritative genre hint to CORRECT any genre mislabels in the source. "
       "Be specific and faithful to the source's instrumentation and mood. "
       "Output ONLY the requested XML tags, each on its own line, nothing else.")

# Each revision -> one XML tag. SHORT_TAGS get pooled across N samples (variants to pick from);
# medium_review is taken once (the single best genre-correct sentence).
REVISIONS = {
    "short_genremood": "genre + era + mood + BPM as SA3-style comma tags, <=12 words, "
                       "e.g. 'mid-90s goa trance, hypnotic, driving, 145 bpm'",
    "short_technical": "the lead synths / bassline / percussion character in <=15 words, no genre words",
    "short_mood":      "the emotional character and atmosphere in <=12 words",
    "medium_review":   "ONE accurate, genre-correct sentence (<=35 words) describing the whole track",
}
SHORT_TAGS = ["short_genremood", "short_technical", "short_mood"]

def read_mf(d):
    """Robust: goa_caption_task json schema may vary — take a known key or the longest string.
    goa_caption_task.py nests the actual caption text under d["captions"][prompt_type] (e.g.
    d["captions"]["full"]), NOT at the top level -- a prior version of this function checked
    only top-level keys, found nothing, and fell back to "longest top-level string", which is
    always d["path"] (the absolute file path). That ran Granite on the file path as if it were
    the track description for the entire goa big-set corpus (23232/23232, confirmed 2026-08-17)
    -- Granite parsed real artist/title out of the path and hallucinated plausible-sounding but
    audio-ungrounded genre-generic boilerplate for everything else. Check the nested dict FIRST."""
    caps = d.get("captions")
    if isinstance(caps, dict):
        for k in ("full", "technical", "genre_mood", "instrumentation", "structure"):
            v = caps.get(k)
            if isinstance(v, str) and len(v) > 40:
                return v
        cands = [v for v in caps.values() if isinstance(v, str)]
        if cands:
            return max(cands, key=len)
    for k in ("full", "music_flamingo_full", "caption", "prompt", "text", "description"):
        v = d.get(k)
        if isinstance(v, str) and len(v) > 40:
            return v
    cands = [v for k, v in d.items() if isinstance(v, str) and k not in ("path", "rel", "key")]
    return max(cands, key=len) if cands else ""

def genre_hint(d, override=None):
    # Known corpus default = goa/psytrance. --genre-hint (or the MF caption json's own
    # genre_hint field, written by goa_caption_task.py) overrides this for other corpora
    # (e.g. Suomisoundi) -- without an override this silently mislabels anything non-goa.
    if override:
        return override
    if d.get("genre_hint"):
        return str(d["genre_hint"])
    parts = ["goa trance / psytrance (NOT generic electronic/EDM/techno)"]
    yr = d.get("year") or d.get("era")
    if yr:
        parts.append(str(yr))
    return ", ".join(parts)

def build_user(mf, hint):
    instr = "\n".join(f"<{k}>{v}</{k}>" for k, v in REVISIONS.items())
    return (f"Authoritative genre (correct any mislabels to this): {hint}\n\n"
            f"Source description:\n{mf}\n\n"
            f"Produce exactly these, each inside its XML tag:\n{instr}")

def parse(raw):
    out = {}
    for k in REVISIONS:
        m = re.search(rf"<{k}>(.*?)</{k}>", raw, re.DOTALL)
        if m:
            t = re.sub(r"\s+", " ", m.group(1)).strip().strip('"')
            if t:
                out[k] = t
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", required=True, help="file of MF caption json paths, one per line")
    ap.add_argument("--out", required=True, help="output dir for granite json (basename mirrors input)")
    ap.add_argument("--model", default=os.environ.get("GRANITE_MODEL", "ibm-granite/granite-3.3-8b-instruct"))
    ap.add_argument("--n-samples", type=int, default=int(os.environ.get("GRANITE_N", "3")))
    ap.add_argument("--batch", type=int, default=int(os.environ.get("GRANITE_BATCH", "8")))
    ap.add_argument("--genre-hint", default=os.environ.get("GRANITE_GENRE_HINT"),
                    help="explicit override; otherwise auto-read from each MF caption json's "
                         "own genre_hint field (goa_caption_task.py writes it), falling back "
                         "to the hardcoded goa/psytrance default when neither is present")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    tok = AutoTokenizer.from_pretrained(a.model)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(a.model, torch_dtype=torch.bfloat16, device_map="cuda").eval()

    paths = [l.strip() for l in open(a.shard) if l.strip()]
    if a.limit:
        paths = paths[:a.limit]
    todo = [p for p in paths if not os.path.exists(os.path.join(a.out, os.path.basename(p)))]
    print(f"[granite] {len(todo)}/{len(paths)} to do; model={a.model} n_samples={a.n_samples} batch={a.batch}", flush=True)

    for i in range(0, len(todo), a.batch):
        chunk = todo[i:i + a.batch]
        items = []  # (out_path, prompt_text)
        for p in chunk:
            try:
                d = json.load(open(p))
            except Exception:
                continue
            mf = read_mf(d)
            if not mf:
                continue
            msgs = [{"role": "system", "content": SYS},
                    {"role": "user", "content": build_user(mf, genre_hint(d, a.genre_hint))}]
            txt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            items.append((os.path.join(a.out, os.path.basename(p)), txt))
        if not items:
            continue

        pools = [{k: [] for k in REVISIONS} for _ in items]  # per-item variant pools
        prompts = [t for _, t in items]
        enc = tok(prompts, return_tensors="pt", padding=True, truncation=True, max_length=2048).to("cuda")
        for s in range(a.n_samples):
            with torch.no_grad():
                gen = model.generate(**enc, max_new_tokens=256, do_sample=True,
                                     temperature=0.85, top_p=0.95, pad_token_id=tok.pad_token_id)
            new = gen[:, enc["input_ids"].shape[1]:]
            for j, seq in enumerate(new):
                parsed = parse(tok.decode(seq, skip_special_tokens=True))
                for k, v in parsed.items():
                    if v not in pools[j][k]:
                        pools[j][k].append(v)

        for (out_path, _), pool in zip(items, pools):
            rec = {k: pool[k] for k in SHORT_TAGS}            # lists of variants
            rec["medium_review"] = pool["medium_review"][0] if pool["medium_review"] else None
            with open(out_path, "w") as f:
                json.dump(rec, f, ensure_ascii=False)
        print(f"[granite] {min(i + a.batch, len(todo))}/{len(todo)}", flush=True)

    print("[granite] done", flush=True)

if __name__ == "__main__":
    main()
