<!--
DRAFT for Kim's read — team blog post, week of 2026-07-06..07-12 (Saturday ritual).
Led by WINTERMUTE. NOT published. Redaction: science open (configs, hyperparams,
metrics, methods, findings); NO checkpoint filenames, absolute paths, infra addresses,
credentials. Commercial-corpus policy: describe methods/findings on the research corpus;
no weights published, no naming commercial tracks as distributable training data.
Voice aimed at Kim's — first person, builder-documenting-from-scratch, honest about
failures, "numbers are instruments, ears are the verdict." Edit freely.
-->

# A week of looking inside the model

Most of this week was spent on one question in different disguises: not *can* the model make a sound, but *can I reach in and change one specific thing about it* — the mood, the density, the darkness — without breaking everything else. The short answer turned out to be "yes, for about a third of the things you'd want to control, and the failures are as interesting as the wins."

## The headline: steering the model with a single direction, no training

Here's the result I keep coming back to. Take 150 short clips, each labelled for a mood. Average the model's internal activations for the "dark" clips, subtract the average for the rest, and you get a single direction vector — a "dark" arrow in the model's head. Add that arrow back in at two specific mid-network blocks during generation, at the same seed and prompt as a plain baseline, and the output comes out **measurably darker** — 19× on a closed-loop meter, with no training whatsoever. Turn the knob too far and it collapses into buzz; that breakdown is itself instructive, a clean read on how much you can push before you leave the region the model actually knows.

What makes this more than a party trick is *where* the arrow goes in. Three completely different methods this week all pointed at the same small band of mid-network blocks as the place where these high-level concepts live: a causal "patch one block and measure the damage" sweep, an external interpretability method from a recent paper, and the mood-probe approach above. Three independent roads, same address. When methods that share no machinery agree, you start to believe the map.

## Verifying other people's research (and it held up)

A quiet theme this week was checking published claims against our own stack, and mostly finding them true:

- A recent benchmark argued that for this kind of steering, **simple supervised methods beat the fancier sparse-autoencoder approach**. We took the hint and skipped the sparse-autoencoder training entirely — the simple difference-of-averages direction did the job.
- A paper on a different music model reported that only **15–35% of concepts are actually steerable** even when they look separable. Ours landed right in that range: of three moods we tried, one worked cleanly, one partially, one not at all.
- A third paper claimed the steering *direction* stays stable across the whole generation process even as its *effect* changes. That replicated on our model almost exactly.

There's something satisfying about a week where the literature and your own measurements shake hands.

## The failures, which are the good part

**"Relaxing" refused to steer** — and it had the *best* separability score of any mood we tested. That's the finding, not a footnote: being able to *detect* a concept in the model's activations is not the same as being able to *push* the model along it. Detection and control are different problems, and this week gave us a concrete, audible example of the gap.

**Trying to hold a single number flat produced only buzz.** When we asked a control head to pin one scalar attribute at a constant value, every setting failed the quality gates — the output degraded into noise no matter how gently we turned the knob. We had two theories for why, and killed both in one evening at about ten minutes each, because we'd wired up automatic quality meters (the same enjoyment/production/zero-crossing checks) alongside the target meter. Cheap science: the gates did exactly their job, telling us the steering direction was right but the audio was wrong before we wasted a night on it.

**Which checkpoint is "the good one" is still contested.** For onset-density control, the metric winner and the ear winner disagree, and we're settling it the honest way — a proper head-to-head re-metering rather than trusting one number.

## Surprises

A speech-to-notes transcription model pulled a **near-complete bassline out of a full mix** — every instrument playing at once — but *failed* on the isolated bass stem alone. The mix gave it context the naked stem couldn't. Kim's hunch about how these tracks sustain notes was confirmed across the whole corpus, with the twist that the sparse, ambient tracks behave differently from the dense ones. Context, again.

On the "make it play forever" front: a technique from the video-generation world that was supposed to fix a looping failure turned out to be **null on our setup by construction** — our generation resets its internal clock each window, so the specific problem the fix targets never arises. Worth knowing before spending a day on it; the real lever for our looping is on the conditioning side, which is exactly where the hand-written "arc" of changing prompts has been paying off.

And a small one that Kim spotted by eyeballing a sorted table: asking for ever-denser rhythm hits a **hard ceiling** at around a 16th-note grid for the tempo. Push past it and the extra energy rearranges timing and timbre instead of adding notes. That's the base model's musical prior showing through, not a control failure.

## The thing that lets you actually listen

None of the above matters if you can't hear it, so a lot of the week went into a single big listening surface: **every model we've trained, in one place**, side by side — pick a model, pick a checkpoint, sweep the settings, and A/B the exact same moment across any of them on a shared playhead. Eight thousand clips, self-updating as new renders land. The point isn't the number; it's that the whole zoo is finally auditable by ear in one sitting instead of scattered across a hundred folders.

## What we learned about *how* we work

Two of the week's best catches weren't results at all. One was a provenance bug caught *before* it went public — a stale line in a metadata file claimed the method did something the code didn't, and flagging it turned a potential published-wrong-claim into a one-line fix. The other was an ear-verdict quietly overruling a significant metric win. The pattern holds: the numbers are instruments, the ears are the verdict, and writing down *why* you believe something beats writing down a clean-sounding story.

Open questions carried into next week: pushing genuinely out-of-distribution styles (which may need full fine-tuning rather than adapters — you can't bolt a new world onto a frozen one); giving the time-varying attributes their own steering treatment now that we know the flat-target approach buzzes; and settling the onset-control head-to-head by ear on sparse vs dense requests separately, since both verdicts may be true on different ranges.

A good week. More of it was falsifying our own guesses than confirming them, which is usually the sign the guesses are getting sharper.
