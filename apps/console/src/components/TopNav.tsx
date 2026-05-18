"use client";

/**
 * Forensa Console — top navigation (BR-14 AC-2, SCR-F01..F10).
 *
 * Pattern: list-views-as-top-nav.
 * --------------------------------
 *   Every top-nav link goes directly to a list view that always
 *   works on a cold page load. No sessionStorage tracking an
 *   "active receipt" or "active intake" for deep-link recovery.
 *
 *   See BR-14 AC-2 in BRD.md and the mendoraci CP-9 cautionary
 *   tale referenced in `_archive/`.
 *
 * Each link's `data-testid` follows the convention
 * `topnav-link-<route>` so Playwright specs can drive them
 * without depending on label copy.
 *
 * Items intentionally only include surfaces that exist today
 * (CP9.52) or are explicitly planned in the v2.0 forward queue:
 *   /              -> Persona landing (SCR-F01, US-F28)
 *   /receipts      -> Enterprise timeline (SCR-F02, US-F29)
 *   /evidence      -> Evidence pack (SCR-F04, US-F19)
 * Future screens (SCR-F05..F10) are added as their CPs land per
 * the v2.0 forward queue (CP9.53, 9.55..9.58).
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

export interface TopNavItem {
  href: string;
  label: string;
  testid: string;
  /** PLANNED in v2.0 forward queue but not yet wired. Renders disabled. */
  planned?: boolean;
}

export const DEFAULT_NAV_ITEMS: ReadonlyArray<TopNavItem> = [
  { href: "/", label: "Home", testid: "topnav-link-home" },
  { href: "/receipts", label: "Receipts", testid: "topnav-link-receipts" },
  { href: "/evidence", label: "Evidence", testid: "topnav-link-evidence" },
  { href: "/anchors", label: "Anchors", testid: "topnav-link-anchors" },
  { href: "/diligence", label: "Diligence", testid: "topnav-link-diligence" },
  { href: "/narratives", label: "Narratives", testid: "topnav-link-narratives" },
  { href: "/tabletop", label: "Tabletop", testid: "topnav-link-tabletop" },
  { href: "/status", label: "Status", testid: "topnav-link-status" },
];

export interface TopNavProps {
  items?: ReadonlyArray<TopNavItem>;
  /** Tenant id label shown on the right (placeholder for tenant picker). */
  tenantLabel?: string;
}

/** Returns true when `pathname` matches `href` exactly or is a child route. */
export function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(href + "/");
}

export function TopNav({ items = DEFAULT_NAV_ITEMS, tenantLabel }: TopNavProps) {
  const pathname = usePathname() ?? "/";
  return (
    <header
      data-testid="topnav"
      role="banner"
      style={{
        display: "flex",
        alignItems: "center",
        gap: "1rem",
        padding: "0.75rem 1.25rem",
        borderBottom: "1px solid #e5e7eb",
        background: "white",
        flexWrap: "wrap",
      }}
    >
      <Link
        href="/"
        data-testid="topnav-logo"
        style={{
          fontWeight: 700,
          color: "#111827",
          textDecoration: "none",
          fontSize: "1.05rem",
          letterSpacing: "-0.01em",
        }}
      >
        Forensa
      </Link>
      <nav
        aria-label="Primary"
        data-testid="topnav-nav"
        style={{ display: "flex", gap: "0.25rem", flexWrap: "wrap", flex: 1 }}
      >
        {items.map((item) => {
          const active = isActive(pathname, item.href);
          const baseStyle: React.CSSProperties = {
            padding: "0.4rem 0.7rem",
            borderRadius: "0.4rem",
            textDecoration: "none",
            fontSize: "0.9rem",
            fontWeight: active ? 600 : 500,
          };
          if (item.planned) {
            return (
              <span
                key={item.href}
                data-testid={item.testid}
                data-planned="true"
                aria-disabled="true"
                title="Planned in a future Checkpoint (v2.0 forward queue)"
                style={{
                  ...baseStyle,
                  color: "#9ca3af",
                  cursor: "not-allowed",
                  background: "transparent",
                }}
              >
                {item.label}
              </span>
            );
          }
          return (
            <Link
              key={item.href}
              href={item.href}
              data-testid={item.testid}
              data-active={active ? "true" : "false"}
              style={{
                ...baseStyle,
                color: active ? "#1e40af" : "#374151",
                background: active ? "#eff6ff" : "transparent",
              }}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      {tenantLabel ? (
        <span
          data-testid="topnav-tenant-label"
          title="Tenant picker arrives in Phase 10 CP10.1 (UC-10)"
          style={{
            padding: "0.3rem 0.6rem",
            border: "1px solid #e5e7eb",
            borderRadius: "999px",
            fontSize: "0.8rem",
            color: "#4b5563",
            background: "#f9fafb",
            fontFamily: "monospace",
          }}
        >
          {tenantLabel}
        </span>
      ) : null}
    </header>
  );
}
