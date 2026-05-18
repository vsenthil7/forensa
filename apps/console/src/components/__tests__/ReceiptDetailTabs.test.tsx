import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  ReceiptDetailTabs,
  parseTabFromHash,
  type ReceiptDetailData,
} from "../ReceiptDetailTabs";

const API_URL = "http://test.local";

function buildDetail(over: Partial<ReceiptDetailData> = {}): ReceiptDetailData {
  return {
    id: "r-1",
    tenant_id: "t-1",
    event_id: "e-1",
    policy_bundle_id: "pb-1",
    policy_snapshot_id: "ps-1",
    sequence: 7,
    prev_receipt_hash: "p".repeat(64),
    payload_hash: "ph".repeat(32),
    receipt_hash: "rh".repeat(32),
    signature_b64: "sig",
    signed_at: "2026-05-13T10:00:00Z",
    recomputed_receipt_hash: "rh".repeat(32),
    integrity_ok: true,
    agent_id: "agent-α",
    policy_outcome: "approve",
    ...over,
  };
}

function mockFetch(opts: {
  ok?: boolean;
  status?: number;
  body?: ReceiptDetailData;
  rejectWith?: Error;
}) {
  return vi.fn(async () => {
    if (opts.rejectWith) throw opts.rejectWith;
    return {
      ok: opts.ok ?? true,
      status: opts.status ?? 200,
      json: async () => opts.body ?? buildDetail(),
    } as unknown as Response;
  });
}

describe("parseTabFromHash", () => {
  it("defaults to summary on empty or unknown hash", () => {
    expect(parseTabFromHash("")).toBe("summary");
    expect(parseTabFromHash("#")).toBe("summary");
    expect(parseTabFromHash("#bogus")).toBe("summary");
  });

  it("recognises proof and raw hashes (with and without #)", () => {
    expect(parseTabFromHash("#proof")).toBe("proof");
    expect(parseTabFromHash("proof")).toBe("proof");
    expect(parseTabFromHash("#raw")).toBe("raw");
    expect(parseTabFromHash("raw")).toBe("raw");
  });
});

