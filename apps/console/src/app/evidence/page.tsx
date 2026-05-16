import Link from "next/link";
import { EvidencePack } from "@/components/EvidencePack";

const DEMO_TENANT_ID =
  process.env.NEXT_PUBLIC_FORENSA_DEMO_TENANT_ID ??
  "00000000-0000-0000-0000-000000000001";

// The seeded chain lives in 2026-05-13..14; we cover both anchored
// and recent days so the pack carries the day-1 RFC 3161 anchor.
const DEFAULT_SCOPE_START = "2026-05-13T00:00:00+00:00";
const DEFAULT_SCOPE_END = "2026-05-14T23:59:59+00:00";

export default function EvidencePage() {
  const scopeStart = process.env.NEXT_PUBLIC_FORENSA_SCOPE_START ?? DEFAULT_SCOPE_START;
  const scopeEnd = process.env.NEXT_PUBLIC_FORENSA_SCOPE_END ?? DEFAULT_SCOPE_END;
  return (
    <main style={{ padding: "2rem", fontFamily: "system-ui, sans-serif" }}>
      <p style={{ marginBottom: "1rem" }}>
        <Link
          href="/"
          data-testid="evidence-back-link"
          style={{ color: "#1e40af", textDecoration: "underline" }}
        >
          &larr; Back to receipts list
        </Link>
      </p>
      <h1>Evidence pack</h1>
      <p style={{ fontSize: "0.95rem", color: "#374151", marginBottom: "1.5rem" }}>
        Produce the tamper-evident regulator artifact for tenant{" "}
        <code style={{ fontFamily: "monospace" }}>{DEMO_TENANT_ID}</code>. The
        pack binds every receipt in the window plus the day&apos;s RFC 3161
        TSA proof under a single root hash.
      </p>
      <EvidencePack
        tenantId={DEMO_TENANT_ID}
        scopeStart={scopeStart}
        scopeEnd={scopeEnd}
      />
    </main>
  );
}
