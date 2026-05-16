import { HealthBadge } from "@/components/HealthBadge";
import { ReceiptList } from "@/components/ReceiptList";
import Link from "next/link";

const DEMO_TENANT_ID =
  process.env.NEXT_PUBLIC_FORENSA_DEMO_TENANT_ID ??
  "00000000-0000-0000-0000-000000000001";

export default function Home() {
  return (
    <main style={{ padding: "2rem", fontFamily: "system-ui, sans-serif" }}>
      <h1>Forensa Console</h1>
      <p>Cryptographic evidence layer for enterprise AI agents.</p>
      <HealthBadge />
      <section style={{ marginTop: "2rem" }}>
        <h2>Receipts</h2>
        <p style={{ fontSize: "0.9rem", color: "#6b7280" }}>
          Append-only evidence chain for tenant{" "}
          <code style={{ fontFamily: "monospace" }}>{DEMO_TENANT_ID}</code>.
        </p>
        <ReceiptList tenantId={DEMO_TENANT_ID} />
      </section>
      <section style={{ marginTop: "2rem" }}>
        <Link
          href="/evidence"
          data-testid="nav-evidence-link"
          style={{
            display: "inline-block",
            padding: "0.5rem 1rem",
            borderRadius: "0.5rem",
            backgroundColor: "#1e40af",
            color: "white",
            textDecoration: "none",
            fontWeight: 600,
          }}
        >
          Generate evidence pack &rarr;
        </Link>
      </section>
    </main>
  );
}
