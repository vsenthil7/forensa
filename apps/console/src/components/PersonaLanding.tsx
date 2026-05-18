"use client";

/**
 * Forensa Console — persona-aware landing (US-F28, SCR-F01).
 *
 * Acceptance:
 *   AC: 6 persona cards (P-COMP, P-AUD, P-SEC, P-COUNSEL, P-PLAT,
 *   P-ACQ — P-REG is a regulator and is a consumer of exports
 *   rather than a Console user, so it does not appear here) + an
 *   "Open my workspace" CTA each, routing to the persona-relevant
 *   first screen. Negative path: unauthenticated -> redirect to
 *   SCR-F09 login (Phase 10, so not enforced here).
 *
 * Anti-pattern guard
 * ------------------
 *   Each card's CTA is a `Link` to an absolute path that resolves
 *   on a cold load. We do NOT write the chosen persona into
 *   sessionStorage. The user can deep-link, bookmark, or share
 *   any console page without first visiting `/`.
 */

import Link from "next/link";

export interface Persona {
  code: string;
  title: string;
  pain: string;
  pitch: string;
  ctaLabel: string;
  ctaHref: string;
  testid: string;
}

export const PERSONAS: ReadonlyArray<Persona> = [
  {
    code: "P-COMP",
    title: "Compliance Officer",
    pain: "FCA inquiry response time",
    pitch: "Pull the regulator-ready evidence pack in minutes, not days.",
    ctaLabel: "Open evidence pack",
    ctaHref: "/evidence",
    testid: "persona-card-comp",
  },
  {
    code: "P-AUD",
    title: "Internal Auditor",
    pain: "Sample-pull time and chain verifiability",
    pitch: "Browse the timeline, drill in, verify hashes offline.",
    ctaLabel: "Open receipts timeline",
    ctaHref: "/receipts",
    testid: "persona-card-aud",
  },
  {
    code: "P-SEC",
    title: "Security Engineer",
    pain: "DORA tabletop turnaround",
    pitch: "Filter receipts by outcome and chain status; tabletop UI coming in CP9.55.",
    ctaLabel: "Open receipts timeline",
    ctaHref: "/receipts",
    testid: "persona-card-sec",
  },
  {
    code: "P-COUNSEL",
    title: "General Counsel",
    pain: "Discovery turnaround and chain-of-custody",
    pitch: "Pull the legal-hold evidence pack; diligence workspace ships CP9.56.",
    ctaLabel: "Open evidence pack",
    ctaHref: "/evidence",
    testid: "persona-card-counsel",
  },
  {
    code: "P-PLAT",
    title: "AI Platform Owner",
    pain: "Ingest reliability and the evidence story",
    pitch: "Operate Forensa across tenants. Status dashboard ships CP9.58.",
    ctaLabel: "Open receipts timeline",
    ctaHref: "/receipts",
    testid: "persona-card-plat",
  },
  {
    code: "P-ACQ",
    title: "M&A Acquirer",
    pain: "Diligence turnaround (11 weeks → 4 hours)",
    pitch: "Pull the diligence pack for the target's AI governance posture.",
    ctaLabel: "Open evidence pack",
    ctaHref: "/evidence",
    testid: "persona-card-acq",
  },
];

export interface PersonaLandingProps {
  /** Optional override; defaults to the canonical 6 personas above. */
  personas?: ReadonlyArray<Persona>;
}

export function PersonaLanding({ personas = PERSONAS }: PersonaLandingProps) {
  return (
    <section
      data-testid="persona-landing"
      style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}
    >
      <header>
        <h1 style={{ marginBottom: "0.25rem" }}>Welcome to Forensa</h1>
        <p style={{ color: "#374151", maxWidth: "40rem", marginTop: 0 }}>
          The cryptographic evidence layer for enterprise AI agents. Pick the
          card that matches how you&apos;ll use Forensa today.
        </p>
      </header>
      <div
        data-testid="persona-grid"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(16rem, 1fr))",
          gap: "1rem",
        }}
      >
        {personas.map((p) => (
          <article
            key={p.code}
            data-testid={p.testid}
            style={{
              padding: "1rem",
              border: "1px solid #e5e7eb",
              borderRadius: "0.6rem",
              background: "white",
              display: "flex",
              flexDirection: "column",
              gap: "0.5rem",
            }}
          >
            <div
              style={{
                fontFamily: "monospace",
                fontSize: "0.7rem",
                color: "#6b7280",
                letterSpacing: "0.05em",
              }}
            >
              {p.code}
            </div>
            <h2
              style={{
                margin: 0,
                fontSize: "1.05rem",
                color: "#111827",
                fontWeight: 600,
              }}
            >
              {p.title}
            </h2>
            <p
              style={{
                margin: 0,
                fontSize: "0.85rem",
                color: "#6b7280",
              }}
            >
              <strong style={{ color: "#374151" }}>Pain:</strong> {p.pain}
            </p>
            <p
              style={{
                margin: 0,
                fontSize: "0.9rem",
                color: "#374151",
                lineHeight: 1.45,
                flex: 1,
              }}
            >
              {p.pitch}
            </p>
            <Link
              href={p.ctaHref}
              data-testid={`${p.testid}-cta`}
              style={{
                marginTop: "0.5rem",
                padding: "0.5rem 0.85rem",
                borderRadius: "0.4rem",
                background: "#1e40af",
                color: "white",
                textDecoration: "none",
                fontWeight: 600,
                fontSize: "0.85rem",
                textAlign: "center",
              }}
            >
              {p.ctaLabel} →
            </Link>
          </article>
        ))}
      </div>
    </section>
  );
}
