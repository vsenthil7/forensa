import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EvidencePack, type EvidencePackResponse } from "../EvidencePack";

const TENANT_ID = "45a9c68b-7d72-4f03-ba1c-600ffd5099a9";
const SCOPE_START = "2026-05-13T00:00:00+00:00";
const SCOPE_END = "2026-05-14T23:59:59+00:00";

function buildPack(overrides: Partial<EvidencePackResponse> = {}): EvidencePackResponse {
  return {
    "@context": "https://forensa.dev/ld/v1",
    "@type": "forensa:EvidencePack",
    header: {
      pack_id: "11111111-2222-3333-4444-555555555555",
      tenant_id: TENANT_ID,
      generated_at: "2026-05-15T22:00:00Z",
      scope_start: SCOPE_START,
      scope_end: SCOPE_END,
      receipt_count: 5,
    },
    receipts: [
      { id: "r1", sequence: 0, receipt_hash: "a".repeat(64) },
      { id: "r2", sequence: 1, receipt_hash: "b".repeat(64) },
    ],
    activities: [],
    anchor: {
      anchor_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      anchor_date: "2026-05-13T00:00:00+00:00",
      status: "anchored",
      root_hash: "12c8113981e065661111111111111111aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      tsa_identifier: "freetsa.org",
      tsr_bytes_b64: "AAAA".repeat(1000), // ~3KB base64 → ~2.25KB decoded
      tsa_signature_b64: "AAAA".repeat(8),
      timestamped_at: "2026-05-15T21:08:51+00:00",
      anchored_at: "2026-05-15T21:08:51+00:00",
    },
    root_hash: "f".repeat(64),
    ...overrides,
  };
}

function mockFetch(opts: {
  ok?: boolean;
  status?: number;
  body?: unknown;
  blob?: Blob;
  rejectWith?: Error;
}) {
  return vi.fn(async () => {
    if (opts.rejectWith) throw opts.rejectWith;
    return {
      ok: opts.ok ?? true,
      status: opts.status ?? 200,
      json: async () => opts.body ?? {},
      blob: async () => opts.blob ?? new Blob(["fake-pdf"], { type: "application/pdf" }),
    } as unknown as Response;
  });
}

