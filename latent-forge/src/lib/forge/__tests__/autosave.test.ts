import { afterEach, describe, expect, it, vi } from "vitest";
import { createAutosave, createSnapshotAutosave } from "../autosave";

afterEach(() => vi.useRealTimers());

describe("createAutosave: 2s after the last change (spec §9.2)", () => {
  it("fires once, 2000ms after trigger()", () => {
    vi.useFakeTimers();
    const save = vi.fn();
    const a = createAutosave(save);
    a.trigger();
    vi.advanceTimersByTime(1999);
    expect(save).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(save).toHaveBeenCalledTimes(1);
  });

  it("resets the timer on every new trigger, so rapid edits save once", () => {
    vi.useFakeTimers();
    const save = vi.fn();
    const a = createAutosave(save);
    a.trigger();
    vi.advanceTimersByTime(1000);
    a.trigger();
    vi.advanceTimersByTime(1999);
    expect(save).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(save).toHaveBeenCalledTimes(1);
  });

  it("cancel() stops a pending save", () => {
    vi.useFakeTimers();
    const save = vi.fn();
    const a = createAutosave(save);
    a.trigger();
    a.cancel();
    vi.advanceTimersByTime(5000);
    expect(save).not.toHaveBeenCalled();
  });

  it("honours a custom delay", () => {
    vi.useFakeTimers();
    const save = vi.fn();
    const a = createAutosave(save, 500);
    a.trigger();
    vi.advanceTimersByTime(500);
    expect(save).toHaveBeenCalledTimes(1);
  });
});

describe("createSnapshotAutosave: never writes a session it did not load or save", () => {
  it("does nothing before arm() -- a fresh mount observing the blank arrangement never PUTs", () => {
    vi.useFakeTimers();
    const save = vi.fn();
    const a = createSnapshotAutosave(save);
    // App's effect runs at mount with whatever `session` is; even a non-empty name must not save
    a.observe("dub-sketch", '{"clips":[]}');
    a.observe("dub-sketch", '{"clips":[1]}');
    vi.advanceTimersByTime(10_000);
    expect(save).not.toHaveBeenCalled();
  });

  it("after arm(), saves a CHANGED snapshot once, 2s later, under the armed name -- and never an unchanged one", () => {
    vi.useFakeTimers();
    const save = vi.fn();
    const a = createSnapshotAutosave(save);
    a.arm("take1", "A");
    a.observe("take1", "A");            // the effect re-running on the state that was just loaded
    vi.advanceTimersByTime(5000);
    expect(save).not.toHaveBeenCalled();
    a.observe("take1", "B");
    vi.advanceTimersByTime(1999);
    expect(save).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(save).toHaveBeenCalledWith("take1", "B");
    a.observe("take1", "B");            // B is now the baseline
    a.observe("other", "C");            // not the armed name
    vi.advanceTimersByTime(5000);
    expect(save).toHaveBeenCalledTimes(1);
  });

  it("arming a different session first flushes the previous session's pending save under ITS name", () => {
    vi.useFakeTimers();
    const save = vi.fn();
    const a = createSnapshotAutosave(save);
    a.arm("take1", "A");
    a.observe("take1", "A-edited");     // pending, not yet due
    a.arm("take2", "Z");                // user loaded another session within the 2s
    expect(save).toHaveBeenCalledWith("take1", "A-edited");
    vi.advanceTimersByTime(5000);
    expect(save).toHaveBeenCalledTimes(1); // nothing written to take2, which did not change
  });

  it("a failed save is not lost: the next observe re-queues it, and arming another session flushes it (critic pass 3 #5)", async () => {
    vi.useFakeTimers();
    const first = deferred<unknown>();
    const second = deferred<unknown>();
    const save = vi.fn<(name: string, snapshot: string) => Promise<unknown>>()
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)
      .mockResolvedValue({ ok: true });
    const a = createSnapshotAutosave(save);
    a.arm("take1", "A");
    a.observe("take1", "B");
    vi.advanceTimersByTime(2000);
    first.reject(new Error("503"));
    await first.promise.catch(() => {});   // runs after autosave's own rejection handler
    a.observe("take1", "B");               // the effect re-running on unchanged stores: B never landed
    vi.advanceTimersByTime(2000);
    expect(save).toHaveBeenCalledTimes(2);
    expect(save.mock.calls[1]).toEqual(["take1", "B"]);
    second.reject(new Error("503"));
    await second.promise.catch(() => {});
    a.arm("take2", "Z");                   // the user loads another session: step 4's flush retries B
    expect(save).toHaveBeenCalledTimes(3);
    expect(save.mock.calls[2]).toEqual(["take1", "B"]);
  });
});

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}
