import { HealthBadge } from "@/components/HealthBadge";

export default function Home() {
  return (
    <main style={{ padding: "2rem", fontFamily: "system-ui, sans-serif" }}>
      <h1>Forensa Console</h1>
      <p>Cryptographic evidence layer for enterprise AI agents.</p>
      <HealthBadge />
    </main>
  );
}
