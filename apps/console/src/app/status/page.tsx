import { StatusDashboard } from "@/components/StatusDashboard";

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
        Live API health + narrative-client transparency from{" "}
        <code style={{ fontFamily: "monospace" }}>/healthz</code>. Operational
        metrics (ingest rate, signing latency, anchor success/failure) ship
        with API-F15 in the v2.0 forward queue.
      </p>
      <StatusDashboard />
    </main>
  );
}
