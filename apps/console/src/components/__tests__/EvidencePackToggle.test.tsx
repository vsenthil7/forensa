import { fireEvent, render, screen, waitFor, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EvidencePackToggle } from "../EvidencePackToggle";
import type { EvidencePackResponse } from "../EvidencePack";

const TENANT_ID = "45a9c68b-7d72-4f03-ba1c-600ffd5099a9";
const SCOPE_START = "2026-05-13T00:00:00+00:00";
const SCOPE_END = "2026-05-14T23:59:59+00:00";

function buildPack(over: Partial<EvidencePackResponse> = {}): EvidencePackResponse {
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
    receipts: [],
    activities: [],
    anchor: {
      anchor_id: "a-1",
      anchor_date: "2026-05-13T00:00:00+00:00",
      status: "anchored",
      root_hash: "f".repeat(64),
      tsa_identifier: "freetsa.org",
      tsr_bytes_b64: "AAAA",
      tsa_signature_b64: "AAAA",
      timestamped_at: "2026-05-15T21:08:51+00:00",
      anchored_at: "2026-05-15T21:08:51+00:00",
    },
    root_hash: "f".repeat(64),
    ...over,
  };
}

function mockFetch(opts: {
  ok?: boolean;
  status?: number;
  body?: EvidencePackResponse;
  blob?: Blob;
}) {
  return vi.fn(async () => ({
    ok: opts.ok ?? true,
    status: opts.status ?? 200,
    json: async () => opts.body ?? buildPack(),
    blob: async () =>
      opts.blob ?? new Blob(["fake-pdf"], { type: "application/pdf" }),
  } as unknown as Response));
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
  vi.useRealTimers();
});

