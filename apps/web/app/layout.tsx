import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "TraceForge",
  description: "Trace investigation",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-forge-base font-sans text-forge-text">
        <header className="flex items-center gap-8 border-b border-forge-border bg-forge-panel px-6 py-3.5">
          <a className="font-bold text-forge-accent no-underline" href="/traces">TraceForge</a>
          <nav className="flex gap-5"><a className="text-forge-muted no-underline hover:text-forge-text" href="/traces">Traces</a><a className="text-forge-muted no-underline hover:text-forge-text" href="/services">Services</a></nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
