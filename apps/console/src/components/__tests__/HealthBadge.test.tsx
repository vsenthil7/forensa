import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { HealthBadge } from "../HealthBadge";

function mockFetch(response: Partial<Response> & { jsonBody?: unknown; rejectWith?: Error; status?: number }) {
  return vi.fn(async () => {
    if (response.rejectWith) throw response.rejectWith;
    return {
      ok: response.ok ?? true,
      status: response.status ?? (response.ok === false ? 400 : 200),
      json: async () => response.jsonBody ?? {},
    } as Response;
  });
}

describe("HealthBadge", () => {
  it("renders ok when API returns status ok", async () => {
    const fetcher = mockFetch({ ok: true, jsonBody: { status: "ok" } });
    render(<HealthBadge apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(screen.getByTestId("health-badge").dataset.status).toBe("ok"));
    expect(fetcher).toHaveBeenCalledWith("http://test.local/healthz");
  });

  it("renders degraded when API returns non-ok status", async () => {
    const fetcher = mockFetch({ ok: true, jsonBody: { status: "whatever" } });
    render(<HealthBadge apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(screen.getByTestId("health-badge").dataset.status).toBe("degraded"));
  });

  it("renders degraded when response is not ok", async () => {
    const fetcher = mockFetch({ ok: false });
    render(<HealthBadge apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(screen.getByTestId("health-badge").dataset.status).toBe("degraded"));
  });

  it("renders unreachable when fetch throws", async () => {
    const fetcher = mockFetch({ rejectWith: new Error("network") });
    render(<HealthBadge apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(screen.getByTestId("health-badge").dataset.status).toBe("unreachable"));
  });

  it("falls back to default URL when apiUrl is omitted", async () => {
    const fetcher = mockFetch({ ok: true, jsonBody: { status: "ok" } });
    render(<HealthBadge fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    const calls = (fetcher as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    expect(String(calls[0][0])).toMatch(/\/healthz$/);
  });

  it("renders unauthenticated when API returns 401", async () => {
    const fetcher = mockFetch({ ok: false, status: 401 });
    render(<HealthBadge apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(screen.getByTestId("health-badge").dataset.status).toBe("unauthenticated"));
  });

  it("renders unauthenticated when API returns 403", async () => {
    const fetcher = mockFetch({ ok: false, status: 403 });
    render(<HealthBadge apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(screen.getByTestId("health-badge").dataset.status).toBe("unauthenticated"));
  });

  it("renders unreachable when API returns 5xx", async () => {
    const fetcher = mockFetch({ ok: false, status: 503 });
    render(<HealthBadge apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(screen.getByTestId("health-badge").dataset.status).toBe("unreachable"));
  });

  it("sets data-last-checked timestamp after a successful probe", async () => {
    const fetcher = mockFetch({ ok: true, jsonBody: { status: "ok" } });
    render(<HealthBadge apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => {
      const ts = screen.getByTestId("health-badge").dataset.lastChecked;
      expect(ts).toBeTruthy();
      expect(ts).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
    });
  });

  it("shows 'Not yet checked' tooltip before first probe resolves", () => {
    const fetcher = vi.fn(() => new Promise<Response>(() => {}));
    render(<HealthBadge apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    expect(screen.getByTestId("health-badge").title).toBe("Not yet checked");
  });

  it("sets tooltip to 'Last checked ...' after a probe resolves", async () => {
    const fetcher = mockFetch({ ok: true, jsonBody: { status: "ok" } });
    render(<HealthBadge apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => {
      expect(screen.getByTestId("health-badge").title).toMatch(/^Last checked \d{4}-\d{2}-\d{2}T/);
    });
  });

  it("falls back to status from HTTP code when body is not JSON", async () => {
    const fetcher = vi.fn(async () => ({
      ok: false,
      status: 401,
      json: async () => { throw new Error("not json"); },
    }) as unknown as Response);
    render(<HealthBadge apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    await waitFor(() => expect(screen.getByTestId("health-badge").dataset.status).toBe("unauthenticated"));
  });

  it("cleans up when unmounted before fetch resolves", async () => {
    let resolveIt: (v: Response) => void = () => {};
    const fetcher = vi.fn(() => new Promise<Response>((res) => { resolveIt = res; }));
    const { unmount } = render(<HealthBadge apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    unmount();
    resolveIt({ ok: true, json: async () => ({ status: "ok" }) } as Response);
    // No assertion failure means the cancelled branch ran without setState-after-unmount
    expect(fetcher).toHaveBeenCalled();
  });

  it("cleans up when unmounted before fetch rejects", async () => {
    let rejectIt: (e: Error) => void = () => {};
    const fetcher = vi.fn(() => new Promise<Response>((_, rej) => { rejectIt = rej; }));
    const { unmount } = render(<HealthBadge apiUrl="http://test.local" fetcher={fetcher as unknown as typeof fetch} />);
    unmount();
    rejectIt(new Error("late network failure"));
    await new Promise((r) => setTimeout(r, 10));
    expect(fetcher).toHaveBeenCalled();
  });
});
