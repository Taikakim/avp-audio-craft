// @vitest-environment jsdom
import { cleanup, fireEvent, render, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { forgeApi } from "../../../lib/forge/api";
import Files from "../Files.svelte";

vi.mock("../../../lib/forge/api", () => ({
  forgeApi: { files: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const FILES_RESPONSE = {
  ok: true as const,
  roots: [
    { id: "crops", label: "crops", available: true },
    { id: "renders", label: "renders", available: true },
    { id: "uploads", label: "uploads", available: false },
  ],
  files: [
    { root: "crops", rel: "000412.npy", kind: "latent" as const, size: 1024, mtime: 1,
      ref: { kind: "crop" as const, crop_id: "000412" } },
    { root: "crops", rel: "kick_loop.wav", kind: "audio" as const, size: 2048, mtime: 2,
      ref: { kind: "file" as const, root: "crops", rel: "kick_loop.wav" } },
  ],
};

describe("Files.svelte (spec §4.6.2) -- Task 15's real implementation, plus this task's two HELP ids", () => {
  it("fetches on mount and lists what the server returned", async () => {
    vi.mocked(forgeApi.files).mockResolvedValue(FILES_RESPONSE);
    const { findAllByRole } = render(Files);
    await waitFor(() => expect(forgeApi.files).toHaveBeenCalledWith({ root: "crops", q: undefined, limit: 200 }));
    const rows = await findAllByRole("listitem"); // the response renders a tick after the call
    expect(rows).toHaveLength(2);
    expect(rows[0].textContent).toContain("000412.npy");
  });

  it("re-fetches with the query when the filter field changes", async () => {
    vi.mocked(forgeApi.files).mockResolvedValue(FILES_RESPONSE);
    const { getByLabelText } = render(Files);
    await waitFor(() => expect(forgeApi.files).toHaveBeenCalledTimes(1));
    await fireEvent.input(getByLabelText("filter files"), { target: { value: "kick" } });
    await waitFor(() => expect(forgeApi.files).toHaveBeenCalledWith({ root: "crops", q: "kick", limit: 200 }));
  });

  it("shows an unavailable root disabled, with the (unmounted) suffix, not hidden", async () => {
    vi.mocked(forgeApi.files).mockResolvedValue(FILES_RESPONSE);
    const { findByText } = render(Files);
    const opt = (await findByText("uploads (unmounted)")) as HTMLOptionElement;
    expect(opt.tagName).toBe("OPTION");
    expect(opt.disabled).toBe(true);
  });

  it("sets application/x-forge-ref and text/sa3-crop-id on drag for a crop row, only x-forge-ref for a file row", async () => {
    vi.mocked(forgeApi.files).mockResolvedValue(FILES_RESPONSE);
    const { getAllByRole } = render(Files);
    await waitFor(() => expect(getAllByRole("listitem")).toHaveLength(2));
    const rows = getAllByRole("listitem");

    const dtCrop = { setData: vi.fn(), effectAllowed: "" };
    await fireEvent.dragStart(rows[0], { dataTransfer: dtCrop });
    expect(dtCrop.setData).toHaveBeenCalledWith("application/x-forge-ref", JSON.stringify(FILES_RESPONSE.files[0].ref));
    expect(dtCrop.setData).toHaveBeenCalledWith("text/sa3-crop-id", "000412");

    const dtFile = { setData: vi.fn(), effectAllowed: "" };
    await fireEvent.dragStart(rows[1], { dataTransfer: dtFile });
    expect(dtFile.setData).toHaveBeenCalledWith("application/x-forge-ref", JSON.stringify(FILES_RESPONSE.files[1].ref));
    expect(dtFile.setData).not.toHaveBeenCalledWith("text/sa3-crop-id", expect.anything());
  });

  it("carries data-help on the root select and the filter field", () => {
    vi.mocked(forgeApi.files).mockResolvedValue({ ok: true, roots: [], files: [] });
    const { getByLabelText } = render(Files);
    expect(getByLabelText("file root").getAttribute("data-help")).toBeTruthy();
    expect(getByLabelText("filter files").getAttribute("data-help")).toBeTruthy();
  });
});
