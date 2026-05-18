"use client";

/**
 * Forensa Console — anchors list view (SCR-F05, US-F16 UI access).
 *
 * Acceptance closed:
 *   - List of anchored days for the tenant
 *   - Click an anchor row -> downloads the raw RFC 3161 TSR DER bytes
 *     (US-F16 — "Accept: application/timestamp-reply returns DER bytes"
 *     mediated through the apiFetch helper; the link sets the Accept
 *     header and pipes the response into a Blob download.
 *   - Deferred anchors (no TSR yet) render with the deferred chip and
 *     no download button.
 *
 * The list is short (one row per anchored day; a year is at most 366
 * rows) so we don't paginate.
 */

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiFetch";
import { StatusChip } from "@/components/StatusChip";

export interface AnchorListItem {
  id: string;
  tenant_id: string;
  anchor_date: string;
  status: "anchored" | "deferred";
  root_hash: string | null;
  tsa_identifier: string;
  tsr_bytes_b64: string | null;
  tsa_signature_b64: string | null;
  timestamped_at: string | null;
  anchored_at: string;
}

export interface AnchorListResponse {
  tenant_id: string;
  items: AnchorListItem[];
  count: number;
}

type LoadState = "loading" | "ok" | "empty" | "error";

export interface AnchorsListProps {
  tenantId: string;
  apiUrl?: string;
  fetcher?: typeof fetch;
}

const DEFAULT_URL =
  /* v8 ignore next */
  process.env.NEXT_PUBLIC_FORENSA_API_URL ?? "http://localhost:8000";

export function AnchorsList({ tenantId, apiUrl, fetcher = apiFetch }: AnchorsListProps) {
  const [state, setState] = useState<LoadState>("loading");
  const [items, setItems] = useState<AnchorListItem[]>([]);
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [downloading, setDownloading] = useState<string | null>(null);

  const baseUrl = apiUrl ?? DEFAULT_URL;
  const listUrl = `${baseUrl}/v1/anchors?tenant_id=${encodeURIComponent(tenantId)}`;

  useEffect(() => {
    let cancelled = false;
    fetcher(listUrl)
      .then(async (r) => {
        /* v8 ignore next */
        if (cancelled) return;
        if (!r.ok) {
          setState("error");
          setErrorMsg(`HTTP ${r.status}`);
          return;
        }
        const body = (await r.json()) as AnchorListResponse;
        const fetched = body.items ?? [];
        setItems(fetched);
        setState(fetched.length === 0 ? "empty" : "ok");
      })
      .catch((e: Error) => {
        /* v8 ignore next */
        if (cancelled) return;
        setState("error");
        setErrorMsg(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [listUrl, fetcher]);

  const handleDownloadTsr = useCallback(
    async (anchor: AnchorListItem) => {
      setDownloading(anchor.id);
      try {
        const r = await fetcher(`${baseUrl}/v1/anchors/${anchor.id}`, {
          headers: { Accept: "application/timestamp-reply" },
        });
        if (!r.ok) {
          setErrorMsg(`TSR download HTTP ${r.status}`);
          return;
        }
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        const day = anchor.anchor_date.slice(0, 10);
        a.download = `forensa-anchor-${day}-${anchor.id.slice(0, 8)}.tsr`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      } catch (e) {
        setErrorMsg(`TSR download failed: ${(e as Error).message}`);
      } finally {
        setDownloading(null);
      }
    },
    [baseUrl, fetcher],
  );

  if (state === "loading")
    return <p data-testid="anchors-list-loading">Loading anchors…</p>;
  if (state === "error")
    return (
      <p data-testid="anchors-list-error" style={{ color: "#991b1b" }}>
        Error loading anchors: {errorMsg}
      </p>
    );
  if (state === "empty")
    return (
      <p data-testid="anchors-list-empty" style={{ color: "#374151" }}>
        No anchors yet for this tenant. The daily cron writes one
        per day with at least one signed receipt.
      </p>
    );

  return (
    <div data-testid="anchors-list">
      <table
        data-testid="anchors-table"
        style={{ borderCollapse: "collapse", width: "100%", fontSize: "0.9rem" }}
      >
        <thead>
          <tr style={{ background: "#f9fafb" }}>
            <th style={th}>Date</th>
            <th style={th}>Status</th>
            <th style={th}>TSA</th>
            <th style={th}>Timestamp</th>
            <th style={th}>Root hash</th>
            <th style={th} />
          </tr>
        </thead>
        <tbody>
          {items.map((a) => {
            const day = a.anchor_date.slice(0, 10);
            const isDownloading = downloading === a.id;
            const canDownload = a.status === "anchored" && a.tsr_bytes_b64 !== null;
            return (
              <tr
                key={a.id}
                data-testid={`anchor-row-${a.id}`}
                style={{ borderBottom: "1px solid #f3f4f6" }}
              >
                <td style={td}>{day}</td>
                <td style={td}>
                  <StatusChip status={a.status === "anchored" ? "anchored" : "deferred"} />
                </td>
                <td style={td}>{a.tsa_identifier}</td>
                <td style={td}>
                  {a.timestamped_at ? new Date(a.timestamped_at).toISOString() : "—"}
                </td>
                <td style={{ ...td, fontFamily: "monospace", fontSize: "0.75rem" }}>
                  {a.root_hash ? a.root_hash.slice(0, 16) + "…" : "—"}
                </td>
                <td style={td}>
                  {canDownload ? (
                    <button
                      type="button"
                      data-testid={`anchor-download-${a.id}`}
                      onClick={() => handleDownloadTsr(a)}
                      disabled={isDownloading}
                      style={{
                        padding: "0.3rem 0.6rem",
                        borderRadius: "0.3rem",
                        border: "1px solid #d1d5db",
                        background: isDownloading ? "#9ca3af" : "white",
                        color: "#374151",
                        cursor: isDownloading ? "wait" : "pointer",
                        fontSize: "0.8rem",
                      }}
                    >
                      {isDownloading ? "Downloading…" : "Download TSR"}
                    </button>
                  ) : (
                    <span
                      data-testid={`anchor-no-download-${a.id}`}
                      style={{ fontSize: "0.8rem", color: "#9ca3af" }}
                    >
                      (deferred)
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {errorMsg ? (
        <p
          data-testid="anchor-download-error"
          style={{ color: "#991b1b", marginTop: "0.75rem" }}
        >
          {errorMsg}
        </p>
      ) : null}
    </div>
  );
}

const th: React.CSSProperties = {
  textAlign: "left",
  padding: "0.5rem 0.75rem",
  borderBottom: "1px solid #e5e7eb",
  fontWeight: 600,
  color: "#374151",
};
const td: React.CSSProperties = {
  padding: "0.5rem 0.75rem",
  verticalAlign: "top",
};
