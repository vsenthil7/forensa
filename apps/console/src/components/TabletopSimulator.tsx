"use client";

/**
 * Forensa Console — tabletop simulator (US-F23, SCR-F06, RT-F21 advance).
 *
 * Acceptance closed:
 *   - UI to pick a candidate policy bundle (via scenario JSON), define
 *     an action list, run a simulation, and render per-action verdicts
 *     + aggregate counts.
 *
 * UI shape:
 *   Textarea for the TabletopScenario JSON. Power-user UX deliberately
 *   chosen over a guided form because the action payloads are
 *   open-ended dicts that don't have a single canonical shape; the
 *   security engineer who runs tabletops is comfortable with JSON.
 *   A "Load sample" button populates a minimal valid skeleton so the
 *   user sees the shape immediately.
 *
 *   The simulator never persists; the API contract is read-only.
 *
 * API surface used:
 *   POST /v1/tabletop/simulate  (body: TabletopScenario)
 */

import { useCallback, useState } from "react";
import { apiFetch } from "@/lib/apiFetch";

export interface TabletopActionResult {
  label: string;
  decision: string | null;
  reason: string | null;
  errored: boolean;
}

export interface TabletopSummary {
  total: number;
  allow: number;
  deny: number;
  escalate: number;
  errored: number;
}

export interface TabletopResult {
  scenario: {
    name: string;
    tenant_id: string;
    policy_bundle_id: string;
    actions: Array<{ label: string; action: Record<string, unknown> }>;
  };
  bundle_id: string;
  bundle_version: string;
  bundle_content_hash: string;
  action_results: TabletopActionResult[];
  summary: TabletopSummary;
}

type LoadState = "idle" | "loading" | "ok" | "error";

export interface TabletopSimulatorProps {
  tenantId: string;
  apiUrl?: string;
  fetcher?: typeof fetch;
  initialJson?: string;
}

const DEFAULT_URL =
  /* v8 ignore next */
  process.env.NEXT_PUBLIC_FORENSA_API_URL ?? "http://localhost:8000";

const SAMPLE_TEMPLATE = (tenantId: string): string =>
  JSON.stringify(
    {
      name: "tabletop-2026-Q2",
      tenant_id: tenantId,
      policy_bundle_id: "<paste-your-policy-bundle-uuid>",
      actions: [
        {
          label: "high-risk-credit-approval",
          action: {
            type: "credit_decision",
            applicant_score: 540,
            amount: 250000,
            principal: "agent-mortgage-bot-v3",
          },
        },
      ],
    },
    null,
    2,
  );

