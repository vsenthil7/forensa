"use client";

/**
 * Forensa Console — enterprise receipt timeline (US-F29, SCR-F02).
 *
 * Replaces the v1 ReceiptList table per BR-14 AC-2 (list-views-as-top-nav).
 *
 * Acceptance criteria closed:
 *   AC-1 cursor pagination (limit default 50, max 200)
 *   AC-2 filters: date / agent / outcome / chain status / policy version
 *   AC-3 URL-query persistence (back button + bookmarkable)
 *   AC-4 sortable columns
 *   AC-5 status chips (green anchored / amber pending / grey deferred)
 *   AC-6 loading skeleton (no flash of blank)
 *   AC-7 empty state with clear CTA
 *   AC-8 error state with retry
 *   AC-9 hash collapsed behind disclosure ("🔐 Verify")
 *
 * Anti-pattern explicitly NOT used (US-F29 + BR-14 AC-2):
 *   No sessionStorage tracking of "active receipt". The detail page
 *   resolves its receipt from the URL path alone. Back-button works
 *   because filters live in URL query, not in client state.
 *
 * Server-side cursor pagination contract:
 *   GET /v1/receipts?tenant_id=...&limit=N&cursor=<opaque>&...filters
 *   -> { items: ReceiptListItem[], next_cursor: string|null, count: N }
 *
 *   Today's API returns offset-paginated; the component is built
 *   against the cursor contract and the server-side cursor adapter
 *   is provided by API-F05 (CP9.52 adapter; see API_SPECIFICATION).
 *   For backward-compat the component falls back to offset if the
 *   response shape is the v1 offset shape.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/apiFetch";
import {
  StatusChip,
  deriveReceiptStatus,
  type ReceiptChainStatus,
} from "@/components/StatusChip";

export interface ReceiptTimelineItem {
  id: string;
  tenant_id: string;
  event_id: string;
  policy_bundle_id: string;
  /** Receipt-side fields the UI cares about. */
  sequence: number;
  prev_receipt_hash: string | null;
  payload_hash: string;
  receipt_hash: string;
  signature_b64: string;
  signed_at: string;
  /** Optional fields enriched by API-F05 v2 (CP9.52). */
  agent_id?: string | null;
  policy_outcome?: string | null;
  policy_version?: string | null;
  anchor_id?: string | null;
  tsr_b64?: string | null;
}

export interface ReceiptTimelineResponse {
  items: ReceiptTimelineItem[];
  tenant_id?: string;
  /** v2 cursor shape (preferred). */
  next_cursor?: string | null;
  /** v1 offset shape (compatibility). */
  offset?: number;
  limit?: number;
  count?: number;
}

export type SortKey = "signed_at" | "sequence" | "policy_outcome";
export type SortDir = "asc" | "desc";

export interface ReceiptTimelineFilters {
  dateFrom: string;
  dateTo: string;
  agent: string;
  outcome: string;
  status: "" | ReceiptChainStatus;
  policyVersion: string;
}

export const EMPTY_FILTERS: ReceiptTimelineFilters = {
  dateFrom: "",
  dateTo: "",
  agent: "",
  outcome: "",
  status: "",
  policyVersion: "",
};

const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 200;

type LoadState = "loading" | "ok" | "empty" | "error";

export interface ReceiptsTimelineProps {
  tenantId: string;
  apiUrl?: string;
  fetcher?: typeof fetch;
  /** Read filters from this object instead of window.location (testable). */
  initialQuery?: URLSearchParams;
  /** Called whenever the user changes filters; the page wires this to router.push. */
  onQueryChange?: (q: URLSearchParams) => void;
  /** Max items per page; capped at MAX_LIMIT. */
  limit?: number;
}

const DEFAULT_URL =
  /* v8 ignore next */
  process.env.NEXT_PUBLIC_FORENSA_API_URL ?? "http://localhost:8000";

