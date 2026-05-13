import { expect, test } from "@playwright/test";

test("API healthz returns ok status", async ({ request }) => {
  const response = await request.get("/healthz");
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body.status).toBe("ok");
  expect(body.version).toBeTruthy();
});

test("API rejects malformed event with 422", async ({ request }) => {
  const response = await request.post("/v1/events", { data: { not: "a valid event" } });
  expect(response.status()).toBe(422);
});
