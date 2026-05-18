import { act, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { isCacheStale, OfflineBanner } from "../OfflineBanner";

describe("isCacheStale", () => {
  it("returns false when cachedAtMs is null/undefined", () => {
    expect(isCacheStale(null, 1_000)).toBe(false);
    expect(isCacheStale(undefined, 1_000)).toBe(false);
  });

  it("returns false when cache age is under threshold", () => {
    const now = 1_000_000;
    const oneHour = 60 * 60 * 1000;
    expect(isCacheStale(now - oneHour, now)).toBe(false);
  });

  it("returns true when cache age exceeds the 24h default", () => {
    const now = 1_000_000_000;
    const twentyFiveHours = 25 * 60 * 60 * 1000;
    expect(isCacheStale(now - twentyFiveHours, now)).toBe(true);
  });

  it("accepts a custom threshold", () => {
    expect(isCacheStale(0, 5_000, 1_000)).toBe(true);
    expect(isCacheStale(0, 500, 1_000)).toBe(false);
  });
});

describe("OfflineBanner", () => {
  it("renders nothing when online + cache is fresh (or absent)", () => {
    const { container } = render(<OfflineBanner initialOnline={true} />);
    expect(container.querySelector("[data-testid='offline-banner']")).toBeNull();
  });

  it("renders the offline message when navigator reports offline (US-F31 AC-5 affordance)", () => {
    render(<OfflineBanner initialOnline={false} />);
    const banner = screen.getByTestId("offline-banner");
    expect(banner.getAttribute("data-online")).toBe("false");
    expect(banner.textContent).toContain("offline");
  });

  it("renders the stale message when online but cache is older than 24h", () => {
    const now = 2_000_000_000;
    const cachedAt = now - 25 * 60 * 60 * 1000;
    render(
      <OfflineBanner initialOnline={true} cachedAtMs={cachedAt} now={() => now} />,
    );
    const banner = screen.getByTestId("offline-banner");
    expect(banner.getAttribute("data-stale")).toBe("true");
    expect(banner.textContent).toContain("older than 24h");
  });

  it("reacts to the window 'offline' / 'online' events", () => {
    render(<OfflineBanner initialOnline={true} />);
    expect(screen.queryByTestId("offline-banner")).toBeNull();
    act(() => {
      window.dispatchEvent(new Event("offline"));
    });
    expect(screen.getByTestId("offline-banner")).toBeTruthy();
    act(() => {
      window.dispatchEvent(new Event("online"));
    });
    expect(screen.queryByTestId("offline-banner")).toBeNull();
  });

  it("defaults the online state from navigator.onLine when initialOnline is omitted", () => {
    const originalDescriptor = Object.getOwnPropertyDescriptor(
      window.navigator,
      "onLine",
    );
    try {
      Object.defineProperty(window.navigator, "onLine", {
        configurable: true,
        get: () => false,
      });
      render(<OfflineBanner />);
      expect(screen.getByTestId("offline-banner").getAttribute("data-online")).toBe(
        "false",
      );
    } finally {
      if (originalDescriptor) {
        Object.defineProperty(window.navigator, "onLine", originalDescriptor);
      }
    }
  });
});
