// @vitest-environment jsdom
import { render } from "@testing-library/svelte";
import { beforeEach, describe, expect, it } from "vitest";
import { jobs } from "../../../lib/render/jobs.svelte";
import InlineError from "../InlineError.svelte";

beforeEach(() => {
  jobs.lastError = null;
  jobs.gpuBusyOther = null;
});

describe("InlineError -- §9.7's one line under the target bar", () => {
  it("shows the message for its own target", () => {
    jobs.lastError = { targetKey: "clip:c1", message: "unknown render field(s): duration_sec" };
    const { getByTestId } = render(InlineError, { props: { targetKey: "clip:c1" } });
    expect(getByTestId("render-error").textContent).toContain("duration_sec");
  });

  it("stays out of the way for another target's error", () => {
    jobs.lastError = { targetKey: "clip:c9", message: "boom" };
    const { queryByTestId } = render(InlineError, { props: { targetKey: "clip:c1" } });
    expect(queryByTestId("render-error")).toBeNull();
  });

  it("shows `GPU busy — <job_id>` on every target, with no error of its own", () => {
    jobs.gpuBusyOther = "dash-77";
    const { getByTestId } = render(InlineError, { props: { targetKey: "session" } });
    expect(getByTestId("render-error").textContent?.trim()).toBe("GPU busy — dash-77");
  });
});
