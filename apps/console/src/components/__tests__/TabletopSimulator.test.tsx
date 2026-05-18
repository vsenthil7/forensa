import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  TabletopSimulator,
  type TabletopResult,
} from "../TabletopSimulator";

const TENANT_ID = "45a9c68b-7d72-4f03-ba1c-600ffd5099a9";
const BUNDLE_ID = "11111111-2222-3333-4444-555555555555";
const API_URL = "http://test.local";

function validScenarioJson(): string {
  return JSON.stringify({
    name: "test-scenario",
    tenant_id: TENANT_ID,
    policy_bundle_id: BUNDLE_ID,
    actions: [
      { label: "a1", action: { type: "x" } },
      { label: "a2", action: { type: "y" } },
    ],
  });
}

function buildResult(over: Partial<TabletopResult> = {}): TabletopResult {
  return {
    scenario: {
      name: "test-scenario",
      tenant_id: TENANT_ID,
      policy_bundle_id: BUNDLE_ID,
      actions: [
        { label: "a1", action: { type: "x" } },
        { label: "a2", action: { type: "y" } },
      ],
    },
    bundle_id: BUNDLE_ID,
    bundle_version: "1.0.0",
    bundle_content_hash: "c".repeat(64),
    action_results: [
      { label: "a1", decision: "allow", reason: "policy ok", errored: false },
      { label: "a2", decision: "deny", reason: "amount over limit", errored: false },
    ],
    summary: { total: 2, allow: 1, deny: 1, escalate: 0, errored: 0 },
    ...over,
  };
}

