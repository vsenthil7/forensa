"use client";

/**
 * Forensa Console — evidence pack with Compliance/Technical toggle
 * (US-F19, SCR-F04).
 *
 * Acceptance:
 *   Compliance view (default): plain English summary + big Download
 *   PDF CTA. No hex hashes visible.
 *   Technical view: full JSON-LD pack as today.
 *
 * Narrated loading (BR-14 AC-2 + UC-09 paragraph): while the pack
 * builds, show stepwise human-readable progress ("Collecting
 * receipts...", "Computing root hash...", "Anchoring with FreeTSA...",
 * "Sealing evidence...") rather than a generic spinner.
 *
 * Architecture
 * ------------
 *   This component wraps EvidencePack rather than replacing it.
 *   The legacy `EvidencePack` component is preserved as-is so its
 *   existing test suite continues to pass; this wrapper drives it
 *   in technical mode and renders a separate compliance-view
 *   summary in compliance mode.
 */

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/apiFetch";
import type { EvidencePackResponse } from "@/components/EvidencePack";

export type EvidenceView = "compliance" | "technical";

export interface EvidencePackToggleProps {
  tenantId: string;
  scopeStart: string;
  scopeEnd: string;
  apiUrl?: string;
  fetcher?: typeof fetch;
  initialView?: EvidenceView;
  /** Step delay for narrated loading, ms. Lower in tests. */
  stepDelayMs?: number;
}

const DEFAULT_URL =
  /* v8 ignore next */
  process.env.NEXT_PUBLIC_FORENSA_API_URL ?? "http://localhost:8000";

type LoadState = "idle" | "loading" | "ok" | "error";

const NARRATIVE_STEPS = [
  "Collecting receipts in the requested window…",
  "Hashing each receipt and chaining…",
  "Computing the evidence-pack root hash…",
  "Reading the RFC 3161 anchor from FreeTSA…",
  "Sealing the pack for regulator handover…",
] as const;

