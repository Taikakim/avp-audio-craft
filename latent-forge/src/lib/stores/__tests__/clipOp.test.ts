import { beforeEach, describe, expect, it } from "vitest";
import type { AudioRef } from "../../forge/types";
import { CLIP_OPS } from "../../forge/types";
import { CLIP_OPS as TARGET_BAR_CLIP_OPS } from "../../../ui/prompt/targetBar";
import { arrangement } from "../arrangement.svelte";

const REF: AudioRef = { kind: "upload", sha256: "b".repeat(64) };

beforeEach(() => {
  for (const c of [...arrangement.clips]) arrangement.removeClip(c.id);
});

describe("ForgeClip.op — §7.1 row 3's OP, in M8's own wire vocabulary", () => {
  it("a new clip has no op, so §7.1's `turn A2A on or choose an op` is reachable", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    expect(c.op).toBeNull();
  });

  it("setClipOp writes through the live proxy, not a dead handle ($state rule)", () => {
    const c = arrangement.addClip({ lane: 0, startSec: 0, durSec: 4, audio: REF });
    arrangement.setClipOp(c.id, "bend");
    expect(arrangement.clips[0].op).toBe("bend");
    expect(c.op).toBe("bend");
  });

  it("every op is a JobOp the server's POST /forge/jobs already accepts (no translation)", () => {
    expect([...CLIP_OPS]).toEqual(["generate", "decode", "longform", "bend"]);
    // One array, not two: M4 T8's `targetBar.ts` re-exports this one, so the OP select and
    // `validateProjectV2`'s `isClipOp` cannot drift apart.
    expect(TARGET_BAR_CLIP_OPS).toBe(CLIP_OPS);
  });
});
