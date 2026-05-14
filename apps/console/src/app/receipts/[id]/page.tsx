"use client";

import { use } from "react";
import Link from "next/link";
import { ReceiptDetail } from "@/components/ReceiptDetail";

export default function ReceiptDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <main style={{ padding: "2rem", fontFamily: "system-ui, sans-serif" }}>
      <h1>Receipt</h1>
      <p>
        <Link href="/" style={{ color: "#2563eb" }}>Back to receipts list</Link>
      </p>
      <ReceiptDetail receiptId={id} />
    </main>
  );
}
