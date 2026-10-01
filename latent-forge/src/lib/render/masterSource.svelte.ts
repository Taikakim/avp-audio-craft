import { forgeApi } from "../forge/api";
import type { RenderHistoryEntry } from "../forge/types";
import { history } from "./history.svelte";

export type MasterSource = "preview" | "mixdown";

/** M5 wrote almost this sentence as the placeholder title on the disabled button; it is kept, minus
 *  the promise about M9, because the operator's question is "why can't I press this". */
export const MIXDOWN_UNAVAILABLE_HINT = "nothing has been committed yet";

class MasterSourceStore {
  /** What the operator chose. Never rewritten by anything but the operator: a session load that has
   *  no mix must not silently un-choose MIXDOWN, and an $effect that did would be writing state
   *  another derivation reads. `effective` does the gating instead. */
  value = $state<MasterSource>("preview");

  get entry(): RenderHistoryEntry | null {
    return history.mixdown === null ? null : history.renders[history.mixdown] ?? null;
  }

  get available(): boolean {
    return this.entry !== null;
  }

  /** What is actually played and drawn. */
  get effective(): MasterSource {
    return this.value === "mixdown" && this.available ? "mixdown" : "preview";
  }

  get url(): string | null {
    const e = this.entry;
    return e === null ? null : forgeApi.audioUrl(history.refOf(e));
  }

  get durSec(): number {
    return this.entry?.dur_sec ?? 0;
  }

  set(v: MasterSource): void {
    this.value = v;
  }
}

export const masterSource = new MasterSourceStore();
