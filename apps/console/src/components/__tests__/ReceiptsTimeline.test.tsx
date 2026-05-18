import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  ReceiptsTimeline,
  buildApiUrl,
  buildQuery,
  EMPTY_FILTERS,
  parseQuery,
  sortItems,
  type ReceiptTimelineFilters,
  type ReceiptTimelineItem,
  type ReceiptTimelineResponse,
} from "../ReceiptsTimeline";

const TENANT_ID = "45a9c68b-7d72-4f03-ba1c-600ffd5099a9";
const API_URL = "http://test.local";

function makeItem(over: Partial<ReceiptTimelineItem> = {}): ReceiptTimelineItem {
  return {
    id: "r-" + Math.random().toString(36).slice(2, 9),
    tenant_id: TENANT_ID,
    event_id: "ev-1",
    policy_bundle_id: "pb-1",
    sequence: 0,
    prev_receipt_hash: null,
    payload_hash: "p".repeat(64),
    receipt_hash: "h".repeat(64),
    signature_b64: "sig",
    signed_at: "2026-05-13T10:00:00Z",
    agent_id: "agent-α",
    policy_outcome: "approve",
    policy_version: "v1.0.0",
    anchor_id: "anc-1",
    tsr_b64: "tsr",
    ...over,
  };
}

function mockFetch(opts: {
  ok?: boolean;
  status?: number;
  body?: ReceiptTimelineResponse;
  rejectWith?: Error;
}) {
  return vi.fn(async (_input: string | URL | Request) => {
    if (opts.rejectWith) throw opts.rejectWith;
    return {
      ok: opts.ok ?? true,
      status: opts.status ?? 200,
      json: async () => opts.body ?? { items: [] },
    } as unknown as Response;
  });
}

// ---------- helper-function tests ----------

describe("parseQuery", () => {
  it("returns EMPTY_FILTERS defaults on an empty query", () => {
    const out = parseQuery(new URLSearchParams());
    expect(out.filters).toEqual(EMPTY_FILTERS);
    expect(out.cursor).toBe("");
    expect(out.sortKey).toBe("signed_at");
    expect(out.sortDir).toBe("desc");
  });

  it("parses all filter, cursor, sort and dir fields", () => {
    const q = new URLSearchParams({
      from: "2026-05-13",
      to: "2026-05-14",
      agent: "a1",
      outcome: "deny",
      status: "anchored",
      pv: "v2",
      cursor: "c1",
      sort: "sequence",
      dir: "asc",
    });
    const out = parseQuery(q);
    expect(out.filters).toEqual({
      dateFrom: "2026-05-13",
      dateTo: "2026-05-14",
      agent: "a1",
      outcome: "deny",
      status: "anchored",
      policyVersion: "v2",
    });
    expect(out.cursor).toBe("c1");
    expect(out.sortKey).toBe("sequence");
    expect(out.sortDir).toBe("asc");
  });

  it("rejects unknown status / sort values, falling back to defaults", () => {
    const q = new URLSearchParams({ status: "weird", sort: "bogus", dir: "sideways" });
    const out = parseQuery(q);
    expect(out.filters.status).toBe("");
    expect(out.sortKey).toBe("signed_at");
    expect(out.sortDir).toBe("desc");
  });

  it("accepts policy_outcome as a sort key", () => {
    const out = parseQuery(new URLSearchParams({ sort: "policy_outcome" }));
    expect(out.sortKey).toBe("policy_outcome");
  });
});

describe("buildQuery", () => {
  it("returns an empty query for defaults", () => {
    const q = buildQuery(EMPTY_FILTERS, "", "signed_at", "desc");
    expect(q.toString()).toBe("");
  });

  it("serialises every populated filter, cursor, and non-default sort", () => {
    const f: ReceiptTimelineFilters = {
      dateFrom: "2026-05-13",
      dateTo: "2026-05-14",
      agent: "a",
      outcome: "o",
      status: "pending",
      policyVersion: "v",
    };
    const q = buildQuery(f, "cur", "sequence", "asc");
    expect(q.get("from")).toBe("2026-05-13");
    expect(q.get("to")).toBe("2026-05-14");
    expect(q.get("agent")).toBe("a");
    expect(q.get("outcome")).toBe("o");
    expect(q.get("status")).toBe("pending");
    expect(q.get("pv")).toBe("v");
    expect(q.get("cursor")).toBe("cur");
    expect(q.get("sort")).toBe("sequence");
    expect(q.get("dir")).toBe("asc");
  });

  it("omits sort/dir when they're at the default values", () => {
    const q = buildQuery(EMPTY_FILTERS, "", "signed_at", "desc");
    expect(q.has("sort")).toBe(false);
    expect(q.has("dir")).toBe(false);
  });
});

