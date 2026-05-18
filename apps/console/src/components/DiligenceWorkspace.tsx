"use client";

/**
 * Forensa Console — M&A diligence workspace (US-F26, SCR-F07, BR-13, BR-14).
 *
 * Acceptance closed:
 *   AC: create export job -> list jobs -> view detail -> download bundle.
 *
 * API surface used:
 *   POST   /v1/exports/ma-diligence/jobs       -> 202 {job_id, status, poll_url}
 *   GET    /v1/exports/ma-diligence/jobs       -> {items: MaExportJobStatusResponse[], tenant_id}
 *   GET    /v1/exports/ma-diligence/jobs/{id}  -> MaExportJobStatusResponse
 *
 * UC-07 hook: this screen is the P-ACQ Console deliverable —
 * "diligence turnaround 11 weeks -> 4 hours" depends on this UI being
 * usable without the operator constructing JSON or calling the CLI.
 */

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiFetch";

export type DiligenceJobStatus = "pending" | "running" | "completed" | "failed";

export interface DiligenceJob {
  job_id: string;
  tenant_id: string;
  status: DiligenceJobStatus;
  scope_start: string;
  scope_end: string;
  requested_at: string;
  started_at: string | null;
  completed_at: string | null;
  result_export: Record<string, unknown> | null;
  result_error: string | null;
}

interface JobListResponse {
  items: DiligenceJob[];
  tenant_id: string;
}

interface JobCreateResponse {
  job_id: string;
  status: string;
  poll_url: string;
}

type LoadState = "loading" | "ok" | "empty" | "error";

export interface DiligenceWorkspaceProps {
  tenantId: string;
  apiUrl?: string;
  fetcher?: typeof fetch;
  /** Polling interval, ms; lower in tests. */
  pollMs?: number;
}

const DEFAULT_URL =
  /* v8 ignore next */
  process.env.NEXT_PUBLIC_FORENSA_API_URL ?? "http://localhost:8000";

