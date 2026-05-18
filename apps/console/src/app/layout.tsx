import type { Metadata, Viewport } from "next";
import { TopNav } from "@/components/TopNav";
import { OfflineBanner } from "@/components/OfflineBanner";

export const metadata: Metadata = {
  title: "Forensa Console",
  description: "Cryptographic evidence layer for enterprise AI agents",
  manifest: "/manifest.webmanifest",
  applicationName: "Forensa",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Forensa",
  },
  icons: {
    icon: "/icon-192.svg",
    apple: "/icon-192.svg",
  },
};

export const viewport: Viewport = {
  themeColor: "#1e40af",
  width: "device-width",
  initialScale: 1,
};

const DEMO_TENANT_ID =
  process.env.NEXT_PUBLIC_FORENSA_DEMO_TENANT_ID ??
  "00000000-0000-0000-0000-000000000001";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Truncate the UUID for the chip display; tenant picker proper
  // arrives in Phase 10 CP10.1 per UC-10.
  const tenantLabel = DEMO_TENANT_ID.slice(0, 8) + "…";
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          fontFamily: "system-ui, -apple-system, sans-serif",
          background: "#f9fafb",
          color: "#111827",
          minHeight: "100vh",
        }}
      >
        <OfflineBanner />
        <TopNav tenantLabel={tenantLabel} />
        <div
          style={{
            padding: "1.5rem clamp(1rem, 4vw, 2.5rem)",
            maxWidth: "80rem",
            margin: "0 auto",
          }}
        >
          {children}
        </div>
        <ServiceWorkerRegistrar />
      </body>
    </html>
  );
}

/**
 * Registers the PWA service worker once on the client (US-F31 AC-2).
 *
 * Inlined as a <script> rather than a client component because (a)
 * the registration is a single side-effectful line and (b) keeping
 * it out of the React tree means there's no hydration coupling
 * with the rest of the layout. The graceful fallback per AC
 * negative path is the browser's own behaviour: if serviceWorker
 * is unavailable (private mode, old browsers), the page degrades
 * to a normal web app and the offline shell simply doesn't engage.
 */
function ServiceWorkerRegistrar() {
  const script = `
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', function () {
        navigator.serviceWorker.register('/sw.js').catch(function (err) {
          console.warn('Forensa SW registration failed:', err);
        });
      });
    }
  `;
  return <script dangerouslySetInnerHTML={{ __html: script }} />;
}
