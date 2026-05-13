"use client";

import { useEffect, useState } from "react";

export type HealthStatus =
  | "ok"
  | "degraded"
  | "unreachable"
  | "unauthenticated"
  | "unknown";

export interface HealthBadgeProps {
  apiUrl?: string;
  fetcher?: typeof fetch;
}

const DEFAULT_URL =
  process.env.NEXT_PUBLIC_FORENSA_API_URL ?? "http://localhost:8000";

const STATUS_STYLES: Record<HealthStatus, { bg: string; fg: string }> = {
  ok: { bg: "#d1fae5", fg: "#065f46" },
  degraded: { bg: "#fef3c7", fg: "#92400e" },
  unreachable: { bg: "#fee2e2", fg: "#991b1b" },
  unauthenticated: { bg: "#e0e7ff", fg: "#3730a3" },
  unknown: { bg: "#f3f4f6", fg: "#374151" },
};

function classifyResponse(r: Response, body: { status?: string }): HealthStatus {
  if (r.status === 401 || r.status === 403) return "unauthenticated";
  if (r.status >= 500) return "unreachable";
  if (!r.ok) return "degraded";
  return body.status === "ok" ? "ok" : "degraded";
}

export function HealthBadge({ apiUrl, fetcher = fetch }: HealthBadgeProps) {
  const [status, setStatus] = useState<HealthStatus>("unknown");
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const url = (apiUrl ?? DEFAULT_URL) + "/healthz";

  useEffect(() => {
    let cancelled = false;
    fetcher(url)
      .then(async (r) => {
        if (cancelled) return;
        let body: { status?: string } = {};
        try {
          body = (await r.json()) as { status?: string };
        } catch {
          // Body was not JSON; rely on HTTP status alone.
        }
        setStatus(classifyResponse(r, body));
        setLastChecked(new Date());
      })
      .catch(() => {
        if (!cancelled) {
          setStatus("unreachable");
          setLastChecked(new Date());
        }
      });
    return () => {
      cancelled = true;
    };
  }, [url, fetcher]);

  const style = STATUS_STYLES[status];
  const tooltip = lastChecked
    ? `Last checked ${lastChecked.toISOString()}`
    : "Not yet checked";

  return (
    <span
      data-testid="health-badge"
      data-status={status}
      data-last-checked={lastChecked ? lastChecked.toISOString() : ""}
      title={tooltip}
      style={{
        display: "inline-block",
        padding: "0.25rem 0.75rem",
        borderRadius: "9999px",
        backgroundColor: style.bg,
        color: style.fg,
        fontSize: "0.875rem",
        fontWeight: 500,
      }}
    >
      API: {status}
    </span>
  );
}
