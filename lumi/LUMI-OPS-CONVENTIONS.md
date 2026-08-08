# LUMI ops conventions (for agents crafting commands Kim pastes)

Agents never ssh to LUMI — Kim's key needs an interactive passphrase — so every LUMI command we
produce is pasted by a human into a live shell. That imposes rules we kept violating:

1. **SINGLE LINE, COPY-PASTEABLE. No multi-line blocks** (Kim direct, 2026-08-09). A `for` loop
   split across lines with `\` continuations breaks on paste: the continuation eats the next
   token, the shell drops into `>` and the whole thing has to be Ctrl-C'd. If it needs a loop,
   write it as ONE line with `;` separators.
2. **NEVER `du -sh` a Lustre directory to answer a counting question.** `du` stats every file;
   on a 3.5 GB render dir it hangs long enough that Kim Ctrl-C's it. Use `ls DIR | wc -l` (no
   stat) when you want a count, and only reach for `du` when the answer really is bytes.
3. **One question per command.** A command that both counts and sizes fails slowly and tells you
   nothing when interrupted.
4. **`sacct` for job outcomes, artifacts for truth.** `squeue` empty means *terminated*, not
   *succeeded*: `sacct -X -u $USER --starttime now-10days --format=JobID,JobName%24,State,ExitCode,Elapsed,End%19`
   distinguishes COMPLETED / FAILED / TIMEOUT / CANCELLED. Then count the files — a COMPLETED
   job with zero output and a FAILED job that ran 9 seconds look identical from the filesystem.

Verified example of why 4 matters: on 2026-08-09 `sa3_aug8_render` (20792735) was believed
COMPLETED with clips on scratch and was recorded that way in the open-tails audit. `sacct` shows
**FAILED, ExitCode 2:0, elapsed 00:00:09** — there were never any clips to pull.
