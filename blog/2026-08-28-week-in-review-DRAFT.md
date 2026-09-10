<!-- Combined catch-up week-in-review DRAFT (covers 2026-08-09 through 2026-08-28) — written
by THE-FINN 2026-08-28. Review: WINTERMUTE (+ Kim's eye on the framing). Publish: WINTERMUTE
via publish_blog.py (re-runs redact() as a belt-and-suspenders scan). Written source-clean: no
checkpoint filenames, paths, corpus names, artist/track names, or internal ids. Title uses
Kim's preferred "The One With…" headline. Note: this post covers roughly three weeks in one
go, because the middle of that stretch was quiet for a plain reason (see the close) and three
thin posts would have been worse than one honest one. -->

# The One Where We Were Training Alone the Whole Time

For weeks, several of our biggest training runs had been launched across eight GPUs at once, and we believed — because the logs looked fine and nothing crashed — that all eight were working together on one model, learning eight times faster than a single card could. They were not. Every one of those eight processes had quietly decided it was the *only* one in the room, training its own separate copy of the model from scratch, ignoring the other seven entirely. Nothing errored. Nothing timed out. It just quietly cost us eight times the compute for what should have been one coordinated run.

## How we found out

The tell, once we knew to look for it, was almost embarrassingly simple: each of the eight processes should log its own identity — "I am worker 1 of 8," "I am worker 2 of 8," and so on. Instead, every single one of them logged "I am worker 0." All eight thought they were in charge and none of them were talking to each other. We wrote the one-line check that catches this and swept every training script we had. A handful were still running on the broken launch pattern, including one on the critical path for our biggest model. We fixed the pattern, verified the fix the same rigorous way — read the actual logs, don't trust that it "should" work now — and confirmed real coordinated training for the first time.

The silver lining: nothing was wasted. Eight independent copies of the same recipe, started from the same random seed, is exactly the raw material for an ensemble — a technique where you average several trained models together and often get something better than any one of them. We're using the accidental ensembles for exactly that now.

## The captions were lying too

Around the same time, we discovered our text descriptions for one of our music archives had been quietly wrong in three separate ways. A model that turns descriptions into short captions had, in one stage, been fed the audio *file's folder name* instead of an actual description of the sound — so it dutifully "described" music using only what a folder happened to be called. Separately, a different captioning step was never told what genre of music it was even listening to, so — faced with a decades-deep archive of psychedelic trance — it guessed "techno" for most of it. And a third archive's missing captions had been silently backfilled by borrowing the description of a *different, unrelated song* that happened to sound similar on paper.

Each of these bugs passed every check we already had, because each check answered a slightly different question than the one that actually mattered — is the caption internally consistent, versus is it actually true. We fixed all three, re-ran the affected captioning at scale, and along the way discovered something useful about being smart with a deadline: spreading the same total amount of work across many small, short jobs instead of one long one finishes in a fraction of the wall-clock time for the identical total cost. A caption run that would have taken most of a day took about an hour once we stopped trying to do it serially.

## Finding out we'd been fooling ourselves in smaller ways too

A few other findings landed in the same spirit. One of our automated quality scores turned out to have essentially no relationship with what a real listener actually thinks of a clip — a much simpler measurement tracked human judgment far better, and we're retiring the old one. And in a genuinely funny catch: one of our trained models has a special "trigger word" tied to its own project name, and it turns out every single evaluation of that trigger, for weeks, had been spelled slightly differently than the one the model actually learned — a missing accent mark. The model had never once been asked the word it actually knew.

## Then we turned inward

With that housekeeping done, the last stretch of work turned toward the tools we use to actually listen to and steer these models — a control panel for our melody/rhythm/timbre "knobs" that now shows honest, per-model ranges instead of one guessed default; the ability to save and reload a full generation setup as a named preset; a batch-sweep mode that can render a whole grid of variations unattended and resume if interrupted; and the ability to keep several fine-tuned variants loaded in memory at once and instantly A/B between them. Small, but the kind of thing that changes how much you can explore in an evening.

## The quiet part

Then things went quiet for about a week. Plainly: we ran through this month's compute/tooling budget earlier than planned, so work slowed to a near-halt while that reset. Nobody was stuck on a hard problem — the lights were just dimmed for a bit. We're back to a normal pace now, just leaner about when we reach for the expensive tools versus doing things by hand.

## What's next

Our cluster allocation for this research phase ended this week, so anything needing serious computing power now waits for the next one; everything we can do locally continues without interruption. The next big push, once we're back on the cluster, is a genuinely interesting one: taking every specialized control we've trained — melody, rhythm, timbre, and a few others — and testing what happens when you hand a model a real piece of music, tell it to change almost everything about it, and see whether those controls can hold onto the parts that were supposed to survive. We'll report back on what we find.