export function EvidencePackToggle({
  tenantId,
  scopeStart,
  scopeEnd,
  apiUrl,
  fetcher = apiFetch,
  initialView = "compliance",
  stepDelayMs = 350,
}: EvidencePackToggleProps) {
  const [view, setView] = useState<EvidenceView>(initialView);
  const [state, setState] = useState<LoadState>("idle");
  const [pack, setPack] = useState<EvidencePackResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [narrativeIdx, setNarrativeIdx] = useState<number>(0);
  const [downloading, setDownloading] = useState<boolean>(false);

  const baseUrl =
    (apiUrl ?? DEFAULT_URL) +
    `/v1/evidence-packs?tenant_id=${encodeURIComponent(tenantId)}` +
    `&scope_start=${encodeURIComponent(scopeStart)}` +
    `&scope_end=${encodeURIComponent(scopeEnd)}`;

  // Narrated loading: advance the step counter while loading.
  useEffect(() => {
    if (state !== "loading") return;
    const id = setInterval(() => {
      setNarrativeIdx((i) => (i + 1 < NARRATIVE_STEPS.length ? i + 1 : i));
    }, stepDelayMs);
    return () => clearInterval(id);
  }, [state, stepDelayMs]);

  const handleGenerate = async () => {
    setState("loading");
    setErrorMsg("");
    setNarrativeIdx(0);
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
      // pack is guaranteed non-null here: the Download button is only
      // rendered inside the `pack ? ... : null` branch below.
      /* v8 ignore next */
      if (!pack) return;
      const rootHead = pack.root_hash.slice(0, 12);
      a.download = `forensa-evidence-pack-${rootHead}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErrorMsg(`PDF download failed: ${(e as Error).message}`);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <article data-testid="evidence-pack-toggle">
      <ViewSwitcher view={view} onChange={setView} />
      <p style={{ fontSize: "0.9rem", color: "#6b7280", marginBottom: "1rem" }}>
        Evidence window{" "}
        <code style={{ fontFamily: "monospace" }}>{scopeStart.slice(0, 10)}</code> to{" "}
        <code style={{ fontFamily: "monospace" }}>{scopeEnd.slice(0, 10)}</code>.
      </p>

      {state === "idle" ? (
        <button
          data-testid="generate-pack-button"
          type="button"
          onClick={handleGenerate}
          style={primaryCta}
        >
          {view === "compliance" ? "Build evidence pack for FCA" : "Generate evidence pack"}
        </button>
      ) : state === "loading" ? (
        <NarratedLoading idx={narrativeIdx} />
      ) : state === "error" ? (
        <p data-testid="pack-error" style={{ color: "#991b1b" }}>
          Error: {errorMsg}
        </p>
      ) : pack ? (
        view === "compliance" ? (
          <ComplianceView
            pack={pack}
            onDownload={handleDownloadPdf}
            downloading={downloading}
            errorMsg={errorMsg}
          />
        ) : (
          <TechnicalView
            pack={pack}
            onDownload={handleDownloadPdf}
            downloading={downloading}
            errorMsg={errorMsg}
          />
        )
      ) : /* v8 ignore next */ null}
    </article>
  );
}

function ViewSwitcher({
  view,
  onChange,
}: {
  view: EvidenceView;
  onChange: (v: EvidenceView) => void;
}) {
  return (
    <div
      role="tablist"
      aria-label="Evidence view"
      data-testid="evidence-view-switcher"
      style={{
        display: "inline-flex",
        gap: "0.25rem",
        padding: "0.2rem",
        background: "#f3f4f6",
        borderRadius: "0.5rem",
        marginBottom: "1rem",
      }}
    >
      {(["compliance", "technical"] as const).map((v) => (
        <button
          key={v}
          role="tab"
          type="button"
          aria-selected={view === v}
          data-testid={`view-${v}`}
          data-active={view === v ? "true" : "false"}
          onClick={() => onChange(v)}
          style={{
            padding: "0.35rem 0.85rem",
            borderRadius: "0.35rem",
            border: "none",
            background: view === v ? "white" : "transparent",
            color: view === v ? "#1e40af" : "#374151",
            fontWeight: view === v ? 600 : 500,
            cursor: "pointer",
            fontSize: "0.85rem",
            boxShadow: view === v ? "0 1px 2px rgba(0,0,0,0.05)" : "none",
          }}
        >
          {v === "compliance" ? "Compliance view" : "Technical view"}
        </button>
      ))}
    </div>
  );
}

function NarratedLoading({ idx }: { idx: number }) {
  return (
    <div
      data-testid="pack-narrated-loading"
      aria-busy="true"
      role="status"
      style={{
        padding: "1.25rem",
        border: "1px solid #e5e7eb",
        borderRadius: "0.5rem",
        background: "#f9fafb",
      }}
    >
      <p style={{ marginTop: 0, fontWeight: 600 }}>Building evidence pack…</p>
      <ol style={{ paddingLeft: "1.2rem", margin: 0, lineHeight: 1.7 }}>
        {NARRATIVE_STEPS.map((step, i) => {
          const done = i < idx;
          const current = i === idx;
          return (
            <li
              key={step}
              data-testid={`narrative-step-${i}`}
              data-state={done ? "done" : current ? "current" : "pending"}
              style={{
                color: done ? "#166534" : current ? "#1e40af" : "#9ca3af",
                fontWeight: current ? 600 : 400,
              }}
            >
              {done ? "✓ " : current ? "→ " : "  "}
              {step}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

interface ViewProps {
  pack: EvidencePackResponse;
  onDownload: () => void;
  downloading: boolean;
  errorMsg: string;
}

function ComplianceView({ pack, onDownload, downloading, errorMsg }: ViewProps) {
  const window = `${pack.header.scope_start.slice(0, 10)} → ${pack.header.scope_end.slice(0, 10)}`;
  const anchorState = pack.anchor
    ? pack.anchor.status === "anchored"
      ? `time-stamped by ${pack.anchor.tsa_identifier}`
      : `time-stamp deferred (will anchor on next cycle)`
    : "not yet time-stamped";
  return (
    <section data-testid="compliance-view">
      <div
        data-testid="compliance-headline"
        style={{
          padding: "1rem",
          borderRadius: "0.5rem",
          background: "#dcfce7",
          color: "#166534",
          marginBottom: "1rem",
          fontWeight: 600,
        }}
      >
        Evidence pack ready for regulator handover.
      </div>
      <p style={{ fontSize: "1rem", lineHeight: 1.55 }}>
        This pack covers <strong>{pack.header.receipt_count}</strong> signed agent
        actions in the window <strong>{window}</strong>. Every action is
        chained to the previous one and the chain is{" "}
        <strong>{anchorState}</strong>. Hand the PDF below to the FCA reviewer;
        no further preparation is required.
      </p>
      <button
        data-testid="download-pdf-button"
        type="button"
        onClick={onDownload}
        disabled={downloading}
        style={{
          ...primaryCta,
          background: downloading ? "#9ca3af" : "#065f46",
          cursor: downloading ? "wait" : "pointer",
          marginTop: "0.5rem",
        }}
      >
        {downloading ? "Building PDF…" : "Download PDF for FCA"}
      </button>
      {errorMsg ? (
        <p data-testid="pdf-error" style={{ color: "#991b1b", marginTop: "0.5rem" }}>
          {errorMsg}
        </p>
      ) : null}
      <p
        data-testid="compliance-need-tech"
        style={{ marginTop: "1rem", fontSize: "0.85rem", color: "#6b7280" }}
      >
        Need the hashes for your forensics team? Switch to Technical view.
      </p>
    </section>
  );
}

function TechnicalView({ pack, onDownload, downloading, errorMsg }: ViewProps) {
  return (
    <section data-testid="technical-view">
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
        {pack.anchor ? (
          <>
            <dt>Anchor</dt>
            <dd data-testid="pack-anchor-tsa">
              {pack.anchor.tsa_identifier} ({pack.anchor.status})
            </dd>
            <dt>TSA timestamp</dt>
            <dd data-testid="pack-anchor-time">
              {pack.anchor.timestamped_at
                ? new Date(pack.anchor.timestamped_at).toISOString()
                : "(pending)"}
            </dd>
          </>
        ) : null}
      </dl>
      <div style={{ marginTop: "1rem" }}>
        <button
          data-testid="download-pdf-button"
          type="button"
          onClick={onDownload}
          disabled={downloading}
          style={{
            ...primaryCta,
            background: downloading ? "#9ca3af" : "#065f46",
            cursor: downloading ? "wait" : "pointer",
          }}
        >
          {downloading ? "Building PDF…" : "Download PDF"}
        </button>
        {errorMsg ? (
          <p data-testid="pdf-error" style={{ color: "#991b1b", marginTop: "0.5rem" }}>
            {errorMsg}
          </p>
        ) : null}
      </div>
    </section>
  );
}

const primaryCta: React.CSSProperties = {
  padding: "0.75rem 1.5rem",
  borderRadius: "0.5rem",
  border: "none",
  background: "#1e40af",
  color: "white",
  fontWeight: 600,
  cursor: "pointer",
  fontSize: "1rem",
};
