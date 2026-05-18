import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusChip, deriveReceiptStatus } from "../StatusChip";

describe("deriveReceiptStatus", () => {
  it("returns 'anchored' when anchor_id and tsr_b64 are both present", () => {
    expect(deriveReceiptStatus({ anchor_id: "a", tsr_b64: "t" })).toBe("anchored");
  });

  it("returns 'deferred' when anchor_id is present but tsr_b64 is missing", () => {
    expect(deriveReceiptStatus({ anchor_id: "a", tsr_b64: null })).toBe("deferred");
    expect(deriveReceiptStatus({ anchor_id: "a" })).toBe("deferred");
    expect(deriveReceiptStatus({ anchor_id: "a", tsr_b64: "" })).toBe("deferred");
  });

  it("returns 'pending' when anchor_id is missing or empty", () => {
    expect(deriveReceiptStatus({})).toBe("pending");
    expect(deriveReceiptStatus({ anchor_id: null })).toBe("pending");
    expect(deriveReceiptStatus({ anchor_id: "" })).toBe("pending");
  });
});

describe("StatusChip", () => {
  it.each(["anchored", "pending", "deferred"] as const)(
    "renders the %s palette",
    (status) => {
      render(<StatusChip status={status} />);
      expect(screen.getByTestId(`status-chip-${status}`)).toBeTruthy();
    },
  );

  it("uses human-readable labels (not raw status keys)", () => {
    render(<StatusChip status="pending" />);
    expect(screen.getByTestId("status-chip-pending").textContent).toBe(
      "Pending anchor",
    );
  });
});
