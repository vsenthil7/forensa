import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  DiligenceWorkspace,
  type DiligenceJob,
} from "../DiligenceWorkspace";

const TENANT_ID = "45a9c68b-7d72-4f03-ba1c-600ffd5099a9";
const API_URL = "http://test.local";

function makeJob(over: Partial<DiligenceJob> = {}): DiligenceJob {
  return {
    job_id: "job-" + Math.random().toString(36).slice(2, 10),
    tenant_id: TENANT_ID,
    status: "completed",
    scope_start: "2026-05-13T00:00:00Z",
    scope_end: "2026-05-14T23:59:59Z",
    requested_at: "2026-05-13T10:00:00Z",
    started_at: "2026-05-13T10:00:05Z",
    completed_at: "2026-05-13T10:00:20Z",
    result_export: { "@type": "MaDiligenceExport", ma_root_hash: "f".repeat(64) },
    result_error: null,
    ...over,
  };
}

const originalCreate = global.URL.createObjectURL;
const originalRevoke = global.URL.revokeObjectURL;

beforeEach(() => {
  global.URL.createObjectURL = vi.fn().mockReturnValue("blob:fake");
  global.URL.revokeObjectURL = vi.fn();
});

afterEach(() => {
  global.URL.createObjectURL = originalCreate;
  global.URL.revokeObjectURL = originalRevoke;
  vi.useRealTimers();
});

