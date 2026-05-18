import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TopNav, DEFAULT_NAV_ITEMS, isActive } from "../TopNav";

// next/navigation usePathname needs mocking in jsdom.
vi.mock("next/navigation", () => ({
  usePathname: vi.fn(),
}));

import { usePathname } from "next/navigation";

const mockedUsePathname = vi.mocked(usePathname);

describe("isActive", () => {
  it("matches root exactly", () => {
    expect(isActive("/", "/")).toBe(true);
    expect(isActive("/receipts", "/")).toBe(false);
  });

  it("matches exact non-root", () => {
    expect(isActive("/receipts", "/receipts")).toBe(true);
  });

  it("matches child route as active parent", () => {
    expect(isActive("/receipts/abc", "/receipts")).toBe(true);
  });

  it("does not match unrelated routes", () => {
    expect(isActive("/evidence", "/receipts")).toBe(false);
  });
});

describe("TopNav", () => {
  it("renders the logo + default nav items", () => {
    mockedUsePathname.mockReturnValue("/");
    render(<TopNav />);
    expect(screen.getByTestId("topnav-logo")).toBeTruthy();
    for (const item of DEFAULT_NAV_ITEMS) {
      expect(screen.getByTestId(item.testid)).toBeTruthy();
    }
  });

  it("marks the home link active on the root path", () => {
    mockedUsePathname.mockReturnValue("/");
    render(<TopNav />);
    const home = screen.getByTestId("topnav-link-home");
    expect(home.getAttribute("data-active")).toBe("true");
  });

  it("marks the receipts link active when on /receipts/[id]", () => {
    mockedUsePathname.mockReturnValue("/receipts/abc123");
    render(<TopNav />);
    expect(screen.getByTestId("topnav-link-receipts").getAttribute("data-active")).toBe(
      "true",
    );
    expect(screen.getByTestId("topnav-link-evidence").getAttribute("data-active")).toBe(
      "false",
    );
  });

  it("renders planned links as disabled spans with aria-disabled", () => {
    mockedUsePathname.mockReturnValue("/");
    render(<TopNav />);
    const anchors = screen.getByTestId("topnav-link-anchors");
    expect(anchors.getAttribute("aria-disabled")).toBe("true");
    expect(anchors.getAttribute("data-planned")).toBe("true");
    expect(anchors.tagName.toLowerCase()).toBe("span");
  });

  it("renders the tenant label chip when provided", () => {
    mockedUsePathname.mockReturnValue("/");
    render(<TopNav tenantLabel="00000000…" />);
    const chip = screen.getByTestId("topnav-tenant-label");
    expect(chip.textContent).toContain("00000000");
  });

  it("does not render the tenant chip when label is undefined", () => {
    mockedUsePathname.mockReturnValue("/");
    render(<TopNav />);
    expect(screen.queryByTestId("topnav-tenant-label")).toBeNull();
  });

  it("falls back to root path when usePathname returns null", () => {
    mockedUsePathname.mockReturnValue(null as unknown as string);
    render(<TopNav />);
    expect(screen.getByTestId("topnav-link-home").getAttribute("data-active")).toBe(
      "true",
    );
  });

  it("honours a custom items list (renders only those, including a non-planned item)", () => {
    mockedUsePathname.mockReturnValue("/x");
    render(
      <TopNav
        items={[
          { href: "/x", label: "X", testid: "topnav-link-x" },
        ]}
      />,
    );
    expect(screen.getByTestId("topnav-link-x")).toBeTruthy();
    expect(screen.queryByTestId("topnav-link-receipts")).toBeNull();
  });
});
