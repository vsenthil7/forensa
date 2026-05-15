"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiFetch";

export interface ReceiptDetail {
  id: string;
  tenant_id: string;
  event_id: string;
  policy_bundle_id: string;
  policy_snapshot_id: string;
  sequence: number;
  prev_receipt_hash: string | null;
  payload_hash: string;
  receipt_hash: string;
  signature_b64: string;
  signed_at: string;
  recomputed_receipt_hash: string;
  integrity_ok: boolean;
}

type LoadState = "loading" | "ok" | "not-found" | "error";

export interface ReceiptDetailProps {
  receiptId: string;
  apiUrl?: string;
  fetcher?: typeof fetch;
}

const DEFAULT_URL =
  /* v8 ignore next */
  process.env.NEXT_PUBLIC_FORENSA_API_URL ?? "http://localhost:8000";

export function ReceiptDetail({ receiptId, apiUrl, fetcher = apiFetch }: ReceiptDetailProps) {
  const [state, setState] = useState<LoadState>("loading");
  const [data, setData] = useState<ReceiptDetail | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");

  const url = (apiUrl ?? DEFAULT_URL) + `/v1/receipts/${encodeURIComponent(receiptId)}`;

  useEffect(() => {
    let cancelled = false;
    fetcher(url)
      .then(async (r) => {
        /* v8 ignore next */
        if (cancelled) return;
        if (r.status === 404) {
          setState("not-found");
          return;
        }
        if (!r.ok) {
          setState("error");
          setErrorMsg(`HTTP ${r.status}`);
          return;
        }
        const body = (await r.json()) as ReceiptDetail;
        setData(body);
        setState("ok");
      })
      .catch((e: Error) => {
        /* v8 ignore next */
        if (cancelled) return;
        setState("error");
        setErrorMsg(e.message);
      });
    return () => { cancelled = true; };
  }, [url, fetcher]);

  if (state === "loading") return <p data-testid="receipt-detail-loading">Loading receipt...</p>;
  if (state === "not-found") return <p data-testid="receipt-detail-not-found">Receipt not found.</p>;
  if (state === "error")
    return (
      <p data-testid="receipt-detail-error" style={{ color: "#991b1b" }}>
        Error loading receipt: {errorMsg}
      </p>
    );
  /* v8 ignore next */
  if (!data) return null;

  const integrityColor = data.integrity_ok ? "#065f46" : "#991b1b";
  const integrityBg = data.integrity_ok ? "#d1fae5" : "#fee2e2";

  return (
    <article data-testid="receipt-detail">
      <div
        data-testid="integrity-badge"
        data-integrity-ok={String(data.integrity_ok)}
        style={{ display: "inline-block", padding: "0.5rem 1rem", borderRadius: "0.5rem", backgroundColor: integrityBg, color: integrityColor, fontWeight: 600, marginBottom: "1rem" }}
      >
        {data.integrity_ok ? "Chain integrity verified" : "TAMPER DETECTED - hash mismatch"}
      </div>
      <dl style={{ display: "grid", gridTemplateColumns: "max-content 1fr", gap: "0.5rem 1rem", fontSize: "0.9rem" }}>
        <dt>Receipt id</dt><dd data-testid="detail-id" style={{ fontFamily: "monospace" }}>{data.id}</dd>
        <dt>Tenant</dt><dd style={{ fontFamily: "monospace" }}>{data.tenant_id}</dd>
        <dt>Event id</dt><dd style={{ fontFamily: "monospace" }}>{data.event_id}</dd>
        <dt>Sequence</dt><dd data-testid="detail-sequence">{data.sequence}</dd>
        <dt>Signed at</dt><dd>{new Date(data.signed_at).toISOString()}</dd>
        <dt>Payload hash</dt><dd data-testid="detail-payload-hash" style={{ fontFamily: "monospace", wordBreak: "break-all" }}>{data.payload_hash}</dd>
        <dt>Receipt hash</dt><dd data-testid="detail-receipt-hash" style={{ fontFamily: "monospace", wordBreak: "break-all" }}>{data.receipt_hash}</dd>
        <dt>Recomputed hash</dt><dd data-testid="detail-recomputed-hash" style={{ fontFamily: "monospace", wordBreak: "break-all" }}>{data.recomputed_receipt_hash}</dd>
        <dt>Previous hash</dt><dd data-testid="detail-prev-hash" style={{ fontFamily: "monospace", wordBreak: "break-all" }}>{data.prev_receipt_hash ?? "(genesis)"}</dd>
        <dt>Policy snapshot</dt><dd style={{ fontFamily: "monospace" }}>{data.policy_snapshot_id}</dd>
        <dt>Policy bundle</dt><dd style={{ fontFamily: "monospace" }}>{data.policy_bundle_id}</dd>
        <dt>Signature</dt><dd style={{ fontFamily: "monospace", wordBreak: "break-all", fontSize: "0.75rem" }}>{data.signature_b64}</dd>
      </dl>
    </article>
  );
}
