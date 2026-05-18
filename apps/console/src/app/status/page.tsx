import { StatusDashboard } from "@/components/StatusDashboard";

const DEMO_TENANT_ID =
  process.env.NEXT_PUBLIC_FORENSA_DEMO_TENANT_ID ??
  "00000000-0000-0000-0000-000000000001";

export default function StatusPage() {
  return (
    <main data-testid="status-page">
      <h1>Status</h1>
      <p
        style={{
          color: "#374151",
          maxWidth: "44rem",
          marginBottom: "1.5rem",
        }}
      >
        Live API health from <code style={{ fontFamily: "monospace" }}>/healthz</code> +
        tenant-scoped operational metrics from{" "}
        <code style={{ fontFamily: "monospace" }}>/v1/metrics</code> (API-F15).
        Signing latency p50 / p95 / p99 ships with the Phase 11 observability
        sweep.
      </p>
      <StatusDashboard tenantId={DEMO_TENANT_ID} />
    </main>
  );
}