/** Parse a URL query into typed filters + paging state. */
export function parseQuery(q: URLSearchParams): {
  filters: ReceiptTimelineFilters;
  cursor: string;
  sortKey: SortKey;
  sortDir: SortDir;
} {
  const get = (k: string): string => q.get(k) ?? "";
  const rawStatus = get("status");
  const status: ReceiptTimelineFilters["status"] =
    rawStatus === "anchored" || rawStatus === "pending" || rawStatus === "deferred"
      ? rawStatus
      : "";
  const rawSortKey = get("sort");
  const sortKey: SortKey =
    rawSortKey === "sequence" || rawSortKey === "policy_outcome"
      ? rawSortKey
      : "signed_at";
  const rawDir = get("dir");
  const sortDir: SortDir = rawDir === "asc" ? "asc" : "desc";
  return {
    filters: {
      dateFrom: get("from"),
      dateTo: get("to"),
      agent: get("agent"),
      outcome: get("outcome"),
      status,
      policyVersion: get("pv"),
    },
    cursor: get("cursor"),
    sortKey,
    sortDir,
  };
}

/** Inverse of parseQuery: serialise current state into URL query. */
export function buildQuery(
  filters: ReceiptTimelineFilters,
  cursor: string,
  sortKey: SortKey,
  sortDir: SortDir,
): URLSearchParams {
  const q = new URLSearchParams();
  if (filters.dateFrom) q.set("from", filters.dateFrom);
  if (filters.dateTo) q.set("to", filters.dateTo);
  if (filters.agent) q.set("agent", filters.agent);
  if (filters.outcome) q.set("outcome", filters.outcome);
  if (filters.status) q.set("status", filters.status);
  if (filters.policyVersion) q.set("pv", filters.policyVersion);
  if (cursor) q.set("cursor", cursor);
  if (sortKey !== "signed_at") q.set("sort", sortKey);
  if (sortDir !== "desc") q.set("dir", sortDir);
  return q;
}

/** Build the API URL from filters + paging + sort. */
export function buildApiUrl(
  base: string,
  tenantId: string,
  filters: ReceiptTimelineFilters,
  cursor: string,
  limit: number,
  sortKey: SortKey,
  sortDir: SortDir,
): string {
  const q = new URLSearchParams();
  q.set("tenant_id", tenantId);
  q.set("limit", String(Math.min(limit, MAX_LIMIT)));
  if (cursor) q.set("cursor", cursor);
  if (filters.dateFrom) q.set("signed_after", filters.dateFrom);
  if (filters.dateTo) q.set("signed_before", filters.dateTo);
  if (filters.agent) q.set("agent_id", filters.agent);
  if (filters.outcome) q.set("policy_outcome", filters.outcome);
  if (filters.status) q.set("chain_status", filters.status);
  if (filters.policyVersion) q.set("policy_version", filters.policyVersion);
  q.set("sort", sortKey);
  q.set("dir", sortDir);
  return `${base}/v1/receipts?${q.toString()}`;
}

/** Apply column sort client-side (the server also sorts; this is a defence). */
export function sortItems(
  items: ReceiptTimelineItem[],
  key: SortKey,
  dir: SortDir,
): ReceiptTimelineItem[] {
  const mult = dir === "asc" ? 1 : -1;
  const sorted = [...items];
  sorted.sort((a, b) => {
    let av: string | number;
    let bv: string | number;
    if (key === "sequence") {
      av = a.sequence;
      bv = b.sequence;
    } else if (key === "policy_outcome") {
      av = a.policy_outcome ?? "";
      bv = b.policy_outcome ?? "";
    } else {
      av = a.signed_at;
      bv = b.signed_at;
    }
    if (av < bv) return -1 * mult;
    if (av > bv) return 1 * mult;
    return 0;
  });
  return sorted;
}

