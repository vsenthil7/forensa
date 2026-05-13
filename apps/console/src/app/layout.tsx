import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Forensa Console",
  description: "Cryptographic evidence layer for enterprise AI agents",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
