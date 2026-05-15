/**
 * Forensa demo-script E2E spec (CP9.46 / IP #5).
 *
 * Walks the regulator's end-to-end verification flow via the live
 * FastAPI -- the same flow tools/demo.sh + tools/demo.ps1 + the
 * 5-minute submission video walk through. Catches regressions that
 * would break the on-stage demo before the hackathon judges see it.
 *
 * Test flow (mirrors tools/demo.sh exactly):
 *   1. GET /v1/evidence-packs?tenant_id=...&scope_start=...&scope_end=...
 *      -> verify JSON-LD body, capture root_hash + anchor_id
 *   2. GET /v1/evidence-packs with Accept: application/pdf
 *      -> verify content-type, sanity-check byte size
 *   3. GET /v1/anchors/{anchor_id} with Accept: application/timestamp-reply
 *      -> verify raw DER bytes, response headers, filename
 *   4. (Skipped) openssl ts -verify -- not portable inside Playwright;
 *      see tools/demo.sh for the full offline verification.
 *
 * Pre-flight (these MUST be set before invoking playwright):
 *   FORENSA_TENANT_ID    UUID of a seeded tenant with at least one anchor
 *   FORENSA_TOKEN        Bearer token (any string in dev stub mode)
 *
 * Recommended seed path:
 *   poetry run python scripts/seed_demo_data.py
 *   (Prints the FORENSA_TENANT_ID + FORENSA_TOKEN to export.)
 *
 * If either env var is unset the entire describe block skips with a
 * clear reason -- the spec does NOT auto-seed because seeding wipes
 * the database and that's not something a CI flow should do silently.
 *
 * Pattern inherited from the Verixa control-plane-ui demo specs
 * (sibling hackathon project, same author).
 */

import { expect, test } from "@playwright/test";

const TENANT_ID = process.env.FORENSA_TENANT_ID ?? "";
const TOKEN = process.env.FORENSA_TOKEN ?? "";
const SCOPE_START =
  process.env.FORENSA_SCOPE_START ?? "2026-05-13T00:00:00+00:00";
const SCOPE_END =
  process.env.FORENSA_SCOPE_END ?? "2026-05-15T23:59:59+00:00";

// Module-scope skip: if the seed env vars aren't set, the entire
// describe block is skipped with a single clear reason rather than
// each test failing individually with cryptic 401/403.
const seedAvailable = TENANT_ID.length > 0 && TOKEN.length > 0;

