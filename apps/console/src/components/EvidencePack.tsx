"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/apiFetch";

/**
 * EvidencePack - the "produce" side of Forensa's regulator workflow.
 *
 * Matches auditex's sign-report pattern: clicking "Generate" calls
 * GET /v1/evidence-packs with the tenant + scope window, displays the
 * returned JSON-LD pack (root_hash, receipt count, anchor TSA proof
 * if present), and exposes a "Download PDF" button that fetches the
 * same endpoint with Accept: application/pdf for the regulator-grade
 * A4 rendering.
 *
 * The demo's STEP 3 (CP9.50) opens this page and clicks Generate to
 * produce the cryptographic artifact (1 of 2 ops per auditex parity).
 * STEP 2 (receipt detail) is the verify op. STEP 1 (chain view) is
 * just product surface, not a verification.
 */

export interface AnchorEvidence {
  anchor_id: string;
  anchor_date: string;
  status: "anchored" | "deferred";
  root_hash: string | null;
  tsa_identifier: string;
  tsr_bytes_b64: string | null;
  tsa_signature_b64: string | null;
  timestamped_at: string | null;
  anchored_at: string;
}

export interface EvidencePackHeader {
  pack_id: string;
  tenant_id: string;
  generated_at: string;
  scope_start: string;
  scope_end: string;
  receipt_count: number;
}

export interface EvidencePackResponse {
  "@context": string;
  "@type": "forensa:EvidencePack";
  header: EvidencePackHeader;
  receipts: Array<{ id: string; sequence: number; receipt_hash: string }>;
  activities: unknown[];
  anchor: AnchorEvidence | null;
  root_hash: string;
}

type LoadState = "idle" | "loading" | "ok" | "error";

export interface EvidencePackProps {
  tenantId: string;
  scopeStart: string; // ISO 8601 with tz
  scopeEnd: string; // ISO 8601 with tz
  apiUrl?: string;
  fetcher?: typeof fetch;
}

const DEFAULT_URL =
  /* v8 ignore next */
  process.env.NEXT_PUBLIC_FORENSA_API_URL ?? "http://localhost:8000";