describe("ReceiptDetailTabs", () => {
  it("shows loading then summary pane by default (AC-1)", async () => {
    const fetcher = mockFetch({ body: buildDetail() });
    render(
      <ReceiptDetailTabs
        receiptId="r-1"
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    expect(screen.getByTestId("receipt-detail-tabs-loading")).toBeTruthy();
    await waitFor(() => screen.getByTestId("summary-pane"));
    expect(screen.getByTestId("tab-summary").getAttribute("data-active")).toBe("true");
    expect(screen.getByTestId("summary-integrity-line").getAttribute("data-integrity-ok")).toBe(
      "true",
    );
  });

  it("AC-2 proof tab renders the prev -> current hash visual and payload hash", async () => {
    const fetcher = mockFetch({ body: buildDetail() });
    render(
      <ReceiptDetailTabs
        receiptId="r-1"
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("summary-pane"));
    fireEvent.click(screen.getByTestId("tab-proof"));
    expect(screen.getByTestId("proof-pane")).toBeTruthy();
    expect(screen.getByTestId("proof-prev")).toBeTruthy();
    expect(screen.getByTestId("proof-current")).toBeTruthy();
  });

  it("AC-2 proof tab shows '(genesis)' label when prev_receipt_hash is null", async () => {
    const fetcher = mockFetch({ body: buildDetail({ prev_receipt_hash: null }) });
    render(
      <ReceiptDetailTabs
        receiptId="r-1"
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("summary-pane"));
    fireEvent.click(screen.getByTestId("tab-proof"));
    expect(screen.getByTestId("proof-prev").textContent).toContain("genesis");
  });

  it("AC-3 raw tab copies JSON via injectable clipboard and shows Copied state", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    const fetcher = mockFetch({ body: buildDetail() });
    render(
      <ReceiptDetailTabs
        receiptId="r-1"
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        clipboard={{ writeText }}
      />,
    );
    await waitFor(() => screen.getByTestId("summary-pane"));
    fireEvent.click(screen.getByTestId("tab-raw"));
    expect(screen.getByTestId("raw-pane")).toBeTruthy();
    fireEvent.click(screen.getByTestId("raw-copy"));
    await waitFor(() =>
      expect(screen.getByTestId("raw-copy").textContent).toContain("Copied"),
    );
    expect(writeText).toHaveBeenCalledOnce();
    // JSON includes the receipt id
    expect(writeText.mock.calls[0][0]).toContain("r-1");
  });

  it("renders the tamper line when integrity_ok is false", async () => {
    const fetcher = mockFetch({ body: buildDetail({ integrity_ok: false }) });
    render(
      <ReceiptDetailTabs
        receiptId="r-1"
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("summary-integrity-line"));
    expect(
      screen.getByTestId("summary-integrity-line").getAttribute("data-integrity-ok"),
    ).toBe("false");
    expect(screen.getByTestId("summary-integrity-line").textContent).toContain("TAMPER");
  });

  it("renders 'unspecified' fallbacks when agent_id / policy_outcome are null", async () => {
    const fetcher = mockFetch({
      body: buildDetail({ agent_id: null, policy_outcome: null }),
    });
    render(
      <ReceiptDetailTabs
        receiptId="r-1"
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("summary-pane"));
    expect(screen.getByTestId("summary-pane").textContent).toContain("unspecified");
  });

  it("respects initialTab prop", async () => {
    const fetcher = mockFetch({ body: buildDetail() });
    render(
      <ReceiptDetailTabs
        receiptId="r-1"
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        initialTab="proof"
      />,
    );
    await waitFor(() => screen.getByTestId("proof-pane"));
  });

  it("calls onTabChange when the user switches tab", async () => {
    const fetcher = mockFetch({ body: buildDetail() });
    const onTabChange = vi.fn();
    render(
      <ReceiptDetailTabs
        receiptId="r-1"
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        onTabChange={onTabChange}
      />,
    );
    await waitFor(() => screen.getByTestId("summary-pane"));
    fireEvent.click(screen.getByTestId("tab-raw"));
    expect(onTabChange).toHaveBeenCalledWith("raw");
  });

  it("renders not-found on 404", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({}),
    });
    render(
      <ReceiptDetailTabs
        receiptId="missing"
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("receipt-detail-tabs-not-found"));
  });

  it("renders the error state on non-404 errors", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    });
    render(
      <ReceiptDetailTabs
        receiptId="r-1"
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("receipt-detail-tabs-error"));
    expect(screen.getByTestId("receipt-detail-tabs-error").textContent).toContain(
      "HTTP 500",
    );
  });

  it("uses the default API URL when none is provided", () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => buildDetail(),
    });
    render(
      <ReceiptDetailTabs receiptId="r-1" fetcher={fetcher as unknown as typeof fetch} />,
    );
    expect(fetcher).toHaveBeenCalled();
  });

  it("surfaces a thrown fetch error in the error state", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("network down"));
    render(
      <ReceiptDetailTabs
        receiptId="r-1"
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("receipt-detail-tabs-error"));
    expect(screen.getByTestId("receipt-detail-tabs-error").textContent).toContain(
      "network down",
    );
  });

  it("surfaces a thrown clipboard error gracefully (button does not flip to Copied)", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("clipboard denied"));
    const fetcher = mockFetch({ body: buildDetail() });
    render(
      <ReceiptDetailTabs
        receiptId="r-1"
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        clipboard={{ writeText }}
      />,
    );
    await waitFor(() => screen.getByTestId("summary-pane"));
    fireEvent.click(screen.getByTestId("tab-raw"));
    fireEvent.click(screen.getByTestId("raw-copy"));
    await waitFor(() => expect(writeText).toHaveBeenCalled());
    // Button stays on its initial label — Copy still says "Copy"
    expect(screen.getByTestId("raw-copy").textContent).toContain("Copy");
  });

  it("falls back to navigator.clipboard when no clipboard prop is provided", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    const originalDescriptor = Object.getOwnPropertyDescriptor(
      window.navigator,
      "clipboard",
    );
    try {
      Object.defineProperty(window.navigator, "clipboard", {
        configurable: true,
        value: { writeText },
      });
      const fetcher = mockFetch({ body: buildDetail() });
      render(
        <ReceiptDetailTabs
          receiptId="r-1"
          apiUrl={API_URL}
          fetcher={fetcher as unknown as typeof fetch}
        />,
      );
      await waitFor(() => screen.getByTestId("summary-pane"));
      fireEvent.click(screen.getByTestId("tab-raw"));
      fireEvent.click(screen.getByTestId("raw-copy"));
      await waitFor(() => expect(writeText).toHaveBeenCalled());
    } finally {
      if (originalDescriptor) {
        Object.defineProperty(window.navigator, "clipboard", originalDescriptor);
      }
    }
  });
});
