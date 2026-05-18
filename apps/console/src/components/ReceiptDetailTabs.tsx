"use client";

/**
 * Forensa Console — receipt detail with tabbed view (US-F30, SCR-F03).
 *
 * Acceptance criteria closed:
 *   AC-1 Summary tab default with plain English
 *   AC-2 Proof tab with prev -> current hash visual
 *   AC-3 Raw tab with copy-to-clipboard
 *
 * Architecture
 * ------------
 *   ReceiptDetailTabs owns the tab state + data fetch and renders
 *   one of three tab bodies. The data shape is identical to the
 *   one ReceiptDetail (the v1 single-pane view) already consumes;
 *   the v1 component is preserved at the path `ReceiptDetail.tsx`
 *   and its tests still pass.
 *
 * Tab routing
 * -----------
 *   The active tab is mirrored in the URL hash (`#summary`,
 *   `#proof`, `#raw`) so that deep links + back button work
 *   without sessionStorage. Per BR-14 AC-2 list-views-as-top-nav
 *   the page itself is reachable from the top-nav at any time.
 */

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiFetch";

export interface ReceiptDetailData {
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
  /** Optional enrichments. */
  agent_id?: string | null;
  policy_outcome?: string | null;
}

export type DetailTab = "summary" | "proof" | "raw";

const TABS: ReadonlyArray<{ id: DetailTab; label: string; testid: string }> = [
  { id: "summary", label: "Summary", testid: "tab-summary" },
  { id: "proof", label: "Cryptographic proof", testid: "tab-proof" },
  { id: "raw", label: "Raw JSON", testid: "tab-raw" },
];

type LoadState = "loading" | "ok" | "not-found" | "error";

export interface ReceiptDetailTabsProps {
  receiptId: string;
  apiUrl?: string;
  fetcher?: typeof fetch;
  /** Initial tab; defaults to "summary" per AC-1. */
  initialTab?: DetailTab;
  /** Called when the user changes tab; the page can mirror to URL hash. */
  onTabChange?: (tab: DetailTab) => void;
  /** Injectable clipboard for tests; defaults to navigator.clipboard. */
  clipboard?: { writeText: (s: string) => Promise<void> };
}

const DEFAULT_URL =
  /* v8 ignore next */
  process.env.NEXT_PUBLIC_FORENSA_API_URL ?? "http://localhost:8000";

export function parseTabFromHash(hash: string): DetailTab {
  const stripped = hash.startsWith("#") ? hash.slice(1) : hash;
  if (stripped === "proof" || stripped === "raw") return stripped;
  return "summary";
}

export function ReceiptDetailTabs({
  receiptId,
  apiUrl,
  fetcher = apiFetch,
  initialTab = "summary",
  onTabChange,
  clipboard,
}: ReceiptDetailTabsProps) {
  const [tab, setTab] = useState<DetailTab>(initialTab);
  const [state, setState] = useState<LoadState>("loading");
  const [data, setData] = useState<ReceiptDetailData | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [copied, setCopied] = useState<boolean>(false);

  const url =
    (apiUrl ?? DEFAULT_URL) + `/v1/receipts/${encodeURIComponent(receiptId)}`;

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
        const body = (await r.json()) as ReceiptDetailData;
        setData(body);
        setState("ok");
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
  }, [url, fetcher]);

  const handleTabClick = useCallback(
    (next: DetailTab) => {
      setTab(next);
      if (onTabChange) onTabChange(next);
    },
    [onTabChange],
  );

  const handleCopy = useCallback(async () => {
    /* v8 ignore next */
    if (!data) return;
    const text = JSON.stringify(data, null, 2);
    const clip = clipboard ?? navigator.clipboard;
    /* v8 ignore start */
    if (!clip) {
      setCopied(false);
      return;
    }
    /* v8 ignore stop */
    try {
      await clip.writeText(text);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }, [data, clipboard]);

  if (state === "loading")
    return <p data-testid="receipt-detail-tabs-loading">Loading receipt…</p>;
  if (state === "not-found")
    return <p data-testid="receipt-detail-tabs-not-found">Receipt not found.</p>;
  if (state === "error")
    return (
      <p data-testid="receipt-detail-tabs-error" style={{ color: "#991b1b" }}>
        Error loading receipt: {errorMsg}
      </p>
    );
  /* v8 ignore next */
  if (!data) return null;

  return (
    <section data-testid="receipt-detail-tabs">
      <div role="tablist" aria-label="Receipt sections" style={{ display: "flex", gap: "0.25rem", borderBottom: "1px solid #e5e7eb" }}>
        {TABS.map((t) => {
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              role="tab"
              type="button"
              aria-selected={active}
              data-testid={t.testid}
              data-active={active ? "true" : "false"}
              onClick={() => handleTabClick(t.id)}
              style={{
                padding: "0.5rem 1rem",
                background: active ? "white" : "transparent",
                border: "1px solid transparent",
                borderColor: active ? "#e5e7eb" : "transparent",
                borderBottomColor: active ? "white" : "transparent",
                marginBottom: "-1px",
                fontWeight: active ? 600 : 500,
                color: active ? "#1e40af" : "#374151",
                cursor: "pointer",
                borderTopLeftRadius: "0.4rem",
                borderTopRightRadius: "0.4rem",
              }}
            >
              {t.label}
            </button>
          );
        })}
      </div>
      <div
        role="tabpanel"
        data-testid={`tabpanel-${tab}`}
        style={{ padding: "1.25rem 0" }}
      >
        {tab === "summary" ? (
          <SummaryPane data={data} />
        ) : tab === "proof" ? (
          <ProofPane data={data} />
        ) : (
          <RawPane data={data} onCopy={handleCopy} copied={copied} />
        )}
      </div>
    </section>
  );
}

