import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PersonaLanding, PERSONAS } from "../PersonaLanding";

describe("PersonaLanding", () => {
  it("renders all 6 default persona cards", () => {
    render(<PersonaLanding />);
    expect(screen.getByTestId("persona-landing")).toBeTruthy();
    expect(screen.getByTestId("persona-grid")).toBeTruthy();
    for (const p of PERSONAS) {
      expect(screen.getByTestId(p.testid)).toBeTruthy();
      expect(screen.getByTestId(`${p.testid}-cta`)).toBeTruthy();
    }
  });

  it("each card CTA links to a non-empty, root-relative path (US-F28 AC)", () => {
    render(<PersonaLanding />);
    for (const p of PERSONAS) {
      const cta = screen.getByTestId(`${p.testid}-cta`);
      const href = cta.getAttribute("href") ?? "";
      expect(href.startsWith("/")).toBe(true);
    }
  });

  it("includes the canonical persona codes (P-COMP, P-AUD, P-SEC, P-COUNSEL, P-PLAT, P-ACQ)", () => {
    render(<PersonaLanding />);
    const codes = PERSONAS.map((p) => p.code);
    for (const c of ["P-COMP", "P-AUD", "P-SEC", "P-COUNSEL", "P-PLAT", "P-ACQ"]) {
      expect(codes).toContain(c);
    }
  });

  it("respects a custom personas prop", () => {
    render(
      <PersonaLanding
        personas={[
          {
            code: "P-X",
            title: "Test Persona",
            pain: "Test pain",
            pitch: "Test pitch",
            ctaLabel: "Open",
            ctaHref: "/x",
            testid: "persona-card-x",
          },
        ]}
      />,
    );
    expect(screen.getByTestId("persona-card-x")).toBeTruthy();
    expect(screen.queryByTestId("persona-card-comp")).toBeNull();
  });
});
