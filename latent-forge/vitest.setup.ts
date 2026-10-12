// jsdom implements no Web Audio API at all. `lib/store.svelte.ts`'s ProjectStore
// singleton constructs a `Transport` (Web Audio playback engine) eagerly, as a
// field initializer, so any test that merely IMPORTS a component that imports
// the store -- render or not, playback or not -- hits `new AudioContext()` and
// throws `ReferenceError: AudioContext is not defined`.
//
// This is a jsdom gap, not app behaviour: no test here exercises real audio
// playback, so a no-op stub changes nothing any test asserts. Scoped to jsdom
// only (`typeof window !== "undefined"`) so the faster node-environment test
// files are untouched.
if (typeof window !== "undefined" && typeof (globalThis as { AudioContext?: unknown }).AudioContext === "undefined") {
  class FakeAudioNode {
    connect(): void {}
    disconnect(): void {}
  }
  class FakeAudioContext {
    readonly destination = new FakeAudioNode();
    readonly currentTime = 0;
    readonly sampleRate = 44100;
    createGain(): FakeAudioNode {
      return new FakeAudioNode();
    }
    createBufferSource(): FakeAudioNode & { start(): void; stop(): void; buffer: unknown } {
      return Object.assign(new FakeAudioNode(), { start(): void {}, stop(): void {}, buffer: null });
    }
    decodeAudioData(): Promise<never> {
      return Promise.reject(new Error("decodeAudioData is not implemented in the jsdom test stub"));
    }
    close(): Promise<void> {
      return Promise.resolve();
    }
  }
  (globalThis as unknown as { AudioContext: unknown }).AudioContext = FakeAudioContext;
}
