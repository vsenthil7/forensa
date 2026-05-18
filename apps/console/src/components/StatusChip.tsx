/**
 * Forensa Console — status chip (US-F29 AC-5).
 *
 * Renders a coloured pill for a receipt's chain-anchor state:
 *   - "anchored" -> green   (chained + RFC 3161 timestamped)
 *   - "pending"  -> amber   (signed, awaiting next anchor cycle)
 *   - "deferred" -> grey    (chain present, anchor deferred via tombstone)
 *
 * Status derivation from API fields:
 *   anchor_id present + tsr_b64 present  -> "anchored"
 *   anchor_id present + tsr_b64 missing  -> "deferred"  (tombstone path)
 *   anchor_id missing                    -> "pending"   (next anchor cycle)
 *
 * Per BR-14 AC-2 the operator must see human-meaningful status
 * without parsing JSON. The chip's textContent + colour are both
 * available to Playwright via data-testid="status-chip-<status>".
 */

export type ReceiptChainStatus = "anchored" | "pending" | "deferred";

export interface ReceiptAnchorShape {
  anchor_id?: string | null;
  tsr_b64?: string | null;
}

export function deriveReceiptStatus(r: ReceiptAnchorShape): ReceiptChainStatus {
  if (r.anchor_id && r.anchor_id.length > 0) {
    if (r.tsr_b64 && r.tsr_b64.length > 0) return "anchored";
    return "deferred";
  }
  return "pending";
}

const STATUS_PALETTE: Record<ReceiptChainStatus, { bg: string; fg: string; label: string }> = {
  anchored: { bg: "#dcfce7", fg: "#166534", label: "Anchored" },
  pending: { bg: "#fef3c7", fg: "#92400e", label: "Pending anchor" },
  deferred: { bg: "#e5e7eb", fg: "#374151", label: "Deferred" },
};

export interface StatusChipProps {
  status: ReceiptChainStatus;
}

export function StatusChip({ status }: StatusChipProps) {
  const { bg, fg, label } = STATUS_PALETTE[status];
  return (
    <span
      data-testid={`status-chip-${status}`}
      style={{
        display: "inline-block",
        padding: "0.15rem 0.55rem",
        borderRadius: "999px",
        fontSize: "0.75rem",
        fontWeight: 600,
        background: bg,
        color: fg,
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </span>
  );
}
