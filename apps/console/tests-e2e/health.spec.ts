/**
 * Forensa API minimal smoke tests.
 *
 * Kept distinct from demo_script.spec.ts -- this file is the
 * smallest viable smoke: it does NOT require FORENSA_TENANT_ID or
 * FORENSA_TOKEN, so it runs against any FastAPI bring-up (CI cold
 * start, fresh dev box, no seed).
 *
 * Heavier flow tests with seeded preconditions live in
 * demo_script.spec.ts and skip themselves when the seed env vars
 * are absent.
 */

import { expect, test } from "@playwright/test";

test("API healthz returns ok status", async ({ request }) => {
  const response = await request.get("/healthz");
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body.status).toBe("ok");
  expect(body.version).toBeTruthy();
});

test("Unauthenticated POST /v1/events is rejected by the auth layer", async ({
  request,
}) => {
  // CP9.18c wired get_principal into every non-public endpoint.
  // Without a bearer token the request is rejected before the body
  // validator runs. The exact status depends on whether the auth
  // layer is fully configured: 401 / 403 in production, 503 in a
  // bare-bones dev boot (no FORENSA_AUTH_SHARED_SECRET set). All
  // three answers prove the body never got validated, which is the
  // assertion this smoke test is making.
  const response = await request.post("/v1/events", {
    data: { not: "a valid event" },
  });
  expect([401, 403, 503]).toContain(response.status());
});
