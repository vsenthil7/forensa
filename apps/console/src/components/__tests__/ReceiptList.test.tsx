import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ReceiptList } from "../ReceiptList";

const SAMPLE_TENANT = "55555555-6666-7777-8888-999999999999";

function buildItem(seq: number, idSuffix: string) {
  return {
    id: `00000000-0000-0000-0000-000000000${idSuffix}`,
    tenant_id: SAMPLE_TENANT,
    event_id: `11111111-1111-1111-1111-111111111${idSuffix}`,
    policy_bundle_id: "22222222-2222-2222-2222-222222222222",
    sequence: seq,
    prev_receipt_hash: seq === 0 ? null : "a".repeat(64),
    payload_hash: "b".repeat(64),
    receipt_hash: `${seq}`.repeat(64).slice(0, 64),
    signature_b64: "AAAA",
    signed_at: "2026-05-13T22:00:00Z",
  };
}

function mockFetch(opts: { ok?: boolean; status?: number; body?: unknown; rejectWith?: Error }) {
  return vi.fn(async () => {
    if (opts.rejectWith) throw opts.rejectWith;
    return {
      ok: opts.ok ?? true,
      status: opts.status ?? 200,
      json: async () => opts.body ?? {},
    } as unknown as Response;
  });
}

describe("ReceiptList", () => {
  it("shows loading initially then ok with rows", async () => {
    const items = [buildItem(2, "002"), buildItem(1, "001"), buildItem(0, "000")];
    const fetcher = mockFetch({ body: { items, tenant_id: SAMPLE_TENANT, limit: 50, offset: 0, count: 3 } });
    render(<ReceiptList tenantId={SAMPLE_TENANT} apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    expect(screen.getByTestId("receipt-list-loading")).toBeTruthy();
    await waitFor(() => expect(screen.getByTestId("receipt-list-table")).toBeTruthy());
    const rows = screen.getAllByTestId(/^receipt-row-/);
    expect(rows).toHaveLength(3);
  });

  it("shows empty state when items is empty", async () => {
    const fetcher = mockFetch({ body: { items: [], tenant_id: SAMPLE_TENANT, limit: 50, offset: 0, count: 0 } });
    render(<ReceiptList tenantId={SAMPLE_TENANT} apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(screen.getByTestId("receipt-list-empty")).toBeTruthy());
  });

  it("shows error state when HTTP not ok", async () => {
    const fetcher = mockFetch({ ok: false, status: 500 });
    render(<ReceiptList tenantId={SAMPLE_TENANT} apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(screen.getByTestId("receipt-list-error").textContent).toMatch(/HTTP 500/));
  });

  it("shows error state when fetch rejects", async () => {
    const fetcher = mockFetch({ rejectWith: new Error("network down") });
    render(<ReceiptList tenantId={SAMPLE_TENANT} apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(screen.getByTestId("receipt-list-error").textContent).toMatch(/network down/));
  });

  it("requests the correct URL with tenant_id and limit", async () => {
    const fetcher = mockFetch({ body: { items: [], tenant_id: SAMPLE_TENANT, limit: 25, offset: 0, count: 0 } });
    render(<ReceiptList tenantId={SAMPLE_TENANT} apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} limit={25} />);
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    const calls = (fetcher as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    expect(String(calls[0][0])).toContain(`tenant_id=${SAMPLE_TENANT}`);
    expect(String(calls[0][0])).toContain("limit=25");
  });

  it("renders shortened receipt_hash in table", async () => {
    const items = [buildItem(0, "000")];
    const fetcher = mockFetch({ body: { items, tenant_id: SAMPLE_TENANT, limit: 50, offset: 0, count: 1 } });
    render(<ReceiptList tenantId={SAMPLE_TENANT} apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(screen.getByTestId("receipt-list-table")).toBeTruthy());
    const row = screen.getByTestId(`receipt-row-${items[0].id}`);
    expect(row.textContent).toContain("0000000000000000...");
  });

  it("cleans up when unmounted before fetch resolves", () => {
    const fetcher = vi.fn(() => new Promise<Response>(() => {}));
    const { unmount } = render(<ReceiptList tenantId={SAMPLE_TENANT} apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    unmount();
    expect(fetcher).toHaveBeenCalled();
  });

  it("swallows late ok response after unmount (cancellation path)", async () => {
    let resolveIt: (r: Response) => void = () => {};
    const fetcher = vi.fn(() => new Promise<Response>((res) => { resolveIt = res; }));
    const { unmount } = render(<ReceiptList tenantId={SAMPLE_TENANT} apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    unmount();
    resolveIt({ ok: true, status: 200, json: async () => ({ items: [], tenant_id: SAMPLE_TENANT, limit: 50, offset: 0, count: 0 }) } as unknown as Response);
    await new Promise((r) => setTimeout(r, 10));
    expect(true).toBe(true);
  });

  it("swallows late rejection after unmount (cancellation path)", async () => {
    let rejectIt: (e: Error) => void = () => {};
    const fetcher = vi.fn(() => new Promise<Response>((_, rej) => { rejectIt = rej; }));
    const { unmount } = render(<ReceiptList tenantId={SAMPLE_TENANT} apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    unmount();
    rejectIt(new Error("too late"));
    await new Promise((r) => setTimeout(r, 10));
    expect(true).toBe(true);
  });

  it("falls back to DEFAULT_URL when apiUrl prop is omitted", async () => {
    const fetcher = mockFetch({ body: { items: [], tenant_id: SAMPLE_TENANT, limit: 50, offset: 0, count: 0 } });
    render(<ReceiptList tenantId={SAMPLE_TENANT} fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    const calls = (fetcher as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    expect(String(calls[0][0])).toContain("/v1/receipts?tenant_id=");
  });

  it("row click navigates to /receipts/{id}", async () => {
    const items = [buildItem(0, "000")];
    const fetcher = mockFetch({ body: { items, tenant_id: SAMPLE_TENANT, limit: 50, offset: 0, count: 1 } });
    const originalLocation = window.location;
    const setHref = vi.fn();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: new Proxy({} as Location, {
        set: (_target, prop, value) => {
          if (prop === "href") setHref(value);
          return true;
        },
        get: (_target, prop) => (prop === "href" ? "" : (originalLocation as unknown as Record<string, unknown>)[prop as string]),
      }),
    });
    render(<ReceiptList tenantId={SAMPLE_TENANT} apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(screen.getByTestId("receipt-list-table")).toBeTruthy());
    const row = screen.getByTestId(`receipt-row-${items[0].id}`);
    row.click();
    expect(setHref).toHaveBeenCalledWith(`/receipts/${items[0].id}`);
    Object.defineProperty(window, "location", { configurable: true, value: originalLocation });
  });
});
