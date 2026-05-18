"use client";

/**
 * Forensa Console — narrative viewer (SCR-F08, RT-F21 advance).
 *
 * Acceptance:
 *   - Pick a receipt window (start + end ISO dates).
 *   - Click "Explain this window" -> call POST /v1/narratives (query
 *     params per the API spec).
 *   - Render the plain-English narrative with model id and token
 *     counts so the operator sees the AI surface honestly.
 *   - Surface upstream errors (502 / 413 / 422) with clear copy.
 *
 * The 422 path includes an `incident_id` per packages/narrative
 * defence policy; we display it without exposing the offending text
 * (BR-10 defence pattern).
 */

import { useCallback, useState } from "react";
import { apiFetch } from "@/lib/apiFetch";

export interface NarrativeResponse {
  narrative_text: string;
  model_id: string;
  prompt_token_count: number;
  completion_token_count: number;
  content_hash: string;
  prompt_hash: string;
  pack_root_hash: string;
  generated_at: string;
}

interface NarrativeError {
  detail?: string | { incident_id?: string; message?: string };
}

type LoadState = "idle" | "loading" | "ok" | "error";

export interface NarrativeViewerProps {
  tenantId: string;
  apiUrl?: string;
  fetcher?: typeof fetch;
  initialScopeStart?: string;
  initialScopeEnd?: string;
}

const DEFAULT_URL =
  /* v8 ignore next */
  process.env.NEXT_PUBLIC_FORENSA_API_URL ?? "http://localhost:8000";

export function NarrativeViewer({
  tenantId,
  apiUrl,
  fetcher = apiFetch,
  initialScopeStart = "",
  initialScopeEnd = "",
}: NarrativeViewerProps) {
  const baseUrl = apiUrl ?? DEFAULT_URL;
  const [scopeStart, setScopeStart] = useState<string>(initialScopeStart);
  const [scopeEnd, setScopeEnd] = useState<string>(initialScopeEnd);
  const [state, setState] = useState<LoadState>("idle");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [errorIncidentId, setErrorIncidentId] = useState<string>("");
  const [errorStatus, setErrorStatus] = useState<number>(0);
  const [narrative, setNarrative] = useState<NarrativeResponse | null>(null);

  const handleGenerate = useCallback(async () => {
    if (!scopeStart || !scopeEnd) {
      setState("error");
      setErrorStatus(0);
      setErrorMsg("Pick both a start date and an end date.");
      setErrorIncidentId("");
      return;
    }
    setState("loading");
    setErrorMsg("");
    setErrorIncidentId("");
    setErrorStatus(0);
    try {
      const start = new Date(`${scopeStart}T00:00:00Z`).toISOString();
      const end = new Date(`${scopeEnd}T23:59:59Z`).toISOString();
      const url =
        `${baseUrl}/v1/narratives` +
        `?tenant_id=${encodeURIComponent(tenantId)}` +
        `&scope_start=${encodeURIComponent(start)}` +
        `&scope_end=${encodeURIComponent(end)}`;
      const r = await fetcher(url, { method: "POST" });
      if (!r.ok) {
        setState("error");
        setErrorStatus(r.status);
        // The defence-triggered 422 carries an incident_id.
        try {
          const body = (await r.json()) as NarrativeError;
          if (typeof body.detail === "string") {
            setErrorMsg(body.detail);
          } else if (body.detail && typeof body.detail === "object") {
            setErrorMsg(body.detail.message ?? `HTTP ${r.status}`);
            setErrorIncidentId(body.detail.incident_id ?? "");
          } else {
            setErrorMsg(`HTTP ${r.status}`);
          }
        } catch {
          setErrorMsg(`HTTP ${r.status}`);
        }
        return;
      }
      const body = (await r.json()) as NarrativeResponse;
      setNarrative(body);
      setState("ok");
    } catch (e) {
      setState("error");
      setErrorMsg((e as Error).message);
    }
  }, [baseUrl, fetcher, scopeEnd, scopeStart, tenantId]);

  return (
    <div
      data-testid="narrative-viewer"
      style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}
    >
      <fieldset
        data-testid="narrative-form"
        style={{
          display: "flex",
          gap: "0.5rem",
          flexWrap: "wrap",
          alignItems: "flex-end",
          border: "1px solid #e5e7eb",
          borderRadius: "0.5rem",
          padding: "0.75rem",
        }}
      >
        <legend style={{ padding: "0 0.5rem", fontSize: "0.85rem", color: "#6b7280" }}>
          Window
        </legend>
        <label style={fieldStyle}>
          <span style={{ marginBottom: "0.15rem" }}>Start</span>
          <input
            type="date"
            data-testid="narrative-scope-start"
            value={scopeStart}
            onChange={(e) => setScopeStart(e.target.value)}
            style={inputStyle}
          />
        </label>
        <label style={fieldStyle}>
          <span style={{ marginBottom: "0.15rem" }}>End</span>
          <input
            type="date"
            data-testid="narrative-scope-end"
            value={scopeEnd}
            onChange={(e) => setScopeEnd(e.target.value)}
            style={inputStyle}
          />
        </label>
        <button
          type="button"
          data-testid="narrative-submit"
          onClick={handleGenerate}
          disabled={state === "loading"}
          style={{
            padding: "0.5rem 1rem",
            borderRadius: "0.4rem",
            border: "none",
            background: state === "loading" ? "#9ca3af" : "#1e40af",
            color: "white",
            fontWeight: 600,
            cursor: state === "loading" ? "wait" : "pointer",
          }}
        >
          {state === "loading" ? "Asking the model…" : "Explain this window"}
        </button>
      </fieldset>

      {state === "loading" ? (
        <p data-testid="narrative-loading">
          Reading receipts and asking the model for a plain-English summary…
        </p>
      ) : state === "error" ? (
        <NarrativeError
          message={errorMsg}
          incidentId={errorIncidentId}
          status={errorStatus}
        />
      ) : state === "ok" && narrative ? (
        <NarrativePane narrative={narrative} />
      ) : null}
    </div>
  );
}

