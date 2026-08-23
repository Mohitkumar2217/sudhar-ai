import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sudhar AI — Operations Console",
  description: "Autonomous revenue recovery: detection, root cause, recovery actions, and a CFO copilot.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-body">{children}</body>
    </html>
  );
}
