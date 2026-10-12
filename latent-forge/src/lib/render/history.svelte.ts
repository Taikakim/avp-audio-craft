// Every render of the session, in the order they finished (spec §4.5: the HISTORY select shows
// them newest FIRST, but storage keeps newest LAST so an index stays valid as more arrive -- a
// newest-first array would renumber every entry on every render, and `mixdown`/`preview` are
// indexes that ProjectV2 persists).
//
// This store holds NO audio and no settings. It holds refs. §4.5: "Loading from HISTORY loads
// audio only. The previewed render changes; the pane's settings do not" (and §10 X15). Settings
// come back only through USE SETTINGS, which reads the job record's `payload` -- hence jobRecord().

import { forgeApi } from "../forge/api";
import type { AudioRef, JobRecord, RenderHistoryEntry } from "../forge/types";

function isIndexInto<T>(list: T[], i: number | null): boolean {
  return i !== null && Number.isInteger(i) && i >= 0 && i < list.length;
}

export class HistoryStore {
  /** Newest LAST. The UI reverses for display; the indexes below address THIS order. */
  renders = $state<RenderHistoryEntry[]>([]);

  /** Index into `renders` -- always the newest `kind: "mix"` (§7.1: "always the latest"). */
  mixdown = $state<number | null>(null);

  /** Index into `renders` -- what the preview container is showing. */
  preview = $state<number | null>(null);

  /**
   * Svelte 5 proxy rule (HANDOUT): pushing into a `$state` array deep-proxies the object, so the
   * literal the caller built is a dead handle. Return the array's live element -- Task 1's
   * `jobs.submit` hands this straight on to a caller that scrubs and drags it.
   */
  add(e: RenderHistoryEntry): RenderHistoryEntry {
    this.renders.push(e);
    const index = this.renders.length - 1;
    this.preview = index;                       // §4.5: "A finished render lands here"
    if (e.kind === "mix") this.mixdown = index;  // a later gen/a2a must not steal the slot
    return this.renders[index];
  }

  /** Audio only. This method sets exactly one field on purpose (§4.5, §10 X15). */
  select(index: number): void {
    if (!isIndexInto(this.renders, index)) return;
    this.preview = index;
  }

  /** `job_id` here is the RESULT's output-dir id (`result.job_id`), which is what /forge/audio and
   *  /audio/{job_id}/{file} resolve -- not the `forge-…` queue id. */
  refOf(e: RenderHistoryEntry): AudioRef {
    return { kind: "render", job_id: e.job_id, file: e.file };
  }

  /** The queue id is what GET /forge/jobs/{id} keys on; `payload` is what USE SETTINGS reads
   *  (spec §7.2: "Every job record keeps the exact payload it ran with"). */
  jobRecord(e: RenderHistoryEntry): Promise<JobRecord> {
    return forgeApi.job(e.forge_job_id);
  }

  clear(): void {
    this.renders = [];
    this.mixdown = null;
    this.preview = null;
  }

  /** Called by applyProject. An index a saved project cannot address becomes null rather than
   *  pointing the MIXDOWN slot or the preview container at nothing. */
  restore(renders: RenderHistoryEntry[], mixdown: number | null, preview: number | null): void {
    this.renders = structuredClone(renders);
    this.mixdown = isIndexInto(this.renders, mixdown) ? mixdown : null;
    this.preview = isIndexInto(this.renders, preview) ? preview : null;
  }
}

export const history = new HistoryStore();
