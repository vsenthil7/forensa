import { AnchorsList } from "@/components/AnchorsList";

const DEMO_TENANT_ID =
  process.env.NEXT_PUBLIC_FORENSA_DEMO_TENANT_ID ??
  "00000000-0000-0000-0000-000000000001";

export default function AnchorsPage() {
  return (
    <main data-testid="anchors-page">
      <h1>Anchors</h1>
      <p
        style={{
          color: "#374151",
          maxWidth: "40rem",
          marginBottom: "1.5rem",
        }}
      >
        One RFC 3161 timestamp anchor per day. Click <em>Download TSR</em> to
        get the raw DER bytes and verify offline with{" "}
        <code>openssl ts -verify</code>.
      </p>
      <AnchorsList tenantId={DEMO_TENANT_ID} />
    </main>
  );
}