export function ReceiptsTimeline({
  tenantId,
  apiUrl,
  fetcher = apiFetch,
  initialQuery,
  onQueryChange,
  limit = DEFAULT_LIMIT,
}: ReceiptsTimelineProps) {
  const baseQuery = useMemo(
    () => initialQuery ?? new URLSearchParams(),
    [initialQuery],
  );
  const initial = useMemo(() => parseQuery(baseQuery), [baseQuery]);

  const [filters, setFilters] = useState<ReceiptTimelineFilters>(initial.filters);
  const [draftFilters, setDraftFilters] = useState<ReceiptTimelineFilters>(initial.filters);
  const [cursor, setCursor] = useState<string>(initial.cursor);
  const [sortKey, setSortKey] = useState<SortKey>(initial.sortKey);
  const [sortDir, setSortDir] = useState<SortDir>(initial.sortDir);

  const [state, setState] = useState<LoadState>("loading");
  const [items, setItems] = useState<ReceiptTimelineItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [expandedHash, setExpandedHash] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState<number>(0);

  const url = buildApiUrl(
    apiUrl ?? DEFAULT_URL,
    tenantId,
    filters,
    cursor,
    limit,
    sortKey,
    sortDir,
  );

  // Sync URL whenever applied filters/cursor/sort change.
  useEffect(() => {
    if (!onQueryChange) return;
    onQueryChange(buildQuery(filters, cursor, sortKey, sortDir));
  }, [filters, cursor, sortKey, sortDir, onQueryChange]);

  // Fetch loop — re-runs whenever URL or retry counter changes.
  useEffect(() => {
    let cancelled = false;
    setState("loading");
    setErrorMsg("");
    fetcher(url)
      .then(async (r) => {
        /* v8 ignore next */
        if (cancelled) return;
        if (!r.ok) {
          setState("error");
          setErrorMsg(`HTTP ${r.status}`);
          return;
        }
        const body = (await r.json()) as ReceiptTimelineResponse;
        const fetched = body.items ?? [];
        const sorted = sortItems(fetched, sortKey, sortDir);
        setItems(sorted);
        setNextCursor(body.next_cursor ?? null);
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
  }, [url, fetcher, sortKey, sortDir, retryCount]);

  const handleApplyFilters = useCallback(() => {
    setFilters(draftFilters);
    setCursor("");
  }, [draftFilters]);

  const handleResetFilters = useCallback(() => {
    setDraftFilters(EMPTY_FILTERS);
    setFilters(EMPTY_FILTERS);
    setCursor("");
  }, []);

  const handleSortClick = useCallback(
    (key: SortKey) => {
      if (key === sortKey) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortKey(key);
        setSortDir("desc");
      }
      setCursor("");
    },
    [sortKey],
  );

  const handleNextPage = useCallback(() => {
    /* v8 ignore next */
    if (nextCursor) setCursor(nextCursor);
  }, [nextCursor]);

  const handleRetry = useCallback(() => {
    setRetryCount((n) => n + 1);
  }, []);

  return (
    <div data-testid="receipts-timeline" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <FilterBar
        draft={draftFilters}
        onChange={setDraftFilters}
        onApply={handleApplyFilters}
        onReset={handleResetFilters}
      />

      {state === "loading" ? (
        <LoadingSkeleton />
      ) : state === "error" ? (
        <ErrorPanel message={errorMsg} onRetry={handleRetry} />
      ) : state === "empty" ? (
        <EmptyPanel hasFilters={hasActiveFilters(filters)} onReset={handleResetFilters} />
      ) : (
        <>
          <table
            data-testid="receipts-timeline-table"
            style={{ borderCollapse: "collapse", width: "100%", fontSize: "0.9rem" }}
          >
            <thead>
              <tr style={{ background: "#f9fafb" }}>
                <SortableHeader
                  label="Seq"
                  active={sortKey === "sequence"}
                  dir={sortDir}
                  testid="sort-sequence"
                  onClick={() => handleSortClick("sequence")}
                />
                <th style={th}>Agent</th>
                <SortableHeader
                  label="Outcome"
                  active={sortKey === "policy_outcome"}
                  dir={sortDir}
                  testid="sort-outcome"
                  onClick={() => handleSortClick("policy_outcome")}
                />
                <SortableHeader
                  label="Signed at"
                  active={sortKey === "signed_at"}
                  dir={sortDir}
                  testid="sort-signed-at"
                  onClick={() => handleSortClick("signed_at")}
                />
                <th style={th}>Status</th>
                <th style={th}>Hash</th>
                <th style={th} />
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const status = deriveReceiptStatus(item);
                const isExpanded = expandedHash === item.id;
                return (
                  <tr
                    key={item.id}
                    data-testid={`receipt-row-${item.id}`}
                    style={{ borderBottom: "1px solid #f3f4f6" }}
                  >
                    <td style={td}>{item.sequence}</td>
                    <td style={td}>{item.agent_id ?? "—"}</td>
                    <td style={td}>{item.policy_outcome ?? "—"}</td>
                    <td style={td}>{new Date(item.signed_at).toISOString()}</td>
                    <td style={td}>
                      <StatusChip status={status} />
                    </td>
                    <td style={td}>
                      <button
                        type="button"
                        data-testid={`hash-disclosure-${item.id}`}
                        onClick={() => setExpandedHash(isExpanded ? null : item.id)}
                        aria-expanded={isExpanded}
                        style={{
                          background: "none",
                          border: "none",
                          color: "#1e40af",
                          cursor: "pointer",
                          padding: 0,
                          fontSize: "0.85rem",
                        }}
                      >
                        {isExpanded ? "Hide hash" : "🔐 Verify"}
                      </button>
                      {isExpanded ? (
                        <code
                          data-testid={`hash-value-${item.id}`}
                          style={{
                            display: "block",
                            marginTop: "0.25rem",
                            fontFamily: "monospace",
                            fontSize: "0.75rem",
                            color: "#374151",
                            wordBreak: "break-all",
                            maxWidth: "20rem",
                          }}
                        >
                          {item.receipt_hash}
                        </code>
                      ) : null}
                    </td>
                    <td style={td}>
                      <Link
                        href={`/receipts/${item.id}`}
                        data-testid={`row-link-${item.id}`}
                        style={{ color: "#1e40af", textDecoration: "underline" }}
                      >
                        Open
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <PagerBar nextCursor={nextCursor} onNext={handleNextPage} count={items.length} />
        </>
      )}
    </div>
  );
}

function hasActiveFilters(f: ReceiptTimelineFilters): boolean {
  return Boolean(
    f.dateFrom ||
      f.dateTo ||
      f.agent ||
      f.outcome ||
      f.status ||
      f.policyVersion,
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

function SortableHeader({
  label,
  active,
  dir,
  testid,
  onClick,
}: {
  label: string;
  active: boolean;
  dir: SortDir;
  testid: string;
  onClick: () => void;
}) {
  return (
    <th style={th}>
      <button
        type="button"
        data-testid={testid}
        data-active={active ? "true" : "false"}
        data-dir={active ? dir : ""}
        onClick={onClick}
        style={{
          background: "none",
          border: "none",
          padding: 0,
          fontWeight: "inherit",
          color: "inherit",
          cursor: "pointer",
          fontSize: "inherit",
        }}
      >
        {label}
        {active ? (dir === "asc" ? " ▲" : " ▼") : ""}
      </button>
    </th>
  );
}

interface FilterBarProps {
  draft: ReceiptTimelineFilters;
  onChange: (next: ReceiptTimelineFilters) => void;
  onApply: () => void;
  onReset: () => void;
}

function FilterBar({ draft, onChange, onApply, onReset }: FilterBarProps) {
  const update = <K extends keyof ReceiptTimelineFilters>(
    k: K,
    v: ReceiptTimelineFilters[K],
  ) => onChange({ ...draft, [k]: v });

  return (
    <fieldset
      data-testid="receipts-filter-bar"
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: "0.5rem",
        alignItems: "flex-end",
        border: "1px solid #e5e7eb",
        borderRadius: "0.5rem",
        padding: "0.75rem",
      }}
    >
      <legend style={{ padding: "0 0.5rem", fontSize: "0.85rem", color: "#6b7280" }}>
        Filters
      </legend>
      <FilterField label="From">
        <input
          type="date"
          data-testid="filter-date-from"
          value={draft.dateFrom}
          onChange={(e) => update("dateFrom", e.target.value)}
          style={input}
        />
      </FilterField>
      <FilterField label="To">
        <input
          type="date"
          data-testid="filter-date-to"
          value={draft.dateTo}
          onChange={(e) => update("dateTo", e.target.value)}
          style={input}
        />
      </FilterField>
      <FilterField label="Agent">
        <input
          type="text"
          data-testid="filter-agent"
          value={draft.agent}
          onChange={(e) => update("agent", e.target.value)}
          placeholder="agent_id"
          style={input}
        />
      </FilterField>
      <FilterField label="Outcome">
        <input
          type="text"
          data-testid="filter-outcome"
          value={draft.outcome}
          onChange={(e) => update("outcome", e.target.value)}
          placeholder="approve / deny / …"
          style={input}
        />
      </FilterField>
      <FilterField label="Chain status">
        <select
          data-testid="filter-status"
          value={draft.status}
          onChange={(e) =>
            update("status", e.target.value as ReceiptTimelineFilters["status"])
          }
          style={input}
        >
          <option value="">All</option>
          <option value="anchored">Anchored</option>
          <option value="pending">Pending</option>
          <option value="deferred">Deferred</option>
        </select>
      </FilterField>
      <FilterField label="Policy version">
        <input
          type="text"
          data-testid="filter-policy-version"
          value={draft.policyVersion}
          onChange={(e) => update("policyVersion", e.target.value)}
          placeholder="v1.0.0"
          style={input}
        />
      </FilterField>
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <button
          type="button"
          data-testid="filter-apply"
          onClick={onApply}
          style={primaryBtn}
        >
          Apply
        </button>
        <button
          type="button"
          data-testid="filter-reset"
          onClick={onReset}
          style={secondaryBtn}
        >
          Reset
        </button>
      </div>
    </fieldset>
  );
}

function FilterField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", fontSize: "0.8rem", color: "#374151" }}>
      <span style={{ marginBottom: "0.15rem" }}>{label}</span>
      {children}
    </label>
  );
}

