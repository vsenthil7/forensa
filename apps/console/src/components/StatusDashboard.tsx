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
}

const DEFAULT_URL =
  /* v8 ignore next */
  process.env.NEXT_PUBLIC_FORENSA_API_URL ?? "http://localhost:8000";

export function StatusDashboard({
  apiUrl,
  fetcher = fetch,
  pollMs = 10_000,
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
        Operational metrics{" "}
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
          API-F15 planned
        </span>
      </h2>
      <p style={{ fontSize: "0.9rem", color: "#374151", margin: "0 0 0.75rem" }}>
        The following panels render when{" "}
        <code style={{ fontFamily: "monospace" }}>GET /v1/metrics</code> lands
        per the v2.0 forward queue. Today only{" "}
        <code style={{ fontFamily: "monospace" }}>/healthz</code> is wired.
      </p>
      <ul
        data-testid="status-planned-list"
        style={{ margin: 0, paddingLeft: "1.25rem", color: "#6b7280", fontSize: "0.85rem" }}
      >
        <li>Ingest rate (events / second, 24h sparkline)</li>
        <li>Signing latency p50 / p95 / p99</li>
        <li>Anchor success / failure / deferred counts</li>
        <li>Chain integrity check (rolling)</li>
      </ul>
    </article>
  );
}
