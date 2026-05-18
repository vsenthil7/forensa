import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  StatusDashboard,
  type HealthzResponse,
  type MetricsResponse,
} from "../StatusDashboard";

const API_URL = "http://test.local";
const TENANT_ID = "00000000-0000-0000-0000-000000000001";

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

function buildMetrics(over: Partial<MetricsResponse> = {}): MetricsResponse {
  return {
    tenant_id: TENANT_ID,
    generated_at: "2026-05-18T15:00:00Z",
    window_hours: 24,
    window_start: "2026-05-17T15:00:00Z",
    window_end: "2026-05-18T15:00:00Z",
    ingest: { events_total: 120, events_in_window: 48, events_per_hour: 2.0 },
    signing: {
      receipts_total: 120,
      receipts_in_window: 48,
      receipts_per_hour: 2.0,
      chain_head_sequence: 119,
      last_receipt_signed_at: "2026-05-18T14:55:00Z",
    },
    anchoring: { anchors_in_window: 1, anchored: 1, deferred: 0 },
    ma_export_jobs: { pending: 0, running: 0, completed: 2, failed: 0 },
    ...over,
  };
}

/** A fetcher that returns different bodies for /healthz vs /v1/metrics. */
function makeFetcher(opts: {
  healthzOk?: boolean;
  healthzStatus?: number;
  healthzBody?: HealthzResponse;
  healthzThrow?: Error;
  metricsOk?: boolean;
  metricsStatus?: number;
  metricsBody?: MetricsResponse;
  metricsThrow?: Error;
}) {
  return vi.fn(async (input: string | URL | Request) => {
    const url = String(input);
    if (url.includes("/healthz")) {
      if (opts.healthzThrow) throw opts.healthzThrow;
      return {
        ok: opts.healthzOk ?? true,
        status: opts.healthzStatus ?? 200,
        json: async () => opts.healthzBody ?? buildHealthz(),
      } as unknown as Response;
    }
    if (opts.metricsThrow) throw opts.metricsThrow;
    return {
      ok: opts.metricsOk ?? true,
      status: opts.metricsStatus ?? 200,
      json: async () => opts.metricsBody ?? buildMetrics(),
    } as unknown as Response;
  });
}

afterEach(() => {
  vi.useRealTimers();
});

