"use client";

/**
 * /receipts route — Enterprise receipt timeline (SCR-F02, US-F29).
 *
 * Owns the URL-query <-> filter state mirroring per AC-3
 * (bookmarkable, back-button-recovers-state). The component
 * itself does all the actual filter / paging / sort work; this
 * page is just the URL adapter.
 */

import { Suspense, useCallback, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ReceiptsTimeline } from "@/components/ReceiptsTimeline";

const DEMO_TENANT_ID =
  process.env.NEXT_PUBLIC_FORENSA_DEMO_TENANT_ID ??
  "00000000-0000-0000-0000-000000000001";

function ReceiptsPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Convert ReadonlyURLSearchParams -> URLSearchParams so the
  // component can rebuild and compare reliably. useMemo so the
  // ref is stable for the component's `initialQuery` dependency.
  const initialQuery = useMemo(() => {
    const q = new URLSearchParams();
    searchParams.forEach((v, k) => q.append(k, v));
    return q;
  }, [searchParams]);

  const handleQueryChange = useCallback(
    (q: URLSearchParams) => {
      const next = q.toString();
      const here = "/receipts" + (next ? "?" + next : "");
      router.replace(here, { scroll: false });
    },
    [router],
  );

  return (
    <main data-testid="receipts-page">
      <header style={{ marginBottom: "1rem" }}>
        <h1 style={{ marginBottom: "0.25rem" }}>Receipts</h1>
        <p style={{ color: "#6b7280", margin: 0 }}>
          Every agent action, chained and signed.
        </p>
      </header>
      <ReceiptsTimeline
        tenantId={DEMO_TENANT_ID}
        initialQuery={initialQuery}
        onQueryChange={handleQueryChange}
      />
    </main>
  );
}

export default function ReceiptsPage() {
  // useSearchParams must be inside a Suspense boundary on the
  // App Router, otherwise prerender bails out.
  return (
    <Suspense fallback={<p data-testid="receipts-page-fallback">Loading…</p>}>
      <ReceiptsPageInner />
    </Suspense>
  );
}
