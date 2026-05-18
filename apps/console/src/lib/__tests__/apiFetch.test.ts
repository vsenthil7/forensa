import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// DEFAULT_TOKEN is captured at module load. To exercise both
// branches (token present / token absent) we re-import the module
// after mutating process.env between tests.

describe("apiFetch", () => {
  const originalFetch = global.fetch;
  const originalToken = process.env.NEXT_PUBLIC_FORENSA_TOKEN;

  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200 } as Response);
  });

  afterEach(() => {
    global.fetch = originalFetch;
    if (originalToken === undefined) {
      delete process.env.NEXT_PUBLIC_FORENSA_TOKEN;
    } else {
      process.env.NEXT_PUBLIC_FORENSA_TOKEN = originalToken;
    }
    vi.resetModules();
  });

  it("passes the input through to global.fetch without auth when token is absent", async () => {
    delete process.env.NEXT_PUBLIC_FORENSA_TOKEN;
    vi.resetModules();
    const mod = await import("../apiFetch");
    await mod.apiFetch("/healthz");
    const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;
    expect(fetchMock).toHaveBeenCalledOnce();
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.has("Authorization")).toBe(false);
  });

  it("injects Authorization: Bearer <token> when the env var is set", async () => {
    process.env.NEXT_PUBLIC_FORENSA_TOKEN = "tok-xyz";
    vi.resetModules();
    const mod = await import("../apiFetch");
    await mod.apiFetch("/v1/receipts");
    const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe("Bearer tok-xyz");
  });

  it("does not overwrite a caller-supplied Authorization header", async () => {
    process.env.NEXT_PUBLIC_FORENSA_TOKEN = "tok-xyz";
    vi.resetModules();
    const mod = await import("../apiFetch");
    await mod.apiFetch("/v1/receipts", { headers: { Authorization: "Bearer caller" } });
    const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe("Bearer caller");
  });
});