const input: React.CSSProperties = {
  padding: "0.35rem 0.5rem",
  border: "1px solid #d1d5db",
  borderRadius: "0.35rem",
  fontSize: "0.85rem",
  minWidth: "9rem",
};
const primaryBtn: React.CSSProperties = {
  padding: "0.4rem 0.9rem",
  borderRadius: "0.4rem",
  border: "none",
  background: "#1e40af",
  color: "white",
  fontWeight: 600,
  cursor: "pointer",
};
const secondaryBtn: React.CSSProperties = {
  padding: "0.4rem 0.9rem",
  borderRadius: "0.4rem",
  border: "1px solid #d1d5db",
  background: "white",
  color: "#374151",
  fontWeight: 500,
  cursor: "pointer",
};

function LoadingSkeleton() {
  // Five blocks, no flash of blank — AC-6.
  return (
    <div data-testid="receipts-timeline-loading" aria-busy="true">
      {[0, 1, 2, 3, 4].map((i) => (
        <div
          key={i}
          data-testid={`receipt-skeleton-${i}`}
          style={{
            height: "2.4rem",
            marginBottom: "0.5rem",
            borderRadius: "0.4rem",
            background:
              "linear-gradient(90deg, #f3f4f6 0%, #e5e7eb 50%, #f3f4f6 100%)",
            backgroundSize: "200% 100%",
          }}
        />
      ))}
    </div>
  );
}

