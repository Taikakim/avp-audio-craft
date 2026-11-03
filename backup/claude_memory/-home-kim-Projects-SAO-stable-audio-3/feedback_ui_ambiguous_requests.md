---
name: feedback-ui-ambiguous-requests
description: "Kim's short UI phrasings (\"hover player\", \"notification when loading\") describe a visibility goal, not necessarily a new interaction trigger — don't infer both from one sentence."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b46bac88-6902-4ad2-a9ea-d4df3a96ae04
---

When Kim asks for a UI feature in one short sentence, separate what he's asking to
be TRUE (visible, working) from HOW to make it true — don't infer a new interaction
trigger just because the feature needs one to exist.

Concrete case (2026-07-20, SAO eval boards / [[latch-sa3-phase1]] context): Kim asked
for "the hover player which shows a notification when it's loading a sound." Read
literally this could mean "hover triggers playback, with a loading notification" —
that's the interpretation I built (`onmouseenter="hoverPlay(this)"` on every grid
cell, autoplaying audio on mouse transit). Kim's actual complaint minutes after
shipping: "the cells should not autoplay on hover, this makes things quite
uncomfortable. And I can't see the hovering player." He meant: playback stays
click-triggered (unchanged); the LOADING FEEDBACK for an existing/imminent play
action should be visible right where you're looking, not tucked in a sticky header
far from the cursor. Two independent misses stacked from one ambiguous sentence —
audio autoplay is not a preview affordance he wanted, and even the harmless half
(the loading indicator) failed because of *placement*, not existence.

**Why:** Kim's phrasing style is dense and assumes the model fills in intent from
context, not from literal parse. On UI/audio features specifically, an interpretation
that adds a new *automatic* side effect (autoplaying sound, sending data, changing
state) from a terse sentence is higher-risk than one that only makes existing
affordances more visible. Audio autoplay is especially costly to get wrong since it's
sensory/uncomfortable, not just visually wrong.

**How to apply:** When a one-line UI ask could be read as either (a) a purely visual/
informational improvement, or (b) that plus a new automatic trigger (autoplay, auto-
submit, auto-navigate), default to (a) and ask before adding (b) — or ship (a) first,
call it out explicitly ("didn't wire hover to autoplay, wanted to check first"), and
let Kim ask for the trigger if he wants it. Also: when placing any kind of status/
feedback indicator (loading, error, progress), put it AT the point of interaction
(on the element itself, e.g. an outline/class), not only in a shared status bar
elsewhere on the page — especially on dense grid layouts where the header can be far
from the cursor.
