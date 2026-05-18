import { TabletopSimulator } from "@/components/TabletopSimulator";

const DEMO_TENANT_ID =
  process.env.NEXT_PUBLIC_FORENSA_DEMO_TENANT_ID ??
  "00000000-0000-0000-0000-000000000001";

export default function TabletopPage() {
  return (
    <main data-testid="tabletop-page">
      <h1>Tabletop</h1>
      <p
        style={{
          color: "#374151",
          maxWidth: "44rem",
          marginBottom: "1.5rem",
        }}
      >
        Replay synthetic actions through a candidate policy bundle. Nothing
        is persisted; nothing is written to the chain. DORA Article 30
        tabletop drill.
      </p>
      <TabletopSimulator tenantId={DEMO_TENANT_ID} />
    </main>
  );
}
