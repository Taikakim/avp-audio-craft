// Spec §9.2: "Autosave to the current session name 2 s after the last change."
// Timer-owning, deliberately not a $effect itself, so it is testable with
// vi.useFakeTimers() without mounting anything.
export function createAutosave(save: () => void, delayMs = 2000): { trigger(): void; cancel(): void } {
  let handle: ReturnType<typeof setTimeout> | null = null;
  return {
    trigger() {
      if (handle !== null) clearTimeout(handle);
      handle = setTimeout(() => {
        handle = null;
        save();
      }, delayMs);
    },
    cancel() {
      if (handle !== null) {
        clearTimeout(handle);
        handle = null;
      }
    },
  };
}

export interface SnapshotAutosave {
  /** A session was just loaded or explicitly saved as `snapshot`: start autosaving `name`.
   *  An empty name disarms. A pending save for a DIFFERENT name is flushed first, under that name. */
  arm(name: string, snapshot: string): void;
  /** Called by App's $effect on every change. Saves nothing until `name` is the armed session,
   *  and nothing when `snapshot` equals the last armed/saved one. */
  observe(name: string, snapshot: string): void;
  cancel(): void;
}

/**
 * The session autosave. Three guarantees the bare debounce cannot give on its own:
 *  1. a tab that has not loaded or saved a session never writes one -- the launch arrangement is
 *     blank, and PUTting it over a listed session would destroy that session;
 *  2. a re-run of the watching effect that changed nothing saves nothing;
 *  3. a save whose promise rejects is not lost (critic pass 3 #5): it stays pending against the
 *     last snapshot the server confirmed, so the next observe() re-queues it and arming another
 *     session flushes it. No timer is restarted for it, so a server that keeps failing is not
 *     retried in a loop -- the next change, or the next load, retries it.
 */
export function createSnapshotAutosave(
  save: (name: string, snapshot: string) => Promise<unknown> | void,
  delayMs = 2000,
): SnapshotAutosave {
  let armedName = "";
  let baseline = "";
  /** The last snapshot of `armedName` the server is known to hold: armed, or a save that resolved. */
  let confirmed = "";
  let pending: { name: string; snapshot: string } | null = null;

  function write(name: string, snapshot: string): void {
    Promise.resolve(save(name, snapshot)).then(
      () => {
        if (name === armedName) confirmed = snapshot;
      },
      () => {
        // Superseded by a newer save of this name, or by a re-arm: that one carries the state now.
        if (name !== armedName || baseline !== snapshot) return;
        baseline = confirmed;
        if (!pending) pending = { name, snapshot };
      },
    );
  }

  const debounce = createAutosave(() => {
    if (!pending) return;
    const { name, snapshot } = pending;
    pending = null;
    if (name === armedName) baseline = snapshot;
    write(name, snapshot);
  }, delayMs);

  return {
    arm(name, snapshot) {
      if (pending && pending.name !== name) {
        const p = pending;
        pending = null;
        debounce.cancel();
        write(p.name, p.snapshot);   // a failure now is only logged by the caller: the name is disarmed
      }
      armedName = name;
      baseline = snapshot;
      confirmed = snapshot;
    },
    observe(name, snapshot) {
      if (!armedName || name !== armedName) return;
      if (snapshot === baseline) {
        if (pending?.name === name) {
          pending = null;
          debounce.cancel();
        }
        return;
      }
      pending = { name, snapshot };
      debounce.trigger();
    },
    cancel() {
      pending = null;
      debounce.cancel();
    },
  };
}