describe("EvidencePackToggle", () => {
  it("defaults to Compliance view + idle CTA", () => {
    const fetcher = mockFetch({ body: buildPack() });
    render(
      <EvidencePackToggle
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    expect(screen.getByTestId("view-compliance").getAttribute("data-active")).toBe(
      "true",
    );
    expect(screen.getByTestId("view-technical").getAttribute("data-active")).toBe(
      "false",
    );
    expect(screen.getByTestId("generate-pack-button").textContent).toContain(
      "FCA",
    );
  });

  it("switches to Technical view and shows technical CTA copy", () => {
    const fetcher = mockFetch({ body: buildPack() });
    render(
      <EvidencePackToggle
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    fireEvent.click(screen.getByTestId("view-technical"));
    expect(screen.getByTestId("view-technical").getAttribute("data-active")).toBe(
      "true",
    );
    expect(screen.getByTestId("generate-pack-button").textContent).toMatch(
      /Generate evidence pack/,
    );
  });

  it("Generate -> narrated loading -> compliance ok pane with download button", async () => {
    vi.useFakeTimers();
    const fetcher = mockFetch({ body: buildPack() });
    render(
      <EvidencePackToggle
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
        stepDelayMs={10}
      />,
    );

    fireEvent.click(screen.getByTestId("generate-pack-button"));
    // narrated loading should appear immediately
    expect(screen.getByTestId("pack-narrated-loading")).toBeTruthy();
    // step 0 'current'
    expect(
      screen.getByTestId("narrative-step-0").getAttribute("data-state"),
    ).toBe("current");

    // advance fake clock so the narrator ticks forward
    await act(async () => {
      vi.advanceTimersByTime(15);
      await Promise.resolve();
    });

    vi.useRealTimers();

    await waitFor(() => screen.getByTestId("compliance-view"));
    expect(screen.getByTestId("compliance-headline")).toBeTruthy();
    expect(screen.getByTestId("download-pdf-button")).toBeTruthy();
  });

  it("technical view renders hash table after generation", async () => {
    const fetcher = mockFetch({ body: buildPack() });
    render(
      <EvidencePackToggle
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
        initialView="technical"
        stepDelayMs={1}
      />,
    );
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    await waitFor(() => screen.getByTestId("technical-view"));
    expect(screen.getByTestId("pack-root-hash")).toBeTruthy();
    expect(screen.getByTestId("pack-anchor-tsa")).toBeTruthy();
  });

  it("technical view omits anchor block when pack.anchor is null", async () => {
    const fetcher = mockFetch({ body: buildPack({ anchor: null }) });
    render(
      <EvidencePackToggle
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
        initialView="technical"
        stepDelayMs={1}
      />,
    );
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    await waitFor(() => screen.getByTestId("technical-view"));
    expect(screen.queryByTestId("pack-anchor-tsa")).toBeNull();
  });

  it("compliance view describes a deferred anchor when status is deferred", async () => {
    const fetcher = mockFetch({
      body: buildPack({
        anchor: {
          anchor_id: "a-2",
          anchor_date: "2026-05-13T00:00:00+00:00",
          status: "deferred",
          root_hash: "f".repeat(64),
          tsa_identifier: "freetsa.org",
          tsr_bytes_b64: null,
          tsa_signature_b64: null,
          timestamped_at: null,
          anchored_at: "2026-05-15T21:08:51+00:00",
        },
      }),
    });
    render(
      <EvidencePackToggle
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
        stepDelayMs={1}
      />,
    );
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    await waitFor(() => screen.getByTestId("compliance-view"));
    expect(screen.getByTestId("compliance-view").textContent).toContain("deferred");
  });

  it("compliance view says 'not yet time-stamped' when anchor is missing", async () => {
    const fetcher = mockFetch({ body: buildPack({ anchor: null }) });
    render(
      <EvidencePackToggle
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
        stepDelayMs={1}
      />,
    );
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    await waitFor(() => screen.getByTestId("compliance-view"));
    expect(screen.getByTestId("compliance-view").textContent).toContain(
      "not yet time-stamped",
    );
  });

  it("technical view '(pending)' label when timestamped_at is null", async () => {
    const fetcher = mockFetch({
      body: buildPack({
        anchor: {
          anchor_id: "a-3",
          anchor_date: "2026-05-13T00:00:00+00:00",
          status: "deferred",
          root_hash: "f".repeat(64),
          tsa_identifier: "freetsa.org",
          tsr_bytes_b64: null,
          tsa_signature_b64: null,
          timestamped_at: null,
          anchored_at: "2026-05-15T21:08:51+00:00",
        },
      }),
    });
    render(
      <EvidencePackToggle
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
        initialView="technical"
        stepDelayMs={1}
      />,
    );
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    await waitFor(() => screen.getByTestId("pack-anchor-time"));
    expect(screen.getByTestId("pack-anchor-time").textContent).toContain("pending");
  });

  it("downloads a PDF blob (compliance view) on Download click", async () => {
    const fetcher = mockFetch({ body: buildPack() });
    render(
      <EvidencePackToggle
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
        stepDelayMs={1}
      />,
    );
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    await waitFor(() => screen.getByTestId("compliance-view"));
    fireEvent.click(screen.getByTestId("download-pdf-button"));
    await waitFor(() => expect(global.URL.createObjectURL).toHaveBeenCalled());
  });

  it("downloads a PDF blob (technical view) on Download click", async () => {
    const fetcher = mockFetch({ body: buildPack() });
    render(
      <EvidencePackToggle
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
        initialView="technical"
        stepDelayMs={1}
      />,
    );
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    await waitFor(() => screen.getByTestId("technical-view"));
    fireEvent.click(screen.getByTestId("download-pdf-button"));
    await waitFor(() => expect(global.URL.createObjectURL).toHaveBeenCalled());
  });

  it("surfaces a PDF download error when the API returns non-ok", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => buildPack(),
        blob: async () => new Blob(),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 502,
        json: async () => ({}),
        blob: async () => new Blob(),
      });
    render(
      <EvidencePackToggle
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
        stepDelayMs={1}
      />,
    );
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    await waitFor(() => screen.getByTestId("download-pdf-button"));
    fireEvent.click(screen.getByTestId("download-pdf-button"));
    await waitFor(() => screen.getByTestId("pdf-error"));
    expect(screen.getByTestId("pdf-error").textContent).toContain("502");
  });

  it("surfaces an error when Generate returns non-ok", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({}),
      blob: async () => new Blob(),
    });
    render(
      <EvidencePackToggle
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
        stepDelayMs={1}
      />,
    );
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    await waitFor(() => screen.getByTestId("pack-error"));
    expect(screen.getByTestId("pack-error").textContent).toContain("HTTP 503");
  });

  it("uses the default API URL when none is provided", () => {
    const fetcher = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => buildPack(),
      blob: async () => new Blob(),
    });
    render(
      <EvidencePackToggle
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    expect(screen.getByTestId("generate-pack-button")).toBeTruthy();
  });

  it("surfaces a thrown Generate error in the error state", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("boom"));
    render(
      <EvidencePackToggle
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
        stepDelayMs={1}
      />,
    );
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    await waitFor(() => screen.getByTestId("pack-error"));
    expect(screen.getByTestId("pack-error").textContent).toContain("boom");
  });

  it("surfaces a thrown Download error in the pdf-error state", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => buildPack(),
        blob: async () => new Blob(),
      })
      .mockRejectedValueOnce(new Error("blob-boom"));
    render(
      <EvidencePackToggle
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
        stepDelayMs={1}
      />,
    );
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    await waitFor(() => screen.getByTestId("download-pdf-button"));
    fireEvent.click(screen.getByTestId("download-pdf-button"));
    await waitFor(() => screen.getByTestId("pdf-error"));
    expect(screen.getByTestId("pdf-error").textContent).toContain("blob-boom");
  });

  it("narrated loading marks earlier steps as 'done' once the timer advances", async () => {
    vi.useFakeTimers();
    // The fetcher resolves only when we tell it to, so we can park
    // in the loading state long enough for the narrator's interval
    // to tick.
    let resolveFetch: (r: Response) => void = () => undefined;
    const fetcher = vi.fn(
      () =>
        new Promise<Response>((res) => {
          resolveFetch = res;
        }),
    );
    render(
      <EvidencePackToggle
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
        stepDelayMs={5}
      />,
    );

    fireEvent.click(screen.getByTestId("generate-pack-button"));
    expect(
      screen.getByTestId("narrative-step-0").getAttribute("data-state"),
    ).toBe("current");

    // Advance two ticks: step 0 -> done, step 1 -> done, step 2 -> current.
    await act(async () => {
      vi.advanceTimersByTime(20);
      await Promise.resolve();
    });
    expect(
      screen.getByTestId("narrative-step-0").getAttribute("data-state"),
    ).toBe("done");
    expect(
      screen.getByTestId("narrative-step-1").getAttribute("data-state"),
    ).toBe("done");

    // Advance well past the cap so the (i + 1 < N) -> false branch hits.
    await act(async () => {
      vi.advanceTimersByTime(200);
      await Promise.resolve();
    });
    // Last step is "current"; nothing remains pending.
    expect(
      screen.getByTestId("narrative-step-4").getAttribute("data-state"),
    ).toBe("current");

    // Now resolve the fetch so the component leaves the loading state.
    await act(async () => {
      resolveFetch({
        ok: true,
        status: 200,
        json: async () => buildPack(),
        blob: async () => new Blob(),
      } as unknown as Response);
      await Promise.resolve();
    });
    vi.useRealTimers();
    await waitFor(() => screen.getByTestId("compliance-view"));
  });

  it("technical view shows pdf-error when download fails", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => buildPack(),
        blob: async () => new Blob(),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 504,
        json: async () => ({}),
        blob: async () => new Blob(),
      });
    render(
      <EvidencePackToggle
        tenantId={TENANT_ID}
        scopeStart={SCOPE_START}
        scopeEnd={SCOPE_END}
        apiUrl="http://test.local"
        fetcher={fetcher as unknown as typeof fetch}
        initialView="technical"
        stepDelayMs={1}
      />,
    );
    fireEvent.click(screen.getByTestId("generate-pack-button"));
    await waitFor(() => screen.getByTestId("technical-view"));
    fireEvent.click(screen.getByTestId("download-pdf-button"));
    await waitFor(() => screen.getByTestId("pdf-error"));
    expect(screen.getByTestId("pdf-error").textContent).toContain("504");
  });
});
