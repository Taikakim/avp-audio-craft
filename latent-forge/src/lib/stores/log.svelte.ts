// The TERMINAL tab's backing store (spec §4.5, §6.4, §9.7).
//
// `GET /forge/log?since=<seq>` returns only the lines after the sequence number
// the client already holds, so polling is cheap and no line is drawn twice. The
// client keeps the same 400-line window the server's LOG_RING does.
//
// A dead render server is a normal state on this box (the server is stopped
// whenever the GPU is wanted elsewhere), so a transport failure becomes one red
// line rather than a thrown error, and it is not repeated on every tick.

import { forgeApi } from "../forge/api";

export type LogTone = "text" | "dim" | "accent" | "error";

export interface LogLine {
  seq: number;
  text: string;
  tone: LogTone;
}

/** The server's own log ring (spec §6.4). */
export const LOG_RING = 400;

export function logTone(text: string): LogTone {
  // No leading \b on "error": it must also catch "RuntimeError", where the E is
  // preceded by a word character (Runtime) and so carries no word boundary.
  if (/error|traceback|\bfailed\b|\bexception\b|\brefused\b|\bunreachable\b/i.test(text)) return "error";
  if (text.startsWith("$ ")) return "dim";
  if (/^\s*warn(ing)?\b/i.test(text)) return "accent";
  return "text";
}

class LogStore {
  lines = $state<LogLine[]>([]);
  busy = $state(false);
  seq = $state(0);
  error = $state<string | null>(null);

  #timer: ReturnType<typeof setInterval> | null = null;
  #reported: string | null = null;

  /**
   * Svelte 5 proxy rule: pushing an object into a `$state` array deep-proxies it,
   * so the literal built here is a dead handle. Return the array's live element.
   */
  /**
   * A line the CLIENT produced, not the server. It goes in the same ring TERMINAL renders, at the
   * current cursor -- never past it. `poll()` fetches `forgeApi.log(this.seq)`, i.e. lines SINCE
   * the cursor, so a client line appended at an invented sequence number would skip real server
   * lines forever. This is the same trick poll()'s own failure path already uses. (M9 T5)
   */
  appendLocal(text: string, tone: LogTone = logTone(text)): LogLine {
    return this.append(text, this.seq, tone);
  }

  append(text: string, seq: number, tone: LogTone = logTone(text)): LogLine {
    this.lines.push({ seq, text, tone });
    if (this.lines.length > LOG_RING) this.lines.splice(0, this.lines.length - LOG_RING);
    if (seq > this.seq) this.seq = seq;
    return this.lines[this.lines.length - 1];
  }

  async poll(): Promise<void> {
    try {
      const [log, status] = await Promise.all([forgeApi.log(this.seq), forgeApi.status()]);
      // Trust `since` filtering to reduce payload size, but never trust it to be
      // exact: a misbehaving server (or the dev:mock fixture, which always answers
      // the same fixed lines regardless of `since`) would otherwise re-append
      // already-held lines every tick, producing duplicate seq keys in the
      // keyed {#each} and a growing, repeating TERMINAL. Re-filter client-side.
      for (const l of log.lines) if (l.seq > this.seq) this.append(l.text, l.seq);
      if (log.seq > this.seq) this.seq = log.seq;
      this.busy = status.busy;
      this.error = null;
      this.#reported = null;
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      this.busy = false;
      this.error = message;
      if (this.#reported !== message) {
        this.#reported = message;
        this.append(message, this.seq, "error");
      }
    }
  }

  /** Polled only while the TERMINAL tab is the visible one. */
  start(intervalMs = 1000): void {
    if (this.#timer !== null) return;
    void this.poll();
    this.#timer = setInterval(() => void this.poll(), intervalMs);
  }

  stop(): void {
    if (this.#timer === null) return;
    clearInterval(this.#timer);
    this.#timer = null;
  }

  clear(): void {
    this.lines = [];
    this.seq = 0;
    this.busy = false;
    this.error = null;
    this.#reported = null;
  }
}

export const logStore = new LogStore();