test.describe("Forensa demo-script regulator flow", () => {
  test.skip(
    !seedAvailable,
    "FORENSA_TENANT_ID and FORENSA_TOKEN must be set; run scripts/seed_demo_data.py first",
  );

  // Captured between steps so step 3 can reference step 1's anchor_id.
  let capturedAnchorId = "";
  let capturedRootHash = "";

  test("Step 1: GET evidence-pack returns JSON-LD with anchor", async ({
    request,
  }) => {
    const response = await request.get(
      `/v1/evidence-packs?tenant_id=${TENANT_ID}&scope_start=${encodeURIComponent(SCOPE_START)}&scope_end=${encodeURIComponent(SCOPE_END)}`,
      {
        headers: { Authorization: `Bearer ${TOKEN}` },
      },
    );
    expect(response.status(), await response.text()).toBe(200);
    expect(response.headers()["content-type"]).toContain("application/json");

    const body = await response.json();
    // Header shape (CP9.20 schema).
    expect(body.header).toBeTruthy();
    expect(body.header.tenant_id).toBe(TENANT_ID);
    expect(typeof body.header.receipt_count).toBe("number");
    expect(body.header.receipt_count).toBeGreaterThanOrEqual(0);
    // The integrity bind that the acquirer recomputes offline.
    expect(typeof body.root_hash).toBe("string");
    expect(body.root_hash).toMatch(/^[0-9a-f]{64}$/);
    capturedRootHash = body.root_hash;
    // Anchor block (CP9.22 schema). Required for step 3.
    expect(body.anchor).toBeTruthy();
    expect(typeof body.anchor.anchor_id).toBe("string");
    expect(body.anchor.anchor_id).toMatch(/^[0-9a-f-]{36}$/);
    capturedAnchorId = body.anchor.anchor_id;
    expect(["anchored", "deferred"]).toContain(body.anchor.status);
    // Tamper-evidence sanity: every receipt has a 64-char hex hash.
    expect(Array.isArray(body.receipts)).toBe(true);
    for (const receipt of body.receipts) {
      expect(receipt.receipt_hash).toMatch(/^[0-9a-f]{64}$/);
      expect(receipt.payload_hash).toMatch(/^[0-9a-f]{64}$/);
    }
  });

  test("Step 2: GET evidence-pack with Accept: application/pdf returns PDF bytes", async ({
    request,
  }) => {
    const response = await request.get(
      `/v1/evidence-packs?tenant_id=${TENANT_ID}&scope_start=${encodeURIComponent(SCOPE_START)}&scope_end=${encodeURIComponent(SCOPE_END)}`,
      {
        headers: {
          Authorization: `Bearer ${TOKEN}`,
          Accept: "application/pdf",
        },
      },
    );
    expect(response.status(), await response.text()).toBe(200);
    expect(response.headers()["content-type"]).toContain("application/pdf");
    // PDFs start with the magic %PDF- header. Sanity-check the first
    // few bytes rather than rendering the full PDF in a headless browser.
    const buffer = await response.body();
    expect(buffer.length).toBeGreaterThan(100); // not a trivial empty doc
    const magic = buffer.subarray(0, 4).toString("ascii");
    expect(magic).toBe("%PDF");
  });

  test("Step 3: GET anchor with Accept: application/timestamp-reply returns DER", async ({
    request,
  }) => {
    // This step depends on step 1 having captured an anchor_id.
    test.skip(
      capturedAnchorId.length === 0,
      "Step 1 did not capture an anchor_id; cannot fetch the TSR",
    );
    const response = await request.get(`/v1/anchors/${capturedAnchorId}`, {
      headers: {
        Authorization: `Bearer ${TOKEN}`,
        Accept: "application/timestamp-reply",
      },
    });
    // Anchors that are in 'deferred' status have no TSR bytes -> 406.
    // Anchors in 'anchored' status return the raw DER. Both are valid
    // pre-conditions for the demo; we assert the dichotomy.
    expect([200, 406]).toContain(response.status());
    if (response.status() === 200) {
      expect(response.headers()["content-type"]).toBe(
        "application/timestamp-reply",
      );
      const buffer = await response.body();
      // ASN.1 DER for a TimeStampResp starts with 0x30 (SEQUENCE tag).
      expect(buffer.length).toBeGreaterThan(0);
      expect(buffer[0]).toBe(0x30);
      // The X-Forensa-Anchor-Root-Hash header carries the bound root.
      const headerRootHash = response.headers()["x-forensa-anchor-root-hash"];
      expect(headerRootHash).toBeTruthy();
      expect(headerRootHash).toMatch(/^[0-9a-f]{64}$/);
      // Content-Disposition carries a filename suitable for piping into
      // 'openssl ts -verify -in <file>'.
      const dispo = response.headers()["content-disposition"];
      expect(dispo).toContain(`filename="anchor-${capturedAnchorId}.tsr"`);
    }
  });

  test("Step 4: chain integrity sanity via receipts + anchor stability", async ({
    request,
  }) => {
    // pack.root_hash binds a fresh generated_at on every request, so it
    // intentionally differs per call. The append-only invariant lives
    // on receipts[].receipt_hash + anchor.anchor_id which ARE stable.
    test.skip(
      capturedAnchorId.length === 0,
      "Step 1 did not capture an anchor_id",
    );
    const response = await request.get(
      `/v1/evidence-packs?tenant_id=${TENANT_ID}&scope_start=${encodeURIComponent(SCOPE_START)}&scope_end=${encodeURIComponent(SCOPE_END)}`,
      {
        headers: { Authorization: `Bearer ${TOKEN}` },
      },
    );
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.anchor.anchor_id).toBe(capturedAnchorId);
    // Every receipt hash is a 64-char hex sha-256 and the chain is
    // ordered by sequence ASC. The set is stable across requests.
    for (const receipt of body.receipts) {
      expect(receipt.receipt_hash).toMatch(/^[0-9a-f]{64}$/);
    }
  });
});

test.describe("Forensa healthz + auth surface (CP9.18c + CP9.45)", () => {
  test("GET /healthz returns ok without auth", async ({ request }) => {
    const response = await request.get("/healthz");
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.status).toBe("ok");
    expect(body.version).toBeTruthy();
    // CP9.10 narrative-provider transparency on healthz.
    expect(body.narrative_provider).toBeTruthy();
    expect(typeof body.narrative_is_fallback).toBe("boolean");
  });

  test("Unauthenticated POST /v1/events is rejected by the auth layer", async ({ request }) => {
    const response = await request.post("/v1/events", {
      data: {
        tenant_id: "00000000-0000-0000-0000-000000000000",
        kind: "tool_call",
      },
    });
    // CP9.18c: every non-public endpoint is gated by get_principal.
    // No bearer -> 401/403 in production, 503 in a bare-bones boot
    // when FORENSA_AUTH_SHARED_SECRET is not configured. All three
    // prove the body never reached the route's validator.
    expect([401, 403, 503]).toContain(response.status());
  });

  test("Malformed event body returns 422 (with auth)", async ({ request }) => {
    test.skip(
      !seedAvailable,
      "FORENSA_TOKEN required for the 422 path; 401 fires first without",
    );
    const response = await request.post("/v1/events", {
      headers: { Authorization: `Bearer ${TOKEN}` },
      data: { not: "a valid event" },
    });
    expect(response.status()).toBe(422);
  });
});
