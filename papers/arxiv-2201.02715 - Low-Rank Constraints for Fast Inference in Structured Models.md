# Low-Rank Constraints for Fast Inference in Structured Models

**arXiv 2201.02715v1** · Justin T. Chiu (Cornell), Yuntian Deng (Harvard), Alexander M. Rush
(Cornell) · **NeurIPS 2021** · read 2026-08-12 (WINTERMUTE), pp.1–4 in detail

Last of my eleven. I expected an efficiency paper with no musical content. **It is the candidate
answer to the discretisation gate I identified across the other three topology papers**, and one
of its four evaluation tasks is polyphonic music modelling.

---

## What it contains

**The bottleneck.** Structured latent models — HMMs, PCFGs, HSMMs — give interpretable,
controllable, probabilistically-principled sequence models, but inference costs **quadratic**
(HMM) to **cubic** (PCFG) in the number of hidden states. That caps how large a state space you
can use, which caps what the model can represent.

**The trick.** Inference over these models reduces to a labelled directed hypergraph
marginalisation whose inner loop is a **matrix–vector product** `α_u ⟵ Ψ_e β_v`. Constrain the
scoring matrix to low rank, `Ψ_e = U_e V_eᵀ`, and reassociate:

```
Ψ_e β_v = (U_e V_eᵀ) β_v = U_e (V_eᵀ β_v)
```

which **trades a factor of L (states) for a factor of N (rank)**. Explicitly inspired by
linear-attention work (Performers, Katharopoulos et al.), applied to a different formalism.
`U_e`, `V_e` are parameterised as embedding matrices with a nonnegativity map so the result
stays a valid probability distribution.

**Results.** HMMs scale past **16,000 states**; PCFGs achieve significant perplexity reduction
against prior large-state work; HSMMs scale to much larger state spaces **with continuous
emissions**. Tasks: language modelling, **polyphonic music modelling**, unsupervised grammar
induction, video modelling.

**Their own caveat, stated up front:** applying low-rank constraints in high-dimensional
structured models "is nontrivial … due to reduced expressivity", and they had to develop
techniques to overcome practical difficulties. Rank buys speed by spending expressivity.

---

## What stays ours

**1 — The HSMM-with-continuous-emissions result is a direct answer to the gate blocking three
other papers in my batch.** I flagged, filing 2405.04796, that `2505.10004` needs a surrogate
`v(t)`, meter networks need an articulation set, and featured-time-series PH needs a
discretisation — **all three reduce to turning our continuous multi-field timeseries into the
right discrete/scalar stream**. A hidden semi-Markov model over continuous emissions does
exactly that, and gives three things at once:

| HSMM output | what it feeds |
|---|---|
| discrete latent states | **nodes** for the score-network / featured-PH graph constructions |
| state **durations** | cycle lengths, candidate metrical layer periods |
| segment **boundaries** | articulation points for meter networks, change-points |

So the gate has a named, principled candidate rather than an ad-hoc binning threshold — and this
paper is what makes such a model affordable at the state-space sizes real audio features need.

**2 — It links my batch to C's unread block.** PCFGs are how symbolic harmony is formalised, and
C's second-wave queue contains Rohrmeier's *Rules and Representations in a Generative Syntax of
Tonal Harmony* — a PCFG for harmony. This paper is the inference machinery that makes such
grammars tractable at scale. Whoever reads that block should know this exists.

**3 — Their framing is our agenda, in their words.** Structured models "afford interpretability
and controllability that are lacking in neural models". We are trying to bolt controllability
onto a neural generative model; this is the other direction — start from a controllable model
and scale it. Not a proposal to switch, but a reminder that the axis we are fighting for is free
in a different model family, which is worth knowing when judging how much complexity our control
stack deserves.

**Honest limits.** It is inference-efficiency work: nothing here is a control target, nothing is
askable by ear. Adopting it means adopting a modelling paradigm we do not currently use anywhere
in the pipeline. And rank trades expressivity — their own caveat — so the win is not free.
Filed, like 1708.09359, as **infrastructure**: it removes a blocker rather than naming a knob.

---

## Status

Read pp.1–4 in detail (abstract, introduction, hypergraph background, the HMM/PCFG/HSMM
instantiations, and §3.1's low-rank matrix–vector reformulation); experiments skimmed. Nothing
implemented. The HSMM-as-discretiser argument and the link to Rohrmeier are my inferences, not
claims the authors make.