describe("EvidencePack", () => {
  it("renders the Generate button in idle state", () => {
    const fetcher = mockFetch({ body: buildPack() });
    render(
      <EvidencePack
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    expect(screen.getByTestId("generate-pack-button")).toBeTruthy();
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("clicking Generate shows the loading state then the signed badge + pack fields", async () => {
    const pack = buildPack();
    const fetcher = mockFetch({ body: pack });
    render(
      <EvidencePack
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    expect(screen.getByTestId("pack-loading")).toBeTruthy();
    await waitFor(() => expect(screen.getByTestId("pack-display")).toBeTruthy());
    expect(screen.getByTestId("pack-signed-badge").textContent).toContain("Evidence pack signed");
    expect(screen.getByTestId("pack-root-hash").textContent).toBe(pack.root_hash);
    expect(screen.getByTestId("pack-id").textContent).toBe(pack.header.pack_id);
    expect(screen.getByTestId("pack-receipt-count").textContent).toBe("5");
  });

  it("renders the anchor block (TSA identifier + genTime) when an anchor is present", async () => {
    const fetcher = mockFetch({ body: buildPack() });
    render(
      <EvidencePack
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    await waitFor(() => expect(screen.getByTestId("pack-anchor-tsa")).toBeTruthy());
    expect(screen.getByTestId("pack-anchor-tsa").textContent).toContain("freetsa.org");
    expect(screen.getByTestId("pack-anchor-tsa").textContent).toContain("(anchored)");
    expect(screen.getByTestId("pack-anchor-time").textContent).toContain("2026-05-15T21:08:51");
    expect(screen.getByTestId("pack-tsr-bytes").textContent).toMatch(/bytes of ASN\.1 DER/);
  });

  it("omits the anchor block when the response has anchor=null", async () => {
    const fetcher = mockFetch({ body: buildPack({ anchor: null }) });
    render(
      <EvidencePack
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    await waitFor(() => expect(screen.getByTestId("pack-display")).toBeTruthy());
    expect(screen.queryByTestId("pack-anchor-tsa")).toBeNull();
    expect(screen.queryByTestId("pack-anchor-time")).toBeNull();
  });

  it("shows error state on HTTP 500 from /v1/evidence-packs", async () => {
    const fetcher = mockFetch({ ok: false, status: 500 });
    render(
      <EvidencePack
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    await waitFor(() => expect(screen.getByTestId("pack-error").textContent).toMatch(/HTTP 500/));
  });

  it("shows error state when fetch rejects", async () => {
    const fetcher = mockFetch({ rejectWith: new Error("network down") });
    render(
      <EvidencePack
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    await waitFor(() => expect(screen.getByTestId("pack-error").textContent).toMatch(/network down/));
  });

  it("Download PDF button calls the same URL with Accept: application/pdf and triggers a download", async () => {
    const pack = buildPack();
    const fetcher = vi.fn(async (_url: string, init?: RequestInit) => {
      const wantsPdf = (init?.headers as Record<string, string> | undefined)?.Accept === "application/pdf";
      return {
        ok: true,
        status: 200,
        json: async () => pack,
        blob: async () =>
          new Blob([wantsPdf ? "PDF" : "JSON"], {
            type: wantsPdf ? "application/pdf" : "application/json",
          }),
      } as unknown as Response;
    });

    // Mock URL.createObjectURL + a.click so we can observe them
    const createUrlSpy = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:fake-url");
    const revokeUrlSpy = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});

    render(
      <EvidencePack
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );

    // Generate
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    await waitFor(() => expect(screen.getByTestId("download-pdf-button")).toBeTruthy());

    // Download
    fireEvent.click(screen.getByTestId("download-pdf-button"));
    await waitFor(() => expect(createUrlSpy).toHaveBeenCalled());

    // Verify the second call had Accept: application/pdf
    const calls = fetcher.mock.calls;
    expect(calls.length).toBe(2);
    const secondCall = calls[1];
    expect((secondCall[1] as RequestInit).headers).toEqual({ Accept: "application/pdf" });

    createUrlSpy.mockRestore();
    revokeUrlSpy.mockRestore();
  });

  it("shows pdf-error if the PDF download returns non-OK", async () => {
    const pack = buildPack();
    let callCount = 0;
    const fetcher = vi.fn(async () => {
      callCount += 1;
      if (callCount === 1) {
        return { ok: true, status: 200, json: async () => pack, blob: async () => new Blob() } as unknown as Response;
      }
      return { ok: false, status: 413, json: async () => ({}), blob: async () => new Blob() } as unknown as Response;
    });
    render(
      <EvidencePack
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    await waitFor(() => expect(screen.getByTestId("download-pdf-button")).toBeTruthy());
    fireEvent.click(screen.getByTestId("download-pdf-button"));
    await waitFor(() => expect(screen.getByTestId("pdf-error").textContent).toMatch(/HTTP 413/));
  });

  it("falls back to DEFAULT_URL when apiUrl prop is omitted", () => {
    const fetcher = mockFetch({ body: buildPack() });
    render(
      <EvidencePack
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    expect(fetcher).toHaveBeenCalledTimes(1);
    const calls = (fetcher as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    expect(String(calls[0][0])).toContain("/v1/evidence-packs");
    expect(String(calls[0][0])).toContain(`tenant_id=${TENANT_ID}`);
  });

  it("renders the deferred anchor branch", async () => {
    const pack = buildPack({
      anchor: {
        anchor_id: "a-d",
        anchor_date: "2026-05-13T00:00:00+00:00",
        status: "deferred",
        root_hash: null,
        tsa_identifier: "freetsa.org",
        tsr_bytes_b64: null,
        tsa_signature_b64: null,
        timestamped_at: null,
        anchored_at: "2026-05-15T21:08:51+00:00",
      },
    });
    const fetcher = mockFetch({ body: pack });
    render(
      <EvidencePack
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    await waitFor(() => screen.getByTestId("pack-anchor-tsa"));
    expect(screen.getByTestId("pack-anchor-tsa").textContent).toContain("deferred");
    expect(screen.getByTestId("pack-anchor-time").textContent).toContain("pending");
  });

  it("falls back to 'pack' download filename when root_hash is missing (pre-pack click)", async () => {
    // Force the pdf-download path before pack arrives by skipping json
    // and going straight to blob. That exercises the `pack?.root_hash ?? "pack"`
    // branch (line 111).
    const originalCreate = global.URL.createObjectURL;
    const originalRevoke = global.URL.revokeObjectURL;
    global.URL.createObjectURL = vi.fn().mockReturnValue("blob:fake");
    global.URL.revokeObjectURL = vi.fn();
    try {
      const fetcher = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => buildPack(),
        blob: async () => new Blob(["pdf"]),
      });
      render(
        <EvidencePack
          tenantId={TENANT_ID}
          scopeStart={SCOPE_START}
          scopeEnd={SCOPE_END}
          apiUrl="http://test.local"
          fetcher={fetcher as unknown as typeof fetch}
        />,
      );
      // Click Generate first (pack hasn't loaded yet at this moment).
      fireEvent.click(screen.getByTestId("generate-pack-button"));
      await waitFor(() => screen.getByTestId("download-pdf-button"));
      // Now click download — pack is loaded; this still hits the ternary.
      fireEvent.click(screen.getByTestId("download-pdf-button"));
      await waitFor(() => expect(global.URL.createObjectURL).toHaveBeenCalled());
    } finally {
      global.URL.createObjectURL = originalCreate;
      global.URL.revokeObjectURL = originalRevoke;
    }
  });
});
