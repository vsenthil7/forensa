import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StatusDashboard, type HealthzResponse } from "../StatusDashboard";

const API_URL = "http://test.local";

function buildHealthz(over: Partial<HealthzResponse> = {}): HealthzResponse {
  return {
    status: "ok",
    version: "1.0.0",
    narrative_provider: "google",
    narrative_model_id: "gemini-2.5-pro",
    narrative_is_fallback: false,
    ...over,
  };
}

afterEach(() => {
  vi.useRealTimers();
});

describe("StatusDashboard", () => {
  it("shows loading then a healthy api panel when /healthz returns ok", async () => {
    const fetcher = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => buildHealthz(),
    } as unknown as Response));
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    expect(screen.getByTestId("status-loading")).toBeTruthy();
    await waitFor(() => screen.getByTestId("status-api-panel"));
    expect(screen.getByTestId("status-overall-chip").textContent).toContain(
      "API healthy",
    );
    expect(screen.getByTestId("status-api-status").textContent).toBe("ok");
    expect(screen.getByTestId("status-api-version").textContent).toBe("1.0.0");
    expect(screen.getByTestId("status-narrative-fallback").textContent).toContain(
      "no",
    );
  });

  it("shows the fallback line when narrative_is_fallback=true", async () => {
    const fetcher = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => buildHealthz({ narrative_is_fallback: true }),
    } as unknown as Response));
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("status-api-panel"));
    expect(screen.getByTestId("status-narrative-fallback").textContent).toContain(
      "mock",
    );
  });

  it("shows Degraded chip when /healthz returns a non-ok status body", async () => {
    const fetcher = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => buildHealthz({ status: "degraded" }),
    } as unknown as Response));
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("status-overall-chip"));
    expect(screen.getByTestId("status-overall-chip").textContent).toContain(
      "Degraded",
    );
  });

  it("shows Unreachable + error message when /healthz returns non-ok HTTP", async () => {
    const fetcher = vi.fn(async () => ({
      ok: false,
      status: 503,
      json: async () => ({}),
    } as unknown as Response));
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("status-error"));
    expect(screen.getByTestId("status-error").textContent).toContain("HTTP 503");
    expect(screen.getByTestId("status-overall-chip").textContent).toContain(
      "Unreachable",
    );
  });

  it("shows Unreachable when /healthz fetch throws", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("connection refused"));
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("status-error"));
    expect(screen.getByTestId("status-error").textContent).toContain(
      "connection refused",
    );
  });

  it("clicking Refresh re-fetches /healthz", async () => {
    const fetcher = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => buildHealthz(),
    } as unknown as Response));
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("status-api-panel"));
    const initial = fetcher.mock.calls.length;
    fireEvent.click(screen.getByTestId("status-refresh"));
    await waitFor(() =>
      expect(fetcher.mock.calls.length).toBeGreaterThan(initial),
    );
  });

  it("renders the API-F15 planned panels list", async () => {
    const fetcher = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => buildHealthz(),
    } as unknown as Response));
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("status-planned-panels"));
    expect(screen.getByTestId("status-planned-list")).toBeTruthy();
    expect(screen.getByTestId("status-planned-list").textContent).toContain(
      "Ingest rate",
    );
  });

  it("auto-refreshes on the polling interval", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => buildHealthz(),
    } as unknown as Response));
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        pollMs={50}
      />,
    );
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    const callsAfterInitial = fetcher.mock.calls.length;
    await act(async () => {
      vi.advanceTimersByTime(120);
      await Promise.resolve();
    });
    expect(fetcher.mock.calls.length).toBeGreaterThan(callsAfterInitial);
    vi.useRealTimers();
  });

  it("uses the default API URL when none is provided", () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => buildHealthz(),
    });
    render(<StatusDashboard fetcher={fetcher as unknown as typeof fetch} />);
    expect(fetcher).toHaveBeenCalled();
  });
});