describe("TabletopSimulator", () => {
  it("renders the empty form in idle state", () => {
    const fetcher = vi.fn();
    render(
      <TabletopSimulator
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    expect(screen.getByTestId("tabletop-simulator")).toBeTruthy();
    expect(screen.getByTestId("tabletop-scenario-input")).toBeTruthy();
    expect(screen.getByTestId("tabletop-run")).toBeTruthy();
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("Load sample populates the textarea with a valid skeleton", () => {
    const fetcher = vi.fn();
    render(
      <TabletopSimulator
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    fireEvent.click(screen.getByTestId("tabletop-load-sample"));
    const ta = screen.getByTestId("tabletop-scenario-input") as HTMLTextAreaElement;
    expect(ta.value).toContain(TENANT_ID);
    expect(ta.value).toContain("policy_bundle_id");
  });

  it("running with an empty textarea surfaces the validation error", () => {
    const fetcher = vi.fn();
    render(
      <TabletopSimulator
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    fireEvent.click(screen.getByTestId("tabletop-run"));
    expect(screen.getByTestId("tabletop-error").textContent).toContain("Paste");
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("running with malformed JSON surfaces the parse error", () => {
    const fetcher = vi.fn();
    render(
      <TabletopSimulator
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        initialJson="{not valid"
      />,
    );
    fireEvent.click(screen.getByTestId("tabletop-run"));
    expect(screen.getByTestId("tabletop-error").textContent).toContain(
      "Invalid JSON",
    );
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("happy path: posts the scenario and renders verdicts + summary", async () => {
    const result = buildResult();
    const fetcher = vi.fn(async (_u: string | URL | Request, _init?: RequestInit) => ({
      ok: true,
      status: 200,
      json: async () => result,
    } as unknown as Response));
    render(
      <TabletopSimulator
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        initialJson={validScenarioJson()}
      />,
    );
    fireEvent.click(screen.getByTestId("tabletop-run"));
    expect(screen.getByTestId("tabletop-loading")).toBeTruthy();
    await waitFor(() => screen.getByTestId("tabletop-result"));
    // Bundle metadata visible
    expect(screen.getByTestId("tabletop-result-bundle").textContent).toContain(
      "1.0.0",
    );
    // Each action row + a decision pill present
    expect(screen.getByTestId("tabletop-action-row-0")).toBeTruthy();
    expect(screen.getByTestId("tabletop-action-row-1")).toBeTruthy();
    expect(screen.getAllByTestId("decision-allow").length).toBeGreaterThan(0);
    expect(screen.getAllByTestId("decision-deny").length).toBeGreaterThan(0);
    // Summary stats present
    expect(screen.getByTestId("tabletop-summary-total").textContent).toContain("2");
    expect(screen.getByTestId("tabletop-summary-allow").textContent).toContain("1");
    expect(screen.getByTestId("tabletop-summary-deny").textContent).toContain("1");

    // Posted body is the scenario JSON we filled in
    const call = fetcher.mock.calls[0];
    const init = call[1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(String(call[0])).toContain("/v1/tabletop/simulate");
    const sent = JSON.parse(init.body as string);
    expect(sent.tenant_id).toBe(TENANT_ID);
  });

  it("surfaces an errored action row + the ERROR decision pill", async () => {
    const result = buildResult({
      action_results: [
        { label: "a1", decision: null, reason: "adapter crashed", errored: true },
      ],
      summary: { total: 1, allow: 0, deny: 0, escalate: 0, errored: 1 },
    });
    const fetcher = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => result,
    } as unknown as Response));
    render(
      <TabletopSimulator
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        initialJson={validScenarioJson()}
      />,
    );
    fireEvent.click(screen.getByTestId("tabletop-run"));
    await waitFor(() => screen.getByTestId("tabletop-result"));
    expect(screen.getByTestId("decision-errored")).toBeTruthy();
    expect(screen.getByTestId("tabletop-action-row-0").textContent).toContain(
      "adapter crashed",
    );
    expect(screen.getByTestId("tabletop-summary-errored").textContent).toContain("1");
  });

  it("renders an escalate decision with the right pill", async () => {
    const result = buildResult({
      action_results: [
        { label: "a1", decision: "escalate", reason: "needs human review", errored: false },
      ],
      summary: { total: 1, allow: 0, deny: 0, escalate: 1, errored: 0 },
    });
    const fetcher = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => result,
    } as unknown as Response));
    render(
      <TabletopSimulator
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        initialJson={validScenarioJson()}
      />,
    );
    fireEvent.click(screen.getByTestId("tabletop-run"));
    await waitFor(() => screen.getByTestId("tabletop-result"));
    expect(screen.getByTestId("decision-escalate")).toBeTruthy();
  });

  it("renders '—' for a null reason on a non-errored verdict", async () => {
    const result = buildResult({
      action_results: [
        { label: "a1", decision: "allow", reason: null, errored: false },
      ],
      summary: { total: 1, allow: 1, deny: 0, escalate: 0, errored: 0 },
    });
    const fetcher = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => result,
    } as unknown as Response));
    render(
      <TabletopSimulator
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        initialJson={validScenarioJson()}
      />,
    );
    fireEvent.click(screen.getByTestId("tabletop-run"));
    await waitFor(() => screen.getByTestId("tabletop-result"));
    expect(screen.getByTestId("tabletop-action-row-0").textContent).toContain("—");
  });

  it("renders an unknown-decision pill when the API returns a decision string we don't have a palette for", async () => {
    const result = buildResult({
      action_results: [
        { label: "a1", decision: "novel-state", reason: "future expansion", errored: false },
      ],
      summary: { total: 1, allow: 0, deny: 0, escalate: 0, errored: 0 },
    });
    const fetcher = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => result,
    } as unknown as Response));
    render(
      <TabletopSimulator
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        initialJson={validScenarioJson()}
      />,
    );
    fireEvent.click(screen.getByTestId("tabletop-run"));
    await waitFor(() => screen.getByTestId("tabletop-result"));
    expect(screen.getByTestId("decision-novel-state")).toBeTruthy();
  });

  it("renders 'unknown' when decision is null but not errored", async () => {
    const result = buildResult({
      action_results: [
        { label: "a1", decision: null, reason: "no adapter response", errored: false },
      ],
      summary: { total: 1, allow: 0, deny: 0, escalate: 0, errored: 0 },
    });
    const fetcher = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => result,
    } as unknown as Response));
    render(
      <TabletopSimulator
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        initialJson={validScenarioJson()}
      />,
    );
    fireEvent.click(screen.getByTestId("tabletop-run"));
    await waitFor(() => screen.getByTestId("tabletop-result"));
    expect(screen.getByTestId("decision-unknown")).toBeTruthy();
  });

  it("surfaces an HTTP error status", async () => {
    const fetcher = vi.fn(async () => ({
      ok: false,
      status: 422,
      json: async () => ({}),
    } as unknown as Response));
    render(
      <TabletopSimulator
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        initialJson={validScenarioJson()}
      />,
    );
    fireEvent.click(screen.getByTestId("tabletop-run"));
    await waitFor(() => screen.getByTestId("tabletop-error"));
    expect(screen.getByTestId("tabletop-error").textContent).toContain("422");
  });

  it("surfaces a thrown fetch error", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("network"));
    render(
      <TabletopSimulator
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
        initialJson={validScenarioJson()}
      />,
    );
    fireEvent.click(screen.getByTestId("tabletop-run"));
    await waitFor(() => screen.getByTestId("tabletop-error"));
    expect(screen.getByTestId("tabletop-error").textContent).toContain("network");
  });

  it("the textarea reflects user edits", () => {
    const fetcher = vi.fn();
    render(
      <TabletopSimulator
        tenantId={TENANT_ID}
        apiUrl={API_URL}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    const ta = screen.getByTestId("tabletop-scenario-input") as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "{}" } });
    expect(ta.value).toBe("{}");
  });

  it("uses the default API URL when none is provided", () => {
    const fetcher = vi.fn();
    render(
      <TabletopSimulator
        tenantId={TENANT_ID}
        fetcher={fetcher as unknown as typeof fetch}
      />,
    );
    expect(screen.getByTestId("tabletop-simulator")).toBeTruthy();
  });
});
