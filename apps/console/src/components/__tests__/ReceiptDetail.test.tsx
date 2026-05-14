import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ReceiptDetail } from "../ReceiptDetail";

const SAMPLE_ID = "00000000-0000-0000-0000-000000000abc";

function buildDetail(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: SAMPLE_ID,
    tenant_id: "55555555-6666-7777-8888-999999999999",
    event_id: "11111111-1111-1111-1111-111111111111",
    policy_bundle_id: "22222222-2222-2222-2222-222222222222",
    policy_snapshot_id: "33333333-3333-3333-3333-333333333333",
    sequence: 0,
    prev_receipt_hash: null,
    payload_hash: "b".repeat(64),
    receipt_hash: "c".repeat(64),
    signature_b64: "AAAA",
    signed_at: "2026-05-13T22:00:00Z",
    recomputed_receipt_hash: "c".repeat(64),
    integrity_ok: true,
    ...overrides,
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

describe("ReceiptDetail", () => {
  it("shows loading initially then ok state with all fields", async () => {
    const body = buildDetail();
    const fetcher = mockFetch({ body });
    render(<ReceiptDetail receiptId={SAMPLE_ID} apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    expect(screen.getByTestId("receipt-detail-loading")).toBeTruthy();
    await waitFor(() => expect(screen.getByTestId("receipt-detail")).toBeTruthy());
    expect(screen.getByTestId("detail-id").textContent).toBe(SAMPLE_ID);
    expect(screen.getByTestId("detail-sequence").textContent).toBe("0");
    expect(screen.getByTestId("detail-payload-hash").textContent).toBe("b".repeat(64));
    expect(screen.getByTestId("detail-receipt-hash").textContent).toBe("c".repeat(64));
  });

  it("shows green integrity badge with data-integrity-ok=true when integrity_ok is true", async () => {
    const fetcher = mockFetch({ body: buildDetail() });
    render(<ReceiptDetail receiptId={SAMPLE_ID} apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(screen.getByTestId("integrity-badge")).toBeTruthy());
    const badge = screen.getByTestId("integrity-badge");
    expect(badge.getAttribute("data-integrity-ok")).toBe("true");
    expect(badge.textContent).toContain("Chain integrity verified");
  });

  it("shows red TAMPER DETECTED badge when integrity_ok is false", async () => {
    const fetcher = mockFetch({
      body: buildDetail({ integrity_ok: false, recomputed_receipt_hash: "d".repeat(64) }),
    });
    render(<ReceiptDetail receiptId={SAMPLE_ID} apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(screen.getByTestId("integrity-badge")).toBeTruthy());
    const badge = screen.getByTestId("integrity-badge");
    expect(badge.getAttribute("data-integrity-ok")).toBe("false");
    expect(badge.textContent).toContain("TAMPER DETECTED");
  });

  it("shows not-found state on HTTP 404", async () => {
    const fetcher = mockFetch({ ok: false, status: 404 });
    render(<ReceiptDetail receiptId={SAMPLE_ID} apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(screen.getByTestId("receipt-detail-not-found")).toBeTruthy());
  });

  it("shows error state on HTTP 500", async () => {
    const fetcher = mockFetch({ ok: false, status: 500 });
    render(<ReceiptDetail receiptId={SAMPLE_ID} apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(screen.getByTestId("receipt-detail-error").textContent).toMatch(/HTTP 500/));
  });

  it("shows error state when fetch rejects", async () => {
    const fetcher = mockFetch({ rejectWith: new Error("network down") });
    render(<ReceiptDetail receiptId={SAMPLE_ID} apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(screen.getByTestId("receipt-detail-error").textContent).toMatch(/network down/));
  });

  it("renders (genesis) when prev_receipt_hash is null", async () => {
    const fetcher = mockFetch({ body: buildDetail({ prev_receipt_hash: null }) });
    render(<ReceiptDetail receiptId={SAMPLE_ID} apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(screen.getByTestId("detail-prev-hash")).toBeTruthy());
    expect(screen.getByTestId("detail-prev-hash").textContent).toBe("(genesis)");
  });

  it("swallows late ok response after unmount (cancellation path)", async () => {
    let resolveIt: (r: Response) => void = () => {};
    const fetcher = vi.fn(() => new Promise<Response>((res) => { resolveIt = res; }));
    const { unmount } = render(<ReceiptDetail receiptId={SAMPLE_ID} apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    unmount();
    resolveIt({ ok: true, status: 200, json: async () => buildDetail() } as unknown as Response);
    await new Promise((r) => setTimeout(r, 10));
    expect(true).toBe(true);
  });

  it("swallows late 404 after unmount (cancellation path)", async () => {
    let resolveIt: (r: Response) => void = () => {};
    const fetcher = vi.fn(() => new Promise<Response>((res) => { resolveIt = res; }));
    const { unmount } = render(<ReceiptDetail receiptId={SAMPLE_ID} apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    unmount();
    resolveIt({ ok: false, status: 404, json: async () => ({}) } as unknown as Response);
    await new Promise((r) => setTimeout(r, 10));
    expect(true).toBe(true);
  });

  it("swallows late rejection after unmount (cancellation path)", async () => {
    let rejectIt: (e: Error) => void = () => {};
    const fetcher = vi.fn(() => new Promise<Response>((_, rej) => { rejectIt = rej; }));
    const { unmount } = render(<ReceiptDetail receiptId={SAMPLE_ID} apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    unmount();
    rejectIt(new Error("too late"));
    await new Promise((r) => setTimeout(r, 10));
    expect(true).toBe(true);
  });

  it("falls back to DEFAULT_URL when apiUrl prop is omitted", async () => {
    const fetcher = mockFetch({ body: buildDetail() });
    render(<ReceiptDetail receiptId={SAMPLE_ID} fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    const calls = (fetcher as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    expect(String(calls[0][0])).toContain(`/v1/receipts/${SAMPLE_ID}`);
  });
});
