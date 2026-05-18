"use client";

/**
 * Forensa Console — operator status dashboard (SCR-F10).
 *
 * Acceptance:
 *   - Show what `/healthz` already exposes today: API status, version,
 *     narrative-client provider + model id + fallback flag.
 *   - Show the panels US-F10's parent surface (API-F15 `GET /v1/metrics`)
 *     will populate when it lands, with explicit "Planned in API-F15"
 *     placeholders. This is the v2.0 honest-gaps pattern (BR-14 AC-2):
 *     surface the product surface area without lying about what's wired.
 *
 * Auto-refreshes every 10 s.
 */

import { useCallback, useEffect, useState } from "react";

export interface HealthzResponse {
  status: string;
  version: string;
  narrative_provider: string;
  narrative_model_id: string;
  narrative_is_fallback: boolean;
}

type LoadState = "loading" | "ok" | "error";

export interface StatusDashboardProps {
  apiUrl?: string;
  fetcher?: typeof fetch;
  /** Refresh interval, ms; lower in tests. */
  pollMs?: number;
  /** Tenant whose metrics to fetch from /v1/metrics. */
  tenantId?: string;
}

const DEFAULT_URL =
  /* v8 ignore next */
  process.env.NEXT_PUBLIC_FORENSA_API_URL ?? "http://localhost:8000";

const DEFAULT_TENANT_ID =
  /* v8 ignore next */
  process.env.NEXT_PUBLIC_FORENSA_DEMO_TENANT_ID ??
  "00000000-0000-0000-0000-000000000001";

export function StatusDashboard({
  apiUrl,
  fetcher = fetch,
  pollMs = 10_000,
  tenantId = DEFAULT_TENANT_ID,
}: StatusDashboardProps) {
  const baseUrl = apiUrl ?? DEFAULT_URL;
  const [state, setState] = useState<LoadState>("loading");
  const [healthz, setHealthz] = useState<HealthzResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [lastChecked, setLastChecked] = useState<string>("");

  const refresh = useCallback(async () => {
    try {
      const r = await fetcher(`${baseUrl}/healthz`);
      if (!r.ok) {
        setState("error");
        setErrorMsg(`HTTP ${r.status}`);
        setLastChecked(new Date().toISOString());
        return;
      }
      const body = (await r.json()) as HealthzResponse;
      setHealthz(body);
      setState("ok");
      setLastChecked(new Date().toISOString());
    } catch (e) {
      setState("error");
      setErrorMsg((e as Error).message);
      setLastChecked(new Date().toISOString());
    }
  }, [baseUrl, fetcher]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, pollMs);
    return () => clearInterval(id);
  }, [refresh, pollMs]);

  return (
    <div
      data-testid="status-dashboard"
      style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}
    >
      <header
        data-testid="status-header"
        style={{
          display: "flex",
          alignItems: "center",
          gap: "1rem",
          flexWrap: "wrap",
        }}
      >
        <OverallChip state={state} bodyStatus={healthz?.status ?? ""} />
        <span
          data-testid="status-last-checked"
          style={{ fontSize: "0.85rem", color: "#6b7280" }}
        >
          {lastChecked ? `Last checked ${lastChecked}` : "Checking…"}
        </span>
        <button
          type="button"
          data-testid="status-refresh"
          onClick={refresh}
          style={{
            padding: "0.35rem 0.7rem",
            borderRadius: "0.35rem",
            border: "1px solid #d1d5db",
            background: "white",
            color: "#374151",
            cursor: "pointer",
            fontSize: "0.85rem",
            marginLeft: "auto",
          }}
        >
          Refresh
        </button>
      </header>

      {state === "loading" ? (
        <p data-testid="status-loading">Checking API health…</p>
      ) : state === "error" ? (
        <p
          data-testid="status-error"
          role="alert"
          style={{
            color: "#991b1b",
            padding: "0.75rem 1rem",
            background: "#fef2f2",
            border: "1px solid #fca5a5",
            borderRadius: "0.4rem",
          }}
        >
          Couldn&apos;t reach the API: {errorMsg}
        </p>
      ) : healthz ? (
        <ApiHealthPanel healthz={healthz} />
      ) : /* v8 ignore next */ null}

      <MetricsPanel
        apiUrl={baseUrl}
        fetcher={fetcher}
        tenantId={tenantId}
        pollMs={pollMs}
      />
      <PlannedPanels />
    </div>
  );
}

