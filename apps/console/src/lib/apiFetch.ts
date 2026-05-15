/**
 * Small fetch helper for the Forensa Console.
 *
 * Why this exists
 * ---------------
 * The Forensa API requires ``Authorization: Bearer <token>`` on all
 * /v1/* routes (apps/api/auth/dependencies.py:get_principal). The
 * Console talks to the API from the browser, so each request needs
 * the token in the header.
 *
 * For the captioned demo + local dev, the token is passed in via the
 * env var ``NEXT_PUBLIC_FORENSA_TOKEN`` (read at build time by Next.js
 * for client bundles). Production deployments will replace this with
 * a real session-cookie / OIDC flow; this helper isolates the auth
 * detail so the swap is local to one file.
 *
 * For /healthz the bearer is omitted because the route is
 * unauthenticated; the helper sees an empty token and just passes the
 * call through.
 *
 * Shape: drop-in for ``fetch`` so existing components can swap with
 * minimal churn::
 *
 *   fetcher={apiFetch}    // instead of fetcher={fetch}
 */
const DEFAULT_TOKEN = process.env.NEXT_PUBLIC_FORENSA_TOKEN ?? "";

/**
 * fetch()-shaped wrapper that injects ``Authorization: Bearer <token>``
 * from ``NEXT_PUBLIC_FORENSA_TOKEN`` when the env var is set.
 *
 * Same signature as ``fetch``: ``apiFetch(input, init?)``. Use as a
 * drop-in for the components' ``fetcher`` prop.
 */
export function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers ?? {});
  if (DEFAULT_TOKEN && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${DEFAULT_TOKEN}`);
  }
  return fetch(input, { ...init, headers });
}