export function TabletopSimulator({
  tenantId,
  apiUrl,
  fetcher = apiFetch,
  initialJson = "",
}: TabletopSimulatorProps) {
  const baseUrl = apiUrl ?? DEFAULT_URL;
  const [scenarioJson, setScenarioJson] = useState<string>(initialJson);
  const [state, setState] = useState<LoadState>("idle");
  const [result, setResult] = useState<TabletopResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");

  const handleLoadSample = useCallback(() => {
    setScenarioJson(SAMPLE_TEMPLATE(tenantId));
  }, [tenantId]);

  const handleRun = useCallback(async () => {
    if (!scenarioJson.trim()) {
      setState("error");
      setErrorMsg("Paste a scenario JSON first (or click Load sample).");
      return;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(scenarioJson);
    } catch (e) {
      setState("error");
      setErrorMsg(`Invalid JSON: ${(e as Error).message}`);
      return;
    }
    setState("loading");
    setErrorMsg("");
    try {
      const r = await fetcher(`${baseUrl}/v1/tabletop/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed),
      });
      if (!r.ok) {
        setState("error");
        setErrorMsg(`HTTP ${r.status}`);
        return;
      }
      const body = (await r.json()) as TabletopResult;
      setResult(body);
      setState("ok");
    } catch (e) {
      setState("error");
      setErrorMsg((e as Error).message);
    }
  }, [baseUrl, fetcher, scenarioJson]);

  return (
    <div
      data-testid="tabletop-simulator"
      style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}
    >
      <fieldset
        data-testid="tabletop-form"
        style={{
          border: "1px solid #e5e7eb",
          borderRadius: "0.5rem",
          padding: "0.75rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.5rem",
        }}
      >
        <legend style={{ padding: "0 0.5rem", fontSize: "0.85rem", color: "#6b7280" }}>
          Scenario JSON
        </legend>
        <textarea
          data-testid="tabletop-scenario-input"
          value={scenarioJson}
          onChange={(e) => setScenarioJson(e.target.value)}
          rows={14}
          placeholder="Paste a TabletopScenario JSON or click 'Load sample'."
          style={{
            width: "100%",
            padding: "0.6rem",
            border: "1px solid #d1d5db",
            borderRadius: "0.35rem",
            fontFamily: "monospace",
            fontSize: "0.8rem",
            resize: "vertical",
          }}
        />
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            type="button"
            data-testid="tabletop-load-sample"
            onClick={handleLoadSample}
            style={secondaryBtn}
          >
            Load sample
          </button>
          <button
            type="button"
            data-testid="tabletop-run"
            onClick={handleRun}
            disabled={state === "loading"}
            style={{
              ...primaryBtn,
              background: state === "loading" ? "#9ca3af" : "#1e40af",
              cursor: state === "loading" ? "wait" : "pointer",
            }}
          >
            {state === "loading" ? "Running simulation…" : "Run simulation"}
          </button>
        </div>
      </fieldset>

      {state === "loading" ? (
        <p data-testid="tabletop-loading">Running simulation…</p>
      ) : state === "error" ? (
        <p
          data-testid="tabletop-error"
          role="alert"
          style={{
            color: "#991b1b",
            padding: "0.75rem 1rem",
            background: "#fef2f2",
            border: "1px solid #fca5a5",
            borderRadius: "0.4rem",
          }}
        >
          {errorMsg}
        </p>
      ) : state === "ok" && result ? (
        <TabletopResultPane result={result} />
      ) : null}
    </div>
  );
}

function TabletopResultPane({ result }: { result: TabletopResult }) {
  return (
    <article
      data-testid="tabletop-result"
      style={{
        padding: "1rem",
        border: "1px solid #e5e7eb",
        borderRadius: "0.5rem",
        background: "white",
        display: "flex",
        flexDirection: "column",
        gap: "1rem",
      }}
    >
      <header>
        <h2 style={{ margin: 0, fontSize: "1.05rem" }}>
          {result.scenario.name}
        </h2>
        <p
          data-testid="tabletop-result-bundle"
          style={{
            margin: "0.25rem 0 0",
            fontSize: "0.85rem",
            color: "#6b7280",
          }}
        >
          Bundle {result.bundle_id.slice(0, 8)}… v{result.bundle_version}
        </p>
      </header>
      <Summary summary={result.summary} />
      <table
        data-testid="tabletop-actions-table"
        style={{ borderCollapse: "collapse", width: "100%", fontSize: "0.9rem" }}
      >
        <thead>
          <tr style={{ background: "#f9fafb" }}>
            <th style={th}>Action</th>
            <th style={th}>Decision</th>
            <th style={th}>Reason</th>
          </tr>
        </thead>
        <tbody>
          {result.action_results.map((a, i) => (
            <tr
              key={`${a.label}-${i}`}
              data-testid={`tabletop-action-row-${i}`}
              style={{ borderBottom: "1px solid #f3f4f6" }}
            >
              <td style={td}>{a.label}</td>
              <td style={td}>
                <DecisionPill decision={a.decision} errored={a.errored} />
              </td>
              <td style={{ ...td, color: a.errored ? "#991b1b" : "#374151" }}>
                {a.reason ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </article>
  );
}

function Summary({ summary }: { summary: TabletopSummary }) {
  return (
    <dl
      data-testid="tabletop-summary"
      style={{
        display: "flex",
        gap: "0.5rem",
        flexWrap: "wrap",
        margin: 0,
      }}
    >
      <SummaryStat
        label="Total"
        value={summary.total}
        testid="tabletop-summary-total"
      />
      <SummaryStat
        label="Allow"
        value={summary.allow}
        testid="tabletop-summary-allow"
        fg="#166534"
        bg="#dcfce7"
      />
      <SummaryStat
        label="Deny"
        value={summary.deny}
        testid="tabletop-summary-deny"
        fg="#991b1b"
        bg="#fee2e2"
      />
      <SummaryStat
        label="Escalate"
        value={summary.escalate}
        testid="tabletop-summary-escalate"
        fg="#92400e"
        bg="#fef3c7"
      />
      <SummaryStat
        label="Errored"
        value={summary.errored}
        testid="tabletop-summary-errored"
        fg="#374151"
        bg="#e5e7eb"
      />
    </dl>
  );
}

function SummaryStat({
  label,
  value,
  testid,
  fg = "#111827",
  bg = "#f3f4f6",
}: {
  label: string;
  value: number;
  testid: string;
  fg?: string;
  bg?: string;
}) {
  return (
    <div
      data-testid={testid}
      style={{
        padding: "0.5rem 0.75rem",
        background: bg,
        color: fg,
        borderRadius: "0.4rem",
        minWidth: "5rem",
      }}
    >
      <dt style={{ fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {label}
      </dt>
      <dd style={{ margin: 0, fontSize: "1.25rem", fontWeight: 700 }}>{value}</dd>
    </div>
  );
}

function DecisionPill({
  decision,
  errored,
}: {
  decision: string | null;
  errored: boolean;
}) {
  if (errored) {
    return (
      <span
        data-testid="decision-errored"
        style={{
          padding: "0.15rem 0.55rem",
          borderRadius: "999px",
          background: "#e5e7eb",
          color: "#374151",
          fontSize: "0.75rem",
          fontWeight: 600,
        }}
      >
        ERROR
      </span>
    );
  }
  const palette: Record<string, { bg: string; fg: string }> = {
    allow: { bg: "#dcfce7", fg: "#166534" },
    deny: { bg: "#fee2e2", fg: "#991b1b" },
    escalate: { bg: "#fef3c7", fg: "#92400e" },
  };
  const key = (decision ?? "").toLowerCase();
  const palCfg = palette[key] ?? { bg: "#e5e7eb", fg: "#374151" };
  return (
    <span
      data-testid={`decision-${key || "unknown"}`}
      style={{
        padding: "0.15rem 0.55rem",
        borderRadius: "999px",
        background: palCfg.bg,
        color: palCfg.fg,
        fontSize: "0.75rem",
        fontWeight: 600,
      }}
    >
      {decision ?? "unknown"}
    </span>
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
const primaryBtn: React.CSSProperties = {
  padding: "0.5rem 1rem",
  borderRadius: "0.4rem",
  border: "none",
  background: "#1e40af",
  color: "white",
  fontWeight: 600,
  cursor: "pointer",
};
const secondaryBtn: React.CSSProperties = {
  padding: "0.5rem 1rem",
  borderRadius: "0.4rem",
  border: "1px solid #d1d5db",
  background: "white",
  color: "#374151",
  fontWeight: 500,
  cursor: "pointer",
};