function OverallChip({
  state,
  bodyStatus,
}: {
  state: LoadState;
  bodyStatus: string;
}) {
  let label: string;
  let palette: { bg: string; fg: string };
  if (state === "loading") {
    label = "Checking…";
    palette = { bg: "#f3f4f6", fg: "#374151" };
  } else if (state === "error") {
    label = "Unreachable";
    palette = { bg: "#fee2e2", fg: "#991b1b" };
  } else if (bodyStatus === "ok") {
    label = "API healthy";
    palette = { bg: "#dcfce7", fg: "#166534" };
  } else {
    label = "Degraded";
    palette = { bg: "#fef3c7", fg: "#92400e" };
  }
  return (
    <span
      data-testid="status-overall-chip"
      data-state={state}
      style={{
        padding: "0.35rem 0.85rem",
        borderRadius: "999px",
        background: palette.bg,
        color: palette.fg,
        fontWeight: 600,
        fontSize: "0.9rem",
      }}
    >
      {label}
    </span>
  );
}

function ApiHealthPanel({ healthz }: { healthz: HealthzResponse }) {
  return (
    <article
      data-testid="status-api-panel"
      style={{
        padding: "1rem",
        border: "1px solid #e5e7eb",
        borderRadius: "0.5rem",
        background: "white",
      }}
    >
      <h2 style={{ marginTop: 0, fontSize: "1rem" }}>API</h2>
      <dl
        style={{
          display: "grid",
          gridTemplateColumns: "max-content 1fr",
          gap: "0.4rem 1rem",
          fontSize: "0.9rem",
          margin: 0,
        }}
      >
        <dt>Status</dt>
        <dd data-testid="status-api-status" style={{ margin: 0 }}>
          {healthz.status}
        </dd>
        <dt>Version</dt>
        <dd
          data-testid="status-api-version"
          style={{ margin: 0, fontFamily: "monospace" }}
        >
          {healthz.version}
        </dd>
        <dt>Narrative provider</dt>
        <dd
          data-testid="status-narrative-provider"
          style={{ margin: 0, fontFamily: "monospace" }}
        >
          {healthz.narrative_provider}
        </dd>
        <dt>Narrative model</dt>
        <dd
          data-testid="status-narrative-model"
          style={{ margin: 0, fontFamily: "monospace" }}
        >
          {healthz.narrative_model_id}
        </dd>
        <dt>Fallback?</dt>
        <dd
          data-testid="status-narrative-fallback"
          data-is-fallback={String(healthz.narrative_is_fallback)}
          style={{ margin: 0 }}
        >
          {healthz.narrative_is_fallback
            ? "yes — mock narrative client active"
            : "no — live narrative client"}
        </dd>
      </dl>
    </article>
  );
}

function PlannedPanels() {
  return (
    <article
      data-testid="status-planned-panels"
      style={{
        padding: "1rem",
        border: "1px dashed #d1d5db",
        borderRadius: "0.5rem",
        background: "#f9fafb",
      }}
    >
      <h2 style={{ marginTop: 0, fontSize: "1rem" }}>
        Signing latency{" "}
        <span
          style={{
            fontSize: "0.75rem",
            background: "#e5e7eb",
            color: "#374151",
            padding: "0.15rem 0.45rem",
            borderRadius: "0.4rem",
            marginLeft: "0.5rem",
            fontWeight: 500,
          }}
        >
          Phase 11 — request middleware
        </span>
      </h2>
      <p style={{ fontSize: "0.9rem", color: "#374151", margin: "0 0 0.75rem" }}>
        p50 / p95 / p99 require HTTP middleware to record per-request
        timings. <code style={{ fontFamily: "monospace" }}>GET /v1/metrics</code>{" "}
        (API-F15) is wired today; latency histograms ship with the Phase 11
        observability sweep.
      </p>
      <ul
        data-testid="status-planned-list"
        style={{ margin: 0, paddingLeft: "1.25rem", color: "#6b7280", fontSize: "0.85rem" }}
      >
        <li>Ingest rate (events / hour, 24h window) — present above</li>
        <li>Signing latency p50 / p95 / p99 — Phase 11</li>
        <li>Anchor success / failure / deferred counts — present above</li>
        <li>Chain integrity (head sequence + freshness) — present above</li>
      </ul>
    </article>
  );
}

export interface MetricsResponse {
  tenant_id: string;
  generated_at: string;
  window_hours: number;
  window_start: string;
  window_end: string;
  ingest: {
    events_total: number;
    events_in_window: number;
    events_per_hour: number;
  };
  signing: {
    receipts_total: number;
    receipts_in_window: number;
    receipts_per_hour: number;
    chain_head_sequence: number | null;
    last_receipt_signed_at: string | null;
  };
  anchoring: {
    anchors_in_window: number;
    anchored: number;
    deferred: number;
  };
  ma_export_jobs: {
    pending: number;
    running: number;
    completed: number;
    failed: number;
  };
}

interface MetricsPanelProps {
  apiUrl: string;
  fetcher: typeof fetch;
  tenantId: string;
  pollMs: number;
}

