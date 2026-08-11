<!--
DRAFT for Kim's read — team blog post, week of 2026-07-20..07-26 (W30, Saturday ritual).
Drafted by THE-FINN. NOT published — W deploys after leak-scan. Redaction: science open
(configs, hyperparams, metrics, methods, findings); NO checkpoint filenames, absolute paths,
infra addresses, credentials. Commercial-corpus policy: describe methods/findings on the
research corpus; no weights published, no naming commercial tracks or corpus scale as
distributable training data. Voice: first person, builder-documenting-from-scratch, honest
about failures, "numbers are instruments, ears are the verdict." Edit freely.
-->

# The week we built the ruler, not the thing it measures

Some weeks you ship a result. This was the other kind — the week you spend making sure that when the result *does* land, you'll be able to tell whether it's real. We rendered the candidate for our best recipe, sharpened two research questions down to something answerable, caught our own tools lying to us, and — twice — crashed the machine hard enough to have to rebuild how it protects itself. The payoff renders are queued for next week. This week was about earning the right to trust them.

## The question underneath: can you teach a frozen model to follow a tune?

Most of the week was one question in two halves. First: *can the model even represent a melody internally?* We probed its guts with synthesized phrases played across many different instruments and found something clean — the model does carry melodic **contour** (the up-and-down shape, the intervals), and it carries it *robustly across timbres*: the same tune on a piano and on a string pad reads as the same shape. Absolute pitch is far more fragile; contour is the durable thing.

Then the half that mattered: *reading a thing is not the same as controlling it.* A lightweight probe that tries to **read** the melody back out of the model hits a hard ceiling — about 0.27 on our accuracy meter, everywhere we looked, at every depth. For a while that looked like bad news. It isn't: the ceiling bounds the **readout**, not the model. The fix is to stop asking the model to *report* its melody and instead teach it to *use* a melody signal we hand it — conditioning, not decoding. That build started this week. Whether it actually steers is a next-week question, and we're holding the champagne until the meters and the ear both sign off.

There's a companion finding here that saved us from a whole dead branch: melody has to be learned **on real mixes, not clean solo stems**. A reader trained on isolated instruments falls apart the moment two voices play at once, and offbeat hi-hats — the signature of the exact genre we care about — are the worst offenders. The naive plan (train on clean stems, it'll be easier) was quietly the wrong plan. Better to find that out from a probe than from a week of training.

## The winning recipe, rendered — verdict pending

The candidate for our best training recipe got rendered this week across its family of variants. No full scorecard yet — that's the job that's running now — but there's an early read from the only meter that ultimately counts. Listening to the higher-precision (fp32) versions against their cheaper (bf16) twins, Kim's verdict: the fp32 arms sound **cleaner** — better separation between instruments, less noise in the high end — occasionally with a touch less punch, though that may just be them being more faithful to the source rather than a real loss. Preliminary, deliberately. The proper per-setting head-to-head is next week's work, and one specific thing we're listening for — a stereo-image and punch difference Kim caught by ear between two variants — is exactly the axis a careless metric run would be blind to. So we're making sure the meters expose it before we trust any ranking.

## Our own meter was scoring static as success

The best catch of the week was a piece of self-doubt that turned out to be justified. When you build a "does this knob work?" meter for steering the model, the obvious design measures *how much the target feature moved*. The problem: a broken knob that turns the output into **static buzz** also moves that meter — noise is, by the numbers, extremely "bright" and "busy." So a head that does nothing useful can score as "working."

The fix, now mandatory for every steering claim we make: before any head is allowed to be called *working*, every steered clip has to be checked against its **own** unsteered baseline for the fingerprints of buzz — whitening, high-frequency blowout, noise, loss of beat. Dead knobs and buzzing knobs are different failures (a dead knob does nothing and passes; a buzzing knob does damage and used to pass too), and a real control has to clear both screens. The first time we ran the stricter gate on an existing sweep, it caught six "working" results that the old gate had waved through. Six claims we'd have half-believed, now correctly labelled.

## A finding that is not a product

We spent real effort pulling dozens of style adapters out of a trained model by decomposition — the idea being a cheap way to mint many steerable variants from one expensive run. The honest conclusion is that the resulting board is a **finding, not a shipping list**: it tells us something true about how style is distributed in the weights, but the extracted adapters don't hold up as usable models. Naming that difference out loud — "this is a result about the model, not a set of things to release" — is the kind of discipline that keeps a research log trustworthy. Not every interesting thing is a deliverable.

## The week we broke our own machine (twice)

The unglamorous headline: the box hard-crashed twice, because two heavy GPU jobs ended up running at once when our lock was supposed to prevent exactly that. The rest of the week went into making the lock actually trustworthy — teaching it to tell a genuinely-running job from a crashed one, to reclaim a lock whose owner has died, and to shout loudly when two jobs try to run under the same identity (which, it turned out, was the real hole — the lock happily let one worker collide with itself). Nobody enjoys a week of fixing their own plumbing, but "the job said it finished" is a *claim*, and this week hammered home — again — that a claim is not evidence. The machine is meaningfully harder to crash now than it was on Monday.

## Carried into next week

- The winning family gets its full per-setting scorecard, with the stereo/punch axis exposed, so the ear-verdict and the numbers can be checked against each other rather than one trusted blind.
- The melody **conditioner** faces its first real test: does handing the model a contour actually bend the output toward it, or does it just pass the buzz gate by doing nothing? Both are informative; only one is the goal.
- Two independent quality columns — does it hold its mood, does it hold its genre — get run on that test, so "it steers" has to survive more than one definition of success before it's called a win.

A quieter week than most, and a good one. More ruler-building than result-shipping — but the results are only worth having if the ruler is honest, and this week the ruler got a lot more honest.
