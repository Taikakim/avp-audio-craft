<!-- Combined catch-up week-in-review DRAFT (covers 2026-09-25 through 2026-11-01, five and a half
weeks) — written by THE-FINN 2026-11-02 as part of the weekly routine. Review: Kim's eye first, then
WINTERMUTE. Publish: WINTERMUTE via publish_blog.py, only after that review. What is live was read
from the server directly and confirmed by WINTERMUTE the same evening.
NOTES FOR THE REVIEWER, delete before publishing:
1. Two earlier drafts were never published (2026-08-28 and 2026-09-24), and neither was the Synth-JEPA
   post (2026-10-19, awaits its fact review). This post does not fold them in. Decide: publish, merge or drop.
2. The sentence "First listens are encouraging" rests on two recorded verdicts: a first-pass one
   relayed by WINTERMUTE, and a 2026-10-29 one that entered EXPERIMENTS through an ANTIGRAVITY commit
   (WINTERMUTE believed that page was still unheard). Please confirm, or cut the sentence.
3. The drum-separation numbers are the collaborator's own and not independently reviewed; the post says so.
   Its synth-inversion V8 work is staged, not live, so it gets one unquantified sentence.
4. The planned public release and its prior-art purpose are deliberately NOT mentioned. Your call. -->

# The One Where We Were Asking for the Wrong Chord

Five and a half weeks this time, one of them almost silent. The thing that kept coming back was not a
bug so much as a kind of embarrassment: a number that looked fine, attached to a question nobody had
meant to ask.

## Nine semitones

We steer generation with small trained "heads" that read the model's intermediate state and nudge it
toward a target, such as a chord. One of ours, a pitch-class head, had been written off months ago as
dead: it didn't seem to follow chord requests at all.

It turns out we were asking it for the wrong chords. The audio library that produced its training data
numbers pitch classes starting from A by default, and our targets started from C. Every request was
nine semitones off, so every earlier test, including the one that pronounced it dead, measured how well
it obeyed an instruction we hadn't meant to give. With the targets rotated, it follows transpositions
and lands on the chord requested.

The same stretch brought a retrained version of our other chroma head, which now steers chords about as
far at a guidance gain of 512 as the old one did at 8192, and passes our automatic check for clips
falling apart all the way up to 8192. Making it deeper or wider didn't take it any further, and
validation loss once again failed to predict which head steers best. First listens are encouraging, but
they are early, and the measurements are what we would stand behind today.

## "Clean" meant "barely changed"

We published a page showing how far a set of rhythm-density heads could go before quality broke down.
Within hours we had to correct it. Up to that limit, the heads moved density by only 2 to 2.8 onsets per
second, where a different method, a trained FiLM adapter, spans 2.3 to 11.2. The clips passed the check
because almost nothing had happened to them. The rule we took from it: report the size of the effect
against a reference, not just a pass.

Looking for the cause, we found that our guidance weighting gives the first 20% of sampling steps about
0.2% of the budget, so it mostly acts after rhythm is already decided. Flattening it helped, about 1.45
times the range, which is still about half of what the adapter does, and by ear the original setting
stayed cleanest. What worked better was using both methods together: 5.5 onsets per second of range at
a little over half the style drift of the adapter alone at 4.4. A long crossfade from one into the other
went further still on drift, 3.3 at 0.10 against 4.1 at 0.17. These are measured, not yet settled by ear.

## The reward that got better while the sound didn't

Our synth-inversion work had a bad few weeks, in instructive ways. The synth we render training data with
keeps hidden chorus and delay state between renders, so one run had trained on subtly altered audio. We
fixed that, and then found the delay had never really been off: setting its mix to zero leaves it sounding,
and only switching the effect slot off silences it.

Clean data took accuracy on held-out synth presets to about 80%. Yet on 24 real bass phrases, the old
model still scored best. The bug was real, but the gap between real and synthetic audio was the actual
constraint. Then a preference-optimization loop kept improving its rewarded metric on synthetic notes,
round after round, while the metric that tracks listening on real stems rose and then fell below where it
started. More rounds were optimizing a reward that doesn't follow the ear.

## Things we took back

We withdrew a ranking of optimizer features after finding that the number of data-loading workers alone
moves a run by about 0.004, twenty times the seed spread we had been using as our noise floor. A batch-size
conclusion turned out to be an artefact of unequal step counts. A morph conditioner, tested with a meter
that had first passed a positive control, showed no detectable melodic contour following at all. An
intermittent fault in one way of rendering with a live adapter, returning garbage on identical inputs,
survived new firmware and a new compute stack, and we still don't have a local fix.

Meanwhile a DJ-mix audition found that every one of 39 transitions replayed the incoming clip from about
ten seconds back. Our corruption scans could not see it, because nothing was corrupted. Ears caught it, and
the rebuild now continues from the exact source position on all 34 splices checked. Three versions of the
newer mix are up on one comparison page.

## What's new to read and hear

The [Muon survival guide](2026-10-21-muon-survival-guide.html) went up, with an in-page help pane, 54
glossary entries and six animations, and with its untested claims marked as untested. A collaborator working
outside the team published drum-separation boards: by their own numbers, a NorMuon arm with Schedule-Free
beat the AdamW control in half the steps, a plain Muon arm diverged at step 399, and one larger arm was
striking at step 1000 before a loss spike undid it. We haven't independently reviewed those, or their newer
synth-inversion pipeline, which isn't public yet.

Looking back, very little of this was found by running something new. Most of it came from going back to a
result we had already accepted and asking what question it had actually answered. Next we want the steering
we can now measure to survive a proper listen.