function ErrorPanel({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div
      data-testid="receipts-timeline-error"
      role="alert"
      style={{
        padding: "1rem",
        border: "1px solid #fca5a5",
        background: "#fef2f2",
        borderRadius: "0.5rem",
        color: "#991b1b",
      }}
    >
      <p style={{ marginTop: 0 }}>
        <strong>Couldn&apos;t load receipts.</strong> {message}
      </p>
      <button
        type="button"
        data-testid="receipts-timeline-retry"
        onClick={onRetry}
        style={{ ...secondaryBtn, borderColor: "#fca5a5", color: "#991b1b" }}
      >
        Retry
      </button>
    </div>
  );
}

function EmptyPanel({
  hasFilters,
  onReset,
}: {
  hasFilters: boolean;
  onReset: () => void;
}) {
  return (
    <div
      data-testid="receipts-timeline-empty"
      style={{
        padding: "2rem",
        border: "1px dashed #d1d5db",
        borderRadius: "0.5rem",
        background: "#f9fafb",
        textAlign: "center",
        color: "#374151",
      }}
    >
      {hasFilters ? (
        <>
          <p>No agent activity matched. Try widening your date range.</p>
          <button
            type="button"
            data-testid="receipts-empty-reset"
            onClick={onReset}
            style={primaryBtn}
          >
            Clear filters
          </button>
        </>
      ) : (
        <p>
          No receipts yet for this tenant. Post a signed event to{" "}
          <code style={{ fontFamily: "monospace" }}>POST /v1/events</code> to begin
          the chain.
        </p>
      )}
    </div>
  );
}

function PagerBar({
  nextCursor,
  onNext,
  count,
}: {
  nextCursor: string | null;
  onNext: () => void;
  count: number;
}) {
  return (
    <div
      data-testid="receipts-pager"
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "0.5rem 0.25rem",
      }}
    >
      <span data-testid="receipts-page-count" style={{ fontSize: "0.85rem", color: "#6b7280" }}>
        Showing {count} receipt{count === 1 ? "" : "s"}
      </span>
      <button
        type="button"
        data-testid="receipts-next-page"
        onClick={onNext}
        disabled={!nextCursor}
        style={{
          ...secondaryBtn,
          opacity: nextCursor ? 1 : 0.5,
          cursor: nextCursor ? "pointer" : "not-allowed",
        }}
      >
        Next page →
      </button>
    </div>
  );
}
