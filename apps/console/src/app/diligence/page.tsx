import { DiligenceWorkspace } from "@/components/DiligenceWorkspace";

const DEMO_TENANT_ID =
  process.env.NEXT_PUBLIC_FORENSA_DEMO_TENANT_ID ??
  "00000000-0000-0000-0000-000000000001";

export default function DiligencePage() {
  return (
    <main data-testid="diligence-page">
      <h1>M&amp;A diligence</h1>
      <p
        style={{
          color: "#374151",
          maxWidth: "44rem",
          marginBottom: "1.5rem",
        }}
      >
        Build a sealed multi-day evidence bundle bound by a single{" "}
        <code>ma_root_hash</code>. UC-07: target diligence turnaround of{" "}
        <strong>≤ 4 business hours</strong>.
      </p>
      <DiligenceWorkspace tenantId={DEMO_TENANT_ID} />
    </main>
  );
}