describe("StatusDashboard", () => {
  it("shows loading then a healthy api panel + a metrics panel", async () => {
    const fetcher = makeFetcher({});
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        tenantId={TENANT_ID}
      />,
    );
    expect(screen.getByTestId("status-loading")).toBeTruthy();
    await waitFor(() => screen.getByTestId("status-api-panel"));
    await waitFor(() => screen.getByTestId("status-metrics-panel"));
    expect(screen.getByTestId("status-overall-chip").textContent).toContain(
      "API healthy",
    );
    expect(screen.getByTestId("status-api-version").textContent).toBe("1.0.0");
    expect(screen.getByTestId("status-metrics-ingest").textContent).toContain(
      "2.0",
    );
  });

  it("shows the fallback line when narrative_is_fallback=true", async () => {
    const fetcher = makeFetcher({
      healthzBody: buildHealthz({ narrative_is_fallback: true }),
    });
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        tenantId={TENANT_ID}
      />,
    );
    await waitFor(() => screen.getByTestId("status-api-panel"));
    expect(screen.getByTestId("status-narrative-fallback").textContent).toContain(
      "mock",
    );
  });

  it("shows Degraded chip when /healthz returns a non-ok status body", async () => {
    const fetcher = makeFetcher({
      healthzBody: buildHealthz({ status: "degraded" }),
    });
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        tenantId={TENANT_ID}
      />,
    );
    await waitFor(() => screen.getByTestId("status-overall-chip"));
    expect(screen.getByTestId("status-overall-chip").textContent).toContain(
      "Degraded",
    );
  });

  it("shows Unreachable + error message when /healthz returns non-ok HTTP", async () => {
    const fetcher = makeFetcher({ healthzOk: false, healthzStatus: 503 });
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        tenantId={TENANT_ID}
      />,
    );
    await waitFor(() => screen.getByTestId("status-error"));
    expect(screen.getByTestId("status-error").textContent).toContain("HTTP 503");
    expect(screen.getByTestId("status-overall-chip").textContent).toContain(
      "Unreachable",
    );
  });

  it("shows Unreachable when /healthz fetch throws", async () => {
    const fetcher = makeFetcher({ healthzThrow: new Error("connection refused") });
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        tenantId={TENANT_ID}
      />,
    );
    await waitFor(() => screen.getByTestId("status-error"));
    expect(screen.getByTestId("status-error").textContent).toContain(
      "connection refused",
    );
  });

  it("clicking Refresh re-fetches /healthz", async () => {
    const fetcher = makeFetcher({});
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        tenantId={TENANT_ID}
      />,
    );
    await waitFor(() => screen.getByTestId("status-api-panel"));
    const initial = fetcher.mock.calls.filter((c) =>
      String(c[0]).includes("/healthz"),
    ).length;
    fireEvent.click(screen.getByTestId("status-refresh"));
    await waitFor(() => {
      const after = fetcher.mock.calls.filter((c) =>
        String(c[0]).includes("/healthz"),
      ).length;
      expect(after).toBeGreaterThan(initial);
    });
  });

  it("renders the Phase-11 planned-latency panel", async () => {
    const fetcher = makeFetcher({});
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        tenantId={TENANT_ID}
      />,
    );
    await waitFor(() => screen.getByTestId("status-planned-panels"));
    expect(screen.getByTestId("status-planned-list")).toBeTruthy();
    expect(screen.getByTestId("status-planned-panels").textContent).toContain(
      "Phase 11",
    );
  });

  it("auto-refreshes /healthz on the polling interval", async () => {
    vi.useFakeTimers();
    const fetcher = makeFetcher({});
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        tenantId={TENANT_ID}
        pollMs={50}
      />,
    );
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    const callsAfterInitial = fetcher.mock.calls.filter((c) =>
      String(c[0]).includes("/healthz"),
    ).length;
    await act(async () => {
      vi.advanceTimersByTime(120);
      await Promise.resolve();
    });
    const callsAfter = fetcher.mock.calls.filter((c) =>
      String(c[0]).includes("/healthz"),
    ).length;
    expect(callsAfter).toBeGreaterThan(callsAfterInitial);
    vi.useRealTimers();
  });

  it("uses the default API URL when none is provided", () => {
    const fetcher = vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("/healthz")) {
        return {
          ok: true,
          status: 200,
          json: async () => buildHealthz(),
        } as unknown as Response;
      }
      return {
        ok: true,
        status: 200,
        json: async () => buildMetrics(),
      } as unknown as Response;
    });
    render(<StatusDashboard fetcher={fetcher as unknown as typeof fetch} />);
    expect(fetcher).toHaveBeenCalled();
  });

  it("renders the metrics panel with the window-hours chip", async () => {
    const fetcher = makeFetcher({
      metricsBody: buildMetrics({ window_hours: 6 }),
    });
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        tenantId={TENANT_ID}
      />,
    );
    await waitFor(() => screen.getByTestId("status-metrics-panel"));
    expect(screen.getByTestId("status-metrics-window").textContent).toContain(
      "6h",
    );
  });

  it("flags anchors as warn when deferred > 0", async () => {
    const fetcher = makeFetcher({
      metricsBody: buildMetrics({
        anchoring: { anchors_in_window: 2, anchored: 1, deferred: 1 },
      }),
    });
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        tenantId={TENANT_ID}
      />,
    );
    await waitFor(() => screen.getByTestId("status-metrics-anchors"));
    expect(screen.getByTestId("status-metrics-anchors").textContent).toContain(
      "1 deferred",
    );
  });

  it("flags M&A jobs as warn when failed > 0", async () => {
    const fetcher = makeFetcher({
      metricsBody: buildMetrics({
        ma_export_jobs: { pending: 0, running: 0, completed: 0, failed: 2 },
      }),
    });
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        tenantId={TENANT_ID}
      />,
    );
    await waitFor(() => screen.getByTestId("status-metrics-jobs"));
    expect(screen.getByTestId("status-metrics-jobs").textContent).toContain(
      "2 failed",
    );
  });

  it("handles null chain head sequence (empty tenant)", async () => {
    const fetcher = makeFetcher({
      metricsBody: buildMetrics({
        signing: {
          receipts_total: 0,
          receipts_in_window: 0,
          receipts_per_hour: 0,
          chain_head_sequence: null,
          last_receipt_signed_at: null,
        },
      }),
    });
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        tenantId={TENANT_ID}
      />,
    );
    await waitFor(() => screen.getByTestId("status-metrics-chain"));
    expect(screen.getByTestId("status-metrics-chain").textContent).toContain(
      "no receipts",
    );
  });

  it("surfaces a /v1/metrics HTTP error in the metrics panel without breaking the api panel", async () => {
    const fetcher = makeFetcher({ metricsOk: false, metricsStatus: 500 });
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        tenantId={TENANT_ID}
      />,
    );
    await waitFor(() => screen.getByTestId("status-api-panel"));
    await waitFor(() => screen.getByTestId("status-metrics-error"));
    expect(screen.getByTestId("status-metrics-error").textContent).toContain(
      "HTTP 500",
    );
  });

  it("surfaces a /v1/metrics thrown error", async () => {
    const fetcher = makeFetcher({ metricsThrow: new Error("net-boom") });
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        tenantId={TENANT_ID}
      />,
    );
    await waitFor(() => screen.getByTestId("status-metrics-error"));
    expect(screen.getByTestId("status-metrics-error").textContent).toContain(
      "net-boom",
    );
  });

  it("renders a 'last signed at' value when present", async () => {
    const fetcher = makeFetcher({});
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        tenantId={TENANT_ID}
      />,
    );
    await waitFor(() => screen.getByTestId("status-metrics-chain"));
    expect(screen.getByTestId("status-metrics-chain").textContent).toContain(
      "last signed",
    );
  });

  it("falls back to '—' when last_receipt_signed_at is null but chain head sequence exists (defensive)", async () => {
    const fetcher = makeFetcher({
      metricsBody: buildMetrics({
        signing: {
          receipts_total: 1,
          receipts_in_window: 1,
          receipts_per_hour: 0.04,
          chain_head_sequence: 0,
          last_receipt_signed_at: null,
        },
      }),
    });
    render(
      <StatusDashboard
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        tenantId={TENANT_ID}
      />,
    );
    await waitFor(() => screen.getByTestId("status-metrics-chain"));
    expect(screen.getByTestId("status-metrics-chain").textContent).toContain("—");
  });
});