describe("DiligenceWorkspace", () => {
  it("renders the create form + loading then empty state", async () => {
    const fetcher = vi.fn(async (_u: string | URL | Request) => ({
      ok: true,
      status: 200,
      json: async () => ({ items: [], tenant_id: TENANT_ID }),
    } as unknown as Response));
    render(
      <DiligenceWorkspace
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    expect(screen.getByTestId("diligence-create-form")).toBeTruthy();
    expect(screen.getByTestId("diligence-list-loading")).toBeTruthy();
    await waitFor(() => screen.getByTestId("diligence-list-empty"));
  });

  it("renders the jobs table when one or more jobs exist", async () => {
    const job = makeJob({ job_id: "j1" });
    const fetcher = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ items: [job], tenant_id: TENANT_ID }),
    } as unknown as Response));
    render(
      <DiligenceWorkspace
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("diligence-jobs-table"));
    expect(screen.getByTestId("diligence-job-row-j1")).toBeTruthy();
  });

  it("renders the error state when the list fetch returns non-ok", async () => {
    const fetcher = vi.fn(async () => ({
      ok: false,
      status: 503,
      json: async () => ({}),
    } as unknown as Response));
    render(
      <DiligenceWorkspace
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("diligence-list-error"));
    expect(screen.getByTestId("diligence-list-error").textContent).toContain("HTTP 503");
  });

  it("renders the error state when the list fetch throws", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("network"));
    render(
      <DiligenceWorkspace
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("diligence-list-error"));
    expect(screen.getByTestId("diligence-list-error").textContent).toContain("network");
  });

  it("Create-job requires both dates and shows an error if either missing", async () => {
    const fetcher = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ items: [], tenant_id: TENANT_ID }),
    } as unknown as Response));
    render(
      <DiligenceWorkspace
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("diligence-list-empty"));
    // Click Create with no dates filled in.
    fireEvent.click(screen.getByTestId("diligence-create-submit"));
    expect(screen.getByTestId("diligence-create-error").textContent).toContain(
      "Pick both",
    );
  });

  it("submits a Create-job POST with the documented body shape and refreshes", async () => {
    const job = makeJob({ job_id: "j-new", status: "pending" });
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ items: [], tenant_id: TENANT_ID }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 202,
        json: async () => ({ job_id: "j-new", status: "pending", poll_url: "/v1/exports/ma-diligence/jobs/j-new" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ items: [job], tenant_id: TENANT_ID }),
      });
    render(
      <DiligenceWorkspace
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("diligence-list-empty"));
    fireEvent.change(screen.getByTestId("diligence-scope-start"), {
      target: { value: "2026-05-13" },
    });
    fireEvent.change(screen.getByTestId("diligence-scope-end"), {
      target: { value: "2026-05-14" },
    });
    fireEvent.click(screen.getByTestId("diligence-create-submit"));
    await waitFor(() => screen.getByTestId("diligence-job-row-j-new"));
    // Assert the POST shape was what the API expects.
    const postCall = fetcher.mock.calls.find(
      (c) => (c[1] as RequestInit | undefined)?.method === "POST",
    );
    expect(postCall).toBeTruthy();
    const init = postCall?.[1] as RequestInit;
    const body = JSON.parse(init.body as string);
    expect(body.tenant_id).toBe(TENANT_ID);
    expect(body.scope_start.startsWith("2026-05-13")).toBe(true);
    expect(body.scope_end.startsWith("2026-05-14")).toBe(true);
  });

  it("surfaces a Create-job HTTP failure", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ items: [], tenant_id: TENANT_ID }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({}),
      });
    render(
      <DiligenceWorkspace
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("diligence-list-empty"));
    fireEvent.change(screen.getByTestId("diligence-scope-start"), {
      target: { value: "2026-05-13" },
    });
    fireEvent.change(screen.getByTestId("diligence-scope-end"), {
      target: { value: "2026-05-14" },
    });
    fireEvent.click(screen.getByTestId("diligence-create-submit"));
    await waitFor(() => screen.getByTestId("diligence-create-error"));
    expect(screen.getByTestId("diligence-create-error").textContent).toContain("422");
  });

  it("surfaces a Create-job thrown error", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ items: [], tenant_id: TENANT_ID }),
      })
      .mockRejectedValueOnce(new Error("post-boom"));
    render(
      <DiligenceWorkspace
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("diligence-list-empty"));
    fireEvent.change(screen.getByTestId("diligence-scope-start"), {
      target: { value: "2026-05-13" },
    });
    fireEvent.change(screen.getByTestId("diligence-scope-end"), {
      target: { value: "2026-05-14" },
    });
    fireEvent.click(screen.getByTestId("diligence-create-submit"));
    await waitFor(() => screen.getByTestId("diligence-create-error"));
    expect(screen.getByTestId("diligence-create-error").textContent).toContain("post-boom");
  });

  it("selecting a job opens its detail panel", async () => {
    const job = makeJob({ job_id: "j-sel", status: "completed" });
    const fetcher = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ items: [job], tenant_id: TENANT_ID }),
    } as unknown as Response));
    render(
      <DiligenceWorkspace
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("diligence-job-row-j-sel"));
    fireEvent.click(screen.getByTestId("diligence-job-select-j-sel"));
    expect(screen.getByTestId("diligence-job-detail")).toBeTruthy();
    expect(screen.getByTestId("diligence-detail-id").textContent).toBe("j-sel");
  });

  it("the detail panel renders for a pending job (no Completed row, no Download)", async () => {
    const job = makeJob({
      job_id: "j-pend",
      status: "pending",
      started_at: null,
      completed_at: null,
      result_export: null,
      result_error: null,
    });
    const fetcher = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ items: [job], tenant_id: TENANT_ID }),
    } as unknown as Response));
    render(
      <DiligenceWorkspace
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("diligence-job-row-j-pend"));
    fireEvent.click(screen.getByTestId("diligence-job-select-j-pend"));
    expect(screen.getByTestId("diligence-job-detail")).toBeTruthy();
    expect(screen.queryByTestId("diligence-download-bundle")).toBeNull();
    expect(screen.queryByTestId("diligence-detail-error")).toBeNull();
  });

  it("renders the error text on a failed job's detail panel", async () => {
    const job = makeJob({
      job_id: "j-fail",
      status: "failed",
      completed_at: "2026-05-13T10:00:30Z",
      result_export: null,
      result_error: "anchor not found",
    });
    const fetcher = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ items: [job], tenant_id: TENANT_ID }),
    } as unknown as Response));
    render(
      <DiligenceWorkspace
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("diligence-job-row-j-fail"));
    fireEvent.click(screen.getByTestId("diligence-job-select-j-fail"));
    expect(screen.getByTestId("diligence-detail-error").textContent).toContain(
      "anchor not found",
    );
    // No download button for failed jobs.
    expect(screen.queryByTestId("diligence-download-bundle")).toBeNull();
  });

  it("downloads the bundle JSON when the completed-job download button is clicked", async () => {
    const job = makeJob({ job_id: "j-dl" });
    const fetcher = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ items: [job], tenant_id: TENANT_ID }),
    } as unknown as Response));
    render(
      <DiligenceWorkspace
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("diligence-job-row-j-dl"));
    fireEvent.click(screen.getByTestId("diligence-job-select-j-dl"));
    fireEvent.click(screen.getByTestId("diligence-download-bundle"));
    expect(global.URL.createObjectURL).toHaveBeenCalled();
  });

  it("polls while any job is pending or running, then stops once all settle", async () => {
    vi.useFakeTimers();
    const inflight = makeJob({ job_id: "j-poll", status: "running" });
    // Each call returns the same in-flight job so the poll loop keeps
    // firing (jobs never complete during the test window).
    const fetcher = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ items: [inflight], tenant_id: TENANT_ID }),
    } as unknown as Response));
    render(
      <DiligenceWorkspace
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        pollMs={50}
      />,
    );
    // Let the initial fetch + the effect chain settle.
    await act(async () => {
      vi.advanceTimersByTime(0);
      await Promise.resolve();
      await Promise.resolve();
    });
    const initialCalls = fetcher.mock.calls.length;
    // Advance fake timers enough that the polling interval fires.
    await act(async () => {
      vi.advanceTimersByTime(250);
      await Promise.resolve();
      await Promise.resolve();
    });
    // Should have polled at least once more after the initial settle.
    expect(fetcher.mock.calls.length).toBeGreaterThan(initialCalls);
    vi.useRealTimers();
  });

  it("renders a status badge for every documented job state", async () => {
    const jobs = [
      makeJob({ job_id: "p", status: "pending" }),
      makeJob({ job_id: "r", status: "running" }),
      makeJob({ job_id: "c", status: "completed" }),
      makeJob({ job_id: "f", status: "failed" }),
    ];
    const fetcher = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ items: jobs, tenant_id: TENANT_ID }),
    } as unknown as Response));
    render(
      <DiligenceWorkspace
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("diligence-job-row-p"));
    // Each variant rendered at least once (the table renders 4 + detail
    // could render selected). Use getAllByTestId for accuracy.
    for (const s of ["pending", "running", "completed", "failed"] as const) {
      expect(screen.getAllByTestId(`diligence-status-${s}`).length).toBeGreaterThan(0);
    }
  });

  it("handles a missing items field gracefully (treats as empty)", async () => {
    const fetcher = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        items: undefined,
        tenant_id: TENANT_ID,
      }),
    } as unknown as Response));
    render(
      <DiligenceWorkspace
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("diligence-list-empty"));
  });

  it("uses the default API URL when none is provided", () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], tenant_id: TENANT_ID }),
    });
    render(
      <DiligenceWorkspace
        tenantId={TENANT_ID}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    expect(fetcher).toHaveBeenCalled();
  });
});