function MetricsPanel({ apiUrl, fetcher, tenantId, pollMs }: MetricsPanelProps) {
  const [state, setState] = useState<LoadState>("loading");
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");

  const refresh = useCallback(async () => {
    try {
      const r = await fetcher(
        `${apiUrl}/v1/metrics?tenant_id=${encodeURIComponent(tenantId)}`,
      );
      if (!r.ok) {
        setState("error");
        setErrorMsg(`HTTP ${r.status}`);
        return;
      }
      const body = (await r.json()) as MetricsResponse;
      setMetrics(body);
      setState("ok");
    } catch (e) {
      setState("error");
      setErrorMsg((e as Error).message);
    }
  }, [apiUrl, fetcher, tenantId]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, pollMs);
    return () => clearInterval(id);
  }, [refresh, pollMs]);

  if (state === "loading") {
    return <p data-testid="status-metrics-loading">Loading metrics…</p>;
  }
  if (state === "error") {
    return (
      <p
        data-testid="status-metrics-error"
        role="alert"
        style={{
          color: "#991b1b",
          padding: "0.75rem 1rem",
          background: "#fef2f2",
          border: "1px solid #fca5a5",
          borderRadius: "0.4rem",
        }}
      >
        Couldn&apos;t load metrics: {errorMsg}
      </p>
    );
  }
  /* v8 ignore next 3 */
  if (!metrics) {
    return null;
  }
  return (
    <article
      data-testid="status-metrics-panel"
      style={{
        padding: "1rem",
        border: "1px solid #e5e7eb",
        borderRadius: "0.5rem",
        background: "white",
      }}
    >
      <h2 style={{ marginTop: 0, fontSize: "1rem" }}>
        Operational metrics{" "}
        <span
          data-testid="status-metrics-window"
          style={{
            fontSize: "0.75rem",
            background: "#dcfce7",
            color: "#166534",
            padding: "0.15rem 0.45rem",
            borderRadius: "0.4rem",
            marginLeft: "0.5rem",
            fontWeight: 500,
          }}
        >
          {metrics.window_hours}h window
        </span>
      </h2>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(12rem, 1fr))",
          gap: "0.75rem",
          marginTop: "0.5rem",
        }}
      >
        <MetricCard
          testid="status-metrics-ingest"
          label="Ingest rate"
          value={`${metrics.ingest.events_per_hour.toFixed(1)} / hour`}
          sub={`${metrics.ingest.events_in_window} events in window · ${metrics.ingest.events_total} total`}
        />
        <MetricCard
          testid="status-metrics-signing"
          label="Signing rate"
          value={`${metrics.signing.receipts_per_hour.toFixed(1)} / hour`}
          sub={`${metrics.signing.receipts_in_window} receipts in window · ${metrics.signing.receipts_total} total`}
        />
        <MetricCard
          testid="status-metrics-chain"
          label="Chain head"
          value={
            metrics.signing.chain_head_sequence === null
              ? "no receipts yet"
              : `seq ${metrics.signing.chain_head_sequence}`
          }
          sub={
            metrics.signing.last_receipt_signed_at
              ? `last signed ${new Date(metrics.signing.last_receipt_signed_at).toISOString()}`
              : "—"
          }
        />
        <MetricCard
          testid="status-metrics-anchors"
          label="Anchors (window)"
          value={`${metrics.anchoring.anchored} ok · ${metrics.anchoring.deferred} deferred`}
          sub={`${metrics.anchoring.anchors_in_window} total`}
          flag={metrics.anchoring.deferred > 0 ? "warn" : "ok"}
        />
        <MetricCard
          testid="status-metrics-jobs"
          label="M&A jobs (window)"
          value={`${metrics.ma_export_jobs.completed} done · ${metrics.ma_export_jobs.failed} failed`}
          sub={`${metrics.ma_export_jobs.pending} pending · ${metrics.ma_export_jobs.running} running`}
          flag={metrics.ma_export_jobs.failed > 0 ? "warn" : "ok"}
        />
      </div>
    </article>
  );
}

function MetricCard({
  testid,
  label,
  value,
  sub,
  flag = "ok",
}: {
  testid: string;
  label: string;
  value: string;
  sub: string;
  flag?: "ok" | "warn";
}) {
  const bg = flag === "warn" ? "#fef3c7" : "#f9fafb";
  const fg = flag === "warn" ? "#92400e" : "#111827";
  return (
    <div
      data-testid={testid}
      style={{
        padding: "0.65rem 0.85rem",
        background: bg,
        color: fg,
        borderRadius: "0.4rem",
        border: "1px solid #e5e7eb",
      }}
    >
      <div
        style={{
          fontSize: "0.7rem",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          opacity: 0.7,
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: "1rem", fontWeight: 600, marginTop: "0.15rem" }}>
        {value}
      </div>
      <div style={{ fontSize: "0.75rem", marginTop: "0.15rem", opacity: 0.7 }}>
        {sub}
      </div>
    </div>
  );
}
