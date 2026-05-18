"use client";

import { Suspense, use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ReceiptDetailTabs,
  parseTabFromHash,
  type DetailTab,
} from "@/components/ReceiptDetailTabs";

function ReceiptDetailInner({ id }: { id: string }) {
  const [tab, setTab] = useState<DetailTab>("summary");

  // Hydrate initial tab from URL hash on mount, and listen for
  // back/forward changes. Hash-based routing keeps deep-link AC met
  // without sessionStorage (BR-14 AC-2).
  useEffect(() => {
    /* v8 ignore start */
    if (typeof window === "undefined") return;
    /* v8 ignore stop */
    setTab(parseTabFromHash(window.location.hash));
    const onHashChange = () => setTab(parseTabFromHash(window.location.hash));
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const handleTabChange = useCallback((next: DetailTab) => {
    setTab(next);
    /* v8 ignore start */
    if (typeof window !== "undefined") {
      // Replace rather than push so each tab click doesn't fill
      // history; only the page itself is a history entry.
      const newHash = "#" + next;
      if (window.location.hash !== newHash) {
        history.replaceState(null, "", newHash);
      }
    }
    /* v8 ignore stop */
  }, []);

  return (
    <main data-testid="receipt-detail-page">
      <p style={{ marginBottom: "1rem" }}>
        <Link
          href="/receipts"
          data-testid="receipt-detail-back-link"
          style={{ color: "#1e40af", textDecoration: "underline" }}
        >
          ← Back to receipts
        </Link>
      </p>
      <h1>Receipt</h1>
      <ReceiptDetailTabs
        receiptId={id}
        initialTab={tab}
        onTabChange={handleTabChange}
      />
    </main>
  );
}

export default function ReceiptDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return (
    <Suspense fallback={<p data-testid="receipt-detail-fallback">Loading…</p>}>
      <ReceiptDetailInner id={id} />
    </Suspense>
  );
}
