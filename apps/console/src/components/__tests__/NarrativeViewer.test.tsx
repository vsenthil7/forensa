import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  NarrativeViewer,
  type NarrativeResponse,
} from "../NarrativeViewer";

const TENANT_ID = "45a9c68b-7d72-4f03-ba1c-600ffd5099a9";
const API_URL = "http://test.local";

function buildNarrative(over: Partial<NarrativeResponse> = {}): NarrativeResponse {
  return {
    narrative_text:
      "Between 2026-05-13 and 2026-05-14 the tenant's agents took 17 actions. " +
      "All were policy-compliant and chained without gap.",
    model_id: "gemini-2.5-pro",
    prompt_token_count: 312,
    completion_token_count: 184,
    content_hash: "c".repeat(64),
    prompt_hash: "p".repeat(64),
    pack_root_hash: "r".repeat(64),
    generated_at: "2026-05-13T10:00:00Z",
    ...over,
  };
}

describe("NarrativeViewer", () => {
  it("renders the form in idle state", () => {
    const fetcher = vi.fn();
    render(
      <NarrativeViewer
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    expect(screen.getByTestId("narrative-form")).toBeTruthy();
    expect(screen.getByTestId("narrative-submit")).toBeTruthy();
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("submitting without dates shows an error (validation)", () => {
    const fetcher = vi.fn();
    render(
      <NarrativeViewer
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    fireEvent.click(screen.getByTestId("narrative-submit"));
    expect(screen.getByTestId("narrative-error").textContent).toContain(
      "Pick both",
    );
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("happy path: shows loading then renders the narrative pane with model + tokens + hashes", async () => {
    const body = buildNarrative();
    const fetcher = vi.fn(async (_u: string | URL | Request, _init?: RequestInit) => ({
      ok: true,
      status: 200,
      json: async () => body,
    } as unknown as Response));
    render(
      <NarrativeViewer
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        initialScopeStart="2026-05-13"
        initialScopeEnd="2026-05-14"
      />,
    );
    fireEvent.click(screen.getByTestId("narrative-submit"));
    expect(screen.getByTestId("narrative-loading")).toBeTruthy();
    await waitFor(() => screen.getByTestId("narrative-pane"));
    expect(screen.getByTestId("narrative-text").textContent).toContain(
      "policy-compliant",
    );
    expect(screen.getByTestId("narrative-model").textContent).toBe("gemini-2.5-pro");
    expect(screen.getByTestId("narrative-tokens").textContent).toContain("312");
    expect(screen.getByTestId("narrative-pack-root").textContent).toBe(
      body.pack_root_hash,
    );
    // The URL had POST + query params, no body.
    const call = fetcher.mock.calls[0];
    const init = call[1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(String(call[0])).toContain("/v1/narratives");
    expect(String(call[0])).toContain(
      "tenant_id=" + encodeURIComponent(TENANT_ID),
    );
  });

  it("surfaces a defence-triggered 422 with an incident_id (detail object shape)", async () => {
    const fetcher = vi.fn(async () => ({
      ok: false,
      status: 422,
      json: async () => ({
        detail: { incident_id: "inc-12345", message: "Injection defence triggered" },
      }),
    } as unknown as Response));
    render(
      <NarrativeViewer
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        initialScopeStart="2026-05-13"
        initialScopeEnd="2026-05-14"
      />,
    );
    fireEvent.click(screen.getByTestId("narrative-submit"));
    await waitFor(() => screen.getByTestId("narrative-error"));
    expect(screen.getByTestId("narrative-error").textContent).toContain(
      "injection-defence",
    );
    expect(screen.getByTestId("narrative-error").textContent).toContain(
      "Injection defence triggered",
    );
    expect(screen.getByTestId("narrative-incident-id").textContent).toContain(
      "inc-12345",
    );
  });

  it("surfaces a 413 (too many receipts) error with the detail string", async () => {
    const fetcher = vi.fn(async () => ({
      ok: false,
      status: 413,
      json: async () => ({ detail: "Window has 5000 receipts; limit 1000" }),
    } as unknown as Response));
    render(
      <NarrativeViewer
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        initialScopeStart="2026-05-13"
        initialScopeEnd="2026-05-14"
      />,
    );
    fireEvent.click(screen.getByTestId("narrative-submit"));
    await waitFor(() => screen.getByTestId("narrative-error"));
    expect(screen.getByTestId("narrative-error").textContent).toContain(
      "5000 receipts",
    );
  });

  it("falls back to HTTP <status> when the error JSON has no detail at all", async () => {
    const fetcher = vi.fn(async () => ({
      ok: false,
      status: 502,
      json: async () => ({}),
    } as unknown as Response));
    render(
      <NarrativeViewer
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        initialScopeStart="2026-05-13"
        initialScopeEnd="2026-05-14"
      />,
    );
    fireEvent.click(screen.getByTestId("narrative-submit"));
    await waitFor(() => screen.getByTestId("narrative-error"));
    expect(screen.getByTestId("narrative-error").textContent).toContain("HTTP 502");
  });

  it("falls back to HTTP <status> when the error JSON parse throws", async () => {
    const fetcher = vi.fn(async () => ({
      ok: false,
      status: 502,
      json: async () => {
        throw new Error("malformed json");
      },
    } as unknown as Response));
    render(
      <NarrativeViewer
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        initialScopeStart="2026-05-13"
        initialScopeEnd="2026-05-14"
      />,
    );
    fireEvent.click(screen.getByTestId("narrative-submit"));
    await waitFor(() => screen.getByTestId("narrative-error"));
    expect(screen.getByTestId("narrative-error").textContent).toContain("HTTP 502");
  });

  it("handles a defence-detail object with message but no incident_id", async () => {
    const fetcher = vi.fn(async () => ({
      ok: false,
      status: 422,
      json: async () => ({ detail: { message: "fallback msg" } }),
    } as unknown as Response));
    render(
      <NarrativeViewer
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        initialScopeStart="2026-05-13"
        initialScopeEnd="2026-05-14"
      />,
    );
    fireEvent.click(screen.getByTestId("narrative-submit"));
    await waitFor(() => screen.getByTestId("narrative-error"));
    expect(screen.getByTestId("narrative-error").textContent).toContain(
      "fallback msg",
    );
    expect(screen.queryByTestId("narrative-incident-id")).toBeNull();
  });

  it("handles a defence-detail object with neither message nor incident_id", async () => {
    const fetcher = vi.fn(async () => ({
      ok: false,
      status: 422,
      json: async () => ({ detail: {} }),
    } as unknown as Response));
    render(
      <NarrativeViewer
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        initialScopeStart="2026-05-13"
        initialScopeEnd="2026-05-14"
      />,
    );
    fireEvent.click(screen.getByTestId("narrative-submit"));
    await waitFor(() => screen.getByTestId("narrative-error"));
    expect(screen.getByTestId("narrative-error").textContent).toContain("HTTP 422");
  });

  it("surfaces a thrown fetch error", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("network"));
    render(
      <NarrativeViewer
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        initialScopeStart="2026-05-13"
        initialScopeEnd="2026-05-14"
      />,
    );
    fireEvent.click(screen.getByTestId("narrative-submit"));
    await waitFor(() => screen.getByTestId("narrative-error"));
    expect(screen.getByTestId("narrative-error").textContent).toContain("network");
  });

  it("user can edit the scope fields after they're set", () => {
    const fetcher = vi.fn();
    render(
      <NarrativeViewer
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    fireEvent.change(screen.getByTestId("narrative-scope-start"), {
      target: { value: "2026-05-13" },
    });
    fireEvent.change(screen.getByTestId("narrative-scope-end"), {
      target: { value: "2026-05-14" },
    });
    expect(
      (screen.getByTestId("narrative-scope-start") as HTMLInputElement).value,
    ).toBe("2026-05-13");
  });

  it("uses the default API URL when none is provided", () => {
    const fetcher = vi.fn();
    render(
      <NarrativeViewer
        tenantId={TENANT_ID}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    expect(screen.getByTestId("narrative-form")).toBeTruthy();
  });
});
