import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AnchorsList, type AnchorListItem, type AnchorListResponse } from "../AnchorsList";

const TENANT_ID = "45a9c68b-7d72-4f03-ba1c-600ffd5099a9";
const API_URL = "http://test.local";

function makeAnchor(over: Partial<AnchorListItem> = {}): AnchorListItem {
  return {
    id: "anc-" + Math.random().toString(36).slice(2, 8),
    tenant_id: TENANT_ID,
    anchor_date: "2026-05-13T00:00:00Z",
    status: "anchored",
    root_hash: "f".repeat(64),
    tsa_identifier: "freetsa.org",
    tsr_bytes_b64: "AAAA",
    tsa_signature_b64: "AAAA",
    timestamped_at: "2026-05-13T00:08:51Z",
    anchored_at: "2026-05-13T00:08:51Z",
    ...over,
  };
}

function mockFetch(opts: {
  ok?: boolean;
  status?: number;
  body?: AnchorListResponse;
  rejectWith?: Error;
}) {
  return vi.fn(async (_input: string | URL | Request, _init?: RequestInit) => {
    if (opts.rejectWith) throw opts.rejectWith;
    return {
      ok: opts.ok ?? true,
      status: opts.status ?? 200,
      json: async () => opts.body ?? { items: [], tenant_id: TENANT_ID, count: 0 },
      blob: async () => new Blob(["DER"], { type: "application/timestamp-reply" }),
    } as unknown as Response;
  });
}

const originalCreateObjectURL = global.URL.createObjectURL;
const originalRevokeObjectURL = global.URL.revokeObjectURL;

beforeEach(() => {
  global.URL.createObjectURL = vi.fn().mockReturnValue("blob:fake");
  global.URL.revokeObjectURL = vi.fn();
});

afterEach(() => {
  global.URL.createObjectURL = originalCreateObjectURL;
  global.URL.revokeObjectURL = originalRevokeObjectURL;
});

describe("AnchorsList", () => {
  it("shows loading then the table when items arrive", async () => {
    const items = [makeAnchor({ id: "a1" }), makeAnchor({ id: "a2" })];
    const fetcher = mockFetch({
      body: { items, tenant_id: TENANT_ID, count: 2 },
    });
    render(
      <AnchorsList
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    expect(screen.getByTestId("anchors-list-loading")).toBeTruthy();
    await waitFor(() => screen.getByTestId("anchors-table"));
    expect(screen.getByTestId("anchor-row-a1")).toBeTruthy();
    expect(screen.getByTestId("anchor-row-a2")).toBeTruthy();
  });

  it("renders the empty state when no anchors are returned", async () => {
    const fetcher = mockFetch({
      body: { items: [], tenant_id: TENANT_ID, count: 0 },
    });
    render(
      <AnchorsList
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("anchors-list-empty"));
  });

  it("renders an error state when the list fetch returns non-ok", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    });
    render(
      <AnchorsList
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("anchors-list-error"));
    expect(screen.getByTestId("anchors-list-error").textContent).toContain("HTTP 500");
  });

  it("renders an error state when the list fetch throws", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("network"));
    render(
      <AnchorsList
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("anchors-list-error"));
    expect(screen.getByTestId("anchors-list-error").textContent).toContain("network");
  });

  it("shows the deferred indicator + no download button on a deferred row", async () => {
    const items = [
      makeAnchor({
        id: "ad",
        status: "deferred",
        tsr_bytes_b64: null,
        tsa_signature_b64: null,
        timestamped_at: null,
        root_hash: null,
      }),
    ];
    const fetcher = mockFetch({
      body: { items, tenant_id: TENANT_ID, count: 1 },
    });
    render(
      <AnchorsList
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("anchor-row-ad"));
    expect(screen.getByTestId("anchor-no-download-ad")).toBeTruthy();
    expect(screen.queryByTestId("anchor-download-ad")).toBeNull();
  });

  it("downloads the TSR DER when the download button is clicked (US-F16 UI access)", async () => {
    const items = [makeAnchor({ id: "a1" })];
    const fetcher = mockFetch({
      body: { items, tenant_id: TENANT_ID, count: 1 },
    });
    render(
      <AnchorsList
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("anchor-row-a1"));
    fireEvent.click(screen.getByTestId("anchor-download-a1"));
    await waitFor(() => expect(global.URL.createObjectURL).toHaveBeenCalled());
    // The second fetch call should set Accept: application/timestamp-reply.
    const detailCall = fetcher.mock.calls[1];
    const init = detailCall[1] as RequestInit;
    const headers = new Headers(init?.headers);
    expect(headers.get("Accept")).toBe("application/timestamp-reply");
  });

  it("surfaces a TSR download HTTP error", async () => {
    const items = [makeAnchor({ id: "a1" })];
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ items, tenant_id: TENANT_ID, count: 1 }),
        blob: async () => new Blob(),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
        json: async () => ({}),
        blob: async () => new Blob(),
      });
    render(
      <AnchorsList
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("anchor-row-a1"));
    fireEvent.click(screen.getByTestId("anchor-download-a1"));
    await waitFor(() => screen.getByTestId("anchor-download-error"));
    expect(screen.getByTestId("anchor-download-error").textContent).toContain("503");
  });

  it("surfaces a thrown TSR download error", async () => {
    const items = [makeAnchor({ id: "a1" })];
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ items, tenant_id: TENANT_ID, count: 1 }),
        blob: async () => new Blob(),
      })
      .mockRejectedValueOnce(new Error("boom"));
    render(
      <AnchorsList
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("anchor-row-a1"));
    fireEvent.click(screen.getByTestId("anchor-download-a1"));
    await waitFor(() => screen.getByTestId("anchor-download-error"));
    expect(screen.getByTestId("anchor-download-error").textContent).toContain("boom");
  });

  it("handles a missing items field gracefully (treats as empty)", async () => {
    const fetcher = mockFetch({
      body: {
        items: undefined as unknown as AnchorListItem[],
        tenant_id: TENANT_ID,
        count: 0,
      },
    });
    render(
      <AnchorsList
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("anchors-list-empty"));
  });

  it("renders '—' for missing root_hash + timestamped_at", async () => {
    const items = [
      makeAnchor({
        id: "a-x",
        status: "deferred",
        tsr_bytes_b64: null,
        timestamped_at: null,
        root_hash: null,
      }),
    ];
    const fetcher = mockFetch({
      body: { items, tenant_id: TENANT_ID, count: 1 },
    });
    render(
      <AnchorsList
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    await waitFor(() => screen.getByTestId("anchor-row-a-x"));
    expect(screen.getByTestId("anchor-row-a-x").textContent).toContain("—");
  });

  it("uses the default API URL when none is provided", () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], tenant_id: TENANT_ID, count: 0 }),
      blob: async () => new Blob(),
    });
    render(
      <AnchorsList
        tenantId={TENANT_ID}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    expect(fetcher).toHaveBeenCalled();
  });
});