export function DiligenceWorkspace({
  tenantId,
  apiUrl,
  fetcher = apiFetch,
  pollMs = 4_000,
}: DiligenceWorkspaceProps) {
  const baseUrl = apiUrl ?? DEFAULT_URL;
  const [state, setState] = useState<LoadState>("loading");
  const [jobs, setJobs] = useState<DiligenceJob[]>([]);
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [creating, setCreating] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string>("");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [scopeStart, setScopeStart] = useState<string>("");
  const [scopeEnd, setScopeEnd] = useState<string>("");

  // Auto-refresh while there's at least one pending/running job.
  const hasInflightJob = jobs.some(
    (j) => j.status === "pending" || j.status === "running",
  );

  const listUrl = `${baseUrl}/v1/exports/ma-diligence/jobs`;

  const refresh = useCallback(async () => {
    try {
      const r = await fetcher(listUrl);
      if (!r.ok) {
        setState("error");
        setErrorMsg(`HTTP ${r.status}`);
        return;
      }
      const body = (await r.json()) as JobListResponse;
      const items = body.items ?? [];
      setJobs(items);
      setState(items.length === 0 ? "empty" : "ok");
    } catch (e) {
      setState("error");
      setErrorMsg((e as Error).message);
    }
  }, [fetcher, listUrl]);

  // Initial load + polling while jobs are in-flight.
  useEffect(() => {
    refresh();
    if (!hasInflightJob) return;
    const id = setInterval(() => {
      refresh();
    }, pollMs);
    return () => clearInterval(id);
  }, [refresh, hasInflightJob, pollMs]);

  const handleCreate = useCallback(async () => {
    if (!scopeStart || !scopeEnd) {
      setCreateError("Pick both a start date and an end date.");
      return;
    }
    setCreating(true);
    setCreateError("");
    try {
      // Convert to ISO with UTC midnight bounds; API expects tz-aware.
      const start = new Date(`${scopeStart}T00:00:00Z`).toISOString();
      const end = new Date(`${scopeEnd}T23:59:59Z`).toISOString();
      const r = await fetcher(`${baseUrl}/v1/exports/ma-diligence/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tenant_id: tenantId,
          scope_start: start,
          scope_end: end,
        }),
      });
      if (!r.ok) {
        setCreateError(`Job create HTTP ${r.status}`);
        return;
      }
      const body = (await r.json()) as JobCreateResponse;
      // Optimistically refresh — the new pending job should appear.
      await refresh();
      setSelectedJobId(body.job_id);
    } catch (e) {
      setCreateError((e as Error).message);
    } finally {
      setCreating(false);
    }
  }, [baseUrl, fetcher, refresh, scopeEnd, scopeStart, tenantId]);

  const selectedJob = jobs.find((j) => j.job_id === selectedJobId) ?? null;

  return (
    <div
      data-testid="diligence-workspace"
      style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}
    >
      <CreateJobForm
        scopeStart={scopeStart}
        scopeEnd={scopeEnd}
        onScopeStartChange={setScopeStart}
        onScopeEndChange={setScopeEnd}
        onCreate={handleCreate}
        creating={creating}
        error={createError}
      />
      {state === "loading" ? (
        <p data-testid="diligence-list-loading">Loading jobs…</p>
      ) : state === "error" ? (
        <p data-testid="diligence-list-error" style={{ color: "#991b1b" }}>
          Error loading jobs: {errorMsg}
        </p>
      ) : state === "empty" ? (
        <p data-testid="diligence-list-empty" style={{ color: "#374151" }}>
          No diligence jobs yet. Create one above to begin.
        </p>
      ) : (
        <JobList
          jobs={jobs}
          selectedJobId={selectedJobId}
          onSelect={setSelectedJobId}
        />
      )}
      {selectedJob ? <JobDetail job={selectedJob} /> : null}
    </div>
  );
}

interface CreateJobFormProps {
  scopeStart: string;
  scopeEnd: string;
  onScopeStartChange: (v: string) => void;
  onScopeEndChange: (v: string) => void;
  onCreate: () => void;
  creating: boolean;
  error: string;
}

function CreateJobForm({
  scopeStart,
  scopeEnd,
  onScopeStartChange,
  onScopeEndChange,
  onCreate,
  creating,
  error,
}: CreateJobFormProps) {
  return (
    <fieldset
      data-testid="diligence-create-form"
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
      <legend
        style={{ padding: "0 0.5rem", fontSize: "0.85rem", color: "#6b7280" }}
      >
        Create diligence export
      </legend>
      <Field label="Window start">
        <input
          type="date"
          data-testid="diligence-scope-start"
          value={scopeStart}
          onChange={(e) => onScopeStartChange(e.target.value)}
          style={inputStyle}
        />
      </Field>
      <Field label="Window end">
        <input
          type="date"
          data-testid="diligence-scope-end"
          value={scopeEnd}
          onChange={(e) => onScopeEndChange(e.target.value)}
          style={inputStyle}
        />
      </Field>
      <button
        type="button"
        data-testid="diligence-create-submit"
        onClick={onCreate}
        disabled={creating}
        style={{
          padding: "0.5rem 1rem",
          borderRadius: "0.4rem",
          border: "none",
          background: creating ? "#9ca3af" : "#1e40af",
          color: "white",
          fontWeight: 600,
          cursor: creating ? "wait" : "pointer",
        }}
      >
        {creating ? "Creating…" : "Create job"}
      </button>
      {error ? (
        <p
          data-testid="diligence-create-error"
          style={{ color: "#991b1b", width: "100%", margin: 0, fontSize: "0.85rem" }}
        >
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label
      style={{
        display: "flex",
        flexDirection: "column",
        fontSize: "0.8rem",
        color: "#374151",
      }}
    >
      <span style={{ marginBottom: "0.15rem" }}>{label}</span>
      {children}
    </label>
  );
}

interface JobListProps {
  jobs: DiligenceJob[];
  selectedJobId: string | null;
  onSelect: (id: string) => void;
}

function JobList({ jobs, selectedJobId, onSelect }: JobListProps) {
  return (
    <table
      data-testid="diligence-jobs-table"
      style={{ borderCollapse: "collapse", width: "100%", fontSize: "0.9rem" }}
    >
      <thead>
        <tr style={{ background: "#f9fafb" }}>
          <th style={th}>Job</th>
          <th style={th}>Status</th>
          <th style={th}>Window</th>
          <th style={th}>Requested</th>
          <th style={th} />
        </tr>
      </thead>
      <tbody>
        {jobs.map((j) => {
          const selected = j.job_id === selectedJobId;
          return (
            <tr
              key={j.job_id}
              data-testid={`diligence-job-row-${j.job_id}`}
              style={{
                borderBottom: "1px solid #f3f4f6",
                background: selected ? "#eff6ff" : "transparent",
              }}
            >
              <td style={{ ...td, fontFamily: "monospace", fontSize: "0.8rem" }}>
                {j.job_id.slice(0, 8)}…
              </td>
              <td style={td}>
                <JobStatusBadge status={j.status} />
              </td>
              <td style={td}>
                {j.scope_start.slice(0, 10)} → {j.scope_end.slice(0, 10)}
              </td>
              <td style={td}>{new Date(j.requested_at).toISOString()}</td>
              <td style={td}>
                <button
                  type="button"
                  data-testid={`diligence-job-select-${j.job_id}`}
                  onClick={() => onSelect(j.job_id)}
                  style={{
                    background: "none",
                    border: "none",
                    color: "#1e40af",
                    cursor: "pointer",
                    textDecoration: "underline",
                    fontSize: "0.85rem",
                  }}
                >
                  View
                </button>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function JobStatusBadge({ status }: { status: DiligenceJobStatus }) {
  const palette: Record<DiligenceJobStatus, { bg: string; fg: string }> = {
    pending: { bg: "#fef3c7", fg: "#92400e" },
    running: { bg: "#dbeafe", fg: "#1e40af" },
    completed: { bg: "#dcfce7", fg: "#166534" },
    failed: { bg: "#fee2e2", fg: "#991b1b" },
  };
  const { bg, fg } = palette[status];
  return (
    <span
      data-testid={`diligence-status-${status}`}
      style={{
        display: "inline-block",
        padding: "0.15rem 0.55rem",
        borderRadius: "999px",
        fontSize: "0.75rem",
        fontWeight: 600,
        background: bg,
        color: fg,
      }}
    >
      {status}
    </span>
  );
}

function JobDetail({ job }: { job: DiligenceJob }) {
  return (
    <article
      data-testid="diligence-job-detail"
      style={{
        padding: "1rem",
        border: "1px solid #e5e7eb",
        borderRadius: "0.5rem",
        background: "white",
      }}
    >
      <h2 style={{ marginTop: 0, fontSize: "1.05rem" }}>Job detail</h2>
      <dl
        style={{
          display: "grid",
          gridTemplateColumns: "max-content 1fr",
          gap: "0.5rem 1rem",
          fontSize: "0.9rem",
          margin: 0,
        }}
      >
        <dt>Job id</dt>
        <dd
          data-testid="diligence-detail-id"
          style={{ fontFamily: "monospace", margin: 0 }}
        >
          {job.job_id}
        </dd>
        <dt>Status</dt>
        <dd data-testid="diligence-detail-status" style={{ margin: 0 }}>
          <JobStatusBadge status={job.status} />
        </dd>
        <dt>Window</dt>
        <dd style={{ margin: 0 }}>
          {job.scope_start.slice(0, 10)} → {job.scope_end.slice(0, 10)}
        </dd>
        <dt>Requested</dt>
        <dd style={{ margin: 0 }}>{new Date(job.requested_at).toISOString()}</dd>
        {job.completed_at ? (
          <>
            <dt>Completed</dt>
            <dd style={{ margin: 0 }}>
              {new Date(job.completed_at).toISOString()}
            </dd>
          </>
        ) : null}
        {job.result_error ? (
          <>
            <dt>Error</dt>
            <dd
              data-testid="diligence-detail-error"
              style={{ margin: 0, color: "#991b1b" }}
            >
              {job.result_error}
            </dd>
          </>
        ) : null}
      </dl>
      {job.status === "completed" && job.result_export ? (
        <BundleDownload job={job} />
      ) : null}
    </article>
  );
}

function BundleDownload({ job }: { job: DiligenceJob }) {
  const handleDownload = useCallback(() => {
    const text = JSON.stringify(job.result_export, null, 2);
    const blob = new Blob([text], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `forensa-diligence-${job.job_id.slice(0, 8)}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }, [job]);
  return (
    <div style={{ marginTop: "1rem" }}>
      <button
        type="button"
        data-testid="diligence-download-bundle"
        onClick={handleDownload}
        style={{
          padding: "0.5rem 1rem",
          borderRadius: "0.4rem",
          border: "none",
          background: "#065f46",
          color: "white",
          fontWeight: 600,
          cursor: "pointer",
        }}
      >
        Download bundle JSON
      </button>
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
const inputStyle: React.CSSProperties = {
  padding: "0.35rem 0.5rem",
  border: "1px solid #d1d5db",
  borderRadius: "0.35rem",
  fontSize: "0.85rem",
  minWidth: "9rem",
};
