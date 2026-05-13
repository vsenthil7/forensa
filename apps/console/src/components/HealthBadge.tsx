"use client";

import { useEffect, useState } from "react";

export type HealthStatus = "ok" | "degraded" | "unknown";

export interface HealthBadgeProps {
  apiUrl?: string;
  fetcher?: typeof fetch;
}

const DEFAULT_URL =
  process.env.NEXT_PUBLIC_FORENSA_API_URL ?? "http://localhost:8000";

export function HealthBadge({ apiUrl, fetcher = fetch }: HealthBadgeProps) {
  const [status, setStatus] = useState<HealthStatus>("unknown");
  const url = (apiUrl ?? DEFAULT_URL) + "/healthz";

  useEffect(() => {
    let cancelled = false;
    fetcher(url)
      .then(async (r) => {
        if (cancelled) return;
        if (!r.ok) {
          setStatus("degraded");
          return;
        }
        const body = (await r.json()) as { status?: string };
        setStatus(body.status === "ok" ? "ok" : "degraded");
      })
      .catch(() => {
        if (!cancelled) setStatus("degraded");
      });
    return () => {
      cancelled = true;
    };
  }, [url, fetcher]);

  return (
    <span data-testid="health-badge" data-status={status}>
      API: {status}
    </span>
  );
}
