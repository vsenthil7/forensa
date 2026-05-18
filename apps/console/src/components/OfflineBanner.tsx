"use client";

/**
 * Forensa Console — offline / stale banner (US-F31 AC-4, AC-5).
 *
 * Subscribes to window online/offline events and renders a yellow
 * banner when the browser reports offline AND/OR the last cached
 * payload is older than 24h. Per US-F31 AC-4 read-only views must
 * render offline; per AC-5 write actions must be disabled with an
 * explicit affordance — which is rendered here so each page can
 * compose it without duplicating the logic.
 *
 * The "stale" computation is injectable so tests can pass a fixed
 * clock without monkey-patching Date.
 */

import { useEffect, useState } from "react";

const STALE_THRESHOLD_MS = 24 * 60 * 60 * 1000;

export interface OfflineBannerProps {
  /** Returns the timestamp (ms epoch) of the most recently cached payload. */
  cachedAtMs?: number | null;
  /** Injectable for tests; defaults to Date.now. */
  now?: () => number;
  /** Override navigator.onLine for tests. */
  initialOnline?: boolean;
}

export function isCacheStale(
  cachedAtMs: number | null | undefined,
  nowMs: number,
  thresholdMs: number = STALE_THRESHOLD_MS,
): boolean {
  if (cachedAtMs === null || cachedAtMs === undefined) return false;
  return nowMs - cachedAtMs > thresholdMs;
}

export function OfflineBanner({
  cachedAtMs = null,
  now = () => Date.now(),
  initialOnline,
}: OfflineBannerProps) {
  const [online, setOnline] = useState<boolean>(() => {
    if (initialOnline !== undefined) return initialOnline;
    /* v8 ignore start */
    if (typeof navigator !== "undefined") return navigator.onLine;
    return true;
    /* v8 ignore stop */
  });

  useEffect(() => {
    /* v8 ignore next */
    if (typeof window === "undefined") return;
    const onUp = () => setOnline(true);
    const onDown = () => setOnline(false);
    window.addEventListener("online", onUp);
    window.addEventListener("offline", onDown);
    return () => {
      window.removeEventListener("online", onUp);
      window.removeEventListener("offline", onDown);
    };
  }, []);

  const stale = isCacheStale(cachedAtMs, now());

  if (online && !stale) return null;

  const message = !online
    ? "You're offline. Read-only views show the last cached state. Write actions are disabled."
    : "Cached data is older than 24h. Reconnect to refresh.";

  return (
    <div
      data-testid="offline-banner"
      data-online={online ? "true" : "false"}
      data-stale={stale ? "true" : "false"}
      role="status"
      style={{
        padding: "0.6rem 1rem",
        background: "#fef3c7",
        color: "#78350f",
        borderBottom: "1px solid #fde68a",
        fontSize: "0.9rem",
        fontWeight: 500,
      }}
    >
      {message}
    </div>
  );
}