export function EvidencePack({ tenantId, scopeStart, scopeEnd, apiUrl, fetcher = apiFetch }: EvidencePackProps) {
  const [state, setState] = useState<LoadState>("idle");
  const [pack, setPack] = useState<EvidencePackResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [downloading, setDownloading] = useState(false);

  const baseUrl =
    (apiUrl ?? DEFAULT_URL) +
    `/v1/evidence-packs?tenant_id=${encodeURIComponent(tenantId)}` +
    `&scope_start=${encodeURIComponent(scopeStart)}` +
    `&scope_end=${encodeURIComponent(scopeEnd)}`;

  const handleGenerate = async () => {
    setState("loading");
    setErrorMsg("");
    try {
      const r = await fetcher(baseUrl);
      if (!r.ok) {
        setState("error");
        setErrorMsg(`HTTP ${r.status}`);
        return;
      }
      const body = (await r.json()) as EvidencePackResponse;
      setPack(body);
      setState("ok");
    } catch (e) {
      /* v8 ignore next 3 */
      setState("error");
      setErrorMsg((e as Error).message);
    }
  };

  const handleDownloadPdf = async () => {
    setDownloading(true);
    try {
      const r = await fetcher(baseUrl, { headers: { Accept: "application/pdf" } });
      if (!r.ok) {
        setErrorMsg(`PDF download HTTP ${r.status}`);
        return;
      }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const rootHead = (pack?.root_hash ?? "pack").slice(0, 12);
      a.download = `forensa-evidence-pack-${rootHead}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      /* v8 ignore next 2 */
      setErrorMsg(`PDF download failed: ${(e as Error).message}`);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <article data-testid="evidence-pack-page">
      <p style={{ fontSize: "0.9rem", color: "#6b7280", marginBottom: "1rem" }}>
        Regulator-ready evidence pack covering the chain in window{" "}
        <code style={{ fontFamily: "monospace" }}>{scopeStart.slice(0, 10)}</code> to{" "}
        <code style={{ fontFamily: "monospace" }}>{scopeEnd.slice(0, 10)}</code>.
      </p>

      {state === "idle" && (
        <button
          data-testid="generate-pack-button"
          type="button"
          onClick={handleGenerate}
          style={{
            padding: "0.75rem 1.5rem",
            borderRadius: "0.5rem",
            backgroundColor: "#1e40af",
            color: "white",
            border: "none",
            fontWeight: 600,
            cursor: "pointer",
            fontSize: "1rem",
          }}
        >
          Generate evidence pack
        </button>
      )}

      {state === "loading" && (
        <p data-testid="pack-loading">Building evidence pack...</p>
      )}

      {state === "error" && (
        <p data-testid="pack-error" style={{ color: "#991b1b" }}>
          Error: {errorMsg}
        </p>
      )}

      {state === "ok" && pack && (
        <section data-testid="pack-display">
          <div
            data-testid="pack-signed-badge"
            style={{
              display: "inline-block",
              padding: "0.5rem 1rem",
              borderRadius: "0.5rem",
              backgroundColor: "#d1fae5",
              color: "#065f46",
              fontWeight: 600,
              marginBottom: "1rem",
            }}
          >
            Evidence pack signed
          </div>

          <dl
            style={{
              display: "grid",
              gridTemplateColumns: "max-content 1fr",
              gap: "0.5rem 1rem",
              fontSize: "0.9rem",
            }}
          >
            <dt>Pack id</dt>
            <dd data-testid="pack-id" style={{ fontFamily: "monospace" }}>
              {pack.header.pack_id}
            </dd>

            <dt>Root hash</dt>
            <dd
              data-testid="pack-root-hash"
              style={{ fontFamily: "monospace", wordBreak: "break-all" }}
            >
              {pack.root_hash}
            </dd>

            <dt>Receipt count</dt>
            <dd data-testid="pack-receipt-count">{pack.header.receipt_count}</dd>

            <dt>Generated at</dt>
            <dd>{new Date(pack.header.generated_at).toISOString()}</dd>

            <dt>Scope</dt>
            <dd>
              {new Date(pack.header.scope_start).toISOString()} &rarr;{" "}
              {new Date(pack.header.scope_end).toISOString()}
            </dd>

            {pack.anchor && (
              <>
                <dt>RFC 3161 anchor</dt>
                <dd
                  data-testid="pack-anchor-tsa"
                  style={{ fontFamily: "monospace" }}
                >
                  {pack.anchor.tsa_identifier}
                  {pack.anchor.status === "anchored" ? " (anchored)" : " (deferred)"}
                </dd>

                <dt>TSA timestamp</dt>
                <dd data-testid="pack-anchor-time">
                  {pack.anchor.timestamped_at
                    ? new Date(pack.anchor.timestamped_at).toISOString()
                    : "(pending)"}
                </dd>

                {pack.anchor.tsr_bytes_b64 && (
                  <>
                    <dt>TSR bytes</dt>
                    <dd data-testid="pack-tsr-bytes" style={{ fontSize: "0.75rem", color: "#6b7280" }}>
                      {Math.floor((pack.anchor.tsr_bytes_b64.length * 3) / 4)} bytes of ASN.1 DER
                    </dd>
                  </>
                )}
              </>
            )}
          </dl>

          <div style={{ marginTop: "1.5rem" }}>
            <button
              data-testid="download-pdf-button"
              type="button"
              onClick={handleDownloadPdf}
              disabled={downloading}
              style={{
                padding: "0.5rem 1rem",
                borderRadius: "0.5rem",
                backgroundColor: downloading ? "#9ca3af" : "#065f46",
                color: "white",
                border: "none",
                fontWeight: 600,
                cursor: downloading ? "wait" : "pointer",
              }}
            >
              {downloading ? "Building PDF..." : "Download PDF for regulator"}
            </button>
            {errorMsg && (
              <p data-testid="pdf-error" style={{ color: "#991b1b", marginTop: "0.5rem" }}>
                {errorMsg}
              </p>
            )}
          </div>
        </section>
      )}
    </article>
  );
}
