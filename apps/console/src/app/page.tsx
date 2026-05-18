import { HealthBadge } from "@/components/HealthBadge";
import { PersonaLanding } from "@/components/PersonaLanding";

export default function Home() {
  return (
    <main>
      <HealthBadge />
      <div style={{ marginTop: "1.5rem" }}>
        <PersonaLanding />
      </div>
    </main>
  );
}
