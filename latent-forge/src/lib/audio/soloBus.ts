// Spec §4.5: "Preview playback is independent of the timeline transport; starting one stops the
// other." Neither store can own that rule -- previewPlayer imports playback or playback imports
// previewPlayer, and either way it is a cycle. A registry owns it instead, which also means a third
// audio source (M10's statistics auditioning, say) joins without touching either store.
//
// Deliberately not reactive: nothing renders from this, and a $state Map would make every stop
// callback a proxied function for no gain.

export const AUDIO_SOURCE_TIMELINE = "timeline";
export const AUDIO_SOURCE_PREVIEW = "preview";

const sources = new Map<string, () => void>();

/** Idempotent: re-registering the same id replaces the callback, so HMR does not leave a stale one. */
export function registerAudioSource(id: string, stop: () => void): void {
  sources.set(id, stop);
}

/** Stops every registered source except `id`. Safe to call when `id` is not registered. */
export function takeAudio(id: string): void {
  for (const [key, stop] of sources) {
    if (key !== id) stop();
  }
}
