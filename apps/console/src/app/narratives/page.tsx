import { NarrativeViewer } from "@/components/NarrativeViewer";

const DEMO_TENANT_ID =
  process.env.NEXT_PUBLIC_FORENSA_DEMO_TENANT_ID ??
  "00000000-0000-0000-0000-000000000001";

export default function NarrativesPage() {
  return (
    <main data-testid="narratives-page">
      <h1>Narratives</h1>
      <p
        style={{
          color: "#374151",
          maxWidth: "44rem",
          marginBottom: "1.5rem",
        }}
      >
        Generate a regulator-ready plain-English summary of a receipt window.
        Powered by Gemini 2.5 Pro behind the 4-layer prompt-injection defence.
      </p>
      <NarrativeViewer tenantId={DEMO_TENANT_ID} />
    </main>
  );
}