describe("buildApiUrl", () => {
  it("attaches tenant_id, limit, sort, and dir on a default call", () => {
    const url = buildApiUrl(API_URL, TENANT_ID, EMPTY_FILTERS, "", 50, "signed_at", "desc");
    expect(url).toContain("tenant_id=" + encodeURIComponent(TENANT_ID));
    expect(url).toContain("limit=50");
    expect(url).toContain("sort=signed_at");
    expect(url).toContain("dir=desc");
  });

  it("caps limit at the documented MAX_LIMIT (200)", () => {
    const url = buildApiUrl(API_URL, TENANT_ID, EMPTY_FILTERS, "", 999, "signed_at", "desc");
    expect(url).toContain("limit=200");
  });

  it("threads every filter through the URL", () => {
    const f: ReceiptTimelineFilters = {
      dateFrom: "2026-05-13",
      dateTo: "2026-05-14",
      agent: "ag",
      outcome: "approve",
      status: "anchored",
      policyVersion: "v2",
    };
    const url = buildApiUrl(API_URL, TENANT_ID, f, "cur1", 25, "sequence", "asc");
    expect(url).toContain("signed_after=2026-05-13");
    expect(url).toContain("signed_before=2026-05-14");
    expect(url).toContain("agent_id=ag");
    expect(url).toContain("policy_outcome=approve");
    expect(url).toContain("chain_status=anchored");
    expect(url).toContain("policy_version=v2");
    expect(url).toContain("cursor=cur1");
    expect(url).toContain("sort=sequence");
    expect(url).toContain("dir=asc");
  });
});

describe("sortItems", () => {
  const a = makeItem({ id: "a", sequence: 1, signed_at: "2026-01-01", policy_outcome: "approve" });
  const b = makeItem({ id: "b", sequence: 3, signed_at: "2026-03-01", policy_outcome: "deny" });
  const c = makeItem({ id: "c", sequence: 2, signed_at: "2026-02-01", policy_outcome: "approve" });

  it("sorts by signed_at desc by default", () => {
    const out = sortItems([a, c, b], "signed_at", "desc");
    expect(out.map((i) => i.id)).toEqual(["b", "c", "a"]);
  });

  it("sorts by signed_at asc when requested", () => {
    const out = sortItems([b, a, c], "signed_at", "asc");
    expect(out.map((i) => i.id)).toEqual(["a", "c", "b"]);
  });

  it("sorts by sequence", () => {
    const out = sortItems([b, a, c], "sequence", "asc");
    expect(out.map((i) => i.id)).toEqual(["a", "c", "b"]);
  });

  it("sorts by policy_outcome, treating null as empty string", () => {
    const d = makeItem({ id: "d", policy_outcome: null });
    const out = sortItems([a, d, b], "policy_outcome", "asc");
    // null/"" sorts before "approve" before "deny"
    expect(out[0].id).toBe("d");
    expect(out[out.length - 1].id).toBe("b");
  });

  it("returns equal-keyed items in their input order (stable enough for our use)", () => {
    const x = makeItem({ id: "x", sequence: 5 });
    const y = makeItem({ id: "y", sequence: 5 });
    const out = sortItems([x, y], "sequence", "asc");
    expect(out.map((i) => i.id)).toEqual(["x", "y"]);
  });
});

// ---------- component tests ----------

