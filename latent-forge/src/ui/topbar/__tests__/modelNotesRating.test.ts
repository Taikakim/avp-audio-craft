// @vitest-environment jsdom
// Owner: WINTERMUTE (created 2026-10-14) -- the MODEL NOTES rating row posts only forge_rating
import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import ModelNotes from "../ModelNotes.svelte";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function stubServer(initial: number | null) {
  const posts: unknown[] = [];
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.startsWith("/models/notes")) {
      return new Response(JSON.stringify({
        ok: true, label: "armA", known: true, fields: { purpose: "auto" },
        forge_notes: "", forge_notes_updated: null, forge_rating: initial,
      }));
    }
    const body = JSON.parse(String(init?.body));
    posts.push({ url, body });
    return new Response(JSON.stringify({ ok: true, label: body.label, forge_rating: body.rating }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return posts;
}

describe("MODEL NOTES rating", () => {
  it("saves a click as forge_rating and reports it; clicking it again clears it", async () => {
    const posts = stubServer(null);
    const onrated = vi.fn();
    const { getByTestId } = render(ModelNotes, { props: { label: "armA", onrated } });
    await fireEvent.click(getByTestId("model-notes-toggle"));
    await waitFor(() => expect((getByTestId("model-rating-4") as HTMLButtonElement).disabled).toBe(false));

    await fireEvent.click(getByTestId("model-rating-4"));
    await waitFor(() => expect(onrated).toHaveBeenCalledWith("armA", 4));
    expect(posts).toEqual([{ url: "/models/rating", body: { label: "armA", rating: 4 } }]);
    expect(getByTestId("model-rating-4").classList.contains("on")).toBe(true);

    await fireEvent.click(getByTestId("model-rating-4"));
    await waitFor(() => expect(onrated).toHaveBeenLastCalledWith("armA", null));
    expect(posts[1]).toEqual({ url: "/models/rating", body: { label: "armA", rating: null } });
  });

  it("shows the stored rating when it opens", async () => {
    stubServer(3);
    const { getByTestId } = render(ModelNotes, { props: { label: "armA" } });
    await fireEvent.click(getByTestId("model-notes-toggle"));
    await waitFor(() => expect(getByTestId("model-rating-3").classList.contains("on")).toBe(true));
  });
});
