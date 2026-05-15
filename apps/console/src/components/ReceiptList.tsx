"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiFetch";

export interface ReceiptListItem {
  id: string;
  tenant_id: string;
  event_id: string;
  policy_bundle_id: string;
  sequence: number;
  prev_receipt_hash: string | null;
  payload_hash: string;
  receipt_hash: string;
  signature_b64: string;
  signed_at: string;
}

export interface ReceiptListResponse {
  items: ReceiptListItem[];
  tenant_id: string;
  limit: number;
  offset: number;
  count: number;
}

type LoadState = "loading" | "ok" | "empty" | "error";

export interface ReceiptListProps {
  tenantId: string;
  apiUrl?: string;
  fetcher?: typeof fetch;
  limit?: number;
}

const DEFAULT_URL =
  /* v8 ignore next */
  process.env.NEXT_PUBLIC_FORENSA_API_URL ?? "http://localhost:8000";

export function ReceiptList({ tenantId, apiUrl, fetcher = apiFetch, limit = 50 }: ReceiptListProps) {
  const [state, setState] = useState<LoadState>("loading");
  const [items, setItems] = useState<ReceiptListItem[]>([]);
  const [errorMsg, setErrorMsg] = useState<string>("");

  const url =
    (apiUrl ?? DEFAULT_URL) +
    `/v1/receipts?tenant_id=${encodeURIComponent(tenantId)}&limit=${limit}`;

  useEffect(() => {
    let cancelled = false;
    fetcher(url)
      .then(async (r) => {
        /* v8 ignore next */
        if (cancelled) return;
        if (!r.ok) {
          setState("error");
          setErrorMsg(`HTTP ${r.status}`);
          return;
        }
        const body = (await r.json()) as ReceiptListResponse;
        setItems(body.items);
        setState(body.items.length === 0 ? "empty" : "ok");
      })
      .catch((e: Error) => {
        /* v8 ignore next */
        if (cancelled) return;
        setState("error");
        setErrorMsg(e.message);
      });
    return () => { cancelled = true; };
  }, [url, fetcher]);

  if (state === "loading") {
    return <p data-testid="receipt-list-loading">Loading receipts...</p>;
  }
  if (state === "error") {
    return (
      <p data-testid="receipt-list-error" style={{ color: "#991b1b" }}>
        Error loading receipts: {errorMsg}
      </p>
    );
  }
  if (state === "empty") {
    return <p data-testid="receipt-list-empty">No receipts yet for this tenant.</p>;
  }
  return (
    <table data-testid="receipt-list-table" style={{ borderCollapse: "collapse", width: "100%" }}>
      <thead>
        <tr>
          <th style={{ textAlign: "left", padding: "0.5rem", borderBottom: "1px solid #e5e7eb" }}>Seq</th>
          <th style={{ textAlign: "left", padding: "0.5rem", borderBottom: "1px solid #e5e7eb" }}>Receipt id</th>
          <th style={{ textAlign: "left", padding: "0.5rem", borderBottom: "1px solid #e5e7eb" }}>Event id</th>
          <th style={{ textAlign: "left", padding: "0.5rem", borderBottom: "1px solid #e5e7eb" }}>Signed at</th>
          <th style={{ textAlign: "left", padding: "0.5rem", borderBottom: "1px solid #e5e7eb" }}>Hash (head)</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.id} data-testid={`receipt-row-${item.id}`} style={{ cursor: "pointer" }} onClick={() => { window.location.href = `/receipts/${item.id}`; }}>
            <td style={{ padding: "0.5rem", borderBottom: "1px solid #f3f4f6" }}>{item.sequence}</td>
            <td style={{ padding: "0.5rem", borderBottom: "1px solid #f3f4f6", fontFamily: "monospace", fontSize: "0.85rem" }}>{item.id}</td>
            <td style={{ padding: "0.5rem", borderBottom: "1px solid #f3f4f6", fontFamily: "monospace", fontSize: "0.85rem" }}>{item.event_id}</td>
            <td style={{ padding: "0.5rem", borderBottom: "1px solid #f3f4f6", fontSize: "0.85rem" }}>{new Date(item.signed_at).toISOString()}</td>
            <td style={{ padding: "0.5rem", borderBottom: "1px solid #f3f4f6", fontFamily: "monospace", fontSize: "0.85rem" }}>{item.receipt_hash.slice(0, 16)}...</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