describe("ReceiptsTimeline component", () => {
  it("renders the loading skeleton then the table when items arrive", async () => {
    const items = [makeItem({ id: "r1", sequence: 1 }), makeItem({ id: "r2", sequence: 2 })];
    const fetcher = mockFetch({ body: { items, next_cursor: null } });
    render(
      <ReceiptsTimeline
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    expect(screen.getByTestId("receipts-timeline-loading")).toBeTruthy();
    await waitFor(() =>
      expect(screen.getByTestId("receipts-timeline-table")).toBeTruthy(),
    );
    expect(screen.getByTestId("receipt-row-r1")).toBeTruthy();
    expect(screen.getByTestId("receipt-row-r2")).toBeTruthy();
  });

  it("AC-7 empty state with CTA — first-time empty (no filters)", async () => {
    const fetcher = mockFetch({ body: { items: [], next_cursor: null } });
    render(
      <ReceiptsTimeline
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() =>
      expect(screen.getByTestId("receipts-timeline-empty")).toBeTruthy(),
    );
    expect(screen.queryByTestId("receipts-empty-reset")).toBeNull();
  });

  it("AC-7 empty state offers a clear filter-reset CTA when filters are active", async () => {
    const fetcher = mockFetch({ body: { items: [], next_cursor: null } });
    const initialQuery = new URLSearchParams({ agent: "ag-1" });
    render(
      <ReceiptsTimeline
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        initialQuery={initialQuery}
      />,
    );
    await waitFor(() =>
      expect(screen.getByTestId("receipts-empty-reset")).toBeTruthy(),
    );
    fireEvent.click(screen.getByTestId("receipts-empty-reset"));
    await waitFor(() => {
      const calls = fetcher.mock.calls.map((c) => String(c[0]));
      expect(calls.some((u) => !u.includes("agent_id=ag-1"))).toBe(true);
    });
  });

  it("AC-8 error state surfaces HTTP status and the retry button refires the fetch", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({}) })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ items: [makeItem()], next_cursor: null }),
      });
    render(
      <ReceiptsTimeline
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() =>
      expect(screen.getByTestId("receipts-timeline-error")).toBeTruthy(),
    );
    expect(screen.getByTestId("receipts-timeline-error").textContent).toContain("HTTP 500");
    fireEvent.click(screen.getByTestId("receipts-timeline-retry"));
    await waitFor(() =>
      expect(screen.getByTestId("receipts-timeline-table")).toBeTruthy(),
    );
  });

  it("AC-9 hash disclosure expands and collapses the receipt hash", async () => {
    const item = makeItem({ id: "r1", receipt_hash: "deadbeef".repeat(8) });
    const fetcher = mockFetch({ body: { items: [item], next_cursor: null } });
    render(
      <ReceiptsTimeline
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("receipt-row-r1"));
    const btn = screen.getByTestId("hash-disclosure-r1");
    expect(btn.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(btn);
    expect(btn.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByTestId("hash-value-r1").textContent).toBe(item.receipt_hash);
    fireEvent.click(btn);
    expect(btn.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByTestId("hash-value-r1")).toBeNull();
  });

  it("AC-4 column sort toggles direction on same key, switches to desc on new key", async () => {
    const fetcher = mockFetch({
      body: { items: [makeItem({ id: "r1" })], next_cursor: null },
    });
    const onQueryChange = vi.fn();
    render(
      <ReceiptsTimeline
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        onQueryChange={onQueryChange}
      />,
    );
    await waitFor(() => screen.getByTestId("receipts-timeline-table"));
    fireEvent.click(screen.getByTestId("sort-sequence"));
    await waitFor(() =>
      expect(screen.getByTestId("sort-sequence").getAttribute("data-active")).toBe("true"),
    );
    expect(screen.getByTestId("sort-sequence").getAttribute("data-dir")).toBe("desc");
    fireEvent.click(screen.getByTestId("sort-sequence"));
    await waitFor(() =>
      expect(screen.getByTestId("sort-sequence").getAttribute("data-dir")).toBe("asc"),
    );
    // Click sort-sequence again to flip back asc -> desc (the other branch of the toggle)
    fireEvent.click(screen.getByTestId("sort-sequence"));
    await waitFor(() =>
      expect(screen.getByTestId("sort-sequence").getAttribute("data-dir")).toBe("desc"),
    );
    // Click signed_at — different key — should reset to desc
    fireEvent.click(screen.getByTestId("sort-signed-at"));
    await waitFor(() =>
      expect(screen.getByTestId("sort-signed-at").getAttribute("data-dir")).toBe("desc"),
    );
  });

  it("AC-2 + AC-3 applying filters updates URL query and refires fetch", async () => {
    const fetcher = mockFetch({ body: { items: [], next_cursor: null } });
    const onQueryChange = vi.fn();
    render(
      <ReceiptsTimeline
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        onQueryChange={onQueryChange}
      />,
    );
    await waitFor(() => screen.getByTestId("filter-apply"));

    fireEvent.change(screen.getByTestId("filter-date-from"), {
      target: { value: "2026-05-13" },
    });
    fireEvent.change(screen.getByTestId("filter-agent"), {
      target: { value: "ag-1" },
    });
    fireEvent.change(screen.getByTestId("filter-outcome"), {
      target: { value: "approve" },
    });
    fireEvent.change(screen.getByTestId("filter-status"), {
      target: { value: "pending" },
    });
    fireEvent.change(screen.getByTestId("filter-policy-version"), {
      target: { value: "v2" },
    });
    fireEvent.change(screen.getByTestId("filter-date-to"), {
      target: { value: "2026-05-14" },
    });
    fireEvent.click(screen.getByTestId("filter-apply"));

    await waitFor(() => {
      const lastUrl = String(fetcher.mock.calls.at(-1)?.[0] ?? "");
      expect(lastUrl).toContain("agent_id=ag-1");
      expect(lastUrl).toContain("policy_outcome=approve");
      expect(lastUrl).toContain("chain_status=pending");
    });
    // The URL-query callback fired with the same filters
    const lastQ = onQueryChange.mock.calls.at(-1)?.[0] as URLSearchParams | undefined;
    expect(lastQ?.get("agent")).toBe("ag-1");
    expect(lastQ?.get("status")).toBe("pending");
  });

  it("filter Reset clears draft + applied filters", async () => {
    const fetcher = mockFetch({ body: { items: [makeItem()], next_cursor: null } });
    const initialQuery = new URLSearchParams({ agent: "ag-1" });
    render(
      <ReceiptsTimeline
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        initialQuery={initialQuery}
      />,
    );
    await waitFor(() => screen.getByTestId("filter-reset"));
    fireEvent.click(screen.getByTestId("filter-reset"));
    await waitFor(() => {
      const lastUrl = String(fetcher.mock.calls.at(-1)?.[0] ?? "");
      expect(lastUrl.includes("agent_id=")).toBe(false);
    });
  });

  it("AC-1 pager 'Next page' advances using next_cursor", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ items: [makeItem({ id: "r1" })], next_cursor: "cursor-1" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ items: [makeItem({ id: "r2" })], next_cursor: null }),
      });
    render(
      <ReceiptsTimeline
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("receipt-row-r1"));
    const next = screen.getByTestId("receipts-next-page") as HTMLButtonElement;
    expect(next.disabled).toBe(false);
    fireEvent.click(next);
    await waitFor(() => screen.getByTestId("receipt-row-r2"));
    expect(
      (screen.getByTestId("receipts-next-page") as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("pager Next-page does nothing when next_cursor is null (button stays disabled)", async () => {
    const fetcher = mockFetch({ body: { items: [makeItem({ id: "r1" })], next_cursor: null } });
    render(
      <ReceiptsTimeline
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("receipt-row-r1"));
    const next = screen.getByTestId("receipts-next-page") as HTMLButtonElement;
    expect(next.disabled).toBe(true);
    fireEvent.click(next); // no-op
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("renders a missing items field as empty (no crash)", async () => {
    const fetcher = mockFetch({
      body: { items: undefined as unknown as ReceiptTimelineItem[] },
    });
    render(
      <ReceiptsTimeline
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("receipts-timeline-empty"));
  });

  it("shows '—' for missing agent_id / policy_outcome", async () => {
    const item = makeItem({ id: "r1", agent_id: null, policy_outcome: null });
    const fetcher = mockFetch({ body: { items: [item], next_cursor: null } });
    render(
      <ReceiptsTimeline
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("receipt-row-r1"));
    const row = screen.getByTestId("receipt-row-r1");
    expect(row.textContent).toContain("—");
  });

  it("uses tenantId-default apiUrl when not provided (smoke; no network in test)", () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [] }),
    });
    render(
      <ReceiptsTimeline
        tenantId={TENANT_ID}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    expect(fetcher).toHaveBeenCalled();
  });

  it("renders '1 receipt' singular when count === 1", async () => {
    const fetcher = mockFetch({ body: { items: [makeItem({ id: "r1" })], next_cursor: null } });
    render(
      <ReceiptsTimeline
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() =>
      expect(screen.getByTestId("receipts-page-count").textContent).toBe(
        "Showing 1 receipt",
      ),
    );
  });

  it("surfaces a thrown fetch error in the error state", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("kaboom"));
    render(
      <ReceiptsTimeline
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("receipts-timeline-error"));
    expect(screen.getByTestId("receipts-timeline-error").textContent).toContain(
      "kaboom",
    );
  });

  it("clicking the outcome column header sorts by policy_outcome", async () => {
    const fetcher = mockFetch({
      body: { items: [makeItem({ id: "r1" })], next_cursor: null },
    });
    render(
      <ReceiptsTimeline
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("receipts-timeline-table"));
    fireEvent.click(screen.getByTestId("sort-outcome"));
    await waitFor(() => {
      const lastUrl = String(fetcher.mock.calls.at(-1)?.[0] ?? "");
      expect(lastUrl).toContain("sort=policy_outcome");
    });
  });
});