function NarrativeError({
  message,
  incidentId,
  status,
}: {
  message: string;
  incidentId: string;
  status: number;
}) {
  const isDefenceTrigger = status === 422;
  return (
    <div
      data-testid="narrative-error"
      role="alert"
      style={{
        padding: "1rem",
        border: "1px solid #fca5a5",
        background: "#fef2f2",
        borderRadius: "0.5rem",
        color: "#991b1b",
      }}
    >
      <p style={{ marginTop: 0, fontWeight: 600 }}>
        {isDefenceTrigger
          ? "Request blocked by injection-defence layer."
          : "Couldn't generate the narrative."}
      </p>
      <p style={{ margin: 0 }}>{message}</p>
      {incidentId ? (
        <p
          data-testid="narrative-incident-id"
          style={{ margin: "0.5rem 0 0", fontSize: "0.85rem", fontFamily: "monospace" }}
        >
          Incident id: {incidentId}
        </p>
      ) : null}
    </div>
  );
}

function NarrativePane({ narrative }: { narrative: NarrativeResponse }) {
  return (
    <article
      data-testid="narrative-pane"
      style={{
        padding: "1rem",
        border: "1px solid #e5e7eb",
        borderRadius: "0.5rem",
        background: "white",
      }}
    >
      <h2 style={{ marginTop: 0, fontSize: "1.05rem" }}>Plain-English narrative</h2>
      <p
        data-testid="narrative-text"
        style={{
          whiteSpace: "pre-wrap",
          fontSize: "0.95rem",
          lineHeight: 1.6,
          color: "#111827",
        }}
      >
        {narrative.narrative_text}
      </p>
      <dl
        style={{
          display: "grid",
          gridTemplateColumns: "max-content 1fr",
          gap: "0.4rem 1rem",
          fontSize: "0.85rem",
          color: "#374151",
          marginTop: "1rem",
          paddingTop: "1rem",
          borderTop: "1px solid #f3f4f6",
        }}
      >
        <dt>Model</dt>
        <dd data-testid="narrative-model" style={{ margin: 0, fontFamily: "monospace" }}>
          {narrative.model_id}
        </dd>
        <dt>Tokens (prompt / completion)</dt>
        <dd data-testid="narrative-tokens" style={{ margin: 0 }}>
          {narrative.prompt_token_count} / {narrative.completion_token_count}
        </dd>
        <dt>Pack root hash</dt>
        <dd
          data-testid="narrative-pack-root"
          style={{ margin: 0, fontFamily: "monospace", wordBreak: "break-all" }}
        >
          {narrative.pack_root_hash}
        </dd>
        <dt>Content hash</dt>
        <dd
          data-testid="narrative-content-hash"
          style={{ margin: 0, fontFamily: "monospace", wordBreak: "break-all" }}
        >
          {narrative.content_hash}
        </dd>
        <dt>Generated at</dt>
        <dd style={{ margin: 0 }}>{new Date(narrative.generated_at).toISOString()}</dd>
      </dl>
    </article>
  );
}

const fieldStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  fontSize: "0.8rem",
  color: "#374151",
};

const inputStyle: React.CSSProperties = {
  padding: "0.35rem 0.5rem",
  border: "1px solid #d1d5db",
  borderRadius: "0.35rem",
  fontSize: "0.85rem",
  minWidth: "9rem",
};