function SummaryPane({ data }: { data: ReceiptDetailData }) {
  const when = new Date(data.signed_at).toISOString();
  const outcome = data.policy_outcome ?? "unspecified";
  const agent = data.agent_id ?? "unspecified agent";
  return (
    <div data-testid="summary-pane" style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      <p style={{ fontSize: "1rem", lineHeight: 1.5, margin: 0 }}>
        On <strong>{when}</strong>, <strong>{agent}</strong> took an action whose
        policy outcome was <strong>{outcome}</strong>. The action is sequenced
        as <strong>#{data.sequence}</strong> in this tenant&apos;s evidence chain
        and was sealed against the tenant signing key. Open the
        <em> Cryptographic proof </em> tab to inspect the chain link or
        <em> Raw JSON </em> to copy the full receipt.
      </p>
      <p
        data-testid="summary-integrity-line"
        data-integrity-ok={String(data.integrity_ok)}
        style={{
          margin: 0,
          padding: "0.5rem 0.75rem",
          borderRadius: "0.4rem",
          background: data.integrity_ok ? "#dcfce7" : "#fee2e2",
          color: data.integrity_ok ? "#166534" : "#991b1b",
          fontWeight: 600,
        }}
      >
        {data.integrity_ok
          ? "Chain integrity verified: recomputed hash matches stored hash."
          : "TAMPER DETECTED: recomputed hash does not match stored hash."}
      </p>
    </div>
  );
}

function ProofPane({ data }: { data: ReceiptDetailData }) {
  const prev = data.prev_receipt_hash ?? "(genesis — no predecessor)";
  return (
    <div data-testid="proof-pane" style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr auto 1fr",
          gap: "0.5rem",
          alignItems: "center",
        }}
      >
        <HashBox label="Previous receipt hash" testid="proof-prev" value={prev} />
        <span style={{ fontSize: "1.5rem", color: "#9ca3af" }}>→</span>
        <HashBox
          label="This receipt hash"
          testid="proof-current"
          value={data.receipt_hash}
          highlight
        />
      </div>
      <dl style={{ display: "grid", gridTemplateColumns: "max-content 1fr", gap: "0.5rem 1rem", fontSize: "0.9rem", margin: 0 }}>
        <dt>Payload hash</dt>
        <dd data-testid="proof-payload-hash" style={{ fontFamily: "monospace", wordBreak: "break-all", margin: 0 }}>
          {data.payload_hash}
        </dd>
        <dt>Recomputed hash</dt>
        <dd data-testid="proof-recomputed-hash" style={{ fontFamily: "monospace", wordBreak: "break-all", margin: 0 }}>
          {data.recomputed_receipt_hash}
        </dd>
        <dt>Signature (b64)</dt>
        <dd data-testid="proof-signature" style={{ fontFamily: "monospace", wordBreak: "break-all", fontSize: "0.75rem", margin: 0 }}>
          {data.signature_b64}
        </dd>
        <dt>Policy snapshot</dt>
        <dd style={{ fontFamily: "monospace", margin: 0 }}>{data.policy_snapshot_id}</dd>
      </dl>
    </div>
  );
}

function HashBox({
  label,
  value,
  testid,
  highlight,
}: {
  label: string;
  value: string;
  testid: string;
  highlight?: boolean;
}) {
  return (
    <div
      data-testid={testid}
      style={{
        padding: "0.6rem 0.75rem",
        borderRadius: "0.4rem",
        background: highlight ? "#eff6ff" : "#f9fafb",
        border: highlight ? "1px solid #bfdbfe" : "1px solid #e5e7eb",
      }}
    >
      <div style={{ fontSize: "0.75rem", color: "#6b7280", marginBottom: "0.25rem" }}>
        {label}
      </div>
      <code
        style={{
          fontFamily: "monospace",
          fontSize: "0.75rem",
          wordBreak: "break-all",
          color: "#111827",
        }}
      >
        {value}
      </code>
    </div>
  );
}

function RawPane({
  data,
  onCopy,
  copied,
}: {
  data: ReceiptDetailData;
  onCopy: () => void;
  copied: boolean;
}) {
  const json = JSON.stringify(data, null, 2);
  return (
    <div data-testid="raw-pane" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: "0.85rem", color: "#6b7280" }}>
          Raw receipt JSON ({json.length.toLocaleString()} chars)
        </span>
        <button
          type="button"
          data-testid="raw-copy"
          onClick={onCopy}
          style={{
            padding: "0.35rem 0.7rem",
            borderRadius: "0.35rem",
            border: "1px solid #d1d5db",
            background: copied ? "#dcfce7" : "white",
            color: copied ? "#166534" : "#374151",
            fontWeight: 500,
            cursor: "pointer",
            fontSize: "0.85rem",
          }}
        >
          {copied ? "Copied ✓" : "Copy to clipboard"}
        </button>
      </div>
      <pre
        data-testid="raw-json"
        style={{
          padding: "0.75rem",
          background: "#0f172a",
          color: "#e2e8f0",
          borderRadius: "0.4rem",
          overflowX: "auto",
          fontSize: "0.78rem",
          lineHeight: 1.45,
          fontFamily: "monospace",
          margin: 0,
        }}
      >
        {json}
      </pre>
    </div>
  );
}


